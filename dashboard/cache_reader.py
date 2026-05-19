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
}


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
