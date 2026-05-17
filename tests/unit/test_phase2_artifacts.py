from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_phase2_report_and_review_exist() -> None:
    assert (ROOT / "reports/phase_2_baseline/phase_2_baseline_method.md").exists()
    assert (ROOT / "docs/phase_reviews/phase_2_review.md").exists()


def test_phase2_regression_fixture_exists() -> None:
    assert (ROOT / "tests/fixtures/phase2_toy_prices.csv").exists()


def test_phase2_5_report_and_review_exist() -> None:
    assert (ROOT / "reports/phase_2_5_rolling_slice/phase_2_5_policy_report.md").exists()
    assert (ROOT / "docs/phase_reviews/phase_2_5_review.md").exists()
