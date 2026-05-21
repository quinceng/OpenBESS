from __future__ import annotations

import csv
import tomllib
from pathlib import Path

import pytest
import yaml

from gb_bess_revenue_stack import __version__
from gb_bess_revenue_stack.schemas.market import CapacityMarketScenario

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_source_registry_has_phase1_gate_decisions() -> None:
    registry = yaml.safe_load((ROOT / "docs/source_registry.yaml").read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in registry["sources"]}

    assert sources["ELEXON_BMRS_MID"]["status"] == "verified"
    assert sources["NESO_EAC_AUCTION_RESULTS"]["status"] == "verified"
    assert sources["CM_OFFICIAL_AUCTION_PARAMETERS"]["status"] == "usable_with_caveat"
    assert sources["PUBLIC_BENCHMARK_ANCHORS"]["status"] == "usable_with_caveat"
    assert "phase1_verify" not in yaml.safe_dump(sources["ELEXON_BMRS_MID"])
    assert "phase1_verify" not in yaml.safe_dump(sources["NESO_EAC_AUCTION_RESULTS"])


def test_public_explanatory_docs_exist() -> None:
    for relative_path in [
        "README.md",
        "docs/README.md",
        "docs/methodology.md",
        "docs/model_boundaries.md",
        "docs/openbess_stack_index.md",
        "docs/reproducibility.md",
        "docs/known_limitations.md",
    ]:
        assert (ROOT / relative_path).exists()


def test_capacity_market_reference_scenarios_validate() -> None:
    scenario_path = ROOT / "data/reference/capacity_market_scenarios.csv"

    with scenario_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    scenarios = [
        CapacityMarketScenario(
            **{
                **row,
                "clearing_price_gbp_per_kw_year": float(row["clearing_price_gbp_per_kw_year"]),
                "derating_factor": float(row["derating_factor"]),
                "asset_duration_hours": float(row["asset_duration_hours"]),
                "contracted_mw_nameplate": float(row["contracted_mw_nameplate"]),
            }
        )
        for row in rows
    ]

    assert {scenario.scenario_name for scenario in scenarios} == {
        "t1_2025_26_two_hour_research_anchor",
        "t4_2028_29_two_hour_research_anchor",
    }


def test_public_residential_doc_records_scenario_sweeps() -> None:
    residential_assumptions = (ROOT / "docs/residential_bess_assumptions.md").read_text(
        encoding="utf-8"
    )

    assert "Residential Scenario Sweeps" in residential_assumptions


def test_capacity_market_caveat_is_closed_as_reference_sidecar() -> None:
    cm_config = (ROOT / "configs/scenarios_cm.yaml").read_text(encoding="utf-8")
    source_registry = (ROOT / "docs/source_registry.yaml").read_text(encoding="utf-8")
    methodology = (ROOT / "docs/methodology.md").read_text(encoding="utf-8")

    assert "scenario/reference sidecar only" in cm_config
    assert "not a central official storage-derating result" in cm_config
    assert "Contracts for Difference and Capacity Market scheme update 2025" in source_registry
    assert "CM research-anchor derating values remain reference sidecars" in methodology


def test_release_hardening_files_exist() -> None:
    assert (ROOT / "LICENSE").is_file()
    assert (ROOT / "CHANGELOG.md").is_file()
    assert (ROOT / "docs/release_notes_v0.1.1.md").is_file()
    assert (ROOT / "docs/phase_reviews/phase_6_review.md").is_file()


def test_release_version_docs_match_package_version() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]
    release_note = ROOT / f"docs/release_notes_v{version}.md"
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert __version__ == version
    assert release_note.is_file()
    assert f"OpenBESS v{version} Release Note" in release_note.read_text(encoding="utf-8")
    assert f"## {version} -" in changelog


def test_openbess_stack_index_public_doc_records_required_boundary_language() -> None:
    doc = (ROOT / "docs/openbess_stack_index.md").read_text(encoding="utf-8")

    required_phrases = [
        "OpenBESS Stack Index",
        "OpenBESS Stack Index Preview",
        "not an official market index",
        "not investment advice",
        "Elexon BMRS MID wholesale proxy",
        "NESO EAC price-taking availability proxy",
        "Capacity Market annual scenario",
        "known_at_utc <= decision_time_utc",
        "Balancing Mechanism counterfactual revenue is excluded",
        "educational simple-market preset",
    ]

    for phrase in required_phrases:
        assert phrase in doc

    for phrase in [
        "reference assets",
        "GB sequence",
        "7d",
        "30d",
        "90d",
        "ytd",
        "trailing_12m",
        "published artefacts",
        "not_a_market_index",
        "partial_sample_annualised",
        "asset actually solved",
        "suppressed/null until coverage gates pass",
        "calendar year-to-date",
    ]:
        assert phrase in doc


def test_openbess_stack_index_is_referenced_by_boundary_docs() -> None:
    methodology = (ROOT / "docs/methodology.md").read_text(encoding="utf-8")
    model_boundaries = (ROOT / "docs/model_boundaries.md").read_text(encoding="utf-8")
    cache_contract = (ROOT / "docs/dashboard_cache_contract.md").read_text(encoding="utf-8")

    assert "openbess_stack_index.md" in methodology
    assert "not_a_market_index" in model_boundaries
    assert "not_a_market_index" in cache_contract
    assert "stack_series.parquet" in cache_contract
    assert "stack_series.csv" in cache_contract
    assert "data_quality.json` under\n`stack_series_windows`" in cache_contract
    assert "90d window is the minimum annualisation" in cache_contract
    assert "asset actually solved in the cache" in cache_contract
    assert "duplicate fixed 90-day" in cache_contract
    assert "suppressed/null until stack-series coverage gates pass" in cache_contract
