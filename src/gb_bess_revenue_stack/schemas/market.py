from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from gb_bess_revenue_stack.schemas.base import ProvenanceFields, StrictBaseModel, ensure_aware_utc

PriceSourceType = Literal["MID", "EPEX_LICENSED", "N2EX_LICENSED", "SYNTHETIC_TEST"]
DirectionModelLabel = Literal["upward", "downward", "both", "unknown"]


class IntervalRecord(ProvenanceFields):
    delivery_start_utc: datetime
    delivery_end_utc: datetime
    known_at_utc: datetime

    @field_validator("delivery_start_utc", "delivery_end_utc", "known_at_utc", "retrieved_at_utc")
    @classmethod
    def datetimes_are_aware_utc(cls, value: datetime) -> datetime:
        return ensure_aware_utc(value)

    @model_validator(mode="after")
    def end_after_start(self) -> IntervalRecord:
        if self.delivery_end_utc <= self.delivery_start_utc:
            msg = "delivery_end_utc must be after delivery_start_utc."
            raise ValueError(msg)
        return self


class WholesalePricePoint(IntervalRecord):
    """Canonical public wholesale-price proxy observation."""

    settlement_date: str
    settlement_period: int = Field(ge=1, le=50)
    duration_h: float = Field(gt=0)
    price_gbp_per_mwh: float
    price_source_type: PriceSourceType
    is_proxy: bool
    data_provider: str | None = None
    volume_mwh: float | None = None

    @model_validator(mode="after")
    def enforce_mid_proxy_and_duration(self) -> WholesalePricePoint:
        if self.price_source_type == "MID" and not self.is_proxy:
            msg = "MID wholesale records must be labelled as proxy observations."
            raise ValueError(msg)
        actual = (self.delivery_end_utc - self.delivery_start_utc).total_seconds() / 3600
        if abs(actual - self.duration_h) > 1e-9:
            msg = "duration_h must match delivery interval."
            raise ValueError(msg)
        return self


class EACAuctionResult(IntervalRecord):
    """Canonical EAC clearing-price and volume observation."""

    product_source_label: str
    product_model_label: str
    direction_source_label: str
    direction_model_label: DirectionModelLabel
    clearing_price_gbp_per_mw_h: float
    procured_mw: float | None = Field(default=None, ge=0)
    accepted_mw: float | None = Field(default=None, ge=0)
    block_id: str | None = None
    service_type: str | None = None


class CapacityMarketScenario(StrictBaseModel):
    """Capacity Market scenario value used by finance/revenue-stack layers."""

    scenario_name: str
    auction_type: str
    delivery_year: str
    clearing_price_gbp_per_kw_year: float = Field(ge=0)
    derating_factor: float = Field(ge=0, le=1)
    asset_duration_hours: float = Field(gt=0)
    contracted_mw_nameplate: float = Field(ge=0)
    contracted_mw_derated: float | None = Field(default=None, ge=0)
    source_id: str
    source_url: str
    source_date: str
    notes: str

    @model_validator(mode="after")
    def derive_or_check_derated_capacity(self) -> CapacityMarketScenario:
        expected = self.contracted_mw_nameplate * self.derating_factor
        if self.contracted_mw_derated is None:
            self.contracted_mw_derated = expected
        elif abs(self.contracted_mw_derated - expected) > 1e-9:
            msg = "contracted_mw_derated must equal contracted_mw_nameplate * derating_factor."
            raise ValueError(msg)
        return self
