from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from gb_bess_revenue_stack.schemas.base import ensure_aware_utc
from gb_bess_revenue_stack.schemas.market import (
    DirectionModelLabel,
    EACAuctionResult,
    WholesalePricePoint,
)

AvailabilityState = Literal[
    "available",
    "source_gap",
    "not_known_at_decision_time",
    "not_procured",
]
BlockCommitmentRule = Literal["none", "constant_within_block"]


class EACPriceCell(BaseModel):
    """EAC availability price and provenance for one product-period pair."""

    model_config = ConfigDict(extra="forbid")

    product_model_label: str
    direction_model_label: DirectionModelLabel
    period_index: int
    price_gbp_per_mw_h: float | None
    availability_state: AvailabilityState
    service_duration_h: float
    product_source_label: str | None = None
    direction_source_label: str | None = None
    known_at_utc: datetime | None = None
    source_record_id: str | None = None
    source_id: str | None = None
    source_url: str | None = None
    procured_mw: float | None = None
    block_id: str | None = None
    block_commitment_rule: BlockCommitmentRule = "none"
    modelling_caveat: str = "price-taking EAC availability proxy"

    @field_validator("known_at_utc")
    @classmethod
    def known_at_is_aware(cls, value: datetime | None) -> datetime | None:
        return ensure_aware_utc(value) if value is not None else None


class EACPriceMatrix(BaseModel):
    """Product-by-period EAC price matrix with explicit missing-data states."""

    model_config = ConfigDict(extra="forbid")

    cells: list[EACPriceCell]

    def cell(self, *, product_model_label: str, period_index: int) -> EACPriceCell:
        for cell in self.cells:
            if (
                cell.product_model_label == product_model_label
                and cell.period_index == period_index
            ):
                return cell
        msg = f"No EAC price cell for {product_model_label!r} at period {period_index}."
        raise KeyError(msg)

    def available_cells_for_period(self, period_index: int) -> list[EACPriceCell]:
        return [
            cell
            for cell in self.cells
            if cell.period_index == period_index and cell.availability_state == "available"
        ]

    @property
    def has_services(self) -> bool:
        return any(cell.availability_state == "available" for cell in self.cells)

    @property
    def product_model_labels(self) -> list[str]:
        return sorted({cell.product_model_label for cell in self.cells})


def build_eac_price_matrix(
    *,
    records: list[EACAuctionResult],
    target_periods: list[WholesalePricePoint],
    decision_time_utc: datetime | None = None,
    product_model_labels: list[str] | None = None,
) -> EACPriceMatrix:
    """Align canonical EAC records to dispatch periods without zero-filling gaps."""

    if decision_time_utc is not None:
        decision_time_utc = ensure_aware_utc(decision_time_utc)
    labels = product_model_labels or sorted({record.product_model_label for record in records})
    cells: list[EACPriceCell] = []
    for product_label in labels:
        for period_index, period in enumerate(target_periods):
            candidates = [
                record
                for record in records
                if record.product_model_label == product_label
                and _record_covers_period(record, period)
            ]
            if not candidates:
                cells.append(_missing_cell(product_label, period_index, "source_gap"))
                continue
            record = candidates[0]
            if decision_time_utc is not None and record.known_at_utc > decision_time_utc:
                cells.append(
                    _missing_cell(product_label, period_index, "not_known_at_decision_time")
                )
                continue
            if _is_not_procured(record):
                cells.append(_not_procured_cell(record, period_index))
                continue
            cells.append(_available_cell(record, period_index))
    return EACPriceMatrix(cells=cells)


def empty_eac_price_matrix() -> EACPriceMatrix:
    return EACPriceMatrix(cells=[])


