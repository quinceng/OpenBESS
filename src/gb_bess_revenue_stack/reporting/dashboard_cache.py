from __future__ import annotations

import json
from datetime import UTC, date, datetime
from math import ceil
from pathlib import Path
from typing import Any, cast

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from gb_bess_revenue_stack.phase4.scenarios import (
    Phase4MarketStackCaptureResult,
    Phase4SmokeWindowComparison,
)
from gb_bess_revenue_stack.policies.rolling_market_stack import (
    RollingMarketStackRun,
    RollingMarketStackScenarioResult,
)
from gb_bess_revenue_stack.reporting.stack_series import (
    DEFAULT_STACK_WINDOWS,
    StackSeriesRow,
    StackSeriesWindowLabel,
    build_window_eligibility,
    write_stack_series,
)
from gb_bess_revenue_stack.schemas.base import ensure_aware_utc

STACK_WINDOW_LABEL_PRIORITY: dict[str, int] = {
    window.label: index for index, window in enumerate(DEFAULT_STACK_WINDOWS)
}


class PublicBenchmarkAnchor(BaseModel):
    """Public benchmark row used for reconciliation context, not calibration."""

    model_config = ConfigDict(extra="forbid")

    benchmark_label: str
    source_id: str = "PUBLIC_BENCHMARK_ANCHORS"
    source_url: str
    publication_date: date | None = None
    access_date: date = date(2026, 5, 19)
    methodology_status: str
    component_scope: str
    benchmark_value_gbp_per_mw_year: float | None = Field(default=None, ge=0)
    caveat_labels: list[str] = Field(
        default_factory=lambda: ["benchmark_reconciliation_not_replication"]
    )


def default_public_benchmark_anchors() -> list[PublicBenchmarkAnchor]:
    """Return sourced public benchmark anchors used by the Release 1 cache."""

    return [
        PublicBenchmarkAnchor(
            benchmark_label="Modo GB BESS 2024 average",
            source_url=(
                "https://modoenergy.com/research/"
                "battery-revenues-operational-strategy-2024-gb-benchmark-year-review/"
            ),
            publication_date=date(2025, 2, 18),
            access_date=date(2026, 5, 19),
            methodology_status="public_summary_with_methodology_reference",
            component_scope="GB BESS average revenues in 2024, public article summary",
            benchmark_value_gbp_per_mw_year=50_000,
            caveat_labels=[
                "benchmark_reconciliation_not_replication",
                "public_summary_value",
            ],
        ),
        PublicBenchmarkAnchor(
            benchmark_label="Modo GB BESS Index April 2024 including Capacity Market",
            source_url=(
                "https://modoenergy.com/research/"
                "gb-benchmark-index-battery-energy-storage-april-2024-revenue"
            ),
            publication_date=date(2024, 5, 3),
            access_date=date(2026, 5, 19),
            methodology_status="public_summary_with_modo_gb_index_methodology",
            component_scope="April 2024 annualised GB BESS Index including Capacity Market",
            benchmark_value_gbp_per_mw_year=54_000,
            caveat_labels=[
                "benchmark_reconciliation_not_replication",
                "includes_capacity_market",
                "public_summary_value",
            ],
        ),
    ]


class Phase4FinanceAssumptions(BaseModel):
    """Configurable Phase 5 finance and benchmark assumptions."""

    model_config = ConfigDict(extra="forbid")

    finance_years: int = Field(default=15, ge=1)
    discount_rate: float = Field(default=0.08, ge=0)
    annual_revenue_decay_rate: float = Field(default=0.02, ge=0, le=1)
    degradation_cost_gbp_per_mwh_throughput: float = Field(default=2.0, ge=0)
    benchmark_anchors: list[PublicBenchmarkAnchor] = Field(
        default_factory=default_public_benchmark_anchors
    )


