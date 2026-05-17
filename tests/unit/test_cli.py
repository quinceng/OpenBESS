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
