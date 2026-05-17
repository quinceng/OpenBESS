from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from gb_bess_revenue_stack.schemas.base import ensure_aware_utc, parse_source_datetime
from gb_bess_revenue_stack.schemas.market import WholesalePricePoint

ELEXON_BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
MARKET_INDEX_PATH = "/balancing/pricing/market-index"


class ElexonMIDClient:
    """Bounded Elexon Insights API client for Market Index Data."""

    def __init__(
        self,
        *,
        base_url: str = ELEXON_BASE_URL,
        timeout_seconds: float = 20,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._owns_client = http_client is None
        self.http_client = http_client or httpx.Client(timeout=timeout_seconds)

    def close(self) -> None:
        if self._owns_client:
            self.http_client.close()

    @retry(wait=wait_exponential(multiplier=0.25, max=2), stop=stop_after_attempt(3), reraise=True)
    def fetch_market_index(
        self,
        *,
        start: datetime,
        end: datetime,
        provider: str | None = None,
    ) -> dict[str, Any]:
        start = ensure_aware_utc(start)
        end = ensure_aware_utc(end)
        if end <= start:
            msg = "end must be after start."
            raise ValueError(msg)
        params: dict[str, str] = {
            "from": _format_query_time(start),
            "to": _format_query_time(end),
            "format": "json",
        }
        if provider is not None:
            params["dataProviders"] = provider
        response = self.http_client.get(f"{self.base_url}{MARKET_INDEX_PATH}", params=params)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            msg = "Elexon MID response must be a JSON object."
            raise ValueError(msg)
        return payload


def parse_market_index_points(
    payload: dict[str, Any],
    *,
    source_url: str,
    retrieved_at_utc: datetime,
) -> list[WholesalePricePoint]:
    retrieved_at_utc = ensure_aware_utc(retrieved_at_utc)
    raw_records = payload.get("data", [])
    if not isinstance(raw_records, list):
        msg = "Elexon MID payload 'data' must be a list."
        raise ValueError(msg)
    points: list[WholesalePricePoint] = []
    for raw in raw_records:
        if not isinstance(raw, dict):
            msg = "Each Elexon MID row must be an object."
            raise ValueError(msg)
        start = parse_source_datetime(str(raw["startTime"]))
        end = start + timedelta(minutes=30)
        provider = str(raw["dataProvider"])
        settlement_date = str(raw["settlementDate"])
        settlement_period = int(raw["settlementPeriod"])
        points.append(
            WholesalePricePoint(
                delivery_start_utc=start,
                delivery_end_utc=end,
                settlement_date=settlement_date,
                settlement_period=settlement_period,
                duration_h=0.5,
                price_gbp_per_mwh=float(raw["price"]),
                price_source_type="MID",
                is_proxy=True,
                data_provider=provider,
                volume_mwh=float(raw["volume"]) if raw.get("volume") is not None else None,
                known_at_utc=end,
                retrieved_at_utc=retrieved_at_utc,
                source_id="ELEXON_BMRS_MID",
                source_url=source_url,
                source_record_id=f"{provider}:{settlement_date}:{settlement_period}",
                schema_version="0.1.0",
                quality_flag="ok",
            )
        )
    return sorted(points, key=lambda point: (point.delivery_start_utc, point.data_provider or ""))


def _format_query_time(value: datetime) -> str:
    return ensure_aware_utc(value).isoformat().replace("+00:00", "Z")
