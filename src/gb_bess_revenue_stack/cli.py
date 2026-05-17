from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

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
from gb_bess_revenue_stack.schemas.base import parse_source_datetime

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
