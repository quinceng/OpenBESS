from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gb_bess_revenue_stack.cli import app

pytestmark = pytest.mark.unit


def test_residential_household_smoke_writes_summary_and_dispatch(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run-residential-household-smoke",
            "--profile-csv",
            "tests/fixtures/residential_household_profile.csv",
            "--tariff-csv",
            "tests/fixtures/residential_tariff.csv",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["branch_name"] == "residential"
    assert summary["total_bill_savings_gbp"] >= 0
    assert (tmp_path / "dispatch.csv").exists()
