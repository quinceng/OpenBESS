from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from gb_bess_revenue_stack.config.models import AssetConfig, SolverConfig
from gb_bess_revenue_stack.data.elexon import (
    ELEXON_BASE_URL,
    MARKET_INDEX_PATH,
    parse_market_index_points,
)
from gb_bess_revenue_stack.data.neso import (
    EAC_RESULTS_SUMMARY_RESOURCE_ID,
    NESO_CKAN_ACTION_BASE_URL,
    parse_eac_summary_records,
)
from gb_bess_revenue_stack.markets.eac_prices import EACPriceMatrix, build_eac_price_matrix
from gb_bess_revenue_stack.optimisation.inputs import TerminalSocPolicy
from gb_bess_revenue_stack.optimisation.market_stack_model import solve_market_stack
from gb_bess_revenue_stack.policies.forecasts import ForecastModel
from gb_bess_revenue_stack.policies.rolling import RollingConfig
from gb_bess_revenue_stack.policies.rolling_market_stack import (
    RollingMarketStackRun,
    RollingMarketStackScenario,
    RollingMarketStackScenarioResult,
    run_rolling_market_stack_policy,
    run_rolling_market_stack_scenarios,
)
from gb_bess_revenue_stack.schemas.base import ensure_aware_utc, parse_source_datetime
from gb_bess_revenue_stack.schemas.market import EACAuctionResult, WholesalePricePoint

PHASE4_FIXTURES_PACKAGE = "gb_bess_revenue_stack.phase4.fixtures"
DEFAULT_PHASE4_ELEXON_MID_SAMPLE = "phase4_elexon_mid_aligned_sample.json"
DEFAULT_PHASE4_NESO_EAC_SAMPLE = "phase4_neso_eac_aligned_sample.json"
PHASE4_HISTORICAL_SAMPLE_RETRIEVED_AT_UTC = datetime(2026, 5, 19, 12, tzinfo=UTC)
PHASE4_EAC_PRODUCT_ORDER = {
    "dynamic_containment_low": 10,
    "dynamic_containment_high": 20,
    "dynamic_moderation_low": 30,
    "dynamic_moderation_high": 40,
    "dynamic_regulation_low": 50,
    "dynamic_regulation_high": 60,
    "positive_quick_reserve": 70,
    "negative_quick_reserve": 80,
    "positive_slow_reserve": 90,
    "negative_slow_reserve": 100,
}


class Phase4ScenarioSweepResult(BaseModel):
    """Phase 4 rolling wholesale plus EAC scenario sweep output."""

    model_config = ConfigDict(extra="forbid")

    price_period_count: int = Field(ge=0)
    stress_day_count: int = Field(gt=0)
    scenario_results: list[RollingMarketStackScenarioResult]


class Phase4MarketStackCaptureResult(BaseModel):
    """Phase 4 rolling policy comparison against a perfect-foresight ceiling."""

    model_config = ConfigDict(extra="forbid")

    price_period_count: int = Field(ge=0)
    sample_hours: float = Field(ge=0)
    perfect_energy_revenue_gbp: float
    perfect_service_revenue_gbp: float
    perfect_total_revenue_gbp: float
    rolling_energy_revenue_gbp: float
    rolling_service_revenue_gbp: float
    rolling_total_revenue_gbp: float
    rolling_planned_revenue_gbp: float
    capture_ratio: float | None
    regret_gbp: float
    solver_failure_count: int = Field(ge=0)
    forecast_mae_gbp_per_mwh: float
    forecast_rmse_gbp_per_mwh: float


class Phase4SmokeWindowComparison(BaseModel):
    """Compact 24h/48h Phase 4 smoke comparison result."""

    model_config = ConfigDict(extra="forbid")

    label: str
    day_count: int = Field(gt=0)
    capture: Phase4MarketStackCaptureResult


class Phase4SmokeWindowSkip(BaseModel):
    """Skipped 24h/48h smoke comparison with an explicit reason."""

    model_config = ConfigDict(extra="forbid")

    label: str
    day_count: int = Field(gt=0)
    required_period_count: int = Field(gt=0)
    available_period_count: int = Field(ge=0)
    reason: str


