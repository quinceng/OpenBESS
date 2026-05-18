from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from gb_bess_revenue_stack.config.models import AssetConfig
from gb_bess_revenue_stack.markets.eac_prices import (
    EACPriceCell,
    EACPriceMatrix,
    empty_eac_price_matrix,
    synthetic_service_matrix,
)
from gb_bess_revenue_stack.policies.forecasts import OracleForecast
from gb_bess_revenue_stack.policies.rolling import RollingConfig, run_rolling_policy
from gb_bess_revenue_stack.policies.rolling_market_stack import (
    RollingMarketStackScenario,
    run_rolling_market_stack_policy,
    run_rolling_market_stack_scenarios,
)
from gb_bess_revenue_stack.schemas.market import WholesalePricePoint

pytestmark = pytest.mark.unit


def _asset() -> AssetConfig:
    return AssetConfig(
        name="rolling-market-stack-test-asset",
        power_mw=1,
        energy_capacity_mwh=2,
        eta_charge=1,
        eta_discharge=1,
    )


def _prices(values: list[float]) -> list[WholesalePricePoint]:
    rows: list[WholesalePricePoint] = []
    for index, price in enumerate(values, start=1):
        start = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(minutes=30 * (index - 1))
        end = start + timedelta(minutes=30)
        rows.append(
            WholesalePricePoint(
                delivery_start_utc=start,
                delivery_end_utc=end,
                known_at_utc=end,
                settlement_date=start.date().isoformat(),
                settlement_period=index,
                duration_h=0.5,
                price_gbp_per_mwh=price,
                price_source_type="SYNTHETIC_TEST",
                is_proxy=False,
                retrieved_at_utc=datetime(2024, 1, 2, tzinfo=UTC),
                source_id="PROJECT_CONVENTION",
                source_url="fixture",
                schema_version="0.1.0",
                quality_flag="ok",
            )
        )
    return rows


def test_rolling_market_stack_without_services_matches_energy_only_policy() -> None:
    rows = _prices([10, 10, 100, 100])
    config = RollingConfig(
        horizon_periods=4, step_periods=1, terminal_soc_policy="target", terminal_soc_target_mwh=1
    )

    energy_only = run_rolling_policy(
        prices=rows,
        asset=_asset(),
        initial_soc_mwh=1,
        forecast_model=OracleForecast(),
        config=config,
    )
    market_stack = run_rolling_market_stack_policy(
        prices=rows,
        eac_price_matrix=empty_eac_price_matrix(),
        asset=_asset(),
        initial_soc_mwh=1,
        forecast_model=OracleForecast(),
        config=config,
    )

    assert market_stack.realised_total_revenue_gbp == pytest.approx(
        energy_only.realised_revenue_gbp
    )
    assert market_stack.realised_service_revenue_gbp == pytest.approx(0)
    assert len(market_stack.steps) == len(energy_only.steps)


def test_rolling_market_stack_excludes_eac_not_known_at_decision_time() -> None:
    rows = _prices([0])
    future_known_cell = EACPriceCell(
        product_model_label="dynamic_containment_low",
        direction_model_label="upward",
        period_index=0,
        price_gbp_per_mw_h=1_000,
        availability_state="available",
        service_duration_h=0.5,
        known_at_utc=rows[0].delivery_start_utc + timedelta(hours=1),
    )

    run = run_rolling_market_stack_policy(
        prices=rows,
        eac_price_matrix=EACPriceMatrix(cells=[future_known_cell]),
        asset=_asset(),
        initial_soc_mwh=1,
        forecast_model=OracleForecast(),
        config=RollingConfig(horizon_periods=1, step_periods=1, terminal_soc_policy="free"),
    )

    assert run.realised_service_revenue_gbp == pytest.approx(0)
    assert run.steps[0].excluded_service_cell_count == 1
    assert sum(run.steps[0].executed_reserve_up_mw.values()) == pytest.approx(0)


def test_rolling_market_stack_scenarios_apply_eac_price_scalars() -> None:
    rows = _prices([0])
    matrix = synthetic_service_matrix(
        product_model_label="dynamic_containment_low",
        direction_model_label="upward",
        prices_gbp_per_mw_h=[10],
        duration_h=0.5,
    )

    results = run_rolling_market_stack_scenarios(
        prices=rows,
        eac_price_matrix=matrix,
        asset=_asset(),
        initial_soc_mwh=1,
        forecast_model=OracleForecast(),
        config=RollingConfig(horizon_periods=1, step_periods=1, terminal_soc_policy="free"),
        scenarios=[
            RollingMarketStackScenario(name="baseline"),
            RollingMarketStackScenario(name="double_eac", eac_price_scalar=2),
        ],
    )

    by_name = {result.name: result for result in results}

    assert by_name["baseline"].realised_service_revenue_gbp > 0
    assert by_name["double_eac"].realised_service_revenue_gbp == pytest.approx(
        by_name["baseline"].realised_service_revenue_gbp * 2
    )
