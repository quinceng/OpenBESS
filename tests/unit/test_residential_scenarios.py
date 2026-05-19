from __future__ import annotations

import pytest

from gb_bess_revenue_stack.residential import (
    ResidentialPaybackScenario,
    default_residential_payback_scenarios,
    run_residential_payback_scenarios,
)

pytestmark = pytest.mark.unit


def test_default_residential_scenarios_cover_tariff_pv_export_limit_and_vpp() -> None:
    scenarios = default_residential_payback_scenarios()
    by_name = {scenario.name: scenario for scenario in scenarios}

    assert {
        "standard_flat_tariff",
        "smart_tariff_high_spread",
        "pv_rich_export_limited",
        "g100_export_uplift",
        "low_use_no_vpp",
    } <= set(by_name)
    assert by_name["smart_tariff_high_spread"].annual_tariff_arbitrage_savings_gbp > (
        by_name["standard_flat_tariff"].annual_tariff_arbitrage_savings_gbp
    )
    assert by_name["pv_rich_export_limited"].annual_export_revenue_gbp > (
        by_name["standard_flat_tariff"].annual_export_revenue_gbp
    )
    assert by_name["g100_export_uplift"].dno_export_limit_kw >= 10
    assert by_name["low_use_no_vpp"].include_aggregator_vpp is False


def test_residential_scenario_runner_preserves_branch_and_market_access() -> None:
    results = run_residential_payback_scenarios(default_residential_payback_scenarios())
    by_name = {result.scenario_name: result for result in results}

    assert len(results) >= 5
    assert all(result.payback.branch_name == "residential" for result in results)
    assert by_name["smart_tariff_high_spread"].payback.total_annual_benefit_gbp > (
        by_name["standard_flat_tariff"].payback.total_annual_benefit_gbp
    )
    assert (
        by_name["g100_export_uplift"]
        .payback.market_access.stream("ukpn_london_local_flex_direct")
        .eligible
        is True
    )
    assert by_name["low_use_no_vpp"].payback.aggregator_vpp_revenue_gbp == pytest.approx(0)


def test_residential_scenario_runner_respects_explicit_empty_sweep() -> None:
    assert run_residential_payback_scenarios([]) == []


def test_residential_scenario_rejects_negative_tariff_arbitrage() -> None:
    with pytest.raises(ValueError):
        ResidentialPaybackScenario(
            name="negative_arbitrage",
            system_preset_key="tesla_powerwall_3",
            dno_export_limit_kw=3.68,
            annual_self_consumption_savings_gbp=100,
            annual_tariff_arbitrage_savings_gbp=-1,
            annual_export_revenue_gbp=20,
            annual_aggregator_vpp_revenue_gbp=0,
        )
