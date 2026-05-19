from __future__ import annotations

import csv
from pathlib import Path

import pytest
import yaml

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


def test_phase_reviews_exist_and_record_gate_decisions() -> None:
    feasibility = ROOT / "docs/phase_reviews/p1_00_source_feasibility.md"
    phase_review = ROOT / "docs/phase_reviews/phase_1_review.md"

    assert feasibility.exists()
    assert phase_review.exists()
    assert (
        "production client build may proceed with caveats"
        in feasibility.read_text(encoding="utf-8").lower()
    )
    assert "proceed with caveat" in phase_review.read_text(encoding="utf-8").lower()


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


def test_release_docs_record_historical_phase4_and_residential_scenario_sweeps() -> None:
    phase4_plan = (ROOT / "docs/phase_4_plan.md").read_text(encoding="utf-8")
    release_checklist = (ROOT / "docs/release_checklist.md").read_text(encoding="utf-8")
    residential_assumptions = (ROOT / "docs/residential_bess_assumptions.md").read_text(
        encoding="utf-8"
    )

    assert "aligned historical Elexon/NESO sample" in phase4_plan
    assert "Phase 4 default smoke sample is historical" in release_checklist
    assert "Residential Scenario Sweeps" in residential_assumptions


def test_release_hardening_files_exist() -> None:
    assert (ROOT / "LICENSE").is_file()
    assert (ROOT / "CHANGELOG.md").is_file()
