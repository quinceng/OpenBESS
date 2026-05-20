from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal, cast

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from gb_bess_revenue_stack.schemas.base import ensure_aware_utc

StackSeriesBasis = Literal["rolling_policy", "perfect_foresight", "scenario"]
StackSeriesWindowLabel = Literal["7d", "30d", "90d", "ytd", "trailing_12m"]
STACK_SERIES_COLUMNS = [
    "timestamp_utc",
    "window_label",
    "asset_id",
    "basis",
    "wholesale_energy_gbp",
    "eac_availability_gbp",
    "degradation_cost_gbp",
    "cm_annual_scenario_gbp_per_mw_year",
    "caveat_flags",
    "gross_operating_value_gbp",
    "degradation_adjusted_value_gbp",
]


class StackSeriesRow(BaseModel):
    timestamp_utc: datetime
    window_label: StackSeriesWindowLabel
    asset_id: str
    basis: StackSeriesBasis
    wholesale_energy_gbp: float
    eac_availability_gbp: float
    degradation_cost_gbp: float = Field(default=0, ge=0)
    cm_annual_scenario_gbp_per_mw_year: float | None = Field(default=None, ge=0)
    caveat_flags: list[str]

    model_config = ConfigDict(extra="forbid")

    @field_validator("timestamp_utc")
    @classmethod
    def _timestamp_must_be_aware_utc(cls, value: datetime) -> datetime:
        return ensure_aware_utc(value)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def gross_operating_value_gbp(self) -> float:
        return self.wholesale_energy_gbp + self.eac_availability_gbp

    @computed_field  # type: ignore[prop-decorator]
    @property
    def degradation_adjusted_value_gbp(self) -> float:
        return self.gross_operating_value_gbp - self.degradation_cost_gbp


class StackWindowSpec(BaseModel):
    label: StackSeriesWindowLabel
    minimum_days: int = Field(gt=0)
    minimum_coverage_pct: float = Field(default=0.95, ge=0, le=1)
    annualisation_allowed: bool = False
    expected_period_basis: Literal["fixed_days", "calendar_ytd"] = "fixed_days"

    model_config = ConfigDict(extra="forbid")


class StackWindowEligibility(BaseModel):
    window_label: StackSeriesWindowLabel
    observed_period_count: int = Field(ge=0)
    expected_period_count: int = Field(gt=0)
    coverage_pct: float = Field(ge=0, le=1)
    eligible_for_annualisation: bool
    eligible_for_public_index: bool
    caveat_flags: list[str]

    model_config = ConfigDict(extra="forbid")


DEFAULT_STACK_WINDOWS: tuple[StackWindowSpec, ...] = (
    StackWindowSpec(label="7d", minimum_days=7, annualisation_allowed=False),
    StackWindowSpec(label="30d", minimum_days=30, annualisation_allowed=False),
    StackWindowSpec(label="90d", minimum_days=90, annualisation_allowed=True),
    StackWindowSpec(
        label="ytd",
        minimum_days=90,
        annualisation_allowed=True,
        expected_period_basis="calendar_ytd",
    ),
    StackWindowSpec(label="trailing_12m", minimum_days=365, annualisation_allowed=True),
)


def build_window_eligibility(
    observed_period_count: int,
    expected_period_count: int,
    window_label: str,
    minimum_coverage_pct: float = 0.95,
) -> StackWindowEligibility:
    if not 0 <= minimum_coverage_pct <= 1:
        msg = "minimum_coverage_pct must be between 0 and 1."
        raise ValueError(msg)
    if expected_period_count <= 0:
        msg = "expected_period_count must be greater than 0."
        raise ValueError(msg)
    if observed_period_count < 0:
        msg = "observed_period_count must be greater than or equal to 0."
        raise ValueError(msg)

    window_specs_by_label = {window.label: window for window in DEFAULT_STACK_WINDOWS}
    window_label_key = cast(StackSeriesWindowLabel, window_label)
    window_spec = window_specs_by_label.get(window_label_key)
    if window_spec is None:
        msg = f"Unknown stack window label: {window_label}"
        raise ValueError(msg)

    coverage_pct = min(1.0, observed_period_count / expected_period_count)
    effective_minimum_coverage_pct = max(minimum_coverage_pct, window_spec.minimum_coverage_pct)
    eligible = window_spec.annualisation_allowed and coverage_pct >= effective_minimum_coverage_pct
    caveat_flags = ["not_a_market_index"]
    if coverage_pct < 1.0:
        caveat_flags.append("partial_sample_annualised")

    return StackWindowEligibility(
        window_label=window_label_key,
        observed_period_count=observed_period_count,
        expected_period_count=expected_period_count,
        coverage_pct=coverage_pct,
        eligible_for_annualisation=eligible,
        eligible_for_public_index=eligible,
        caveat_flags=caveat_flags,
    )


def stack_rows_to_dataframe(rows: list[StackSeriesRow]) -> pd.DataFrame:
    return pd.DataFrame(
        [row.model_dump(mode="json") for row in rows],
        columns=STACK_SERIES_COLUMNS,
    )


def write_stack_series(rows: list[StackSeriesRow], output_dir: str | Path) -> dict[str, Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    frame = stack_rows_to_dataframe(rows)
    parquet_path = output_path / "stack_series.parquet"
    csv_path = output_path / "stack_series.csv"

    csv_frame = frame.copy()
    csv_frame["caveat_flags"] = csv_frame["caveat_flags"].map(json.dumps)

    frame.to_parquet(parquet_path, index=False)
    csv_frame.to_csv(csv_path, index=False)

    return {"parquet": parquet_path, "csv": csv_path}
