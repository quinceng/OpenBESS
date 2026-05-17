from __future__ import annotations

from datetime import date

import pytest

from gb_bess_revenue_stack.schemas.time import settlement_periods_for_gb_date

pytestmark = pytest.mark.unit


def test_spring_dst_day_has_46_settlement_periods() -> None:
    periods = settlement_periods_for_gb_date(date(2024, 3, 31))

    assert len(periods) == 46
    assert periods[0].settlement_period == 1
    assert periods[-1].settlement_period == 46
    assert all(period.duration_h == 0.5 for period in periods)


def test_autumn_dst_day_has_50_settlement_periods() -> None:
    periods = settlement_periods_for_gb_date(date(2024, 10, 27))

    assert len(periods) == 50
    assert periods[0].settlement_period == 1
    assert periods[-1].settlement_period == 50
    assert periods[1].delivery_start_utc < periods[2].delivery_start_utc
