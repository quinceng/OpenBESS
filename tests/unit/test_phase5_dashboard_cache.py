from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from gb_bess_revenue_stack.phase4.scenarios import Phase4MarketStackCaptureResult
from gb_bess_revenue_stack.policies.rolling_market_stack import (
    RollingMarketStackRun,
    RollingMarketStackScenarioResult,
    RollingMarketStackStepRecord,
)
from gb_bess_revenue_stack.reporting.dashboard_cache import (
    Phase4DashboardCacheInput,
    Phase4FinanceAssumptions,
    load_phase4_finance_assumptions,
    write_phase4_dashboard_cache,
)

pytestmark = pytest.mark.unit


def test_phase5_dashboard_cache_writes_degradation_finance_and_benchmark_files(
    tmp_path: Path,
) -> None:
    paths = write_phase4_dashboard_cache(_phase5_payload(), tmp_path)

    assert (tmp_path / "degradation_summary.json").exists()
    assert (tmp_path / "finance_summary.json").exists()
    assert (tmp_path / "finance_cashflows.parquet").exists()
    assert (tmp_path / "benchmark_reconciliation.json").exists()
    assert (tmp_path / "eac_commitments.parquet").exists()
    assert (tmp_path / "data_quality.json").exists()
    assert (tmp_path / "stack_series.parquet").exists()
    assert (tmp_path / "stack_series.csv").exists()
    assert paths["stack_series_parquet"] == tmp_path / "stack_series.parquet"
    assert paths["stack_series_csv"] == tmp_path / "stack_series.csv"

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"]["degradation_summary"] == "degradation_summary.json"
    assert manifest["files"]["finance_cashflows"] == "finance_cashflows.parquet"
    assert manifest["files"]["benchmark_reconciliation"] == "benchmark_reconciliation.json"
    assert manifest["files"]["eac_commitments"] == "eac_commitments.parquet"
    assert manifest["files"]["data_quality"] == "data_quality.json"
    assert manifest["files"]["stack_series_parquet"] == "stack_series.parquet"
    assert manifest["files"]["stack_series_csv"] == "stack_series.csv"
    assert "not_a_market_index" in manifest["licence_caveat_flags"]
    assert "partial_sample_annualised" not in manifest["licence_caveat_flags"]


def test_phase5_cache_labels_finance_as_scenario_appraisal_not_bankability(
    tmp_path: Path,
) -> None:
    write_phase4_dashboard_cache(_phase5_payload(), tmp_path)

    finance = json.loads((tmp_path / "finance_summary.json").read_text(encoding="utf-8"))
    cashflows = pd.read_parquet(tmp_path / "finance_cashflows.parquet")
    degradation = json.loads((tmp_path / "degradation_summary.json").read_text(encoding="utf-8"))
    benchmark = json.loads((tmp_path / "benchmark_reconciliation.json").read_text(encoding="utf-8"))

    assert finance["finance_scope"] == "illustrative scenario appraisal"
    assert "bankability" not in finance["finance_scope"]
    assert finance["annualisation_eligible"] is False
    assert finance["annualised_rolling_revenue_gbp"] is None
    assert finance["annualised_degradation_cost_gbp"] is None
    assert finance["npv_gbp"] is None
    assert finance["simple_payback_year"] is None
    assert "coverage gates pass" in finance["annualisation_caveat"]
    assert set(cashflows["year"]) == {0}
    assert degradation["throughput_mwh"] > 0
    assert degradation["equivalent_full_cycles"] > 0
    assert benchmark["reconciliation_scope"] == "benchmark reconciliation, not replication"
    assert benchmark["model_annualised_rolling_revenue_gbp"] is None
    assert benchmark["model_annualised_rolling_revenue_gbp_per_mw"] is None
    assert benchmark["rows"][0]["model_value_gbp_per_mw_year"] is None
    assert benchmark["rows"][0]["delta_gbp_per_mw_year"] is None
    assert "partial_sample_annualised" in benchmark["rows"][0]["caveat_labels"]
    assert benchmark["rows"][0]["source_url"].startswith("https://")
    assert benchmark["rows"][0]["access_date"] == "2026-05-19"
    assert benchmark["rows"][0]["methodology_status"] != "unknown_public_anchor_placeholder"


