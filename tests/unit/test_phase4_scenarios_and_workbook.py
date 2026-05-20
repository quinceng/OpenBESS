from __future__ import annotations

import json
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pytest
from typer.testing import CliRunner

from gb_bess_revenue_stack.cli import app
from gb_bess_revenue_stack.commercial import CommercialBessSystem
from gb_bess_revenue_stack.config.models import AssetConfig
from gb_bess_revenue_stack.markets.eac_prices import synthetic_service_matrix
from gb_bess_revenue_stack.phase4.scenarios import (
    build_realistic_stress_price_profile,
    default_phase4_market_stack_scenarios,
    load_phase4_historical_sample,
    run_phase4_market_stack_capture_comparison,
    run_phase4_market_stack_sweep,
    run_phase4_smoke_window_comparisons,
    skipped_phase4_smoke_windows,
)
from gb_bess_revenue_stack.policies.forecasts import OracleForecast
from gb_bess_revenue_stack.policies.rolling import RollingConfig
from gb_bess_revenue_stack.policies.rolling_market_stack import (
    RollingMarketStackRun,
    RollingMarketStackScenarioResult,
    RollingMarketStackStepRecord,
    run_rolling_market_stack_policy,
)
from gb_bess_revenue_stack.reporting.dashboard_cache import (
    Phase4DashboardCacheInput,
    write_phase4_dashboard_cache,
)
from gb_bess_revenue_stack.reporting.investor_workbook import (
    InvestorWorkbookInput,
    write_investor_workbook,
)

pytestmark = pytest.mark.unit


def test_realistic_stress_price_profile_covers_multiple_full_days() -> None:
    rows = build_realistic_stress_price_profile(
        start_utc=datetime(2024, 1, 1, tzinfo=UTC),
        day_count=14,
    )

    assert len(rows) == 14 * 48
    assert rows[0].settlement_period == 1
    assert rows[47].settlement_period == 48
    assert rows[48].settlement_period == 1
    assert max(row.price_gbp_per_mwh for row in rows) > 240
    assert min(row.price_gbp_per_mwh for row in rows) < 0
    assert all(row.delivery_start_utc.tzinfo is not None for row in rows)


def test_default_phase4_scenarios_include_wholesale_and_eac_stresses() -> None:
    scenarios = default_phase4_market_stack_scenarios()
    names = {scenario.name for scenario in scenarios}

    assert len(scenarios) >= 6
    assert "base_case" in names
    assert "winter_peak_spread" in names
    assert "low_spread_eac_downside" in names
    assert all(scenario.stress_label for scenario in scenarios)
    assert "synthetic" not in " ".join(scenario.notes.lower() for scenario in scenarios)


def test_phase4_historical_sample_aligns_elexon_mid_and_neso_eac() -> None:
    sample = load_phase4_historical_sample()

    assert sample.label == "elexon_mid_neso_eac_2026_04_01_0000_0230_utc"
    assert len(sample.prices) == 5
    assert sample.sample_hours == pytest.approx(2.5)
    assert {price.source_id for price in sample.prices} == {"ELEXON_BMRS_MID"}
    assert {price.price_source_type for price in sample.prices} == {"MID"}
    assert sample.eac_price_matrix.product_model_labels == [
        "dynamic_regulation_high",
        "negative_quick_reserve",
    ]
    assert sample.source_ids == ["ELEXON_BMRS_MID", "NESO_EAC_AUCTION_RESULTS"]
    assert sample.source_labels["wholesale"].startswith("Elexon BMRS MID")
    assert sample.source_labels["eac"].startswith("NESO EAC auction")
    assert all(
        sample.eac_price_matrix.available_cells_for_period(period_index)
        for period_index in range(len(sample.prices))
    )

    nqr = sample.eac_price_matrix.cell(
        product_model_label="negative_quick_reserve",
        period_index=0,
    )

    assert nqr.product_source_label == "NQR"
    assert nqr.price_gbp_per_mw_h == pytest.approx(1.53)
    assert nqr.source_id == "NESO_EAC_AUCTION_RESULTS"


