from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from gb_bess_revenue_stack.config.models import AssetConfig
from gb_bess_revenue_stack.optimisation.inputs import build_dispatch_input
from gb_bess_revenue_stack.optimisation.model_factory import build_energy_dispatch_model
from gb_bess_revenue_stack.optimisation.results import extract_dispatch_result
from gb_bess_revenue_stack.optimisation.solve import solve_dispatch_model
from gb_bess_revenue_stack.policies.evaluation import (
    detect_free_terminal_artifact,
    evaluate_rolling_policy,
)
from gb_bess_revenue_stack.policies.forecasts import OracleForecast
from gb_bess_revenue_stack.policies.rolling import (
    RollingConfig,
    RollingPolicyError,
    run_rolling_policy,
)
from gb_bess_revenue_stack.schemas.market import WholesalePricePoint

pytestmark = pytest.mark.unit


def _asset() -> AssetConfig:
    return AssetConfig(
        name="rolling-test-asset",
        power_mw=1,
        energy_capacity_mwh=2,
        eta_charge=1,
        eta_discharge=1,
    )


def _prices(values: list[float]) -> list[WholesalePricePoint]:
    rows: list[WholesalePricePoint] = []
    for index, price in enumerate(values, start=1):
        start = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=(index - 1) * 0.5)
        end = start + timedelta(minutes=30)
        rows.append(
            WholesalePricePoint(
                delivery_start_utc=start,
                delivery_end_utc=end,
                settlement_date="2024-01-01",
                settlement_period=index,
                duration_h=0.5,
                price_gbp_per_mwh=price,
                price_source_type="MID",
                is_proxy=True,
                known_at_utc=end,
                retrieved_at_utc=datetime(2024, 1, 2, tzinfo=UTC),
                source_id="ELEXON_BMRS_MID",
                source_url="https://data.elexon.co.uk",
                schema_version="0.1.0",
                quality_flag="ok",
            )
        )
    return rows


def _perfect_foresight_revenue(rows: list[WholesalePricePoint]) -> float:
    dispatch_input = build_dispatch_input(
        rows,
        asset=_asset(),
        initial_soc_mwh=1,
        terminal_soc_policy="cyclic",
        binary_dispatch=True,
    )
    model = build_energy_dispatch_model(dispatch_input)
    diagnostics = solve_dispatch_model(model)
    return extract_dispatch_result(model, diagnostics).total_revenue_gbp


def test_rolling_state_updates_from_executed_action_not_planned_tail() -> None:
    run = run_rolling_policy(
        prices=_prices([-10, -10, 100, 100]),
        asset=_asset(),
        initial_soc_mwh=1,
        forecast_model=OracleForecast(),
        config=RollingConfig(horizon_periods=4, step_periods=1, terminal_soc_policy="free"),
    )

    first = run.steps[0]

    assert first.executed_charge_mw > 0
    assert first.soc_end_mwh == pytest.approx(1.5)
    assert first.planned_terminal_soc_mwh != pytest.approx(first.soc_end_mwh)


def test_rolling_oracle_full_block_matches_perfect_foresight_on_toy_case() -> None:
    rows = _prices([10, 10, 100, 100])
    perfect_revenue = _perfect_foresight_revenue(rows)
    run = run_rolling_policy(
        prices=rows,
        asset=_asset(),
        initial_soc_mwh=1,
        forecast_model=OracleForecast(),
        config=RollingConfig(horizon_periods=4, step_periods=4, terminal_soc_policy="cyclic"),
    )

    assert run.realised_revenue_gbp == pytest.approx(perfect_revenue)


def test_rolling_with_reference_terminal_target_matches_toy_oracle() -> None:
    rows = _prices([10, 10, 100, 100])
    perfect_revenue = _perfect_foresight_revenue(rows)
    run = run_rolling_policy(
        prices=rows,
        asset=_asset(),
        initial_soc_mwh=1,
        forecast_model=OracleForecast(),
        config=RollingConfig(
            horizon_periods=4,
            step_periods=1,
            terminal_soc_policy="target",
            terminal_soc_target_mwh=1,
        ),
    )

    assert run.realised_revenue_gbp == pytest.approx(perfect_revenue)
    assert run.terminal_soc_target_mwh == pytest.approx(1)


def test_target_terminal_policy_requires_reference_soc() -> None:
    with pytest.raises(ValueError, match="terminal_soc_target_mwh"):
        RollingConfig(horizon_periods=4, step_periods=1, terminal_soc_policy="target")


def test_capture_ratio_and_regret_are_computed_against_same_realised_data() -> None:
    rows = _prices([10, 10, 100, 100])
    perfect_revenue = _perfect_foresight_revenue(rows)
    run = run_rolling_policy(
        prices=rows,
        asset=_asset(),
        initial_soc_mwh=1,
        forecast_model=OracleForecast(),
        config=RollingConfig(horizon_periods=4, step_periods=4, terminal_soc_policy="cyclic"),
    )

    evaluation = evaluate_rolling_policy(run, perfect_foresight_revenue_gbp=perfect_revenue)

    assert evaluation.capture_ratio == pytest.approx(1)
    assert evaluation.regret_gbp == pytest.approx(0)
    assert evaluation.solver_failure_count == 0


def test_free_terminal_soc_creates_flagged_end_drain_artifact() -> None:
    rows = _prices([100, 100])
    cyclic = run_rolling_policy(
        prices=rows,
        asset=_asset(),
        initial_soc_mwh=1,
        forecast_model=OracleForecast(),
        config=RollingConfig(horizon_periods=2, step_periods=1, terminal_soc_policy="cyclic"),
    )
    free = run_rolling_policy(
        prices=rows,
        asset=_asset(),
        initial_soc_mwh=1,
        forecast_model=OracleForecast(),
        config=RollingConfig(horizon_periods=2, step_periods=1, terminal_soc_policy="free"),
    )

    artifact = detect_free_terminal_artifact(cyclic, free)

    assert artifact.artifact_detected is True
    assert artifact.incremental_revenue_gbp > 0


def test_step_records_are_reproducible() -> None:
    rows = _prices([10, 10, 100, 100])
    config = RollingConfig(horizon_periods=4, step_periods=1, terminal_soc_policy="free")

    first = run_rolling_policy(
        prices=rows,
        asset=_asset(),
        initial_soc_mwh=1,
        forecast_model=OracleForecast(),
        config=config,
    )
    second = run_rolling_policy(
        prices=rows,
        asset=_asset(),
        initial_soc_mwh=1,
        forecast_model=OracleForecast(),
        config=config,
    )

    first_records = [step.model_dump(exclude={"solver_wall_time_seconds"}) for step in first.steps]
    second_records = [
        step.model_dump(exclude={"solver_wall_time_seconds"}) for step in second.steps
    ]

    assert first_records == second_records


def test_solver_failures_raise_controlled_policy_error() -> None:
    with pytest.raises(RollingPolicyError, match="Rolling solve failed"):
        run_rolling_policy(
            prices=_prices([10, 100]),
            asset=_asset(),
            initial_soc_mwh=1,
            forecast_model=OracleForecast(),
            config=RollingConfig(
                horizon_periods=2,
                step_periods=1,
                terminal_soc_policy="cyclic",
                solver={"name": "missing_solver_for_policy_test"},
            ),
        )
