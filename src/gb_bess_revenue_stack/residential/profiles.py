from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from gb_bess_revenue_stack.schemas.base import ensure_aware_utc


class ResidentialHouseholdInterval(BaseModel):
    """One household modelling interval using kWh energy quantities."""

    model_config = ConfigDict(extra="forbid")

    delivery_start_utc: datetime
    delivery_end_utc: datetime
    load_kwh: float = Field(ge=0)
    pv_generation_kwh: float = Field(default=0, ge=0)

    @field_validator("delivery_start_utc", "delivery_end_utc")
    @classmethod
    def datetimes_are_aware(cls, value: datetime) -> datetime:
        return ensure_aware_utc(value)

    @model_validator(mode="after")
    def end_after_start(self) -> ResidentialHouseholdInterval:
        if self.delivery_end_utc <= self.delivery_start_utc:
            msg = "delivery_end_utc must be after delivery_start_utc."
            raise ValueError(msg)
        return self

    @property
    def duration_h(self) -> float:
        return (self.delivery_end_utc - self.delivery_start_utc).total_seconds() / 3600


class ResidentialTariffPeriod(BaseModel):
    """Retail import/export tariff active over a UTC interval."""

    model_config = ConfigDict(extra="forbid")

    valid_from_utc: datetime
    valid_to_utc: datetime
    import_rate_gbp_per_kwh: float
    export_rate_gbp_per_kwh: float
    standing_charge_gbp_per_day: float = Field(default=0, ge=0)

    @field_validator("valid_from_utc", "valid_to_utc")
    @classmethod
    def datetimes_are_aware(cls, value: datetime) -> datetime:
        return ensure_aware_utc(value)

    @model_validator(mode="after")
    def end_after_start(self) -> ResidentialTariffPeriod:
        if self.valid_to_utc <= self.valid_from_utc:
            msg = "valid_to_utc must be after valid_from_utc."
            raise ValueError(msg)
        return self


class ResidentialTariffSchedule(BaseModel):
    """Retail tariff schedule with explicit interval lookup."""

    model_config = ConfigDict(extra="forbid")

    periods: tuple[ResidentialTariffPeriod, ...]

    def rate_for(self, timestamp_utc: datetime) -> ResidentialTariffPeriod:
        timestamp_utc = ensure_aware_utc(timestamp_utc)
        for period in self.periods:
            if period.valid_from_utc <= timestamp_utc < period.valid_to_utc:
                return period
        msg = f"No residential tariff period covers {timestamp_utc.isoformat()}."
        raise KeyError(msg)


def validate_household_intervals(
    rows: list[ResidentialHouseholdInterval],
    *,
    allow_empty_energy_profile: bool = False,
) -> list[ResidentialHouseholdInterval]:
    """Sort and validate household intervals for contiguous simulation."""

    if not rows:
        msg = "At least one residential household interval is required."
        raise ValueError(msg)
    ordered = sorted(rows, key=lambda row: row.delivery_start_utc)
    starts = [row.delivery_start_utc for row in ordered]
    if len(starts) != len(set(starts)):
        msg = "Household intervals contain duplicate delivery_start_utc values."
        raise ValueError(msg)
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if previous.delivery_end_utc != current.delivery_start_utc:
            msg = "Household intervals must be contiguous."
            raise ValueError(msg)
    if (
        not allow_empty_energy_profile
        and sum(row.load_kwh + row.pv_generation_kwh for row in ordered) == 0
    ):
        msg = "Household intervals contain no load or PV energy."
        raise ValueError(msg)
    return ordered
