from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from gb_bess_revenue_stack.config.models import AssetConfig
from gb_bess_revenue_stack.markets.eac_prices import EACPriceCell, EACPriceMatrix
from gb_bess_revenue_stack.optimisation.market_stack_model import (
    MarketStackResult,
    MarketStackRow,
    solve_market_stack,
)
from gb_bess_revenue_stack.policies.forecasts import ForecastModel, ForecastPoint
from gb_bess_revenue_stack.policies.information_set import build_information_set
from gb_bess_revenue_stack.policies.rolling import RollingConfig, RollingPolicyError
from gb_bess_revenue_stack.schemas.base import ensure_aware_utc
from gb_bess_revenue_stack.schemas.market import WholesalePricePoint


class RollingMarketStackStepRecord(BaseModel):
    """Trace record for one rolling market-stack decision."""

    model_config = ConfigDict(extra="forbid")

    decision_time_utc: datetime
    horizon_period_count: int
    executed_period_count: int
    information_source_hash: str
    excluded_future_row_count: int
    service_cell_count: int
    excluded_service_cell_count: int
    forecast_model: str
    forecast_is_oracle: bool
    forecast_mae_gbp_per_mwh: float
    forecast_rmse_gbp_per_mwh: float
    soc_start_mwh: float
    soc_end_mwh: float
    planned_terminal_soc_mwh: float
    executed_charge_mw: float
    executed_discharge_mw: float
    executed_reserve_up_mw: dict[str, float]
    executed_reserve_down_mw: dict[str, float]
    realised_energy_revenue_gbp: float
    realised_service_revenue_gbp: float
    realised_total_revenue_gbp: float
    planned_total_revenue_gbp: float
    solver_termination_condition: str
    solver_wall_time_seconds: float

    @field_validator("decision_time_utc")
    @classmethod
    def decision_time_is_aware(cls, value: datetime) -> datetime:
        return ensure_aware_utc(value)


class RollingMarketStackRun(BaseModel):
    """Complete rolling policy result for wholesale plus EAC availability."""

    model_config = ConfigDict(extra="forbid")

    steps: list[RollingMarketStackStepRecord]
    realised_energy_revenue_gbp: float
    realised_service_revenue_gbp: float
    realised_total_revenue_gbp: float
    planned_total_revenue_gbp: float
    final_soc_mwh: float
    initial_soc_mwh: float
    terminal_soc_policy: str
    terminal_soc_target_mwh: float | None = None
    forecast_model: str
    solver_failure_count: int


class RollingMarketStackScenario(BaseModel):
    """Deterministic scalar scenario for Phase 4 sensitivity sweeps."""

    model_config = ConfigDict(extra="forbid")

    name: str
    stress_label: str = "central"
    wholesale_price_scalar: float = Field(default=1, ge=0)
    eac_price_scalar: float = Field(default=1, ge=0)
    notes: str = ""


class RollingMarketStackScenarioResult(BaseModel):
    """Compact result from one deterministic rolling market-stack scenario."""

    model_config = ConfigDict(extra="forbid")

    name: str
    stress_label: str = "central"
    period_count: int = Field(default=0, ge=0)
    wholesale_price_scalar: float
    eac_price_scalar: float
    realised_energy_revenue_gbp: float
    realised_service_revenue_gbp: float
    realised_total_revenue_gbp: float
    final_soc_mwh: float


