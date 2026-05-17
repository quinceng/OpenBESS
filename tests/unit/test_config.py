from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from gb_bess_revenue_stack.config.models import AssetConfig, load_run_config

pytestmark = pytest.mark.unit


def test_asset_config_splits_round_trip_efficiency() -> None:
    asset = AssetConfig(
        name="2h-reference",
        power_mw=50,
        energy_capacity_mwh=100,
        round_trip_efficiency=0.81,
    )

    assert asset.eta_charge == pytest.approx(0.9)
    assert asset.eta_discharge == pytest.approx(0.9)


def test_asset_config_rejects_invalid_energy_capacity() -> None:
    with pytest.raises(ValidationError):
        AssetConfig(name="bad", power_mw=50, energy_capacity_mwh=0, round_trip_efficiency=0.9)


def test_load_run_config_applies_nested_environment_overrides(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "run.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "run_id": "phase1-smoke",
                "asset": {
                    "name": "reference",
                    "power_mw": 50,
                    "energy_capacity_mwh": 100,
                    "round_trip_efficiency": 0.81,
                },
                "data": {},
                "solver": {},
                "market": {},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GB_BESS_ASSET__POWER_MW", "60")
    monkeypatch.setenv("GB_BESS_MARKET__WHOLESALE_PROVIDER", "N2EXMIDP")

    config = load_run_config(config_path)

    assert config.asset.power_mw == 60
    assert config.market.wholesale_provider == "N2EXMIDP"
