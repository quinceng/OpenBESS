from __future__ import annotations

import builtins
import importlib
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pandas as pd
import pytest

pytestmark = pytest.mark.unit


def test_dashboard_import_does_not_import_solver_or_api_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked_prefixes = (
        "gb_bess_revenue_stack.data",
        "gb_bess_revenue_stack.optimisation",
        "gb_bess_revenue_stack.phase4",
        "highspy",
        "httpx",
        "pyomo",
        "tenacity",
    )
    real_import = builtins.__import__

    def guarded_import(
        name: str,
        globals_: dict[str, Any] | None = None,
        locals_: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> ModuleType:
        if name.startswith(blocked_prefixes):
            msg = f"Dashboard imported forbidden dependency {name!r}."
            raise AssertionError(msg)
        return real_import(name, globals_, locals_, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    importlib.import_module("dashboard.cache_reader")
    importlib.import_module("dashboard.streamlit_app")


def test_load_dashboard_cache_reads_phase4_tables(tmp_path: Path) -> None:
    _write_minimal_dashboard_cache(tmp_path)
    from dashboard.cache_reader import load_dashboard_cache

    cache = load_dashboard_cache(tmp_path)

    assert cache.manifest["run_id"] == "dashboard-test"
    assert cache.executive_summary["capture_ratios"]["central"] == pytest.approx(0.82)
    assert set(cache.policy_capture["label"]) == {"central", "24h", "48h"}
    assert set(cache.revenue_stack["component"]) == {"wholesale_energy", "eac_availability"}
    assert list(cache.scenario_sweeps["scenario"]) == ["base_case"]
    assert cache.caveats["caveats"] == ["Synthetic stress profile."]
    assert cache.eac_commitments is not None
    assert cache.eac_commitments["service_model_label"].tolist() == ["dynamic_containment_low"]
    assert cache.data_quality is not None
    assert cache.data_quality["known_at_policy"] == "test_known_at_policy"


def test_load_dashboard_cache_missing_files_fails_gracefully(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    from dashboard.cache_reader import DashboardCacheError, load_dashboard_cache

    with pytest.raises(DashboardCacheError, match="Missing dashboard cache files"):
        load_dashboard_cache(tmp_path)


def test_dashboard_view_model_exposes_phase4_sections(tmp_path: Path) -> None:
    _write_minimal_dashboard_cache(tmp_path)
    from dashboard.cache_reader import load_dashboard_cache
    from dashboard.streamlit_app import build_view_model

    model = build_view_model(load_dashboard_cache(tmp_path))

    assert model["capture_ratio"] == pytest.approx(0.82)
    assert model["source_labels"]["wholesale"] == "synthetic Phase 4 stress profile"
    assert set(model["window_labels"]) == {"24h", "48h"}
    assert "rolling_policy" in model["revenue_basis"]
    assert model["scenario_count"] == 1
    assert model["caveats"] == ["Synthetic stress profile."]
    assert model["has_eac_commitments"] is True
    assert model["has_data_quality"] is True


def _write_minimal_dashboard_cache(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "dashboard-test",
                "files": {
                    "executive_summary": "executive_summary.json",
                    "policy_capture": "policy_capture.parquet",
                    "revenue_stack": "revenue_stack.parquet",
                    "scenario_sweeps": "scenario_sweeps.parquet",
                    "caveats": "caveats.json",
                    "eac_commitments": "eac_commitments.parquet",
                    "data_quality": "data_quality.json",
                },
            }
        ),
        encoding="utf-8",
    )
    (cache_dir / "executive_summary.json").write_text(
        json.dumps(
            {
                "capture_ratios": {"central": 0.82, "24h": 0.75, "48h": 0.8},
                "source_labels": {
                    "wholesale": "synthetic Phase 4 stress profile",
                    "eac": "synthetic EAC availability proxy",
                },
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {"label": "central", "capture_ratio": 0.82, "regret_gbp": 180.0},
            {"label": "24h", "capture_ratio": 0.75, "regret_gbp": 70.0},
            {"label": "48h", "capture_ratio": 0.8, "regret_gbp": 130.0},
        ]
    ).to_parquet(cache_dir / "policy_capture.parquet", index=False)
    pd.DataFrame(
        [
            {
                "basis": "rolling_policy",
                "component": "wholesale_energy",
                "value_gbp": 1200.0,
            },
            {
                "basis": "rolling_policy",
                "component": "eac_availability",
                "value_gbp": 450.0,
            },
        ]
    ).to_parquet(cache_dir / "revenue_stack.parquet", index=False)
    pd.DataFrame(
        [
            {
                "scenario": "base_case",
                "stress_label": "central",
                "total_revenue_gbp": 1650.0,
            }
        ]
    ).to_parquet(cache_dir / "scenario_sweeps.parquet", index=False)
    (cache_dir / "caveats.json").write_text(
        json.dumps({"caveats": ["Synthetic stress profile."]}),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "decision_time_utc": "2024-01-01T00:00:00+00:00",
                "service_model_label": "dynamic_containment_low",
                "direction": "up",
                "committed_mw": 0.25,
                "executed_period_count": 2,
            }
        ]
    ).to_parquet(cache_dir / "eac_commitments.parquet", index=False)
    (cache_dir / "data_quality.json").write_text(
        json.dumps(
            {
                "known_at_policy": "test_known_at_policy",
                "solver_failure_count": 0,
                "excluded_future_row_count": 0,
            }
        ),
        encoding="utf-8",
    )
