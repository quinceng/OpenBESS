from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from gb_bess_revenue_stack.residential import (
    ResidentialBessSystem,
    ResidentialHouseholdDispatchInput,
    ResidentialHouseholdInterval,
    ResidentialTariffPeriod,
    ResidentialTariffSchedule,
    solve_residential_household_dispatch,
)

pytestmark = pytest.mark.unit


def _system() -> ResidentialBessSystem:
    return ResidentialBessSystem(
        name="household-test",
        battery_capacity_kwh=4,
        inverter_power_kw=2,
        has_integrated_inverter=True,
        battery_cost_gbp=3_000,
        installation_cost_gbp=500,
    )


def _tariff() -> ResidentialTariffSchedule:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return ResidentialTariffSchedule(
        periods=(
            ResidentialTariffPeriod(
                valid_from_utc=start,
                valid_to_utc=start + timedelta(minutes=30),
                import_rate_gbp_per_kwh=0.10,
                export_rate_gbp_per_kwh=0.05,
            ),
            ResidentialTariffPeriod(
                valid_from_utc=start + timedelta(minutes=30),
                valid_to_utc=start + timedelta(hours=1),
                import_rate_gbp_per_kwh=0.40,
                export_rate_gbp_per_kwh=0.05,
            ),
        )
    )


def test_dispatch_charges_from_grid_when_off_peak_and_grid_charging_allowed() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    intervals = [
        ResidentialHouseholdInterval(
            delivery_start_utc=start,
            delivery_end_utc=start + timedelta(minutes=30),
            load_kwh=0,
            pv_generation_kwh=0,
        ),
        ResidentialHouseholdInterval(
            delivery_start_utc=start + timedelta(minutes=30),
            delivery_end_utc=start + timedelta(hours=1),
            load_kwh=1,
            pv_generation_kwh=0,
        ),
    ]
    result = solve_residential_household_dispatch(
        ResidentialHouseholdDispatchInput(
            system=_system(),
            intervals=intervals,
            tariff=_tariff(),
            dno_export_limit_kw=3.68,
            initial_soc_kwh=0,
            terminal_soc_policy="free",
            round_trip_efficiency=1,
            allow_grid_charging=True,
        )
    )

    assert result.rows[0].grid_to_battery_kwh > 0
    assert result.rows[1].battery_to_load_kwh == pytest.approx(1)
    assert result.battery_bill.energy_bill_gbp < result.no_battery_bill.energy_bill_gbp


def test_dispatch_respects_export_limit_for_pv_and_battery_export() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    intervals = [
        ResidentialHouseholdInterval(
            delivery_start_utc=start,
            delivery_end_utc=start + timedelta(minutes=30),
            load_kwh=0,
            pv_generation_kwh=8,
        )
    ]
    result = solve_residential_household_dispatch(
        ResidentialHouseholdDispatchInput(
            system=_system(),
            intervals=intervals,
            tariff=ResidentialTariffSchedule(
                periods=(
                    ResidentialTariffPeriod(
                        valid_from_utc=start,
                        valid_to_utc=start + timedelta(minutes=30),
                        import_rate_gbp_per_kwh=0.30,
                        export_rate_gbp_per_kwh=0.20,
                    ),
                )
            ),
            dno_export_limit_kw=3.68,
            initial_soc_kwh=0,
            terminal_soc_policy="free",
            round_trip_efficiency=1,
            allow_grid_charging=False,
        )
    )

    assert result.rows[0].site_export_kwh <= 1.84 + 1e-9
    assert result.rows[0].pv_curtailed_kwh > 0


def test_grid_charged_energy_cannot_be_exported_when_disabled() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    intervals = [
        ResidentialHouseholdInterval(
            delivery_start_utc=start,
            delivery_end_utc=start + timedelta(minutes=30),
            load_kwh=0,
            pv_generation_kwh=0,
        ),
        ResidentialHouseholdInterval(
            delivery_start_utc=start + timedelta(minutes=30),
            delivery_end_utc=start + timedelta(hours=1),
            load_kwh=0,
            pv_generation_kwh=0,
        ),
    ]
    tariff = ResidentialTariffSchedule(
        periods=(
            ResidentialTariffPeriod(
                valid_from_utc=start,
                valid_to_utc=start + timedelta(minutes=30),
                import_rate_gbp_per_kwh=0.01,
                export_rate_gbp_per_kwh=0.00,
            ),
            ResidentialTariffPeriod(
                valid_from_utc=start + timedelta(minutes=30),
                valid_to_utc=start + timedelta(hours=1),
                import_rate_gbp_per_kwh=0.01,
                export_rate_gbp_per_kwh=1.00,
            ),
        )
    )

    result = solve_residential_household_dispatch(
        ResidentialHouseholdDispatchInput(
            system=_system(),
            intervals=intervals,
            tariff=tariff,
            dno_export_limit_kw=3.68,
            initial_soc_kwh=0,
            terminal_soc_policy="free",
            round_trip_efficiency=1,
            allow_grid_charging=True,
            allow_grid_charged_export=False,
        )
    )

    assert sum(row.battery_to_export_kwh for row in result.rows) == pytest.approx(0)
