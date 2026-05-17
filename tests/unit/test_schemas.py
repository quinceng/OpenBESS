from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from gb_bess_revenue_stack.schemas.market import (
    CapacityMarketScenario,
    EACAuctionResult,
    WholesalePricePoint,
)

pytestmark = pytest.mark.unit


def test_wholesale_mid_requires_proxy_label() -> None:
    with pytest.raises(ValidationError):
        WholesalePricePoint(
            delivery_start_utc=datetime(2024, 1, 1, tzinfo=UTC),
            delivery_end_utc=datetime(2024, 1, 1, 0, 30, tzinfo=UTC),
            settlement_date="2024-01-01",
            settlement_period=1,
            duration_h=0.5,
            price_gbp_per_mwh=42.0,
            price_source_type="MID",
            is_proxy=False,
            known_at_utc=datetime(2024, 1, 1, 0, 30, tzinfo=UTC),
            retrieved_at_utc=datetime(2024, 1, 2, tzinfo=UTC),
            source_id="ELEXON_BMRS_MID",
            source_url="https://data.elexon.co.uk",
            schema_version="0.1.0",
            quality_flag="ok",
        )


def test_wholesale_negative_price_is_valid() -> None:
    point = WholesalePricePoint(
        delivery_start_utc=datetime(2024, 1, 1, tzinfo=UTC),
        delivery_end_utc=datetime(2024, 1, 1, 0, 30, tzinfo=UTC),
        settlement_date="2024-01-01",
        settlement_period=1,
        duration_h=0.5,
        price_gbp_per_mwh=-5.25,
        price_source_type="MID",
        is_proxy=True,
        known_at_utc=datetime(2024, 1, 1, 0, 30, tzinfo=UTC),
        retrieved_at_utc=datetime(2024, 1, 2, tzinfo=UTC),
        source_id="ELEXON_BMRS_MID",
        source_url="https://data.elexon.co.uk",
        schema_version="0.1.0",
        quality_flag="ok",
    )

    assert point.price_gbp_per_mwh == -5.25


def test_eac_result_rejects_end_before_start() -> None:
    with pytest.raises(ValidationError):
        EACAuctionResult(
            product_source_label="DCL",
            product_model_label="dynamic_containment_low",
            direction_source_label="DCL",
            direction_model_label="upward",
            delivery_start_utc=datetime(2024, 1, 1, 1, tzinfo=UTC),
            delivery_end_utc=datetime(2024, 1, 1, tzinfo=UTC),
            known_at_utc=datetime(2023, 12, 31, tzinfo=UTC),
            clearing_price_gbp_per_mw_h=10,
            procured_mw=20,
            accepted_mw=20,
            retrieved_at_utc=datetime(2024, 1, 1, 2, tzinfo=UTC),
            source_id="NESO_EAC_AUCTION_RESULTS",
            source_url="https://api.neso.energy",
            schema_version="0.1.0",
            quality_flag="ok",
        )


def test_capacity_market_derated_mw_is_computed_when_omitted() -> None:
    scenario = CapacityMarketScenario(
        scenario_name="t4_2028_29_two_hour",
        auction_type="T-4",
        delivery_year="2028/29",
        clearing_price_gbp_per_kw_year=60,
        derating_factor=0.2094,
        asset_duration_hours=2,
        contracted_mw_nameplate=50,
        source_id="CM_OFFICIAL_AUCTION_PARAMETERS",
        source_url="https://www.gov.uk/",
        source_date="2025-12-17",
        notes="official result anchor with storage derating placeholder",
    )

    assert scenario.contracted_mw_derated == pytest.approx(50 * 0.2094)


def test_timezone_naive_datetimes_are_rejected() -> None:
    with pytest.raises(ValidationError):
        WholesalePricePoint(
            delivery_start_utc=datetime(2024, 1, 1),
            delivery_end_utc=datetime(2024, 1, 1) + timedelta(minutes=30),
            settlement_date="2024-01-01",
            settlement_period=1,
            duration_h=0.5,
            price_gbp_per_mwh=42,
            price_source_type="MID",
            is_proxy=True,
            known_at_utc=datetime(2024, 1, 1, 0, 30),
            retrieved_at_utc=datetime(2024, 1, 2),
            source_id="ELEXON_BMRS_MID",
            source_url="https://data.elexon.co.uk",
            schema_version="0.1.0",
            quality_flag="ok",
        )
