from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from gb_bess_revenue_stack.schemas.base import (
    QuarantinedRecord,
    ensure_aware_utc,
    parse_source_datetime,
)
from gb_bess_revenue_stack.schemas.market import EACAuctionResult

NESO_CKAN_ACTION_BASE_URL = "https://api.neso.energy/api/3/action"
EAC_RESULTS_SUMMARY_RESOURCE_ID = "596f29ac-0387-4ba4-a6d3-95c243140707"


PRODUCT_MAP: dict[str, tuple[str, str]] = {
    "DCL": ("dynamic_containment_low", "upward"),
    "DCH": ("dynamic_containment_high", "downward"),
    "DML": ("dynamic_moderation_low", "upward"),
    "DMH": ("dynamic_moderation_high", "downward"),
    "DRL": ("dynamic_regulation_low", "upward"),
    "DRH": ("dynamic_regulation_high", "downward"),
    "PQR": ("positive_quick_reserve", "upward"),
    "NQR": ("negative_quick_reserve", "downward"),
    "PSR": ("positive_slow_reserve", "upward"),
    "NSR": ("negative_slow_reserve", "downward"),
}


@dataclass(frozen=True)
class ParsedEACRecords:
    accepted: list[EACAuctionResult] = field(default_factory=list)
    quarantined: list[QuarantinedRecord] = field(default_factory=list)


class NESOEACClient:
    """Bounded CKAN datastore client for NESO EAC auction-result resources."""

    def __init__(
        self,
        *,
        action_base_url: str = NESO_CKAN_ACTION_BASE_URL,
        timeout_seconds: float = 20,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.action_base_url = action_base_url.rstrip("/")
        self._owns_client = http_client is None
        self.http_client = http_client or httpx.Client(timeout=timeout_seconds)

    def close(self) -> None:
        if self._owns_client:
            self.http_client.close()

    @retry(wait=wait_exponential(multiplier=0.25, max=2), stop=stop_after_attempt(3), reraise=True)
    def fetch_summary_records(
        self,
        *,
        limit: int = 100,
        resource_id: str = EAC_RESULTS_SUMMARY_RESOURCE_ID,
    ) -> list[dict[str, Any]]:
        if limit <= 0:
            msg = "limit must be positive."
            raise ValueError(msg)
        response = self.http_client.get(
            f"{self.action_base_url}/datastore_search",
            params={"resource_id": resource_id, "limit": str(limit)},
        )
        response.raise_for_status()
        payload = response.json()
        records = payload.get("result", {}).get("records", [])
        if not isinstance(records, list):
            msg = "NESO datastore response did not contain a records list."
            raise ValueError(msg)
        return [dict(record) for record in records]


def parse_eac_summary_records(
    records: list[dict[str, Any]],
    *,
    source_url: str,
    retrieved_at_utc: datetime,
) -> ParsedEACRecords:
    retrieved_at_utc = ensure_aware_utc(retrieved_at_utc)
    accepted: list[EACAuctionResult] = []
    quarantined: list[QuarantinedRecord] = []
    for raw in records:
        product = str(raw.get("auctionProduct", "")).strip()
        mapping = PRODUCT_MAP.get(product)
        if mapping is None:
            quarantined.append(
                QuarantinedRecord(
                    reason="unknown_product_label",
                    source_id="NESO_EAC_AUCTION_RESULTS",
                    source_record=raw,
                )
            )
            continue
        product_model_label, direction_model_label = mapping
        delivery_start = parse_source_datetime(str(raw["deliveryStart"]))
        delivery_end = parse_source_datetime(str(raw["deliveryEnd"]))
        auction_id = str(raw.get("auctionID", "unknown"))
        cleared_volume = (
            float(raw["clearedVolume"]) if raw.get("clearedVolume") is not None else None
        )
        accepted.append(
            EACAuctionResult(
                product_source_label=product,
                product_model_label=product_model_label,
                direction_source_label=product,
                direction_model_label=direction_model_label,  # type: ignore[arg-type]
                delivery_start_utc=delivery_start,
                delivery_end_utc=delivery_end,
                known_at_utc=delivery_start,
                clearing_price_gbp_per_mw_h=float(raw["clearingPrice"]),
                procured_mw=cleared_volume,
                accepted_mw=cleared_volume,
                block_id=_optional_str(raw.get("linkedServiceWindowID")),
                service_type=_optional_str(raw.get("serviceType")),
                retrieved_at_utc=retrieved_at_utc,
                source_id="NESO_EAC_AUCTION_RESULTS",
                source_url=source_url,
                source_record_id=f"{auction_id}:{product}:{delivery_start.isoformat()}",
                schema_version="0.1.0",
                quality_flag="ok",
            )
        )
    return ParsedEACRecords(accepted=accepted, quarantined=quarantined)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    return text
