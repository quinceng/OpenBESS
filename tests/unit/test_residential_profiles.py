from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from gb_bess_revenue_stack.residential import (
    ResidentialHouseholdInterval,
    ResidentialTariffPeriod,
    ResidentialTariffSchedule,
    validate_household_intervals,
)

pytestmark = pytest.mark.unit


def _interval(
    index: int,
    *,
    load_kwh: float = 1.0,
    pv_kwh: float = 0.5,
) -> ResidentialHouseholdInterval:
    start = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=30 * index)
    return ResidentialHouseholdInterval(
        delivery_start_utc=start,
        delivery_end_utc=start + timedelta(minutes=30),
        load_kwh=load_kwh,
        pv_generation_kwh=pv_kwh,
    )


def test_household_interval_rejects_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="aware"):
        ResidentialHouseholdInterval(
            delivery_start_utc=datetime(2026, 1, 1),
            delivery_end_utc=datetime(2026, 1, 1, 0, 30),
            load_kwh=1,
            pv_generation_kwh=0,
        )


def test_validate_household_intervals_rejects_duplicate_starts() -> None:
    rows = [_interval(0), _interval(0)]

    with pytest.raises(ValueError, match="duplicate"):
        validate_household_intervals(rows)


def test_validate_household_intervals_rejects_gaps() -> None:
    rows = [_interval(0), _interval(2)]

    with pytest.raises(ValueError, match="contiguous"):
        validate_household_intervals(rows)


def test_tariff_schedule_selects_rate_for_each_interval() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    schedule = ResidentialTariffSchedule(
        periods=(
            ResidentialTariffPeriod(
                valid_from_utc=start,
                valid_to_utc=start + timedelta(hours=1),
                import_rate_gbp_per_kwh=0.25,
                export_rate_gbp_per_kwh=0.15,
            ),
        )
    )

    rate = schedule.rate_for(start + timedelta(minutes=30))

    assert rate.import_rate_gbp_per_kwh == pytest.approx(0.25)
    assert rate.export_rate_gbp_per_kwh == pytest.approx(0.15)
