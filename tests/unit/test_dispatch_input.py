from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from gb_bess_revenue_stack.config.models import AssetConfig
from gb_bess_revenue_stack.optimisation.inputs import build_dispatch_input
from gb_bess_revenue_stack.schemas.market import WholesalePricePoint

pytestmark = pytest.mark.unit


def _asset() -> AssetConfig:
    return AssetConfig(
        name="test-asset",
        power_mw=1,
        energy_capacity_mwh=2,
        round_trip_efficiency=0.81,
    )


def _price_point(
    period: int,
    price: float,
    *,
    start_hour: float | None = None,
) -> WholesalePricePoint:
    start = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(
        hours=start_hour if start_hour is not None else (period - 1) * 0.5
    )
    end = start + timedelta(minutes=30)
    return WholesalePricePoint(
        delivery_start_utc=start,
        delivery_end_utc=end,
        settlement_date="2024-01-01",
        settlement_period=period,
        duration_h=0.5,
        price_gbp_per_mwh=price,
        price_source_type="MID",
        is_proxy=True,
        known_at_utc=end,
        retrieved_at_utc=datetime(2024, 1, 2, tzinfo=UTC),
        source_id="ELEXON_BMRS_MID",
        source_url="https://data.elexon.co.uk",
        schema_version="0.1.0",
        quality_flag="ok",
    )


def test_dispatch_input_preserves_order_and_manifest_metadata() -> None:
    dispatch_input = build_dispatch_input(
        [_price_point(2, 20), _price_point(1, 10)],
        asset=_asset(),
        initial_soc_mwh=1,
        terminal_soc_policy="cyclic",
        binary_dispatch=True,
        data_manifest_ref="fixture.manifest.json",
        config_hash="abc123",
    )

    assert [period.price_gbp_per_mwh for period in dispatch_input.periods] == [10, 20]
    assert dispatch_input.period_count == 2
    assert dispatch_input.data_manifest_ref == "fixture.manifest.json"
    assert dispatch_input.config_hash == "abc123"


def test_dispatch_input_rejects_duplicate_delivery_starts() -> None:
    first = _price_point(1, 10)
    duplicate = _price_point(2, 20, start_hour=0)

    with pytest.raises(ValueError, match="duplicate"):
        build_dispatch_input(
            [first, duplicate],
            asset=_asset(),
            initial_soc_mwh=1,
            terminal_soc_policy="cyclic",
            binary_dispatch=True,
        )


def test_dispatch_input_rejects_initial_soc_outside_bounds() -> None:
    with pytest.raises(ValueError, match="initial_soc_mwh"):
        build_dispatch_input(
            [_price_point(1, 10)],
            asset=_asset(),
            initial_soc_mwh=3,
            terminal_soc_policy="cyclic",
            binary_dispatch=True,
        )


def test_dispatch_input_accepts_explicit_terminal_target() -> None:
    dispatch_input = build_dispatch_input(
        [_price_point(1, 10), _price_point(2, 100)],
        asset=_asset(),
        initial_soc_mwh=1,
        terminal_soc_policy="target",
        terminal_soc_target_mwh=0.5,
        binary_dispatch=True,
    )

    assert dispatch_input.terminal_soc_policy == "target"
    assert dispatch_input.terminal_soc_target_mwh == pytest.approx(0.5)


def test_dispatch_input_rejects_missing_terminal_target() -> None:
    with pytest.raises(ValueError, match="terminal_soc_target_mwh"):
        build_dispatch_input(
            [_price_point(1, 10), _price_point(2, 100)],
            asset=_asset(),
            initial_soc_mwh=1,
            terminal_soc_policy="target",
            binary_dispatch=True,
        )
