from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator, model_validator

from gb_bess_revenue_stack.schemas.base import ProvenanceFields, ensure_aware_utc

GB_TZ = ZoneInfo("Europe/London")


class SettlementPeriodIndex(ProvenanceFields):
    """Canonical settlement-period interval with UTC as the source of truth."""

    delivery_start_utc: datetime
    delivery_end_utc: datetime
    timestamp_local: str
    settlement_date: str
    settlement_period: int = Field(ge=1, le=50)
    duration_h: float = Field(gt=0)
    known_at_utc: datetime

    @field_validator("delivery_start_utc", "delivery_end_utc", "known_at_utc", "retrieved_at_utc")
    @classmethod
    def datetimes_are_aware_utc(cls, value: datetime) -> datetime:
        return ensure_aware_utc(value)

    @model_validator(mode="after")
    def end_after_start_and_duration_matches(self) -> SettlementPeriodIndex:
        if self.delivery_end_utc <= self.delivery_start_utc:
            msg = "delivery_end_utc must be after delivery_start_utc."
            raise ValueError(msg)
        actual = (self.delivery_end_utc - self.delivery_start_utc).total_seconds() / 3600
        if abs(actual - self.duration_h) > 1e-9:
            msg = "duration_h must match delivery_start_utc/delivery_end_utc."
            raise ValueError(msg)
        return self


def settlement_periods_for_gb_date(settlement_day: date) -> list[SettlementPeriodIndex]:
    """Generate half-hour UTC intervals for a GB local settlement date."""

    local_start = datetime.combine(settlement_day, datetime.min.time(), tzinfo=GB_TZ)
    local_end = local_start + timedelta(days=1)
    cursor = local_start.astimezone(UTC)
    utc_end = local_end.astimezone(UTC)
    periods: list[SettlementPeriodIndex] = []
    period = 1
    while cursor < utc_end:
        delivery_end = cursor + timedelta(minutes=30)
        periods.append(
            SettlementPeriodIndex(
                delivery_start_utc=cursor,
                delivery_end_utc=delivery_end,
                timestamp_local=cursor.astimezone(GB_TZ).isoformat(),
                settlement_date=settlement_day.isoformat(),
                settlement_period=period,
                duration_h=0.5,
                known_at_utc=delivery_end,
                retrieved_at_utc=delivery_end,
                source_id="PROJECT_CONVENTION",
                source_url="docs/implementation_conventions.md",
                schema_version="0.1.0",
                quality_flag="ok",
            )
        )
        cursor = delivery_end
        period += 1
    return periods
