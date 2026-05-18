from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

from gb_bess_revenue_stack.schemas.market import CapacityMarketScenario

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _phase3_module(name: str) -> Any:
    try:
        return import_module(name)
    except ModuleNotFoundError as exc:
        raise AssertionError(f"Phase 3 module is not implemented yet: {name}") from exc


def test_capacity_market_annual_revenue_uses_derated_mw_and_kw_year_price() -> None:
    capacity_market = _phase3_module("gb_bess_revenue_stack.markets.capacity_market")
    scenario = CapacityMarketScenario(
        scenario_name="central",
        auction_type="T-1",
        delivery_year="2025/26",
        clearing_price_gbp_per_kw_year=20,
        derating_factor=0.2715,
        asset_duration_hours=2,
        contracted_mw_nameplate=50,
        source_id="CM_OFFICIAL_AUCTION_PARAMETERS",
        source_url="fixture",
        source_date="2024-08-12",
        notes="fixture",
    )

    result = capacity_market.calculate_cm_annual_revenue(scenario)

    assert result.derated_mw == pytest.approx(13.575)
    assert result.annual_revenue_gbp == pytest.approx(271_500)


def test_capacity_market_loader_preserves_duration_auction_and_delivery_year_specificity() -> None:
    capacity_market = _phase3_module("gb_bess_revenue_stack.markets.capacity_market")

    scenarios = capacity_market.load_cm_scenarios(
        ROOT / "data/reference/capacity_market_scenarios.csv"
    )
    selected = scenarios.by_key(
        auction_type="T-1",
        delivery_year="2025/26",
        asset_duration_hours=2,
    )

    assert selected.scenario_name == "t1_2025_26_two_hour_research_anchor"
    assert selected.derating_factor == pytest.approx(0.2715)


def test_capacity_market_config_yaml_loads_central_scenarios() -> None:
    capacity_market = _phase3_module("gb_bess_revenue_stack.markets.capacity_market")

    scenarios = capacity_market.load_cm_scenarios(ROOT / "configs/scenarios_cm.yaml")
    selected = scenarios.by_key(
        auction_type="T-4",
        delivery_year="2028/29",
        asset_duration_hours=2,
    )

    assert selected.scenario_name == "t4_2028_29_two_hour_research_anchor"
    assert selected.source_id == "MODO_CM_DERATING_2024_25_ANCHOR"


def test_no_derating_capacity_market_diagnostic_is_excluded_from_central_results() -> None:
    capacity_market = _phase3_module("gb_bess_revenue_stack.markets.capacity_market")

    with pytest.raises(ValueError, match="no-derating diagnostic"):
        capacity_market.validate_cm_scenario_for_central_result(
            CapacityMarketScenario(
                scenario_name="no_derating_diagnostic",
                auction_type="T-1",
                delivery_year="2025/26",
                clearing_price_gbp_per_kw_year=20,
                derating_factor=1,
                asset_duration_hours=2,
                contracted_mw_nameplate=50,
                source_id="PROJECT_CONVENTION",
                source_url="fixture",
                source_date="2024-08-12",
                notes="no-derating diagnostic",
            )
        )


def test_capacity_market_revenue_is_not_added_to_period_dispatch_rows() -> None:
    capacity_market = _phase3_module("gb_bess_revenue_stack.markets.capacity_market")

    dispatch_rows = [{"period_revenue_gbp": 10.0}, {"period_revenue_gbp": 20.0}]
    enriched = capacity_market.attach_cm_revenue_to_annual_summary_only(
        dispatch_rows=dispatch_rows,
        annual_cm_revenue_gbp=271_500,
    )

    assert enriched.period_rows == dispatch_rows
    assert enriched.annual_summary["capacity_market_revenue_gbp"] == pytest.approx(271_500)
    assert all("capacity_market_revenue_gbp" not in row for row in enriched.period_rows)
