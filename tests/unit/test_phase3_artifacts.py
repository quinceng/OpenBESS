from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_phase3_report_and_review_exist() -> None:
    assert (ROOT / "reports/phase_3_eac_availability/phase_3_eac_availability_report.md").exists()
    assert (ROOT / "docs/phase_reviews/phase_3_review.md").exists()


def test_phase3_smoke_outputs_exist() -> None:
    output_dir = ROOT / "reports/phase_3_eac_availability/smoke_outputs"

    assert (output_dir / "market_stack_result.json").exists()
    assert (output_dir / "eac_price_matrix.json").exists()
    assert (output_dir / "cm_annual_summary.json").exists()
