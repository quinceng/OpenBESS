from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from gb_bess_revenue_stack.policies.information_set import InformationSet
from gb_bess_revenue_stack.schemas.base import ensure_aware_utc
from gb_bess_revenue_stack.schemas.market import WholesalePricePoint


class ForecastPoint(BaseModel):
    """Forecast value and trace metadata for one target interval."""

    model_config = ConfigDict(extra="forbid")

    forecast_created_at_utc: datetime
    target_start_utc: datetime
    target_end_utc: datetime
    forecast_value_gbp_per_mwh: float
    source_model: str
    training_start_utc: datetime | None = None
    training_end_utc: datetime | None = None
    training_row_count: int = Field(ge=0)
    source_data_hash: str
    is_oracle: bool = False

    @field_validator("forecast_created_at_utc", "target_start_utc", "target_end_utc")
    @classmethod
    def datetimes_are_aware(cls, value: datetime) -> datetime:
        return ensure_aware_utc(value)


class ForecastResult(BaseModel):
    """Forecast output for a rolling solve window."""

    model_config = ConfigDict(extra="forbid")

    points: list[ForecastPoint]
    source_model: str
    source_data_hash: str


class ForecastModel(Protocol):
    source_model: str

    def predict(
        self,
        information_set: InformationSet,
        *,
        target_periods: list[WholesalePricePoint],
    ) -> ForecastResult:
        """Forecast target prices from the information set."""


class OracleForecast:
    """Diagnostic forecast that uses realised future prices."""

    source_model = "oracle_diagnostic"

    def predict(
        self,
        information_set: InformationSet,
        *,
        target_periods: list[WholesalePricePoint],
    ) -> ForecastResult:
        points = [
            ForecastPoint(
                forecast_created_at_utc=information_set.decision_time_utc,
                target_start_utc=target.delivery_start_utc,
                target_end_utc=target.delivery_end_utc,
                forecast_value_gbp_per_mwh=target.price_gbp_per_mwh,
                source_model=self.source_model,
                training_row_count=len(information_set.known_prices),
                source_data_hash=information_set.source_data_hash,
                is_oracle=True,
            )
            for target in target_periods
        ]
        return ForecastResult(
            points=points,
            source_model=self.source_model,
            source_data_hash=information_set.source_data_hash,
        )


class PreviousDaySamePeriodForecast:
    """Use the last known observation from the same settlement period."""

    source_model = "previous_day_same_period"

    def predict(
        self,
        information_set: InformationSet,
        *,
        target_periods: list[WholesalePricePoint],
    ) -> ForecastResult:
        points = [self._forecast_one(information_set, target) for target in target_periods]
        return ForecastResult(
            points=points,
            source_model=self.source_model,
            source_data_hash=information_set.source_data_hash,
        )

    def _forecast_one(
        self,
        information_set: InformationSet,
        target: WholesalePricePoint,
    ) -> ForecastPoint:
        candidates = [
            point
            for point in information_set.known_prices
            if point.settlement_period == target.settlement_period
            and point.delivery_start_utc < target.delivery_start_utc
        ]
        selected = candidates[-1:] or information_set.known_prices[-1:]
        value = selected[0].price_gbp_per_mwh if selected else 0.0
        return _forecast_point(
            information_set=information_set,
            target=target,
            value=value,
            source_model=self.source_model,
            training_rows=selected,
        )


class TrailingMeanBySettlementPeriodForecast:
    """Mean price by settlement period over a trailing window."""

    def __init__(self, *, lookback_days: int) -> None:
        if lookback_days <= 0:
            msg = "lookback_days must be positive."
            raise ValueError(msg)
        self.lookback_days = lookback_days
        self.source_model = f"trailing_{lookback_days}_day_mean_by_settlement_period"

    def predict(
        self,
        information_set: InformationSet,
        *,
        target_periods: list[WholesalePricePoint],
    ) -> ForecastResult:
        by_period: dict[int, list[WholesalePricePoint]] = defaultdict(list)
        threshold = information_set.decision_time_utc - timedelta(days=self.lookback_days)
        for point in information_set.known_prices:
            if point.delivery_start_utc >= threshold:
                by_period[point.settlement_period].append(point)
        points = [
            self._forecast_one(information_set, target, by_period) for target in target_periods
        ]
        return ForecastResult(
            points=points,
            source_model=self.source_model,
            source_data_hash=information_set.source_data_hash,
        )

    def _forecast_one(
        self,
        information_set: InformationSet,
        target: WholesalePricePoint,
        by_period: dict[int, list[WholesalePricePoint]],
    ) -> ForecastPoint:
        training_rows = by_period.get(target.settlement_period, [])
        if training_rows:
            value = sum(point.price_gbp_per_mwh for point in training_rows) / len(training_rows)
        elif information_set.known_prices:
            value = information_set.known_prices[-1].price_gbp_per_mwh
            training_rows = [information_set.known_prices[-1]]
        else:
            value = 0.0
        return _forecast_point(
            information_set=information_set,
            target=target,
            value=value,
            source_model=self.source_model,
            training_rows=training_rows,
        )


def _forecast_point(
    *,
    information_set: InformationSet,
    target: WholesalePricePoint,
    value: float,
    source_model: str,
    training_rows: list[WholesalePricePoint],
) -> ForecastPoint:
    starts = [row.delivery_start_utc for row in training_rows]
    return ForecastPoint(
        forecast_created_at_utc=information_set.decision_time_utc,
        target_start_utc=target.delivery_start_utc,
        target_end_utc=target.delivery_end_utc,
        forecast_value_gbp_per_mwh=value,
        source_model=source_model,
        training_start_utc=min(starts) if starts else None,
        training_end_utc=max(starts) if starts else None,
        training_row_count=len(training_rows),
        source_data_hash=information_set.source_data_hash,
    )
