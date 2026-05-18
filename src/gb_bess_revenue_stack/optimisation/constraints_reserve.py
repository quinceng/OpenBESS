from __future__ import annotations

from gb_bess_revenue_stack.config.models import AssetConfig


def upward_reserve_required_soc_mwh(
    *,
    reserve_mw: float,
    service_duration_h: float,
    asset: AssetConfig,
) -> float:
    """Stored MWh required to deliver upward reserve denominated as AC MW."""

    eta_discharge = asset.eta_discharge
    if eta_discharge is None:
        msg = "AssetConfig did not derive eta_discharge."
        raise ValueError(msg)
    return reserve_mw * service_duration_h / eta_discharge


def downward_reserve_required_footroom_mwh(
    *,
    reserve_mw: float,
    service_duration_h: float,
    asset: AssetConfig,
) -> float:
    """Empty battery capacity required to absorb downward reserve as AC MW."""

    eta_charge = asset.eta_charge
    if eta_charge is None:
        msg = "AssetConfig did not derive eta_charge."
        raise ValueError(msg)
    return reserve_mw * service_duration_h * eta_charge


def available_upward_reserve_mw(*, p_export_max_mw: float, discharge_mw: float) -> float:
    return max(0.0, p_export_max_mw - discharge_mw)


def available_downward_reserve_mw(*, p_import_max_mw: float, charge_mw: float) -> float:
    return max(0.0, p_import_max_mw - charge_mw)
