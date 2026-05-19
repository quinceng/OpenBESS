from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

import pyomo.environ as pyo
from pydantic import BaseModel, ConfigDict, Field, model_validator

from gb_bess_revenue_stack.config.models import SolverConfig
from gb_bess_revenue_stack.optimisation.solve import SolverDiagnostics, solve_dispatch_model
from gb_bess_revenue_stack.residential.billing import (
    ResidentialBillBreakdown,
    calculate_no_battery_bill,
)
from gb_bess_revenue_stack.residential.models import ResidentialBessSystem
from gb_bess_revenue_stack.residential.profiles import (
    ResidentialHouseholdInterval,
    ResidentialTariffSchedule,
    validate_household_intervals,
)
from gb_bess_revenue_stack.residential.vpp import (
    ResidentialVPPRevenue,
    ResidentialVPPSchedule,
    calculate_vpp_revenue,
)

TerminalSocPolicy = Literal["free", "cyclic", "target"]


class ResidentialHouseholdDispatchInput(BaseModel):
    """Residential load/PV/tariff dispatch input in kW/kWh units."""

    model_config = ConfigDict(extra="forbid")

    system: ResidentialBessSystem
    intervals: list[ResidentialHouseholdInterval]
    tariff: ResidentialTariffSchedule
    dno_export_limit_kw: float = Field(gt=0)
    initial_soc_kwh: float = Field(ge=0)
    terminal_soc_policy: TerminalSocPolicy = "cyclic"
    terminal_soc_target_kwh: float | None = Field(default=None, ge=0)
    round_trip_efficiency: float = Field(default=0.90, gt=0, le=1)
    allow_grid_charging: bool = True
    allow_grid_charged_export: bool = False
    vpp_schedule: ResidentialVPPSchedule | None = None
    solver: SolverConfig = SolverConfig(time_limit_seconds=120, mip_gap=0.001)

    @model_validator(mode="after")
    def validate_soc_targets(self) -> ResidentialHouseholdDispatchInput:
        if self.initial_soc_kwh > self.system.battery_capacity_kwh:
            msg = "initial_soc_kwh must be within battery capacity."
            raise ValueError(msg)
        if self.terminal_soc_policy == "target" and self.terminal_soc_target_kwh is None:
            msg = "terminal_soc_target_kwh is required when terminal_soc_policy='target'."
            raise ValueError(msg)
        if (
            self.terminal_soc_target_kwh is not None
            and self.terminal_soc_target_kwh > self.system.battery_capacity_kwh
        ):
            msg = "terminal_soc_target_kwh must be within battery capacity."
            raise ValueError(msg)
        validate_household_intervals(self.intervals, allow_empty_energy_profile=True)
        return self


class ResidentialHouseholdDispatchRow(BaseModel):
    """Solved residential household battery dispatch for one interval."""

    model_config = ConfigDict(extra="forbid")

    interval_index: int
    delivery_start_utc: datetime
    delivery_end_utc: datetime
    duration_h: float
    load_kwh: float
    pv_generation_kwh: float
    grid_to_load_kwh: float
    grid_to_battery_kwh: float
    pv_to_load_kwh: float
    pv_to_battery_kwh: float
    pv_to_export_kwh: float
    battery_to_load_kwh: float
    battery_to_export_kwh: float
    site_export_kwh: float
    pv_curtailed_kwh: float
    soc_start_kwh: float
    soc_end_kwh: float
    import_rate_gbp_per_kwh: float
    export_rate_gbp_per_kwh: float
    period_bill_gbp: float


class ResidentialHouseholdDispatchResult(BaseModel):
    """Residential bill-aware dispatch result and value-stack split."""

    model_config = ConfigDict(extra="forbid")

    rows: list[ResidentialHouseholdDispatchRow]
    no_battery_bill: ResidentialBillBreakdown
    battery_bill: ResidentialBillBreakdown
    self_consumption_savings_gbp: float
    tariff_arbitrage_savings_gbp: float
    export_revenue_delta_gbp: float
    total_bill_savings_gbp: float
    charged_kwh: float = Field(ge=0)
    discharged_kwh: float = Field(ge=0)
    equivalent_cycles: float = Field(ge=0)
    solver: SolverDiagnostics | None
    vpp_revenue: ResidentialVPPRevenue | None = None


