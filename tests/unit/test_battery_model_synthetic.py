from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from gb_bess_revenue_stack.config.models import AssetConfig
from gb_bess_revenue_stack.optimisation.inputs import build_dispatch_input
from gb_bess_revenue_stack.optimisation.model_factory import build_energy_dispatch_model
from gb_bess_revenue_stack.optimisation.results import extract_dispatch_result
from gb_bess_revenue_stack.optimisation.solve import solve_dispatch_model
from gb_bess_revenue_stack.schemas.market import WholesalePricePoint

pytestmark = pytest.mark.unit


def _asset() -> AssetConfig:
    return AssetConfig(
        name="test-asset",
        power_mw=1,
        energy_capacity_mwh=2,
        eta_charge=1,
        eta_discharge=1,
    )


def _lossy_asset() -> AssetConfig:
    return AssetConfig(
        name="lossy-test-asset",
        power_mw=1,
        energy_capacity_mwh=2,
        round_trip_efficiency=0.81,
    )


def _point(period: int, price: float) -> WholesalePricePoint:
    start = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=(period - 1) * 0.5)
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


def _solve(prices: list[float], *, asset: AssetConfig | None = None, terminal: str = "cyclic"):
    dispatch_input = build_dispatch_input(
        [_point(index + 1, price) for index, price in enumerate(prices)],
        asset=asset or _asset(),
        initial_soc_mwh=1,
        terminal_soc_policy=terminal,
        binary_dispatch=True,
    )
    model = build_energy_dispatch_model(dispatch_input)
    diagnostics = solve_dispatch_model(model)
    return extract_dispatch_result(model, diagnostics)


def test_model_builds_with_expected_dimensions() -> None:
    dispatch_input = build_dispatch_input(
        [_point(1, 10), _point(2, 20)],
        asset=_asset(),
        initial_soc_mwh=1,
        terminal_soc_policy="cyclic",
        binary_dispatch=True,
    )

    model = build_energy_dispatch_model(dispatch_input)

    assert len(model.T) == 2
    assert len(model.SOC_INDEX) == 3
    assert hasattr(model, "is_discharging")


def test_flat_zero_price_produces_no_movement_and_zero_revenue() -> None:
    result = _solve([0, 0, 0, 0])

    assert result.total_revenue_gbp == pytest.approx(0)
    assert result.charged_mwh == pytest.approx(0)
    assert result.discharged_mwh == pytest.approx(0)


def test_low_then_high_price_charges_then_discharges() -> None:
    result = _solve([10, 10, 100, 100])

    assert result.total_revenue_gbp > 0
    assert result.rows[0].charge_mw > 0
    assert result.rows[-1].discharge_mw > 0
    assert result.final_soc_mwh == pytest.approx(result.initial_soc_mwh)


def test_negative_then_positive_price_handles_negative_prices() -> None:
    result = _solve([-20, -20, 80, 80])

    assert result.total_revenue_gbp > 80
    assert result.rows[0].charge_mw > 0
    assert result.rows[-1].discharge_mw > 0


def test_insufficient_spread_below_losses_avoids_cycling() -> None:
    result = _solve([100, 100, 105, 105], asset=_lossy_asset())

    assert result.total_revenue_gbp == pytest.approx(0, abs=1e-6)
    assert result.charged_mwh == pytest.approx(0, abs=1e-6)
    assert result.discharged_mwh == pytest.approx(0, abs=1e-6)


def test_free_terminal_soc_shows_end_drain_artifact() -> None:
    cyclic = _solve([10, 10, 100, 100], terminal="cyclic")
    free = _solve([10, 10, 100, 100], terminal="free")

    assert free.total_revenue_gbp > cyclic.total_revenue_gbp
    assert free.final_soc_mwh < cyclic.final_soc_mwh


def test_binary_mode_prevents_simultaneous_charge_and_discharge() -> None:
    result = _solve([-20, -20, 80, 80])

    for row in result.rows:
        assert row.charge_mw * row.discharge_mw == pytest.approx(0, abs=1e-8)


def test_objective_equals_extracted_revenue() -> None:
    result = _solve([10, 10, 100, 100])

    assert result.solver.objective_value == pytest.approx(result.total_revenue_gbp)
