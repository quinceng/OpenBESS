"""Residential BESS modelling branch.

This namespace is intentionally separate from the utility-scale market-stack
optimiser. Residential models use household-scale kW/kWh assumptions and UK
market-access rules that should not be mixed into the central commercial model.
"""

from gb_bess_revenue_stack.residential.billing import (
    ResidentialBillBreakdown,
    calculate_no_battery_bill,
)
from gb_bess_revenue_stack.residential.dispatch import (
    ResidentialHouseholdDispatchInput,
    ResidentialHouseholdDispatchResult,
    ResidentialHouseholdDispatchRow,
    solve_residential_household_dispatch,
)
from gb_bess_revenue_stack.residential.models import (
    ResidentialBessSystem,
    ResidentialHouseholdCalculatorInputs,
    ResidentialHouseholdCalculatorResult,
    ResidentialMarketAccessResult,
    RevenueStreamEligibility,
    UKResidentialMarketAccessAssumptions,
    calculate_residential_household_payback,
    calculate_residential_household_payback_from_dispatch,
    evaluate_residential_market_access,
    get_residential_preset,
    residential_presets,
)
from gb_bess_revenue_stack.residential.profiles import (
    ResidentialHouseholdInterval,
    ResidentialTariffPeriod,
    ResidentialTariffSchedule,
    validate_household_intervals,
)
from gb_bess_revenue_stack.residential.public_assumptions import (
    ResidentialPublicDataSource,
    ResidentialPublicReferenceHouseholdAssumptions,
    build_flat_public_reference_load_profile,
    build_public_reference_tariff_schedule,
    build_pvgis_hourly_url,
    get_public_reference_household_assumptions,
    public_residential_data_sources,
)
from gb_bess_revenue_stack.residential.vpp import (
    ResidentialVPPEvent,
    ResidentialVPPRevenue,
    ResidentialVPPSchedule,
    calculate_vpp_revenue,
)

__all__ = [
    "ResidentialHouseholdCalculatorInputs",
    "ResidentialHouseholdCalculatorResult",
    "ResidentialBessSystem",
    "ResidentialBillBreakdown",
    "ResidentialHouseholdDispatchInput",
    "ResidentialHouseholdDispatchResult",
    "ResidentialHouseholdDispatchRow",
    "ResidentialHouseholdInterval",
    "ResidentialMarketAccessResult",
    "ResidentialPublicDataSource",
    "ResidentialPublicReferenceHouseholdAssumptions",
    "ResidentialTariffPeriod",
    "ResidentialTariffSchedule",
    "ResidentialVPPEvent",
    "ResidentialVPPRevenue",
    "ResidentialVPPSchedule",
    "RevenueStreamEligibility",
    "UKResidentialMarketAccessAssumptions",
    "build_flat_public_reference_load_profile",
    "build_public_reference_tariff_schedule",
    "build_pvgis_hourly_url",
    "calculate_no_battery_bill",
    "calculate_residential_household_payback",
    "calculate_residential_household_payback_from_dispatch",
    "calculate_vpp_revenue",
    "evaluate_residential_market_access",
    "get_public_reference_household_assumptions",
    "get_residential_preset",
    "public_residential_data_sources",
    "residential_presets",
    "solve_residential_household_dispatch",
    "validate_household_intervals",
]
