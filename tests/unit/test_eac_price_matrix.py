from __future__ import annotations

from datetime import UTC, datetime, timedelta
from importlib import import_module
from typing import Any

import pytest

from gb_bess_revenue_stack.schemas.market import EACAuctionResult, WholesalePricePoint

pytestmark = pytest.mark.unit


def _phase3_module(name: str) -> Any:
    try:
        return import_module(name)
    except ModuleNotFoundError as exc:
        raise AssertionError(f"Phase 3 module is not implemented yet: {name}") from exc


def _price_period(period: int) -> WholesalePricePoint:
    start = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(minutes=30 * (period - 1))
    end = start + timedelta(minutes=30)
    return WholesalePricePoint(
        delivery_start_utc=start,
        delivery_end_utc=end,
        known_at_utc=end,
        settlement_date=start.date().isoformat(),
        settlement_period=period,
        duration_h=0.5,
        price_gbp_per_mwh=0,
        price_source_type="SYNTHETIC_TEST",
        is_proxy=False,
        retrieved_at_utc=datetime(2024, 1, 2, tzinfo=UTC),
        source_id="PROJECT_CONVENTION",
        source_url="fixture",
        schema_version="0.1.0",
        quality_flag="ok",
    )


def _eac_result(
    *,
    period: int,
    price: float,
    known_at_utc: datetime,
    product: str = "DCL",
    duration_periods: int = 1,
    procured_mw: float | None = 100,
    block_id: str | None = None,
) -> EACAuctionResult:
    start = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(minutes=30 * (period - 1))
    end = start + timedelta(minutes=30 * duration_periods)
    return EACAuctionResult(
        product_source_label=product,
        product_model_label="dynamic_containment_low",
        direction_source_label=product,
        direction_model_label="upward",
        delivery_start_utc=start,
        delivery_end_utc=end,
        known_at_utc=known_at_utc,
        clearing_price_gbp_per_mw_h=price,
        procured_mw=procured_mw,
        accepted_mw=procured_mw,
        block_id=block_id,
        retrieved_at_utc=datetime(2024, 1, 2, tzinfo=UTC),
        source_id="NESO_EAC_AUCTION_RESULTS",
        source_url="fixture",
        source_record_id=f"{product}:{period}",
        schema_version="0.1.0",
        quality_flag="ok",
    )


def test_eac_price_matrix_preserves_known_at_metadata_and_zero_prices() -> None:
    eac_prices = _phase3_module("gb_bess_revenue_stack.markets.eac_prices")
    periods = [_price_period(1)]
    known_at = datetime(2023, 12, 31, 11, tzinfo=UTC)

    matrix = eac_prices.build_eac_price_matrix(
        records=[_eac_result(period=1, price=0, known_at_utc=known_at)],
        target_periods=periods,
    )
    cell = matrix.cell(product_model_label="dynamic_containment_low", period_index=0)

    assert cell.price_gbp_per_mw_h == 0
    assert cell.availability_state == "available"
    assert cell.known_at_utc == known_at
    assert cell.source_record_id == "DCL:1"


def test_eac_price_matrix_classifies_missing_source_gap_without_zero_filling() -> None:
    eac_prices = _phase3_module("gb_bess_revenue_stack.markets.eac_prices")
    periods = [_price_period(1), _price_period(2)]

    matrix = eac_prices.build_eac_price_matrix(
        records=[
            _eac_result(
                period=1,
                price=5,
                known_at_utc=datetime(2023, 12, 31, 11, tzinfo=UTC),
            )
        ],
        target_periods=periods,
        product_model_labels=["dynamic_containment_low"],
    )

    missing = matrix.cell(product_model_label="dynamic_containment_low", period_index=1)

    assert missing.price_gbp_per_mw_h is None
    assert missing.availability_state == "source_gap"
    assert missing.known_at_utc is None


def test_eac_price_matrix_excludes_rows_not_known_at_decision_time() -> None:
    eac_prices = _phase3_module("gb_bess_revenue_stack.markets.eac_prices")
    periods = [_price_period(1)]
    decision_time = datetime(2024, 1, 1, tzinfo=UTC)

    matrix = eac_prices.build_eac_price_matrix(
        records=[
            _eac_result(
                period=1,
                price=999,
                known_at_utc=decision_time + timedelta(hours=1),
            )
        ],
        target_periods=periods,
        decision_time_utc=decision_time,
        product_model_labels=["dynamic_containment_low"],
    )

    cell = matrix.cell(product_model_label="dynamic_containment_low", period_index=0)

    assert cell.price_gbp_per_mw_h is None
    assert cell.availability_state == "not_known_at_decision_time"


def test_eac_price_matrix_aligns_source_window_across_settlement_periods() -> None:
    eac_prices = _phase3_module("gb_bess_revenue_stack.markets.eac_prices")
    periods = [_price_period(1), _price_period(2)]

    matrix = eac_prices.build_eac_price_matrix(
        records=[
            _eac_result(
                period=1,
                price=7.5,
                known_at_utc=datetime(2023, 12, 31, 11, tzinfo=UTC),
                duration_periods=2,
                block_id="block-a",
            )
        ],
        target_periods=periods,
    )

    first = matrix.cell(product_model_label="dynamic_containment_low", period_index=0)
    second = matrix.cell(product_model_label="dynamic_containment_low", period_index=1)

    assert first.price_gbp_per_mw_h == pytest.approx(7.5)
    assert second.price_gbp_per_mw_h == pytest.approx(7.5)
    assert first.block_id == "block-a"
    assert second.block_id == "block-a"


def test_eac_price_matrix_classifies_not_procured_separately_from_source_gap() -> None:
    eac_prices = _phase3_module("gb_bess_revenue_stack.markets.eac_prices")

    matrix = eac_prices.build_eac_price_matrix(
        records=[
            _eac_result(
                period=1,
                price=0,
                known_at_utc=datetime(2023, 12, 31, 11, tzinfo=UTC),
                procured_mw=0,
            )
        ],
        target_periods=[_price_period(1)],
    )
    cell = matrix.cell(product_model_label="dynamic_containment_low", period_index=0)

    assert cell.price_gbp_per_mw_h is None
    assert cell.availability_state == "not_procured"