def solve_residential_household_dispatch(
    dispatch_input: ResidentialHouseholdDispatchInput,
) -> ResidentialHouseholdDispatchResult:
    """Solve a residential bill-aware battery dispatch model."""

    intervals = validate_household_intervals(
        dispatch_input.intervals,
        allow_empty_energy_profile=True,
    )
    rates = [dispatch_input.tariff.rate_for(row.delivery_start_utc) for row in intervals]
    model = _build_model(dispatch_input, intervals, rates)
    diagnostics = solve_dispatch_model(model, dispatch_input.solver)
    rows = _extract_rows(model, intervals, rates)
    no_battery_bill = calculate_no_battery_bill(
        intervals,
        tariff=dispatch_input.tariff,
        export_limit_kw=dispatch_input.dno_export_limit_kw,
    )
    battery_bill = _battery_bill(rows)
    vpp_revenue = _dispatch_vpp_revenue(dispatch_input, rows)
    pv_battery_to_load_value = sum(
        _value(model.pv_battery_to_load_kwh[index]) * rates[index].import_rate_gbp_per_kwh
        for index in range(len(intervals))
    )
    export_delta = battery_bill.export_revenue_gbp - no_battery_bill.export_revenue_gbp
    total_savings = no_battery_bill.energy_bill_gbp - battery_bill.energy_bill_gbp
    tariff_arbitrage = total_savings - pv_battery_to_load_value - export_delta
    charged = sum(row.pv_to_battery_kwh + row.grid_to_battery_kwh for row in rows)
    discharged = sum(row.battery_to_load_kwh + row.battery_to_export_kwh for row in rows)
    return ResidentialHouseholdDispatchResult(
        rows=rows,
        no_battery_bill=no_battery_bill,
        battery_bill=battery_bill,
        self_consumption_savings_gbp=pv_battery_to_load_value,
        tariff_arbitrage_savings_gbp=tariff_arbitrage,
        export_revenue_delta_gbp=export_delta,
        total_bill_savings_gbp=total_savings,
        charged_kwh=charged,
        discharged_kwh=discharged,
        equivalent_cycles=(charged + discharged) / (2 * dispatch_input.system.battery_capacity_kwh),
        solver=diagnostics,
        vpp_revenue=vpp_revenue,
    )


