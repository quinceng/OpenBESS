from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from gb_bess_revenue_stack.schemas.base import ensure_aware_utc


class ResidentialVPPEvent(BaseModel):
    """One optional household VPP export/support event."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_start_utc: datetime
    event_end_utc: datetime
    payment_gbp_per_kwh: float = Field(ge=0)
    required_export_kwh: float = Field(default=0, ge=0)
    min_soc_kwh_at_start: float = Field(default=0, ge=0)

    @field_validator("event_start_utc", "event_end_utc")
    @classmethod
    def datetimes_are_aware(cls, value: datetime) -> datetime:
        return ensure_aware_utc(value)

    @model_validator(mode="after")
    def end_after_start(self) -> ResidentialVPPEvent:
        if self.event_end_utc <= self.event_start_utc:
            msg = "event_end_utc must be after event_start_utc."
            raise ValueError(msg)
        return self


class ResidentialVPPSchedule(BaseModel):
    """Fixed and event-linked residential VPP payment assumptions."""

    model_config = ConfigDict(extra="forbid")

    annual_fixed_payment_gbp: float = Field(default=0, ge=0)
    events: tuple[ResidentialVPPEvent, ...] = ()


class ResidentialVPPRevenue(BaseModel):
    """Residential VPP revenue over the modelled sample."""

    model_config = ConfigDict(extra="forbid")

    fixed_payment_gbp: float = Field(ge=0)
    event_payment_gbp: float = Field(ge=0)
    total_vpp_revenue_gbp: float = Field(ge=0)
    delivered_event_kwh: float = Field(ge=0)
    shortfall_kwh: float = Field(ge=0)


def calculate_vpp_revenue(
    schedule: ResidentialVPPSchedule,
    *,
    sample_hours: float,
    delivered_event_kwh: dict[str, float],
) -> ResidentialVPPRevenue:
    """Calculate prorated fixed and delivered-event VPP revenue."""

    if sample_hours < 0:
        msg = "sample_hours must be non-negative."
        raise ValueError(msg)
    fixed = schedule.annual_fixed_payment_gbp * sample_hours / 8760
    event_payment = 0.0
    delivered_total = 0.0
    shortfall = 0.0
    for event in schedule.events:
        delivered = max(0.0, delivered_event_kwh.get(event.event_id, 0.0))
        delivered_total += delivered
        paid_kwh = (
            min(delivered, event.required_export_kwh) if event.required_export_kwh else delivered
        )
        event_payment += paid_kwh * event.payment_gbp_per_kwh
        shortfall += max(0.0, event.required_export_kwh - delivered)
    return ResidentialVPPRevenue(
        fixed_payment_gbp=fixed,
        event_payment_gbp=event_payment,
        total_vpp_revenue_gbp=fixed + event_payment,
        delivered_event_kwh=delivered_total,
        shortfall_kwh=shortfall,
    )
