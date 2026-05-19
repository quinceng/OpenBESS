from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field

from gb_bess_revenue_stack.config.models import AssetConfig, SolverConfig
from gb_bess_revenue_stack.markets.eac_prices import EACPriceMatrix
from gb_bess_revenue_stack.optimisation.inputs import TerminalSocPolicy
from gb_bess_revenue_stack.optimisation.market_stack_model import solve_market_stack
from gb_bess_revenue_stack.policies.forecasts import ForecastModel
from gb_bess_revenue_stack.policies.rolling import RollingConfig
from gb_bess_revenue_stack.policies.rolling_market_stack import (
    RollingMarketStackRun,
    RollingMarketStackScenario,
    RollingMarketStackScenarioResult,
    run_rolling_market_stack_policy,
    run_rolling_market_stack_scenarios,
)
from gb_bess_revenue_stack.schemas.base import ensure_aware_utc
from gb_bess_revenue_stack.schemas.market import WholesalePricePoint


class Phase4ScenarioSweepResult(BaseModel):
    """Phase 4 rolling wholesale plus EAC scenario sweep output."""

    model_config = ConfigDict(extra="forbid")

    price_period_count: int = Field(ge=0)
    stress_day_count: int = Field(gt=0)
    scenario_results: list[RollingMarketStackScenarioResult]


class Phase4MarketStackCaptureResult(BaseModel):
    """Phase 4 rolling policy comparison against a perfect-foresight ceiling."""

    model_config = ConfigDict(extra="forbid")

    price_period_count: int = Field(ge=0)
    sample_hours: float = Field(ge=0)
    perfect_energy_revenue_gbp: float
    perfect_service_revenue_gbp: float
    perfect_total_revenue_gbp: float
    rolling_energy_revenue_gbp: float
    rolling_service_revenue_gbp: float
    rolling_total_revenue_gbp: float
    rolling_planned_revenue_gbp: float
    capture_ratio: float | None
    regret_gbp: float
    solver_failure_count: int = Field(ge=0)
    forecast_mae_gbp_per_mwh: float
    forecast_rmse_gbp_per_mwh: float


class Phase4SmokeWindowComparison(BaseModel):
    """Compact 24h/48h Phase 4 smoke comparison result."""

    model_config = ConfigDict(extra="forbid")

    label: str
    day_count: int = Field(gt=0)
    capture: Phase4MarketStackCaptureResult


def build_realistic_stress_price_profile(
    *,
    start_utc: datetime,
    day_count: int,
) -> list[WholesalePricePoint]:
    """Build a deterministic multi-day GB-like stress profile for network-free tests."""

    if day_count <= 0:
        msg = "day_count must be positive."
        raise ValueError(msg)
    start_utc = ensure_aware_utc(start_utc)
    rows: list[WholesalePricePoint] = []
    for day_index in range(day_count):
        for settlement_period in range(1, 49):
            period_start = start_utc + timedelta(
                days=day_index, minutes=30 * (settlement_period - 1)
            )
            period_end = period_start + timedelta(minutes=30)
            rows.append(
                WholesalePricePoint(
                    delivery_start_utc=period_start,
                    delivery_end_utc=period_end,
                    known_at_utc=period_end - timedelta(days=1),
                    settlement_date=period_start.date().isoformat(),
                    settlement_period=settlement_period,
                    duration_h=0.5,
                    price_gbp_per_mwh=_stress_price(day_index, settlement_period),
                    price_source_type="SYNTHETIC_TEST",
                    is_proxy=True,
                    retrieved_at_utc=start_utc,
                    source_id="PROJECT_CONVENTION",
                    source_url="phase4:realistic_stress_profile",
                    schema_version="0.1.0",
                    quality_flag="synthetic_stress",
                )
            )
    return rows