def _build_model(
    dispatch_input: ResidentialHouseholdDispatchInput,
    intervals: list[ResidentialHouseholdInterval],
    rates: list[Any],
) -> Any:
    model = pyo.ConcreteModel()
    count = len(intervals)
    indexes = range(count)
    model.T = pyo.RangeSet(0, count - 1)
    model.S = pyo.RangeSet(0, count)
    model.pv_to_load_kwh = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.pv_to_battery_kwh = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.pv_to_export_kwh = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.pv_curtailed_kwh = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.grid_to_load_kwh = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.grid_to_battery_kwh = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.pv_battery_to_load_kwh = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.pv_battery_to_export_kwh = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.grid_battery_to_load_kwh = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.grid_battery_to_export_kwh = pyo.Var(model.T, domain=pyo.NonNegativeReals)
    model.soc_pv_kwh = pyo.Var(model.S, domain=pyo.NonNegativeReals)
    model.soc_grid_kwh = pyo.Var(model.S, domain=pyo.NonNegativeReals)
    model.charge_binary = pyo.Var(model.T, domain=pyo.Binary)
    model.discharge_binary = pyo.Var(model.T, domain=pyo.Binary)

    eta = dispatch_input.round_trip_efficiency**0.5
    capacity = dispatch_input.system.battery_capacity_kwh
    inverter_kw = dispatch_input.system.inverter_power_kw
    export_limit_kw = dispatch_input.dno_export_limit_kw

    model.initial_soc_pv = pyo.Constraint(
        expr=model.soc_pv_kwh[0] == dispatch_input.initial_soc_kwh
    )
    model.initial_soc_grid = pyo.Constraint(expr=model.soc_grid_kwh[0] == 0)
    model.pv_balance = pyo.Constraint(
        model.T,
        rule=lambda model, idx: (
            intervals[idx].pv_generation_kwh
            == model.pv_to_load_kwh[idx]
            + model.pv_to_battery_kwh[idx]
            + model.pv_to_export_kwh[idx]
            + model.pv_curtailed_kwh[idx]
        ),
    )
    model.load_balance = pyo.Constraint(
        model.T,
        rule=lambda model, idx: (
            intervals[idx].load_kwh
            == model.pv_to_load_kwh[idx]
            + model.grid_to_load_kwh[idx]
            + model.pv_battery_to_load_kwh[idx]
            + model.grid_battery_to_load_kwh[idx]
        ),
    )
    model.export_limit = pyo.Constraint(
        model.T,
        rule=lambda model, idx: (
            model.pv_to_export_kwh[idx]
            + model.pv_battery_to_export_kwh[idx]
            + model.grid_battery_to_export_kwh[idx]
            <= export_limit_kw * intervals[idx].duration_h
        ),
    )
    model.charge_limit = pyo.Constraint(
        model.T,
        rule=lambda model, idx: (
            model.pv_to_battery_kwh[idx] + model.grid_to_battery_kwh[idx]
            <= inverter_kw * intervals[idx].duration_h * model.charge_binary[idx]
        ),
    )
    model.discharge_limit = pyo.Constraint(
        model.T,
        rule=lambda model, idx: (
            model.pv_battery_to_load_kwh[idx]
            + model.pv_battery_to_export_kwh[idx]
            + model.grid_battery_to_load_kwh[idx]
            + model.grid_battery_to_export_kwh[idx]
            <= inverter_kw * intervals[idx].duration_h * model.discharge_binary[idx]
        ),
    )
    model.no_simultaneous_charge_discharge = pyo.Constraint(
        model.T,
        rule=lambda model, idx: model.charge_binary[idx] + model.discharge_binary[idx] <= 1,
    )
    model.pv_soc = pyo.Constraint(
        model.T,
        rule=lambda model, idx: (
            model.soc_pv_kwh[idx + 1]
            == model.soc_pv_kwh[idx]
            + eta * model.pv_to_battery_kwh[idx]
            - (model.pv_battery_to_load_kwh[idx] + model.pv_battery_to_export_kwh[idx]) / eta
        ),
    )
    model.grid_soc = pyo.Constraint(
        model.T,
        rule=lambda model, idx: (
            model.soc_grid_kwh[idx + 1]
            == model.soc_grid_kwh[idx]
            + eta * model.grid_to_battery_kwh[idx]
            - (model.grid_battery_to_load_kwh[idx] + model.grid_battery_to_export_kwh[idx]) / eta
        ),
    )
    model.capacity_limit = pyo.Constraint(
        model.S,
        rule=lambda model, idx: model.soc_pv_kwh[idx] + model.soc_grid_kwh[idx] <= capacity,
    )
    if not dispatch_input.allow_grid_charging:
        model.no_grid_charging = pyo.Constraint(
            model.T,
            rule=lambda model, idx: model.grid_to_battery_kwh[idx] == 0,
        )
    if not dispatch_input.allow_grid_charged_export:
        model.no_grid_charged_export = pyo.Constraint(
            model.T,
            rule=lambda model, idx: model.grid_battery_to_export_kwh[idx] == 0,
        )
    if dispatch_input.terminal_soc_policy == "cyclic":
        model.terminal_soc = pyo.Constraint(
            expr=model.soc_pv_kwh[count] + model.soc_grid_kwh[count]
            == dispatch_input.initial_soc_kwh
        )
    if dispatch_input.terminal_soc_policy == "target":
        target = dispatch_input.terminal_soc_target_kwh
        if target is None:
            msg = "terminal_soc_target_kwh is required when terminal_soc_policy='target'."
            raise ValueError(msg)
        model.terminal_soc = pyo.Constraint(
            expr=model.soc_pv_kwh[count] + model.soc_grid_kwh[count] == target
        )
    events = dispatch_input.vpp_schedule.events if dispatch_input.vpp_schedule else ()
    if events:
        model.EVENTS = pyo.RangeSet(0, len(events) - 1)
        model.event_delivered_kwh = pyo.Var(model.EVENTS, domain=pyo.NonNegativeReals)
        model.event_delivery_limit = pyo.ConstraintList()
        for event_index, event in enumerate(events):
            event_indexes = [
                idx
                for idx, interval in enumerate(intervals)
                if interval.delivery_start_utc >= event.event_start_utc
                and interval.delivery_end_utc <= event.event_end_utc
            ]
            model.event_delivery_limit.add(
                model.event_delivered_kwh[event_index]
                <= sum(_site_export_expr(model, idx) for idx in event_indexes)
            )
            if event.required_export_kwh > 0:
                model.event_delivery_limit.add(
                    model.event_delivered_kwh[event_index] <= event.required_export_kwh
                )
            for idx, interval in enumerate(intervals):
                if interval.delivery_start_utc == event.event_start_utc:
                    model.event_delivery_limit.add(
                        model.soc_pv_kwh[idx] + model.soc_grid_kwh[idx]
                        >= event.min_soc_kwh_at_start
                    )
    model.objective = pyo.Objective(
        expr=_energy_bill_expr(model, indexes, rates) - _event_payment_expr(model, events),
        sense=pyo.minimize,
    )
    return model


def _site_export_expr(model: Any, idx: int) -> Any:
    return (
        model.pv_to_export_kwh[idx]
        + model.pv_battery_to_export_kwh[idx]
        + model.grid_battery_to_export_kwh[idx]
    )


def _energy_bill_expr(model: Any, indexes: range, rates: list[Any]) -> Any:
    return sum(
        (model.grid_to_load_kwh[idx] + model.grid_to_battery_kwh[idx])
        * rates[idx].import_rate_gbp_per_kwh
        - _site_export_expr(model, idx) * rates[idx].export_rate_gbp_per_kwh
        for idx in indexes
    )


def _event_payment_expr(model: Any, events: tuple[Any, ...]) -> Any:
    if not events:
        return 0
    return sum(
        model.event_delivered_kwh[event_index] * event.payment_gbp_per_kwh
        for event_index, event in enumerate(events)
    )


