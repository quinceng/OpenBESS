from __future__ import annotations

from gb_bess_revenue_stack.optimisation.results import DispatchMetrics


def test_annualised_revenue_scales_by_sample_hours_and_nameplate_power() -> None:
    metrics = DispatchMetrics(
        total_revenue_gbp=100,
        sample_hours=10,
        asset_power_mw=2,
        charged_mwh=4,
        discharged_mwh=3,
        energy_capacity_mwh=6,
        average_buy_price_gbp_per_mwh=20,
        average_sell_price_gbp_per_mwh=80,
    )

    assert metrics.annualised_gbp_per_mw_year == 100 / 10 * 8760 / 2
    assert metrics.equivalent_throughput_cycles == (4 + 3) / (2 * 6)
    assert metrics.captured_spread_gbp_per_mwh == 60