def default_phase4_market_stack_scenarios() -> list[RollingMarketStackScenario]:
    """Return default Phase 4 wholesale and EAC sensitivity scenarios."""

    return [
        RollingMarketStackScenario(
            name="base_case",
            stress_label="central",
            notes="Central synthetic stress profile with unscaled wholesale and EAC prices.",
        ),
        RollingMarketStackScenario(
            name="winter_peak_spread",
            stress_label="high_wholesale_spread",
            wholesale_price_scalar=1.35,
            eac_price_scalar=1,
            notes="Higher wholesale spreads during system-stress windows.",
        ),
        RollingMarketStackScenario(
            name="low_spread_eac_downside",
            stress_label="low_spread_low_eac",
            wholesale_price_scalar=0.7,
            eac_price_scalar=0.65,
            notes="Compressed wholesale spreads with weaker EAC availability pricing.",
        ),
        RollingMarketStackScenario(
            name="eac_upside",
            stress_label="high_eac",
            wholesale_price_scalar=1,
            eac_price_scalar=1.4,
            notes="EAC upside sensitivity with unchanged wholesale profile.",
        ),
        RollingMarketStackScenario(
            name="wholesale_downside",
            stress_label="low_wholesale",
            wholesale_price_scalar=0.75,
            eac_price_scalar=1,
            notes="Lower wholesale price capture with unchanged EAC availability pricing.",
        ),
        RollingMarketStackScenario(
            name="stack_upside",
            stress_label="high_wholesale_high_eac",
            wholesale_price_scalar=1.25,
            eac_price_scalar=1.25,
            notes="Combined wholesale and EAC upside case.",
        ),
    ]


def run_phase4_market_stack_sweep(
    *,
    prices: list[WholesalePricePoint],
    eac_price_matrix: EACPriceMatrix,
    asset: AssetConfig,
    initial_soc_mwh: float,
    forecast_model: ForecastModel,
    config: RollingConfig,
    scenarios: list[RollingMarketStackScenario] | None = None,
) -> Phase4ScenarioSweepResult:
    """Run the Phase 4 deterministic rolling market-stack scenario sweep."""

    selected = scenarios or default_phase4_market_stack_scenarios()
    results = run_rolling_market_stack_scenarios(
        prices=prices,
        eac_price_matrix=eac_price_matrix,
        asset=asset,
        initial_soc_mwh=initial_soc_mwh,
        forecast_model=forecast_model,
        config=config,
        scenarios=selected,
    )
    dates = {row.settlement_date for row in prices}
    return Phase4ScenarioSweepResult(
        price_period_count=len(prices),
        stress_day_count=len(dates),
        scenario_results=results,
    )


def run_phase4_market_stack_capture_comparison(
    *,
    prices: list[WholesalePricePoint],
    eac_price_matrix: EACPriceMatrix,
    asset: AssetConfig,
    initial_soc_mwh: float,
    rolling_run: RollingMarketStackRun,
    terminal_soc_policy: TerminalSocPolicy,
    terminal_soc_target_mwh: float | None = None,
    solver_config: SolverConfig | None = None,
) -> Phase4MarketStackCaptureResult:
    """Compare a realised rolling market-stack run with perfect foresight."""

    perfect = solve_market_stack(
        prices=prices,
        eac_price_matrix=eac_price_matrix,
        asset=asset,
        initial_soc_mwh=initial_soc_mwh,
        terminal_soc_policy=terminal_soc_policy,
        terminal_soc_target_mwh=terminal_soc_target_mwh,
        solver_config=solver_config,
    )
    perfect_total = perfect.total_revenue_gbp
    rolling_total = rolling_run.realised_total_revenue_gbp
    capture_ratio = rolling_total / perfect_total if abs(perfect_total) > 1e-9 else None
    return Phase4MarketStackCaptureResult(
        price_period_count=len(prices),
        sample_hours=sum(price.duration_h for price in prices),
        perfect_energy_revenue_gbp=perfect.energy_revenue_gbp,
        perfect_service_revenue_gbp=perfect.service_revenue_gbp,
        perfect_total_revenue_gbp=perfect_total,
        rolling_energy_revenue_gbp=rolling_run.realised_energy_revenue_gbp,
        rolling_service_revenue_gbp=rolling_run.realised_service_revenue_gbp,
        rolling_total_revenue_gbp=rolling_total,
        rolling_planned_revenue_gbp=rolling_run.planned_total_revenue_gbp,
        capture_ratio=capture_ratio,
        regret_gbp=perfect_total - rolling_total,
        solver_failure_count=rolling_run.solver_failure_count,
        forecast_mae_gbp_per_mwh=_mean(
            [step.forecast_mae_gbp_per_mwh for step in rolling_run.steps]
        ),
        forecast_rmse_gbp_per_mwh=_mean(
            [step.forecast_rmse_gbp_per_mwh for step in rolling_run.steps]
        ),
    )