def _extract_rows(
    model: Any,
    intervals: list[ResidentialHouseholdInterval],
    rates: list[Any],
) -> list[ResidentialHouseholdDispatchRow]:
    rows: list[ResidentialHouseholdDispatchRow] = []
    for idx, interval in enumerate(intervals):
        pv_to_export = _value(model.pv_to_export_kwh[idx])
        pv_battery_to_load = _value(model.pv_battery_to_load_kwh[idx])
        grid_battery_to_load = _value(model.grid_battery_to_load_kwh[idx])
        pv_battery_to_export = _value(model.pv_battery_to_export_kwh[idx])
        grid_battery_to_export = _value(model.grid_battery_to_export_kwh[idx])
        battery_to_load = pv_battery_to_load + grid_battery_to_load
        battery_to_export = pv_battery_to_export + grid_battery_to_export
        site_export = pv_to_export + battery_to_export
        grid_to_load = _value(model.grid_to_load_kwh[idx])
        grid_to_battery = _value(model.grid_to_battery_kwh[idx])
        period_bill = (grid_to_load + grid_to_battery) * rates[
            idx
        ].import_rate_gbp_per_kwh - site_export * rates[idx].export_rate_gbp_per_kwh
        rows.append(
            ResidentialHouseholdDispatchRow(
                interval_index=idx,
                delivery_start_utc=interval.delivery_start_utc,
                delivery_end_utc=interval.delivery_end_utc,
                duration_h=interval.duration_h,
                load_kwh=interval.load_kwh,
                pv_generation_kwh=interval.pv_generation_kwh,
                grid_to_load_kwh=grid_to_load,
                grid_to_battery_kwh=grid_to_battery,
                pv_to_load_kwh=_value(model.pv_to_load_kwh[idx]),
                pv_to_battery_kwh=_value(model.pv_to_battery_kwh[idx]),
                pv_to_export_kwh=pv_to_export,
                battery_to_load_kwh=battery_to_load,
                battery_to_export_kwh=battery_to_export,
                site_export_kwh=site_export,
                pv_curtailed_kwh=_value(model.pv_curtailed_kwh[idx]),
                soc_start_kwh=_value(model.soc_pv_kwh[idx]) + _value(model.soc_grid_kwh[idx]),
                soc_end_kwh=_value(model.soc_pv_kwh[idx + 1]) + _value(model.soc_grid_kwh[idx + 1]),
                import_rate_gbp_per_kwh=rates[idx].import_rate_gbp_per_kwh,
                export_rate_gbp_per_kwh=rates[idx].export_rate_gbp_per_kwh,
                period_bill_gbp=period_bill,
            )
        )
    return rows


def _battery_bill(rows: list[ResidentialHouseholdDispatchRow]) -> ResidentialBillBreakdown:
    import_kwh = sum(row.grid_to_load_kwh + row.grid_to_battery_kwh for row in rows)
    export_kwh = sum(row.site_export_kwh for row in rows)
    import_cost = sum(
        (row.grid_to_load_kwh + row.grid_to_battery_kwh) * row.import_rate_gbp_per_kwh
        for row in rows
    )
    export_revenue = sum(row.site_export_kwh * row.export_rate_gbp_per_kwh for row in rows)
    standing_charge = 0.0
    energy_bill = import_cost - export_revenue
    return ResidentialBillBreakdown(
        import_kwh=import_kwh,
        export_kwh=export_kwh,
        pv_to_load_kwh=sum(row.pv_to_load_kwh for row in rows),
        pv_curtailed_kwh=sum(row.pv_curtailed_kwh for row in rows),
        import_cost_gbp=import_cost,
        export_revenue_gbp=export_revenue,
        energy_bill_gbp=energy_bill,
        standing_charge_gbp=standing_charge,
        total_bill_gbp=energy_bill + standing_charge,
    )


def _dispatch_vpp_revenue(
    dispatch_input: ResidentialHouseholdDispatchInput,
    rows: list[ResidentialHouseholdDispatchRow],
) -> ResidentialVPPRevenue | None:
    if dispatch_input.vpp_schedule is None:
        return None
    delivered: dict[str, float] = {}
    for event in dispatch_input.vpp_schedule.events:
        delivered[event.event_id] = sum(
            row.site_export_kwh
            for row in rows
            if row.delivery_start_utc >= event.event_start_utc
            and row.delivery_end_utc <= event.event_end_utc
        )
    return calculate_vpp_revenue(
        dispatch_input.vpp_schedule,
        sample_hours=sum(row.duration_h for row in rows),
        delivered_event_kwh=delivered,
    )


def _value(pyomo_value: Any) -> float:
    value = pyo.value(pyomo_value)
    return 0.0 if abs(value) < 1e-9 else float(value)