def test_phase5_finance_outputs_match_hand_calculated_npv_and_payback(
    tmp_path: Path,
) -> None:
    assumptions = Phase4FinanceAssumptions(
        finance_years=3,
        discount_rate=0.10,
        annual_revenue_decay_rate=0,
        degradation_cost_gbp_per_mwh_throughput=0,
        benchmark_anchors=[],
    )
    payload = _phase5_payload().model_copy(
        update={
            "capex_gbp": 1_000,
            "finance_assumptions": assumptions,
        }
    )
    payload.central_capture.rolling_total_revenue_gbp = 600
    payload.central_capture.price_period_count = 365 * 48
    payload.central_capture.sample_hours = 8760

    write_phase4_dashboard_cache(payload, tmp_path)

    finance = json.loads((tmp_path / "finance_summary.json").read_text(encoding="utf-8"))
    cashflows = pd.read_parquet(tmp_path / "finance_cashflows.parquet")
    expected_npv = -1000 + 600 / 1.1 + 600 / (1.1**2) + 600 / (1.1**3)

    assert finance["npv_gbp"] == pytest.approx(expected_npv)
    assert finance["annualisation_eligible"] is True
    assert finance["annualisation_caveat"] == (
        "Annualised from eligible trailing_12m stack-series coverage window."
    )
    assert finance["simple_payback_year"] == 2
    assert cashflows.loc[cashflows["year"] == 1, "discounted_cashflow_gbp"].iloc[
        0
    ] == pytest.approx(600 / 1.1)
    assert finance["finance_assumptions"]["discount_rate"] == pytest.approx(0.10)


def test_phase5_finance_assumptions_load_from_yaml(tmp_path: Path) -> None:
    assumptions_path = tmp_path / "finance_assumptions.yaml"
    assumptions_path.write_text(
        "\n".join(
            [
                "finance_years: 7",
                "discount_rate: 0.06",
                "annual_revenue_decay_rate: 0.015",
                "degradation_cost_gbp_per_mwh_throughput: 4.5",
                "benchmark_anchors:",
                "  - benchmark_label: Modo GB BESS 2024 average",
                "    source_id: PUBLIC_BENCHMARK_ANCHORS",
                "    source_url: https://modoenergy.com/research/battery-revenues-operational-strategy-2024-gb-benchmark-year-review/",
                "    publication_date: '2025-02-18'",
                "    access_date: '2026-05-19'",
                "    methodology_status: public_summary_with_methodology_reference",
                "    component_scope: GB BESS average revenues in 2024",
                "    benchmark_value_gbp_per_mw_year: 50000",
                "    caveat_labels:",
                "      - benchmark_reconciliation_not_replication",
            ]
        ),
        encoding="utf-8",
    )

    assumptions = load_phase4_finance_assumptions(assumptions_path)

    assert assumptions.finance_years == 7
    assert assumptions.discount_rate == pytest.approx(0.06)
    assert assumptions.degradation_cost_gbp_per_mwh_throughput == pytest.approx(4.5)
    assert assumptions.benchmark_anchors[0].benchmark_value_gbp_per_mw_year == pytest.approx(50_000)


