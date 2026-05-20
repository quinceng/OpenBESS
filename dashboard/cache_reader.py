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
    "benchmark_reconciliation": "benchmark_reconciliation.json",
    "eac_commitments": "eac_commitments.parquet",
    "data_quality": "data_quality.json",
    "stack_series": "stack_series.parquet",
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
    benchmark_reconciliation: dict[str, Any] | None = None
    eac_commitments: pd.DataFrame | None = None
    data_quality: dict[str, Any] | None = None
    stack_series: pd.DataFrame | None = None


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
        return DashboardCache(
            cache_dir=root,
            manifest=_read_json(root / REQUIRED_FILES["manifest"]),
            executive_summary=_read_json(root / REQUIRED_FILES["executive_summary"]),
            policy_capture=pd.read_parquet(root / REQUIRED_FILES["policy_capture"]),
            revenue_stack=pd.read_parquet(root / REQUIRED_FILES["revenue_stack"]),
            scenario_sweeps=pd.read_parquet(root / REQUIRED_FILES["scenario_sweeps"]),
            caveats=_read_json(root / REQUIRED_FILES["caveats"]),
            degradation_summary=_read_optional_json(root / OPTIONAL_FILES["degradation_summary"]),
            finance_summary=_read_optional_json(root / OPTIONAL_FILES["finance_summary"]),
            finance_cashflows=_read_optional_parquet(root / OPTIONAL_FILES["finance_cashflows"]),
            benchmark_reconciliation=_read_optional_json(
                root / OPTIONAL_FILES["benchmark_reconciliation"]
            ),
            eac_commitments=_read_optional_parquet(root / OPTIONAL_FILES["eac_commitments"]),
            data_quality=_read_optional_json(root / OPTIONAL_FILES["data_quality"]),
            stack_series=_read_optional_stack_series(root / OPTIONAL_FILES["stack_series"]),
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


def _read_optional_stack_series(path: Path) -> pd.DataFrame | None:
    frame = _read_optional_parquet(path)
    if frame is None:
        return None

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
