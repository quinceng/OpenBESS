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
    write_phase4_dashboard_cache(_phase5_payload(), tmp_path)

    assert (tmp_path / "degradation_summary.json").exists()
    assert (tmp_path / "finance_summary.json").exists()
    assert (tmp_path / "finance_cashflows.parquet").exists()
    assert (tmp_path / "benchmark_reconciliation.json").exists()
    assert (tmp_path / "eac_commitments.parquet").exists()
    assert (tmp_path / "data_quality.json").exists()

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"]["degradation_summary"] == "degradation_summary.json"
    assert manifest["files"]["finance_cashflows"] == "finance_cashflows.parquet"
    assert manifest["files"]["benchmark_reconciliation"] == "benchmark_reconciliation.json"
    assert manifest["files"]["eac_commitments"] == "eac_commitments.parquet"
    assert manifest["files"]["data_quality"] == "data_quality.json"


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
    assert finance["npv_gbp"] < 0
    assert set(cashflows["year"]) == set(range(16))
    assert degradation["throughput_mwh"] > 0
    assert degradation["equivalent_full_cycles"] > 0
    assert benchmark["reconciliation_scope"] == "benchmark reconciliation, not replication"
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
    payload.central_capture.sample_hours = 8760

    write_phase4_dashboard_cache(payload, tmp_path)

    finance = json.loads((tmp_path / "finance_summary.json").read_text(encoding="utf-8"))
    cashflows = pd.read_parquet(tmp_path / "finance_cashflows.parquet")
    expected_npv = -1000 + 600 / 1.1 + 600 / (1.1**2) + 600 / (1.1**3)

    assert finance["npv_gbp"] == pytest.approx(expected_npv)
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

    assert set(commitments["service_model_label"]) == {"dynamic_containment_low"}
    assert set(commitments["direction"]) == {"up"}
    assert commitments["committed_mw"].sum() == pytest.approx(0.25)
    assert data_quality["known_at_policy"] == "synthetic_day_ahead_known_time"
    assert data_quality["solver_failure_count"] == 0
    assert data_quality["excluded_future_row_count"] == 0
    assert data_quality["source_ids"] == ["PROJECT_CONVENTION"]


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
        capex_gbp=20_000_000,
        created_at_utc=datetime(2024, 1, 2, tzinfo=UTC),
    )
