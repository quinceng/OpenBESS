from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ResidentialRevenueStreamName = Literal[
    "self_consumption_arbitrage",
    "export",
    "aggregator_vpp",
    "direct_neso_market_bidding",
    "ukpn_london_local_flex_direct",
]


class ResidentialBessSystem(BaseModel):
    """Household-scale BESS product and cost assumptions."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    branch_name: Literal["residential"] = "residential"
    name: str
    battery_capacity_kwh: float = Field(gt=0)
    inverter_power_kw: float = Field(gt=0)
    has_integrated_inverter: bool
    battery_cost_gbp: float = Field(ge=0)
    installation_cost_gbp: float = Field(ge=0)
    inverter_cost_gbp: float = Field(default=0, ge=0)
    total_capex_gbp: float = Field(default=0, ge=0)
    installed_capex_low_gbp: float | None = Field(default=None, ge=0)
    installed_capex_high_gbp: float | None = Field(default=None, ge=0)
    source_id: str = "USER_ASSUMPTION"
    source_url: str | None = None
    notes: str = ""

    @property
    def effective_inverter_cost_gbp(self) -> float:
        """External inverter cost counted in capex after integrated-inverter logic."""

        if self.has_integrated_inverter:
            return 0.0
        return self.inverter_cost_gbp

    @model_validator(mode="after")
    def validate_and_derive_capex(self) -> ResidentialBessSystem:
        if not self.has_integrated_inverter and self.inverter_cost_gbp <= 0:
            msg = "Battery-only residential systems must include compatible inverter cost."
            raise ValueError(msg)
        if (self.installed_capex_low_gbp is None) != (self.installed_capex_high_gbp is None):
            msg = "Provide both installed_capex_low_gbp and installed_capex_high_gbp, or neither."
            raise ValueError(msg)
        if (
            self.installed_capex_low_gbp is not None
            and self.installed_capex_high_gbp is not None
            and self.installed_capex_low_gbp > self.installed_capex_high_gbp
        ):
            msg = "installed_capex_low_gbp must be less than or equal to installed_capex_high_gbp."
            raise ValueError(msg)

        total = (
            self.battery_cost_gbp + self.installation_cost_gbp + self.effective_inverter_cost_gbp
        )
        object.__setattr__(self, "total_capex_gbp", total)
        return self


class UKResidentialMarketAccessAssumptions(BaseModel):
    """Default UK residential access constraints for household BESS routes."""

    model_config = ConfigDict(extra="forbid")

    aggregator_vpp_allowed: bool = True
    direct_neso_min_kw: float = Field(default=1_000, gt=0)
    ukpn_london_local_flex_direct_min_kw: float = Field(default=10, gt=0)
    dno_export_limit_kw: float = Field(default=3.68, gt=0)


class RevenueStreamEligibility(BaseModel):
    """Eligibility result for one residential revenue route."""

    model_config = ConfigDict(extra="forbid")

    name: ResidentialRevenueStreamName
    eligible: bool
    power_cap_kw: float = Field(ge=0)
    reason: str


class ResidentialMarketAccessResult(BaseModel):
    """Residential revenue-route eligibility under a concrete export limit."""

    model_config = ConfigDict(extra="forbid")

    system_name: str
    inverter_power_kw: float = Field(gt=0)
    dno_export_limit_kw: float = Field(gt=0)
    effective_export_limit_kw: float = Field(gt=0)
    revenue_streams: tuple[RevenueStreamEligibility, ...]

    def stream(self, name: ResidentialRevenueStreamName) -> RevenueStreamEligibility:
        for revenue_stream in self.revenue_streams:
            if revenue_stream.name == name:
                return revenue_stream
        msg = f"Unknown residential revenue stream {name!r}."
        raise KeyError(msg)


class ResidentialHouseholdCalculatorInputs(BaseModel):
    """Simple household BESS annual benefit assumptions."""

    model_config = ConfigDict(extra="forbid")

    dno_export_limit_kw: float = Field(default=3.68, gt=0)
    annual_self_consumption_savings_gbp: float = Field(ge=0)
    annual_tariff_arbitrage_savings_gbp: float
    annual_export_revenue_gbp: float = 0
    annual_aggregator_vpp_revenue_gbp: float = Field(default=0, ge=0)
    include_aggregator_vpp: bool = True


class ResidentialHouseholdCalculatorResult(BaseModel):
    """Payback-style household calculator output."""

    model_config = ConfigDict(extra="forbid")

    branch_name: Literal["residential"] = "residential"
    system_name: str
    battery_capacity_kwh: float = Field(gt=0)
    inverter_power_kw: float = Field(gt=0)
    export_limit_kw: float = Field(gt=0)
    capex_gbp: float = Field(ge=0)
    self_consumption_savings_gbp: float = Field(ge=0)
    tariff_arbitrage_savings_gbp: float
    export_revenue_gbp: float
    aggregator_vpp_revenue_gbp: float = Field(ge=0)
    total_annual_benefit_gbp: float
    simple_payback_years: float | None = Field(default=None, ge=0)
    market_access: ResidentialMarketAccessResult


def evaluate_residential_market_access(
    system: ResidentialBessSystem,
    *,
    assumptions: UKResidentialMarketAccessAssumptions | None = None,
) -> ResidentialMarketAccessResult:
    """Evaluate residential revenue routes without invoking the main optimiser."""

    market_assumptions = assumptions or UKResidentialMarketAccessAssumptions()
    effective_export_limit_kw = min(
        system.inverter_power_kw, market_assumptions.dno_export_limit_kw
    )
    local_flex_eligible = (
        effective_export_limit_kw >= market_assumptions.ukpn_london_local_flex_direct_min_kw
    )
    direct_neso_eligible = effective_export_limit_kw >= market_assumptions.direct_neso_min_kw

    revenue_streams = (
        RevenueStreamEligibility(
            name="self_consumption_arbitrage",
            eligible=True,
            power_cap_kw=system.inverter_power_kw,
            reason="Behind-the-meter use is limited by the inverter, not the DNO export cap.",
        ),
        RevenueStreamEligibility(
            name="export",
            eligible=effective_export_limit_kw > 0,
            power_cap_kw=effective_export_limit_kw,
            reason=(
                "Export is capped by the lower of inverter power and configured DNO export limit."
            ),
        ),
        RevenueStreamEligibility(
            name="aggregator_vpp",
            eligible=market_assumptions.aggregator_vpp_allowed,
            power_cap_kw=effective_export_limit_kw,
            reason=(
                "Residential participation is modelled through an aggregator/VPP route by default."
            ),
        ),
        RevenueStreamEligibility(
            name="direct_neso_market_bidding",
            eligible=direct_neso_eligible,
            power_cap_kw=effective_export_limit_kw,
            reason=(
                "Direct NESO access requires the effective export capability to meet the "
                f"{market_assumptions.direct_neso_min_kw:g} kW modelling threshold."
            ),
        ),
        RevenueStreamEligibility(
            name="ukpn_london_local_flex_direct",
            eligible=local_flex_eligible,
            power_cap_kw=effective_export_limit_kw,
            reason=(
                "Direct UKPN/London local flexibility access requires the effective export "
                "capability to meet the "
                f"{market_assumptions.ukpn_london_local_flex_direct_min_kw:g} kW modelling "
                "threshold."
            ),
        ),
    )

    return ResidentialMarketAccessResult(
        system_name=system.name,
        inverter_power_kw=system.inverter_power_kw,
        dno_export_limit_kw=market_assumptions.dno_export_limit_kw,
        effective_export_limit_kw=effective_export_limit_kw,
        revenue_streams=revenue_streams,
    )


def calculate_residential_household_payback(
    system: ResidentialBessSystem,
    *,
    inputs: ResidentialHouseholdCalculatorInputs,
) -> ResidentialHouseholdCalculatorResult:
    """Calculate simple annual household BESS savings and payback outputs."""

    market_access = evaluate_residential_market_access(
        system,
        assumptions=UKResidentialMarketAccessAssumptions(
            dno_export_limit_kw=inputs.dno_export_limit_kw
        ),
    )
    aggregator_revenue = (
        inputs.annual_aggregator_vpp_revenue_gbp
        if inputs.include_aggregator_vpp and market_access.stream("aggregator_vpp").eligible
        else 0.0
    )
    total_annual_benefit = (
        inputs.annual_self_consumption_savings_gbp
        + inputs.annual_tariff_arbitrage_savings_gbp
        + inputs.annual_export_revenue_gbp
        + aggregator_revenue
    )
    simple_payback_years = (
        system.total_capex_gbp / total_annual_benefit if total_annual_benefit > 0 else None
    )
    return ResidentialHouseholdCalculatorResult(
        system_name=system.name,
        battery_capacity_kwh=system.battery_capacity_kwh,
        inverter_power_kw=system.inverter_power_kw,
        export_limit_kw=market_access.effective_export_limit_kw,
        capex_gbp=system.total_capex_gbp,
        self_consumption_savings_gbp=inputs.annual_self_consumption_savings_gbp,
        tariff_arbitrage_savings_gbp=inputs.annual_tariff_arbitrage_savings_gbp,
        export_revenue_gbp=inputs.annual_export_revenue_gbp,
        aggregator_vpp_revenue_gbp=aggregator_revenue,
        total_annual_benefit_gbp=total_annual_benefit,
        simple_payback_years=simple_payback_years,
        market_access=market_access,
    )


def calculate_residential_household_payback_from_dispatch(
    system: ResidentialBessSystem,
    *,
    dispatch: object,
    sample_hours: float,
    dno_export_limit_kw: float,
) -> ResidentialHouseholdCalculatorResult:
    """Annualise a bill-aware residential dispatch result into payback outputs."""

    from gb_bess_revenue_stack.residential.dispatch import ResidentialHouseholdDispatchResult

    if sample_hours <= 0:
        msg = "sample_hours must be positive."
        raise ValueError(msg)
    validated_dispatch = ResidentialHouseholdDispatchResult.model_validate(dispatch)
    annualisation_factor = 8760 / sample_hours
    vpp_revenue = (
        0.0
        if validated_dispatch.vpp_revenue is None
        else validated_dispatch.vpp_revenue.total_vpp_revenue_gbp
    )
    return calculate_residential_household_payback(
        system,
        inputs=ResidentialHouseholdCalculatorInputs(
            dno_export_limit_kw=dno_export_limit_kw,
            annual_self_consumption_savings_gbp=validated_dispatch.self_consumption_savings_gbp
            * annualisation_factor,
            annual_tariff_arbitrage_savings_gbp=validated_dispatch.tariff_arbitrage_savings_gbp
            * annualisation_factor,
            annual_export_revenue_gbp=validated_dispatch.export_revenue_delta_gbp
            * annualisation_factor,
            annual_aggregator_vpp_revenue_gbp=vpp_revenue * annualisation_factor,
            include_aggregator_vpp=True,
        ),
    )


def residential_presets() -> dict[str, ResidentialBessSystem]:
    """Return default UK residential product presets as independent model copies."""

    return {key: preset.model_copy(deep=True) for key, preset in _RESIDENTIAL_PRESETS.items()}


def get_residential_preset(key: str) -> ResidentialBessSystem:
    """Return one residential preset by stable key."""

    try:
        return _RESIDENTIAL_PRESETS[key].model_copy(deep=True)
    except KeyError as exc:
        msg = f"Unknown residential BESS preset {key!r}."
        raise KeyError(msg) from exc


_RESIDENTIAL_PRESETS: dict[str, ResidentialBessSystem] = {
    "tesla_powerwall_3": ResidentialBessSystem(
        name="Tesla Powerwall 3",
        battery_capacity_kwh=13.5,
        inverter_power_kw=11.04,
        has_integrated_inverter=True,
        battery_cost_gbp=7_249.50,
        installation_cost_gbp=1_000,
        inverter_cost_gbp=0,
        installed_capex_low_gbp=7_499,
        installed_capex_high_gbp=9_000,
        source_id="OFFICIAL_PRODUCT_SPEC_AND_USER_SUPPLIED_COST_RANGE",
        source_url="https://www.tesla.com/en_GB/powerwall",
        notes=(
            "Integrated-inverter household preset; component split is a modelling default. "
            "Capex range is user supplied."
        ),
    ),
    "givenergy_9_5_module": ResidentialBessSystem(
        name="GivEnergy 9.5 kWh module",
        battery_capacity_kwh=9.5,
        inverter_power_kw=3.6,
        has_integrated_inverter=False,
        battery_cost_gbp=4_350,
        installation_cost_gbp=800,
        inverter_cost_gbp=1_000,
        installed_capex_low_gbp=5_800,
        installed_capex_high_gbp=6_500,
        source_id="OFFICIAL_PRODUCT_SPEC_AND_USER_SUPPLIED_COST_RANGE",
        source_url="https://givenergy.com/resource-hub/datasheets/giv-bat-9-5-datasheet/",
        notes=(
            "Battery-only preset includes a compatible external inverter cost. "
            "Capex range is user supplied."
        ),
    ),
    "givenergy_all_in_one_2": ResidentialBessSystem(
        name="GivEnergy All-in-One 2",
        battery_capacity_kwh=13.5,
        inverter_power_kw=6.0,
        has_integrated_inverter=True,
        battery_cost_gbp=5_950,
        installation_cost_gbp=800,
        inverter_cost_gbp=0,
        installed_capex_low_gbp=6_200,
        installed_capex_high_gbp=7_300,
        source_id="OFFICIAL_PRODUCT_SPEC_AND_USER_SUPPLIED_COST_RANGE",
        source_url="https://givenergy.com/hardware/all-in-one-2/",
        notes=(
            "Integrated-inverter household preset; component split is a modelling default. "
            "Capex range is user supplied."
        ),
    ),
    "enphase_iq_battery_5p": ResidentialBessSystem(
        name="Enphase IQ Battery 5P",
        battery_capacity_kwh=5.0,
        inverter_power_kw=3.84,
        has_integrated_inverter=True,
        battery_cost_gbp=3_400,
        installation_cost_gbp=600,
        inverter_cost_gbp=0,
        installed_capex_low_gbp=3_500,
        installed_capex_high_gbp=4_500,
        source_id="OFFICIAL_PRODUCT_SPEC_AND_USER_SUPPLIED_COST_RANGE",
        source_url="https://enphase.com/store/storage/gen3/iq-battery-5p",
        notes=(
            "Integrated AC-coupled household preset; component split is a modelling default. "
            "Capex range is user supplied."
        ),
    ),
}
