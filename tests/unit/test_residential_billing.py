from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from gb_bess_revenue_stack.residential import (
    ResidentialHouseholdInterval,
    ResidentialTariffPeriod,
    ResidentialTariffSchedule,
    calculate_no_battery_bill,
)

pytestmark = pytest.mark.unit


def _tariff() -> ResidentialTariffSchedule:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return ResidentialTariffSchedule(
        periods=(
            ResidentialTariffPeriod(
                valid_from_utc=start,
                valid_to_utc=start + timedelta(days=1),
                import_rate_gbp_per_kwh=0.30,
                export_rate_gbp_per_kwh=0.10,
                standing_charge_gbp_per_day=0.50,
            ),
        )
    )


def test_no_battery_bill_uses_pv_for_load_then_exports_surplus() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    row = ResidentialHouseholdInterval(
        delivery_start_utc=start,
        delivery_end_utc=start + timedelta(minutes=30),
        load_kwh=1.0,
        pv_generation_kwh=1.5,
    )

    result = calculate_no_battery_bill([row], tariff=_tariff(), export_limit_kw=3.68)

    assert result.import_kwh == pytest.approx(0)
    assert result.pv_to_load_kwh == pytest.approx(1.0)
    assert result.export_kwh == pytest.approx(0.5)
    assert result.energy_bill_gbp == pytest.approx(-0.05)
    assert result.standing_charge_gbp == pytest.approx(0.50 / 48)


def test_no_battery_bill_applies_export_limit_and_curtails_surplus() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    row = ResidentialHouseholdInterval(
        delivery_start_utc=start,
        delivery_end_utc=start + timedelta(minutes=30),
        load_kwh=0,
        pv_generation_kwh=10,
    )

    result = calculate_no_battery_bill([row], tariff=_tariff(), export_limit_kw=3.68)

    assert result.export_kwh == pytest.approx(1.84)
    assert result.pv_curtailed_kwh == pytest.approx(8.16)
