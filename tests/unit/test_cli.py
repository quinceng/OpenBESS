from __future__ import annotations

import pytest
from typer.testing import CliRunner

from gb_bess_revenue_stack.cli import app

pytestmark = pytest.mark.unit


def test_cli_exposes_fetch_data_subcommand() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["fetch-data", "--help"])

    assert result.exit_code == 0
    assert "--source" in result.output


def test_cli_exposes_run_smoke_subcommand() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["run-smoke", "--help"])

    assert result.exit_code == 0
    assert "--output-dir" in result.output


def test_cli_exposes_run_rolling_smoke_subcommand() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["run-rolling-smoke", "--help"])

    assert result.exit_code == 0
    assert "--output-dir" in result.output


def test_cli_exposes_run_market_stack_smoke_subcommand() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["run-market-stack-smoke", "--help"])

    assert result.exit_code == 0
    assert "--output-dir" in result.output


def test_cli_exposes_run_phase4_smoke_subcommand() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["run-phase4-smoke", "--help"])

    assert result.exit_code == 0
    assert "--output-dir" in result.output
    assert "--dashboard-dir" in result.output
    assert "--day-count" in result.output


def test_cli_exposes_run_residential_household_smoke_subcommand() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["run-residential-household-smoke", "--help"])

    assert result.exit_code == 0
    assert "--profile-csv" in result.output
    assert "--tariff-csv" in result.output
    assert "--output-dir" in result.output


def test_cli_exposes_run_residential_scenario_sweep_subcommand() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["run-residential-scenario-sweep", "--help"])

    assert result.exit_code == 0
    assert "--output-dir" in result.output