def test_phase4_historical_sample_defaults_are_packaged_resources() -> None:
    fixture_root = files("gb_bess_revenue_stack.phase4.fixtures")

    assert fixture_root.joinpath("phase4_elexon_mid_aligned_sample.json").is_file()
    assert fixture_root.joinpath("phase4_neso_eac_aligned_sample.json").is_file()

    sample = load_phase4_historical_sample()

    assert sample.source_snapshot_hash == (
        "93a2e8fdf909bed24b4557973d1c49679079b08277723b252861791f45972c0d"
    )
    assert sample.prices[0].source_url.endswith("from=2026-04-01T00:00:00Z&to=2026-04-01T02:30:00Z")


def test_phase4_historical_sample_override_derives_label_from_fixture_window(
    tmp_path: Path,
) -> None:
    fixture_root = files("gb_bess_revenue_stack.phase4.fixtures")
    elexon_payload = json.loads(
        fixture_root.joinpath("phase4_elexon_mid_aligned_sample.json").read_text(encoding="utf-8")
    )
    neso_payload = json.loads(
        fixture_root.joinpath("phase4_neso_eac_aligned_sample.json").read_text(encoding="utf-8")
    )
    for row in elexon_payload["data"]:
        row["startTime"] = row["startTime"].replace("2026-04-01", "2026-04-02")
        row["settlementDate"] = "2026-04-02"
    for record in neso_payload["records"]:
        record["deliveryStart"] = record["deliveryStart"].replace("2026-04-01", "2026-04-02")
        record["deliveryStart"] = record["deliveryStart"].replace("2026-03-31", "2026-04-01")
        record["deliveryEnd"] = record["deliveryEnd"].replace("2026-04-01", "2026-04-02")

    elexon_path = tmp_path / "shifted_elexon.json"
    neso_path = tmp_path / "shifted_neso.json"
    elexon_path.write_text(
        json.dumps(elexon_payload),
        encoding="utf-8",
    )
    neso_path.write_text(json.dumps(neso_payload), encoding="utf-8")

    sample = load_phase4_historical_sample(
        elexon_mid_path=elexon_path,
        neso_eac_path=neso_path,
    )

    assert sample.label == "elexon_mid_neso_eac_2026_04_02_0000_0230_utc"
    assert sample.prices[0].source_url.endswith("from=2026-04-02T00:00:00Z&to=2026-04-02T02:30:00Z")
    assert "Fixture override paths were supplied" in sample.caveats[-1]


