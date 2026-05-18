from __future__ import annotations

from datetime import UTC, datetime, timedelta
from importlib import import_module
from typing import Any

import pytest

from gb_bess_revenue_stack.config.models import AssetConfig
from gb_bess_revenue_stack.optimisation.inputs import build_dispatch_input
from gb_bess_revenue_stack.optimisation.model_factory import build_energy_dispatch_model
from gb_bess_revenue_stack.optimisation.results import extract_dispatch_result
from gb_bess_revenue_stack.optimisation.solve import solve_dispatch_model
from gb_bess_revenue_stack.schemas.market import WholesalePricePoint

pytestmark = pytest.mark.unit


def _phase3_module(name: str) -> Any:
    try:
        return import_module(name)
    except ModuleNotFoundError as exc:
        raise AssertionError(f"Phase 3 module is not implemented yet: {name}") from exc


def _asset(*, round_trip_efficiency: float = 1) -> AssetConfig:
    return AssetConfig(
        name="reserve-test-asset",
        power_mw=1,
        energy_capacity_mwh=2,
        round_trip_efficiency=round_trip_efficiency,
    )


def _prices(values: list[float]) -> list[WholesalePricePoint]:
    rows: list[WholesalePricePoint] = []
    for index, price in enumerate(values, start=1):
        start = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(minutes=30 * (index - 1))
        end = start + timedelta(minutes=30)
        rows.append(
            WholesalePricePoint(
                delivery_start_utc=start,
                delivery_end_utc=end,
                known_at_utc=end,
                settlement_date=start.date().isoformat(),
                settlement_period=index,
                duration_h=0.5,
                price_gbp_per_mwh=price,
                price_source_type="SYNTHETIC_TEST",
                is_proxy=False,
                retrieved_at_utc=datetime(2024, 1, 2, tzinfo=UTC),
                source_id="PROJECT_CONVENTION",
                source_url="fixture",
                schema_version="0.1.0",
                quality_flag="ok",
            )
        )
    return rows


def _phase2_revenue(prices: list[float]) -> float:
    dispatch_input = build_dispatch_input(
        _prices(prices),
        asset=_asset(),
        initial_soc_mwh=1,
        terminal_soc_policy="cyclic",
        binary_dispatch=True,
    )
    model = build_energy_dispatch_model(dispatch_input)
    diagnostics = solve_dispatch_model(model)
    return extract_dispatch_result(model, diagnostics).total_revenue_gbp


def test_all_services_off_reproduces_phase2_energy_objective() -> None:
    market_stack = _phase3_module("gb_bess_revenue_stack.optimisation.market_stack_model")
    revenue_terms = _phase3_module("gb_bess_revenue_stack.optimisation.revenue_terms")
    prices = [10, 10, 100, 100]

    result = market_stack.solve_market_stack(
        prices=_prices(prices),
        eac_price_matrix=revenue_terms.empty_eac_price_matrix(),
        asset=_asset(),
        initial_soc_mwh=1,
        terminal_soc_policy="cyclic",
    )

    assert result.total_revenue_gbp == pytest.approx(_phase2_revenue(prices))
    assert result.service_revenue_gbp == pytest.approx(0)


def test_idle_battery_can_hold_upward_reserve_without_scheduled_discharge() -> None:
    market_stack = _phase3_module("gb_bess_revenue_stack.optimisation.market_stack_model")
    eac_prices = _phase3_module("gb_bess_revenue_stack.markets.eac_prices")

    result = market_stack.solve_market_stack(
        prices=_prices([0]),
        eac_price_matrix=eac_prices.synthetic_single_service_matrix(
            product_model_label="dynamic_containment_low",
            direction_model_label="upward",
            price_gbp_per_mw_h=100,
            duration_h=0.5,
        ),
        asset=_asset(),
        initial_soc_mwh=1,
        terminal_soc_policy="free",
    )
    row = result.rows[0]

    assert row.discharge_mw == pytest.approx(0)
    assert row.reserve_up_mw["dynamic_containment_low"] > 0
    assert row.reserve_up_mw["dynamic_containment_low"] <= 1


def test_idle_battery_can_hold_downward_reserve_without_scheduled_charge() -> None:
    market_stack = _phase3_module("gb_bess_revenue_stack.optimisation.market_stack_model")
    eac_prices = _phase3_module("gb_bess_revenue_stack.markets.eac_prices")

    result = market_stack.solve_market_stack(
        prices=_prices([0]),
        eac_price_matrix=eac_prices.synthetic_single_service_matrix(
            product_model_label="dynamic_containment_high",
            direction_model_label="downward",
            price_gbp_per_mw_h=100,
            duration_h=0.5,
        ),
        asset=_asset(),
        initial_soc_mwh=1,
        terminal_soc_policy="free",
    )
    row = result.rows[0]

    assert row.charge_mw == pytest.approx(0)
    assert row.reserve_down_mw["dynamic_containment_high"] > 0
    assert row.reserve_down_mw["dynamic_containment_high"] <= 1