def load_phase4_finance_assumptions(path: str | Path | None = None) -> Phase4FinanceAssumptions:
    """Load Phase 5 finance assumptions from YAML, or return Release 1 defaults."""

    if path is None:
        return Phase4FinanceAssumptions()
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if raw is None:
        return Phase4FinanceAssumptions()
    if not isinstance(raw, dict):
        msg = "Finance assumptions YAML must contain a mapping."
        raise ValueError(msg)
    return Phase4FinanceAssumptions.model_validate(raw)


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
            "not_a_market_index",
        ]
    )
    known_at_policy: str = "synthetic_day_ahead_known_time"
    degradation_treatment: str = "linear throughput proxy"
    central_or_sensitivity: str = "central_and_sensitivity"
    refresh_cadence: str = "manual rebuild before public release"
    battery_energy_capacity_mwh: float | None = Field(default=None, gt=0)
    battery_power_mw: float | None = Field(default=None, gt=0)
    stack_series_asset_id: str = Field(min_length=1)
    capex_gbp: float | None = Field(default=None, ge=0)
    finance_assumptions: Phase4FinanceAssumptions = Field(default_factory=Phase4FinanceAssumptions)

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
        "eac_commitments": cache_dir / "eac_commitments.parquet",
        "data_quality": cache_dir / "data_quality.json",
    }
    degradation = _degradation_summary(payload)
    finance_summary, finance_cashflows = _finance_outputs(payload, degradation)
    benchmark = _benchmark_reconciliation(payload, finance_summary)
    stack_series_paths = write_stack_series(_stack_series_rows(payload, degradation), cache_dir)
    paths["stack_series_parquet"] = stack_series_paths["parquet"]
    paths["stack_series_csv"] = stack_series_paths["csv"]

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
    pd.DataFrame(
        _eac_commitment_rows(payload),
        columns=[
            "step_index",
            "decision_time_utc",
            "service_model_label",
            "direction",
            "committed_mw",
            "executed_period_count",
        ],
    ).to_parquet(paths["eac_commitments"], index=False)
    _write_json(paths["data_quality"], _data_quality(payload))
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
        "source_labels": payload.source_labels,
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
        "degradation_cost_gbp": throughput_mwh
        * payload.finance_assumptions.degradation_cost_gbp_per_mwh_throughput,
        "degradation_cost_gbp_per_mwh_throughput": (
            payload.finance_assumptions.degradation_cost_gbp_per_mwh_throughput
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
    assumptions = payload.finance_assumptions
    annualisation_eligible = _annualisation_eligible(payload)
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
    if not annualisation_eligible:
        return (
            {
                "finance_scope": "illustrative scenario appraisal",
                "not_bankability_statement": (
                    "This is not investment advice, bankability analysis or a "
                    "substitute for commercial due diligence."
                ),
                "capex_gbp": capex,
                "annualised_rolling_revenue_gbp": None,
                "annualised_degradation_cost_gbp": None,
                "npv_gbp": None,
                "simple_payback_year": None,
                "finance_years": assumptions.finance_years,
                "discount_rate": assumptions.discount_rate,
                "annual_revenue_decay_rate": assumptions.annual_revenue_decay_rate,
                "finance_assumptions": assumptions.model_dump(
                    mode="json",
                    exclude={"benchmark_anchors"},
                ),
                "annualisation_eligible": False,
                "annualisation_caveat": (
                    "Annualised finance suppressed until stack-series coverage gates pass."
                ),
            },
            rows,
        )

    annualisation_factor = (
        8760 / payload.central_capture.sample_hours
        if payload.central_capture.sample_hours > 0
        else 0.0
    )
    annual_revenue = payload.central_capture.rolling_total_revenue_gbp * annualisation_factor
    annual_degradation_cost = float(degradation["degradation_cost_gbp"]) * annualisation_factor

    for year in range(1, assumptions.finance_years + 1):
        gross = annual_revenue * (1 - assumptions.annual_revenue_decay_rate) ** (year - 1)
        net = gross - annual_degradation_cost
        cumulative += net
        discount_factor = 1 / (1 + assumptions.discount_rate) ** year
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
            "finance_years": assumptions.finance_years,
            "discount_rate": assumptions.discount_rate,
            "annual_revenue_decay_rate": assumptions.annual_revenue_decay_rate,
            "finance_assumptions": assumptions.model_dump(
                mode="json",
                exclude={"benchmark_anchors"},
            ),
            "annualisation_eligible": True,
            "annualisation_caveat": _annualisation_caveat(payload),
        },
        rows,
    )


