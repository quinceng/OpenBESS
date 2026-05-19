from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CommercialRouteName = Literal["direct_markets", "aggregator_route"]


class CommercialBessSystem(BaseModel):
    """Commercial-scale BESS branch model using MW/MWh units."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    branch_name: Literal["commercial"] = "commercial"
    name: str
    battery_capacity_mwh: float = Field(gt=0)
    inverter_power_mw: float = Field(gt=0)
    site_export_limit_mw: float | None = Field(default=None, gt=0)
    effective_export_limit_mw: float = Field(default=0, ge=0)
    battery_capex_gbp_per_mwh: float = Field(default=0, ge=0)
    inverter_capex_gbp_per_mw: float = Field(default=0, ge=0)
    installation_cost_gbp: float = Field(default=0, ge=0)
    grid_connection_cost_gbp: float = Field(default=0, ge=0)
    total_capex_gbp: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def derive_effective_export_limit_and_capex(self) -> CommercialBessSystem:
        export_limit = self.site_export_limit_mw
        if export_limit is None:
            export_limit = self.inverter_power_mw
        object.__setattr__(
            self,
            "effective_export_limit_mw",
            min(self.inverter_power_mw, export_limit),
        )
        total_capex = (
            self.battery_capacity_mwh * self.battery_capex_gbp_per_mwh
            + self.inverter_power_mw * self.inverter_capex_gbp_per_mw
            + self.installation_cost_gbp
            + self.grid_connection_cost_gbp
        )
        object.__setattr__(self, "total_capex_gbp", total_capex)
        return self


class CommercialRouteToMarketAssumptions(BaseModel):
    """Commercial market-access thresholds and route-to-market fee assumptions."""

    model_config = ConfigDict(extra="forbid")

    aggregator_allowed: bool = True
    aggregator_revenue_share_pct: float = Field(default=0.15, ge=0, le=1)
    aggregator_fixed_fee_gbp_per_year: float = Field(default=0, ge=0)
    direct_market_min_export_mw: float = Field(default=1, gt=0)
    direct_market_variable_fee_pct: float = Field(default=0.03, ge=0, le=1)
    direct_market_fixed_fee_gbp_per_year: float = Field(default=15_000, ge=0)


class CommercialRouteEligibility(BaseModel):
    """Eligibility and fee result for one commercial route to market."""

    model_config = ConfigDict(extra="forbid")

    name: CommercialRouteName
    eligible: bool
    effective_export_limit_mw: float = Field(ge=0)
    variable_fee_pct: float = Field(ge=0, le=1)
    fixed_fee_gbp_per_year: float = Field(ge=0)
    reason: str


class CommercialRouteToMarketResult(BaseModel):
    """Commercial market-access result for direct and aggregator routes."""

    model_config = ConfigDict(extra="forbid")

    system_name: str
    effective_export_limit_mw: float = Field(ge=0)
    routes: tuple[CommercialRouteEligibility, ...]

    def route(self, name: CommercialRouteName) -> CommercialRouteEligibility:
        for route in self.routes:
            if route.name == name:
                return route
        msg = f"Unknown commercial route {name!r}."
        raise KeyError(msg)


def evaluate_commercial_route_to_market(
    system: CommercialBessSystem,
    *,
    assumptions: CommercialRouteToMarketAssumptions | None = None,
) -> CommercialRouteToMarketResult:
    """Evaluate commercial direct-market and aggregator route options."""

    route_assumptions = assumptions or CommercialRouteToMarketAssumptions()
    direct_eligible = (
        system.effective_export_limit_mw >= route_assumptions.direct_market_min_export_mw
    )
    return CommercialRouteToMarketResult(
        system_name=system.name,
        effective_export_limit_mw=system.effective_export_limit_mw,
        routes=(
            CommercialRouteEligibility(
                name="direct_markets",
                eligible=direct_eligible,
                effective_export_limit_mw=system.effective_export_limit_mw,
                variable_fee_pct=route_assumptions.direct_market_variable_fee_pct,
                fixed_fee_gbp_per_year=route_assumptions.direct_market_fixed_fee_gbp_per_year,
                reason=(
                    "Direct-market route requires effective export capability of at least "
                    f"{route_assumptions.direct_market_min_export_mw:g} MW."
                    if not direct_eligible
                    else "Effective export capability meets the direct-market threshold."
                ),
            ),
            CommercialRouteEligibility(
                name="aggregator_route",
                eligible=route_assumptions.aggregator_allowed,
                effective_export_limit_mw=system.effective_export_limit_mw,
                variable_fee_pct=route_assumptions.aggregator_revenue_share_pct,
                fixed_fee_gbp_per_year=route_assumptions.aggregator_fixed_fee_gbp_per_year,
                reason=(
                    "Aggregator route is enabled for commercial assets under the current "
                    "assumption set."
                    if route_assumptions.aggregator_allowed
                    else "Aggregator route is disabled by the current assumption set."
                ),
            ),
        ),
    )
