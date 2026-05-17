from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from gb_bess_revenue_stack.policies.forecasts import TrailingMeanBySettlementPeriodForecast
from gb_bess_revenue_stack.policies.information_set import build_information_set
from gb_bess_revenue_stack.schemas.market import WholesalePricePoint

pytestmark = pytest.mark.unit


def _point(
    period: int,
    price: float,
    *,
    day: int = 1,
    known_offset_hours: float = 0,
) -> WholesalePricePoint:
    start = datetime(2024, 1, day, tzinfo=UTC) + timedelta(hours=(period - 1) * 0.5)
    end = start + timedelta(minutes=30)
    return WholesalePricePoint(
        delivery_start_utc=start,
        delivery_end_utc=end,
        settlement_date=start.date().isoformat(),
        settlement_period=period,
        duration_h=0.5,
        price_gbp_per_mwh=price,
        price_source_type="MID",
        is_proxy=True,
        known_at_utc=end + timedelta(hours=known_offset_hours),
        retrieved_at_utc=datetime(2024, 1, 10, tzinfo=UTC),
        source_id="ELEXON_BMRS_MID",
        source_url="https://data.elexon.co.uk",
        schema_version="0.1.0",
        quality_flag="ok",
    )


def test_information_set_excludes_rows_not_known_at_decision_time() -> None:
    decision_time = datetime(2024, 1, 2, tzinfo=UTC)
    known = _point(1, 20, day=1)
    future_marker = _point(1, 999, day=2, known_offset_hours=48)

    info = build_information_set(
        decision_time_utc=decision_time,
        all_prices=[known, future_marker],
        current_soc_mwh=1,
    )

    assert [point.price_gbp_per_mwh for point in info.known_prices] == [20]
    assert info.excluded_future_row_count == 1


def test_forecast_uses_only_rows_inside_information_set() -> None:
    decision_time = datetime(2024, 1, 2, tzinfo=UTC)
    target = _point(1, 999, day=2, known_offset_hours=48)
    info = build_information_set(
        decision_time_utc=decision_time,
        all_prices=[_point(1, 20, day=1), target],
        current_soc_mwh=1,
    )
    model = TrailingMeanBySettlementPeriodForecast(lookback_days=7)

    forecast = model.predict(info, target_periods=[target])

    assert forecast.points[0].forecast_value_gbp_per_mwh == 20
    assert forecast.points[0].training_row_count == 1
    assert "999" not in forecast.source_data_hash
