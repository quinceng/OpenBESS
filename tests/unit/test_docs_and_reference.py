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
    assert (ROOT / "docs/release_notes_v0.1.2.md").is_file()
    assert (ROOT / "docs/phase_reviews/phase_6_review.md").is_file()


def test_public_process_evidence_docs_exist() -> None:
    for relative_path in [
        "docs/product_plan.md",
        "docs/quality_gates.md",
        "docs/release_checklist.md",
        "docs/source_research_notes.md",
        "docs/validation_memo.md",
        "docs/phase_reviews/README.md",
        "docs/phase_reviews/p1_00_source_feasibility.md",
        "docs/phase_reviews/phase_1_review.md",
        "docs/phase_reviews/phase_2_review.md",
        "docs/phase_reviews/phase_2_5_review.md",
        "docs/phase_reviews/phase_3_review.md",
        "docs/phase_reviews/phase_4_review.md",
        "docs/phase_reviews/phase_5_review.md",
        "docs/phase_reviews/phase_6_review.md",
    ]:
        assert (ROOT / relative_path).is_file()


def test_phase6_review_records_trailing_12m_follow_up() -> None:
    review = (ROOT / "docs/phase_reviews/phase_6_review.md").read_text(encoding="utf-8")

    assert "Post-Phase-6 Follow-Up" in review
    assert "results/dashboard/release_trailing_12m_historical" in review
    assert "target_window_eligible=true" in review
    assert "results/dashboard/release_90d_historical" in review
    assert "below_trailing_12m_coverage" in review


def test_verified_source_assumptions_are_reconciled() -> None:
    ledger = (ROOT / "docs/assumptions_ledger.md").read_text(encoding="utf-8")

    expected_sources = {
        "A-WHOLESALE-001": "ELEXON_BMRS_MID",
        "A-EAC-002": "NESO_EAC_AUCTION_RESULTS",
        "A-EAC-004": "NESO_EAC_AUCTION_RESULTS",
    }

    for assumption_id, source_id in expected_sources.items():
        matching_rows = [
            line for line in ledger.splitlines() if line.startswith(f"| {assumption_id}")
        ]

        assert len(matching_rows) == 1
        assert "central_default" in matching_rows[0]
        assert "phase1_required" not in matching_rows[0]
        assert source_id in matching_rows[0]


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


def test_release_docs_pin_preview_cache_and_trailing_12m_target() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    reproducibility = (ROOT / "docs/reproducibility.md").read_text(encoding="utf-8")
    cache_contract = (ROOT / "docs/dashboard_cache_contract.md").read_text(encoding="utf-8")
    quality_gates = (ROOT / "docs/quality_gates.md").read_text(encoding="utf-8")
    release_checklist = (ROOT / "docs/release_checklist.md").read_text(encoding="utf-8")

    for phrase in [
        "results/dashboard/release_90d_historical",
        "results/dashboard/release_trailing_12m_historical",
        "below_trailing_12m_coverage",
        "GB_BESS_DASHBOARD_CACHE_DIR",
    ]:
        assert phrase in reproducibility

    readme_release_pointer = (
        "Release evidence and generated outputs live in the release notes and\nreproducibility docs"
    )
    assert readme_release_pointer in readme
    assert "Optional local viewer for cached outputs" in readme
    assert "For cache rebuilds or selecting named caches" in readme
    assert "## Key Results" not in readme
    assert "openbess_trailing_12m_headline.svg" not in readme
    assert "GBP 49,438.74" not in readme
    assert "release_cache" not in readme
    assert "trailing-12-month" not in readme
    assert "90-day preview cache" in reproducibility
    assert "long-running release job" in reproducibility
    assert "--profile trailing12m" in reproducibility
    assert "90-day preview reference\nrun" in cache_contract
    assert "target_window_eligible" in cache_contract
    assert "`rolling_policy`: forecast model" in cache_contract
    assert "supplementary diagnostics" in cache_contract.replace("\n", " ")
    assert "present but empty" in cache_contract
    assert "OpenBESS Stack Index Preview` to `OpenBESS Stack Index" in quality_gates
    assert "target_window_eligible" in release_checklist
