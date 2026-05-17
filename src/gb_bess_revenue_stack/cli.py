from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

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
from gb_bess_revenue_stack.optimisation.inputs import build_dispatch_input
from gb_bess_revenue_stack.optimisation.model_factory import build_energy_dispatch_model
from gb_bess_revenue_stack.optimisation.results import DispatchResult, extract_dispatch_result
from gb_bess_revenue_stack.optimisation.solve import solve_dispatch_model
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


def _write_dispatch_result(result: DispatchResult, path: Path) -> None:
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
