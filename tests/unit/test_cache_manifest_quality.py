from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gb_bess_revenue_stack.data.cache import RawCache
from gb_bess_revenue_stack.data.manifest import DatasetManifest, dataframe_hash
from gb_bess_revenue_stack.data.quality import validate_wholesale_prices
from gb_bess_revenue_stack.data.tabular import records_to_dataframe
from gb_bess_revenue_stack.schemas.market import WholesalePricePoint

pytestmark = pytest.mark.unit


def _point(period: int, price: float) -> WholesalePricePoint:
    start = datetime(2024, 1, 1, hour=(period - 1) // 2, minute=30 * ((period - 1) % 2), tzinfo=UTC)
    end = (
        start.replace(minute=start.minute + 30)
        if start.minute == 0
        else start.replace(hour=start.hour + 1, minute=0)
    )
    return WholesalePricePoint(
        delivery_start_utc=start,
        delivery_end_utc=end,
        settlement_date="2024-01-01",
        settlement_period=period,
        duration_h=0.5,
        price_gbp_per_mwh=price,
        price_source_type="MID",
        is_proxy=True,
        known_at_utc=start,
        retrieved_at_utc=datetime(2024, 1, 2, tzinfo=UTC),
        source_id="ELEXON_BMRS_MID",
        source_url="https://data.elexon.co.uk",
        schema_version="0.1.0",
        quality_flag="ok",
    )


def test_raw_cache_writes_content_addressed_files(tmp_path) -> None:
    cache = RawCache(tmp_path)
    first = cache.write_bytes(
        source_id="ELEXON_BMRS_MID",
        dataset="market-index",
        content=b'{"data":[]}',
        suffix=".json",
        retrieved_at_utc=datetime(2024, 1, 1, tzinfo=UTC),
    )
    second = cache.write_bytes(
        source_id="ELEXON_BMRS_MID",
        dataset="market-index",
        content=b'{"data":[]}',
        suffix=".json",
        retrieved_at_utc=datetime(2024, 1, 1, tzinfo=UTC),
    )

    assert first.path == second.path
    assert first.sha256 == second.sha256
    assert first.path.read_bytes() == b'{"data":[]}'


def test_manifest_records_hash_and_quality_status() -> None:
    frame = records_to_dataframe([_point(1, -5), _point(2, 10)])
    manifest = DatasetManifest.from_dataframe(
        dataset="wholesale_price_points",
        schema_version="0.1.0",
        frame=frame,
        source_ids=["ELEXON_BMRS_MID"],
        source_urls=["https://data.elexon.co.uk"],
        retrieved_at_utc=datetime(2024, 1, 2, tzinfo=UTC),
        known_at_policy="delivery_end_utc",
        validation_status="passed",
    )

    assert manifest.row_count == 2
    assert manifest.data_hash == dataframe_hash(frame)
    assert manifest.validation_status == "passed"


def test_quality_report_flags_duplicates_and_missing_periods_but_not_negative_prices() -> None:
    report = validate_wholesale_prices([_point(1, -5), _point(1, 12), _point(3, 9)])

    assert report.negative_price_count == 1
    assert any(issue.code == "duplicate_period" for issue in report.issues)
    assert any(issue.code == "missing_period" for issue in report.issues)
    assert not any(issue.code == "negative_price" for issue in report.issues)