class Phase4HistoricalSample(BaseModel):
    """Aligned historical Elexon MID and NESO EAC sample for release smoke runs."""

    model_config = ConfigDict(extra="forbid")

    label: str
    prices: list[WholesalePricePoint]
    eac_price_matrix: EACPriceMatrix
    source_ids: list[str]
    source_labels: dict[str, str]
    source_snapshot_hash: str
    caveats: list[str]

    @property
    def sample_hours(self) -> float:
        return sum(price.duration_h for price in self.prices)


def load_phase4_historical_sample(
    *,
    elexon_mid_path: Path | None = None,
    neso_eac_path: Path | None = None,
) -> Phase4HistoricalSample:
    """Load the small aligned historical Elexon/NESO sample used by Phase 4 examples."""

    elexon_text = _read_fixture_text(
        path=elexon_mid_path,
        packaged_name=DEFAULT_PHASE4_ELEXON_MID_SAMPLE,
    )
    neso_text = _read_fixture_text(
        path=neso_eac_path,
        packaged_name=DEFAULT_PHASE4_NESO_EAC_SAMPLE,
    )
    elexon_payload = json.loads(elexon_text)
    neso_payload = json.loads(neso_text)
    if not isinstance(elexon_payload, dict):
        msg = "Phase 4 Elexon MID fixture must contain a JSON object."
        raise ValueError(msg)
    elexon_metadata = _fixture_metadata(elexon_payload)
    neso_metadata = _fixture_metadata(neso_payload)
    prices = parse_market_index_points(
        elexon_payload,
        source_url=f"{ELEXON_BASE_URL}{MARKET_INDEX_PATH}",
        retrieved_at_utc=_metadata_retrieved_at(elexon_metadata),
    )
    price_source_url = _elexon_source_url(prices)
    prices = [price.model_copy(update={"source_url": price_source_url}) for price in prices]
    parsed_eac = parse_eac_summary_records(
        _neso_fixture_records(neso_payload),
        source_url=(
            f"{NESO_CKAN_ACTION_BASE_URL}/datastore_search"
            f"?resource_id={EAC_RESULTS_SUMMARY_RESOURCE_ID}"
        ),
        retrieved_at_utc=_metadata_retrieved_at(neso_metadata),
    )
    if parsed_eac.quarantined:
        reasons = ", ".join(sorted({record.reason for record in parsed_eac.quarantined}))
        msg = f"Phase 4 NESO fixture contains quarantined records: {reasons}."
        raise ValueError(msg)
    eac_matrix = build_eac_price_matrix(
        records=parsed_eac.accepted,
        target_periods=prices,
        product_model_labels=_phase4_eac_product_labels(parsed_eac.accepted),
    )
    _validate_historical_sample_alignment(prices, eac_matrix)
    caveats = _fixture_caveats(elexon_metadata, neso_metadata)
    if elexon_mid_path is not None or neso_eac_path is not None:
        caveats.append(
            "Fixture override paths were supplied; provenance is read from fixture metadata "
            "where present and otherwise inferred from parsed records."
        )
    return Phase4HistoricalSample(
        label=_historical_sample_label(prices),
        prices=prices,
        eac_price_matrix=eac_matrix,
        source_ids=[
            _metadata_text(elexon_metadata, "source_id", "ELEXON_BMRS_MID"),
            _metadata_text(neso_metadata, "source_id", "NESO_EAC_AUCTION_RESULTS"),
        ],
        source_labels={
            "wholesale": _metadata_text(
                elexon_metadata,
                "source_label",
                "Elexon BMRS MID historical proxy sample",
            ),
            "eac": _metadata_text(
                neso_metadata,
                "source_label",
                "NESO EAC auction results historical availability sample",
            ),
        },
        source_snapshot_hash=_historical_sample_hash(elexon_text, neso_text),
        caveats=caveats,
    )


