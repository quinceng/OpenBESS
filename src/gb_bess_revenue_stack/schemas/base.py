from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "0.1.0"


class StrictBaseModel(BaseModel):
    """Project base model: no unexpected fields and assignment validation."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ProvenanceFields(StrictBaseModel):
    """Common provenance and data-quality metadata for canonical records."""

    retrieved_at_utc: datetime
    source_id: str
    source_url: str
    source_record_id: str | None = None
    schema_version: str = SCHEMA_VERSION
    quality_flag: str = "ok"
    quality_notes: str | None = None


class QuarantinedRecord(StrictBaseModel):
    """A source record preserved because it cannot enter the central schema."""

    reason: str
    source_id: str
    source_record: dict[str, Any] = Field(default_factory=dict)


def ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        msg = "Datetime must be timezone-aware."
        raise ValueError(msg)
    return value.astimezone(UTC)


def parse_source_datetime(value: str) -> datetime:
    """Parse a source timestamp and treat timezone-free source values as UTC.

    NESO datastore CSV fields are documented as UTC but may arrive without a
    trailing ``Z`` in CSV dumps. Parsers normalise those source fields to UTC
    before constructing strict canonical models.
    """

    normalised = value.strip()
    if normalised.endswith("Z"):
        normalised = normalised[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalised)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
