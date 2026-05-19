from __future__ import annotations

from pathlib import Path

import pytest

from gb_bess_revenue_stack.residential.io import load_household_profile_csv, load_tariff_csv

pytestmark = pytest.mark.unit


def test_load_household_profile_csv_reads_load_and_pv_fixture() -> None:
    rows = load_household_profile_csv(Path("tests/fixtures/residential_household_profile.csv"))

    assert len(rows) == 4
    assert rows[0].load_kwh == pytest.approx(0.6)
    assert rows[0].pv_generation_kwh == pytest.approx(0)


def test_load_tariff_csv_reads_import_and_export_rates() -> None:
    tariff = load_tariff_csv(Path("tests/fixtures/residential_tariff.csv"))

    rate = tariff.periods[0]

    assert rate.import_rate_gbp_per_kwh == pytest.approx(0.10)
    assert rate.export_rate_gbp_per_kwh == pytest.approx(0.15)