def synthetic_single_service_matrix(
    *,
    product_model_label: str,
    direction_model_label: DirectionModelLabel,
    price_gbp_per_mw_h: float,
    duration_h: float,
    product_source_label: str | None = None,
    modelling_caveat: str = "synthetic price-taking EAC availability proxy",
) -> EACPriceMatrix:
    """Build a one-period synthetic EAC matrix for focused optimisation tests."""

    return synthetic_service_matrix(
        product_model_label=product_model_label,
        direction_model_label=direction_model_label,
        prices_gbp_per_mw_h=[price_gbp_per_mw_h],
        duration_h=duration_h,
        product_source_label=product_source_label,
        modelling_caveat=modelling_caveat,
    )


def synthetic_service_matrix(
    *,
    product_model_label: str,
    direction_model_label: DirectionModelLabel,
    prices_gbp_per_mw_h: list[float],
    duration_h: float,
    product_source_label: str | None = None,
    block_id: str | None = None,
    block_commitment_rule: BlockCommitmentRule = "none",
    modelling_caveat: str = "synthetic price-taking EAC availability proxy",
) -> EACPriceMatrix:
    """Build a synthetic service matrix over contiguous test periods."""

    return EACPriceMatrix(
        cells=[
            EACPriceCell(
                product_source_label=product_source_label,
                product_model_label=product_model_label,
                direction_source_label=product_source_label,
                direction_model_label=direction_model_label,
                period_index=index,
                price_gbp_per_mw_h=price,
                availability_state="available",
                service_duration_h=duration_h,
                procured_mw=None,
                block_id=block_id,
                block_commitment_rule=block_commitment_rule,
                modelling_caveat=modelling_caveat,
            )
            for index, price in enumerate(prices_gbp_per_mw_h)
        ]
    )


def _record_covers_period(record: EACAuctionResult, period: WholesalePricePoint) -> bool:
    return (
        record.delivery_start_utc <= period.delivery_start_utc
        and record.delivery_end_utc >= period.delivery_end_utc
    )


def _is_not_procured(record: EACAuctionResult) -> bool:
    return record.procured_mw == 0 or record.accepted_mw == 0


def _available_cell(record: EACAuctionResult, period_index: int) -> EACPriceCell:
    return EACPriceCell(
        product_source_label=record.product_source_label,
        product_model_label=record.product_model_label,
        direction_source_label=record.direction_source_label,
        direction_model_label=record.direction_model_label,
        period_index=period_index,
        price_gbp_per_mw_h=record.clearing_price_gbp_per_mw_h,
        availability_state="available",
        known_at_utc=record.known_at_utc,
        source_record_id=record.source_record_id,
        source_id=record.source_id,
        source_url=record.source_url,
        procured_mw=record.procured_mw,
        block_id=record.block_id,
        block_commitment_rule="constant_within_block" if record.block_id else "none",
        service_duration_h=_duration_hours(record),
    )


def _not_procured_cell(record: EACAuctionResult, period_index: int) -> EACPriceCell:
    return EACPriceCell(
        product_source_label=record.product_source_label,
        product_model_label=record.product_model_label,
        direction_source_label=record.direction_source_label,
        direction_model_label=record.direction_model_label,
        period_index=period_index,
        price_gbp_per_mw_h=None,
        availability_state="not_procured",
        known_at_utc=record.known_at_utc,
        source_record_id=record.source_record_id,
        source_id=record.source_id,
        source_url=record.source_url,
        procured_mw=record.procured_mw,
        block_id=record.block_id,
        block_commitment_rule="constant_within_block" if record.block_id else "none",
        service_duration_h=_duration_hours(record),
    )


def _missing_cell(
    product_model_label: str,
    period_index: int,
    state: AvailabilityState,
) -> EACPriceCell:
    return EACPriceCell(
        product_model_label=product_model_label,
        direction_model_label="unknown",
        period_index=period_index,
        price_gbp_per_mw_h=None,
        availability_state=state,
        service_duration_h=0.5,
    )


def _duration_hours(record: EACAuctionResult) -> float:
    return (record.delivery_end_utc - record.delivery_start_utc).total_seconds() / 3600
