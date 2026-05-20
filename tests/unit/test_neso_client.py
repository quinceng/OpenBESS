from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from gb_bess_revenue_stack.data.neso import NESOEACClient, parse_eac_summary_records

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


def test_client_fetches_summary_records_for_overlapping_delivery_window() -> None:
    seen_sql: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_sql.append(str(request.url.params["sql"]))
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "records": [
                        {
                            "auctionID": 2661,
                            "auctionProduct": "DCL",
                            "serviceType": "Response",
                            "deliveryStart": "2026-04-01T02:00:00",
                            "deliveryEnd": "2026-04-01T06:00:00",
                            "clearedVolume": "499",
                            "clearingPrice": "7.68",
                        }
                    ]
                },
            },
            request=request,
        )

    client = NESOEACClient(http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    records = client.fetch_summary_records_for_window(
        start=datetime(2026, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 8, tzinfo=UTC),
        page_size=5000,
    )

    assert records[0]["auctionProduct"] == "DCL"
    assert "\"deliveryEnd\" > '2026-04-01T00:00:00'" in seen_sql[0]
    assert "\"deliveryStart\" < '2026-04-08T00:00:00'" in seen_sql[0]
    assert "LIMIT 5000 OFFSET 0" in seen_sql[0]


def test_client_paginates_window_records_until_short_page() -> None:
    offsets: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sql = str(request.url.params["sql"])
        offsets.append(sql.rsplit("OFFSET ", maxsplit=1)[1])
        rows = [{"auctionID": offset, "auctionProduct": "DCL"} for offset in range(2)]
        if len(offsets) == 2:
            rows = [{"auctionID": 99, "auctionProduct": "DCL"}]
        return httpx.Response(200, json={"result": {"records": rows}}, request=request)

    client = NESOEACClient(http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    records = client.fetch_summary_records_for_window(
        start=datetime(2026, 4, 1, tzinfo=UTC),
        end=datetime(2026, 4, 2, tzinfo=UTC),
        page_size=2,
    )

    assert offsets == ["0", "2"]
    assert len(records) == 3
