from __future__ import annotations

from typing import Any

import pyomo.environ as pyo
from pydantic import BaseModel, ConfigDict

from gb_bess_revenue_stack.config.models import AssetConfig, SolverConfig
from gb_bess_revenue_stack.markets.eac_prices import EACPriceCell, EACPriceMatrix
from gb_bess_revenue_stack.optimisation.inputs import TerminalSocPolicy, build_dispatch_input
from gb_bess_revenue_stack.optimisation.model_factory import build_energy_dispatch_model
from gb_bess_revenue_stack.optimisation.results import extract_dispatch_result
from gb_bess_revenue_stack.optimisation.solve import SolverDiagnostics, solve_dispatch_model
from gb_bess_revenue_stack.schemas.market import DirectionModelLabel, WholesalePricePoint


class MarketStackServiceComponent(BaseModel):
    """Aggregated service result preserving source labels and caveats."""

    model_config = ConfigDict(extra="forbid")

    product_source_label: str | None
    product_model_label: str
    direction_model_label: DirectionModelLabel
    committed_mw_average: float
    revenue_gbp: float
    modelling_caveat: str


class MarketStackRow(BaseModel):
    """Phase 3 period result with energy and reserve components."""

    model_config = ConfigDict(extra="forbid")

    period_index: int
    charge_mw: float
    discharge_mw: float
    soc_start_mwh: float
    reserve_up_mw: dict[str, float]
    reserve_down_mw: dict[str, float]
    energy_revenue_gbp: float
    service_revenue_gbp: float
    total_revenue_gbp: float


class MarketStackResult(BaseModel):
    """Phase 3 result wrapper for energy plus EAC availability."""

    model_config = ConfigDict(extra="forbid")

    rows: list[MarketStackRow]
    service_components: list[MarketStackServiceComponent]
    energy_revenue_gbp: float
    service_revenue_gbp: float
    total_revenue_gbp: float
    solver_objective_gbp: float
    solver: SolverDiagnostics


def solve_market_stack(
    *,
    prices: list[WholesalePricePoint],
    eac_price_matrix: EACPriceMatrix,
    asset: AssetConfig,
    initial_soc_mwh: float,
    terminal_soc_policy: TerminalSocPolicy = "cyclic",
    solver_config: SolverConfig | None = None,
) -> MarketStackResult:
    """Solve an energy plus price-taking EAC availability model."""

    if not eac_price_matrix.has_services:
        return _solve_energy_only_as_market_stack(
            prices=prices,
            asset=asset,
            initial_soc_mwh=initial_soc_mwh,
            terminal_soc_policy=terminal_soc_policy,
            solver_config=solver_config,
        )

    dispatch_input = build_dispatch_input(
        prices,
        asset=asset,
        initial_soc_mwh=initial_soc_mwh,
        terminal_soc_policy=terminal_soc_policy,
        binary_dispatch=True,
    )
    model = build_energy_dispatch_model(dispatch_input)
    model.del_component(model.objective)
    services = eac_price_matrix.product_model_labels
    cells = {
        (cell.product_model_label, cell.period_index): cell
        for cell in eac_price_matrix.cells
        if cell.product_model_label in services
    }
    model.SERVICES = pyo.Set(initialize=services)
    model.reserve_up_mw = pyo.Var(model.SERVICES, model.T, domain=pyo.NonNegativeReals)
    model.reserve_down_mw = pyo.Var(model.SERVICES, model.T, domain=pyo.NonNegativeReals)

    _add_reserve_availability_constraints(model, dispatch_input.period_count, services, cells)
    _add_reserve_physical_constraints(model, dispatch_input, services, cells)
    _add_block_constancy_constraints(model, services, cells)
    _add_market_stack_objective(model, dispatch_input, services, cells)

    diagnostics = solve_dispatch_model(model, solver_config)
    return _extract_market_stack_result(
        model,
        diagnostics,
        dispatch_input.period_count,
        services,
        cells,
    )


def _solve_energy_only_as_market_stack(
    *,
    prices: list[WholesalePricePoint],
    asset: AssetConfig,
    initial_soc_mwh: float,
    terminal_soc_policy: TerminalSocPolicy,
    solver_config: SolverConfig | None,
) -> MarketStackResult:
    dispatch_input = build_dispatch_input(
        prices,
        asset=asset,
        initial_soc_mwh=initial_soc_mwh,
        terminal_soc_policy=terminal_soc_policy,
        binary_dispatch=True,
    )
    model = build_energy_dispatch_model(dispatch_input)
    diagnostics = solve_dispatch_model(model, solver_config)
    dispatch = extract_dispatch_result(model, diagnostics)
    rows = [
        MarketStackRow(
            period_index=row.index,
            charge_mw=row.charge_mw,
            discharge_mw=row.discharge_mw,
            soc_start_mwh=row.soc_start_mwh,
            reserve_up_mw={},
            reserve_down_mw={},
            energy_revenue_gbp=row.period_revenue_gbp,
            service_revenue_gbp=0,
            total_revenue_gbp=row.period_revenue_gbp,
        )
        for row in dispatch.rows
    ]
    return MarketStackResult(
        rows=rows,
        service_components=[],
        energy_revenue_gbp=dispatch.total_revenue_gbp,
        service_revenue_gbp=0,
        total_revenue_gbp=dispatch.total_revenue_gbp,
        solver_objective_gbp=diagnostics.objective_value,
        solver=diagnostics,
    )