def test_market_stack_cooptimises_energy_and_service_revenue_components() -> None:
    market_stack = _phase3_module("gb_bess_revenue_stack.optimisation.market_stack_model")
    eac_prices = _phase3_module("gb_bess_revenue_stack.markets.eac_prices")

    result = market_stack.solve_market_stack(
        prices=_prices([10, 10, 100, 100]),
        eac_price_matrix=eac_prices.synthetic_single_service_matrix(
            product_model_label="dynamic_containment_low",
            direction_model_label="upward",
            price_gbp_per_mw_h=50,
            duration_h=0.5,
        ),
        asset=_asset(),
        initial_soc_mwh=1,
        terminal_soc_policy="cyclic",
    )

    assert result.energy_revenue_gbp > 0
    assert result.service_revenue_gbp > 0
    assert result.total_revenue_gbp == pytest.approx(
        result.energy_revenue_gbp + result.service_revenue_gbp
    )
    assert result.total_revenue_gbp == pytest.approx(result.solver_objective_gbp)


def test_verified_block_constraints_enforce_constant_reserve_mw() -> None:
    market_stack = _phase3_module("gb_bess_revenue_stack.optimisation.market_stack_model")
    eac_prices = _phase3_module("gb_bess_revenue_stack.markets.eac_prices")

    matrix = eac_prices.synthetic_service_matrix(
        product_model_label="dynamic_containment_low",
        direction_model_label="upward",
        prices_gbp_per_mw_h=[100, 0],
        duration_h=0.5,
        block_id="block-a",
        block_commitment_rule="constant_within_block",
    )
    result = market_stack.solve_market_stack(
        prices=_prices([0, 0]),
        eac_price_matrix=matrix,
        asset=_asset(),
        initial_soc_mwh=1,
        terminal_soc_policy="free",
    )

    assert result.rows[0].reserve_up_mw["dynamic_containment_low"] == pytest.approx(
        result.rows[1].reserve_up_mw["dynamic_containment_low"]
    )


def test_service_output_preserves_source_labels_and_caveat_flags() -> None:
    market_stack = _phase3_module("gb_bess_revenue_stack.optimisation.market_stack_model")
    eac_prices = _phase3_module("gb_bess_revenue_stack.markets.eac_prices")

    result = market_stack.solve_market_stack(
        prices=_prices([0]),
        eac_price_matrix=eac_prices.synthetic_single_service_matrix(
            product_source_label="DCL",
            product_model_label="dynamic_containment_low",
            direction_model_label="upward",
            price_gbp_per_mw_h=100,
            duration_h=0.5,
            modelling_caveat="price-taking availability proxy",
        ),
        asset=_asset(),
        initial_soc_mwh=1,
        terminal_soc_policy="free",
    )

    component = result.service_components[0]

    assert component.product_source_label == "DCL"
    assert component.product_model_label == "dynamic_containment_low"
    assert "price-taking" in component.modelling_caveat


def test_upward_reserve_energy_requirement_uses_discharge_efficiency() -> None:
    constraints_reserve = _phase3_module("gb_bess_revenue_stack.optimisation.constraints_reserve")
    asset = _asset(round_trip_efficiency=0.81)

    required = constraints_reserve.upward_reserve_required_soc_mwh(
        reserve_mw=1,
        service_duration_h=0.5,
        asset=asset,
    )

    assert required == pytest.approx(0.5 / 0.9)


def test_downward_reserve_footroom_requirement_uses_charge_efficiency() -> None:
    constraints_reserve = _phase3_module("gb_bess_revenue_stack.optimisation.constraints_reserve")
    asset = _asset(round_trip_efficiency=0.81)

    required = constraints_reserve.downward_reserve_required_footroom_mwh(
        reserve_mw=1,
        service_duration_h=0.5,
        asset=asset,
    )

    assert required == pytest.approx(0.5 * 0.9)


def test_reserve_capacity_shares_headroom_and_footroom_with_energy_dispatch() -> None:
    constraints_reserve = _phase3_module("gb_bess_revenue_stack.optimisation.constraints_reserve")

    headroom = constraints_reserve.available_upward_reserve_mw(
        p_export_max_mw=1,
        discharge_mw=0.4,
    )
    footroom = constraints_reserve.available_downward_reserve_mw(
        p_import_max_mw=1,
        charge_mw=0.25,
    )

    assert headroom == pytest.approx(0.6)
    assert footroom == pytest.approx(0.75)
