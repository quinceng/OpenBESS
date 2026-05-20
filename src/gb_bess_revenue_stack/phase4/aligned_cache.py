from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from gb_bess_revenue_stack.data.elexon import (
    ELEXON_BASE_URL,
    MARKET_INDEX_PATH,
    ElexonMIDClient,
)
from gb_bess_revenue_stack.data.neso import (
    EAC_RESULTS_SUMMARY_RESOURCE_ID,
    NESO_CKAN_ACTION_BASE_URL,
    NESOEACClient,
)
from gb_bess_revenue_stack.phase4.scenarios import (
    Phase4HistoricalSample,
    build_phase4_historical_sample_from_source_records,
)
from gb_bess_revenue_stack.schemas.base import ensure_aware_utc, parse_source_datetime


class AlignedPhase4Cache(BaseModel):
    """Longer aligned public-source cache ready for Phase 4 release runs."""

    model_config = ConfigDict(extra="forbid")

    sample: Phase4HistoricalSample
    elexon_payload: dict[str, Any]
    neso_payload: dict[str, Any]
    manifest: dict[str, Any]


class AlignedCacheRequest(BaseModel):
    """Network fetch request for an aligned Elexon/NESO window."""

    model_config = ConfigDict(extra="forbid")

    start_utc: datetime
    end_utc: datetime
    elexon_provider: str = "APXMIDP"
    neso_resource_id: str = EAC_RESULTS_SUMMARY_RESOURCE_ID
    neso_page_size: int = Field(default=5000, gt=0)

    @field_validator("start_utc", "end_utc")
    @classmethod
    def datetimes_are_aware(cls, value: datetime) -> datetime:
        return ensure_aware_utc(value)


def fetch_aligned_phase4_cache(
    request: AlignedCacheRequest,
    *,
    elexon_client: ElexonMIDClient | None = None,
    neso_client: NESOEACClient | None = None,
) -> AlignedPhase4Cache:
    """Fetch public Elexon MID and NESO EAC rows for one aligned release window."""

    if request.end_utc <= request.start_utc:
        msg = "end_utc must be after start_utc."
        raise ValueError(msg)
    elexon = elexon_client or ElexonMIDClient()
    neso = neso_client or NESOEACClient()
    close_elexon = elexon_client is None
    close_neso = neso_client is None
    try:
        elexon_payload = _fetch_elexon_window(
            client=elexon,
            start=request.start_utc,
            end=request.end_utc,
            provider=request.elexon_provider,
        )
        neso_records = neso.fetch_summary_records_for_window(
            start=request.start_utc,
            end=request.end_utc,
            page_size=request.neso_page_size,
            resource_id=request.neso_resource_id,
        )
    finally:
        if close_elexon:
            elexon.close()
        if close_neso:
            neso.close()

    return build_aligned_phase4_cache_from_payloads(
        request=request,
        elexon_payload=elexon_payload,
        neso_records=neso_records,
        retrieved_at_utc=datetime.now(tz=request.start_utc.tzinfo),
    )