def _add_reserve_availability_constraints(
    model: Any,
    period_count: int,
    services: list[str],
    cells: dict[tuple[str, int], EACPriceCell],
) -> None:
    model.reserve_availability_constraints = pyo.ConstraintList()
    for service in services:
        for period_index in range(period_count):
            cell = cells.get((service, period_index))
            if cell is None or cell.availability_state != "available":
                model.reserve_availability_constraints.add(
                    model.reserve_up_mw[service, period_index] == 0
                )
                model.reserve_availability_constraints.add(
                    model.reserve_down_mw[service, period_index] == 0
                )
                continue
            if cell.direction_model_label == "upward":
                model.reserve_availability_constraints.add(
                    model.reserve_down_mw[service, period_index] == 0
                )
                _add_procurement_cap(model, cell, model.reserve_up_mw[service, period_index])
            elif cell.direction_model_label == "downward":
                model.reserve_availability_constraints.add(
                    model.reserve_up_mw[service, period_index] == 0
                )
                _add_procurement_cap(model, cell, model.reserve_down_mw[service, period_index])
            else:
                model.reserve_availability_constraints.add(
                    model.reserve_up_mw[service, period_index] == 0
                )
                model.reserve_availability_constraints.add(
                    model.reserve_down_mw[service, period_index] == 0
                )


def _add_procurement_cap(model: Any, cell: EACPriceCell, variable: Any) -> None:
    if cell.procured_mw is not None:
        model.reserve_availability_constraints.add(variable <= cell.procured_mw)


def _add_reserve_physical_constraints(
    model: Any,
    dispatch_input: Any,
    services: list[str],
    cells: dict[tuple[str, int], EACPriceCell],
) -> None:
    def headroom_rule(model: Any, period_index: int) -> Any:
        return (
            model.discharge_mw[period_index]
            + sum(model.reserve_up_mw[service, period_index] for service in services)
            <= dispatch_input.p_export_max_mw
        )

    def footroom_rule(model: Any, period_index: int) -> Any:
        return (
            model.charge_mw[period_index]
            + sum(model.reserve_down_mw[service, period_index] for service in services)
            <= dispatch_input.p_import_max_mw
        )

    def upward_energy_rule(model: Any, period_index: int) -> Any:
        return model.soc_mwh[period_index] - dispatch_input.soc_min_mwh >= sum(
            model.reserve_up_mw[service, period_index]
            * _service_duration_h(cells, service, period_index)
            / dispatch_input.eta_discharge
            for service in services
        )

    def downward_energy_rule(model: Any, period_index: int) -> Any:
        return dispatch_input.soc_max_mwh - model.soc_mwh[period_index] >= sum(
            model.reserve_down_mw[service, period_index]
            * _service_duration_h(cells, service, period_index)
            * dispatch_input.eta_charge
            for service in services
        )

    model.reserve_headroom = pyo.Constraint(model.T, rule=headroom_rule)
    model.reserve_footroom = pyo.Constraint(model.T, rule=footroom_rule)
    model.reserve_upward_energy = pyo.Constraint(model.T, rule=upward_energy_rule)
    model.reserve_downward_energy = pyo.Constraint(model.T, rule=downward_energy_rule)


def _add_block_constancy_constraints(
    model: Any,
    services: list[str],
    cells: dict[tuple[str, int], EACPriceCell],
) -> None:
    groups: dict[tuple[str, str, str], list[int]] = {}
    for (service, period_index), cell in cells.items():
        if (
            service in services
            and cell.availability_state == "available"
            and cell.block_id is not None
            and cell.block_commitment_rule == "constant_within_block"
        ):
            groups.setdefault((service, cell.block_id, cell.direction_model_label), []).append(
                period_index
            )
    model.reserve_block_constancy = pyo.ConstraintList()
    for (service, _block_id, direction), period_indexes in groups.items():
        ordered = sorted(period_indexes)
        anchor = ordered[0]
        for period_index in ordered[1:]:
            if direction == "upward":
                model.reserve_block_constancy.add(
                    model.reserve_up_mw[service, period_index]
                    == model.reserve_up_mw[service, anchor]
                )
            if direction == "downward":
                model.reserve_block_constancy.add(
                    model.reserve_down_mw[service, period_index]
                    == model.reserve_down_mw[service, anchor]
                )


