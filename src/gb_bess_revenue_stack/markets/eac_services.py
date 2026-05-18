from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from gb_bess_revenue_stack.schemas.market import DirectionModelLabel

BlockCommitmentRule = Literal["none", "constant_within_block"]


class EACServiceDefinition(BaseModel):
    """Source-backed EAC service definition used by Phase 3 models."""

    model_config = ConfigDict(extra="forbid")

    product_source_label: str
    product_model_label: str
    direction_source_label: str
    direction_model_label: DirectionModelLabel
    source_id: str
    modelling_caveat: str
    central_active: bool = False
    service_duration_h: float = Field(gt=0)
    service_window_source_id: str
    block_commitment_rule: BlockCommitmentRule = "none"


class ServiceLabelClassification(BaseModel):
    """Registry result for one source product label."""

    model_config = ConfigDict(extra="forbid")

    accepted: bool
    reason: str | None = None
    source_label: str
    model_label: str | None = None


class EACServiceRegistry(BaseModel):
    """Controlled registry of EAC product labels and model conventions."""

    model_config = ConfigDict(extra="forbid")

    services: dict[str, EACServiceDefinition]

    def by_source_label(self, source_label: str) -> EACServiceDefinition:
        try:
            return self.services[source_label]
        except KeyError as exc:
            msg = f"Unknown EAC product source label {source_label!r}."
            raise ValueError(msg) from exc

    def classify_source_label(self, source_label: str) -> ServiceLabelClassification:
        service = self.services.get(source_label)
        if service is None:
            return ServiceLabelClassification(
                accepted=False,
                reason="unknown_product_label",
                source_label=source_label,
            )
        return ServiceLabelClassification(
            accepted=True,
            source_label=source_label,
            model_label=service.product_model_label,
        )

    def central_active_services(self) -> list[EACServiceDefinition]:
        return [service for service in self.services.values() if service.central_active]


def load_eac_service_registry(path: str | Path) -> EACServiceRegistry:
    """Load source-label mapping and service conventions from reference data."""

    registry_path = Path(path)
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    products = payload.get("products", {})
    if not isinstance(products, dict):
        msg = f"{registry_path} must contain a products mapping."
        raise ValueError(msg)
    source_id = str(payload.get("source_id", "NESO_EAC_AUCTION_RESULTS"))
    caveat = str(payload.get("known_caveat", "No caveat recorded."))
    services: dict[str, EACServiceDefinition] = {}
    for source_label, raw_definition in products.items():
        if not isinstance(raw_definition, dict):
            msg = f"Product {source_label!r} definition must be a mapping."
            raise ValueError(msg)
        services[str(source_label)] = EACServiceDefinition(
            product_source_label=str(source_label),
            product_model_label=str(raw_definition["model_label"]),
            direction_source_label=str(source_label),
            direction_model_label=raw_definition["direction_model_label"],
            source_id=source_id,
            modelling_caveat=caveat,
            central_active=bool(raw_definition.get("central_active", False)),
            service_duration_h=float(raw_definition["service_duration_h"]),
            service_window_source_id=str(raw_definition["service_window_source_id"]),
            block_commitment_rule=raw_definition.get("block_commitment_rule", "none"),
        )
    return EACServiceRegistry(services=services)