def test_phase5_cache_writes_eac_commitments_and_data_quality(tmp_path: Path) -> None:
    write_phase4_dashboard_cache(_phase5_payload(), tmp_path)

    commitments = pd.read_parquet(tmp_path / "eac_commitments.parquet")
    data_quality = json.loads((tmp_path / "data_quality.json").read_text(encoding="utf-8"))
    stack_windows = data_quality["stack_series_windows"]

    assert set(commitments["service_model_label"]) == {"dynamic_containment_low"}
    assert set(commitments["direction"]) == {"up"}
    assert commitments["committed_mw"].sum() == pytest.approx(0.25)
    assert data_quality["known_at_policy"] == "synthetic_day_ahead_known_time"
    assert data_quality["solver_failure_count"] == 0
    assert data_quality["excluded_future_row_count"] == 0
    assert data_quality["source_ids"] == ["PROJECT_CONVENTION"]
    assert [window["window_label"] for window in stack_windows] == [
        "7d",
        "30d",
        "90d",
        "ytd",
        "trailing_12m",
    ]
    assert [window["observed_period_count"] for window in stack_windows] == [4, 4, 4, 4, 4]
    assert [window["expected_period_count"] for window in stack_windows] == [
        7 * 48,
        30 * 48,
        90 * 48,
        140 * 48,
        365 * 48,
    ]
    assert stack_windows[3]["expected_period_basis"] == (
        "calendar_ytd_from_created_at_utc_with_minimum_days_floor"
    )
    assert all("not_a_market_index" in window["caveat_flags"] for window in stack_windows)
    assert all(window["eligible_for_public_index"] is False for window in stack_windows)


def test_phase5_stack_series_window_eligibility_allows_90d_public_index(
    tmp_path: Path,
) -> None:
    payload = _phase5_payload()
    payload.central_capture.price_period_count = 90 * 48
    payload.central_capture.sample_hours = 90 * 24

    write_phase4_dashboard_cache(payload, tmp_path)

    data_quality = json.loads((tmp_path / "data_quality.json").read_text(encoding="utf-8"))
    stack_series = pd.read_parquet(tmp_path / "stack_series.parquet")
    windows_by_label = {
        window["window_label"]: window for window in data_quality["stack_series_windows"]
    }

    assert windows_by_label["7d"]["eligible_for_public_index"] is False
    assert windows_by_label["30d"]["eligible_for_public_index"] is False
    assert windows_by_label["90d"]["eligible_for_public_index"] is True
    assert "not_a_market_index" in windows_by_label["90d"]["caveat_flags"]
    assert "partial_sample_annualised" not in windows_by_label["90d"]["caveat_flags"]
    assert stack_series["window_label"].tolist() == ["90d", "90d"]
    assert (
        not stack_series["caveat_flags"]
        .map(lambda flags: "partial_sample_annualised" in flags)
        .any()
    )


def test_phase5_stack_series_prefers_trailing_12m_when_ytd_ties(
    tmp_path: Path,
) -> None:
    payload = _phase5_payload()
    payload.created_at_utc = datetime(2024, 12, 31, tzinfo=UTC)
    payload.central_capture.price_period_count = 365 * 48
    payload.central_capture.sample_hours = 365 * 24

    write_phase4_dashboard_cache(payload, tmp_path)

    stack_series = pd.read_parquet(tmp_path / "stack_series.parquet")
    benchmark = json.loads((tmp_path / "benchmark_reconciliation.json").read_text(encoding="utf-8"))

    assert stack_series["window_label"].tolist() == [
        "trailing_12m",
        "trailing_12m",
    ]
    assert (
        not stack_series["caveat_flags"]
        .map(lambda flags: "partial_sample_annualised" in flags)
        .any()
    )
    assert all("partial_sample_annualised" not in row["caveat_labels"] for row in benchmark["rows"])


def test_phase5_cache_writes_stack_series_rows_for_central_aggregate(
    tmp_path: Path,
) -> None:
    write_phase4_dashboard_cache(_phase5_payload(), tmp_path)

    stack_series = pd.read_parquet(tmp_path / "stack_series.parquet")

    assert stack_series["basis"].tolist() == ["perfect_foresight", "rolling_policy"]
    assert stack_series["window_label"].tolist() == ["7d", "7d"]
    assert stack_series["asset_id"].tolist() == [
        "phase5-reference-asset",
        "phase5-reference-asset",
    ]
    assert "openbess_canonical_1mw_2mwh" not in stack_series["asset_id"].tolist()
    assert stack_series["cm_annual_scenario_gbp_per_mw_year"].isna().all()
    assert stack_series["caveat_flags"].map(lambda flags: "not_a_market_index" in flags).all()
    assert (
        stack_series["caveat_flags"].map(lambda flags: "partial_sample_annualised" in flags).all()
    )

    perfect = stack_series.loc[stack_series["basis"] == "perfect_foresight"].iloc[0]
    rolling = stack_series.loc[stack_series["basis"] == "rolling_policy"].iloc[0]
    assert perfect["wholesale_energy_gbp"] == pytest.approx(240)
    assert perfect["eac_availability_gbp"] == pytest.approx(60)
    assert perfect["degradation_cost_gbp"] == pytest.approx(0)
    assert rolling["wholesale_energy_gbp"] == pytest.approx(200)
    assert rolling["eac_availability_gbp"] == pytest.approx(50)
    assert rolling["degradation_cost_gbp"] == pytest.approx(4)
    assert rolling["degradation_adjusted_value_gbp"] == pytest.approx(200 + 50 - 4)


