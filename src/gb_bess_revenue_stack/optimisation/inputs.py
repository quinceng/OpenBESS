from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from gb_bess_revenue_stack.config.models import AssetConfig
from gb_bess_revenue_stack.schemas.base import ensure_aware_utc
from gb_bess_revenue_stack.schemas.market import WholesalePricePoint

TerminalSocPolicy = Literal["cyclic", "free", "target"]


class DispatchPeriod(BaseModel):
    """Single model timestep with explicit units."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    delivery_start_utc: datetime
    delivery_end_utc: datetime
    duration_h: float = Field(gt=0)
    price_gbp_per_mwh: float
    source_id: str
    price_source_type: str
    is_proxy: bool

    @field_validator("delivery_start_utc", "delivery_end_utc")
    @classmethod
    def datetime_is_aware(cls, value: datetime) -> datetime:
        return ensure_aware_utc(value)

    @model_validator(mode="after")
    def end_after_start(self) -> DispatchPeriod:
        if self.delivery_end_utc <= self.delivery_start_utc:
            msg = "delivery_end_utc must be after delivery_start_utc."
            raise ValueError(msg)
        return self


class DispatchInput(BaseModel):
    """Validated energy-only optimisation input."""

    model_config = ConfigDict(extra="forbid")

    periods: list[DispatchPeriod] = Field(min_length=1)
    asset_name: str
    p_export_max_mw: float = Field(gt=0)
    p_import_max_mw: float = Field(gt=0)
    energy_capacity_mwh: float = Field(gt=0)
    soc_min_mwh: float = Field(ge=0)
    soc_max_mwh: float = Field(gt=0)
    eta_charge: float = Field(gt=0, le=1)
    eta_discharge: float = Field(gt=0, le=1)
    initial_soc_mwh: float = Field(ge=0)
    terminal_soc_policy: TerminalSocPolicy = "cyclic"
    terminal_soc_target_mwh: float | None = Field(default=None, ge=0)
    binary_dispatch: bool = True
    data_manifest_ref: str | None = None
    config_hash: str | None = None

    @property
    def period_count(self) -> int:
        return len(self.periods)

    @property
    def sample_hours(self) -> float:
        return sum(period.duration_h for period in self.periods)

    @model_validator(mode="after")
    def validate_soc_and_ordering(self) -> DispatchInput:
        if self.soc_min_mwh >= self.soc_max_mwh:
            msg = "soc_min_mwh must be below soc_max_mwh."
            raise ValueError(msg)
        if not self.soc_min_mwh <= self.initial_soc_mwh <= self.soc_max_mwh:
            msg = "initial_soc_mwh must be within SoC bounds."
            raise ValueError(msg)
        if self.terminal_soc_policy == "target":
            if self.terminal_soc_target_mwh is None:
                msg = "terminal_soc_target_mwh is required when terminal_soc_policy='target'."
                raise ValueError(msg)
            if not self.soc_min_mwh <= self.terminal_soc_target_mwh <= self.soc_max_mwh:
                msg = "terminal_soc_target_mwh must be within SoC bounds."
                raise ValueError(msg)
        starts = [period.delivery_start_utc for period in self.periods]
        if starts != sorted(starts):
            msg = "Dispatch periods must be ordered by delivery_start_utc."
            raise ValueError(msg)
        if len(starts) != len(set(starts)):
            msg = "Dispatch periods contain duplicate delivery_start_utc values."
            raise ValueError(msg)
        return self


def build_dispatch_input(
    prices: list[WholesalePricePoint],
    *,
    asset: AssetConfig,
    initial_soc_mwh: float,
    terminal_soc_policy: TerminalSocPolicy = "cyclic",
    terminal_soc_target_mwh: float | None = None,
    binary_dispatch: bool = True,
    data_manifest_ref: str | None = None,
    config_hash: str | None = None,
) -> DispatchInput:
    """Convert canonical wholesale prices into deterministic dispatch input."""

    if not prices:
        msg = "At least one price point is required."
        raise ValueError(msg)
    sorted_prices = sorted(prices, key=lambda point: point.delivery_start_utc)
    eta_charge = asset.eta_charge
    eta_discharge = asset.eta_discharge
    soc_max = asset.soc_max_mwh
    if eta_charge is None or eta_discharge is None or soc_max is None:
        msg = "AssetConfig did not derive efficiency or SoC bounds."
        raise ValueError(msg)
    periods = [
        DispatchPeriod(
            index=index,
            delivery_start_utc=point.delivery_start_utc,
            delivery_end_utc=point.delivery_end_utc,
            duration_h=point.duration_h,
            price_gbp_per_mwh=point.price_gbp_per_mwh,
            source_id=point.source_id,
            price_source_type=point.price_source_type,
            is_proxy=point.is_proxy,
        )
        for index, point in enumerate(sorted_prices)
    ]
    return DispatchInput(
        periods=periods,
        asset_name=asset.name,
        p_export_max_mw=asset.power_mw,
        p_import_max_mw=asset.power_mw,
        energy_capacity_mwh=asset.energy_capacity_mwh,
        soc_min_mwh=asset.soc_min_mwh,
        soc_max_mwh=soc_max,
        eta_charge=eta_charge,
        eta_discharge=eta_discharge,
        initial_soc_mwh=initial_soc_mwh,
        terminal_soc_policy=terminal_soc_policy,
        terminal_soc_target_mwh=terminal_soc_target_mwh,
        binary_dispatch=binary_dispatch,
        data_manifest_ref=data_manifest_ref,
        config_hash=config_hash,
    )