def test_phase4_historical_sample_rejects_duplicate_settlement_periods(
    tmp_path: Path,
) -> None:
    fixture_root = files("gb_bess_revenue_stack.phase4.fixtures")
    elexon_payload = json.loads(
        fixture_root.joinpath("phase4_elexon_mid_aligned_sample.json").read_text(encoding="utf-8")
    )
    elexon_payload["data"][1]["settlementPeriod"] = elexon_payload["data"][0]["settlementPeriod"]
    elexon_path = tmp_path / "duplicate_elexon.json"
    elexon_path.write_text(json.dumps(elexon_payload), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate settlement periods"):
        load_phase4_historical_sample(elexon_mid_path=elexon_path)


def test_market_stack_capture_comparison_reports_perfect_foresight_ceiling() -> None:
    prices = build_realistic_stress_price_profile(
        start_utc=datetime(2024, 1, 1, tzinfo=UTC),
        day_count=1,
    )[:4]
    asset = _phase4_test_asset()
    matrix = synthetic_service_matrix(
        product_model_label="dynamic_containment_low",
        direction_model_label="upward",
        prices_gbp_per_mw_h=[12] * len(prices),
        duration_h=0.5,
    )
    config = RollingConfig(
        horizon_periods=len(prices),
        step_periods=len(prices),
        terminal_soc_policy="target",
        terminal_soc_target_mwh=1,
    )
    rolling = run_rolling_market_stack_policy(
        prices=prices,
        eac_price_matrix=matrix,
        asset=asset,
        initial_soc_mwh=1,
        forecast_model=OracleForecast(),
        config=config,
    )

    comparison = run_phase4_market_stack_capture_comparison(
        prices=prices,
        eac_price_matrix=matrix,
        asset=asset,
        initial_soc_mwh=1,
        rolling_run=rolling,
        terminal_soc_policy="target",
        terminal_soc_target_mwh=1,
    )

    assert comparison.price_period_count == 4
    assert comparison.sample_hours == pytest.approx(2)
    assert comparison.perfect_total_revenue_gbp > 0
    assert comparison.rolling_total_revenue_gbp == pytest.approx(
        comparison.perfect_total_revenue_gbp
    )
    assert comparison.capture_ratio == pytest.approx(1)
    assert comparison.regret_gbp == pytest.approx(0)


def test_phase4_smoke_window_comparisons_include_24h_and_48h_windows() -> None:
    prices = build_realistic_stress_price_profile(
        start_utc=datetime(2024, 1, 1, tzinfo=UTC),
        day_count=2,
    )
    matrix = synthetic_service_matrix(
        product_model_label="dynamic_containment_low",
        direction_model_label="upward",
        prices_gbp_per_mw_h=[8] * len(prices),
        duration_h=0.5,
    )

    comparisons = run_phase4_smoke_window_comparisons(
        prices=prices,
        eac_price_matrix=matrix,
        asset=_phase4_test_asset(),
        initial_soc_mwh=1,
        forecast_model=OracleForecast(),
        config=RollingConfig(
            horizon_periods=48,
            step_periods=48,
            terminal_soc_policy="target",
            terminal_soc_target_mwh=1,
        ),
        window_day_counts=[1, 2],
    )

    by_label = {comparison.label: comparison for comparison in comparisons}

    assert set(by_label) == {"24h", "48h"}
    assert by_label["24h"].capture.price_period_count == 48
    assert by_label["24h"].capture.sample_hours == pytest.approx(24)
    assert by_label["48h"].capture.price_period_count == 96
    assert by_label["48h"].capture.sample_hours == pytest.approx(48)
    assert by_label["48h"].capture.capture_ratio is not None


def test_phase4_smoke_window_skips_short_historical_samples() -> None:
    sample = load_phase4_historical_sample()

    skipped = skipped_phase4_smoke_windows(prices=sample.prices, window_day_counts=[1, 2])

    assert [item.label for item in skipped] == ["24h", "48h"]
    assert {item.reason for item in skipped} == {"insufficient_periods"}
    assert all(item.available_period_count == len(sample.prices) for item in skipped)


def test_phase4_market_stack_sweep_respects_explicit_empty_scenarios() -> None:
    sample = load_phase4_historical_sample()

    sweep = run_phase4_market_stack_sweep(
        prices=sample.prices,
        eac_price_matrix=sample.eac_price_matrix,
        asset=_phase4_test_asset(),
        initial_soc_mwh=1,
        forecast_model=OracleForecast(),
        config=RollingConfig(
            horizon_periods=2,
            step_periods=1,
            terminal_soc_policy="target",
            terminal_soc_target_mwh=1,
        ),
        scenarios=[],
    )

    assert sweep.price_period_count == len(sample.prices)
    assert sweep.scenario_results == []


def test_phase4_smoke_command_writes_historical_source_labels(tmp_path: Path) -> None:
    output_dir = tmp_path / "phase4"
    dashboard_dir = tmp_path / "dashboard"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "run-phase4-smoke",
            "--output-dir",
            str(output_dir),
            "--dashboard-dir",
            str(dashboard_dir),
        ],
    )

    assert result.exit_code == 0, result.output

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((dashboard_dir / "manifest.json").read_text(encoding="utf-8"))
    caveats = json.loads((dashboard_dir / "caveats.json").read_text(encoding="utf-8"))
    smoke_windows = json.loads(
        (output_dir / "smoke_window_comparisons.json").read_text(encoding="utf-8")
    )
    stack_series = pd.read_parquet(dashboard_dir / "stack_series.parquet")
    rolling = json.loads((output_dir / "rolling_market_stack_run.json").read_text(encoding="utf-8"))
    scenario_sweep = json.loads(
        (output_dir / "phase4_scenario_sweep.json").read_text(encoding="utf-8")
    )
    base_case = next(
        result for result in scenario_sweep["scenario_results"] if result["name"] == "base_case"
    )

    assert summary["historical_sample_label"] == ("elexon_mid_neso_eac_2026_04_01_0000_0230_utc")
    assert summary["period_count"] == 5
    assert manifest["source_labels"]["wholesale"].startswith("Elexon BMRS MID")
    assert manifest["source_labels"]["eac"].startswith("NESO EAC auction")
    assert manifest["known_at_policy"] == "historical_fixture_source_known_at_policy"
    assert "PROJECT_CONVENTION" not in manifest["source_ids"]
    assert len(rolling["steps"]) == summary["period_count"]
    assert any(step["excluded_service_cell_count"] > 0 for step in rolling["steps"])
    assert summary["rolling_total_revenue_gbp"] > 0
    assert base_case["realised_total_revenue_gbp"] == pytest.approx(
        summary["rolling_total_revenue_gbp"]
    )
    assert base_case["realised_total_revenue_gbp"] < summary["perfect_total_revenue_gbp"]
    assert summary["rolling_policy_horizon_periods"] == 4
    assert summary["rolling_policy_step_periods"] == 1
    assert smoke_windows["comparisons"] == []
    assert [item["label"] for item in smoke_windows["skipped_windows"]] == ["24h", "48h"]
    assert stack_series["asset_id"].tolist() == [
        "phase4-commercial-reference",
        "phase4-commercial-reference",
    ]
    assert "openbess_canonical_1mw_2mwh" not in stack_series["asset_id"].tolist()
    assert any("24h smoke comparison skipped" in caveat for caveat in caveats["caveats"])
    assert any(
        "not 24h wholesale forecast-policy performance" in caveat for caveat in caveats["caveats"]
    )