def _benchmark_reconciliation(
    payload: Phase4DashboardCacheInput,
    finance_summary: dict[str, Any],
) -> dict[str, Any]:
    model_value = finance_summary["annualised_rolling_revenue_gbp"]
    model_per_mw = (
        model_value / payload.battery_power_mw
        if model_value is not None and payload.battery_power_mw
        else None
    )
    return {
        "reconciliation_scope": "benchmark reconciliation, not replication",
        "model_annualised_rolling_revenue_gbp": model_value,
        "model_annualised_rolling_revenue_gbp_per_mw": model_per_mw,
        "rows": [
            _benchmark_row(anchor, model_per_mw, _stack_series_caveat_flags(payload))
            for anchor in payload.finance_assumptions.benchmark_anchors
        ],
    }


def _benchmark_row(
    anchor: PublicBenchmarkAnchor,
    model_per_mw: float | None,
    caveat_flags: list[str],
) -> dict[str, Any]:
    benchmark_value = anchor.benchmark_value_gbp_per_mw_year
    delta = (
        None if benchmark_value is None or model_per_mw is None else model_per_mw - benchmark_value
    )
    return {
        "benchmark_label": anchor.benchmark_label,
        "source_id": anchor.source_id,
        "source_url": anchor.source_url,
        "publication_date": anchor.publication_date.isoformat()
        if anchor.publication_date is not None
        else None,
        "access_date": anchor.access_date.isoformat(),
        "methodology_status": anchor.methodology_status,
        "component_scope": anchor.component_scope,
        "benchmark_value_gbp_per_mw_year": benchmark_value,
        "model_value_gbp_per_mw_year": model_per_mw,
        "delta_gbp_per_mw_year": delta,
        "caveat_labels": sorted(
            {
                *anchor.caveat_labels,
                "benchmark_reconciliation_not_replication",
                *caveat_flags,
            }
        ),
    }


def _eac_commitment_rows(payload: Phase4DashboardCacheInput) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, step in enumerate(payload.rolling_run.steps):
        for direction, commitments in (
            ("up", step.executed_reserve_up_mw),
            ("down", step.executed_reserve_down_mw),
        ):
            for service_model_label, committed_mw in commitments.items():
                rows.append(
                    {
                        "step_index": index,
                        "decision_time_utc": step.decision_time_utc.isoformat(),
                        "service_model_label": service_model_label,
                        "direction": direction,
                        "committed_mw": committed_mw,
                        "executed_period_count": step.executed_period_count,
                    }
                )
    return rows


def _stack_series_rows(
    payload: Phase4DashboardCacheInput,
    degradation: dict[str, Any],
) -> list[StackSeriesRow]:
    central = payload.central_capture
    caveat_flags = _stack_series_caveat_flags(payload)
    window_label = _primary_stack_series_window_label(payload)
    return [
        StackSeriesRow(
            timestamp_utc=payload.created_at_utc,
            window_label=window_label,
            asset_id=payload.stack_series_asset_id,
            basis="perfect_foresight",
            wholesale_energy_gbp=central.perfect_energy_revenue_gbp,
            eac_availability_gbp=central.perfect_service_revenue_gbp,
            degradation_cost_gbp=0,
            cm_annual_scenario_gbp_per_mw_year=None,
            caveat_flags=caveat_flags,
        ),
        StackSeriesRow(
            timestamp_utc=payload.created_at_utc,
            window_label=window_label,
            asset_id=payload.stack_series_asset_id,
            basis="rolling_policy",
            wholesale_energy_gbp=central.rolling_energy_revenue_gbp,
            eac_availability_gbp=central.rolling_service_revenue_gbp,
            degradation_cost_gbp=float(degradation["degradation_cost_gbp"]),
            cm_annual_scenario_gbp_per_mw_year=None,
            caveat_flags=caveat_flags,
        ),
    ]