def build_realistic_stress_price_profile(
    *,
    start_utc: datetime,
    day_count: int,
) -> list[WholesalePricePoint]:
    """Build a deterministic multi-day GB-like stress profile for network-free tests."""

    if day_count <= 0:
        msg = "day_count must be positive."
        raise ValueError(msg)
    start_utc = ensure_aware_utc(start_utc)
    rows: list[WholesalePricePoint] = []
    for day_index in range(day_count):
        for settlement_period in range(1, 49):
            period_start = start_utc + timedelta(
                days=day_index, minutes=30 * (settlement_period - 1)
            )
            period_end = period_start + timedelta(minutes=30)
            rows.append(
                WholesalePricePoint(
                    delivery_start_utc=period_start,
                    delivery_end_utc=period_end,
                    known_at_utc=period_end - timedelta(days=1),
                    settlement_date=period_start.date().isoformat(),
                    settlement_period=settlement_period,
                    duration_h=0.5,
                    price_gbp_per_mwh=_stress_price(day_index, settlement_period),
                    price_source_type="SYNTHETIC_TEST",
                    is_proxy=True,
                    retrieved_at_utc=start_utc,
                    source_id="PROJECT_CONVENTION",
                    source_url="phase4:realistic_stress_profile",
                    schema_version="0.1.0",
                    quality_flag="synthetic_stress",
                )
            )
    return rows


def default_phase4_market_stack_scenarios() -> list[RollingMarketStackScenario]:
    """Return default Phase 4 wholesale and EAC sensitivity scenarios."""

    return [
        RollingMarketStackScenario(
            name="base_case",
            stress_label="central",
            notes="Central historical sample with unscaled wholesale and EAC prices.",
        ),
        RollingMarketStackScenario(
            name="winter_peak_spread",
            stress_label="high_wholesale_spread",
            wholesale_price_scalar=1.35,
            eac_price_scalar=1,
            notes="Higher wholesale spreads during system-stress windows.",
        ),
        RollingMarketStackScenario(
            name="low_spread_eac_downside",
            stress_label="low_spread_low_eac",
            wholesale_price_scalar=0.7,
            eac_price_scalar=0.65,
            notes="Compressed wholesale spreads with weaker EAC availability pricing.",
        ),
        RollingMarketStackScenario(
            name="eac_upside",
            stress_label="high_eac",
            wholesale_price_scalar=1,
            eac_price_scalar=1.4,
            notes="EAC upside sensitivity with unchanged wholesale profile.",
        ),
        RollingMarketStackScenario(
            name="wholesale_downside",
            stress_label="low_wholesale",
            wholesale_price_scalar=0.75,
            eac_price_scalar=1,
            notes="Lower wholesale price capture with unchanged EAC availability pricing.",
        ),
        RollingMarketStackScenario(
            name="stack_upside",
            stress_label="high_wholesale_high_eac",
            wholesale_price_scalar=1.25,
            eac_price_scalar=1.25,
            notes="Combined wholesale and EAC upside case.",
        ),
    ]


def run_phase4_market_stack_sweep(
    *,
    prices: list[WholesalePricePoint],
    eac_price_matrix: EACPriceMatrix,
    asset: AssetConfig,
    initial_soc_mwh: float,
    forecast_model: ForecastModel,
    config: RollingConfig,
    scenarios: list[RollingMarketStackScenario] | None = None,
) -> Phase4ScenarioSweepResult:
    """Run the Phase 4 deterministic rolling market-stack scenario sweep."""

    selected = default_phase4_market_stack_scenarios() if scenarios is None else scenarios
    results = run_rolling_market_stack_scenarios(
        prices=prices,
        eac_price_matrix=eac_price_matrix,
        asset=asset,
        initial_soc_mwh=initial_soc_mwh,
        forecast_model=forecast_model,
        config=config,
        scenarios=selected,
    )
    dates = {row.settlement_date for row in prices}
    return Phase4ScenarioSweepResult(
        price_period_count=len(prices),
        stress_day_count=len(dates),
        scenario_results=results,
    )