def run_rolling_market_stack_policy(
    *,
    prices: list[WholesalePricePoint],
    eac_price_matrix: EACPriceMatrix,
    asset: AssetConfig,
    initial_soc_mwh: float,
    forecast_model: ForecastModel,
    config: RollingConfig,
) -> RollingMarketStackRun:
    """Run a receding-horizon wholesale plus EAC availability policy."""

    if not prices:
        msg = "At least one realised price is required."
        raise RollingPolicyError(msg)
    ordered = sorted(prices, key=lambda point: point.delivery_start_utc)
    evaluation_prices = [
        point
        for point in ordered
        if config.evaluation_start_utc is None
        or point.delivery_start_utc >= config.evaluation_start_utc
    ]
    if not evaluation_prices:
        msg = "No realised prices fall inside the requested evaluation window."
        raise RollingPolicyError(msg)

    global_period_index = {point.delivery_start_utc: index for index, point in enumerate(ordered)}
    soc_mwh = initial_soc_mwh
    steps: list[RollingMarketStackStepRecord] = []
    period_index = 0
    solver_failure_count = 0
    while period_index < len(evaluation_prices):
        horizon = evaluation_prices[period_index : period_index + config.horizon_periods]
        if not horizon:
            break
        decision_time = horizon[0].delivery_start_utc
        info = build_information_set(
            decision_time_utc=decision_time,
            all_prices=ordered,
            current_soc_mwh=soc_mwh,
        )
        forecast = forecast_model.predict(info, target_periods=horizon)
        forecast_prices = _forecast_points_to_price_records(horizon, forecast.points, decision_time)
        horizon_global_indexes = [
            global_period_index[point.delivery_start_utc] for point in horizon
        ]
        decision_matrix, excluded_service_cells = _decision_eac_matrix(
            eac_price_matrix=eac_price_matrix,
            horizon_global_indexes=horizon_global_indexes,
            decision_time_utc=decision_time,
        )
        try:
            market_stack = solve_market_stack(
                prices=forecast_prices,
                eac_price_matrix=decision_matrix,
                asset=asset,
                initial_soc_mwh=soc_mwh,
                terminal_soc_policy=config.terminal_soc_policy,  # type: ignore[arg-type]
                terminal_soc_target_mwh=config.terminal_soc_target_mwh,
                solver_config=config.solver,
            )
        except ValueError as exc:
            solver_failure_count += 1
            msg = f"Rolling market-stack solve failed at {decision_time.isoformat()}: {exc}"
            raise RollingPolicyError(msg) from exc

        execute_count = min(config.step_periods, len(horizon), len(market_stack.rows))
        step_rows = market_stack.rows[:execute_count]
        realised_energy = 0.0
        realised_service = 0.0
        planned_total = 0.0
        for offset, row in enumerate(step_rows):
            actual = horizon[offset]
            realised_energy += (
                actual.price_gbp_per_mwh * (row.discharge_mw - row.charge_mw) * actual.duration_h
            )
            realised_service += row.service_revenue_gbp
            planned_total += row.total_revenue_gbp
        last_row = step_rows[-1]
        last_period = horizon[execute_count - 1]
        soc_mwh = _soc_end_mwh(last_row, last_period.duration_h, asset)
        forecast_errors = [
            forecast.points[index].forecast_value_gbp_per_mwh - horizon[index].price_gbp_per_mwh
            for index in range(len(horizon))
        ]
        steps.append(
            RollingMarketStackStepRecord(
                decision_time_utc=decision_time,
                horizon_period_count=len(horizon),
                executed_period_count=execute_count,
                information_source_hash=info.source_data_hash,
                excluded_future_row_count=info.excluded_future_row_count,
                service_cell_count=len(decision_matrix.cells),
                excluded_service_cell_count=excluded_service_cells,
                forecast_model=forecast.source_model,
                forecast_is_oracle=any(point.is_oracle for point in forecast.points),
                forecast_mae_gbp_per_mwh=_mae(forecast_errors),
                forecast_rmse_gbp_per_mwh=_rmse(forecast_errors),
                soc_start_mwh=step_rows[0].soc_start_mwh,
                soc_end_mwh=soc_mwh,
                planned_terminal_soc_mwh=_planned_terminal_soc_mwh(market_stack, horizon, asset),
                executed_charge_mw=sum(row.charge_mw for row in step_rows) / execute_count,
                executed_discharge_mw=sum(row.discharge_mw for row in step_rows) / execute_count,
                executed_reserve_up_mw=_average_reserve(step_rows, "up"),
                executed_reserve_down_mw=_average_reserve(step_rows, "down"),
                realised_energy_revenue_gbp=realised_energy,
                realised_service_revenue_gbp=realised_service,
                realised_total_revenue_gbp=realised_energy + realised_service,
                planned_total_revenue_gbp=planned_total,
                solver_termination_condition=market_stack.solver.termination_condition,
                solver_wall_time_seconds=market_stack.solver.wall_time_seconds,
            )
        )
        period_index += execute_count

    return RollingMarketStackRun(
        steps=steps,
        realised_energy_revenue_gbp=sum(step.realised_energy_revenue_gbp for step in steps),
        realised_service_revenue_gbp=sum(step.realised_service_revenue_gbp for step in steps),
        realised_total_revenue_gbp=sum(step.realised_total_revenue_gbp for step in steps),
        planned_total_revenue_gbp=sum(step.planned_total_revenue_gbp for step in steps),
        final_soc_mwh=soc_mwh,
        initial_soc_mwh=initial_soc_mwh,
        terminal_soc_policy=config.terminal_soc_policy,
        terminal_soc_target_mwh=config.terminal_soc_target_mwh,
        forecast_model=forecast_model.source_model,
        solver_failure_count=solver_failure_count,
    )


