from __future__ import annotations

import pytest

from gb_bess_revenue_stack.commercial import (
    CommercialBessSystem,
    CommercialRouteToMarketAssumptions,
    evaluate_commercial_route_to_market,
)

pytestmark = pytest.mark.unit


def test_commercial_capex_and_export_limit_are_derived_separately_from_residential() -> None:
    system = CommercialBessSystem(
        name="commercial-phase4",
        battery_capacity_mwh=10,
        inverter_power_mw=5,
        site_export_limit_mw=3,
        battery_capex_gbp_per_mwh=210_000,
        inverter_capex_gbp_per_mw=90_000,
        installation_cost_gbp=125_000,
        grid_connection_cost_gbp=75_000,
    )

    assert system.branch_name == "commercial"
    assert system.effective_export_limit_mw == pytest.approx(3)
    assert system.total_capex_gbp == pytest.approx(2_750_000)


def test_commercial_route_to_market_flags_direct_and_aggregator_fees() -> None:
    system = CommercialBessSystem(
        name="route-test",
        battery_capacity_mwh=4,
        inverter_power_mw=2,
        site_export_limit_mw=1.5,
        battery_capex_gbp_per_mwh=200_000,
        inverter_capex_gbp_per_mw=100_000,
    )
    assumptions = CommercialRouteToMarketAssumptions(
        direct_market_min_export_mw=1,
        direct_market_fixed_fee_gbp_per_year=20_000,
        direct_market_variable_fee_pct=0.03,
        aggregator_revenue_share_pct=0.18,
        aggregator_fixed_fee_gbp_per_year=2_500,
    )

    access = evaluate_commercial_route_to_market(system, assumptions=assumptions)

    direct = access.route("direct_markets")
    aggregator = access.route("aggregator_route")

    assert direct.eligible is True
    assert direct.variable_fee_pct == pytest.approx(0.03)
    assert direct.fixed_fee_gbp_per_year == pytest.approx(20_000)
    assert aggregator.eligible is True
    assert aggregator.variable_fee_pct == pytest.approx(0.18)
    assert aggregator.fixed_fee_gbp_per_year == pytest.approx(2_500)


def test_small_commercial_site_uses_aggregator_when_direct_market_threshold_not_met() -> None:
    system = CommercialBessSystem(
        name="small-site",
        battery_capacity_mwh=0.8,
        inverter_power_mw=0.4,
        site_export_limit_mw=0.3,
        battery_capex_gbp_per_mwh=250_000,
        inverter_capex_gbp_per_mw=120_000,
    )

    access = evaluate_commercial_route_to_market(system)

    assert access.route("direct_markets").eligible is False
    assert access.route("aggregator_route").eligible is True
    assert access.effective_export_limit_mw == pytest.approx(0.3)
