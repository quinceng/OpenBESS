from __future__ import annotations

import hashlib
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from gb_bess_revenue_stack.schemas.base import ensure_aware_utc
from gb_bess_revenue_stack.schemas.market import WholesalePricePoint


class InformationSet(BaseModel):
    """Data available to a policy at one decision time."""

    model_config = ConfigDict(extra="forbid")

    decision_time_utc: datetime
    current_soc_mwh: float = Field(ge=0)
    known_prices: list[WholesalePricePoint]
    excluded_future_row_count: int
    source_data_hash: str

    @field_validator("decision_time_utc")
    @classmethod
    def decision_time_is_aware(cls, value: datetime) -> datetime:
        return ensure_aware_utc(value)


def build_information_set(
    *,
    decision_time_utc: datetime,
    all_prices: list[WholesalePricePoint],
    current_soc_mwh: float,
) -> InformationSet:
    """Filter source data to rows known at the decision time."""

    decision_time_utc = ensure_aware_utc(decision_time_utc)
    known: list[WholesalePricePoint] = []
    excluded = 0
    for point in all_prices:
        if point.known_at_utc <= decision_time_utc:
            known.append(point)
        else:
            excluded += 1
    known = sorted(known, key=lambda point: point.delivery_start_utc)
    return InformationSet(
        decision_time_utc=decision_time_utc,
        current_soc_mwh=current_soc_mwh,
        known_prices=known,
        excluded_future_row_count=excluded,
        source_data_hash=price_rows_hash(known),
    )


def price_rows_hash(prices: list[WholesalePricePoint]) -> str:
    payload = "|".join(
        f"{point.delivery_start_utc.isoformat()}:{point.settlement_period}:{point.price_gbp_per_mwh}"
        for point in prices
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
