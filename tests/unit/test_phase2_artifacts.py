from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_phase2_regression_fixture_exists() -> None:
    assert (ROOT / "tests/fixtures/phase2_toy_prices.csv").exists()
