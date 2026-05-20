from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AssetConfig(BaseModel):
    """Reference asset assumptions used by later optimisation phases."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    name: str
    power_mw: float = Field(gt=0)
    energy_capacity_mwh: float = Field(gt=0)
    round_trip_efficiency: float | None = Field(default=None, gt=0, le=1)
    eta_charge: float | None = Field(default=None, gt=0, le=1)
    eta_discharge: float | None = Field(default=None, gt=0, le=1)
    soc_min_mwh: float = Field(default=0, ge=0)
    soc_max_mwh: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def derive_efficiencies_and_soc_bounds(self) -> AssetConfig:
        if self.eta_charge is None or self.eta_discharge is None:
            if self.round_trip_efficiency is None:
                msg = "Provide either eta_charge/eta_discharge or round_trip_efficiency."
                raise ValueError(msg)
            split = math.sqrt(self.round_trip_efficiency)
            object.__setattr__(self, "eta_charge", split)
            object.__setattr__(self, "eta_discharge", split)
        soc_max_mwh = self.soc_max_mwh
        if soc_max_mwh is None:
            soc_max_mwh = self.energy_capacity_mwh
            object.__setattr__(self, "soc_max_mwh", soc_max_mwh)
        if self.soc_min_mwh >= soc_max_mwh:
            msg = "soc_min_mwh must be below soc_max_mwh."
            raise ValueError(msg)
        return self


class DataConfig(BaseModel):
    """Filesystem and schema-version settings for source processing."""

    model_config = ConfigDict(extra="forbid")

    raw_root: Path = Path("data/raw")
    processed_root: Path = Path("data/processed")
    reference_root: Path = Path("data/reference")
    schema_version: str = "0.1.0"
    known_at_policy: str = "source_specific_conservative"


class SolverConfig(BaseModel):
    """Phase 1 records solver defaults for later phases without solving models."""

    model_config = ConfigDict(extra="forbid")

    name: str = "highs"
    time_limit_seconds: int = Field(default=300, gt=0)
    mip_gap: float = Field(default=0.001, ge=0, le=1)


class MarketConfig(BaseModel):
    """Market-source switches visible in manifests and reports."""

    model_config = ConfigDict(extra="forbid")

    wholesale_source_id: str = "ELEXON_BMRS_MID"
    wholesale_provider: str = "APXMIDP"
    eac_source_id: str = "NESO_EAC_AUCTION_RESULTS"
    cm_source_id: str = "CM_OFFICIAL_AUCTION_PARAMETERS"

    @field_validator("wholesale_provider")
    @classmethod
    def provider_must_be_known_mid_provider(cls, value: str) -> str:
        allowed = {"APXMIDP", "N2EXMIDP"}
        if value not in allowed:
            msg = f"wholesale_provider must be one of {sorted(allowed)}."
            raise ValueError(msg)
        return value


class RunConfig(BaseModel):
    """Top-level run configuration serialisable to run manifests."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    asset: AssetConfig
    data: DataConfig = DataConfig()
    solver: SolverConfig = SolverConfig()
    market: MarketConfig = MarketConfig()


def load_run_config(path: str | Path, *, env_prefix: str = "GB_BESS_") -> RunConfig:
    """Load a YAML run config and apply nested environment overrides.

    Environment keys use double underscores for nesting, for example
    ``GB_BESS_ASSET__POWER_MW=60``.
    """

    config_path = Path(path)
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        msg = f"{config_path} must contain a YAML mapping."
        raise ValueError(msg)
    merged: dict[str, Any] = dict(payload)
    for key, value in os.environ.items():
        if not key.startswith(env_prefix):
            continue
        path_parts = [part.lower() for part in key.removeprefix(env_prefix).split("__")]
        _set_nested(merged, path_parts, _parse_env_value(value))
    return RunConfig.model_validate(merged)


def _set_nested(payload: dict[str, Any], path_parts: list[str], value: Any) -> None:
    target = payload
    for part in path_parts[:-1]:
        existing = target.setdefault(part, {})
        if not isinstance(existing, dict):
            msg = f"Cannot set nested override through non-mapping key {part!r}."
            raise ValueError(msg)
        target = existing
    target[path_parts[-1]] = value


def _parse_env_value(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value
