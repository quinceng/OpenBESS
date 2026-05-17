from __future__ import annotations

from datetime import datetime
from typing import Any

import pyomo.environ as pyo
from pydantic import BaseModel, ConfigDict, Field

from gb_bess_revenue_stack.optimisation.inputs import DispatchInput
from gb_bess_revenue_stack.optimisation.solve import SolverDiagnostics


class DispatchRow(BaseModel):
    """Solved dispatch row for a single period."""

    model_config = ConfigDict(extra="forbid")

    index: int
    delivery_start_utc: datetime
    delivery_end_utc: datetime
    duration_h: float
    price_gbp_per_mwh: float
    charge_mw: float
    discharge_mw: float
    soc_start_mwh: float
    soc_end_mwh: float
    net_export_mw: float
    period_revenue_gbp: float
    cumulative_revenue_gbp: float


class DispatchMetrics(BaseModel):
    """Headline Phase 2 energy-dispatch metrics."""

    model_config = ConfigDict(extra="forbid")

    total_revenue_gbp: float
    sample_hours: float = Field(gt=0)
    asset_power_mw: float = Field(gt=0)
    charged_mwh: float = Field(ge=0)
    discharged_mwh: float = Field(ge=0)
    energy_capacity_mwh: float = Field(gt=0)
    average_buy_price_gbp_per_mwh: float | None = None
    average_sell_price_gbp_per_mwh: float | None = None

    @property
    def annualised_gbp_per_mw_year(self) -> float:
        return self.total_revenue_gbp / self.sample_hours * 8760 / self.asset_power_mw

    @property
    def equivalent_throughput_cycles(self) -> float:
        return (self.charged_mwh + self.discharged_mwh) / (2 * self.energy_capacity_mwh)

    @property
    def captured_spread_gbp_per_mwh(self) -> float | None:
        if (
            self.average_buy_price_gbp_per_mwh is None
            or self.average_sell_price_gbp_per_mwh is None
        ):
            return None
        return self.average_sell_price_gbp_per_mwh - self.average_buy_price_gbp_per_mwh


class DispatchResult(BaseModel):
    """Stable result schema for solved energy-only dispatch."""

    model_config = ConfigDict(extra="forbid")

    rows: list[DispatchRow]
    metrics: DispatchMetrics
    solver: SolverDiagnostics
    terminal_soc_policy: str
    terminal_soc_target_mwh: float | None = None
    binary_dispatch: bool
    initial_soc_mwh: float
    final_soc_mwh: float

    @property
    def total_revenue_gbp(self) -> float:
        return self.metrics.total_revenue_gbp

    @property
    def charged_mwh(self) -> float:
        return self.metrics.charged_mwh

    @property
    def discharged_mwh(self) -> float:
        return self.metrics.discharged_mwh


def extract_dispatch_result(model: Any, solver: SolverDiagnostics) -> DispatchResult:
    """Extract a stable result object from a solved Pyomo model."""

    dispatch_input: DispatchInput = model.dispatch_input
    rows: list[DispatchRow] = []
    cumulative = 0.0
    charged_mwh = 0.0
    discharged_mwh = 0.0
    weighted_buy_cost = 0.0
    weighted_sell_revenue = 0.0
    for period in dispatch_input.periods:
        charge_mw = _value(model.charge_mw[period.index])
        discharge_mw = _value(model.discharge_mw[period.index])
        charge_mwh = charge_mw * period.duration_h
        discharge_mwh = discharge_mw * period.duration_h
        charged_mwh += charge_mwh
        discharged_mwh += discharge_mwh
        weighted_buy_cost += charge_mwh * period.price_gbp_per_mwh
        weighted_sell_revenue += discharge_mwh * period.price_gbp_per_mwh
        period_revenue = period.price_gbp_per_mwh * (discharge_mw - charge_mw) * period.duration_h
        cumulative += period_revenue
        rows.append(
            DispatchRow(
                index=period.index,
                delivery_start_utc=period.delivery_start_utc,
                delivery_end_utc=period.delivery_end_utc,
                duration_h=period.duration_h,
                price_gbp_per_mwh=period.price_gbp_per_mwh,
                charge_mw=charge_mw,
                discharge_mw=discharge_mw,
                soc_start_mwh=_value(model.soc_mwh[period.index]),
                soc_end_mwh=_value(model.soc_mwh[period.index + 1]),
                net_export_mw=discharge_mw - charge_mw,
                period_revenue_gbp=period_revenue,
                cumulative_revenue_gbp=cumulative,
            )
        )
    metrics = DispatchMetrics(
        total_revenue_gbp=cumulative,
        sample_hours=dispatch_input.sample_hours,
        asset_power_mw=dispatch_input.p_export_max_mw,
        charged_mwh=charged_mwh,
        discharged_mwh=discharged_mwh,
        energy_capacity_mwh=dispatch_input.energy_capacity_mwh,
        average_buy_price_gbp_per_mwh=(
            weighted_buy_cost / charged_mwh if charged_mwh > 1e-12 else None
        ),
        average_sell_price_gbp_per_mwh=(
            weighted_sell_revenue / discharged_mwh if discharged_mwh > 1e-12 else None
        ),
    )
    return DispatchResult(
        rows=rows,
        metrics=metrics,
        solver=solver,
        terminal_soc_policy=dispatch_input.terminal_soc_policy,
        terminal_soc_target_mwh=dispatch_input.terminal_soc_target_mwh,
        binary_dispatch=dispatch_input.binary_dispatch,
        initial_soc_mwh=dispatch_input.initial_soc_mwh,
        final_soc_mwh=_value(model.soc_mwh[dispatch_input.period_count]),
    )


def _value(pyomo_value: Any) -> float:
    value = pyo.value(pyomo_value)
    return 0.0 if abs(value) < 1e-9 else float(value)
