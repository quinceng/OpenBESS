from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from gb_bess_revenue_stack.data.elexon import ElexonMIDClient, parse_market_index_points

pytestmark = pytest.mark.unit


def test_parse_market_index_points_preserves_provider_and_proxy_metadata() -> None:
    payload = {
        "metadata": {"datasets": ["MID"]},
        "data": [
            {
                "startTime": "2024-01-01T00:00:00Z",
                "dataProvider": "APXMIDP",
                "settlementDate": "2024-01-01",
                "settlementPeriod": 1,
                "price": 36.51,
                "volume": 664.4,
            },
            {
                "startTime": "2024-01-01T00:30:00Z",
                "dataProvider": "APXMIDP",
                "settlementDate": "2024-01-01",
                "settlementPeriod": 2,
                "price": -2.0,
                "volume": 10.0,
            },
        ],
    }

    points = parse_market_index_points(
        payload,
        source_url="https://data.elexon.co.uk/bmrs/api/v1/balancing/pricing/market-index",
        retrieved_at_utc=datetime(2024, 1, 2, tzinfo=UTC),
    )

    assert [point.settlement_period for point in points] == [1, 2]
    assert points[0].price_source_type == "MID"
    assert points[0].is_proxy is True
    assert points[0].source_record_id == "APXMIDP:2024-01-01:1"
    assert points[1].price_gbp_per_mwh == -2.0


def test_client_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "temporary"}, request=request)

    client = ElexonMIDClient(http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(httpx.HTTPStatusError):
        client.fetch_market_index(
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2024, 1, 1, 1, tzinfo=UTC),
        )