def run_phase4_market_stack_capture_comparison(
    *,
    prices: list[WholesalePricePoint],
    eac_price_matrix: EACPriceMatrix,
    asset: AssetConfig,
    initial_soc_mwh: float,
    rolling_run: RollingMarketStackRun,
    terminal_soc_policy: TerminalSocPolicy,
    terminal_soc_target_mwh: float | None = None,
    solver_config: SolverConfig | None = None,
) -> Phase4MarketStackCaptureResult:
    """Compare a realised rolling market-stack run with perfect foresight."""

    perfect = solve_market_stack(
        prices=prices,
        eac_price_matrix=eac_price_matrix,
        asset=asset,
        initial_soc_mwh=initial_soc_mwh,
        terminal_soc_policy=terminal_soc_policy,
        terminal_soc_target_mwh=terminal_soc_target_mwh,
        solver_config=solver_config,
    )
    perfect_total = perfect.total_revenue_gbp
    rolling_total = rolling_run.realised_total_revenue_gbp
    capture_ratio = rolling_total / perfect_total if abs(perfect_total) > 1e-9 else None
    return Phase4MarketStackCaptureResult(
        price_period_count=len(prices),
        sample_hours=sum(price.duration_h for price in prices),
        perfect_energy_revenue_gbp=perfect.energy_revenue_gbp,
        perfect_service_revenue_gbp=perfect.service_revenue_gbp,
        perfect_total_revenue_gbp=perfect_total,
        rolling_energy_revenue_gbp=rolling_run.realised_energy_revenue_gbp,
        rolling_service_revenue_gbp=rolling_run.realised_service_revenue_gbp,
        rolling_total_revenue_gbp=rolling_total,
        rolling_planned_revenue_gbp=rolling_run.planned_total_revenue_gbp,
        capture_ratio=capture_ratio,
        regret_gbp=perfect_total - rolling_total,
        solver_failure_count=rolling_run.solver_failure_count,
        forecast_mae_gbp_per_mwh=_mean(
            [step.forecast_mae_gbp_per_mwh for step in rolling_run.steps]
        ),
        forecast_rmse_gbp_per_mwh=_mean(
            [step.forecast_rmse_gbp_per_mwh for step in rolling_run.steps]
        ),
    )


def run_phase4_smoke_window_comparisons(
    *,
    prices: list[WholesalePricePoint],
    eac_price_matrix: EACPriceMatrix,
    asset: AssetConfig,
    initial_soc_mwh: float,
    forecast_model: ForecastModel,
    config: RollingConfig,
    window_day_counts: list[int] | None = None,
) -> list[Phase4SmokeWindowComparison]:
    """Run deterministic 24h/48h Phase 4 smoke comparisons where data is available."""

    selected_day_counts = _selected_window_day_counts(window_day_counts)
    ordered = sorted(prices, key=lambda point: point.delivery_start_utc)
    comparisons: list[Phase4SmokeWindowComparison] = []
    for day_count in selected_day_counts:
        period_count = day_count * 48
        if len(ordered) < period_count:
            continue
        window_prices = ordered[:period_count]
        window_matrix = _slice_eac_matrix(eac_price_matrix, period_count)
        rolling = run_rolling_market_stack_policy(
            prices=window_prices,
            eac_price_matrix=window_matrix,
            asset=asset,
            initial_soc_mwh=initial_soc_mwh,
            forecast_model=forecast_model,
            config=config,
        )
        capture = run_phase4_market_stack_capture_comparison(
            prices=window_prices,
            eac_price_matrix=window_matrix,
            asset=asset,
            initial_soc_mwh=initial_soc_mwh,
            rolling_run=rolling,
            terminal_soc_policy=config.terminal_soc_policy,  # type: ignore[arg-type]
            terminal_soc_target_mwh=config.terminal_soc_target_mwh,
            solver_config=config.solver,
        )
        comparisons.append(
            Phase4SmokeWindowComparison(
                label=f"{day_count * 24}h",
                day_count=day_count,
                capture=capture,
            )
        )
    return comparisons


def skipped_phase4_smoke_windows(
    *,
    prices: list[WholesalePricePoint],
    window_day_counts: list[int] | None = None,
) -> list[Phase4SmokeWindowSkip]:
    """Return explicit skip records for 24h/48h smoke windows lacking enough data."""

    selected_day_counts = _selected_window_day_counts(window_day_counts)
    available_period_count = len(prices)
    skipped: list[Phase4SmokeWindowSkip] = []
    for day_count in selected_day_counts:
        required_period_count = day_count * 48
        if available_period_count >= required_period_count:
            continue
        skipped.append(
            Phase4SmokeWindowSkip(
                label=f"{day_count * 24}h",
                day_count=day_count,
                required_period_count=required_period_count,
                available_period_count=available_period_count,
                reason="insufficient_periods",
            )
        )
    return skipped


