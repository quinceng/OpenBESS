from __future__ import annotations

import pytest

from gb_bess_revenue_stack.commercial import CommercialBessSystem
from gb_bess_revenue_stack.residential import (
    ResidentialBessSystem,
    UKResidentialMarketAccessAssumptions,
    evaluate_residential_market_access,
    get_residential_preset,
    residential_presets,
)

pytestmark = pytest.mark.unit


def test_integrated_inverter_capex_excludes_external_inverter_cost() -> None:
    system = ResidentialBessSystem(
        name="integrated-test",
        battery_capacity_kwh=13.5,
        inverter_power_kw=11.04,
        has_integrated_inverter=True,
        battery_cost_gbp=7_000,
        installation_cost_gbp=1_000,
        inverter_cost_gbp=1_200,
    )

    assert system.effective_inverter_cost_gbp == pytest.approx(0)
    assert system.total_capex_gbp == pytest.approx(8_000)
    assert system.branch_name == "residential"


def test_battery_only_capex_includes_compatible_inverter_cost() -> None:
    system = ResidentialBessSystem(
        name="battery-only-test",
        battery_capacity_kwh=9.5,
        inverter_power_kw=3.6,
        has_integrated_inverter=False,
        battery_cost_gbp=4_350,
        installation_cost_gbp=800,
        inverter_cost_gbp=1_000,
    )

    assert system.effective_inverter_cost_gbp == pytest.approx(1_000)
    assert system.total_capex_gbp == pytest.approx(6_150)


def test_default_uk_residential_product_presets_capture_inverter_and_cost_ranges() -> None:
    presets = residential_presets()

    tesla = presets["tesla_powerwall_3"]
    giv_95 = presets["givenergy_9_5_module"]
    giv_aio2 = presets["givenergy_all_in_one_2"]
    enphase = presets["enphase_iq_battery_5p"]

    assert tesla.battery_capacity_kwh == pytest.approx(13.5)
    assert tesla.has_integrated_inverter is True
    assert tesla.installed_capex_low_gbp == pytest.approx(7_499)
    assert tesla.installed_capex_high_gbp == pytest.approx(9_000)

    assert giv_95.battery_capacity_kwh == pytest.approx(9.5)
    assert giv_95.has_integrated_inverter is False
    assert giv_95.inverter_cost_gbp > 0
    assert giv_95.total_capex_gbp == pytest.approx(
        giv_95.battery_cost_gbp + giv_95.installation_cost_gbp + giv_95.inverter_cost_gbp
    )

    assert giv_aio2.battery_capacity_kwh == pytest.approx(13.5)
    assert giv_aio2.has_integrated_inverter is True
    assert giv_aio2.effective_inverter_cost_gbp == pytest.approx(0)

    assert enphase.battery_capacity_kwh == pytest.approx(5)
    assert enphase.has_integrated_inverter is True
    assert enphase.installed_capex_low_gbp == pytest.approx(3_500)
    assert enphase.installed_capex_high_gbp == pytest.approx(4_500)


def test_default_residential_market_access_separates_export_limit_from_inverter_power() -> None:
    system = get_residential_preset("tesla_powerwall_3")
    access = evaluate_residential_market_access(
        system,
        assumptions=UKResidentialMarketAccessAssumptions(),
    )

    assert system.inverter_power_kw > access.effective_export_limit_kw
    assert access.effective_export_limit_kw == pytest.approx(3.68)
    assert access.stream("self_consumption_arbitrage").eligible is True
    assert access.stream("export").eligible is True
    assert access.stream("aggregator_vpp").eligible is True
    assert access.stream("direct_neso_market_bidding").eligible is False
    assert access.stream("ukpn_london_local_flex_direct").eligible is False


def test_market_access_thresholds_allow_direct_local_and_neso_when_scaled() -> None:
    system = ResidentialBessSystem(
        name="scaled-portfolio",
        battery_capacity_kwh=2_500,
        inverter_power_kw=1_200,
        has_integrated_inverter=False,
        battery_cost_gbp=500_000,
        installation_cost_gbp=50_000,
        inverter_cost_gbp=80_000,
    )
    assumptions = UKResidentialMarketAccessAssumptions(dno_export_limit_kw=1_200)

    access = evaluate_residential_market_access(system, assumptions=assumptions)

    assert access.stream("ukpn_london_local_flex_direct").eligible is True
    assert access.stream("direct_neso_market_bidding").eligible is True


def test_residential_and_commercial_branches_keep_scale_units_separate() -> None:
    commercial = CommercialBessSystem(
        name="commercial-test",
        battery_capacity_mwh=2,
        inverter_power_mw=1,
        site_export_limit_mw=0.8,
    )

    assert commercial.effective_export_limit_mw == pytest.approx(0.8)
    assert commercial.branch_name == "commercial"
