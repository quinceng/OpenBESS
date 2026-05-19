from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator

from gb_bess_revenue_stack.phase4.scenarios import (
    Phase4MarketStackCaptureResult,
    Phase4SmokeWindowComparison,
)
from gb_bess_revenue_stack.policies.rolling_market_stack import (
    RollingMarketStackRun,
    RollingMarketStackScenarioResult,
)
from gb_bess_revenue_stack.schemas.base import ensure_aware_utc


class Phase4DashboardCacheInput(BaseModel):
    """Inputs required to build dashboard-ready Phase 4 cache artefacts."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    rolling_run: RollingMarketStackRun
    central_capture: Phase4MarketStackCaptureResult
    smoke_comparisons: list[Phase4SmokeWindowComparison]
    scenario_results: list[RollingMarketStackScenarioResult]
    caveats: list[str]
    created_at_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    schema_version: str = "0.1.0"
    code_version: str = "unknown"
    config_hash: str
    source_snapshot_hash: str
    input_run_ids: list[str]
    source_ids: list[str]
    source_labels: dict[str, str]
    licence_caveat_flags: list[str] = Field(
        default_factory=lambda: [
            "wholesale_proxy",
            "perfect_foresight_upper_bound",
            "rolling_no_leakage_policy",
            "eac_price_taking_proxy",
            "bm_excluded",
            "cm_scenario_only",
            "finance_scenario_appraisal",
            "benchmark_reconciliation_not_replication",
            "partial_sample_annualised",
        ]
    )
    known_at_policy: str = "synthetic_day_ahead_known_time"
    degradation_treatment: str = "not_modelled_in_phase4_smoke"
    central_or_sensitivity: str = "central_and_sensitivity"
    refresh_cadence: str = "manual rebuild before public release"

    @field_validator("created_at_utc")
    @classmethod
    def created_at_is_aware(cls, value: datetime) -> datetime:
        return ensure_aware_utc(value)


def write_phase4_dashboard_cache(
    payload: Phase4DashboardCacheInput,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Write compact Phase 4 artefacts matching the dashboard cache contract."""

    cache_dir = Path(output_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "manifest": cache_dir / "manifest.json",
        "executive_summary": cache_dir / "executive_summary.json",
        "policy_capture": cache_dir / "policy_capture.parquet",
        "revenue_stack": cache_dir / "revenue_stack.parquet",
        "scenario_sweeps": cache_dir / "scenario_sweeps.parquet",
        "caveats": cache_dir / "caveats.json",
    }
    _write_json(paths["manifest"], _manifest(payload, paths))
    _write_json(paths["executive_summary"], _executive_summary(payload))
    pd.DataFrame(_policy_capture_rows(payload)).to_parquet(paths["policy_capture"], index=False)
    pd.DataFrame(_revenue_stack_rows(payload)).to_parquet(paths["revenue_stack"], index=False)
    pd.DataFrame(_scenario_sweep_rows(payload.scenario_results)).to_parquet(
        paths["scenario_sweeps"],
        index=False,
    )
    _write_json(
        paths["caveats"],
        {
            "caveats": payload.caveats,
            "licence_caveat_flags": payload.licence_caveat_flags,
        },
    )
    return paths


def _manifest(payload: Phase4DashboardCacheInput, paths: dict[str, Path]) -> dict[str, Any]:
    return {
        "run_id": payload.run_id,
        "created_at_utc": payload.created_at_utc.isoformat(),
        "schema_version": payload.schema_version,
        "code_version": payload.code_version,
        "config_hash": payload.config_hash,
        "source_snapshot_hash": payload.source_snapshot_hash,
        "input_run_ids": payload.input_run_ids,
        "source_ids": payload.source_ids,
        "licence_caveat_flags": payload.licence_caveat_flags,
        "known_at_policy": payload.known_at_policy,
        "degradation_treatment": payload.degradation_treatment,
        "central_or_sensitivity": payload.central_or_sensitivity,
        "refresh_cadence": payload.refresh_cadence,
        "files": {key: path.name for key, path in paths.items() if key != "manifest"},
    }


