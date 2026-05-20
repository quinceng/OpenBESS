from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from gb_bess_revenue_stack.config.reference_assets import load_reference_assets

pytestmark = pytest.mark.unit


REFERENCE_ASSETS_PATH = "configs/reference_assets.yaml"


def test_reference_asset_registry_has_exact_asset_keys() -> None:
    registry = load_reference_assets(REFERENCE_ASSETS_PATH)

    assert set(registry.assets) == {
        "openbess_canonical_1mw_2mwh",
        "openbess_simple_market_1mw_1mwh",
    }


def test_canonical_reference_asset_values_and_caveats() -> None:
    registry = load_reference_assets(REFERENCE_ASSETS_PATH)

    asset = registry.assets["openbess_canonical_1mw_2mwh"]

    assert asset.public_label == "OpenBESS canonical GB 1MW/2MWh BESS"
    assert asset.asset.name == "openbess-canonical-1mw-2mwh"
    assert asset.asset.power_mw == pytest.approx(1.0)
    assert asset.asset.energy_capacity_mwh == pytest.approx(2.0)
    assert asset.asset.round_trip_efficiency == pytest.approx(0.88)
    assert asset.asset.soc_min_mwh == pytest.approx(0.1)
    assert asset.asset.soc_max_mwh == pytest.approx(1.9)
    assert asset.eac_eligible is True
    assert asset.cm_duration_hours == pytest.approx(2.0)
    assert asset.degradation_cost_gbp_per_mwh_throughput == pytest.approx(2.0)
    assert set(asset.caveat_flags) >= {
        "public_data_reference_asset",
        "eac_price_taking_proxy",
        "cm_scenario_only",
        "not_investment_advice",
        "not_a_market_index",
    }


def test_simple_market_reference_asset_values_and_caveats() -> None:
    registry = load_reference_assets(REFERENCE_ASSETS_PATH)

    asset = registry.assets["openbess_simple_market_1mw_1mwh"]

    assert asset.public_label == "OpenBESS educational simple-market preset"
    assert asset.asset.name == "openbess-simple-market-1mw-1mwh"
    assert asset.asset.power_mw == pytest.approx(1.0)
    assert asset.asset.energy_capacity_mwh == pytest.approx(1.0)
    assert asset.asset.round_trip_efficiency == pytest.approx(1.0)
    assert asset.asset.soc_min_mwh == pytest.approx(0.0)
    assert asset.asset.soc_max_mwh == pytest.approx(1.0)
    assert asset.eac_eligible is False
    assert asset.cm_duration_hours is None
    assert asset.degradation_cost_gbp_per_mwh_throughput == pytest.approx(0.0)
    assert set(asset.caveat_flags) >= {
        "educational_simplified_asset",
        "wholesale_only_comparator",
        "excludes_efficiency_losses",
        "not_investment_advice",
        "not_a_market_index",
    }


def test_load_reference_assets_rejects_top_level_list(tmp_path) -> None:
    config_path = tmp_path / "reference_assets.yaml"
    config_path.write_text(yaml.safe_dump(["not", "a", "mapping"]), encoding="utf-8")

    with pytest.raises(ValueError, match="must contain a YAML mapping"):
        load_reference_assets(config_path)


def test_load_reference_assets_rejects_extra_field(tmp_path) -> None:
    config_path = tmp_path / "reference_assets.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "assets": {
                    "extra_field_asset": {
                        "public_label": "Extra field asset",
                        "asset": {
                            "name": "extra-field-asset",
                            "power_mw": 1.0,
                            "energy_capacity_mwh": 1.0,
                            "round_trip_efficiency": 1.0,
                        },
                        "eac_eligible": False,
                        "degradation_cost_gbp_per_mwh_throughput": 0.0,
                        "caveat_flags": ["not_investment_advice"],
                        "unexpected": "field",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_reference_assets(config_path)
