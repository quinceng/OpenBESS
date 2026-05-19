from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from gb_bess_revenue_stack.residential.models import (
    ResidentialHouseholdCalculatorInputs,
    ResidentialHouseholdCalculatorResult,
    calculate_residential_household_payback,
    get_residential_preset,
)


class ResidentialPaybackScenario(BaseModel):
    """Named household BESS payback scenario for release comparison tables."""

    model_config = ConfigDict(extra="forbid")

    name: str
    system_preset_key: str
    dno_export_limit_kw: float = Field(gt=0)
    annual_self_consumption_savings_gbp: float = Field(ge=0)
    annual_tariff_arbitrage_savings_gbp: float = Field(ge=0)
    annual_export_revenue_gbp: float = Field(ge=0)
    annual_aggregator_vpp_revenue_gbp: float = Field(ge=0)
    include_aggregator_vpp: bool = True
    assumption_basis: str = "public_proxy_scenario"
    notes: str = ""


class ResidentialPaybackScenarioResult(BaseModel):
    """Result for one residential payback scenario."""

    model_config = ConfigDict(extra="forbid")

    scenario_name: str
    system_preset_key: str
    assumption_basis: str
    notes: str
    payback: ResidentialHouseholdCalculatorResult


def default_residential_payback_scenarios() -> list[ResidentialPaybackScenario]:
    """Return default residential scenario cases used by release smoke outputs."""

    return [
        ResidentialPaybackScenario(
            name="standard_flat_tariff",
            system_preset_key="givenergy_all_in_one_2",
            dno_export_limit_kw=3.68,
            annual_self_consumption_savings_gbp=360,
            annual_tariff_arbitrage_savings_gbp=120,
            annual_export_revenue_gbp=72,
            annual_aggregator_vpp_revenue_gbp=36,
            notes="Central flat-rate household proxy with modest PV export and VPP value.",
        ),
        ResidentialPaybackScenario(
            name="smart_tariff_high_spread",
            system_preset_key="tesla_powerwall_3",
            dno_export_limit_kw=3.68,
            annual_self_consumption_savings_gbp=440,
            annual_tariff_arbitrage_savings_gbp=320,
            annual_export_revenue_gbp=90,
            annual_aggregator_vpp_revenue_gbp=60,
            notes="Smart import-tariff upside with higher intra-day spread capture.",
        ),
        ResidentialPaybackScenario(
            name="pv_rich_export_limited",
            system_preset_key="tesla_powerwall_3",
            dno_export_limit_kw=3.68,
            annual_self_consumption_savings_gbp=620,
            annual_tariff_arbitrage_savings_gbp=180,
            annual_export_revenue_gbp=180,
            annual_aggregator_vpp_revenue_gbp=36,
            notes="Larger PV household where G98-style export limit constrains spill value.",
        ),
        ResidentialPaybackScenario(
            name="g100_export_uplift",
            system_preset_key="tesla_powerwall_3",
            dno_export_limit_kw=10,
            annual_self_consumption_savings_gbp=650,
            annual_tariff_arbitrage_savings_gbp=220,
            annual_export_revenue_gbp=260,
            annual_aggregator_vpp_revenue_gbp=60,
            notes="Export-limit sensitivity representing a site-specific G100-style allowance.",
        ),
        ResidentialPaybackScenario(
            name="low_use_no_vpp",
            system_preset_key="enphase_iq_battery_5p",
            dno_export_limit_kw=3.68,
            annual_self_consumption_savings_gbp=180,
            annual_tariff_arbitrage_savings_gbp=45,
            annual_export_revenue_gbp=25,
            annual_aggregator_vpp_revenue_gbp=0,
            include_aggregator_vpp=False,
            notes="Low-use household downside with no aggregator/VPP payment assumed.",
        ),
    ]


def run_residential_payback_scenarios(
    scenarios: Sequence[ResidentialPaybackScenario] | None = None,
) -> list[ResidentialPaybackScenarioResult]:
    """Evaluate named residential payback scenarios without touching commercial models."""

    selected = default_residential_payback_scenarios() if scenarios is None else list(scenarios)
    results: list[ResidentialPaybackScenarioResult] = []
    for scenario in selected:
        system = get_residential_preset(scenario.system_preset_key)
        payback = calculate_residential_household_payback(
            system,
            inputs=ResidentialHouseholdCalculatorInputs(
                dno_export_limit_kw=scenario.dno_export_limit_kw,
                annual_self_consumption_savings_gbp=(scenario.annual_self_consumption_savings_gbp),
                annual_tariff_arbitrage_savings_gbp=(scenario.annual_tariff_arbitrage_savings_gbp),
                annual_export_revenue_gbp=scenario.annual_export_revenue_gbp,
                annual_aggregator_vpp_revenue_gbp=(scenario.annual_aggregator_vpp_revenue_gbp),
                include_aggregator_vpp=scenario.include_aggregator_vpp,
            ),
        )
        results.append(
            ResidentialPaybackScenarioResult(
                scenario_name=scenario.name,
                system_preset_key=scenario.system_preset_key,
                assumption_basis=scenario.assumption_basis,
                notes=scenario.notes,
                payback=payback,
            )
        )
    return results
