from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from math import ceil

import pandas as pd
import pytest
from pydantic import ValidationError

from gb_bess_revenue_stack.reporting.stack_series import (
    DEFAULT_STACK_WINDOWS,
    STACK_SERIES_COLUMNS,
    StackSeriesRow,
    build_window_eligibility,
    stack_rows_to_dataframe,
    write_stack_series,
)

pytestmark = pytest.mark.unit


def test_7d_partial_sample_is_not_eligible_and_has_caveats() -> None:
    eligibility = build_window_eligibility(
        observed_period_count=5,
        expected_period_count=7 * 48,
        window_label="7d",
    )

    assert eligibility.eligible_for_annualisation is False
    assert eligibility.eligible_for_public_index is False
    assert eligibility.caveat_flags == ["not_a_market_index", "partial_sample_annualised"]


def test_90d_full_coverage_is_eligible_without_partial_sample_caveat() -> None:
    expected_period_count = 90 * 48

    eligibility = build_window_eligibility(
        observed_period_count=expected_period_count,
        expected_period_count=expected_period_count,
        window_label="90d",
    )

    assert eligibility.coverage_pct == 1.0
    assert eligibility.eligible_for_annualisation is True
    assert eligibility.eligible_for_public_index is True
    assert eligibility.caveat_flags == ["not_a_market_index"]


def test_90d_partial_but_sufficient_coverage_is_eligible_with_partial_caveat() -> None:
    expected_period_count = 90 * 48

    eligibility = build_window_eligibility(
        observed_period_count=ceil(expected_period_count * 0.97),
        expected_period_count=expected_period_count,
        window_label="90d",
    )

    assert eligibility.coverage_pct >= 0.97
    assert eligibility.eligible_for_annualisation is True
    assert eligibility.eligible_for_public_index is True
    assert eligibility.caveat_flags == ["not_a_market_index", "partial_sample_annualised"]


def test_90d_caller_cannot_lower_spec_coverage_threshold() -> None:
    expected_period_count = 90 * 48

    eligibility = build_window_eligibility(
        observed_period_count=expected_period_count // 2,
        expected_period_count=expected_period_count,
        window_label="90d",
        minimum_coverage_pct=0.5,
    )

    assert eligibility.coverage_pct == 0.5
    assert eligibility.eligible_for_annualisation is False
    assert eligibility.eligible_for_public_index is False
    assert eligibility.caveat_flags == ["not_a_market_index", "partial_sample_annualised"]


def test_90d_caller_can_raise_coverage_threshold() -> None:
    expected_period_count = 90 * 48

    eligibility = build_window_eligibility(
        observed_period_count=ceil(expected_period_count * 0.97),
        expected_period_count=expected_period_count,
        window_label="90d",
        minimum_coverage_pct=0.98,
    )

    assert eligibility.eligible_for_annualisation is False
    assert eligibility.eligible_for_public_index is False
    assert eligibility.caveat_flags == ["not_a_market_index", "partial_sample_annualised"]


@pytest.mark.parametrize("minimum_coverage_pct", [-0.1, 1.1])
def test_invalid_minimum_coverage_pct_raise_value_error(minimum_coverage_pct: float) -> None:
    with pytest.raises(ValueError):
        build_window_eligibility(
            observed_period_count=90 * 48,
            expected_period_count=90 * 48,
            window_label="90d",
            minimum_coverage_pct=minimum_coverage_pct,
        )


def test_default_stack_window_order() -> None:
    assert [window.label for window in DEFAULT_STACK_WINDOWS] == [
        "7d",
        "30d",
        "90d",
        "ytd",
        "trailing_12m",
    ]


@pytest.mark.parametrize(
    ("observed_period_count", "expected_period_count", "window_label"),
    [
        (1, 0, "7d"),
        (-1, 7 * 48, "7d"),
        (1, 7 * 48, "unknown"),
    ],
)
def test_invalid_inputs_raise_value_error(
    observed_period_count: int,
    expected_period_count: int,
    window_label: str,
) -> None:
    with pytest.raises(ValueError):
        build_window_eligibility(
            observed_period_count=observed_period_count,
            expected_period_count=expected_period_count,
            window_label=window_label,
        )


def _stack_row(**overrides: object) -> StackSeriesRow:
    values = {
        "timestamp_utc": datetime(2026, 5, 1, 0, 0, tzinfo=UTC),
        "window_label": "90d",
        "asset_id": "asset-1",
        "basis": "rolling_policy",
        "wholesale_energy_gbp": 125.25,
        "eac_availability_gbp": 20.75,
        "degradation_cost_gbp": 11.0,
        "cm_annual_scenario_gbp_per_mw_year": None,
        "caveat_flags": ["not_a_market_index"],
    }
    values.update(overrides)
    return StackSeriesRow(**values)


