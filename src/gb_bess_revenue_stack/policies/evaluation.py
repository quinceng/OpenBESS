from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from gb_bess_revenue_stack.policies.rolling import RollingRun


class PolicyEvaluation(BaseModel):
    """Comparison of rolling policy against perfect foresight."""

    model_config = ConfigDict(extra="forbid")

    perfect_foresight_revenue_gbp: float
    rolling_realised_revenue_gbp: float
    rolling_planned_revenue_gbp: float
    capture_ratio: float | None
    regret_gbp: float
    solver_failure_count: int = Field(ge=0)
    forecast_mae_gbp_per_mwh: float
    forecast_rmse_gbp_per_mwh: float


class TerminalArtifactResult(BaseModel):
    """Diagnostic comparison for free-terminal end-drain artefacts."""

    model_config = ConfigDict(extra="forbid")

    artifact_detected: bool
    incremental_revenue_gbp: float
    cyclic_revenue_gbp: float
    free_terminal_revenue_gbp: float


def evaluate_rolling_policy(
    run: RollingRun,
    *,
    perfect_foresight_revenue_gbp: float,
) -> PolicyEvaluation:
    capture_ratio = (
        run.realised_revenue_gbp / perfect_foresight_revenue_gbp
        if abs(perfect_foresight_revenue_gbp) > 1e-9
        else None
    )
    return PolicyEvaluation(
        perfect_foresight_revenue_gbp=perfect_foresight_revenue_gbp,
        rolling_realised_revenue_gbp=run.realised_revenue_gbp,
        rolling_planned_revenue_gbp=run.planned_revenue_gbp,
        capture_ratio=capture_ratio,
        regret_gbp=perfect_foresight_revenue_gbp - run.realised_revenue_gbp,
        solver_failure_count=run.solver_failure_count,
        forecast_mae_gbp_per_mwh=_mean([step.forecast_mae_gbp_per_mwh for step in run.steps]),
        forecast_rmse_gbp_per_mwh=_mean([step.forecast_rmse_gbp_per_mwh for step in run.steps]),
    )


def detect_free_terminal_artifact(
    cyclic_run: RollingRun,
    free_terminal_run: RollingRun,
    *,
    tolerance_gbp: float = 1e-6,
) -> TerminalArtifactResult:
    incremental = free_terminal_run.realised_revenue_gbp - cyclic_run.realised_revenue_gbp
    return TerminalArtifactResult(
        artifact_detected=incremental > tolerance_gbp,
        incremental_revenue_gbp=incremental,
        cyclic_revenue_gbp=cyclic_run.realised_revenue_gbp,
        free_terminal_revenue_gbp=free_terminal_run.realised_revenue_gbp,
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
