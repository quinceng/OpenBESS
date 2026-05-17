from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from gb_bess_revenue_stack.config.models import AssetConfig, SolverConfig
from gb_bess_revenue_stack.optimisation.inputs import build_dispatch_input
from gb_bess_revenue_stack.optimisation.model_factory import build_energy_dispatch_model
from gb_bess_revenue_stack.optimisation.results import DispatchRow, extract_dispatch_result
from gb_bess_revenue_stack.optimisation.solve import OptimisationSolveError, solve_dispatch_model
from gb_bess_revenue_stack.policies.forecasts import ForecastModel, ForecastPoint
from gb_bess_revenue_stack.policies.information_set import build_information_set
from gb_bess_revenue_stack.schemas.base import ensure_aware_utc
from gb_bess_revenue_stack.schemas.market import WholesalePricePoint


class RollingPolicyError(RuntimeError):
    """Raised for controlled rolling-policy failures."""


class RollingConfig(BaseModel):
    """Configuration for energy-only rolling policy evaluation."""

    model_config = ConfigDict(extra="forbid")

    horizon_periods: int = Field(gt=0)
    step_periods: int = Field(default=1, gt=0)
    terminal_soc_policy: str = "cyclic"
    terminal_soc_target_mwh: float | None = Field(default=None, ge=0)
    binary_dispatch: bool = True
    solver: SolverConfig = SolverConfig(time_limit_seconds=60, mip_gap=0.001)
    evaluation_start_utc: datetime | None = None

    @field_validator("terminal_soc_policy")
    @classmethod
    def terminal_policy_supported(cls, value: str) -> str:
        if value not in {"cyclic", "free", "target"}:
            msg = "terminal_soc_policy must be 'cyclic', 'free' or 'target'."
            raise ValueError(msg)
        return value

    @field_validator("evaluation_start_utc")
    @classmethod
    def evaluation_start_is_aware(cls, value: datetime | None) -> datetime | None:
        return ensure_aware_utc(value) if value is not None else None

    @model_validator(mode="after")
    def target_policy_has_target(self) -> RollingConfig:
        if self.terminal_soc_policy == "target" and self.terminal_soc_target_mwh is None:
            msg = "terminal_soc_target_mwh is required when terminal_soc_policy='target'."
            raise ValueError(msg)
        return self


class RollingStepRecord(BaseModel):
    """Trace record for a single rolling decision."""

    model_config = ConfigDict(extra="forbid")

    decision_time_utc: datetime
    horizon_period_count: int
    executed_period_count: int
    information_source_hash: str
    excluded_future_row_count: int
    forecast_model: str
    forecast_is_oracle: bool
    forecast_mae_gbp_per_mwh: float
    forecast_rmse_gbp_per_mwh: float
    soc_start_mwh: float
    soc_end_mwh: float
    planned_terminal_soc_mwh: float
    executed_charge_mw: float
    executed_discharge_mw: float
    realised_revenue_gbp: float
    planned_revenue_gbp: float
    solver_termination_condition: str
    solver_wall_time_seconds: float

    @field_validator("decision_time_utc")
    @classmethod
    def decision_time_is_aware(cls, value: datetime) -> datetime:
        return ensure_aware_utc(value)


class RollingRun(BaseModel):
    """Complete rolling-policy result."""

    model_config = ConfigDict(extra="forbid")

    steps: list[RollingStepRecord]
    realised_revenue_gbp: float
    planned_revenue_gbp: float
    final_soc_mwh: float
    initial_soc_mwh: float
    terminal_soc_policy: str
    terminal_soc_target_mwh: float | None = None
    forecast_model: str
    solver_failure_count: int


