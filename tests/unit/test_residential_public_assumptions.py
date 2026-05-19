from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gb_bess_revenue_stack.residential import (
    ResidentialTariffSchedule,
    build_flat_public_reference_load_profile,
    build_public_reference_tariff_schedule,
    build_pvgis_hourly_url,
    get_public_reference_household_assumptions,
    public_residential_data_sources,
)

pytestmark = pytest.mark.unit


def test_public_source_registry_covers_all_residential_input_types() -> None:
    sources = public_residential_data_sources()

    covered_inputs = {
        input_name
        for source in sources.values()
        for input_name in source.residential_inputs_supported
    }

    assert "household_load" in covered_inputs
    assert "load_shape" in covered_inputs
    assert "pv_generation" in covered_inputs
    assert "retail_import_tariff" in covered_inputs
    assert "retail_export_tariff" in covered_inputs
    assert "vpp_payments" in covered_inputs
    assert "export_limit" in covered_inputs
    assert sources["desnz_subnational_electricity_2024"].availability == "public_free"
    assert sources["london_datastore_low_carbon_london"].geography == "London"


def test_london_reference_household_uses_public_2024_desnz_averages() -> None:
    assumptions = get_public_reference_household_assumptions("london")

    assert assumptions.geography_name == "London"
    assert assumptions.source_year == 2024
    assert assumptions.annual_load_mean_per_meter_kwh == pytest.approx(3240.67104307353)
    assert assumptions.annual_load_median_per_meter_kwh == pytest.approx(2357.399999989125)
    assert assumptions.annual_load_mean_per_household_kwh == pytest.approx(3302.319295729267)
    assert assumptions.default_annual_load_kwh == pytest.approx(
        assumptions.annual_load_mean_per_household_kwh
    )
    assert assumptions.default_export_limit_kw == pytest.approx(3.68)
    assert assumptions.default_import_rate_gbp_per_kwh == pytest.approx(0.2467)
    assert assumptions.default_export_rate_gbp_per_kwh == pytest.approx(0.12)
    assert assumptions.seg_export_rate_gbp_per_kwh == pytest.approx(0.041)
    assert assumptions.vpp_low_case_annual_revenue_gbp == pytest.approx(12)
    assert assumptions.vpp_central_case_annual_revenue_gbp == pytest.approx(36)
    assert assumptions.vpp_high_case_annual_revenue_gbp == pytest.approx(60)
    assert "desnz_subnational_electricity_2024" in assumptions.source_ids


def test_gb_reference_household_keeps_separate_aggregate_values() -> None:
    assumptions = get_public_reference_household_assumptions("gb")

    assert assumptions.geography_name == "Great Britain"
    assert assumptions.annual_load_mean_per_meter_kwh == pytest.approx(3322.735541706746)
    assert assumptions.annual_load_median_per_meter_kwh == pytest.approx(2471.1)
    assert assumptions.annual_load_mean_per_household_kwh == pytest.approx(3463.408415200937)


def test_public_reference_tariff_schedule_uses_flat_public_rates() -> None:
    start = datetime(2026, 4, 1, tzinfo=UTC)
    end = datetime(2026, 5, 1, tzinfo=UTC)

    tariff = build_public_reference_tariff_schedule(start, end, geography="london")

    assert isinstance(tariff, ResidentialTariffSchedule)
    assert len(tariff.periods) == 1
    period = tariff.periods[0]
    assert period.valid_from_utc == start
    assert period.valid_to_utc == end
    assert period.import_rate_gbp_per_kwh == pytest.approx(0.2467)
    assert period.export_rate_gbp_per_kwh == pytest.approx(0.12)
    assert period.standing_charge_gbp_per_day == pytest.approx(0.5721)


def test_flat_public_reference_load_profile_scales_london_annual_average() -> None:
    start = datetime(2026, 4, 1, tzinfo=UTC)
    end = datetime(2026, 4, 2, tzinfo=UTC)

    profile = build_flat_public_reference_load_profile(start, end, geography="london")

    assert len(profile) == 48
    assert sum(row.load_kwh for row in profile) == pytest.approx(3302.319295729267 / 365)
    assert all(row.pv_generation_kwh == 0 for row in profile)
    assert profile[0].delivery_start_utc == start
    assert profile[-1].delivery_end_utc == end


def test_pvgis_hourly_url_builder_uses_london_reference_pv_defaults() -> None:
    assumptions = get_public_reference_household_assumptions("london")

    url = build_pvgis_hourly_url(
        latitude=assumptions.default_latitude,
        longitude=assumptions.default_longitude,
        pv_capacity_kwp=assumptions.default_pv_capacity_kwp,
        loss_pct=assumptions.default_pv_system_loss_pct,
        tilt_deg=assumptions.default_pv_tilt_deg,
        azimuth_deg=assumptions.default_pv_azimuth_deg,
        start_year=2024,
        end_year=2024,
    )

    assert url.startswith("https://re.jrc.ec.europa.eu/api/v5_3/seriescalc?")
    assert "lat=51.5074" in url
    assert "lon=-0.1278" in url
    assert "pvcalculation=1" in url
    assert "peakpower=4.0" in url
    assert "loss=14.0" in url
    assert "angle=35.0" in url
    assert "aspect=0.0" in url
    assert "outputformat=json" in url