def _data_quality(payload: Phase4DashboardCacheInput) -> dict[str, Any]:
    return {
        "run_id": payload.run_id,
        "source_ids": payload.source_ids,
        "source_snapshot_hash": payload.source_snapshot_hash,
        "known_at_policy": payload.known_at_policy,
        "licence_caveat_flags": payload.licence_caveat_flags,
        "price_period_count": payload.central_capture.price_period_count,
        "solver_failure_count": payload.rolling_run.solver_failure_count,
        "excluded_future_row_count": sum(
            step.excluded_future_row_count for step in payload.rolling_run.steps
        ),
        "service_cell_count": sum(step.service_cell_count for step in payload.rolling_run.steps),
        "excluded_service_cell_count": sum(
            step.excluded_service_cell_count for step in payload.rolling_run.steps
        ),
        "caveat_count": len(payload.caveats),
        "stack_series_windows": _stack_series_window_eligibility(payload),
    }


def _stack_series_window_eligibility(payload: Phase4DashboardCacheInput) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for window in DEFAULT_STACK_WINDOWS:
        expected_period_count, expected_period_basis = _expected_period_count_for_window(
            payload,
            window.minimum_days,
            window.expected_period_basis,
        )
        row = build_window_eligibility(
            observed_period_count=payload.central_capture.price_period_count,
            expected_period_count=expected_period_count,
            window_label=window.label,
        ).model_dump(mode="json")
        row["expected_period_basis"] = expected_period_basis
        rows.append(row)
    return rows


def _stack_series_caveat_flags(payload: Phase4DashboardCacheInput) -> list[str]:
    primary_window = _primary_stack_series_window(payload)
    return sorted(
        {
            *payload.licence_caveat_flags,
            *[str(flag) for flag in primary_window["caveat_flags"]],
        }
    )


def _expected_period_count_for_window(
    payload: Phase4DashboardCacheInput,
    minimum_days: int,
    expected_period_basis: str,
) -> tuple[int, str]:
    fixed_minimum_period_count = minimum_days * 48
    if expected_period_basis != "calendar_ytd":
        return fixed_minimum_period_count, "minimum_days_48_settlement_periods"

    year_start = datetime(payload.created_at_utc.year, 1, 1, tzinfo=UTC)
    elapsed_seconds = (payload.created_at_utc - year_start).total_seconds()
    elapsed_ytd_period_count = max(1, ceil(elapsed_seconds / 1800))
    return (
        max(fixed_minimum_period_count, elapsed_ytd_period_count),
        "calendar_ytd_from_created_at_utc_with_minimum_days_floor",
    )


def _primary_stack_series_window_label(
    payload: Phase4DashboardCacheInput,
) -> StackSeriesWindowLabel:
    return cast(StackSeriesWindowLabel, _primary_stack_series_window(payload)["window_label"])


def _primary_stack_series_window(payload: Phase4DashboardCacheInput) -> dict[str, Any]:
    windows = _stack_series_window_eligibility(payload)
    annualisation_windows = [window for window in windows if window["eligible_for_annualisation"]]
    if annualisation_windows:
        return _preferred_stack_series_window(annualisation_windows)

    covered_windows = [window for window in windows if float(window["coverage_pct"]) >= 1.0]
    if covered_windows:
        return _preferred_stack_series_window(covered_windows)

    return windows[0]


def _preferred_stack_series_window(
    windows: list[dict[str, Any]],
) -> dict[str, Any]:
    return max(
        windows,
        key=lambda window: (
            int(window["expected_period_count"]),
            STACK_WINDOW_LABEL_PRIORITY.get(str(window["window_label"]), -1),
        ),
    )


def _annualisation_caveat(payload: Phase4DashboardCacheInput) -> str:
    primary_window = _primary_stack_series_window(payload)
    window_label = primary_window["window_label"]
    if "partial_sample_annualised" in primary_window["caveat_flags"]:
        return f"Partial sample annualised from eligible {window_label} stack-series window."
    return f"Annualised from eligible {window_label} stack-series coverage window."


def _annualisation_eligible(payload: Phase4DashboardCacheInput) -> bool:
    return any(
        window["eligible_for_annualisation"] for window in _stack_series_window_eligibility(payload)
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
