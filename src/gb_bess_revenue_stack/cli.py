from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer

from gb_bess_revenue_stack.commercial import CommercialBessSystem
from gb_bess_revenue_stack.config.models import AssetConfig
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
from gb_bess_revenue_stack.phase4.scenarios import (
    build_realistic_stress_price_profile,
    default_phase4_market_stack_scenarios,
    run_phase4_market_stack_capture_comparison,
    run_phase4_market_stack_sweep,
    run_phase4_smoke_window_comparisons,
)
from gb_bess_revenue_stack.policies.evaluation import evaluate_rolling_policy
from gb_bess_revenue_stack.policies.forecasts import OracleForecast, PreviousDaySamePeriodForecast
from gb_bess_revenue_stack.policies.rolling import RollingConfig, RollingRun, run_rolling_policy
from gb_bess_revenue_stack.policies.rolling_market_stack import (
    RollingMarketStackRun,
    run_rolling_market_stack_policy,
)
from gb_bess_revenue_stack.reporting.dashboard_cache import (
    Phase4DashboardCacheInput,
    write_phase4_dashboard_cache,
)
from gb_bess_revenue_stack.reporting.investor_workbook import (
    InvestorWorkbookInput,
    write_investor_workbook,
)
from gb_bess_revenue_stack.residential import (
    ResidentialHouseholdDispatchInput,
    ResidentialHouseholdDispatchResult,
    calculate_residential_household_payback_from_dispatch,
    get_residential_preset,
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
def run_phase4_smoke(
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory for the Phase 4 rolling revenue-stack outputs."),
    ] = Path("results/runs/phase4_revenue_stack"),
    dashboard_dir: Annotated[
        Path,
        typer.Option(help="Directory for dashboard-ready cached Phase 4 outputs."),
    ] = Path("results/dashboard"),
    day_count: Annotated[
        int,
        typer.Option(help="Synthetic stress-profile day count."),
    ] = 7,
) -> None:
    """Run a network-free Phase 4 commercial rolling revenue-stack smoke scenario."""

    prices = build_realistic_stress_price_profile(
        start_utc=datetime(2024, 1, 1, tzinfo=UTC),
        day_count=day_count,
    )
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
    eac_matrix = synthetic_single_service_matrix(
        product_source_label="DCL",
        product_model_label="dynamic_containment_low",
        direction_model_label="upward",
        price_gbp_per_mw_h=42,
        duration_h=0.5,
        modelling_caveat="synthetic Phase 4 price-taking EAC availability proxy",
    )
    eac_matrix = EACPriceMatrix(
        cells=[
            eac_matrix.cells[0].model_copy(update={"period_index": index})
            for index in range(len(prices))
        ]
    )
    rolling_config = RollingConfig(
        horizon_periods=48,
        step_periods=24,
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
    sweep = run_phase4_market_stack_sweep(
        prices=prices,
        eac_price_matrix=eac_matrix,
        asset=asset,
        initial_soc_mwh=5,
        forecast_model=OracleForecast(),
        config=RollingConfig(
            horizon_periods=48,
            step_periods=48,
            terminal_soc_policy="target",
            terminal_soc_target_mwh=5,
        ),
        scenarios=default_phase4_market_stack_scenarios(),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_price_points(prices, output_dir / "stress_prices.csv")
    _write_rolling_market_stack_run(rolling_run, output_dir / "rolling_market_stack_run.json")
    (output_dir / "policy_capture.json").write_text(
        capture.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (output_dir / "smoke_window_comparisons.json").write_text(
        json.dumps(
            [comparison.model_dump(mode="json") for comparison in smoke_window_comparisons],
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
                "stress_day_count": day_count,
                "wholesale_source": "synthetic Phase 4 stress profile",
                "eac_source": "synthetic EAC availability proxy",
            },
            caveats=[
                "Synthetic stress profile; not a bankability forecast.",
                "EAC revenue is a price-taking availability proxy.",
                "Capacity Market and Balancing Mechanism value are not included in this workbook.",
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
            caveats=[
                "Synthetic stress profile; not a bankability forecast.",
                "EAC revenue is a price-taking availability proxy.",
                "Capacity Market and Balancing Mechanism value are not included.",
            ],
            config_hash="phase4-smoke-synthetic-config",
            source_snapshot_hash="phase4-smoke-synthetic-source",
            input_run_ids=["phase4_revenue_stack_smoke"],
            source_ids=["PROJECT_CONVENTION"],
            source_labels={
                "wholesale": "synthetic Phase 4 stress profile",
                "eac": "synthetic EAC availability proxy",
            },
        ),
        dashboard_dir,
    )
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "day_count": day_count,
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
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    typer.echo(
        f"Solved Phase 4 smoke: days={day_count}, periods={len(prices)}, "
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