def _phase5_payload() -> Phase4DashboardCacheInput:
    run = RollingMarketStackRun(
        steps=[
            RollingMarketStackStepRecord(
                decision_time_utc=datetime(2024, 1, 1, tzinfo=UTC),
                horizon_period_count=4,
                executed_period_count=4,
                information_source_hash="fixture",
                excluded_future_row_count=0,
                service_cell_count=4,
                excluded_service_cell_count=0,
                forecast_model="oracle_diagnostic",
                forecast_is_oracle=True,
                forecast_mae_gbp_per_mwh=0,
                forecast_rmse_gbp_per_mwh=0,
                soc_start_mwh=1,
                soc_end_mwh=1,
                planned_terminal_soc_mwh=1,
                executed_charge_mw=0.5,
                executed_discharge_mw=0.5,
                executed_reserve_up_mw={"dynamic_containment_low": 0.25},
                executed_reserve_down_mw={},
                realised_energy_revenue_gbp=200,
                realised_service_revenue_gbp=50,
                realised_total_revenue_gbp=250,
                planned_total_revenue_gbp=250,
                solver_termination_condition="optimal",
                solver_wall_time_seconds=0.1,
            )
        ],
        realised_energy_revenue_gbp=200,
        realised_service_revenue_gbp=50,
        realised_total_revenue_gbp=250,
        planned_total_revenue_gbp=250,
        final_soc_mwh=1,
        initial_soc_mwh=1,
        terminal_soc_policy="target",
        terminal_soc_target_mwh=1,
        forecast_model="oracle_diagnostic",
        solver_failure_count=0,
    )
    capture = Phase4MarketStackCaptureResult(
        price_period_count=4,
        sample_hours=2,
        perfect_energy_revenue_gbp=240,
        perfect_service_revenue_gbp=60,
        perfect_total_revenue_gbp=300,
        rolling_energy_revenue_gbp=200,
        rolling_service_revenue_gbp=50,
        rolling_total_revenue_gbp=250,
        rolling_planned_revenue_gbp=250,
        capture_ratio=250 / 300,
        regret_gbp=50,
        solver_failure_count=0,
        forecast_mae_gbp_per_mwh=0,
        forecast_rmse_gbp_per_mwh=0,
    )
    return Phase4DashboardCacheInput(
        run_id="phase5-dashboard-cache-test",
        rolling_run=run,
        central_capture=capture,
        smoke_comparisons=[],
        scenario_results=[
            RollingMarketStackScenarioResult(
                name="base_case",
                stress_label="central",
                period_count=4,
                wholesale_price_scalar=1,
                eac_price_scalar=1,
                realised_energy_revenue_gbp=200,
                realised_service_revenue_gbp=50,
                realised_total_revenue_gbp=250,
                final_soc_mwh=1,
            )
        ],
        caveats=["Synthetic stress profile; not a bankability forecast."],
        config_hash="fixture-config",
        source_snapshot_hash="fixture-source",
        input_run_ids=["phase5-fixture"],
        source_ids=["PROJECT_CONVENTION"],
        source_labels={
            "wholesale": "synthetic Phase 4 stress profile",
            "eac": "synthetic EAC availability proxy",
        },
        battery_energy_capacity_mwh=2,
        battery_power_mw=1,
        stack_series_asset_id="phase5-reference-asset",
        capex_gbp=20_000_000,
        created_at_utc=datetime(2024, 5, 20, tzinfo=UTC),
    )
