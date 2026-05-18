from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from gb_bess_revenue_stack.schemas.market import CapacityMarketScenario


class CMAnnualRevenue(BaseModel):
    """Annual Capacity Market scenario revenue."""

    model_config = ConfigDict(extra="forbid")

    scenario_name: str
    derated_mw: float = Field(ge=0)
    annual_revenue_gbp: float


class CMScenarioCollection(BaseModel):
    """Lookup wrapper for CM scenarios keyed by auction, year and duration."""

    model_config = ConfigDict(extra="forbid")

    scenarios: list[CapacityMarketScenario]

    def by_key(
        self,
        *,
        auction_type: str,
        delivery_year: str,
        asset_duration_hours: float,
    ) -> CapacityMarketScenario:
        for scenario in self.scenarios:
            if (
                scenario.auction_type == auction_type
                and scenario.delivery_year == delivery_year
                and scenario.asset_duration_hours == asset_duration_hours
            ):
                return scenario
        msg = (
            "No CM scenario for "
            f"auction_type={auction_type!r}, delivery_year={delivery_year!r}, "
            f"asset_duration_hours={asset_duration_hours!r}."
        )
        raise KeyError(msg)


class CMAnnualSummaryAttachment(BaseModel):
    """Dispatch rows plus annual-only Capacity Market summary values."""

    model_config = ConfigDict(extra="forbid")

    period_rows: list[dict[str, Any]]
    annual_summary: dict[str, float]


def calculate_cm_annual_revenue(scenario: CapacityMarketScenario) -> CMAnnualRevenue:
    derated_mw = scenario.contracted_mw_derated
    if derated_mw is None:
        msg = "CapacityMarketScenario did not derive contracted_mw_derated."
        raise ValueError(msg)
    return CMAnnualRevenue(
        scenario_name=scenario.scenario_name,
        derated_mw=derated_mw,
        annual_revenue_gbp=derated_mw * scenario.clearing_price_gbp_per_kw_year * 1000,
    )


def load_cm_scenarios(path: str | Path) -> CMScenarioCollection:
    scenario_path = Path(path)
    if scenario_path.suffix in {".yaml", ".yml"}:
        return _load_cm_scenarios_yaml(scenario_path)
    with scenario_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    scenarios = [_scenario_from_csv_row(row) for row in rows]
    return CMScenarioCollection(scenarios=scenarios)


def validate_cm_scenario_for_central_result(scenario: CapacityMarketScenario) -> None:
    marker = f"{scenario.scenario_name} {scenario.notes}".lower()
    if scenario.derating_factor >= 1 or "no_derating" in marker or "no-derating" in marker:
        msg = "A no-derating diagnostic cannot be selected as a central CM result."
        raise ValueError(msg)


def attach_cm_revenue_to_annual_summary_only(
    *,
    dispatch_rows: list[dict[str, Any]],
    annual_cm_revenue_gbp: float,
) -> CMAnnualSummaryAttachment:
    return CMAnnualSummaryAttachment(
        period_rows=dispatch_rows,
        annual_summary={"capacity_market_revenue_gbp": annual_cm_revenue_gbp},
    )


def _scenario_from_csv_row(row: dict[str, str | None]) -> CapacityMarketScenario:
    return CapacityMarketScenario(
        scenario_name=_required(row, "scenario_name"),
        auction_type=_required(row, "auction_type"),
        delivery_year=_required(row, "delivery_year"),
        clearing_price_gbp_per_kw_year=float(_required(row, "clearing_price_gbp_per_kw_year")),
        derating_factor=float(_required(row, "derating_factor")),
        asset_duration_hours=float(_required(row, "asset_duration_hours")),
        contracted_mw_nameplate=float(_required(row, "contracted_mw_nameplate")),
        source_id=_required(row, "source_id"),
        source_url=_required(row, "source_url"),
        source_date=_required(row, "source_date"),
        notes=_required(row, "notes"),
    )


def _required(row: dict[str, str | None], key: str) -> str:
    value = row.get(key)
    if value is None:
        msg = f"CM scenario row missing required column {key!r}."
        raise ValueError(msg)
    return value


def _load_cm_scenarios_yaml(path: Path) -> CMScenarioCollection:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = payload.get("scenarios", [])
    if not isinstance(rows, list):
        msg = f"{path} must contain a scenarios list."
        raise ValueError(msg)
    return CMScenarioCollection(
        scenarios=[CapacityMarketScenario.model_validate(row) for row in rows]
    )
