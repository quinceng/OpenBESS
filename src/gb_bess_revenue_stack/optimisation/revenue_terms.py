from __future__ import annotations

from gb_bess_revenue_stack.markets.eac_prices import EACPriceMatrix, empty_eac_price_matrix


def eac_availability_revenue_gbp(
    *,
    price_gbp_per_mw_h: float,
    committed_mw: float,
    duration_h: float,
) -> float:
    """Availability revenue in GBP; efficiency is not applied to price."""

    return price_gbp_per_mw_h * committed_mw * duration_h


__all__ = ["EACPriceMatrix", "eac_availability_revenue_gbp", "empty_eac_price_matrix"]
