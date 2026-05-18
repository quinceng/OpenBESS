from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _phase3_module(name: str) -> Any:
    try:
        return import_module(name)
    except ModuleNotFoundError as exc:
        raise AssertionError(f"Phase 3 module is not implemented yet: {name}") from exc


def test_service_registry_maps_source_labels_without_hiding_source_caveats() -> None:
    eac_services = _phase3_module("gb_bess_revenue_stack.markets.eac_services")

    registry = eac_services.load_eac_service_registry(ROOT / "data/reference/eac_product_map.yaml")
    service = registry.by_source_label("DCL")

    assert service.product_source_label == "DCL"
    assert service.product_model_label == "dynamic_containment_low"
    assert service.direction_source_label == "DCL"
    assert service.direction_model_label == "upward"
    assert service.source_id == "NESO_EAC_AUCTION_RESULTS"
    assert service.modelling_caveat


def test_unknown_service_labels_are_quarantined_not_defaulted_to_zero_or_unknown() -> None:
    eac_services = _phase3_module("gb_bess_revenue_stack.markets.eac_services")
    registry = eac_services.load_eac_service_registry(ROOT / "data/reference/eac_product_map.yaml")

    quarantine = registry.classify_source_label("NEW_PRODUCT")

    assert quarantine.accepted is False
    assert quarantine.reason == "unknown_product_label"
    assert quarantine.model_label is None


def test_active_service_definitions_require_source_backed_duration_and_window_rules() -> None:
    eac_services = _phase3_module("gb_bess_revenue_stack.markets.eac_services")
    registry = eac_services.load_eac_service_registry(ROOT / "data/reference/eac_product_map.yaml")

    central_services = registry.central_active_services()

    assert central_services
    for service in central_services:
        assert service.service_duration_h > 0
        assert service.service_window_source_id in {
            "NESO_EAC_MARKET_RULES",
            "NESO_FREQ_RESPONSE_MARKET_INFO_2023",
        }
        assert service.block_commitment_rule in {"none", "constant_within_block"}
