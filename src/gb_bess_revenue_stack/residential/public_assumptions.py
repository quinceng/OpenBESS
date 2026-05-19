from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict, Field

from gb_bess_revenue_stack.residential.profiles import (
    ResidentialHouseholdInterval,
    ResidentialTariffPeriod,
    ResidentialTariffSchedule,
)
from gb_bess_revenue_stack.schemas.base import ensure_aware_utc

ResidentialPublicInput = Literal[
    "household_load",
    "load_shape",
    "pv_generation",
    "retail_import_tariff",
    "retail_export_tariff",
    "vpp_payments",
    "export_limit",
]

ResidentialPublicSourceAvailability = Literal[
    "public_free",
    "public_free_registration",
    "public_api_free",
    "restricted_research_access",
    "private_authenticated",
    "contract_specific",
]


class ResidentialPublicDataSource(BaseModel):
    """Public, free or fallback residential source candidate."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    name: str
    url: str
    availability: ResidentialPublicSourceAvailability
    geography: str
    residential_inputs_supported: tuple[ResidentialPublicInput, ...]
    source_year: int | None = None
    notes: str


class ResidentialPublicReferenceHouseholdAssumptions(BaseModel):
    """Reference household assumptions derived from public UK residential sources."""

    model_config = ConfigDict(extra="forbid")

    key: str
    geography_name: str
    source_year: int
    annual_load_mean_per_meter_kwh: float = Field(gt=0)
    annual_load_median_per_meter_kwh: float = Field(gt=0)
    annual_load_mean_per_household_kwh: float = Field(gt=0)
    default_import_rate_gbp_per_kwh: float = Field(gt=0)
    default_export_rate_gbp_per_kwh: float = Field(ge=0)
    seg_export_rate_gbp_per_kwh: float = Field(ge=0)
    standing_charge_gbp_per_day: float = Field(ge=0)
    default_export_limit_kw: float = Field(gt=0)
    default_latitude: float
    default_longitude: float
    default_pv_capacity_kwp: float = Field(gt=0)
    default_pv_tilt_deg: float
    default_pv_azimuth_deg: float
    default_pv_system_loss_pct: float = Field(ge=0, le=100)
    vpp_event_reward_low_gbp: float = Field(ge=0)
    vpp_event_reward_central_gbp: float = Field(ge=0)
    vpp_event_reward_high_gbp: float = Field(ge=0)
    vpp_reference_events_per_year: int = Field(ge=0)
    source_ids: tuple[str, ...]
    caveats: tuple[str, ...]

    @property
    def default_annual_load_kwh(self) -> float:
        """Default load scalar used for generated reference profiles."""

        return self.annual_load_mean_per_household_kwh

    @property
    def vpp_low_case_annual_revenue_gbp(self) -> float:
        return self.vpp_event_reward_low_gbp * self.vpp_reference_events_per_year

    @property
    def vpp_central_case_annual_revenue_gbp(self) -> float:
        return self.vpp_event_reward_central_gbp * self.vpp_reference_events_per_year

    @property
    def vpp_high_case_annual_revenue_gbp(self) -> float:
        return self.vpp_event_reward_high_gbp * self.vpp_reference_events_per_year


def public_residential_data_sources() -> dict[str, ResidentialPublicDataSource]:
    """Return known public/free residential source candidates."""

    return {key: source.model_copy(deep=True) for key, source in _PUBLIC_SOURCES.items()}


def get_public_reference_household_assumptions(
    geography: Literal["london", "gb", "great_britain", "great britain"] = "london",
) -> ResidentialPublicReferenceHouseholdAssumptions:
    """Return public reference household assumptions for London or Great Britain."""

    key = geography.strip().lower().replace("-", "_")
    if key == "great britain":
        key = "great_britain"
    try:
        return _PUBLIC_REFERENCE_HOUSEHOLDS[key].model_copy(deep=True)
    except KeyError as exc:
        msg = f"Unknown public reference household geography {geography!r}."
        raise KeyError(msg) from exc


def build_public_reference_tariff_schedule(
    valid_from_utc: datetime,
    valid_to_utc: datetime,
    *,
    geography: Literal["london", "gb", "great_britain", "great britain"] = "london",
    export_rate: Literal["octopus_outgoing_fixed", "seg_floor"] = "octopus_outgoing_fixed",
) -> ResidentialTariffSchedule:
    """Build a flat public-reference tariff schedule for a date range."""

    assumptions = get_public_reference_household_assumptions(geography)
    start = ensure_aware_utc(valid_from_utc)
    end = ensure_aware_utc(valid_to_utc)
    export_rate_gbp_per_kwh = (
        assumptions.seg_export_rate_gbp_per_kwh
        if export_rate == "seg_floor"
        else assumptions.default_export_rate_gbp_per_kwh
    )
    return ResidentialTariffSchedule(
        periods=(
            ResidentialTariffPeriod(
                valid_from_utc=start,
                valid_to_utc=end,
                import_rate_gbp_per_kwh=assumptions.default_import_rate_gbp_per_kwh,
                export_rate_gbp_per_kwh=export_rate_gbp_per_kwh,
                standing_charge_gbp_per_day=assumptions.standing_charge_gbp_per_day,
            ),
        )
    )


def build_flat_public_reference_load_profile(
    start_utc: datetime,
    end_utc: datetime,
    *,
    geography: Literal["london", "gb", "great_britain", "great britain"] = "london",
    interval_minutes: int = 30,
) -> list[ResidentialHouseholdInterval]:
    """Generate a flat half-hourly load profile scaled to public annual averages.

    This is a baseline fallback. Prefer observed half-hourly data, London
    Datastore Low Carbon London samples, UKPN/SSEN aggregate shapes, or Elexon
    profile coefficients when a shaped profile is required.
    """

    if interval_minutes <= 0:
        msg = "interval_minutes must be positive."
        raise ValueError(msg)
    start = ensure_aware_utc(start_utc)
    end = ensure_aware_utc(end_utc)
    if end <= start:
        msg = "end_utc must be after start_utc."
        raise ValueError(msg)
    interval = timedelta(minutes=interval_minutes)
    assumptions = get_public_reference_household_assumptions(geography)
    average_kw = assumptions.default_annual_load_kwh / 8760

    rows: list[ResidentialHouseholdInterval] = []
    cursor = start
    while cursor < end:
        next_cursor = min(cursor + interval, end)
        duration_h = (next_cursor - cursor).total_seconds() / 3600
        rows.append(
            ResidentialHouseholdInterval(
                delivery_start_utc=cursor,
                delivery_end_utc=next_cursor,
                load_kwh=average_kw * duration_h,
                pv_generation_kwh=0,
            )
        )
        cursor = next_cursor
    return rows


def build_pvgis_hourly_url(
    *,
    latitude: float,
    longitude: float,
    pv_capacity_kwp: float,
    loss_pct: float,
    tilt_deg: float,
    azimuth_deg: float,
    start_year: int | None = None,
    end_year: int | None = None,
) -> str:
    """Return a PVGIS hourly PV production API URL."""

    params: dict[str, str | int | float] = {
        "lat": latitude,
        "lon": longitude,
        "pvcalculation": 1,
        "peakpower": pv_capacity_kwp,
        "loss": loss_pct,
        "angle": tilt_deg,
        "aspect": azimuth_deg,
        "outputformat": "json",
    }
    if start_year is not None:
        params["startyear"] = start_year
    if end_year is not None:
        params["endyear"] = end_year
    return f"https://re.jrc.ec.europa.eu/api/v5_3/seriescalc?{urlencode(params)}"


_PUBLIC_SOURCES: dict[str, ResidentialPublicDataSource] = {
    "desnz_subnational_electricity_2024": ResidentialPublicDataSource(
        source_id="desnz_subnational_electricity_2024",
        name="DESNZ Subnational electricity consumption statistics 2005-2024",
        url=(
            "https://www.gov.uk/government/statistics/"
            "regional-and-local-authority-electricity-consumption-statistics"
        ),
        availability="public_free",
        geography="Great Britain, countries, regions, local authorities, MSOA/LSOA, postcode",
        residential_inputs_supported=("household_load",),
        source_year=2024,
        notes=(
            "Official annual domestic electricity consumption aggregates. Use for annual "
            "load scalars and London/GB mean or median reference households."
        ),
    ),
    "london_datastore_low_carbon_london": ResidentialPublicDataSource(
        source_id="london_datastore_low_carbon_london",
        name="SmartMeter Energy Consumption Data in London Households",
        url="https://data.london.gov.uk/dataset/smartmeter-energy-use-data-in-london-households/",
        availability="public_free",
        geography="London",
        residential_inputs_supported=("household_load", "load_shape", "retail_import_tariff"),
        source_year=2013,
        notes=(
            "Half-hourly London household sample from the Low Carbon London trial. Useful "
            "for load-shape proxies, but historical and very large."
        ),
    ),
    "ukpn_smart_meter_aggregate_open_data": ResidentialPublicDataSource(
        source_id="ukpn_smart_meter_aggregate_open_data",
        name="UK Power Networks aggregated smart meter sample data",
        url="https://ukpowernetworks.opendatasoft.com/pages/smart-meters/",
        availability="public_free_registration",
        geography="UKPN licence areas including London",
        residential_inputs_supported=("household_load", "load_shape"),
        notes=(
            "Aggregated half-hourly import consumption at secondary-substation level, "
            "with meter counts. Portal access may require free registration."
        ),
    ),
    "ssen_weave_aggregated_smart_meter": ResidentialPublicDataSource(
        source_id="ssen_weave_aggregated_smart_meter",
        name="Weave aggregated half-hourly domestic smart meter data",
        url="https://data.ssen.co.uk/showcases/weave-half-hourly-energy-consumption",
        availability="public_free",
        geography="GB DNO low-voltage feeders",
        residential_inputs_supported=("household_load", "load_shape"),
        notes=(
            "Aggregated domestic smart-meter consumption at LV feeder level from multiple "
            "DNOs, distributed as analysis-ready GeoParquet."
        ),
    ),
    "elexon_profile_classes": ResidentialPublicDataSource(
        source_id="elexon_profile_classes",
        name="Elexon Profile Class load profiles and coefficients",
        url="https://www.elexon.co.uk/knowledgebase/profile-classes/",
        availability="public_free",
        geography="Great Britain",
        residential_inputs_supported=("load_shape",),
        notes=(
            "Profile Classes 1 and 2 represent domestic unrestricted and Economy 7 "
            "customers. Use as a public domestic load-shape fallback."
        ),
    ),
    "pvgis_hourly_pv": ResidentialPublicDataSource(
        source_id="pvgis_hourly_pv",
        name="European Commission JRC PVGIS hourly PV production API",
        url="https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis_en",
        availability="public_api_free",
        geography="Global except poles",
        residential_inputs_supported=("pv_generation",),
        notes=(
            "No-registration API for estimated PV generation from coordinates, system "
            "size, loss, tilt and azimuth assumptions."
        ),
    ),
    "ofgem_price_cap_2026_q2": ResidentialPublicDataSource(
        source_id="ofgem_price_cap_2026_q2",
        name="Ofgem April-June 2026 price cap average electricity rates",
        url="https://www.ofgem.gov.uk/news/changes-energy-price-cap-between-1-april-and-30-june-2026",
        availability="public_free",
        geography="England, Scotland and Wales average",
        residential_inputs_supported=("retail_import_tariff",),
        source_year=2026,
        notes=(
            "Public average standard-variable Direct Debit unit rate and standing charge. "
            "Not a London-specific tariff and not a customer contract."
        ),
    ),
    "octopus_public_tariff_api": ResidentialPublicDataSource(
        source_id="octopus_public_tariff_api",
        name="Octopus Energy public product and tariff API",
        url="https://docs.octopus.energy/rest/guides/endpoints/",
        availability="public_api_free",
        geography="GB tariff regions",
        residential_inputs_supported=("retail_import_tariff", "retail_export_tariff"),
        notes=(
            "Unauthenticated product and tariff endpoints expose public standing-charge "
            "and unit-rate histories. Customer account and consumption endpoints require "
            "authentication."
        ),
    ),
    "octopus_export_tariffs": ResidentialPublicDataSource(
        source_id="octopus_export_tariffs",
        name="Octopus Energy public export tariffs",
        url="https://octopus.energy/export-tariffs/",
        availability="public_free",
        geography="Great Britain where eligible",
        residential_inputs_supported=("retail_export_tariff", "vpp_payments"),
        notes=(
            "Public export tariff rates and battery tariff eligibility. Exact Intelligent "
            "Flux/VPP value depends on hardware eligibility and tariff terms."
        ),
    ),
    "ofgem_seg_framework": ResidentialPublicDataSource(
        source_id="ofgem_seg_framework",
        name="Ofgem Smart Export Guarantee framework and supplier list",
        url="https://www.ofgem.gov.uk/environmental-and-social-schemes/smart-export-guarantee-seg/electricity-suppliers",
        availability="public_free",
        geography="Great Britain",
        residential_inputs_supported=("retail_export_tariff",),
        notes=(
            "SEG licensees choose tariff rates and terms. Use published supplier SEG "
            "rates as scenario inputs, not as universal rates."
        ),
    ),
    "neso_dfs_winter_2024_25": ResidentialPublicDataSource(
        source_id="neso_dfs_winter_2024_25",
        name="NESO Demand Flexibility Service Winter 2024/25 review",
        url="https://www.neso.energy/document/363911/download",
        availability="public_free",
        geography="Great Britain",
        residential_inputs_supported=("vpp_payments",),
        source_year=2025,
        notes=(
            "Public DFS market statistics. Useful for VPP/flexibility scenario ranges, "
            "but not a guaranteed household payment."
        ),
    ),
    "cse_dfs_household_rewards": ResidentialPublicDataSource(
        source_id="cse_dfs_household_rewards",
        name="Centre for Sustainable Energy DFS household reward estimates",
        url="https://www.cse.org.uk/advice/how-much-could-you-earn-demand-flexibility-service/",
        availability="public_free",
        geography="Great Britain household examples",
        residential_inputs_supported=("vpp_payments",),
        source_year=2025,
        notes=(
            "Public household reward examples. CSE reports typical event rewards around "
            "GBP 1-5, depending on peak-time use and reduction."
        ),
    ),
    "ena_g98_g99_g100": ResidentialPublicDataSource(
        source_id="ena_g98_g99_g100",
        name="Energy Networks Association G98/G99/G100 connection rules",
        url=(
            "https://www.energynetworks.org/industry/connecting-to-the-networks/"
            "connecting-generation-to-the-electricity-networks"
        ),
        availability="public_free",
        geography="Great Britain distribution networks",
        residential_inputs_supported=("export_limit",),
        notes=(
            "Public connection-rule basis for 3.68 kW per phase G98 defaults and G100 "
            "export-limitation treatment. Site-specific approval remains private."
        ),
    ),
}

_COMMON_SOURCE_IDS = (
    "desnz_subnational_electricity_2024",
    "london_datastore_low_carbon_london",
    "ukpn_smart_meter_aggregate_open_data",
    "ssen_weave_aggregated_smart_meter",
    "elexon_profile_classes",
    "pvgis_hourly_pv",
    "ofgem_price_cap_2026_q2",
    "octopus_public_tariff_api",
    "octopus_export_tariffs",
    "ofgem_seg_framework",
    "neso_dfs_winter_2024_25",
    "cse_dfs_household_rewards",
    "ena_g98_g99_g100",
)

_COMMON_CAVEATS = (
    "Reference assumptions are public-data proxies, not actual household telemetry.",
    "Retail tariffs and export tariffs should be overridden with a customer contract "
    "where available.",
    "VPP payments are scenario assumptions unless backed by an active aggregator contract.",
    "Export limits should be overridden with site DNO/G98/G99/G100 paperwork where available.",
)

_PUBLIC_REFERENCE_HOUSEHOLDS: dict[str, ResidentialPublicReferenceHouseholdAssumptions] = {
    "london": ResidentialPublicReferenceHouseholdAssumptions(
        key="london",
        geography_name="London",
        source_year=2024,
        annual_load_mean_per_meter_kwh=3240.67104307353,
        annual_load_median_per_meter_kwh=2357.399999989125,
        annual_load_mean_per_household_kwh=3302.319295729267,
        default_import_rate_gbp_per_kwh=0.2467,
        default_export_rate_gbp_per_kwh=0.12,
        seg_export_rate_gbp_per_kwh=0.041,
        standing_charge_gbp_per_day=0.5721,
        default_export_limit_kw=3.68,
        default_latitude=51.5074,
        default_longitude=-0.1278,
        default_pv_capacity_kwp=4.0,
        default_pv_tilt_deg=35.0,
        default_pv_azimuth_deg=0.0,
        default_pv_system_loss_pct=14.0,
        vpp_event_reward_low_gbp=1.0,
        vpp_event_reward_central_gbp=3.0,
        vpp_event_reward_high_gbp=5.0,
        vpp_reference_events_per_year=12,
        source_ids=_COMMON_SOURCE_IDS,
        caveats=_COMMON_CAVEATS,
    ),
    "gb": ResidentialPublicReferenceHouseholdAssumptions(
        key="gb",
        geography_name="Great Britain",
        source_year=2024,
        annual_load_mean_per_meter_kwh=3322.735541706746,
        annual_load_median_per_meter_kwh=2471.1,
        annual_load_mean_per_household_kwh=3463.408415200937,
        default_import_rate_gbp_per_kwh=0.2467,
        default_export_rate_gbp_per_kwh=0.12,
        seg_export_rate_gbp_per_kwh=0.041,
        standing_charge_gbp_per_day=0.5721,
        default_export_limit_kw=3.68,
        default_latitude=54.0,
        default_longitude=-2.0,
        default_pv_capacity_kwp=4.0,
        default_pv_tilt_deg=35.0,
        default_pv_azimuth_deg=0.0,
        default_pv_system_loss_pct=14.0,
        vpp_event_reward_low_gbp=1.0,
        vpp_event_reward_central_gbp=3.0,
        vpp_event_reward_high_gbp=5.0,
        vpp_reference_events_per_year=12,
        source_ids=_COMMON_SOURCE_IDS,
        caveats=_COMMON_CAVEATS,
    ),
}
_PUBLIC_REFERENCE_HOUSEHOLDS["great_britain"] = _PUBLIC_REFERENCE_HOUSEHOLDS["gb"]
