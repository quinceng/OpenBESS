from __future__ import annotations

import pytest

from gb_bess_revenue_stack.commercial import CommercialBessSystem
from gb_bess_revenue_stack.residential import (
    ResidentialBessSystem,
    ResidentialBillBreakdown,
    ResidentialHouseholdCalculatorInputs,
    ResidentialHouseholdDispatchResult,
    ResidentialVPPRevenue,
    UKResidentialMarketAccessAssumptions,
    calculate_residential_household_payback,
    calculate_residential_household_payback_from_dispatch,
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


def test_household_calculator_combines_savings_vpp_and_payback_outputs() -> None:
    system = get_residential_preset("givenergy_all_in_one_2")
    inputs = ResidentialHouseholdCalculatorInputs(
        dno_export_limit_kw=3.68,
        annual_self_consumption_savings_gbp=420,
        annual_tariff_arbitrage_savings_gbp=210,
        annual_export_revenue_gbp=95,
        annual_aggregator_vpp_revenue_gbp=80,
        include_aggregator_vpp=True,
    )

    result = calculate_residential_household_payback(system, inputs=inputs)

    assert result.branch_name == "residential"
    assert result.battery_capacity_kwh == pytest.approx(13.5)
    assert result.export_limit_kw == pytest.approx(3.68)
    assert result.capex_gbp == pytest.approx(system.total_capex_gbp)
    assert result.total_annual_benefit_gbp == pytest.approx(805)
    assert result.simple_payback_years == pytest.approx(system.total_capex_gbp / 805)
    assert result.market_access.stream("direct_neso_market_bidding").eligible is False


def test_household_calculator_excludes_vpp_revenue_when_aggregator_route_disabled() -> None:
    system = get_residential_preset("tesla_powerwall_3")
    inputs = ResidentialHouseholdCalculatorInputs(
        dno_export_limit_kw=3.68,
        annual_self_consumption_savings_gbp=500,
        annual_tariff_arbitrage_savings_gbp=250,
        annual_export_revenue_gbp=100,
        annual_aggregator_vpp_revenue_gbp=120,
        include_aggregator_vpp=False,
    )

    result = calculate_residential_household_payback(system, inputs=inputs)

    assert result.aggregator_vpp_revenue_gbp == pytest.approx(0)
    assert result.total_annual_benefit_gbp == pytest.approx(850)


def test_household_payback_accepts_dispatch_result_components() -> None:
    system = get_residential_preset("tesla_powerwall_3")
    result = calculate_residential_household_payback(
        system,
        inputs=ResidentialHouseholdCalculatorInputs(
            dno_export_limit_kw=3.68,
            annual_self_consumption_savings_gbp=100,
            annual_tariff_arbitrage_savings_gbp=200,
            annual_export_revenue_gbp=30,
            annual_aggregator_vpp_revenue_gbp=40,
            include_aggregator_vpp=True,
        ),
    )

    assert result.total_annual_benefit_gbp == pytest.approx(370)
    assert result.simple_payback_years == pytest.approx(system.total_capex_gbp / 370)


def test_household_dispatch_result_annualises_into_payback() -> None:
    zero_bill = ResidentialBillBreakdown(
        import_kwh=0,
        export_kwh=0,
        pv_to_load_kwh=0,
        pv_curtailed_kwh=0,
        import_cost_gbp=0,
        export_revenue_gbp=0,
        energy_bill_gbp=0,
        standing_charge_gbp=0,
        total_bill_gbp=0,
    )
    dispatch = ResidentialHouseholdDispatchResult.model_construct(
        rows=[],
        no_battery_bill=zero_bill,
        battery_bill=zero_bill,
        self_consumption_savings_gbp=10,
        tariff_arbitrage_savings_gbp=5,
        export_revenue_delta_gbp=2,
        total_bill_savings_gbp=17,
        charged_kwh=20,
        discharged_kwh=18,
        equivalent_cycles=1.5,
        solver=None,
        vpp_revenue=ResidentialVPPRevenue(
            fixed_payment_gbp=1,
            event_payment_gbp=2,
            total_vpp_revenue_gbp=3,
            delivered_event_kwh=1,
            shortfall_kwh=0,
        ),
    )

    result = calculate_residential_household_payback_from_dispatch(
        get_residential_preset("tesla_powerwall_3"),
        dispatch=dispatch,
        sample_hours=24,
        dno_export_limit_kw=3.68,
    )

    assert result.total_annual_benefit_gbp == pytest.approx((17 + 3) * 365)
