"""Residential BESS modelling branch.

This namespace is intentionally separate from the utility-scale market-stack
optimiser. Residential models use household-scale kW/kWh assumptions and UK
market-access rules that should not be mixed into the central commercial model.
"""

from gb_bess_revenue_stack.residential.models import (
    ResidentialBessSystem,
    ResidentialMarketAccessResult,
    RevenueStreamEligibility,
    UKResidentialMarketAccessAssumptions,
    evaluate_residential_market_access,
    get_residential_preset,
    residential_presets,
)

__all__ = [
    "ResidentialBessSystem",
    "ResidentialMarketAccessResult",
    "RevenueStreamEligibility",
    "UKResidentialMarketAccessAssumptions",
    "evaluate_residential_market_access",
    "get_residential_preset",
    "residential_presets",
]