def _stress_price(day_index: int, settlement_period: int) -> float:
    intraday = _intraday_component(settlement_period)
    weekend_softening = -12 if day_index % 7 in {5, 6} else 0
    stress_uplift = _stress_uplift(day_index, settlement_period)
    solar_cannibalisation = -45 if day_index % 5 == 0 and 20 <= settlement_period <= 31 else 0
    return round(55 + intraday + weekend_softening + stress_uplift + solar_cannibalisation, 2)


def _intraday_component(settlement_period: int) -> float:
    if 13 <= settlement_period <= 18:
        return 35
    if 33 <= settlement_period <= 40:
        return 70
    if settlement_period <= 10:
        return -10
    if 22 <= settlement_period <= 30:
        return -25
    return 5


def _stress_uplift(day_index: int, settlement_period: int) -> float:
    if day_index % 6 in {2, 3} and 34 <= settlement_period <= 40:
        return 150
    if day_index % 9 == 4 and settlement_period in {17, 18, 33, 34, 35}:
        return 95
    return 0


def _slice_eac_matrix(eac_price_matrix: EACPriceMatrix, period_count: int) -> EACPriceMatrix:
    return EACPriceMatrix(
        cells=[
            cell.model_copy() for cell in eac_price_matrix.cells if cell.period_index < period_count
        ]
    )


def _selected_window_day_counts(window_day_counts: list[int] | None) -> list[int]:
    selected = window_day_counts or [1, 2]
    if any(day_count <= 0 for day_count in selected):
        msg = "window_day_counts must contain positive integers."
        raise ValueError(msg)
    return selected


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _validate_historical_sample_alignment(
    prices: list[WholesalePricePoint],
    eac_price_matrix: EACPriceMatrix,
) -> None:
    if not prices:
        msg = "Phase 4 historical sample requires at least one Elexon MID price."
        raise ValueError(msg)
    expected_duration_h = prices[0].duration_h
    seen_settlement_keys: set[tuple[str, int]] = set()
    for price in prices:
        if abs(price.duration_h - expected_duration_h) > 1e-9:
            msg = "Phase 4 historical Elexon MID sample must use a uniform duration."
            raise ValueError(msg)
        if not _is_settlement_boundary(price.delivery_start_utc) or not _is_settlement_boundary(
            price.delivery_end_utc
        ):
            msg = "Phase 4 historical Elexon MID sample must align to settlement boundaries."
            raise ValueError(msg)
        settlement_key = (price.settlement_date, price.settlement_period)
        if settlement_key in seen_settlement_keys:
            msg = "Phase 4 historical Elexon MID sample contains duplicate settlement periods."
            raise ValueError(msg)
        seen_settlement_keys.add(settlement_key)
    for previous, current in zip(prices, prices[1:], strict=False):
        if previous.delivery_start_utc >= current.delivery_start_utc:
            msg = "Phase 4 historical Elexon MID sample must be chronologically ordered."
            raise ValueError(msg)
        if previous.delivery_end_utc != current.delivery_start_utc:
            msg = "Phase 4 historical Elexon MID sample must be contiguous."
            raise ValueError(msg)
    uncovered = [
        period_index
        for period_index in range(len(prices))
        if not eac_price_matrix.available_cells_for_period(period_index)
    ]
    if uncovered:
        msg = f"NESO EAC sample does not cover Elexon period indexes {uncovered}."
        raise ValueError(msg)