def _add_market_stack_objective(
    model: Any,
    dispatch_input: Any,
    services: list[str],
    cells: dict[tuple[str, int], EACPriceCell],
) -> None:
    energy_expr = sum(
        model.price_gbp_per_mwh[period.index]
        * (model.discharge_mw[period.index] - model.charge_mw[period.index])
        * period.duration_h
        for period in dispatch_input.periods
    )
    service_expr = sum(
        _cell_price(cells, service, period.index)
        * (
            model.reserve_up_mw[service, period.index]
            + model.reserve_down_mw[service, period.index]
        )
        * period.duration_h
        for service in services
        for period in dispatch_input.periods
    )
    model.objective = pyo.Objective(expr=energy_expr + service_expr, sense=pyo.maximize)


def _extract_market_stack_result(
    model: Any,
    diagnostics: SolverDiagnostics,
    period_count: int,
    services: list[str],
    cells: dict[tuple[str, int], EACPriceCell],
) -> MarketStackResult:
    rows: list[MarketStackRow] = []
    energy_revenue = 0.0
    service_revenue = 0.0
    component_revenue: dict[str, float] = dict.fromkeys(services, 0.0)
    component_commitment: dict[str, float] = dict.fromkeys(services, 0.0)
    for period_index in range(period_count):
        charge_mw = _value(model.charge_mw[period_index])
        discharge_mw = _value(model.discharge_mw[period_index])
        duration_h = float(pyo.value(model.duration_h[period_index]))
        period_energy = (
            float(pyo.value(model.price_gbp_per_mwh[period_index]))
            * (discharge_mw - charge_mw)
            * duration_h
        )
        reserve_up = {
            service: _value(model.reserve_up_mw[service, period_index]) for service in services
        }
        reserve_down = {
            service: _value(model.reserve_down_mw[service, period_index]) for service in services
        }
        period_service = 0.0
        for service in services:
            committed = reserve_up[service] + reserve_down[service]
            revenue = _cell_price(cells, service, period_index) * committed * duration_h
            period_service += revenue
            component_revenue[service] += revenue
            component_commitment[service] += committed
        rows.append(
            MarketStackRow(
                period_index=period_index,
                charge_mw=charge_mw,
                discharge_mw=discharge_mw,
                soc_start_mwh=_value(model.soc_mwh[period_index]),
                reserve_up_mw=reserve_up,
                reserve_down_mw=reserve_down,
                energy_revenue_gbp=period_energy,
                service_revenue_gbp=period_service,
                total_revenue_gbp=period_energy + period_service,
            )
        )
        energy_revenue += period_energy
        service_revenue += period_service
    components = [
        MarketStackServiceComponent(
            product_source_label=_first_cell(cells, service).product_source_label,
            product_model_label=service,
            direction_model_label=_first_cell(cells, service).direction_model_label,
            committed_mw_average=component_commitment[service] / period_count,
            revenue_gbp=component_revenue[service],
            modelling_caveat=_first_cell(cells, service).modelling_caveat,
        )
        for service in services
        if component_revenue[service] != 0 or component_commitment[service] != 0
    ]
    total = energy_revenue + service_revenue
    return MarketStackResult(
        rows=rows,
        service_components=components,
        energy_revenue_gbp=energy_revenue,
        service_revenue_gbp=service_revenue,
        total_revenue_gbp=total,
        solver_objective_gbp=diagnostics.objective_value,
        solver=diagnostics,
    )


def _service_duration_h(
    cells: dict[tuple[str, int], EACPriceCell],
    service: str,
    period_index: int,
) -> float:
    cell = cells.get((service, period_index))
    if cell is None or cell.availability_state != "available":
        return 0.0
    return cell.service_duration_h


def _cell_price(
    cells: dict[tuple[str, int], EACPriceCell],
    service: str,
    period_index: int,
) -> float:
    cell = cells.get((service, period_index))
    if cell is None or cell.availability_state != "available" or cell.price_gbp_per_mw_h is None:
        return 0.0
    return cell.price_gbp_per_mw_h


def _first_cell(cells: dict[tuple[str, int], EACPriceCell], service: str) -> EACPriceCell:
    for (cell_service, _period_index), cell in cells.items():
        if cell_service == service:
            return cell
    msg = f"No cells found for service {service!r}."
    raise KeyError(msg)


def _value(pyomo_value: Any) -> float:
    value = pyo.value(pyomo_value)
    return 0.0 if abs(value) < 1e-9 else float(value)
