from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from gb_bess_revenue_stack.data.elexon import ElexonMIDClient
from gb_bess_revenue_stack.data.neso import NESOEACClient

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("GB_BESS_RUN_INTEGRATION") != "1",
    reason="live source smoke tests are opt-in",
)
def test_elexon_market_index_live_smoke() -> None:
    client = ElexonMIDClient()
    payload = client.fetch_market_index(
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2024, 1, 1, 1, tzinfo=UTC),
    )

    assert payload["data"]
    expected = {
        "startTime",
        "dataProvider",
        "settlementDate",
        "settlementPeriod",
        "price",
        "volume",
    }
    assert expected <= set(payload["data"][0])


@pytest.mark.skipif(
    os.getenv("GB_BESS_RUN_INTEGRATION") != "1",
    reason="live source smoke tests are opt-in",
)
def test_neso_eac_summary_live_smoke() -> None:
    client = NESOEACClient()
    records = client.fetch_summary_records(limit=3)

    assert records
    expected = {"auctionProduct", "deliveryStart", "deliveryEnd", "clearedVolume", "clearingPrice"}
    assert expected <= set(records[0])
