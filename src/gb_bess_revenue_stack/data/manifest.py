from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field, field_validator

from gb_bess_revenue_stack.schemas.base import ensure_aware_utc


class DatasetManifest(BaseModel):
    dataset: str
    schema_version: str
    source_ids: list[str]
    source_urls: list[str]
    retrieved_at_utc: datetime
    period_start_utc: str | None
    period_end_utc: str | None
    row_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    missing_period_count: int = Field(ge=0)
    timezone_convention: str = "UTC"
    data_hash: str
    transformation_version: str = "0.1.0"
    known_at_policy: str
    validation_status: str

    @field_validator("retrieved_at_utc")
    @classmethod
    def retrieved_at_is_aware(cls, value: datetime) -> datetime:
        return ensure_aware_utc(value)

    @classmethod
    def from_dataframe(
        cls,
        *,
        dataset: str,
        schema_version: str,
        frame: pd.DataFrame,
        source_ids: list[str],
        source_urls: list[str],
        retrieved_at_utc: datetime,
        known_at_policy: str,
        validation_status: str,
        transformation_version: str = "0.1.0",
        missing_period_count: int = 0,
    ) -> DatasetManifest:
        period_start, period_end = _period_bounds(frame)
        duplicate_count = _duplicate_count(frame)
        return cls(
            dataset=dataset,
            schema_version=schema_version,
            source_ids=source_ids,
            source_urls=source_urls,
            retrieved_at_utc=retrieved_at_utc,
            period_start_utc=period_start,
            period_end_utc=period_end,
            row_count=len(frame),
            duplicate_count=duplicate_count,
            missing_period_count=missing_period_count,
            data_hash=dataframe_hash(frame),
            transformation_version=transformation_version,
            known_at_policy=known_at_policy,
            validation_status=validation_status,
        )

    def write_json(self, path: str | Path) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return output


class ProcessedDatasetWriter:
    """Write processed parquet plus a sidecar manifest."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def write(
        self,
        *,
        dataset: str,
        schema_version: str,
        frame: pd.DataFrame,
        filename_stem: str,
        manifest: DatasetManifest,
    ) -> tuple[Path, Path]:
        directory = self.root / dataset / schema_version
        directory.mkdir(parents=True, exist_ok=True)
        parquet_path = directory / f"{filename_stem}.parquet"
        manifest_path = directory / f"{filename_stem}.manifest.json"
        frame.to_parquet(parquet_path, index=False)
        manifest.write_json(manifest_path)
        return parquet_path, manifest_path


def dataframe_hash(frame: pd.DataFrame) -> str:
    sorted_frame = frame.reindex(sorted(frame.columns), axis=1)
    payload = sorted_frame.to_json(orient="records", date_format="iso", default_handler=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _period_bounds(frame: pd.DataFrame) -> tuple[str | None, str | None]:
    if frame.empty or "delivery_start_utc" not in frame or "delivery_end_utc" not in frame:
        return None, None
    return str(frame["delivery_start_utc"].min()), str(frame["delivery_end_utc"].max())


def _duplicate_count(frame: pd.DataFrame) -> int:
    keys = [key for key in ["delivery_start_utc", "delivery_end_utc", "source_id"] if key in frame]
    if not keys:
        return 0
    return int(frame.duplicated(subset=keys).sum())


def write_json_payload(path: str | Path, payload: object) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return output
