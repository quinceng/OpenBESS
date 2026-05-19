from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from gb_bess_revenue_stack.residential.profiles import (
    ResidentialHouseholdInterval,
    ResidentialTariffSchedule,
    validate_household_intervals,
)


class ResidentialBillBreakdown(BaseModel):
    """Household bill summary over a modelled interval."""

    model_config = ConfigDict(extra="forbid")

    import_kwh: float = Field(ge=0)
    export_kwh: float = Field(ge=0)
    pv_to_load_kwh: float = Field(ge=0)
    pv_curtailed_kwh: float = Field(ge=0)
    import_cost_gbp: float
    export_revenue_gbp: float
    energy_bill_gbp: float
    standing_charge_gbp: float = Field(ge=0)
    total_bill_gbp: float


def calculate_no_battery_bill(
    intervals: list[ResidentialHouseholdInterval],
    *,
    tariff: ResidentialTariffSchedule,
    export_limit_kw: float,
) -> ResidentialBillBreakdown:
    """Calculate household bill with PV but without a battery."""

    rows = validate_household_intervals(intervals, allow_empty_energy_profile=True)
    import_kwh = 0.0
    export_kwh = 0.0
    pv_to_load_kwh = 0.0
    pv_curtailed_kwh = 0.0
    import_cost = 0.0
    export_revenue = 0.0
    standing_charge = 0.0
    for row in rows:
        rate = tariff.rate_for(row.delivery_start_utc)
        direct_pv = min(row.load_kwh, row.pv_generation_kwh)
        residual_load = row.load_kwh - direct_pv
        surplus_pv = row.pv_generation_kwh - direct_pv
        export_cap_kwh = export_limit_kw * row.duration_h
        exported = min(surplus_pv, export_cap_kwh)
        curtailed = surplus_pv - exported
        import_kwh += residual_load
        export_kwh += exported
        pv_to_load_kwh += direct_pv
        pv_curtailed_kwh += curtailed
        import_cost += residual_load * rate.import_rate_gbp_per_kwh
        export_revenue += exported * rate.export_rate_gbp_per_kwh
        standing_charge += rate.standing_charge_gbp_per_day * row.duration_h / 24
    energy_bill = import_cost - export_revenue
    return ResidentialBillBreakdown(
        import_kwh=import_kwh,
        export_kwh=export_kwh,
        pv_to_load_kwh=pv_to_load_kwh,
        pv_curtailed_kwh=pv_curtailed_kwh,
        import_cost_gbp=import_cost,
        export_revenue_gbp=export_revenue,
        energy_bill_gbp=energy_bill,
        standing_charge_gbp=standing_charge,
        total_bill_gbp=energy_bill + standing_charge,
    )