def build_aligned_phase4_cache_from_payloads(
    *,
    request: AlignedCacheRequest,
    elexon_payload: dict[str, Any],
    neso_records: list[dict[str, Any]],
    retrieved_at_utc: datetime,
) -> AlignedPhase4Cache:
    """Build an aligned cache object from already retrieved source payloads."""

    retrieved_at_utc = ensure_aware_utc(retrieved_at_utc)
    sorted_neso_records = _sorted_neso_records(neso_records)
    neso_payload = {
        "metadata": {
            "source_id": "NESO_EAC_AUCTION_RESULTS",
            "source_label": "NESO EAC auction results aligned release cache",
            "retrieved_at_utc": retrieved_at_utc.isoformat(),
            "caveats": [
                (
                    "NESO EAC rows use delivery-start known-at convention until exact "
                    "publication timestamps are verified."
                ),
            ],
        },
        "records": sorted_neso_records,
    }
    sample = build_phase4_historical_sample_from_source_records(
        elexon_payload=elexon_payload,
        neso_records=sorted_neso_records,
        elexon_source_url=_elexon_source_url(request),
        neso_source_url=_neso_source_url(request),
        retrieved_at_utc=retrieved_at_utc,
        wholesale_source_label="Elexon BMRS MID aligned release cache",
        eac_source_label="NESO EAC auction results aligned release cache",
        caveats=[
            "Elexon MID is a public wholesale proxy, not an executable traded price.",
            "Aligned release caches retain source gaps and expose them in data-quality outputs.",
        ],
        strict_eac_coverage=False,
    )
    manifest = _aligned_manifest(
        request=request,
        sample=sample,
        elexon_payload=elexon_payload,
        neso_payload=neso_payload,
        retrieved_at_utc=retrieved_at_utc,
    )
    return AlignedPhase4Cache(
        sample=sample,
        elexon_payload=elexon_payload,
        neso_payload=neso_payload,
        manifest=manifest,
    )


def write_aligned_phase4_cache(
    cache: AlignedPhase4Cache,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Write aligned source JSON files and a manifest for later release runs."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = {
        "elexon_mid": root / "elexon_mid.json",
        "neso_eac": root / "neso_eac.json",
        "aligned_manifest": root / "aligned_manifest.json",
    }
    _write_json(paths["elexon_mid"], cache.elexon_payload)
    _write_json(paths["neso_eac"], cache.neso_payload)
    _write_json(paths["aligned_manifest"], cache.manifest)
    return paths