def test_stack_series_row_calculates_gross_and_degradation_adjusted_value() -> None:
    row = _stack_row(
        wholesale_energy_gbp=100.0,
        eac_availability_gbp=15.5,
        degradation_cost_gbp=7.25,
    )

    assert row.gross_operating_value_gbp == 115.5
    assert row.degradation_adjusted_value_gbp == 108.25


def test_stack_series_row_rejects_negative_degradation_cost() -> None:
    with pytest.raises(ValidationError):
        _stack_row(degradation_cost_gbp=-0.01)


def test_stack_series_row_rejects_unknown_window_label() -> None:
    with pytest.raises(ValidationError):
        _stack_row(window_label="central")


def test_stack_series_row_rejects_negative_cm_sidecar() -> None:
    with pytest.raises(ValidationError):
        _stack_row(cm_annual_scenario_gbp_per_mw_year=-0.01)


def test_stack_series_row_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        _stack_row(timestamp_utc=datetime(2026, 5, 1, 0, 0))


def test_stack_series_row_normalises_aware_timestamp_to_utc() -> None:
    row = _stack_row(timestamp_utc=datetime(2026, 5, 1, 1, 0, tzinfo=timezone(timedelta(hours=1))))

    assert row.timestamp_utc == datetime(2026, 5, 1, 0, 0, tzinfo=UTC)


def test_cm_sidecar_does_not_enter_operating_value_calculations() -> None:
    row = _stack_row(
        wholesale_energy_gbp=100.0,
        eac_availability_gbp=50.0,
        degradation_cost_gbp=10.0,
        cm_annual_scenario_gbp_per_mw_year=100_000.0,
    )

    assert row.gross_operating_value_gbp == 150.0
    assert row.degradation_adjusted_value_gbp == 140.0


def test_stack_rows_to_dataframe_empty_rows_preserves_schema() -> None:
    frame = stack_rows_to_dataframe([])

    assert frame.empty
    assert list(frame.columns) == STACK_SERIES_COLUMNS


def test_stack_rows_to_dataframe_uses_stable_column_order_for_rows() -> None:
    frame = stack_rows_to_dataframe([_stack_row()])

    assert list(frame.columns) == STACK_SERIES_COLUMNS


def test_write_stack_series_empty_rows_preserves_schema(tmp_path) -> None:
    paths = write_stack_series([], tmp_path)

    csv_frame = pd.read_csv(paths["csv"])
    parquet_frame = pd.read_parquet(paths["parquet"])

    assert csv_frame.empty
    assert parquet_frame.empty
    assert list(csv_frame.columns) == STACK_SERIES_COLUMNS
    assert list(parquet_frame.columns) == STACK_SERIES_COLUMNS


def test_write_stack_series_emits_csv_and_parquet_from_same_dataframe(tmp_path) -> None:
    rows = [
        _stack_row(
            timestamp_utc=datetime(2026, 5, 1, 0, 0, tzinfo=UTC),
            wholesale_energy_gbp=100.0,
            eac_availability_gbp=20.0,
            degradation_cost_gbp=5.0,
        ),
        _stack_row(
            timestamp_utc=datetime(2026, 5, 1, 0, 30, tzinfo=UTC),
            basis="perfect_foresight",
            wholesale_energy_gbp=10.0,
            eac_availability_gbp=0.0,
            degradation_cost_gbp=1.5,
            cm_annual_scenario_gbp_per_mw_year=25_000.0,
        ),
    ]

    paths = write_stack_series(rows, tmp_path)

    csv_frame = pd.read_csv(paths["csv"])
    parquet_frame = pd.read_parquet(paths["parquet"])

    assert paths == {
        "parquet": tmp_path / "stack_series.parquet",
        "csv": tmp_path / "stack_series.csv",
    }
    scalar_columns = [
        "timestamp_utc",
        "window_label",
        "asset_id",
        "basis",
        "wholesale_energy_gbp",
        "eac_availability_gbp",
        "degradation_cost_gbp",
        "cm_annual_scenario_gbp_per_mw_year",
        "gross_operating_value_gbp",
        "degradation_adjusted_value_gbp",
    ]

    assert list(csv_frame.columns) == STACK_SERIES_COLUMNS
    assert list(parquet_frame.columns) == STACK_SERIES_COLUMNS
    pd.testing.assert_frame_equal(
        csv_frame[scalar_columns].astype(str),
        parquet_frame[scalar_columns].astype(str),
    )
    assert csv_frame["caveat_flags"].map(json.loads).tolist() == [
        ["not_a_market_index"],
        ["not_a_market_index"],
    ]
    assert parquet_frame["caveat_flags"].map(lambda flags: "not_a_market_index" in flags).all()