def run_phase4_smoke_window_comparisons(
    *,
    prices: list[WholesalePricePoint],
    eac_price_matrix: EACPriceMatrix,
    asset: AssetConfig,
    initial_soc_mwh: float,
    forecast_model: ForecastModel,
    config: RollingConfig,
    window_day_counts: list[int] | None = None,
) -> list[Phase4SmokeWindowComparison]:
    """Run deterministic 24h/48h Phase 4 smoke comparisons where data is available."""

    selected_day_counts = window_day_counts or [1, 2]
    ordered = sorted(prices, key=lambda point: point.delivery_start_utc)
    comparisons: list[Phase4SmokeWindowComparison] = []
    for day_count in selected_day_counts:
        if day_count <= 0:
            msg = "window_day_counts must contain positive integers."
            raise ValueError(msg)
        period_count = day_count * 48
        if len(ordered) < period_count:
            continue
        window_prices = ordered[:period_count]
        window_matrix = _slice_eac_matrix(eac_price_matrix, period_count)
        rolling = run_rolling_market_stack_policy(
            prices=window_prices,
            eac_price_matrix=window_matrix,
            asset=asset,
            initial_soc_mwh=initial_soc_mwh,
            forecast_model=forecast_model,
            config=config,
        )
        capture = run_phase4_market_stack_capture_comparison(
            prices=window_prices,
            eac_price_matrix=window_matrix,
            asset=asset,
            initial_soc_mwh=initial_soc_mwh,
            rolling_run=rolling,
            terminal_soc_policy=config.terminal_soc_policy,  # type: ignore[arg-type]
            terminal_soc_target_mwh=config.terminal_soc_target_mwh,
            solver_config=config.solver,
        )
        comparisons.append(
            Phase4SmokeWindowComparison(
                label=f"{day_count * 24}h",
                day_count=day_count,
                capture=capture,
            )
        )
    return comparisons


def _stress_price(day_index: int, settlement_period: int) -> float:
    intraday = _intraday_component(settlement_period)
    weekend_softening = -12 if day_index % 7 in {5, 6} else 0
    stress_uplift = _stress_uplift(day_index, settlement_period)
    solar_cannibalisation = -45 if day_index % 5 == 0 and 20 <= settlement_period <= 31 else 0
    return round(55 + intraday + weekend_softening + stress_uplift + solar_cannibalisation, 2)


def _intraday_component(settlement_period: int) -> float:
    if 13 <= settlement_period <= 18:
        return 35
    if 33 <= settlement_period <= 40:
        return 70
    if settlement_period <= 10:
        return -10
    if 22 <= settlement_period <= 30:
        return -25
    return 5


def _stress_uplift(day_index: int, settlement_period: int) -> float:
    if day_index % 6 in {2, 3} and 34 <= settlement_period <= 40:
        return 150
    if day_index % 9 == 4 and settlement_period in {17, 18, 33, 34, 35}:
        return 95
    return 0


def _slice_eac_matrix(eac_price_matrix: EACPriceMatrix, period_count: int) -> EACPriceMatrix:
    return EACPriceMatrix(
        cells=[
            cell.model_copy() for cell in eac_price_matrix.cells if cell.period_index < period_count
        ]
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