def test_phase4_dashboard_cache_writer_outputs_contract_files(tmp_path: Path) -> None:
    prices = build_realistic_stress_price_profile(
        start_utc=datetime(2024, 1, 1, tzinfo=UTC),
        day_count=1,
    )[:4]
    asset = _phase4_test_asset()
    matrix = synthetic_service_matrix(
        product_model_label="dynamic_containment_low",
        direction_model_label="upward",
        prices_gbp_per_mw_h=[10] * len(prices),
        duration_h=0.5,
    )
    rolling = run_rolling_market_stack_policy(
        prices=prices,
        eac_price_matrix=matrix,
        asset=asset,
        initial_soc_mwh=1,
        forecast_model=OracleForecast(),
        config=RollingConfig(
            horizon_periods=len(prices),
            step_periods=len(prices),
            terminal_soc_policy="target",
            terminal_soc_target_mwh=1,
        ),
    )
    capture = run_phase4_market_stack_capture_comparison(
        prices=prices,
        eac_price_matrix=matrix,
        asset=asset,
        initial_soc_mwh=1,
        rolling_run=rolling,
        terminal_soc_policy="target",
        terminal_soc_target_mwh=1,
    )
    scenario_result = RollingMarketStackScenarioResult(
        name="base_case",
        wholesale_price_scalar=1,
        eac_price_scalar=1,
        stress_label="central",
        period_count=len(prices),
        realised_energy_revenue_gbp=rolling.realised_energy_revenue_gbp,
        realised_service_revenue_gbp=rolling.realised_service_revenue_gbp,
        realised_total_revenue_gbp=rolling.realised_total_revenue_gbp,
        final_soc_mwh=rolling.final_soc_mwh,
    )

    write_phase4_dashboard_cache(
        Phase4DashboardCacheInput(
            run_id="phase4-dashboard-cache-test",
            rolling_run=rolling,
            central_capture=capture,
            smoke_comparisons=[],
            scenario_results=[scenario_result],
            caveats=["Synthetic stress profile; not a bankability forecast."],
            config_hash="fixture-config",
            source_snapshot_hash="fixture-source",
            input_run_ids=["phase4-smoke-fixture"],
            source_ids=["PROJECT_CONVENTION"],
            source_labels={
                "wholesale": "synthetic Phase 4 stress profile",
                "eac": "synthetic EAC availability proxy",
            },
            stack_series_asset_id="phase4-dashboard-cache-asset",
            created_at_utc=datetime(2024, 1, 2, tzinfo=UTC),
        ),
        tmp_path,
    )

    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "executive_summary.json").exists()
    assert (tmp_path / "policy_capture.parquet").exists()
    assert (tmp_path / "revenue_stack.parquet").exists()
    assert (tmp_path / "scenario_sweeps.parquet").exists()
    assert (tmp_path / "caveats.json").exists()

    policy_capture = pd.read_parquet(tmp_path / "policy_capture.parquet")
    revenue_stack = pd.read_parquet(tmp_path / "revenue_stack.parquet")
    scenario_sweeps = pd.read_parquet(tmp_path / "scenario_sweeps.parquet")

    assert set(policy_capture["label"]) == {"central"}
    assert policy_capture.loc[0, "capture_ratio"] == pytest.approx(1)
    assert {"perfect_foresight", "rolling_policy"} <= set(revenue_stack["basis"])
    assert list(scenario_sweeps["scenario"]) == ["base_case"]


