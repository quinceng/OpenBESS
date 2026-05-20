from __future__ import annotations

import csv
import json
import math
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, cast

import typer
from pydantic import ValidationError

from gb_bess_revenue_stack.commercial import CommercialBessSystem
from gb_bess_revenue_stack.config.models import AssetConfig
from gb_bess_revenue_stack.config.reference_assets import load_reference_assets
from gb_bess_revenue_stack.data.cache import RawCache
from gb_bess_revenue_stack.data.elexon import ELEXON_BASE_URL, MARKET_INDEX_PATH, ElexonMIDClient
from gb_bess_revenue_stack.data.manifest import DatasetManifest, ProcessedDatasetWriter
from gb_bess_revenue_stack.data.neso import (
    EAC_RESULTS_SUMMARY_RESOURCE_ID,
    NESO_CKAN_ACTION_BASE_URL,
    NESOEACClient,
    parse_eac_summary_records,
)
from gb_bess_revenue_stack.data.quality import validate_wholesale_prices
from gb_bess_revenue_stack.data.tabular import records_to_dataframe
from gb_bess_revenue_stack.markets.capacity_market import (
    CMAnnualRevenue,
    calculate_cm_annual_revenue,
    load_cm_scenarios,
)
from gb_bess_revenue_stack.markets.eac_prices import EACPriceMatrix, synthetic_single_service_matrix
from gb_bess_revenue_stack.optimisation.inputs import build_dispatch_input
from gb_bess_revenue_stack.optimisation.market_stack_model import (
    MarketStackResult,
    solve_market_stack,
)
from gb_bess_revenue_stack.optimisation.model_factory import build_energy_dispatch_model
from gb_bess_revenue_stack.optimisation.results import DispatchResult, extract_dispatch_result
from gb_bess_revenue_stack.optimisation.solve import solve_dispatch_model
from gb_bess_revenue_stack.phase4.aligned_cache import (
    AlignedCacheRequest,
    fetch_aligned_phase4_cache,
    load_aligned_phase4_cache,
    write_aligned_phase4_cache,
)
from gb_bess_revenue_stack.phase4.scenarios import (
    default_phase4_forecast_error_scenarios,
    default_phase4_market_stack_scenarios,
    load_phase4_historical_sample,
    run_phase4_forecast_error_sweep,
    run_phase4_market_stack_capture_comparison,
    run_phase4_market_stack_sweep,
    run_phase4_smoke_window_comparisons,
    skipped_phase4_smoke_windows,
)
from gb_bess_revenue_stack.policies.evaluation import evaluate_rolling_policy
from gb_bess_revenue_stack.policies.forecasts import PreviousDaySamePeriodForecast
from gb_bess_revenue_stack.policies.rolling import RollingConfig, RollingRun, run_rolling_policy
from gb_bess_revenue_stack.policies.rolling_market_stack import (
    RollingMarketStackRun,
    run_rolling_market_stack_policy,
)
from gb_bess_revenue_stack.reporting.dashboard_cache import (
    Phase4DashboardCacheInput,
    load_phase4_finance_assumptions,
    write_phase4_dashboard_cache,
)
from gb_bess_revenue_stack.reporting.investor_workbook import (
    InvestorWorkbookInput,
    write_investor_workbook,
)
from gb_bess_revenue_stack.reporting.stack_series import StackSeriesRow, write_stack_series
from gb_bess_revenue_stack.residential import (
    ResidentialHouseholdDispatchInput,
    ResidentialHouseholdDispatchResult,
    ResidentialPaybackScenarioResult,
    calculate_residential_household_payback_from_dispatch,
    get_residential_preset,
    run_residential_payback_scenarios,
    solve_residential_household_dispatch,
)
from gb_bess_revenue_stack.residential.io import load_household_profile_csv, load_tariff_csv
from gb_bess_revenue_stack.schemas.base import parse_source_datetime
from gb_bess_revenue_stack.schemas.market import WholesalePricePoint

