from __future__ import annotations


def revenue_gbp(price_gbp_per_mwh: float, net_export_mw: float, duration_h: float) -> float:
    """Energy revenue in GBP from GBP/MWh, MW and hours."""

    if duration_h <= 0:
        msg = "duration_h must be positive."
        raise ValueError(msg)
    return price_gbp_per_mwh * net_export_mw * duration_h
