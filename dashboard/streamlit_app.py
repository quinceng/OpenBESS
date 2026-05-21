from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.cache_reader import (
    DEFAULT_CACHE_DIR,
    DashboardCache,
    DashboardCacheError,
    load_dashboard_cache,
)

STACK_STORY_STEPS = [
    "Elexon BMRS MID wholesale proxy",
    "NESO EAC price-taking availability proxy",
    "Capacity Market annual scenario",
    "Degradation-adjusted rolling policy",
]


def build_view_model(cache: DashboardCache) -> dict[str, Any]:
    """Build display-ready values from cached dashboard artefacts."""

    central_capture = _central_capture_row(cache)
    source_labels = cache.executive_summary.get("source_labels", {})
    caveats = cache.caveats.get("caveats", [])
    return {
        "run_id": cache.manifest.get("run_id", "unknown"),
        "headline_period": cache.executive_summary.get("headline_period", "cached sample"),
        "capture_ratio": central_capture.get("capture_ratio"),
        "regret_gbp": central_capture.get("regret_gbp"),
        "perfect_total_revenue_gbp": central_capture.get("perfect_total_revenue_gbp"),
        "rolling_total_revenue_gbp": central_capture.get("rolling_total_revenue_gbp"),
        "source_labels": source_labels if isinstance(source_labels, dict) else {},
        "window_labels": [
            label for label in cache.policy_capture["label"].tolist() if label != "central"
        ],
        "revenue_basis": sorted(cache.revenue_stack["basis"].unique().tolist()),
        "scenario_count": int(len(cache.scenario_sweeps)),
        "caveats": caveats if isinstance(caveats, list) else [],
        "has_phase5": cache.finance_summary is not None
        or cache.degradation_summary is not None
        or cache.benchmark_reconciliation is not None,
        "has_eac_commitments": cache.eac_commitments is not None,
        "has_data_quality": cache.data_quality is not None,
        "has_stack_series": cache.stack_series is not None,
        "has_forecast_error_sweeps": cache.forecast_error_sweeps is not None,
        "has_forecast_model_comparison": cache.forecast_model_comparison is not None,
        "has_finance_sensitivities": cache.finance_sensitivities is not None,
        "stack_index": _stack_index_view(cache),
        "stack_story_steps": STACK_STORY_STEPS,
    }


def render_dashboard(cache_dir: str | Path = DEFAULT_CACHE_DIR) -> None:
    """Render the cached dashboard in Streamlit."""

    import streamlit as st

    st.set_page_config(page_title="GB BESS Revenue Stack", layout="wide")
    st.title("GB BESS Revenue Stack Dashboard")
    st.caption("Cached public-data research artefact. No live API calls or solver runs.")
    try:
        cache = load_dashboard_cache(cache_dir)
    except DashboardCacheError as exc:
        st.error(str(exc))
        st.code("uv run gb-bess run-phase4-smoke", language="bash")
        return

    model = build_view_model(cache)
    _render_summary(st, model)
    _render_policy_capture(st, cache)
    _render_revenue_stack(st, cache)
    _render_scenarios(st, cache)
    _render_phase5(st, cache)
    _render_stack_index_preview(st, cache, model)
    _render_forecast_model_comparison(st, cache)
    _render_forecast_error_sweeps(st, cache)
    _render_data_quality(st, cache)
    _render_sources_and_caveats(st, model)


def main() -> None:
    render_dashboard()


def _central_capture_row(cache: DashboardCache) -> dict[str, Any]:
    matches = cache.policy_capture.loc[cache.policy_capture["label"] == "central"]
    if matches.empty:
        return {}
    return matches.iloc[0].to_dict()


def _render_summary(st: Any, model: dict[str, Any]) -> None:
    st.subheader("Rolling vs Perfect-Foresight Capture Ratio")
    columns = st.columns(4)
    columns[0].metric("Capture Ratio", _format_ratio(model["capture_ratio"]))
    columns[1].metric("Regret", _format_currency(model["regret_gbp"]))
    columns[2].metric("Perfect Foresight", _format_currency(model["perfect_total_revenue_gbp"]))
    columns[3].metric("Rolling Policy", _format_currency(model["rolling_total_revenue_gbp"]))
    st.caption(f"Run `{model['run_id']}` over {model['headline_period']}.")


