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

    eac_source = sources["NESO_EAC_AUCTION_RESULTS"]
    assert str(eac_source["verified_as_of"]) == "2026-05-24"
    assert (
        eac_source["known_at_policy"]
        == "delivery_start_utc_conservative_until_publication_time_verified"
    )
    assert "schema_drift_notes" in eac_source

    bm_source = sources["ELEXON_BM_OBSERVED_OPTIONAL"]
    assert bm_source["status"] == "deferred_future_research"
    assert bm_source["access"]["url"] == "TBD_explicit_future_scope_required_before_use"
    assert "acceptance probability or bid-stack model" in bm_source["caveat"]
    assert "out of sample" in bm_source["caveat"]


def test_public_explanatory_docs_exist() -> None:
    for relative_path in [
        "README.md",
        "docs/README.md",
        "docs/methodology.md",
        "docs/model_boundaries.md",
        "docs/openbess_reference_revenue_stack.md",
        "docs/reproducibility.md",
        "docs/known_limitations.md",
    ]:
        assert (ROOT / relative_path).exists()


def test_readme_states_falsifiable_public_data_research_question() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_flat = readme.replace("\n", " ")
    methodology = (ROOT / "docs/methodology.md").read_text(encoding="utf-8")
    docs_readme = (ROOT / "docs/README.md").read_text(encoding="utf-8")

    for phrase in [
        "perfect-foresight value is lost",
        "auditable public-data rolling policies",
        "forecast error versus market-boundary exclusions",
        "public-boundary perfect-foresight revenue",
        "capture ratio",
        "labelled limitations rather than proven causes",
    ]:
        assert phrase in readme_flat

    assert "## Research Question" in readme
    assert "README states the public research question" in methodology
    assert "research_question.md" not in methodology
    assert "literature_context.md" not in methodology
    assert "research_question.md" not in docs_readme
    assert "literature_context.md" not in docs_readme
    assert "Local-only docs" in docs_readme


def test_bm_deferral_language_is_guarded() -> None:
    known_limitations = (ROOT / "docs/known_limitations.md").read_text(encoding="utf-8")
    model_boundaries = (ROOT / "docs/model_boundaries.md").read_text(encoding="utf-8")

    for phrase in [
        "Central Release 1 excludes deterministic BM counterfactual revenue.",
        "acceptance-probability or bid-stack",
        "deferred future research",
        "uncertainty bands",
    ]:
        assert phrase in known_limitations
        assert phrase in model_boundaries

    assert "must not feed the central optimiser revenue stack" in model_boundaries


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


def test_internal_working_docs_are_kept_local_by_gitignore() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for pattern in [
        "docs/product_plan*.md",
        "docs/phase_*_plan.md",
        "docs/phase_reviews/",
        "docs/adr/",
        "docs/research_question.md",
        "docs/literature_context.md",
        "docs/quality_gates.md",
        "docs/release_checklist.md",
        "docs/source_research_notes.md",
        "docs/validation_memo.md",
        "docs/strategic_positioning.md",
    ]:
        assert pattern in gitignore


def test_release_note_records_trailing_12m_follow_up() -> None:
    release_note = (ROOT / "docs/release_notes_v0.1.2.md").read_text(encoding="utf-8")

    assert "trailing-12-month public evidence cache" in release_note
    assert "results/dashboard/release_trailing_12m_historical" in release_note
    assert "100% `trailing_12m` target-window coverage" in release_note
    assert "results/dashboard/release_90d_historical" not in release_note


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


def test_openbess_reference_revenue_stack_public_doc_records_required_boundary_language() -> None:
    doc = (ROOT / "docs/openbess_reference_revenue_stack.md").read_text(encoding="utf-8")

    required_phrases = [
        "OpenBESS Reference Revenue Stack",
        "OpenBESS Reference Revenue Stack Preview",
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


def test_openbess_reference_revenue_stack_is_referenced_by_boundary_docs() -> None:
    methodology = (ROOT / "docs/methodology.md").read_text(encoding="utf-8")
    model_boundaries = (ROOT / "docs/model_boundaries.md").read_text(encoding="utf-8")
    cache_contract = (ROOT / "docs/dashboard_cache_contract.md").read_text(encoding="utf-8")

    assert "openbess_reference_revenue_stack.md" in methodology
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
    release_note = (ROOT / "docs/release_notes_v0.1.2.md").read_text(encoding="utf-8")

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
    assert "## Contribution" in readme
    assert "open, auditable baseline" in readme
    assert "energy-industry\nreaders" in readme
    assert "research, education and commercial analysis" in readme
    assert "shared open\nreference rather than only against undisclosed internal models" in readme
    assert "not a substitute for site-specific\ncommercial due diligence" in readme
    assert "not as an\nofficial market index, a tradable benchmark" in readme
    assert "analysts, researchers, students and engineering teams" in readme
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
    assert "trailing-12-month public evidence cache" in release_note
    assert "target-window coverage" in release_note
