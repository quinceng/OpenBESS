from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_CACHE_DIR = Path("results/dashboard")

REQUIRED_FILES = {
    "manifest": "manifest.json",
    "executive_summary": "executive_summary.json",
    "policy_capture": "policy_capture.parquet",
    "revenue_stack": "revenue_stack.parquet",
    "scenario_sweeps": "scenario_sweeps.parquet",
    "caveats": "caveats.json",
}

OPTIONAL_FILES = {
    "degradation_summary": "degradation_summary.json",
    "finance_summary": "finance_summary.json",
    "finance_cashflows": "finance_cashflows.parquet",
    "finance_sensitivities": "finance_sensitivities.parquet",
    "benchmark_reconciliation": "benchmark_reconciliation.json",
    "eac_commitments": "eac_commitments.parquet",
    "data_quality": "data_quality.json",
    "stack_series": "stack_series.parquet",
    "stack_series_csv": "stack_series.csv",
    "stack_series_windows": "stack_series_windows.csv",
    "forecast_error_sweeps": "forecast_error_sweeps.parquet",
    "forecast_model_comparison": "forecast_model_comparison.parquet",
    "data_quality_summary": "data_quality_summary.csv",
    "assumptions_ledger": "assumptions_ledger.json",
    "source_snapshot": "source_snapshot.json",
}

STACK_SERIES_REQUIRED_COLUMNS = {
    "timestamp_utc",
    "window_label",
    "asset_id",
    "basis",
    "wholesale_energy_gbp",
    "eac_availability_gbp",
    "degradation_cost_gbp",
    "cm_annual_scenario_gbp_per_mw_year",
    "caveat_flags",
}
STACK_SERIES_WINDOW_LABELS = {"7d", "30d", "90d", "ytd", "trailing_12m"}
STACK_SERIES_BASIS_VALUES = {"rolling_policy", "perfect_foresight", "scenario"}


class DashboardCacheError(RuntimeError):
    """Raised when cached dashboard artefacts are missing or unreadable."""


@dataclass(frozen=True)
class DashboardCache:
    """Cached artefacts used by the Streamlit dashboard."""

    cache_dir: Path
    manifest: dict[str, Any]
    executive_summary: dict[str, Any]
    policy_capture: pd.DataFrame
    revenue_stack: pd.DataFrame
    scenario_sweeps: pd.DataFrame
    caveats: dict[str, Any]
    degradation_summary: dict[str, Any] | None = None
    finance_summary: dict[str, Any] | None = None
    finance_cashflows: pd.DataFrame | None = None
    finance_sensitivities: pd.DataFrame | None = None
    benchmark_reconciliation: dict[str, Any] | None = None
    eac_commitments: pd.DataFrame | None = None
    data_quality: dict[str, Any] | None = None
    stack_series: pd.DataFrame | None = None
    stack_series_windows: pd.DataFrame | None = None
    forecast_error_sweeps: pd.DataFrame | None = None
    forecast_model_comparison: pd.DataFrame | None = None
    data_quality_summary: pd.DataFrame | None = None
    assumptions_ledger: dict[str, Any] | None = None
    source_snapshot: dict[str, Any] | None = None