def test_investor_workbook_contains_required_tabs_and_readable_timestamps(
    tmp_path: Path,
) -> None:
    workbook_path = tmp_path / "investor_workbook.xlsx"
    commercial = CommercialBessSystem(
        name="Investor Site",
        battery_capacity_mwh=10,
        inverter_power_mw=5,
        site_export_limit_mw=3,
        battery_capex_gbp_per_mwh=210_000,
        inverter_capex_gbp_per_mw=90_000,
        installation_cost_gbp=125_000,
        grid_connection_cost_gbp=75_000,
    )
    run = RollingMarketStackRun(
        steps=[
            RollingMarketStackStepRecord(
                decision_time_utc=datetime(2024, 1, 1, tzinfo=UTC),
                horizon_period_count=48,
                executed_period_count=24,
                information_source_hash="fixture",
                excluded_future_row_count=0,
                service_cell_count=48,
                excluded_service_cell_count=0,
                forecast_model="previous_day_same_period",
                forecast_is_oracle=False,
                forecast_mae_gbp_per_mwh=12.5,
                forecast_rmse_gbp_per_mwh=16,
                soc_start_mwh=5,
                soc_end_mwh=5.5,
                planned_terminal_soc_mwh=5,
                executed_charge_mw=1.2,
                executed_discharge_mw=1.4,
                executed_reserve_up_mw={"dynamic_containment_low": 0.8},
                executed_reserve_down_mw={},
                realised_energy_revenue_gbp=1_000,
                realised_service_revenue_gbp=250,
                realised_total_revenue_gbp=1_250,
                planned_total_revenue_gbp=1_300,
                solver_termination_condition="optimal",
                solver_wall_time_seconds=0.2,
            )
        ],
        realised_energy_revenue_gbp=1_000,
        realised_service_revenue_gbp=250,
        realised_total_revenue_gbp=1_250,
        planned_total_revenue_gbp=1_300,
        final_soc_mwh=5.5,
        initial_soc_mwh=5,
        terminal_soc_policy="target",
        terminal_soc_target_mwh=5,
        forecast_model="previous_day_same_period",
        solver_failure_count=0,
    )
    payload = InvestorWorkbookInput(
        commercial_system=commercial,
        rolling_run=run,
        scenario_results=[
            RollingMarketStackScenarioResult(
                name="base_case",
                wholesale_price_scalar=1,
                eac_price_scalar=1,
                stress_label="central",
                period_count=672,
                realised_energy_revenue_gbp=1_000,
                realised_service_revenue_gbp=250,
                realised_total_revenue_gbp=1_250,
                final_soc_mwh=5.5,
            )
        ],
        caveats=["Synthetic stress profile; not a bankability forecast."],
    )

    write_investor_workbook(payload, workbook_path)

    with ZipFile(workbook_path) as archive:
        workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
        shared_summary = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
        dispatch_xml = archive.read("xl/worksheets/sheet4.xml").decode("utf-8")

    assert "Summary" in workbook_xml
    assert "Assumptions" in workbook_xml
    assert "Solver Output" in workbook_xml
    assert "Dispatch" in workbook_xml
    assert "Revenue Stack" in workbook_xml
    assert "Caveats" in workbook_xml
    assert "Battery size" in shared_summary
    assert "10.00 MWh" in shared_summary
    assert "Power rating" in shared_summary
    assert "5.00 MW" in shared_summary
    assert "Export limit" in shared_summary
    assert "3.00 MW" in shared_summary
    assert "Capex" in shared_summary
    assert "2024-01-01 00:00 UTC" in dispatch_xml
    assert "2024-01-01T00:00:00+00:00" not in dispatch_xml


def _phase4_test_asset() -> AssetConfig:
    return AssetConfig(
        name="phase4-test-asset",
        power_mw=1,
        energy_capacity_mwh=2,
        eta_charge=1,
        eta_discharge=1,
    )
