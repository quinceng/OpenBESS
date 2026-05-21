from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from gb_bess_revenue_stack.config.models import AssetConfig

OPENBESS_CANONICAL_ASSET_ID = "openbess_canonical_1mw_2mwh"


class ReferenceAsset(BaseModel):
    """Public reference asset preset and market-scope metadata."""

    model_config = ConfigDict(extra="forbid")

    public_label: str
    asset: AssetConfig
    eac_eligible: bool
    cm_duration_hours: float | None = Field(default=None, gt=0)
    degradation_cost_gbp_per_mwh_throughput: float = Field(ge=0)
    caveat_flags: list[str]


class ReferenceAssetRegistry(BaseModel):
    """Named collection of public reference asset presets."""

    model_config = ConfigDict(extra="forbid")

    assets: dict[str, ReferenceAsset]


def load_reference_assets(path: str | Path) -> ReferenceAssetRegistry:
    """Load and validate the canonical reference asset registry."""

    config_path = Path(path)
    payload: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        msg = f"{config_path} must contain a YAML mapping."
        raise ValueError(msg)
    return ReferenceAssetRegistry.model_validate(payload)
