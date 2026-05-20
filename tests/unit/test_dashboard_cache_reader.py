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
    assert cache.stack_series is not None
    assert cache.stack_series["basis"].tolist() == ["rolling_policy"]
    assert cache.stack_series_windows is not None
    assert cache.stack_series_windows["window_label"].tolist() == ["7d"]
    assert cache.data_quality_summary is not None
    assert cache.data_quality_summary["price_period_count"].tolist() == [336]
    assert cache.assumptions_ledger is not None
    assert cache.source_snapshot is not None
    assert cache.finance_sensitivities is not None
    assert cache.finance_sensitivities["case_name"].tolist() == ["central_case"]


def test_load_dashboard_cache_treats_stack_series_as_optional(tmp_path: Path) -> None:
    _write_minimal_dashboard_cache(tmp_path, include_stack_series=False)
    from dashboard.cache_reader import load_dashboard_cache

    cache = load_dashboard_cache(tmp_path)

    assert cache.stack_series is None


def test_load_dashboard_cache_rejects_invalid_stack_series_window(tmp_path: Path) -> None:
    _write_minimal_dashboard_cache(tmp_path, stack_series_window_label="central")
    from dashboard.cache_reader import DashboardCacheError, load_dashboard_cache

    with pytest.raises(DashboardCacheError, match="Invalid stack_series row 0"):
        load_dashboard_cache(tmp_path)


def test_load_dashboard_cache_rejects_advertised_missing_stack_series_csv(
    tmp_path: Path,
) -> None:
    _write_minimal_dashboard_cache(tmp_path, advertise_stack_series_csv=True)
    (tmp_path / "stack_series.csv").unlink()
    from dashboard.cache_reader import DashboardCacheError, load_dashboard_cache

    with pytest.raises(DashboardCacheError, match="stack_series.csv"):
        load_dashboard_cache(tmp_path)


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
    assert model["has_stack_series"] is True
    assert model["has_finance_sensitivities"] is True
    assert model["stack_index"]["display_label"] == "OpenBESS Stack Index Preview"
    assert model["stack_index"]["primary_window_label"] == "7d"
    assert model["stack_index"]["primary_coverage_pct"] == pytest.approx(1.0)
    assert model["stack_story_steps"] == [
        "Elexon BMRS MID wholesale proxy",
        "NESO EAC price-taking availability proxy",
        "Capacity Market annual scenario",
        "Degradation-adjusted rolling policy",
    ]


def _write_minimal_dashboard_cache(
    cache_dir: Path,
    *,
    include_stack_series: bool = True,
    stack_series_window_label: str = "7d",
    advertise_stack_series_csv: bool = False,
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "executive_summary": "executive_summary.json",
        "policy_capture": "policy_capture.parquet",
        "revenue_stack": "revenue_stack.parquet",
        "scenario_sweeps": "scenario_sweeps.parquet",
        "caveats": "caveats.json",
        "eac_commitments": "eac_commitments.parquet",
        "data_quality": "data_quality.json",
        "finance_sensitivities": "finance_sensitivities.parquet",
    }
    if include_stack_series:
        files["stack_series_parquet"] = "stack_series.parquet"
        if advertise_stack_series_csv:
            files["stack_series_csv"] = "stack_series.csv"
    (cache_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "dashboard-test",
                "stack_series": {
                    "primary_window_label": stack_series_window_label,
                    "eligible_for_public_index": False,
                    "eligible_for_annualisation": False,
                    "caveat_flags": ["not_a_market_index"],
                },
                "files": files,
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
    pd.DataFrame(
        [
            {
                "case_name": "central_case",
                "axis": "finance_scenario",
                "npv_gbp": 12_500.0,
                "npv_delta_vs_baseline_gbp": 0.0,
            }
        ]
    ).to_parquet(cache_dir / "finance_sensitivities.parquet", index=False)
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
                "stack_series_windows": [
                    {
                        "window_label": stack_series_window_label,
                        "observed_period_count": 336,
                        "expected_period_count": 336,
                        "coverage_pct": 1.0,
                        "eligible_for_public_index": False,
                        "eligible_for_annualisation": False,
                        "caveat_flags": ["not_a_market_index"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "window_label": stack_series_window_label,
                "observed_period_count": 336,
                "expected_period_count": 336,
                "coverage_pct": 1.0,
                "eligible_for_public_index": False,
                "eligible_for_annualisation": False,
            }
        ]
    ).to_csv(cache_dir / "stack_series_windows.csv", index=False)
    pd.DataFrame(
        [
            {
                "run_id": "dashboard-test",
                "price_period_count": 336,
                "solver_failure_count": 0,
            }
        ]
    ).to_csv(cache_dir / "data_quality_summary.csv", index=False)
    (cache_dir / "assumptions_ledger.json").write_text(
        json.dumps({"asset": {"asset_id": "phase4-commercial-reference"}}),
        encoding="utf-8",
    )
    (cache_dir / "source_snapshot.json").write_text(
        json.dumps({"source_snapshot_hash": "fixture-source"}),
        encoding="utf-8",
    )
    if include_stack_series:
        stack_series = pd.DataFrame(
            [
                {
                    "timestamp_utc": "2024-01-01T00:00:00+00:00",
                    "window_label": stack_series_window_label,
                    "asset_id": "phase4-commercial-reference",
                    "basis": "rolling_policy",
                    "wholesale_energy_gbp": 1200.0,
                    "eac_availability_gbp": 450.0,
                    "degradation_cost_gbp": 10.0,
                    "cm_annual_scenario_gbp_per_mw_year": None,
                    "caveat_flags": ["not_a_market_index"],
                    "gross_operating_value_gbp": 1650.0,
                    "degradation_adjusted_value_gbp": 1640.0,
                }
            ]
        )
        stack_series.to_parquet(cache_dir / "stack_series.parquet", index=False)
        csv_stack_series = stack_series.copy()
        csv_stack_series["caveat_flags"] = csv_stack_series["caveat_flags"].map(json.dumps)
        csv_stack_series.to_csv(cache_dir / "stack_series.csv", index=False)