def run_rolling_policy(
    *,
    prices: list[WholesalePricePoint],
    asset: AssetConfig,
    initial_soc_mwh: float,
    forecast_model: ForecastModel,
    config: RollingConfig,
) -> RollingRun:
    """Run a receding-horizon energy-only policy over realised prices."""

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
    soc_mwh = initial_soc_mwh
    steps: list[RollingStepRecord] = []
    cursor = 0
    solver_failure_count = 0
    while cursor < len(evaluation_prices):
        horizon = evaluation_prices[cursor : cursor + config.horizon_periods]
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
        try:
            dispatch_input = build_dispatch_input(
                forecast_prices,
                asset=asset,
                initial_soc_mwh=soc_mwh,
                terminal_soc_policy=config.terminal_soc_policy,  # type: ignore[arg-type]
                terminal_soc_target_mwh=config.terminal_soc_target_mwh,
                binary_dispatch=config.binary_dispatch,
                data_manifest_ref=info.source_data_hash,
                config_hash=f"{forecast.source_model}:{config.model_dump_json()}",
            )
            model = build_energy_dispatch_model(dispatch_input)
            diagnostics = solve_dispatch_model(model, config.solver)
        except (OptimisationSolveError, ValueError) as exc:
            solver_failure_count += 1
            msg = f"Rolling solve failed at {decision_time.isoformat()}: {exc}"
            raise RollingPolicyError(msg) from exc
        result = extract_dispatch_result(model, diagnostics)
        execute_count = min(config.step_periods, len(horizon), len(result.rows))
        step_rows = result.rows[:execute_count]
        realised_revenue = 0.0
        planned_revenue = 0.0
        for offset, row in enumerate(step_rows):
            actual = horizon[offset]
            realised_revenue += (
                actual.price_gbp_per_mwh * (row.discharge_mw - row.charge_mw) * actual.duration_h
            )
            planned_revenue += row.period_revenue_gbp
        last_row = step_rows[-1]
        soc_mwh = last_row.soc_end_mwh
        forecast_errors = [
            forecast.points[index].forecast_value_gbp_per_mwh - horizon[index].price_gbp_per_mwh
            for index in range(len(horizon))
        ]
        steps.append(
            RollingStepRecord(
                decision_time_utc=decision_time,
                horizon_period_count=len(horizon),
                executed_period_count=execute_count,
                information_source_hash=info.source_data_hash,
                excluded_future_row_count=info.excluded_future_row_count,
                forecast_model=forecast.source_model,
                forecast_is_oracle=any(point.is_oracle for point in forecast.points),
                forecast_mae_gbp_per_mwh=_mae(forecast_errors),
                forecast_rmse_gbp_per_mwh=_rmse(forecast_errors),
                soc_start_mwh=row_zero_soc_start(step_rows),
                soc_end_mwh=soc_mwh,
                planned_terminal_soc_mwh=result.final_soc_mwh,
                executed_charge_mw=sum(row.charge_mw for row in step_rows) / execute_count,
                executed_discharge_mw=sum(row.discharge_mw for row in step_rows) / execute_count,
                realised_revenue_gbp=realised_revenue,
                planned_revenue_gbp=planned_revenue,
                solver_termination_condition=diagnostics.termination_condition,
                solver_wall_time_seconds=diagnostics.wall_time_seconds,
            )
        )
        cursor += execute_count
    return RollingRun(
        steps=steps,
        realised_revenue_gbp=sum(step.realised_revenue_gbp for step in steps),
        planned_revenue_gbp=sum(step.planned_revenue_gbp for step in steps),
        final_soc_mwh=soc_mwh,
        initial_soc_mwh=initial_soc_mwh,
        terminal_soc_policy=config.terminal_soc_policy,
        terminal_soc_target_mwh=config.terminal_soc_target_mwh,
        forecast_model=forecast_model.source_model,
        solver_failure_count=solver_failure_count,
    )


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


def row_zero_soc_start(step_rows: list[DispatchRow]) -> float:
    return step_rows[0].soc_start_mwh


def _mae(errors: list[float]) -> float:
    return sum(abs(error) for error in errors) / len(errors) if errors else 0.0


def _rmse(errors: list[float]) -> float:
    return (sum(error * error for error in errors) / len(errors)) ** 0.5 if errors else 0.0
