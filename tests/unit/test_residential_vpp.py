from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from gb_bess_revenue_stack.residential import (
    ResidentialVPPEvent,
    ResidentialVPPSchedule,
    calculate_vpp_revenue,
)

pytestmark = pytest.mark.unit


def test_vpp_fixed_payment_is_prorated_to_sample_hours() -> None:
    schedule = ResidentialVPPSchedule(
        annual_fixed_payment_gbp=120,
        events=(),
    )

    result = calculate_vpp_revenue(schedule, sample_hours=720, delivered_event_kwh={})

    assert result.fixed_payment_gbp == pytest.approx(120 * 720 / 8760)
    assert result.event_payment_gbp == pytest.approx(0)


def test_vpp_event_payment_requires_delivered_energy() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    schedule = ResidentialVPPSchedule(
        annual_fixed_payment_gbp=0,
        events=(
            ResidentialVPPEvent(
                event_id="winter-evening-1",
                event_start_utc=start,
                event_end_utc=start + timedelta(hours=1),
                payment_gbp_per_kwh=2,
                required_export_kwh=1.5,
            ),
        ),
    )

    result = calculate_vpp_revenue(
        schedule,
        sample_hours=1,
        delivered_event_kwh={"winter-evening-1": 1.0},
    )

    assert result.event_payment_gbp == pytest.approx(2.0)
    assert result.shortfall_kwh == pytest.approx(0.5)