def _executive_summary(payload: Phase4DashboardCacheInput) -> dict[str, Any]:
    central = payload.central_capture
    capture_ratios = {"central": central.capture_ratio}
    capture_ratios.update(
        {
            comparison.label: comparison.capture.capture_ratio
            for comparison in payload.smoke_comparisons
        }
    )
    return {
        "headline_period": f"{central.price_period_count} settlement periods "
        f"({central.sample_hours:.1f} hours)",
        "wholesale_only_perfect_foresight_revenue_gbp": None,
        "wholesale_only_rolling_revenue_gbp": None,
        "wholesale_plus_eac_perfect_foresight_revenue_gbp": central.perfect_total_revenue_gbp,
        "wholesale_plus_eac_rolling_revenue_gbp": central.rolling_total_revenue_gbp,
        "capture_ratios": capture_ratios,
        "top_caveats": payload.caveats[:5],
        "source_labels": payload.source_labels,
        "links": {
            "policy_capture": "policy_capture.parquet",
            "revenue_stack": "revenue_stack.parquet",
            "scenario_sweeps": "scenario_sweeps.parquet",
            "caveats": "caveats.json",
        },
    }


def _policy_capture_rows(payload: Phase4DashboardCacheInput) -> list[dict[str, Any]]:
    rows = [_capture_row("central", payload.central_capture)]
    rows.extend(
        _capture_row(comparison.label, comparison.capture)
        for comparison in payload.smoke_comparisons
    )
    return rows


def _capture_row(label: str, capture: Phase4MarketStackCaptureResult) -> dict[str, Any]:
    return {
        "label": label,
        "period_count": capture.price_period_count,
        "sample_hours": capture.sample_hours,
        "perfect_energy_revenue_gbp": capture.perfect_energy_revenue_gbp,
        "perfect_service_revenue_gbp": capture.perfect_service_revenue_gbp,
        "perfect_total_revenue_gbp": capture.perfect_total_revenue_gbp,
        "rolling_energy_revenue_gbp": capture.rolling_energy_revenue_gbp,
        "rolling_service_revenue_gbp": capture.rolling_service_revenue_gbp,
        "rolling_total_revenue_gbp": capture.rolling_total_revenue_gbp,
        "rolling_planned_revenue_gbp": capture.rolling_planned_revenue_gbp,
        "capture_ratio": capture.capture_ratio,
        "regret_gbp": capture.regret_gbp,
        "solver_failure_count": capture.solver_failure_count,
        "forecast_mae_gbp_per_mwh": capture.forecast_mae_gbp_per_mwh,
        "forecast_rmse_gbp_per_mwh": capture.forecast_rmse_gbp_per_mwh,
    }


def _revenue_stack_rows(payload: Phase4DashboardCacheInput) -> list[dict[str, Any]]:
    central = payload.central_capture
    return [
        {
            "basis": "perfect_foresight",
            "component": "wholesale_energy",
            "value_gbp": central.perfect_energy_revenue_gbp,
        },
        {
            "basis": "perfect_foresight",
            "component": "eac_availability",
            "value_gbp": central.perfect_service_revenue_gbp,
        },
        {
            "basis": "perfect_foresight",
            "component": "total",
            "value_gbp": central.perfect_total_revenue_gbp,
        },
        {
            "basis": "rolling_policy",
            "component": "wholesale_energy",
            "value_gbp": central.rolling_energy_revenue_gbp,
        },
        {
            "basis": "rolling_policy",
            "component": "eac_availability",
            "value_gbp": central.rolling_service_revenue_gbp,
        },
        {
            "basis": "rolling_policy",
            "component": "total",
            "value_gbp": central.rolling_total_revenue_gbp,
        },
    ]


def _scenario_sweep_rows(
    scenario_results: list[RollingMarketStackScenarioResult],
) -> list[dict[str, Any]]:
    return [
        {
            "scenario": result.name,
            "stress_label": result.stress_label,
            "period_count": result.period_count,
            "wholesale_price_scalar": result.wholesale_price_scalar,
            "eac_price_scalar": result.eac_price_scalar,
            "energy_revenue_gbp": result.realised_energy_revenue_gbp,
            "service_revenue_gbp": result.realised_service_revenue_gbp,
            "total_revenue_gbp": result.realised_total_revenue_gbp,
            "final_soc_mwh": result.final_soc_mwh,
        }
        for result in scenario_results
    ]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