def load_dashboard_cache(cache_dir: str | Path = DEFAULT_CACHE_DIR) -> DashboardCache:
    """Load dashboard cache files without importing solvers or source clients."""

    root = Path(cache_dir)
    missing = [filename for filename in REQUIRED_FILES.values() if not (root / filename).is_file()]
    if missing:
        joined = ", ".join(sorted(missing))
        msg = (
            f"Missing dashboard cache files: {joined}. "
            "Regenerate them with `uv run gb-bess run-phase4-smoke`."
        )
        raise DashboardCacheError(msg)
    try:
        manifest = _read_json(root / REQUIRED_FILES["manifest"])
        stack_series = _read_optional_stack_series(
            root=root,
            manifest=manifest,
        )
        return DashboardCache(
            cache_dir=root,
            manifest=manifest,
            executive_summary=_read_json(root / REQUIRED_FILES["executive_summary"]),
            policy_capture=pd.read_parquet(root / REQUIRED_FILES["policy_capture"]),
            revenue_stack=pd.read_parquet(root / REQUIRED_FILES["revenue_stack"]),
            scenario_sweeps=pd.read_parquet(root / REQUIRED_FILES["scenario_sweeps"]),
            caveats=_read_json(root / REQUIRED_FILES["caveats"]),
            degradation_summary=_read_optional_json(root / OPTIONAL_FILES["degradation_summary"]),
            finance_summary=_read_optional_json(root / OPTIONAL_FILES["finance_summary"]),
            finance_cashflows=_read_optional_parquet(root / OPTIONAL_FILES["finance_cashflows"]),
            finance_sensitivities=_read_optional_parquet(
                root / OPTIONAL_FILES["finance_sensitivities"]
            ),
            benchmark_reconciliation=_read_optional_json(
                root / OPTIONAL_FILES["benchmark_reconciliation"]
            ),
            eac_commitments=_read_optional_parquet(root / OPTIONAL_FILES["eac_commitments"]),
            data_quality=_read_optional_json(root / OPTIONAL_FILES["data_quality"]),
            stack_series=stack_series,
            stack_series_windows=_read_optional_csv(root / OPTIONAL_FILES["stack_series_windows"]),
            forecast_error_sweeps=_read_optional_parquet(
                root / OPTIONAL_FILES["forecast_error_sweeps"]
            ),
            forecast_model_comparison=_read_optional_parquet(
                root / OPTIONAL_FILES["forecast_model_comparison"]
            ),
            data_quality_summary=_read_optional_csv(root / OPTIONAL_FILES["data_quality_summary"]),
            assumptions_ledger=_read_optional_json(root / OPTIONAL_FILES["assumptions_ledger"]),
            source_snapshot=_read_optional_json(root / OPTIONAL_FILES["source_snapshot"]),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        msg = f"Dashboard cache at {root} could not be read: {exc}"
        raise DashboardCacheError(msg) from exc


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"{path.name} must contain a JSON object."
        raise ValueError(msg)
    return payload


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    return _read_json(path) if path.is_file() else None


def _read_optional_parquet(path: Path) -> pd.DataFrame | None:
    return pd.read_parquet(path) if path.is_file() else None


def _read_optional_csv(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path) if path.is_file() else None


def _read_optional_stack_series(*, root: Path, manifest: dict[str, Any]) -> pd.DataFrame | None:
    files = manifest.get("files", {})
    advertised_parquet = isinstance(files, dict) and "stack_series_parquet" in files
    advertised_csv = isinstance(files, dict) and "stack_series_csv" in files
    parquet_path = root / OPTIONAL_FILES["stack_series"]
    csv_path = root / OPTIONAL_FILES["stack_series_csv"]

    if advertised_parquet and not parquet_path.is_file():
        msg = "manifest advertises stack_series.parquet but the file is missing."
        raise ValueError(msg)
    if advertised_csv and not csv_path.is_file():
        msg = "manifest advertises stack_series.csv but the file is missing."
        raise ValueError(msg)

    frame = _read_optional_parquet(parquet_path)
    if frame is None:
        return None
    if csv_path.is_file():
        _validate_stack_series_csv_sidecar(frame, csv_path)

    missing = sorted(STACK_SERIES_REQUIRED_COLUMNS.difference(frame.columns))
    if missing:
        msg = f"stack_series.parquet missing required columns: {', '.join(missing)}."
        raise ValueError(msg)

    normalised = frame.copy()
    normalised["caveat_flags"] = [
        _normalise_stack_caveats(value, row_index)
        for row_index, value in enumerate(normalised["caveat_flags"])
    ]
    normalised["timestamp_utc"] = pd.to_datetime(normalised["timestamp_utc"], utc=True)

    for row_index, row in normalised.iterrows():
        if row["window_label"] not in STACK_SERIES_WINDOW_LABELS:
            msg = f"Invalid stack_series row {row_index}: unknown window_label."
            raise ValueError(msg)
        if row["basis"] not in STACK_SERIES_BASIS_VALUES:
            msg = f"Invalid stack_series row {row_index}: unknown basis."
            raise ValueError(msg)
        if float(row["degradation_cost_gbp"]) < 0:
            msg = f"Invalid stack_series row {row_index}: negative degradation_cost_gbp."
            raise ValueError(msg)
        cm_value = row["cm_annual_scenario_gbp_per_mw_year"]
        if pd.notna(cm_value) and float(cm_value) < 0:
            msg = (
                f"Invalid stack_series row {row_index}: "
                "negative cm_annual_scenario_gbp_per_mw_year."
            )
            raise ValueError(msg)

    normalised["gross_operating_value_gbp"] = (
        normalised["wholesale_energy_gbp"] + normalised["eac_availability_gbp"]
    )
    normalised["degradation_adjusted_value_gbp"] = (
        normalised["gross_operating_value_gbp"] - normalised["degradation_cost_gbp"]
    )
    return normalised


def _validate_stack_series_csv_sidecar(parquet_frame: pd.DataFrame, csv_path: Path) -> None:
    csv_frame = pd.read_csv(csv_path)
    if len(csv_frame) != len(parquet_frame):
        msg = "stack_series.csv row count does not match stack_series.parquet."
        raise ValueError(msg)
    missing = sorted(STACK_SERIES_REQUIRED_COLUMNS.difference(csv_frame.columns))
    if missing:
        msg = f"stack_series.csv missing required columns: {', '.join(missing)}."
        raise ValueError(msg)
    for row_index, value in enumerate(csv_frame["caveat_flags"]):
        _normalise_stack_caveats(value, row_index)


def _normalise_stack_caveats(value: object, row_index: int) -> list[str]:
    if isinstance(value, str):
        parsed = json.loads(value)
        if not isinstance(parsed, list):
            msg = f"Invalid stack_series row {row_index}: caveat_flags is not a list."
            raise ValueError(msg)
        return [str(item) for item in parsed]
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        parsed = tolist()
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    msg = f"Invalid stack_series row {row_index}: caveat_flags is not a list."
    raise ValueError(msg)