app = typer.Typer(help="GB BESS Phase 1 data-foundation commands.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """GB BESS Phase 1 command group."""


@app.command()
def fetch_data(
    source: Annotated[str, typer.Option(help="Source ID to fetch.")],
    start: Annotated[str | None, typer.Option(help="UTC start timestamp for Elexon MID.")] = None,
    end: Annotated[str | None, typer.Option(help="UTC end timestamp for Elexon MID.")] = None,
    provider: Annotated[str | None, typer.Option(help="Elexon MID provider filter.")] = None,
    limit: Annotated[int, typer.Option(help="NESO EAC row limit.")] = 100,
    output_root: Annotated[Path, typer.Option(help="Repository-relative output root.")] = Path("."),
) -> None:
    """Fetch a tiny source sample, write raw cache, processed parquet and manifest."""

    retrieved_at_utc = datetime.now(UTC)
    raw_cache = RawCache(output_root / "data/raw")
    writer = ProcessedDatasetWriter(output_root / "data/processed")

    if source == "ELEXON_BMRS_MID":
        if start is None or end is None:
            raise typer.BadParameter("ELEXON_BMRS_MID requires --start and --end.")
        elexon_client = ElexonMIDClient()
        payload = elexon_client.fetch_market_index(
            start=parse_source_datetime(start),
            end=parse_source_datetime(end),
            provider=provider,
        )
        raw_cache.write_bytes(
            source_id=source,
            dataset="market-index",
            content=json.dumps(payload, sort_keys=True).encode("utf-8"),
            suffix=".json",
            retrieved_at_utc=retrieved_at_utc,
        )
        from gb_bess_revenue_stack.data.elexon import parse_market_index_points

        records = parse_market_index_points(
            payload,
            source_url=f"{ELEXON_BASE_URL}{MARKET_INDEX_PATH}",
            retrieved_at_utc=retrieved_at_utc,
        )
        report = validate_wholesale_prices(records)
        frame = records_to_dataframe(records)
        manifest = DatasetManifest.from_dataframe(
            dataset="wholesale_price_points",
            schema_version="0.1.0",
            frame=frame,
            source_ids=[source],
            source_urls=[f"{ELEXON_BASE_URL}{MARKET_INDEX_PATH}"],
            retrieved_at_utc=retrieved_at_utc,
            known_at_policy="delivery_end_utc_conservative",
            validation_status=report.validation_status,
            missing_period_count=report.missing_period_count,
        )
        writer.write(
            dataset="wholesale_price_points",
            schema_version="0.1.0",
            frame=frame,
            filename_stem=f"{start}_{end}".replace(":", ""),
            manifest=manifest,
        )
        typer.echo(f"Fetched {len(records)} Elexon MID rows; validation={report.validation_status}")
        return

    if source == "NESO_EAC_AUCTION_RESULTS":
        neso_client = NESOEACClient()
        raw_records = neso_client.fetch_summary_records(limit=limit)
        raw_cache.write_bytes(
            source_id=source,
            dataset="eac-results-summary",
            content=json.dumps(raw_records, sort_keys=True, default=str).encode("utf-8"),
            suffix=".json",
            retrieved_at_utc=retrieved_at_utc,
        )
        parsed = parse_eac_summary_records(
            raw_records,
            source_url=f"{NESO_CKAN_ACTION_BASE_URL}/datastore_search?resource_id={EAC_RESULTS_SUMMARY_RESOURCE_ID}",
            retrieved_at_utc=retrieved_at_utc,
        )
        frame = records_to_dataframe(parsed.accepted)
        manifest = DatasetManifest.from_dataframe(
            dataset="eac_auction_results",
            schema_version="0.1.0",
            frame=frame,
            source_ids=[source],
            source_urls=[f"{NESO_CKAN_ACTION_BASE_URL}/datastore_search"],
            retrieved_at_utc=retrieved_at_utc,
            known_at_policy="delivery_start_utc_conservative_until_publication_time_verified",
            validation_status="passed" if not parsed.quarantined else "passed_with_quarantine",
        )
        writer.write(
            dataset="eac_auction_results",
            schema_version="0.1.0",
            frame=frame,
            filename_stem=f"sample_{limit}",
            manifest=manifest,
        )
        typer.echo(
            f"Fetched {len(parsed.accepted)} EAC rows; quarantined={len(parsed.quarantined)}"
        )
        return

    raise typer.BadParameter(f"Unsupported source {source!r}.")


@app.command()
def run_smoke(
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory for the smoke dispatch result."),
    ] = Path("results/runs/phase2_smoke"),
) -> None:
    """Run a tiny network-free energy-only dispatch solve."""

    fixture_path = Path("tests/fixtures/phase2_toy_prices.csv")
    records = _load_fixture_prices(fixture_path)
    asset = AssetConfig(
        name="phase2-reference-2h",
        power_mw=1,
        energy_capacity_mwh=2,
        eta_charge=1,
        eta_discharge=1,
    )
    dispatch_input = build_dispatch_input(
        records,
        asset=asset,
        initial_soc_mwh=1,
        terminal_soc_policy="cyclic",
        binary_dispatch=True,
        data_manifest_ref=str(fixture_path),
        config_hash="phase2-smoke-fixture",
    )
    model = build_energy_dispatch_model(dispatch_input)
    diagnostics = solve_dispatch_model(model)
    result = extract_dispatch_result(model, diagnostics)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_dispatch_result(result, output_dir / "dispatch_result.json")
    typer.echo(
        f"Solved smoke dispatch: revenue_gbp={result.total_revenue_gbp:.2f}, "
        f"solver={result.solver.termination_condition}"
    )


@app.command()
def run_rolling_smoke(
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory for the rolling smoke policy outputs."),
    ] = Path("results/runs/phase2_5_rolling_smoke"),
) -> None:
    """Run a tiny network-free rolling-policy solve with one prior day of history."""

    fixture_path = Path("tests/fixtures/phase2_toy_prices.csv")
    history_records = _load_fixture_prices(fixture_path)
    evaluation_records = [_shift_price_point(point, days=1) for point in history_records]
    records = [*history_records, *evaluation_records]
    asset = AssetConfig(
        name="phase2-5-reference-2h",
        power_mw=1,
        energy_capacity_mwh=2,
        eta_charge=1,
        eta_discharge=1,
    )
    perfect = _solve_perfect_foresight(evaluation_records, asset)
    rolling = run_rolling_policy(
        prices=records,
        asset=asset,
        initial_soc_mwh=1,
        forecast_model=PreviousDaySamePeriodForecast(),
        config=RollingConfig(
            horizon_periods=len(evaluation_records),
            step_periods=1,
            terminal_soc_policy="target",
            terminal_soc_target_mwh=1,
            evaluation_start_utc=evaluation_records[0].delivery_start_utc,
        ),
    )
    evaluation = evaluate_rolling_policy(
        rolling,
        perfect_foresight_revenue_gbp=perfect.total_revenue_gbp,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_dispatch_result(perfect, output_dir / "perfect_foresight_dispatch.json")
    _write_rolling_run(rolling, output_dir / "rolling_run.json")
    (output_dir / "policy_evaluation.json").write_text(
        evaluation.model_dump_json(indent=2),
        encoding="utf-8",
    )
    capture = "n/a" if evaluation.capture_ratio is None else f"{evaluation.capture_ratio:.3f}"
    typer.echo(
        f"Solved rolling smoke: realised_gbp={rolling.realised_revenue_gbp:.2f}, "
        f"perfect_gbp={perfect.total_revenue_gbp:.2f}, capture_ratio={capture}"
    )


@app.command()
def run_market_stack_smoke(
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory for the Phase 3 market-stack smoke outputs."),
    ] = Path("results/runs/phase3_market_stack_smoke"),
) -> None:
    """Run a tiny network-free energy + EAC + CM smoke calculation."""

    fixture_path = Path("tests/fixtures/phase2_toy_prices.csv")
    records = _load_fixture_prices(fixture_path)
    asset = AssetConfig(
        name="phase3-reference-2h",
        power_mw=1,
        energy_capacity_mwh=2,
        eta_charge=1,
        eta_discharge=1,
    )
    eac_matrix = synthetic_single_service_matrix(
        product_source_label="DCL",
        product_model_label="dynamic_containment_low",
        direction_model_label="upward",
        price_gbp_per_mw_h=50,
        duration_h=0.5,
        modelling_caveat="synthetic price-taking EAC availability proxy",
    )
    market_stack = solve_market_stack(
        prices=records,
        eac_price_matrix=eac_matrix,
        asset=asset,
        initial_soc_mwh=1,
        terminal_soc_policy="cyclic",
    )
    cm_scenarios = load_cm_scenarios(Path("configs/scenarios_cm.yaml"))
    cm_revenue = calculate_cm_annual_revenue(
        cm_scenarios.by_key(
            auction_type="T-1",
            delivery_year="2025/26",
            asset_duration_hours=2,
        )
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_eac_price_matrix(eac_matrix, output_dir / "eac_price_matrix.json")
    _write_market_stack_result(market_stack, output_dir / "market_stack_result.json")
    _write_cm_annual_revenue(cm_revenue, output_dir / "cm_annual_summary.json")
    typer.echo(
        f"Solved market-stack smoke: total_gbp={market_stack.total_revenue_gbp:.2f}, "
        f"energy_gbp={market_stack.energy_revenue_gbp:.2f}, "
        f"service_gbp={market_stack.service_revenue_gbp:.2f}, "
        f"cm_annual_gbp={cm_revenue.annual_revenue_gbp:.2f}"
    )


@app.command()
def build_phase4_aligned_cache(
    start: Annotated[
        str,
        typer.Option(help="UTC start timestamp for the aligned Elexon/NESO window."),
    ] = "2026-04-01T00:00:00Z",
    days: Annotated[int, typer.Option(help="Number of calendar days to fetch.")] = 7,
    provider: Annotated[
        str,
        typer.Option(help="Single Elexon MID provider to use for the release cache."),
    ] = "APXMIDP",
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory for aligned source cache JSON files."),
    ] = Path("results/runs/release_cache/aligned_sources"),
    neso_page_size: Annotated[
        int,
        typer.Option(help="NESO CKAN SQL page size."),
    ] = 5000,
) -> None:
    """Fetch and write an aligned public-source cache for longer Phase 4 runs."""

    if days <= 0:
        raise typer.BadParameter("days must be positive.")
    start_utc = parse_source_datetime(start)
    request = AlignedCacheRequest(
        start_utc=start_utc,
        end_utc=start_utc + timedelta(days=days),
        elexon_provider=provider,
        neso_page_size=neso_page_size,
    )
    cache = fetch_aligned_phase4_cache(request)
    paths = write_aligned_phase4_cache(cache, output_dir)
    typer.echo(
        "Built aligned Phase 4 cache: "
        f"periods={len(cache.sample.prices)}, "
        f"hours={cache.sample.sample_hours:.1f}, "
        f"manifest={paths['aligned_manifest']}"
    )


@app.command()
def run_release_cache(
    start: Annotated[
        str,
        typer.Option(help="UTC start timestamp if fetching aligned sources."),
    ] = "2026-04-01T00:00:00Z",
    days: Annotated[int, typer.Option(help="Number of calendar days to fetch.")] = 7,
    aligned_cache_dir: Annotated[
        Path | None,
        typer.Option(help="Existing aligned source cache directory to reuse."),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory for release run outputs."),
    ] = Path("results/runs/release_cache"),
    dashboard_dir: Annotated[
        Path,
        typer.Option(help="Directory for release dashboard cache outputs."),
    ] = Path("results/dashboard/release"),
    provider: Annotated[
        str,
        typer.Option(help="Single Elexon MID provider to use when fetching."),
    ] = "APXMIDP",
    reference_assets_yaml: Annotated[
        Path,
        typer.Option(help="Reference asset registry YAML."),
    ] = Path("configs/reference_assets.yaml"),
    asset_id: Annotated[
        str,
        typer.Option(help="Reference asset id for the OpenBESS Stack Index run."),
    ] = "openbess_canonical_1mw_2mwh",
    finance_assumptions_yaml: Annotated[
        Path | None,
        typer.Option(help="Optional YAML file overriding finance assumptions."),
    ] = Path("configs/finance_assumptions.yaml"),
    cm_scenarios_yaml: Annotated[
        Path,
        typer.Option(help="Capacity Market scenario YAML."),
    ] = Path("configs/scenarios_cm.yaml"),
    horizon_periods: Annotated[
        int,
        typer.Option(help="Rolling solve horizon in settlement periods."),
    ] = 48,
    step_periods: Annotated[
        int,
        typer.Option(help="Executed periods per rolling solve."),
    ] = 48,
) -> None:
    """Run a longer cached OpenBESS Stack Index release preview."""

    if days <= 0:
        raise typer.BadParameter("days must be positive.")
    if horizon_periods <= 0 or step_periods <= 0:
        raise typer.BadParameter("horizon_periods and step_periods must be positive.")

    output_dir.mkdir(parents=True, exist_ok=True)
    if aligned_cache_dir is None:
        start_utc = parse_source_datetime(start)
        aligned = fetch_aligned_phase4_cache(
            AlignedCacheRequest(
                start_utc=start_utc,
                end_utc=start_utc + timedelta(days=days),
                elexon_provider=provider,
            )
        )
        aligned_cache_dir = output_dir / "aligned_sources"
        write_aligned_phase4_cache(aligned, aligned_cache_dir)
    else:
        aligned = load_aligned_phase4_cache(aligned_cache_dir)

    sample = aligned.sample
    registry = load_reference_assets(reference_assets_yaml)
    reference = registry.assets[asset_id]
    asset = reference.asset
    initial_soc_mwh = (asset.soc_min_mwh + cast(float, asset.soc_max_mwh)) / 2
    rolling_config = RollingConfig(
        horizon_periods=min(horizon_periods, len(sample.prices)),
        step_periods=min(step_periods, len(sample.prices)),
        terminal_soc_policy="target",
        terminal_soc_target_mwh=initial_soc_mwh,
    )
    forecast_model = PreviousDaySamePeriodForecast()
    rolling_run = run_rolling_market_stack_policy(
        prices=sample.prices,
        eac_price_matrix=sample.eac_price_matrix,
        asset=asset,
        initial_soc_mwh=initial_soc_mwh,
        forecast_model=forecast_model,
        config=rolling_config,
    )
    capture = run_phase4_market_stack_capture_comparison(
        prices=sample.prices,
        eac_price_matrix=sample.eac_price_matrix,
        asset=asset,
        initial_soc_mwh=initial_soc_mwh,
        rolling_run=rolling_run,
        terminal_soc_policy=rolling_config.terminal_soc_policy,  # type: ignore[arg-type]
        terminal_soc_target_mwh=rolling_config.terminal_soc_target_mwh,
        solver_config=rolling_config.solver,
    )
    smoke_window_comparisons = run_phase4_smoke_window_comparisons(
        prices=sample.prices,
        eac_price_matrix=sample.eac_price_matrix,
        asset=asset,
        initial_soc_mwh=initial_soc_mwh,
        forecast_model=forecast_model,
        config=rolling_config,
        window_day_counts=[1, 2, 7],
    )
    sweep = run_phase4_market_stack_sweep(
        prices=sample.prices,
        eac_price_matrix=sample.eac_price_matrix,
        asset=asset,
        initial_soc_mwh=initial_soc_mwh,
        forecast_model=forecast_model,
        config=rolling_config,
        scenarios=default_phase4_market_stack_scenarios(),
    )
    forecast_error_results = run_phase4_forecast_error_sweep(
        prices=sample.prices,
        eac_price_matrix=sample.eac_price_matrix,
        asset=asset,
        initial_soc_mwh=initial_soc_mwh,
        forecast_model=forecast_model,
        config=rolling_config,
        scenarios=default_phase4_forecast_error_scenarios(),
    )
    cm_label, cm_value, cm_source_id, cm_source_url, cm_notes = _cm_sidecar_for_asset(
        cm_scenarios_yaml=cm_scenarios_yaml,
        asset_duration_hours=reference.cm_duration_hours,
    )
    finance_assumptions = load_phase4_finance_assumptions(finance_assumptions_yaml)
    caveats = [
        *sample.caveats,
        "Release cache outputs remain preview-labelled until coverage gates pass.",
        "Capacity Market value is an annual scenario sidecar.",
    ]
    write_phase4_dashboard_cache(
        Phase4DashboardCacheInput(
            run_id=f"release_cache_{sample.label}",
            rolling_run=rolling_run,
            central_capture=capture,
            smoke_comparisons=smoke_window_comparisons,
            scenario_results=sweep.scenario_results,
            caveats=caveats,
            config_hash=f"release-cache:{asset_id}:{rolling_config.model_dump_json()}",
            source_snapshot_hash=sample.source_snapshot_hash,
            input_run_ids=[sample.label],
            source_ids=sample.source_ids,
            source_labels=sample.source_labels,
            known_at_policy="elexon_mid_delivery_end_and_neso_eac_delivery_start_conservative",
            battery_energy_capacity_mwh=asset.energy_capacity_mwh,
            battery_power_mw=asset.power_mw,
            stack_series_asset_id=asset_id,
            finance_assumptions=finance_assumptions,
            cm_annual_scenario_gbp_per_mw_year=cm_value,
            cm_scenario_label=cm_label,
            cm_scenario_source_id=cm_source_id,
            cm_scenario_source_url=cm_source_url,
            cm_scenario_notes=cm_notes,
            forecast_error_results=forecast_error_results,
            source_snapshot=aligned.manifest,
        ),
        dashboard_dir,
    )
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "sample_label": sample.label,
                "period_count": len(sample.prices),
                "sample_hours": sample.sample_hours,
                "asset_id": asset_id,
                "rolling_total_revenue_gbp": rolling_run.realised_total_revenue_gbp,
                "perfect_total_revenue_gbp": capture.perfect_total_revenue_gbp,
                "capture_ratio": capture.capture_ratio,
                "dashboard_cache_dir": str(dashboard_dir),
                "aligned_cache_dir": str(aligned_cache_dir),
                "cm_scenario_label": cm_label,
                "cm_annual_scenario_gbp_per_mw_year": cm_value,
                "cm_scenario_source_id": cm_source_id,
                "cm_scenario_source_url": cm_source_url,
                "cm_scenario_notes": cm_notes,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    typer.echo(
        "Built release cache: "
        f"periods={len(sample.prices)}, "
        f"rolling_total_gbp={rolling_run.realised_total_revenue_gbp:.2f}, "
        f"dashboard={dashboard_dir}"
    )


@app.command()
def run_phase4_smoke(
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory for the Phase 4 rolling revenue-stack outputs."),
    ] = Path("results/runs/phase4_revenue_stack"),
    dashboard_dir: Annotated[
        Path,
        typer.Option(help="Directory for dashboard-ready cached Phase 4 outputs."),
    ] = Path("results/dashboard"),
    elexon_mid_fixture: Annotated[
        Path | None,
        typer.Option(help="Override Elexon MID JSON fixture for the aligned historical sample."),
    ] = None,
    neso_eac_fixture: Annotated[
        Path | None,
        typer.Option(help="Override NESO EAC JSON fixture for the aligned historical sample."),
    ] = None,
    finance_assumptions_yaml: Annotated[
        Path | None,
        typer.Option(help="Optional YAML file overriding Phase 5 finance assumptions."),
    ] = None,
) -> None:
    """Run a network-free Phase 4 commercial smoke scenario from historical fixtures."""

    finance_assumptions = load_phase4_finance_assumptions(finance_assumptions_yaml)
    sample = load_phase4_historical_sample(
        elexon_mid_path=elexon_mid_fixture,
        neso_eac_path=neso_eac_fixture,
    )
    prices = sample.prices
    eac_matrix = sample.eac_price_matrix
    commercial = CommercialBessSystem(
        name="phase4-commercial-reference",
        battery_capacity_mwh=10,
        inverter_power_mw=5,
        site_export_limit_mw=3,
        battery_capex_gbp_per_mwh=210_000,
        inverter_capex_gbp_per_mw=90_000,
        installation_cost_gbp=125_000,
        grid_connection_cost_gbp=75_000,
    )
    asset = AssetConfig(
        name=commercial.name,
        power_mw=commercial.effective_export_limit_mw,
        energy_capacity_mwh=commercial.battery_capacity_mwh,
        eta_charge=1,
        eta_discharge=1,
    )
    horizon_periods = min(4, len(prices))
    rolling_config = RollingConfig(
        horizon_periods=horizon_periods,
        step_periods=1,
        terminal_soc_policy="target",
        terminal_soc_target_mwh=5,
    )
    rolling_run = run_rolling_market_stack_policy(
        prices=prices,
        eac_price_matrix=eac_matrix,
        asset=asset,
        initial_soc_mwh=5,
        forecast_model=PreviousDaySamePeriodForecast(),
        config=rolling_config,
    )
    capture = run_phase4_market_stack_capture_comparison(
        prices=prices,
        eac_price_matrix=eac_matrix,
        asset=asset,
        initial_soc_mwh=5,
        rolling_run=rolling_run,
        terminal_soc_policy=rolling_config.terminal_soc_policy,  # type: ignore[arg-type]
        terminal_soc_target_mwh=rolling_config.terminal_soc_target_mwh,
        solver_config=rolling_config.solver,
    )
    smoke_window_comparisons = run_phase4_smoke_window_comparisons(
        prices=prices,
        eac_price_matrix=eac_matrix,
        asset=asset,
        initial_soc_mwh=5,
        forecast_model=PreviousDaySamePeriodForecast(),
        config=rolling_config,
        window_day_counts=[1, 2],
    )
    skipped_smoke_windows = skipped_phase4_smoke_windows(
        prices=prices,
        window_day_counts=[1, 2],
    )
    skipped_smoke_window_caveats = [
        (
            f"{skip.label} smoke comparison skipped: requires "
            f"{skip.required_period_count} periods, historical sample contains "
            f"{skip.available_period_count}."
        )
        for skip in skipped_smoke_windows
    ]
    short_sample_policy_caveat = (
        "The default Phase 4 historical smoke fixture is 2.5h; it validates source "
        "alignment and EAC known-at exclusion, not 24h wholesale forecast-policy performance."
    )
    phase4_caveats = [
        *sample.caveats,
        short_sample_policy_caveat,
        *skipped_smoke_window_caveats,
        "EAC revenue is a price-taking availability proxy.",
        "Capacity Market and Balancing Mechanism value are not included.",
    ]
    sweep = run_phase4_market_stack_sweep(
        prices=prices,
        eac_price_matrix=eac_matrix,
        asset=asset,
        initial_soc_mwh=5,
        forecast_model=PreviousDaySamePeriodForecast(),
        config=RollingConfig(
            horizon_periods=horizon_periods,
            step_periods=1,
            terminal_soc_policy="target",
            terminal_soc_target_mwh=5,
        ),
        scenarios=default_phase4_market_stack_scenarios(),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_price_points(prices, output_dir / "historical_prices.csv")
    _write_rolling_market_stack_run(rolling_run, output_dir / "rolling_market_stack_run.json")
    (output_dir / "policy_capture.json").write_text(
        capture.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (output_dir / "smoke_window_comparisons.json").write_text(
        json.dumps(
            {
                "comparisons": [
                    comparison.model_dump(mode="json") for comparison in smoke_window_comparisons
                ],
                "skipped_windows": [
                    skipped.model_dump(mode="json") for skipped in skipped_smoke_windows
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "phase4_scenario_sweep.json").write_text(
        sweep.model_dump_json(indent=2),
        encoding="utf-8",
    )
    write_investor_workbook(
        InvestorWorkbookInput(
            commercial_system=commercial,
            rolling_run=rolling_run,
            scenario_results=sweep.scenario_results,
            assumptions={
                "historical_sample_label": sample.label,
                "sample_hours": sample.sample_hours,
                "wholesale_source": sample.source_labels["wholesale"],
                "eac_source": sample.source_labels["eac"],
                "rolling_policy_horizon_periods": rolling_config.horizon_periods,
                "rolling_policy_step_periods": rolling_config.step_periods,
                "smoke_window_skipped_count": len(skipped_smoke_windows),
            },
            caveats=[
                *phase4_caveats,
                "Workbook values are release smoke outputs, not investment advice.",
            ],
        ),
        output_dir / "gb_bess_investor_phase4_workbook.xlsx",
    )
    write_phase4_dashboard_cache(
        Phase4DashboardCacheInput(
            run_id="phase4_revenue_stack_smoke",
            rolling_run=rolling_run,
            central_capture=capture,
            smoke_comparisons=smoke_window_comparisons,
            scenario_results=sweep.scenario_results,
            caveats=phase4_caveats,
            config_hash="phase4-smoke-historical-fixture-config",
            source_snapshot_hash=sample.source_snapshot_hash,
            input_run_ids=["phase4_revenue_stack_smoke"],
            source_ids=sample.source_ids,
            source_labels=sample.source_labels,
            known_at_policy="historical_fixture_source_known_at_policy",
            battery_energy_capacity_mwh=commercial.battery_capacity_mwh,
            battery_power_mw=commercial.effective_export_limit_mw,
            stack_series_asset_id=commercial.name,
            capex_gbp=commercial.total_capex_gbp,
            finance_assumptions=finance_assumptions,
        ),
        dashboard_dir,
    )
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "historical_sample_label": sample.label,
                "sample_hours": sample.sample_hours,
                "period_count": len(prices),
                "battery_size_mwh": commercial.battery_capacity_mwh,
                "power_rating_mw": commercial.inverter_power_mw,
                "export_limit_mw": commercial.effective_export_limit_mw,
                "capex_gbp": commercial.total_capex_gbp,
                "rolling_total_revenue_gbp": rolling_run.realised_total_revenue_gbp,
                "perfect_total_revenue_gbp": capture.perfect_total_revenue_gbp,
                "capture_ratio": capture.capture_ratio,
                "dashboard_cache_dir": str(dashboard_dir),
                "scenario_count": len(sweep.scenario_results),
                "rolling_policy_horizon_periods": rolling_config.horizon_periods,
                "rolling_policy_step_periods": rolling_config.step_periods,
                "smoke_window_comparison_count": len(smoke_window_comparisons),
                "smoke_window_skipped_windows": [
                    skipped.model_dump(mode="json") for skipped in skipped_smoke_windows
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    typer.echo(
        f"Solved Phase 4 historical smoke: periods={len(prices)}, "
        f"rolling_total_gbp={rolling_run.realised_total_revenue_gbp:.2f}, "
        f"workbook={output_dir / 'gb_bess_investor_phase4_workbook.xlsx'}"
    )


@app.command()
def run_residential_household_smoke(
    profile_csv: Annotated[
        Path,
        typer.Option(help="Household load/PV profile CSV."),
    ] = Path("tests/fixtures/residential_household_profile.csv"),
    tariff_csv: Annotated[
        Path,
        typer.Option(help="Retail tariff CSV."),
    ] = Path("tests/fixtures/residential_tariff.csv"),
    output_dir: Annotated[
        Path,
        typer.Option(help="Output directory."),
    ] = Path("results/runs/residential_household_smoke"),
) -> None:
    """Run a network-free residential household load/PV/tariff smoke solve."""

    profile = load_household_profile_csv(profile_csv)
    tariff = load_tariff_csv(tariff_csv)
    system = get_residential_preset("tesla_powerwall_3")
    result = solve_residential_household_dispatch(
        ResidentialHouseholdDispatchInput(
            system=system,
            intervals=profile,
            tariff=tariff,
            dno_export_limit_kw=3.68,
            initial_soc_kwh=system.battery_capacity_kwh * 0.5,
            terminal_soc_policy="cyclic",
            round_trip_efficiency=0.89,
            allow_grid_charging=True,
            allow_grid_charged_export=False,
        )
    )
    payback = calculate_residential_household_payback_from_dispatch(
        system,
        dispatch=result,
        sample_hours=sum(row.duration_h for row in profile),
        dno_export_limit_kw=3.68,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "branch_name": "residential",
                "system_name": system.name,
                "total_bill_savings_gbp": result.total_bill_savings_gbp,
                "vpp_revenue_gbp": 0
                if result.vpp_revenue is None
                else result.vpp_revenue.total_vpp_revenue_gbp,
                "annualised_benefit_gbp": payback.total_annual_benefit_gbp,
                "simple_payback_years": payback.simple_payback_years,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_residential_dispatch_csv(result, output_dir / "dispatch.csv")
    typer.echo(
        f"Solved residential household smoke: savings_gbp={result.total_bill_savings_gbp:.2f}"
    )


def _best_residential_payback_result(
    results: list[ResidentialPaybackScenarioResult],
) -> ResidentialPaybackScenarioResult | None:
    finite = [result for result in results if result.payback.simple_payback_years is not None]
    if not finite:
        return None
    return min(
        finite,
        key=lambda result: (
            result.payback.simple_payback_years
            if result.payback.simple_payback_years is not None
            else float("inf")
        ),
    )


@app.command()
def run_residential_scenario_sweep(
    output_dir: Annotated[
        Path,
        typer.Option(help="Output directory for residential scenario sweep outputs."),
    ] = Path("results/runs/residential_scenario_sweep"),
) -> None:
    """Run the default residential payback scenario sweep."""

    results = run_residential_payback_scenarios()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "residential_scenario_sweep.json").write_text(
        json.dumps([result.model_dump(mode="json") for result in results], indent=2),
        encoding="utf-8",
    )
    best = _best_residential_payback_result(results)
    if best is None:
        typer.echo(f"Solved residential scenario sweep: scenarios={len(results)}, best_payback=n/a")
    else:
        typer.echo(
            "Solved residential scenario sweep: "
            f"scenarios={len(results)}, best_payback={best.scenario_name}"
        )


@app.command()
def build_stack_series(
    cache_dir: Annotated[
        Path,
        typer.Option(help="Directory containing cached stack_series.parquet input."),
    ] = Path("results/dashboard"),
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory for OpenBESS Stack Index CSV/parquet exports."),
    ] = Path("results/dashboard"),
) -> None:
    """Build OpenBESS Stack Index exports from cached stack-series rows."""

    import pandas as pd

    input_path = cache_dir / "stack_series.parquet"
    if not input_path.is_file():
        raise typer.BadParameter(f"Missing cached stack series parquet: {input_path}")

    frame = pd.read_parquet(input_path)
    rows = _validate_stack_series_records(frame.to_dict(orient="records"))
    paths = write_stack_series(rows, output_dir)
    typer.echo(
        "Built OpenBESS Stack Index exports: "
        f"rows={len(rows)}, parquet={paths['parquet']}, csv={paths['csv']}"
    )


def _validate_stack_series_records(records: list[dict[str, object]]) -> list[StackSeriesRow]:
    rows: list[StackSeriesRow] = []
    for row_index, record in enumerate(records):
        try:
            rows.append(StackSeriesRow.model_validate(_normalise_stack_series_record(record)))
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(
                f"Invalid stack_series row {row_index}: caveat_flags is not valid JSON."
            ) from exc
        except ValidationError as exc:
            raise typer.BadParameter(
                f"Invalid stack_series row {row_index}: {exc.errors()[0]['msg']}"
            ) from exc
    return rows


def _normalise_stack_series_record(record: dict[str, object]) -> dict[str, object]:
    normalised = dict(record)
    normalised.pop("gross_operating_value_gbp", None)
    normalised.pop("degradation_adjusted_value_gbp", None)

    caveat_flags = normalised.get("caveat_flags")
    if isinstance(caveat_flags, str):
        normalised["caveat_flags"] = json.loads(caveat_flags)
    elif caveat_flags is not None and not isinstance(caveat_flags, list):
        tolist = getattr(caveat_flags, "tolist", None)
        if callable(tolist):
            caveat_flags = tolist()
        normalised["caveat_flags"] = list(cast(Iterable[object], caveat_flags))

    cm_value = normalised.get("cm_annual_scenario_gbp_per_mw_year")
    if isinstance(cm_value, float) and math.isnan(cm_value):
        normalised["cm_annual_scenario_gbp_per_mw_year"] = None
    return normalised


def _cm_sidecar_for_asset(
    *,
    cm_scenarios_yaml: Path,
    asset_duration_hours: float | None,
) -> tuple[str | None, float | None, str | None, str | None, str | None]:
    if asset_duration_hours is None or not cm_scenarios_yaml.is_file():
        return None, None, None, None, None
    scenarios = [
        scenario
        for scenario in load_cm_scenarios(cm_scenarios_yaml).scenarios
        if abs(scenario.asset_duration_hours - asset_duration_hours) <= 1e-9
    ]
    if not scenarios:
        return None, None, None, None, None
    selected = next(
        (scenario for scenario in scenarios if scenario.auction_type == "T-4"),
        scenarios[0],
    )
    annual_value = selected.derating_factor * selected.clearing_price_gbp_per_kw_year * 1000
    return (
        selected.scenario_name,
        annual_value,
        selected.source_id,
        selected.source_url,
        selected.notes,
    )


def _load_fixture_prices(path: Path) -> list[WholesalePricePoint]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    records: list[WholesalePricePoint] = []
    for index, row in enumerate(rows, start=1):
        start = parse_source_datetime(row["delivery_start_utc"])
        end = parse_source_datetime(row["delivery_end_utc"])
        records.append(
            WholesalePricePoint(
                delivery_start_utc=start,
                delivery_end_utc=end,
                settlement_date=row.get("settlement_date", start.date().isoformat()),
                settlement_period=int(row.get("settlement_period", index)),
                duration_h=float(row["duration_h"]),
                price_gbp_per_mwh=float(row["price_gbp_per_mwh"]),
                price_source_type="SYNTHETIC_TEST",
                is_proxy=False,
                known_at_utc=end,
                retrieved_at_utc=datetime.now(UTC),
                source_id="PROJECT_CONVENTION",
                source_url=str(path),
                schema_version="0.1.0",
                quality_flag="ok",
            )
        )
    return records


def _shift_price_point(point: WholesalePricePoint, *, days: int) -> WholesalePricePoint:
    shifted_start = point.delivery_start_utc + timedelta(days=days)
    shifted_end = point.delivery_end_utc + timedelta(days=days)
    return point.model_copy(
        update={
            "delivery_start_utc": shifted_start,
            "delivery_end_utc": shifted_end,
            "settlement_date": shifted_start.date().isoformat(),
            "known_at_utc": point.known_at_utc + timedelta(days=days),
            "retrieved_at_utc": point.retrieved_at_utc + timedelta(days=days),
        }
    )


def _solve_perfect_foresight(
    records: list[WholesalePricePoint],
    asset: AssetConfig,
) -> DispatchResult:
    dispatch_input = build_dispatch_input(
        records,
        asset=asset,
        initial_soc_mwh=1,
        terminal_soc_policy="cyclic",
        binary_dispatch=True,
        data_manifest_ref="phase2_5_rolling_smoke",
        config_hash="phase2-5-perfect-foresight-smoke",
    )
    model = build_energy_dispatch_model(dispatch_input)
    diagnostics = solve_dispatch_model(model)
    return extract_dispatch_result(model, diagnostics)


def _write_dispatch_result(result: DispatchResult, path: Path) -> None:
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")


def _write_rolling_run(result: RollingRun, path: Path) -> None:
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")


def _write_eac_price_matrix(result: EACPriceMatrix, path: Path) -> None:
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")


def _write_market_stack_result(result: MarketStackResult, path: Path) -> None:
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")


def _write_cm_annual_revenue(result: CMAnnualRevenue, path: Path) -> None:
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")


def _write_rolling_market_stack_run(result: RollingMarketStackRun, path: Path) -> None:
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")


def _write_price_points(records: list[WholesalePricePoint], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "delivery_start_utc",
                "delivery_end_utc",
                "settlement_date",
                "settlement_period",
                "duration_h",
                "price_gbp_per_mwh",
            ],
        )
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "delivery_start_utc": record.delivery_start_utc.isoformat(),
                    "delivery_end_utc": record.delivery_end_utc.isoformat(),
                    "settlement_date": record.settlement_date,
                    "settlement_period": record.settlement_period,
                    "duration_h": record.duration_h,
                    "price_gbp_per_mwh": record.price_gbp_per_mwh,
                }
            )


def _write_residential_dispatch_csv(
    result: ResidentialHouseholdDispatchResult,
    path: Path,
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "delivery_start_utc",
                "delivery_end_utc",
                "load_kwh",
                "pv_generation_kwh",
                "grid_to_load_kwh",
                "grid_to_battery_kwh",
                "pv_to_load_kwh",
                "pv_to_battery_kwh",
                "pv_to_export_kwh",
                "battery_to_load_kwh",
                "battery_to_export_kwh",
                "site_export_kwh",
                "pv_curtailed_kwh",
                "soc_start_kwh",
                "soc_end_kwh",
                "period_bill_gbp",
            ],
        )
        writer.writeheader()
        for row in result.rows:
            writer.writerow(
                {
                    "delivery_start_utc": row.delivery_start_utc.isoformat(),
                    "delivery_end_utc": row.delivery_end_utc.isoformat(),
                    "load_kwh": row.load_kwh,
                    "pv_generation_kwh": row.pv_generation_kwh,
                    "grid_to_load_kwh": row.grid_to_load_kwh,
                    "grid_to_battery_kwh": row.grid_to_battery_kwh,
                    "pv_to_load_kwh": row.pv_to_load_kwh,
                    "pv_to_battery_kwh": row.pv_to_battery_kwh,
                    "pv_to_export_kwh": row.pv_to_export_kwh,
                    "battery_to_load_kwh": row.battery_to_load_kwh,
                    "battery_to_export_kwh": row.battery_to_export_kwh,
                    "site_export_kwh": row.site_export_kwh,
                    "pv_curtailed_kwh": row.pv_curtailed_kwh,
                    "soc_start_kwh": row.soc_start_kwh,
                    "soc_end_kwh": row.soc_end_kwh,
                    "period_bill_gbp": row.period_bill_gbp,
                }
            )