def _historical_sample_hash(elexon_text: str, neso_text: str) -> str:
    payload = json.dumps(
        {
            "elexon": json.loads(elexon_text),
            "neso": json.loads(neso_text),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _fixture_metadata(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {}
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        msg = "Phase 4 fixture metadata must be a JSON object when present."
        raise ValueError(msg)
    return dict(metadata)


def _metadata_text(metadata: dict[str, object], key: str, default: str) -> str:
    value = metadata.get(key)
    if value is None:
        return default
    return str(value)


def _metadata_retrieved_at(metadata: dict[str, object]) -> datetime:
    value = metadata.get("retrieved_at_utc")
    if value is None:
        value = metadata.get("retrievedAtUtc")
    if value is None:
        return PHASE4_HISTORICAL_SAMPLE_RETRIEVED_AT_UTC
    return parse_source_datetime(str(value))


def _fixture_caveats(
    elexon_metadata: dict[str, object],
    neso_metadata: dict[str, object],
) -> list[str]:
    elexon_caveats = _metadata_string_list(elexon_metadata, "caveats") or [
        "Elexon MID is a public wholesale proxy, not an executable traded price.",
        "The aligned sample is a tiny historical smoke fixture, not a bankability forecast.",
    ]
    neso_caveats = _metadata_string_list(neso_metadata, "caveats") or [
        (
            "NESO EAC rows use delivery-start known-at convention until exact publication "
            "timestamps are verified."
        )
    ]
    return elexon_caveats + neso_caveats


def _metadata_string_list(metadata: dict[str, object], key: str) -> list[str]:
    raw = metadata.get(key, [])
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if not isinstance(raw, list):
        msg = f"Phase 4 fixture metadata {key!r} must be a string list when present."
        raise ValueError(msg)
    return [str(item) for item in raw]


def _neso_fixture_records(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [_record_mapping(record) for record in payload]
    if isinstance(payload, dict):
        records = payload.get("records")
        if records is None:
            records = payload.get("data")
        if not isinstance(records, list):
            msg = "Phase 4 NESO EAC fixture object must contain a records list."
            raise ValueError(msg)
        return [_record_mapping(record) for record in records]
    msg = "Phase 4 NESO EAC fixture must contain a JSON record list or object."
    raise ValueError(msg)


def _phase4_eac_product_labels(records: list[EACAuctionResult]) -> list[str]:
    labels = {record.product_model_label for record in records}
    return sorted(
        labels,
        key=lambda label: (PHASE4_EAC_PRODUCT_ORDER.get(label, 10_000), label),
    )


def _is_settlement_boundary(value: datetime) -> bool:
    value = ensure_aware_utc(value)
    return value.minute in {0, 30} and value.second == 0 and value.microsecond == 0


def _read_fixture_text(*, path: Path | None, packaged_name: str) -> str:
    if path is not None:
        return path.read_text(encoding="utf-8")
    return files(PHASE4_FIXTURES_PACKAGE).joinpath(packaged_name).read_text(encoding="utf-8")


def _record_mapping(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        msg = "Each Phase 4 NESO EAC fixture record must be an object."
        raise ValueError(msg)
    return dict(record)


def _historical_sample_label(prices: list[WholesalePricePoint]) -> str:
    start = ensure_aware_utc(prices[0].delivery_start_utc)
    end = ensure_aware_utc(prices[-1].delivery_end_utc)
    if start.date() == end.date():
        return f"elexon_mid_neso_eac_{start:%Y_%m_%d_%H%M}_{end:%H%M}_utc"
    return f"elexon_mid_neso_eac_{start:%Y_%m_%d_%H%M}_{end:%Y_%m_%d_%H%M}_utc"


def _elexon_source_url(prices: list[WholesalePricePoint]) -> str:
    if not prices:
        return f"{ELEXON_BASE_URL}{MARKET_INDEX_PATH}"
    start = ensure_aware_utc(prices[0].delivery_start_utc)
    end = ensure_aware_utc(prices[-1].delivery_end_utc)
    providers = sorted({price.data_provider for price in prices if price.data_provider is not None})
    provider_query = f"dataProviders={','.join(providers)}&" if providers else ""
    return (
        f"{ELEXON_BASE_URL}{MARKET_INDEX_PATH}?"
        f"{provider_query}from={_query_time(start)}&to={_query_time(end)}"
    )


def _query_time(value: datetime) -> str:
    return ensure_aware_utc(value).isoformat(timespec="seconds").replace("+00:00", "Z")
