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
    degradation_treatment: str = "linear throughput proxy"
    central_or_sensitivity: str = "central_and_sensitivity"
    refresh_cadence: str = "manual rebuild before public release"
    battery_energy_capacity_mwh: float | None = Field(default=None, gt=0)
    capex_gbp: float | None = Field(default=None, ge=0)
    finance_years: int = Field(default=15, ge=1)
    discount_rate: float = Field(default=0.08, ge=0)
    annual_revenue_decay_rate: float = Field(default=0.02, ge=0, le=1)
    degradation_cost_gbp_per_mwh_throughput: float = Field(default=2.0, ge=0)

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
        "degradation_summary": cache_dir / "degradation_summary.json",
        "finance_summary": cache_dir / "finance_summary.json",
        "finance_cashflows": cache_dir / "finance_cashflows.parquet",
        "benchmark_reconciliation": cache_dir / "benchmark_reconciliation.json",
    }
    degradation = _degradation_summary(payload)
    finance_summary, finance_cashflows = _finance_outputs(payload, degradation)
    benchmark = _benchmark_reconciliation(payload, finance_summary)

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
    _write_json(paths["degradation_summary"], degradation)
    _write_json(paths["finance_summary"], finance_summary)
    pd.DataFrame(finance_cashflows).to_parquet(paths["finance_cashflows"], index=False)
    _write_json(paths["benchmark_reconciliation"], benchmark)
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


def _degradation_summary(payload: Phase4DashboardCacheInput) -> dict[str, Any]:
    period_duration_h = (
        payload.central_capture.sample_hours / payload.central_capture.price_period_count
        if payload.central_capture.price_period_count
        else 0.0
    )
    throughput_mwh = sum(
        (step.executed_charge_mw + step.executed_discharge_mw)
        * step.executed_period_count
        * period_duration_h
        for step in payload.rolling_run.steps
    )
    capacity = payload.battery_energy_capacity_mwh
    equivalent_full_cycles = throughput_mwh / (2 * capacity) if capacity else None
    return {
        "degradation_scope": "linear throughput proxy",
        "throughput_mwh": throughput_mwh,
        "battery_energy_capacity_mwh": capacity,
        "equivalent_full_cycles": equivalent_full_cycles,
        "degradation_cost_gbp": throughput_mwh * payload.degradation_cost_gbp_per_mwh_throughput,
        "degradation_cost_gbp_per_mwh_throughput": (
            payload.degradation_cost_gbp_per_mwh_throughput
        ),
        "caveat": (
            "Throughput proxy only; no electrochemical, warranty-specific or "
            "rainflow degradation model."
        ),
    }


def _finance_outputs(
    payload: Phase4DashboardCacheInput,
    degradation: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    annualisation_factor = (
        8760 / payload.central_capture.sample_hours
        if payload.central_capture.sample_hours > 0
        else 0.0
    )
    annual_revenue = payload.central_capture.rolling_total_revenue_gbp * annualisation_factor
    annual_degradation_cost = float(degradation["degradation_cost_gbp"]) * annualisation_factor
    capex = payload.capex_gbp or 0.0
    rows: list[dict[str, Any]] = []
    cumulative = -capex
    rows.append(
        {
            "year": 0,
            "gross_revenue_gbp": 0.0,
            "degradation_cost_gbp": 0.0,
            "net_cashflow_gbp": -capex,
            "discount_factor": 1.0,
            "discounted_cashflow_gbp": -capex,
            "cumulative_cashflow_gbp": cumulative,
        }
    )
    for year in range(1, payload.finance_years + 1):
        gross = annual_revenue * (1 - payload.annual_revenue_decay_rate) ** (year - 1)
        net = gross - annual_degradation_cost
        cumulative += net
        discount_factor = 1 / (1 + payload.discount_rate) ** year
        rows.append(
            {
                "year": year,
                "gross_revenue_gbp": gross,
                "degradation_cost_gbp": annual_degradation_cost,
                "net_cashflow_gbp": net,
                "discount_factor": discount_factor,
                "discounted_cashflow_gbp": net * discount_factor,
                "cumulative_cashflow_gbp": cumulative,
            }
        )
    npv = sum(row["discounted_cashflow_gbp"] for row in rows)
    payback_year = next(
        (row["year"] for row in rows if row["year"] > 0 and row["cumulative_cashflow_gbp"] >= 0),
        None,
    )
    return (
        {
            "finance_scope": "illustrative scenario appraisal",
            "not_bankability_statement": (
                "This is not investment advice, bankability analysis or a "
                "substitute for commercial due diligence."
            ),
            "capex_gbp": capex,
            "annualised_rolling_revenue_gbp": annual_revenue,
            "annualised_degradation_cost_gbp": annual_degradation_cost,
            "npv_gbp": npv,
            "simple_payback_year": payback_year,
            "finance_years": payload.finance_years,
            "discount_rate": payload.discount_rate,
            "annual_revenue_decay_rate": payload.annual_revenue_decay_rate,
            "annualisation_caveat": "Partial sample annualised from cached Phase 4 run.",
        },
        rows,
    )


def _benchmark_reconciliation(
    payload: Phase4DashboardCacheInput,
    finance_summary: dict[str, Any],
) -> dict[str, Any]:
    return {
        "reconciliation_scope": "benchmark reconciliation, not replication",
        "model_annualised_rolling_revenue_gbp": finance_summary["annualised_rolling_revenue_gbp"],
        "rows": [
            {
                "benchmark_label": "public benchmark anchor placeholder",
                "benchmark_value_gbp": None,
                "model_value_gbp": finance_summary["annualised_rolling_revenue_gbp"],
                "delta_gbp": None,
                "methodology_status": "unknown_public_anchor_placeholder",
                "caveat_labels": [
                    "benchmark_reconciliation_not_replication",
                    "partial_sample_annualised",
                    *payload.licence_caveat_flags,
                ],
            }
        ],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
