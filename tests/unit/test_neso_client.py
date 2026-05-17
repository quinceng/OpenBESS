from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gb_bess_revenue_stack.data.neso import parse_eac_summary_records

pytestmark = pytest.mark.unit


def test_parse_eac_summary_records_converts_to_canonical_schema() -> None:
    records = [
        {
            "auctionID": 2661,
            "auctionProduct": "DCL",
            "serviceType": "Response",
            "deliveryStart": "2026-04-01T02:00:00",
            "deliveryEnd": "2026-04-01T06:00:00",
            "clearedVolume": 499,
            "clearingPrice": 7.68,
            "linkedServiceWindowID": None,
        }
    ]

    parsed = parse_eac_summary_records(
        records,
        source_url="https://api.neso.energy",
        retrieved_at_utc=datetime(2026, 4, 1, 12, tzinfo=UTC),
    )

    assert parsed.accepted[0].product_model_label == "dynamic_containment_low"
    assert parsed.accepted[0].direction_model_label == "upward"
    assert parsed.accepted[0].clearing_price_gbp_per_mw_h == 7.68
    assert parsed.accepted[0].procured_mw == 499
    assert parsed.quarantined == []


def test_parse_eac_summary_records_quarantines_unknown_product() -> None:
    records = [
        {
            "auctionID": 1,
            "auctionProduct": "NEW",
            "serviceType": "Mystery",
            "deliveryStart": "2026-04-01T02:00:00",
            "deliveryEnd": "2026-04-01T06:00:00",
            "clearedVolume": 10,
            "clearingPrice": 1,
        }
    ]

    parsed = parse_eac_summary_records(
        records,
        source_url="https://api.neso.energy",
        retrieved_at_utc=datetime(2026, 4, 1, 12, tzinfo=UTC),
    )

    assert parsed.accepted == []
    assert parsed.quarantined[0].reason == "unknown_product_label"