def load_aligned_phase4_cache(cache_dir: str | Path) -> AlignedPhase4Cache:
    """Load a previously generated aligned cache with release-mode gap handling."""

    root = Path(cache_dir)
    elexon_payload = json.loads((root / "elexon_mid.json").read_text(encoding="utf-8"))
    neso_payload = json.loads((root / "neso_eac.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "aligned_manifest.json").read_text(encoding="utf-8"))
    if not isinstance(elexon_payload, dict):
        msg = "elexon_mid.json must contain a JSON object."
        raise ValueError(msg)
    if not isinstance(neso_payload, dict):
        msg = "neso_eac.json must contain a JSON object."
        raise ValueError(msg)
    records = neso_payload.get("records", [])
    if not isinstance(records, list):
        msg = "neso_eac.json must contain a records list."
        raise ValueError(msg)
    request = AlignedCacheRequest(
        start_utc=parse_source_datetime(str(manifest["start_utc"])),
        end_utc=parse_source_datetime(str(manifest["end_utc"])),
        elexon_provider=str(manifest["elexon_provider"]),
        neso_resource_id=str(manifest["neso_resource_id"]),
    )
    sample = build_phase4_historical_sample_from_source_records(
        elexon_payload=elexon_payload,
        neso_records=[dict(record) for record in records if isinstance(record, dict)],
        elexon_source_url=_elexon_source_url(request),
        neso_source_url=_neso_source_url(request),
        retrieved_at_utc=parse_source_datetime(str(manifest["retrieved_at_utc"])),
        wholesale_source_label="Elexon BMRS MID aligned release cache",
        eac_source_label="NESO EAC auction results aligned release cache",
        caveats=list(manifest.get("caveats", [])),
        strict_eac_coverage=False,
    )
    return AlignedPhase4Cache(
        sample=sample,
        elexon_payload=elexon_payload,
        neso_payload=neso_payload,
        manifest=manifest,
    )


def _fetch_elexon_window(
    *,
    client: ElexonMIDClient,
    start: datetime,
    end: datetime,
    provider: str,
) -> dict[str, Any]:
    rows: dict[tuple[str, str, int], dict[str, Any]] = {}
    for chunk_start, chunk_end in _daily_chunks(start, end):
        payload = client.fetch_market_index(start=chunk_start, end=chunk_end, provider=provider)
        for row in _elexon_rows(payload):
            row_start = parse_source_datetime(str(row["startTime"]))
            if not (start <= row_start < end):
                continue
            if str(row.get("dataProvider")) != provider:
                continue
            key = (
                str(row["dataProvider"]),
                str(row["settlementDate"]),
                int(row["settlementPeriod"]),
            )
            rows[key] = dict(row)
    ordered_rows = sorted(
        rows.values(),
        key=lambda row: parse_source_datetime(str(row["startTime"])),
    )
    return {
        "metadata": {
            "source_id": "ELEXON_BMRS_MID",
            "source_label": "Elexon BMRS MID aligned release cache",
            "provider": provider,
            "start_utc": start.isoformat(),
            "end_utc": end.isoformat(),
            "caveats": [
                "Elexon MID is a public wholesale proxy, not an executable traded price.",
            ],
        },
        "data": ordered_rows,
    }


def _daily_chunks(start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    chunks: list[tuple[datetime, datetime]] = []
    chunk_start = ensure_aware_utc(start)
    end = ensure_aware_utc(end)
    while chunk_start < end:
        chunk_end = min(chunk_start + timedelta(days=1), end)
        chunks.append((chunk_start, chunk_end))
        chunk_start = chunk_end
    return chunks


def _elexon_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("data", [])
    if not isinstance(rows, list):
        msg = "Elexon MID payload data must be a list."
        raise ValueError(msg)
    return [dict(row) for row in rows if isinstance(row, dict)]


def _sorted_neso_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [dict(record) for record in records],
        key=lambda record: (
            str(record.get("deliveryStart", "")),
            str(record.get("auctionProduct", "")),
            str(record.get("auctionID", "")),
        ),
    )


def _aligned_manifest(
    *,
    request: AlignedCacheRequest,
    sample: Phase4HistoricalSample,
    elexon_payload: dict[str, Any],
    neso_payload: dict[str, Any],
    retrieved_at_utc: datetime,
) -> dict[str, Any]:
    gap_period_count = sum(
        1
        for period_index in range(len(sample.prices))
        if not sample.eac_price_matrix.available_cells_for_period(period_index)
    )
    return {
        "label": sample.label,
        "start_utc": request.start_utc.isoformat(),
        "end_utc": request.end_utc.isoformat(),
        "retrieved_at_utc": retrieved_at_utc.isoformat(),
        "elexon_provider": request.elexon_provider,
        "neso_resource_id": request.neso_resource_id,
        "source_ids": sample.source_ids,
        "source_labels": sample.source_labels,
        "source_snapshot_hash": sample.source_snapshot_hash,
        "elexon_row_count": len(elexon_payload.get("data", [])),
        "neso_row_count": len(neso_payload.get("records", [])),
        "price_period_count": len(sample.prices),
        "sample_hours": sample.sample_hours,
        "eac_source_gap_period_count": gap_period_count,
        "caveats": sample.caveats,
        "files": {
            "elexon_mid": "elexon_mid.json",
            "neso_eac": "neso_eac.json",
            "aligned_manifest": "aligned_manifest.json",
        },
    }


def _elexon_source_url(request: AlignedCacheRequest) -> str:
    return (
        f"{ELEXON_BASE_URL}{MARKET_INDEX_PATH}"
        f"?dataProviders={request.elexon_provider}"
        f"&from={_query_time(request.start_utc)}"
        f"&to={_query_time(request.end_utc)}"
    )


def _neso_source_url(request: AlignedCacheRequest) -> str:
    return (
        f"{NESO_CKAN_ACTION_BASE_URL}/datastore_search_sql"
        f"?resource_id={request.neso_resource_id}"
        f"&delivery_start_lt={_query_time(request.end_utc)}"
        f"&delivery_end_gt={_query_time(request.start_utc)}"
    )


def _query_time(value: datetime) -> str:
    return ensure_aware_utc(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