def run_rolling_market_stack_scenarios(
    *,
    prices: list[WholesalePricePoint],
    eac_price_matrix: EACPriceMatrix,
    asset: AssetConfig,
    initial_soc_mwh: float,
    forecast_model: ForecastModel,
    config: RollingConfig,
    scenarios: list[RollingMarketStackScenario],
) -> list[RollingMarketStackScenarioResult]:
    """Run deterministic scalar sensitivities for rolling market-stack policy."""

    results: list[RollingMarketStackScenarioResult] = []
    for scenario in scenarios:
        run = run_rolling_market_stack_policy(
            prices=_scale_prices(prices, scenario.wholesale_price_scalar),
            eac_price_matrix=_scale_eac_prices(eac_price_matrix, scenario.eac_price_scalar),
            asset=asset,
            initial_soc_mwh=initial_soc_mwh,
            forecast_model=forecast_model,
            config=config,
        )
        results.append(
            RollingMarketStackScenarioResult(
                name=scenario.name,
                stress_label=scenario.stress_label,
                period_count=len(prices),
                wholesale_price_scalar=scenario.wholesale_price_scalar,
                eac_price_scalar=scenario.eac_price_scalar,
                realised_energy_revenue_gbp=run.realised_energy_revenue_gbp,
                realised_service_revenue_gbp=run.realised_service_revenue_gbp,
                realised_total_revenue_gbp=run.realised_total_revenue_gbp,
                final_soc_mwh=run.final_soc_mwh,
            )
        )
    return results


def _decision_eac_matrix(
    *,
    eac_price_matrix: EACPriceMatrix,
    horizon_global_indexes: list[int],
    decision_time_utc: datetime,
) -> tuple[EACPriceMatrix, int]:
    cells: list[EACPriceCell] = []
    excluded = 0
    local_index_by_global_index = {
        global_index: local_index for local_index, global_index in enumerate(horizon_global_indexes)
    }
    for cell in eac_price_matrix.cells:
        local_index = local_index_by_global_index.get(cell.period_index)
        if local_index is None:
            continue
        if cell.known_at_utc is not None and cell.known_at_utc > decision_time_utc:
            cells.append(
                cell.model_copy(
                    update={
                        "period_index": local_index,
                        "price_gbp_per_mw_h": None,
                        "availability_state": "not_known_at_decision_time",
                    }
                )
            )
            excluded += 1
            continue
        cells.append(cell.model_copy(update={"period_index": local_index}))
    return EACPriceMatrix(cells=cells), excluded


def _forecast_points_to_price_records(
    target_periods: list[WholesalePricePoint],
    forecast_points: list[ForecastPoint],
    decision_time_utc: datetime,
) -> list[WholesalePricePoint]:
    records: list[WholesalePricePoint] = []
    for target, forecast in zip(target_periods, forecast_points, strict=True):
        records.append(
            WholesalePricePoint(
                delivery_start_utc=target.delivery_start_utc,
                delivery_end_utc=target.delivery_end_utc,
                settlement_date=target.settlement_date,
                settlement_period=target.settlement_period,
                duration_h=target.duration_h,
                price_gbp_per_mwh=forecast.forecast_value_gbp_per_mwh,
                price_source_type="SYNTHETIC_TEST",
                is_proxy=False,
                known_at_utc=decision_time_utc,
                retrieved_at_utc=decision_time_utc,
                source_id="PROJECT_CONVENTION",
                source_url=f"forecast:{forecast.source_model}",
                schema_version="0.1.0",
                quality_flag="ok",
            )
        )
    return records


def _soc_end_mwh(row: MarketStackRow, duration_h: float, asset: AssetConfig) -> float:
    eta_charge = asset.eta_charge
    eta_discharge = asset.eta_discharge
    if eta_charge is None or eta_discharge is None:
        msg = "AssetConfig did not derive charge/discharge efficiency."
        raise ValueError(msg)
    return (
        row.soc_start_mwh
        + row.charge_mw * eta_charge * duration_h
        - row.discharge_mw * duration_h / eta_discharge
    )


def _planned_terminal_soc_mwh(
    market_stack: MarketStackResult,
    horizon: list[WholesalePricePoint],
    asset: AssetConfig,
) -> float:
    return _soc_end_mwh(market_stack.rows[-1], horizon[-1].duration_h, asset)


def _average_reserve(rows: list[MarketStackRow], direction: str) -> dict[str, float]:
    totals: dict[str, float] = {}
    for row in rows:
        values = row.reserve_up_mw if direction == "up" else row.reserve_down_mw
        for service, value in values.items():
            totals[service] = totals.get(service, 0.0) + value
    return {service: value / len(rows) for service, value in totals.items()}


def _scale_prices(
    prices: list[WholesalePricePoint],
    scalar: float,
) -> list[WholesalePricePoint]:
    return [
        price.model_copy(update={"price_gbp_per_mwh": price.price_gbp_per_mwh * scalar})
        for price in prices
    ]


def _scale_eac_prices(
    eac_price_matrix: EACPriceMatrix,
    scalar: float,
) -> EACPriceMatrix:
    return EACPriceMatrix(
        cells=[
            cell.model_copy(
                update={
                    "price_gbp_per_mw_h": None
                    if cell.price_gbp_per_mw_h is None
                    else cell.price_gbp_per_mw_h * scalar
                }
            )
            for cell in eac_price_matrix.cells
        ]
    )


def _mae(errors: list[float]) -> float:
    return sum(abs(error) for error in errors) / len(errors) if errors else 0.0


def _rmse(errors: list[float]) -> float:
    return (sum(error * error for error in errors) / len(errors)) ** 0.5 if errors else 0.0