def _render_policy_capture(st: Any, cache: DashboardCache) -> None:
    st.subheader("24h / 48h Stress-Profile Comparisons")
    view = cache.policy_capture.copy()
    if not view.empty:
        view["capture_pct"] = view["capture_ratio"].map(
            lambda value: None if value is None else value * 100
        )
    st.dataframe(
        view[
            [
                "label",
                "period_count",
                "sample_hours",
                "capture_pct",
                "regret_gbp",
                "forecast_mae_gbp_per_mwh",
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )


def _render_revenue_stack(st: Any, cache: DashboardCache) -> None:
    st.subheader("Revenue Stack Split")
    chart_data = cache.revenue_stack.pivot_table(
        index="basis",
        columns="component",
        values="value_gbp",
        aggfunc="sum",
        fill_value=0,
    )
    st.bar_chart(chart_data)
    st.dataframe(cache.revenue_stack, hide_index=True, use_container_width=True)


def _render_scenarios(st: Any, cache: DashboardCache) -> None:
    st.subheader("Scenario Sweep Table")
    st.dataframe(cache.scenario_sweeps, hide_index=True, use_container_width=True)


def _render_phase5(st: Any, cache: DashboardCache) -> None:
    if (
        cache.degradation_summary is None
        and cache.finance_summary is None
        and cache.benchmark_reconciliation is None
        and cache.finance_sensitivities is None
    ):
        return
    st.subheader("Phase 5 Illustrative Outputs")
    columns = st.columns(3)
    if cache.degradation_summary is not None:
        columns[0].metric(
            "Throughput",
            f"{float(cache.degradation_summary.get('throughput_mwh', 0)):,.1f} MWh",
        )
        cycles = cache.degradation_summary.get("equivalent_full_cycles")
        columns[1].metric("Equivalent Cycles", "n/a" if cycles is None else f"{cycles:,.2f}")
    if cache.finance_summary is not None:
        columns[2].metric("NPV", _format_currency(cache.finance_summary.get("npv_gbp")))
        st.caption(str(cache.finance_summary.get("not_bankability_statement", "")))
    if cache.finance_cashflows is not None:
        st.dataframe(cache.finance_cashflows, hide_index=True, use_container_width=True)
    if cache.finance_sensitivities is not None and not cache.finance_sensitivities.empty:
        st.dataframe(cache.finance_sensitivities, hide_index=True, use_container_width=True)
    if cache.benchmark_reconciliation is not None:
        st.json(cache.benchmark_reconciliation)


def _render_stack_index_preview(
    st: Any,
    cache: DashboardCache,
    model: dict[str, Any],
) -> None:
    if cache.stack_series is None:
        return
    stack_index = model["stack_index"]
    st.subheader(stack_index["display_label"])
    st.caption(" | ".join(model["stack_story_steps"]))
    columns = st.columns(4)
    columns[0].metric("Primary Window", stack_index["primary_window_label"])
    columns[1].metric("Coverage", _format_ratio(stack_index["primary_coverage_pct"]))
    columns[2].metric("Public Eligibility", "yes" if stack_index["public_eligible"] else "no")
    columns[3].metric("Annualisation", "yes" if stack_index["annualisation_eligible"] else "no")
    columns = [
        "window_label",
        "basis",
        "wholesale_energy_gbp",
        "eac_availability_gbp",
        "degradation_cost_gbp",
        "cm_annual_scenario_gbp_per_mw_year",
        "degradation_adjusted_value_gbp",
    ]
    available_columns = [column for column in columns if column in cache.stack_series.columns]
    st.dataframe(
        cache.stack_series[available_columns],
        hide_index=True,
        use_container_width=True,
    )
    if stack_index["caveat_flags"]:
        st.caption("Caveats: " + ", ".join(stack_index["caveat_flags"]))


def _render_forecast_error_sweeps(st: Any, cache: DashboardCache) -> None:
    if cache.forecast_error_sweeps is None or cache.forecast_error_sweeps.empty:
        return
    st.subheader("Forecast Error Sensitivities")
    st.dataframe(cache.forecast_error_sweeps, hide_index=True, use_container_width=True)


def _render_forecast_model_comparison(st: Any, cache: DashboardCache) -> None:
    if cache.forecast_model_comparison is None or cache.forecast_model_comparison.empty:
        return
    st.subheader("Forecast Model Comparison")
    st.dataframe(cache.forecast_model_comparison, hide_index=True, use_container_width=True)


def _render_data_quality(st: Any, cache: DashboardCache) -> None:
    if cache.eac_commitments is None and cache.data_quality is None:
        return
    st.subheader("EAC Commitments and Data Quality")
    if cache.eac_commitments is not None:
        st.dataframe(cache.eac_commitments, hide_index=True, use_container_width=True)
    if cache.stack_series_windows is not None:
        st.dataframe(cache.stack_series_windows, hide_index=True, use_container_width=True)
    if cache.data_quality is not None:
        st.json(cache.data_quality)


def _render_sources_and_caveats(st: Any, model: dict[str, Any]) -> None:
    st.subheader("Caveats and Source Labels")
    if model["source_labels"]:
        st.json(model["source_labels"])
    for caveat in model["caveats"]:
        st.warning(str(caveat))


def _format_ratio(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def _format_currency(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"GBP {float(value):,.0f}"


def _stack_index_view(cache: DashboardCache) -> dict[str, Any]:
    metadata = cache.manifest.get("stack_series", {})
    windows = []
    if cache.data_quality is not None:
        raw_windows = cache.data_quality.get("stack_series_windows", [])
        if isinstance(raw_windows, list):
            windows = [window for window in raw_windows if isinstance(window, dict)]
    primary_window_label = str(metadata.get("primary_window_label", "n/a"))
    primary_window = next(
        (window for window in windows if window.get("window_label") == primary_window_label),
        {},
    )
    public_eligible = bool(metadata.get("eligible_for_public_index", False))
    annualisation_eligible = bool(metadata.get("eligible_for_annualisation", False))
    return {
        "display_label": "OpenBESS Stack Index"
        if public_eligible
        else "OpenBESS Stack Index Preview",
        "primary_window_label": primary_window_label,
        "primary_coverage_pct": primary_window.get("coverage_pct"),
        "public_eligible": public_eligible,
        "annualisation_eligible": annualisation_eligible,
        "caveat_flags": list(metadata.get("caveat_flags", [])),
    }


if __name__ == "__main__":
    main()
