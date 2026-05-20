from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from click import unstyle
from typer.testing import CliRunner

from gb_bess_revenue_stack.cli import app

pytestmark = pytest.mark.unit


def command_help(*args: str) -> str:
    result = CliRunner().invoke(
        app,
        [*args, "--help"],
        env={"COLUMNS": "200", "NO_COLOR": "1", "TERM": "dumb"},
    )

    assert result.exit_code == 0
    return unstyle(result.output)


def test_cli_exposes_fetch_data_subcommand() -> None:
    output = command_help("fetch-data")

    assert "--source" in output


def test_cli_exposes_run_smoke_subcommand() -> None:
    output = command_help("run-smoke")

    assert "--output-dir" in output


def test_cli_exposes_run_rolling_smoke_subcommand() -> None:
    output = command_help("run-rolling-smoke")

    assert "--output-dir" in output


def test_cli_exposes_run_market_stack_smoke_subcommand() -> None:
    output = command_help("run-market-stack-smoke")

    assert "--output-dir" in output


def test_cli_exposes_run_phase4_smoke_subcommand() -> None:
    output = command_help("run-phase4-smoke")

    assert "--output-dir" in output
    assert "--dashboard-dir" in output
    assert "--elexon-mid-fixture" in output
    assert "--neso-eac-fixture" in output
    assert "--finance-assumptions-yaml" in output


def test_cli_exposes_run_residential_household_smoke_subcommand() -> None:
    output = command_help("run-residential-household-smoke")

    assert "--profile-csv" in output
    assert "--tariff-csv" in output
    assert "--output-dir" in output


def test_cli_exposes_run_residential_scenario_sweep_subcommand() -> None:
    output = command_help("run-residential-scenario-sweep")

    assert "--output-dir" in output


def test_cli_exposes_build_stack_series_subcommand() -> None:
    output = command_help("build-stack-series")

    assert "OpenBESS Stack Index" in output
    assert "--cache-dir" in output
    assert "--output-dir" in output


def test_build_stack_series_reports_invalid_cache_row(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    output_dir = tmp_path / "exports"
    cache_dir.mkdir()
    pd.DataFrame(
        [
            {
                "timestamp_utc": "2024-01-01T00:00:00+00:00",
                "window_label": "7d",
                "asset_id": "openbess_canonical_1mw_2mwh",
                "basis": "bad_basis",
                "wholesale_energy_gbp": 1200.0,
                "eac_availability_gbp": 450.0,
                "degradation_cost_gbp": 10.0,
                "cm_annual_scenario_gbp_per_mw_year": None,
                "caveat_flags": ["not_a_market_index"],
            }
        ]
    ).to_parquet(cache_dir / "stack_series.parquet", index=False)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "build-stack-series",
            "--cache-dir",
            str(cache_dir),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code != 0
    assert "Invalid stack_series row 0" in result.output


def test_build_stack_series_rejects_unknown_window_label(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    output_dir = tmp_path / "exports"
    cache_dir.mkdir()
    pd.DataFrame(
        [
            {
                "timestamp_utc": "2024-01-01T00:00:00+00:00",
                "window_label": "central",
                "asset_id": "phase4-commercial-reference",
                "basis": "rolling_policy",
                "wholesale_energy_gbp": 1200.0,
                "eac_availability_gbp": 450.0,
                "degradation_cost_gbp": 10.0,
                "cm_annual_scenario_gbp_per_mw_year": None,
                "caveat_flags": ["not_a_market_index"],
            }
        ]
    ).to_parquet(cache_dir / "stack_series.parquet", index=False)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "build-stack-series",
            "--cache-dir",
            str(cache_dir),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code != 0
    assert "Invalid stack_series row 0" in result.output
