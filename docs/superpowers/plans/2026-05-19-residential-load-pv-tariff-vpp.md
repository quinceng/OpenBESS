# Residential Load/PV/Tariff/VPP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a residential bill-aware BESS calculator that uses household load, PV generation, retail import/export tariffs, and VPP payments, while keeping the residential branch separate from commercial and utility-scale modelling.

**Architecture:** Keep all household-specific logic under `src/gb_bess_revenue_stack/residential/`. Add typed time-series inputs, retail tariff schedules, VPP event assumptions, a no-battery bill baseline, and a battery dispatch optimiser that reports self-consumption savings, tariff arbitrage, export revenue, VPP revenue, and payback. Reuse project conventions for UTC timestamps, Pydantic validation, Pyomo/HiGHS solves, and test-first development.

**Tech Stack:** Python 3.11+, Pydantic v2, Pyomo/HiGHS for optimisation, pytest, ruff, mypy.

---

## Design Summary

Yes, this is possible and it belongs in the residential branch.

Status as of 2026-05-19: the first bill-aware household dispatch slice is now
implemented in the residential branch. The code models half-hour household load,
PV generation, import tariffs, export tariffs, grid-charging controls,
grid-charged export provenance and optional VPP event/payment logic without
modifying the commercial route-to-market model or the central MW/MWh
market-stack optimiser. The remaining residential work is scenario depth,
interpretation, longer-period evaluation and homeowner/investor output
packaging.

The implemented first release supports:

- half-hour household load in kWh;
- half-hour PV generation in kWh;
- import tariff in GBP/kWh;
- export tariff in GBP/kWh;
- optional standing charge, reported but excluded from dispatch decisions because it is not battery-controllable;
- DNO export limit in kW;
- inverter power limit in kW;
- battery energy capacity in kWh;
- round-trip efficiency, including product-specific values such as Tesla `solar_battery_home_efficiency=0.89`;
- optional solar-direct efficiency, reported in baseline PV-to-load treatment;
- optional grid charging;
- optional prevention of exporting grid-charged energy;
- optional VPP fixed annual payment and event payments;
- simple payback using capex range and annualised net benefit.

The optimiser should compute two cases over the same input interval:

1. **No-battery baseline bill:** PV serves local load first, surplus PV exports up to export limit, remaining load imports from grid.
2. **Battery case:** optimiser chooses PV-to-load, PV-to-battery, grid-to-battery, battery-to-load, battery-to-export, grid import, export, curtailment, and VPP event participation subject to battery and site constraints.

The result should explicitly split value into:

- self-consumption savings;
- tariff arbitrage savings;
- export revenue change;
- VPP revenue;
- total net benefit;
- annualised net benefit;
- payback range using installed capex low/high.

## Edge Cases To Handle

- **DST and local time:** accept aware timestamps only; normalise to UTC; reject naive timestamps.
- **Duplicate intervals:** reject duplicates by `delivery_start_utc`.
- **Missing intervals:** reject non-contiguous inputs by default; do not silently interpolate household data.
- **Irregular duration:** support any positive interval duration but test 30-minute intervals; power-to-energy constraints must use actual duration.
- **Negative import prices:** allow them; optimiser may charge from grid if grid charging is enabled.
- **Negative export prices:** allow them; optimiser should curtail PV rather than pay to export when curtailment is available.
- **Export limit:** cap total site export from PV plus battery, not only battery discharge.
- **Inverter limit:** cap battery charge and discharge power separately; if the product has one bidirectional inverter limit, use one configured `inverter_power_kw`.
- **PV exceeds load, battery, and export cap:** send residual to curtailment with zero value unless a curtailment penalty is explicitly configured.
- **Load exceeds PV plus battery:** import residual from grid; no unmet-load variable in the first release.
- **No PV data:** allow all PV values to be zero.
- **No load data:** allow zero load for pure export/tariff tests, but reject a whole file with zero load and zero PV unless the caller sets `allow_empty_energy_profile=True`.
- **Grid charging disabled:** force `grid_to_battery_kwh = 0`.
- **Grid-charged export disabled:** track PV-charged SOC and grid-charged SOC separately so battery export cannot use grid-charged energy.
- **High export tariff above import tariff:** no infinite loop because import/export are tied to physical load, PV, battery capacity, and grid-charge export rules.
- **VPP events during low SOC:** event participation should be limited by SOC, inverter power, export limit, and event-specific reserve requirements.
- **VPP fixed payment:** report separately from dispatch-linked event revenue so annual fixed assumptions do not distort half-hour dispatch.
- **Standing charge:** include in gross bills if configured, but do not count it as battery savings because it applies in both baseline and battery case.
- **Capex range:** derive low/high payback when both installed capex values exist; use total capex when range is absent.
- **Warranty:** report cycles during the sample and annualised cycles per year against warranty years; do not enforce warranty degradation in this first release.

## Follow-On Residential Scenario Depth

The bill-aware household dispatch engine is now the base. The next residential
workstream should use that engine to answer a different question: under what
household, tariff, PV, export-limit and VPP conditions does a residential BESS
become economically credible? This is intentionally separate from the commercial
and utility-scale Phase 4 market-stack work. It should remain under
`src/gb_bess_revenue_stack/residential/` and use kW/kWh household units.

The work should flow in this order:

1. **Keep the dispatch engine stable.** Preserve the implemented Tasks 1-10
   surface: validated half-hour inputs, no-battery baseline, battery dispatch,
   VPP event treatment, CSV loading, energy provenance, docs and verification.
   Do not add scenario sweeps until the single-household solve remains reliable.
2. **Add source-backed profile generation.** Replace the flat fallback as the
   main scenario input with named profile builders that combine annual
   consumption anchors with a half-hour shape. The flat profile should remain
   available, but every output must label it as a fallback.
3. **Add tariff scenario builders.** Build explicit import/export tariff
   schedules for flat public-reference tariffs, time-of-use tariffs and volatile
   smart tariffs. These builders should emit ordinary `ResidentialTariffSchedule`
   objects, so the optimiser does not need tariff-specific branches.
4. **Add household archetype sweeps.** Run named household cases across the same
   BESS products, PV sizes, export limits and tariffs. Each case should have a
   manifest explaining where the load, PV, tariff and export assumptions came
   from.
5. **Add annual and seasonal evaluation.** One-month proxy runs are useful for
   debugging, but homeowner economics should be judged on full-year runs plus
   seasonal slices. Annual outputs should not simply multiply one mild month
   unless the output says it is an annualised proxy.
6. **Add investor/homeowner outputs.** Produce summary tables that show simple
   payback, annual bill saving, VPP value, cycling/degradation sensitivity,
   break-even installed capex and the conditions that cause high-power products
   to outperform lower-power variants.

### Household Profile Scenarios

The scenario layer should support these named household archetypes:

| Archetype | Purpose | Profile basis |
|---|---|---|
| `flat_public_reference` | Conservative fallback and regression baseline | DESNZ annual London/GB domestic load divided evenly across intervals |
| `typical_domestic_shaped` | Normal non-EV household with morning/evening peaks | Public half-hour domestic shape normalised to DESNZ annual kWh |
| `high_evening_load` | Tests self-consumption value when battery discharge matters after sunset | Domestic shape with evening uplift and annual kWh uplift |
| `low_daytime_occupancy` | Tests PV surplus and export dependence | Daytime load depression with evening recovery |
| `ev_home_charging` | Tests large overnight or evening flexible load | Domestic base plus EV charging block assumptions |
| `heat_pump_winter` | Tests winter load and seasonal economics | Domestic base plus temperature/seasonal heat-pump demand proxy |
| `ev_and_heat_pump` | Tests high-electrification household economics | EV and heat-pump overlays on domestic base |
| `pv_heavy_low_load` | Tests export-limit and curtailment sensitivity | Lower domestic load with larger PV system |

Implementation detail: load-shape builders should normalise shape energy to a
declared annual kWh target instead of treating public sample data as the actual
household's total demand. A profile manifest should record:

- source annual load value and year;
- shape source and date retrieved;
- geography, region or profile class;
- annual kWh after normalisation;
- interval count, start/end timestamps and timezone handling;
- overlays applied, such as EV charging or heat-pump demand;
- whether the profile is measured, aggregated, synthetic or fallback.

Edge cases for profile generation:

- reject shape profiles with missing or duplicate settlement periods unless a
  deliberate repair mode is enabled and documented in the manifest;
- preserve UTC timestamps after any local-time conversion so DST days have the
  correct number of intervals;
- allow zero PV and zero EV/heat-pump overlays, but reject a scenario where load
  and PV are both zero unless explicitly marked as a solver test case;
- cap physically implausible overlay power values with clear validation errors
  rather than silently smoothing them away.

### Tariff Scenarios

Tariff scenarios should be explicit schedule builders, not hidden constants. At
minimum, support:

| Tariff case | Purpose |
|---|---|
| `flat_ofgem_reference` | Public baseline using the Ofgem average import rate and a public export tariff |
| `seg_low_export` | Low export-value sensitivity using a published SEG-style export rate |
| `economy_7_style` | Cheap overnight import with flat export |
| `go_style_ev` | Short cheap overnight window for EV/battery charging sensitivity |
| `flux_style` | Import/export time bands where export timing has material value |
| `agile_style_public_proxy` | Volatile half-hour import prices, including negative-price edge cases |
| `high_peak_spread` | Stress case for large peak/off-peak import spreads |

Every tariff schedule should record:

- supplier/source name where sourced;
- retrieval date or source publication date;
- region when tariff rates are region-specific;
- VAT treatment and whether rates are inclusive or exclusive;
- standing charge, reported separately from battery-controllable savings;
- export tariff eligibility caveats, especially where battery export is treated
  differently from solar export.

The optimiser should continue to see only import and export rates per interval.
Eligibility, tariff naming and caveats belong in the scenario metadata and
outputs.

### PV, Export-Limit And Installation Scenarios

PV scenarios should include `0`, `2`, `4`, `6` and `8` kWp cases, plus an
override for user-supplied PV generation. PVGIS-derived profiles should record
latitude, longitude, kWp, tilt, azimuth/aspect, system loss, PVGIS endpoint,
requested year and retrieval time. If a future calendar year is not available
from PVGIS, use the latest available weather year as a proxy and label the output
accordingly.

Export-limit scenarios should be treated separately from inverter rating:

| Export case | Treatment |
|---|---|
| `g98_single_phase_default` | `3.68 kW`, public-reference default |
| `g100_limited_5kw` | Export-limited scenario for larger batteries with a modest site cap |
| `g99_7kw` | Higher single-site approval sensitivity |
| `g99_10kw` | Tests direct local flexibility threshold sensitivity |
| `product_power_limit` | Export limit equal to configured product inverter power |
| `user_site_approval` | User-supplied value from actual DNO paperwork |

The effective export limit must always be the lower of configured site export
limit and product inverter export capability. Behind-the-meter load service is
limited by inverter power, not by the DNO export cap. The scenario outputs should
make this distinction obvious so high-power products are not incorrectly
penalised in household self-consumption cases.

Installation scenarios should include installed capex low/mid/high, optional
hardware-only cost, VAT treatment, installation uplift, inverter inclusion and
warranty years. Residential capex must stay separate from commercial capex.

### VPP And Flexibility Scenarios

The existing fixed annual VPP adder is only a coarse sensitivity. The deeper
scenario layer should add dispatch-linked event schedules:

- fixed annual participation fee;
- per-event availability payment;
- per-kWh delivered payment;
- event start/end timestamps;
- required export or required load reduction;
- minimum state-of-charge reservation before events;
- opt-out/failure penalty or missed-event shortfall reporting;
- whether grid charging is allowed before the event;
- whether grid-charged energy may be exported.

VPP events should affect dispatch when their timing is known in the scenario.
The model should report delivered event energy, event revenue, shortfall and any
bill impact caused by pre-charging or reserving state of charge. Annual VPP
income that is not linked to explicit events should remain separate from
dispatch-linked revenue.

### Degradation And Warranty Sensitivities

Homeowner payback should not ignore cycling forever. Add a first-order
degradation sensitivity before treating aggressive smart-tariff arbitrage as
economic:

- equivalent full cycles over the run;
- battery throughput in kWh;
- assumed cycle-life or warranted throughput where available;
- low/central/high degradation cost in GBP/kWh throughput;
- annual benefit before and after degradation sensitivity;
- payback range before and after degradation sensitivity.

Do not embed product warranty legal claims unless they are sourced. If only a
warranty year is known, report it separately from simple payback and flag when
payback exceeds warranty length.

### Scenario Matrix And Outputs

The default residential sweep should be deliberately small enough to run in CI or
as a smoke test, but broad enough to expose the economics:

| Dimension | Default sweep |
|---|---|
| Product | GivEnergy AIO2, Tesla Powerwall 3 low-power, Tesla Powerwall 3 high-power |
| Household | flat public reference, typical shaped, high evening load, EV, heat pump, EV plus heat pump |
| PV | 0, 4 and 8 kWp |
| Tariff | flat, Economy 7 style, Go style, Flux style |
| Export limit | 3.68 kW, 5 kW, 10 kW, product power |
| VPP | none, fixed annual, dispatch event schedule |
| Degradation | none, central throughput cost |

Full research sweeps can add more combinations, but the default should avoid a
cartesian explosion. Use named scenario bundles such as `conservative`,
`smart_tariff`, `electrified_home`, `pv_heavy` and `high_export_approval`.

Each run should write:

- scenario manifest JSON;
- household profile CSV used by the solver;
- tariff schedule CSV used by the solver;
- dispatch CSV;
- summary CSV with one row per scenario;
- sensitivity workbook with clear tabs for assumptions, scenario results,
  dispatch sample, value stack, payback and caveats.

Summary outputs should include:

- annual import cost avoided;
- annual export revenue change;
- annual VPP value;
- degradation sensitivity;
- annual net benefit;
- simple payback low/mid/high capex;
- break-even installed capex for 10-year and 15-year horizons;
- whether payback exceeds warranty;
- effective export limit and inverter power side by side;
- maximum battery discharge to household load, so high-power-product value is
  visible when load peaks actually bind.

### Interpretation Tests

Add tests or golden scenario checks that prevent misleading conclusions:

- a flat low-load profile should produce identical Tesla low/high power results
  when neither inverter power nor export limit binds;
- a high evening-load profile should allow the higher-power product to outperform
  only when load peaks exceed the lower inverter rating;
- raising export limit should not change self-consumption savings unless export
  constraints previously caused curtailment or changed battery dispatch;
- a smart tariff with cheap overnight import should create arbitrage value only
  when grid charging is enabled;
- VPP event revenue should fall when event delivery is constrained by SOC,
  inverter power or export limit;
- annualised one-month proxy outputs must be labelled differently from true
  full-year runs.

---

### Task 1: Residential Time-Series And Tariff Schemas

**Files:**
- Create: `src/gb_bess_revenue_stack/residential/profiles.py`
- Modify: `src/gb_bess_revenue_stack/residential/__init__.py`
- Test: `tests/unit/test_residential_profiles.py`

- [ ] **Step 1: Write the failing schema tests**

Add `tests/unit/test_residential_profiles.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from gb_bess_revenue_stack.residential import (
    ResidentialHouseholdInterval,
    ResidentialTariffPeriod,
    ResidentialTariffSchedule,
    validate_household_intervals,
)

pytestmark = pytest.mark.unit


def _interval(index: int, *, load_kwh: float = 1.0, pv_kwh: float = 0.5) -> ResidentialHouseholdInterval:
    start = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=30 * index)
    return ResidentialHouseholdInterval(
        delivery_start_utc=start,
        delivery_end_utc=start + timedelta(minutes=30),
        load_kwh=load_kwh,
        pv_generation_kwh=pv_kwh,
    )


def test_household_interval_rejects_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="aware"):
        ResidentialHouseholdInterval(
            delivery_start_utc=datetime(2026, 1, 1),
            delivery_end_utc=datetime(2026, 1, 1, 0, 30),
            load_kwh=1,
            pv_generation_kwh=0,
        )


def test_validate_household_intervals_rejects_duplicate_starts() -> None:
    rows = [_interval(0), _interval(0)]

    with pytest.raises(ValueError, match="duplicate"):
        validate_household_intervals(rows)


def test_validate_household_intervals_rejects_gaps() -> None:
    rows = [_interval(0), _interval(2)]

    with pytest.raises(ValueError, match="contiguous"):
        validate_household_intervals(rows)


def test_tariff_schedule_selects_rate_for_each_interval() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    schedule = ResidentialTariffSchedule(
        periods=(
            ResidentialTariffPeriod(
                valid_from_utc=start,
                valid_to_utc=start + timedelta(hours=1),
                import_rate_gbp_per_kwh=0.25,
                export_rate_gbp_per_kwh=0.15,
            ),
        )
    )

    rate = schedule.rate_for(start + timedelta(minutes=30))

    assert rate.import_rate_gbp_per_kwh == pytest.approx(0.25)
    assert rate.export_rate_gbp_per_kwh == pytest.approx(0.15)
```

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_residential_profiles.py -q
```

Expected: FAIL during import because `ResidentialHouseholdInterval`, `ResidentialTariffPeriod`, `ResidentialTariffSchedule`, and `validate_household_intervals` do not exist.

- [ ] **Step 3: Implement the schemas**

Create `src/gb_bess_revenue_stack/residential/profiles.py`:

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from gb_bess_revenue_stack.schemas.base import ensure_aware_utc


class ResidentialHouseholdInterval(BaseModel):
    """One household modelling interval using kWh energy quantities."""

    model_config = ConfigDict(extra="forbid")

    delivery_start_utc: datetime
    delivery_end_utc: datetime
    load_kwh: float = Field(ge=0)
    pv_generation_kwh: float = Field(default=0, ge=0)

    @field_validator("delivery_start_utc", "delivery_end_utc")
    @classmethod
    def datetimes_are_aware(cls, value: datetime) -> datetime:
        return ensure_aware_utc(value)

    @model_validator(mode="after")
    def end_after_start(self) -> ResidentialHouseholdInterval:
        if self.delivery_end_utc <= self.delivery_start_utc:
            msg = "delivery_end_utc must be after delivery_start_utc."
            raise ValueError(msg)
        return self

    @property
    def duration_h(self) -> float:
        return (self.delivery_end_utc - self.delivery_start_utc).total_seconds() / 3600


class ResidentialTariffPeriod(BaseModel):
    """Retail import/export tariff active over a UTC interval."""

    model_config = ConfigDict(extra="forbid")

    valid_from_utc: datetime
    valid_to_utc: datetime
    import_rate_gbp_per_kwh: float
    export_rate_gbp_per_kwh: float
    standing_charge_gbp_per_day: float = Field(default=0, ge=0)

    @field_validator("valid_from_utc", "valid_to_utc")
    @classmethod
    def datetimes_are_aware(cls, value: datetime) -> datetime:
        return ensure_aware_utc(value)

    @model_validator(mode="after")
    def end_after_start(self) -> ResidentialTariffPeriod:
        if self.valid_to_utc <= self.valid_from_utc:
            msg = "valid_to_utc must be after valid_from_utc."
            raise ValueError(msg)
        return self


class ResidentialTariffSchedule(BaseModel):
    """Retail tariff schedule with explicit interval lookup."""

    model_config = ConfigDict(extra="forbid")

    periods: tuple[ResidentialTariffPeriod, ...]

    def rate_for(self, timestamp_utc: datetime) -> ResidentialTariffPeriod:
        timestamp_utc = ensure_aware_utc(timestamp_utc)
        for period in self.periods:
            if period.valid_from_utc <= timestamp_utc < period.valid_to_utc:
                return period
        msg = f"No residential tariff period covers {timestamp_utc.isoformat()}."
        raise KeyError(msg)


def validate_household_intervals(
    rows: list[ResidentialHouseholdInterval],
    *,
    allow_empty_energy_profile: bool = False,
) -> list[ResidentialHouseholdInterval]:
    """Sort and validate household intervals for contiguous simulation."""

    if not rows:
        msg = "At least one residential household interval is required."
        raise ValueError(msg)
    ordered = sorted(rows, key=lambda row: row.delivery_start_utc)
    starts = [row.delivery_start_utc for row in ordered]
    if len(starts) != len(set(starts)):
        msg = "Household intervals contain duplicate delivery_start_utc values."
        raise ValueError(msg)
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if previous.delivery_end_utc != current.delivery_start_utc:
            msg = "Household intervals must be contiguous."
            raise ValueError(msg)
    if (
        not allow_empty_energy_profile
        and sum(row.load_kwh + row.pv_generation_kwh for row in ordered) == 0
    ):
        msg = "Household intervals contain no load or PV energy."
        raise ValueError(msg)
    return ordered
```

Modify `src/gb_bess_revenue_stack/residential/__init__.py` to export:

```python
from gb_bess_revenue_stack.residential.profiles import (
    ResidentialHouseholdInterval,
    ResidentialTariffPeriod,
    ResidentialTariffSchedule,
    validate_household_intervals,
)
```

Add the same four names to `__all__`.

- [ ] **Step 4: Run tests to verify green**

Run:

```bash
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_residential_profiles.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/gb_bess_revenue_stack/residential/profiles.py src/gb_bess_revenue_stack/residential/__init__.py tests/unit/test_residential_profiles.py
git commit -m "feat: add residential household profile schemas"
```

---

### Task 2: No-Battery Household Bill Baseline

**Files:**
- Create: `src/gb_bess_revenue_stack/residential/billing.py`
- Modify: `src/gb_bess_revenue_stack/residential/__init__.py`
- Test: `tests/unit/test_residential_billing.py`

- [ ] **Step 1: Write the failing baseline bill tests**

Add `tests/unit/test_residential_billing.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from gb_bess_revenue_stack.residential import (
    ResidentialHouseholdInterval,
    ResidentialTariffPeriod,
    ResidentialTariffSchedule,
    calculate_no_battery_bill,
)

pytestmark = pytest.mark.unit


def _tariff() -> ResidentialTariffSchedule:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return ResidentialTariffSchedule(
        periods=(
            ResidentialTariffPeriod(
                valid_from_utc=start,
                valid_to_utc=start + timedelta(days=1),
                import_rate_gbp_per_kwh=0.30,
                export_rate_gbp_per_kwh=0.10,
                standing_charge_gbp_per_day=0.50,
            ),
        )
    )


def test_no_battery_bill_uses_pv_for_load_then_exports_surplus() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    row = ResidentialHouseholdInterval(
        delivery_start_utc=start,
        delivery_end_utc=start + timedelta(minutes=30),
        load_kwh=1.0,
        pv_generation_kwh=1.5,
    )

    result = calculate_no_battery_bill([row], tariff=_tariff(), export_limit_kw=3.68)

    assert result.import_kwh == pytest.approx(0)
    assert result.pv_to_load_kwh == pytest.approx(1.0)
    assert result.export_kwh == pytest.approx(0.5)
    assert result.energy_bill_gbp == pytest.approx(-0.05)
    assert result.standing_charge_gbp == pytest.approx(0.50 / 48)


def test_no_battery_bill_applies_export_limit_and_curtails_surplus() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    row = ResidentialHouseholdInterval(
        delivery_start_utc=start,
        delivery_end_utc=start + timedelta(minutes=30),
        load_kwh=0,
        pv_generation_kwh=10,
    )

    result = calculate_no_battery_bill([row], tariff=_tariff(), export_limit_kw=3.68)

    assert result.export_kwh == pytest.approx(1.84)
    assert result.pv_curtailed_kwh == pytest.approx(8.16)
```

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_residential_billing.py -q
```

Expected: FAIL during import because `calculate_no_battery_bill` does not exist.

- [ ] **Step 3: Implement no-battery baseline**

Create `src/gb_bess_revenue_stack/residential/billing.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from gb_bess_revenue_stack.residential.profiles import (
    ResidentialHouseholdInterval,
    ResidentialTariffSchedule,
    validate_household_intervals,
)


class ResidentialBillBreakdown(BaseModel):
    """Household bill summary over a modelled interval."""

    model_config = ConfigDict(extra="forbid")

    import_kwh: float = Field(ge=0)
    export_kwh: float = Field(ge=0)
    pv_to_load_kwh: float = Field(ge=0)
    pv_curtailed_kwh: float = Field(ge=0)
    import_cost_gbp: float
    export_revenue_gbp: float
    energy_bill_gbp: float
    standing_charge_gbp: float = Field(ge=0)
    total_bill_gbp: float


def calculate_no_battery_bill(
    intervals: list[ResidentialHouseholdInterval],
    *,
    tariff: ResidentialTariffSchedule,
    export_limit_kw: float,
) -> ResidentialBillBreakdown:
    """Calculate household bill with PV but without a battery."""

    rows = validate_household_intervals(intervals, allow_empty_energy_profile=True)
    import_kwh = 0.0
    export_kwh = 0.0
    pv_to_load_kwh = 0.0
    pv_curtailed_kwh = 0.0
    import_cost = 0.0
    export_revenue = 0.0
    standing_charge = 0.0
    for row in rows:
        rate = tariff.rate_for(row.delivery_start_utc)
        direct_pv = min(row.load_kwh, row.pv_generation_kwh)
        residual_load = row.load_kwh - direct_pv
        surplus_pv = row.pv_generation_kwh - direct_pv
        export_cap_kwh = export_limit_kw * row.duration_h
        exported = min(surplus_pv, export_cap_kwh)
        curtailed = surplus_pv - exported
        import_kwh += residual_load
        export_kwh += exported
        pv_to_load_kwh += direct_pv
        pv_curtailed_kwh += curtailed
        import_cost += residual_load * rate.import_rate_gbp_per_kwh
        export_revenue += exported * rate.export_rate_gbp_per_kwh
        standing_charge += rate.standing_charge_gbp_per_day * row.duration_h / 24
    energy_bill = import_cost - export_revenue
    return ResidentialBillBreakdown(
        import_kwh=import_kwh,
        export_kwh=export_kwh,
        pv_to_load_kwh=pv_to_load_kwh,
        pv_curtailed_kwh=pv_curtailed_kwh,
        import_cost_gbp=import_cost,
        export_revenue_gbp=export_revenue,
        energy_bill_gbp=energy_bill,
        standing_charge_gbp=standing_charge,
        total_bill_gbp=energy_bill + standing_charge,
    )
```

Modify `src/gb_bess_revenue_stack/residential/__init__.py` to export:

```python
from gb_bess_revenue_stack.residential.billing import (
    ResidentialBillBreakdown,
    calculate_no_battery_bill,
)
```

- [ ] **Step 4: Run tests to verify green**

Run:

```bash
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_residential_billing.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/gb_bess_revenue_stack/residential/billing.py src/gb_bess_revenue_stack/residential/__init__.py tests/unit/test_residential_billing.py
git commit -m "feat: add residential no-battery bill baseline"
```

---

### Task 3: Residential Battery Dispatch Optimiser

**Files:**
- Create: `src/gb_bess_revenue_stack/residential/dispatch.py`
- Modify: `src/gb_bess_revenue_stack/residential/__init__.py`
- Test: `tests/unit/test_residential_household_dispatch.py`

- [ ] **Step 1: Write the failing optimiser tests**

Add `tests/unit/test_residential_household_dispatch.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from gb_bess_revenue_stack.residential import (
    ResidentialBessSystem,
    ResidentialHouseholdDispatchInput,
    ResidentialHouseholdInterval,
    ResidentialTariffPeriod,
    ResidentialTariffSchedule,
    solve_residential_household_dispatch,
)

pytestmark = pytest.mark.unit


def _system() -> ResidentialBessSystem:
    return ResidentialBessSystem(
        name="household-test",
        battery_capacity_kwh=4,
        inverter_power_kw=2,
        has_integrated_inverter=True,
        battery_cost_gbp=3_000,
        installation_cost_gbp=500,
    )


def _tariff() -> ResidentialTariffSchedule:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return ResidentialTariffSchedule(
        periods=(
            ResidentialTariffPeriod(
                valid_from_utc=start,
                valid_to_utc=start + timedelta(minutes=30),
                import_rate_gbp_per_kwh=0.10,
                export_rate_gbp_per_kwh=0.05,
            ),
            ResidentialTariffPeriod(
                valid_from_utc=start + timedelta(minutes=30),
                valid_to_utc=start + timedelta(hours=1),
                import_rate_gbp_per_kwh=0.40,
                export_rate_gbp_per_kwh=0.05,
            ),
        )
    )


def test_dispatch_charges_from_grid_when_off_peak_and_grid_charging_allowed() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    intervals = [
        ResidentialHouseholdInterval(
            delivery_start_utc=start,
            delivery_end_utc=start + timedelta(minutes=30),
            load_kwh=0,
            pv_generation_kwh=0,
        ),
        ResidentialHouseholdInterval(
            delivery_start_utc=start + timedelta(minutes=30),
            delivery_end_utc=start + timedelta(hours=1),
            load_kwh=1,
            pv_generation_kwh=0,
        ),
    ]
    result = solve_residential_household_dispatch(
        ResidentialHouseholdDispatchInput(
            system=_system(),
            intervals=intervals,
            tariff=_tariff(),
            dno_export_limit_kw=3.68,
            initial_soc_kwh=0,
            terminal_soc_policy="free",
            round_trip_efficiency=1,
            allow_grid_charging=True,
        )
    )

    assert result.rows[0].grid_to_battery_kwh > 0
    assert result.rows[1].battery_to_load_kwh == pytest.approx(1)
    assert result.battery_bill.energy_bill_gbp < result.no_battery_bill.energy_bill_gbp


def test_dispatch_respects_export_limit_for_pv_and_battery_export() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    intervals = [
        ResidentialHouseholdInterval(
            delivery_start_utc=start,
            delivery_end_utc=start + timedelta(minutes=30),
            load_kwh=0,
            pv_generation_kwh=8,
        )
    ]
    result = solve_residential_household_dispatch(
        ResidentialHouseholdDispatchInput(
            system=_system(),
            intervals=intervals,
            tariff=ResidentialTariffSchedule(
                periods=(
                    ResidentialTariffPeriod(
                        valid_from_utc=start,
                        valid_to_utc=start + timedelta(minutes=30),
                        import_rate_gbp_per_kwh=0.30,
                        export_rate_gbp_per_kwh=0.20,
                    ),
                )
            ),
            dno_export_limit_kw=3.68,
            initial_soc_kwh=0,
            terminal_soc_policy="free",
            round_trip_efficiency=1,
            allow_grid_charging=False,
        )
    )

    assert result.rows[0].site_export_kwh <= pytest.approx(1.84)
    assert result.rows[0].pv_curtailed_kwh > 0
```

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_residential_household_dispatch.py -q
```

Expected: FAIL during import because `ResidentialHouseholdDispatchInput` and `solve_residential_household_dispatch` do not exist.

- [ ] **Step 3: Implement the dispatch input/result models and solver**

Create `src/gb_bess_revenue_stack/residential/dispatch.py`.

Core model fields:

```python
from __future__ import annotations

from typing import Literal

import pyomo.environ as pyo
from pydantic import BaseModel, ConfigDict, Field, model_validator

from gb_bess_revenue_stack.config.models import SolverConfig
from gb_bess_revenue_stack.optimisation.solve import SolverDiagnostics, solve_dispatch_model
from gb_bess_revenue_stack.residential.billing import (
    ResidentialBillBreakdown,
    calculate_no_battery_bill,
)
from gb_bess_revenue_stack.residential.models import ResidentialBessSystem
from gb_bess_revenue_stack.residential.profiles import (
    ResidentialHouseholdInterval,
    ResidentialTariffSchedule,
    validate_household_intervals,
)

TerminalSocPolicy = Literal["free", "cyclic", "target"]


class ResidentialHouseholdDispatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system: ResidentialBessSystem
    intervals: list[ResidentialHouseholdInterval]
    tariff: ResidentialTariffSchedule
    dno_export_limit_kw: float = Field(gt=0)
    initial_soc_kwh: float = Field(ge=0)
    terminal_soc_policy: TerminalSocPolicy = "cyclic"
    terminal_soc_target_kwh: float | None = Field(default=None, ge=0)
    round_trip_efficiency: float = Field(default=0.90, gt=0, le=1)
    allow_grid_charging: bool = True
    allow_grid_charged_export: bool = False
    solver: SolverConfig = SolverConfig(time_limit_seconds=120, mip_gap=0.001)

    @model_validator(mode="after")
    def validate_soc_targets(self) -> ResidentialHouseholdDispatchInput:
        if self.initial_soc_kwh > self.system.battery_capacity_kwh:
            msg = "initial_soc_kwh must be within battery capacity."
            raise ValueError(msg)
        if self.terminal_soc_policy == "target" and self.terminal_soc_target_kwh is None:
            msg = "terminal_soc_target_kwh is required when terminal_soc_policy='target'."
            raise ValueError(msg)
        if (
            self.terminal_soc_target_kwh is not None
            and self.terminal_soc_target_kwh > self.system.battery_capacity_kwh
        ):
            msg = "terminal_soc_target_kwh must be within battery capacity."
            raise ValueError(msg)
        validate_household_intervals(self.intervals, allow_empty_energy_profile=True)
        return self
```

The Pyomo model should use kWh variables per interval:

- `pv_to_load_kwh[t]`;
- `pv_to_battery_kwh[t]`;
- `pv_to_export_kwh[t]`;
- `pv_curtailed_kwh[t]`;
- `grid_to_load_kwh[t]`;
- `grid_to_battery_kwh[t]`;
- `battery_to_load_kwh[t]`;
- `battery_to_export_kwh[t]`;
- `soc_kwh[t]`;
- `charge_binary[t]`;
- `discharge_binary[t]`.

Required constraints:

```python
pv_generation_kwh[t] == pv_to_load_kwh[t] + pv_to_battery_kwh[t] + pv_to_export_kwh[t] + pv_curtailed_kwh[t]
load_kwh[t] == pv_to_load_kwh[t] + grid_to_load_kwh[t] + battery_to_load_kwh[t]
site_export_kwh[t] == pv_to_export_kwh[t] + battery_to_export_kwh[t]
site_export_kwh[t] <= dno_export_limit_kw * duration_h[t]
pv_to_battery_kwh[t] + grid_to_battery_kwh[t] <= inverter_power_kw * duration_h[t] * charge_binary[t]
battery_to_load_kwh[t] + battery_to_export_kwh[t] <= inverter_power_kw * duration_h[t] * discharge_binary[t]
charge_binary[t] + discharge_binary[t] <= 1
soc_kwh[t + 1] == soc_kwh[t] + eta_charge * (pv_to_battery_kwh[t] + grid_to_battery_kwh[t]) - (battery_to_load_kwh[t] + battery_to_export_kwh[t]) / eta_discharge
soc_kwh[t] <= battery_capacity_kwh
```

If `allow_grid_charging=False`, add:

```python
grid_to_battery_kwh[t] == 0
```

If `allow_grid_charged_export=False`, first implementation can enforce:

```python
battery_to_export_kwh[t] <= pv_to_battery_kwh[t]
```

Then add Task 8 to improve this to full grid/PV SOC provenance tracking before enabling export-heavy products. This conservative rule avoids grid-import/export loops in the first implementation.

Objective:

```python
minimize sum(
    (grid_to_load_kwh[t] + grid_to_battery_kwh[t]) * import_rate[t]
    - (pv_to_export_kwh[t] + battery_to_export_kwh[t]) * export_rate[t]
)
```

The result models should include:

```python
class ResidentialHouseholdDispatchRow(BaseModel):
    interval_index: int
    delivery_start_utc: datetime
    delivery_end_utc: datetime
    load_kwh: float
    pv_generation_kwh: float
    grid_to_load_kwh: float
    grid_to_battery_kwh: float
    pv_to_load_kwh: float
    pv_to_battery_kwh: float
    pv_to_export_kwh: float
    battery_to_load_kwh: float
    battery_to_export_kwh: float
    site_export_kwh: float
    pv_curtailed_kwh: float
    soc_start_kwh: float
    soc_end_kwh: float
    import_rate_gbp_per_kwh: float
    export_rate_gbp_per_kwh: float
    period_bill_gbp: float
```

```python
class ResidentialHouseholdDispatchResult(BaseModel):
    rows: list[ResidentialHouseholdDispatchRow]
    no_battery_bill: ResidentialBillBreakdown
    battery_bill: ResidentialBillBreakdown
    self_consumption_savings_gbp: float
    tariff_arbitrage_savings_gbp: float
    export_revenue_delta_gbp: float
    total_bill_savings_gbp: float
    charged_kwh: float
    discharged_kwh: float
    equivalent_cycles: float
    solver: SolverDiagnostics
```

For first implementation, compute value splits as:

- `total_bill_savings_gbp = no_battery_bill.energy_bill_gbp - battery_bill.energy_bill_gbp`;
- `export_revenue_delta_gbp = battery_bill.export_revenue_gbp - no_battery_bill.export_revenue_gbp`;
- `self_consumption_savings_gbp = sum(battery_to_load_kwh[t] * import_rate[t])`;
- `tariff_arbitrage_savings_gbp = total_bill_savings_gbp - self_consumption_savings_gbp - export_revenue_delta_gbp`.

- [ ] **Step 4: Export from package**

Modify `src/gb_bess_revenue_stack/residential/__init__.py`:

```python
from gb_bess_revenue_stack.residential.dispatch import (
    ResidentialHouseholdDispatchInput,
    ResidentialHouseholdDispatchResult,
    ResidentialHouseholdDispatchRow,
    solve_residential_household_dispatch,
)
```

Add the four names to `__all__`.

- [ ] **Step 5: Run tests to verify green**

Run:

```bash
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_residential_household_dispatch.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/gb_bess_revenue_stack/residential/dispatch.py src/gb_bess_revenue_stack/residential/__init__.py tests/unit/test_residential_household_dispatch.py
git commit -m "feat: add residential household dispatch optimiser"
```

---

### Task 4: VPP Event And Payment Layer

**Files:**
- Create: `src/gb_bess_revenue_stack/residential/vpp.py`
- Modify: `src/gb_bess_revenue_stack/residential/dispatch.py`
- Modify: `src/gb_bess_revenue_stack/residential/__init__.py`
- Test: `tests/unit/test_residential_vpp.py`

- [ ] **Step 1: Write failing VPP tests**

Add `tests/unit/test_residential_vpp.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from gb_bess_revenue_stack.residential import (
    ResidentialVPPEvent,
    ResidentialVPPSchedule,
    calculate_vpp_revenue,
)

pytestmark = pytest.mark.unit


def test_vpp_fixed_payment_is_prorated_to_sample_hours() -> None:
    schedule = ResidentialVPPSchedule(
        annual_fixed_payment_gbp=120,
        events=(),
    )

    result = calculate_vpp_revenue(schedule, sample_hours=720, delivered_event_kwh={})

    assert result.fixed_payment_gbp == pytest.approx(120 * 720 / 8760)
    assert result.event_payment_gbp == pytest.approx(0)


def test_vpp_event_payment_requires_delivered_energy() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    schedule = ResidentialVPPSchedule(
        annual_fixed_payment_gbp=0,
        events=(
            ResidentialVPPEvent(
                event_id="winter-evening-1",
                event_start_utc=start,
                event_end_utc=start + timedelta(hours=1),
                payment_gbp_per_kwh=2,
                required_export_kwh=1.5,
            ),
        ),
    )

    result = calculate_vpp_revenue(
        schedule,
        sample_hours=1,
        delivered_event_kwh={"winter-evening-1": 1.0},
    )

    assert result.event_payment_gbp == pytest.approx(2.0)
    assert result.shortfall_kwh == pytest.approx(0.5)
```

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_residential_vpp.py -q
```

Expected: FAIL during import because VPP classes/functions do not exist.

- [ ] **Step 3: Implement VPP models**

Create `src/gb_bess_revenue_stack/residential/vpp.py`:

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from gb_bess_revenue_stack.schemas.base import ensure_aware_utc


class ResidentialVPPEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_start_utc: datetime
    event_end_utc: datetime
    payment_gbp_per_kwh: float = Field(ge=0)
    required_export_kwh: float = Field(default=0, ge=0)
    min_soc_kwh_at_start: float = Field(default=0, ge=0)

    @field_validator("event_start_utc", "event_end_utc")
    @classmethod
    def datetimes_are_aware(cls, value: datetime) -> datetime:
        return ensure_aware_utc(value)

    @model_validator(mode="after")
    def end_after_start(self) -> ResidentialVPPEvent:
        if self.event_end_utc <= self.event_start_utc:
            msg = "event_end_utc must be after event_start_utc."
            raise ValueError(msg)
        return self


class ResidentialVPPSchedule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annual_fixed_payment_gbp: float = Field(default=0, ge=0)
    events: tuple[ResidentialVPPEvent, ...] = ()


class ResidentialVPPRevenue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixed_payment_gbp: float = Field(ge=0)
    event_payment_gbp: float = Field(ge=0)
    total_vpp_revenue_gbp: float = Field(ge=0)
    delivered_event_kwh: float = Field(ge=0)
    shortfall_kwh: float = Field(ge=0)


def calculate_vpp_revenue(
    schedule: ResidentialVPPSchedule,
    *,
    sample_hours: float,
    delivered_event_kwh: dict[str, float],
) -> ResidentialVPPRevenue:
    fixed = schedule.annual_fixed_payment_gbp * sample_hours / 8760
    event_payment = 0.0
    delivered_total = 0.0
    shortfall = 0.0
    for event in schedule.events:
        delivered = max(0.0, delivered_event_kwh.get(event.event_id, 0.0))
        delivered_total += delivered
        paid_kwh = min(delivered, event.required_export_kwh) if event.required_export_kwh else delivered
        event_payment += paid_kwh * event.payment_gbp_per_kwh
        shortfall += max(0.0, event.required_export_kwh - delivered)
    return ResidentialVPPRevenue(
        fixed_payment_gbp=fixed,
        event_payment_gbp=event_payment,
        total_vpp_revenue_gbp=fixed + event_payment,
        delivered_event_kwh=delivered_total,
        shortfall_kwh=shortfall,
    )
```

- [ ] **Step 4: Integrate VPP into dispatch input/result**

Modify `src/gb_bess_revenue_stack/residential/dispatch.py`:

- add `vpp_schedule: ResidentialVPPSchedule | None = None` to `ResidentialHouseholdDispatchInput`;
- add `vpp_revenue: ResidentialVPPRevenue | None = None` to `ResidentialHouseholdDispatchResult`;
- add VPP event revenue to total benefit after solving;
- for first release, compute delivered event energy from `battery_to_export_kwh + pv_to_export_kwh` during event windows;
- add event `min_soc_kwh_at_start` constraints when an event starts on an interval boundary.

- [ ] **Step 5: Export VPP names from package**

Modify `src/gb_bess_revenue_stack/residential/__init__.py` to export:

```python
from gb_bess_revenue_stack.residential.vpp import (
    ResidentialVPPEvent,
    ResidentialVPPRevenue,
    ResidentialVPPSchedule,
    calculate_vpp_revenue,
)
```

- [ ] **Step 6: Run tests to verify green**

Run:

```bash
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_residential_vpp.py tests/unit/test_residential_household_dispatch.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/gb_bess_revenue_stack/residential/vpp.py src/gb_bess_revenue_stack/residential/dispatch.py src/gb_bess_revenue_stack/residential/__init__.py tests/unit/test_residential_vpp.py tests/unit/test_residential_household_dispatch.py
git commit -m "feat: add residential VPP event revenue"
```

---

### Task 5: Integrate Dispatch Results Into Payback Calculator

**Files:**
- Modify: `src/gb_bess_revenue_stack/residential/models.py`
- Test: `tests/unit/test_residential_bess.py`

- [ ] **Step 1: Write failing payback integration test**

Append to `tests/unit/test_residential_bess.py`:

```python
def test_household_payback_accepts_dispatch_result_components() -> None:
    system = get_residential_preset("tesla_powerwall_3")
    result = calculate_residential_household_payback(
        system,
        inputs=ResidentialHouseholdCalculatorInputs(
            dno_export_limit_kw=3.68,
            annual_self_consumption_savings_gbp=100,
            annual_tariff_arbitrage_savings_gbp=200,
            annual_export_revenue_gbp=30,
            annual_aggregator_vpp_revenue_gbp=40,
            include_aggregator_vpp=True,
        ),
    )

    assert result.total_annual_benefit_gbp == pytest.approx(370)
    assert result.simple_payback_years == pytest.approx(system.total_capex_gbp / 370)
```

Then add a second test after Task 3 result models exist:

```python
def test_household_dispatch_result_annualises_into_payback() -> None:
    # Build a minimal ResidentialHouseholdDispatchResult using model_construct so the
    # test focuses on annualisation and payback wiring, not optimiser details.
    dispatch = ResidentialHouseholdDispatchResult.model_construct(
        rows=[],
        no_battery_bill=None,
        battery_bill=None,
        self_consumption_savings_gbp=10,
        tariff_arbitrage_savings_gbp=5,
        export_revenue_delta_gbp=2,
        total_bill_savings_gbp=17,
        charged_kwh=20,
        discharged_kwh=18,
        equivalent_cycles=1.5,
        solver=None,
        vpp_revenue=ResidentialVPPRevenue(
            fixed_payment_gbp=1,
            event_payment_gbp=2,
            total_vpp_revenue_gbp=3,
            delivered_event_kwh=1,
            shortfall_kwh=0,
        ),
    )

    result = calculate_residential_household_payback_from_dispatch(
        get_residential_preset("tesla_powerwall_3"),
        dispatch=dispatch,
        sample_hours=24,
        dno_export_limit_kw=3.68,
    )

    assert result.total_annual_benefit_gbp == pytest.approx((17 + 3) * 365)
```

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_residential_bess.py -q
```

Expected: the new dispatch annualisation test fails until `calculate_residential_household_payback_from_dispatch` exists.

- [ ] **Step 3: Implement annualisation helper**

Modify `src/gb_bess_revenue_stack/residential/models.py`:

```python
def calculate_residential_household_payback_from_dispatch(
    system: ResidentialBessSystem,
    *,
    dispatch: ResidentialHouseholdDispatchResult,
    sample_hours: float,
    dno_export_limit_kw: float,
) -> ResidentialHouseholdCalculatorResult:
    if sample_hours <= 0:
        msg = "sample_hours must be positive."
        raise ValueError(msg)
    annualisation_factor = 8760 / sample_hours
    vpp_revenue = 0.0 if dispatch.vpp_revenue is None else dispatch.vpp_revenue.total_vpp_revenue_gbp
    return calculate_residential_household_payback(
        system,
        inputs=ResidentialHouseholdCalculatorInputs(
            dno_export_limit_kw=dno_export_limit_kw,
            annual_self_consumption_savings_gbp=dispatch.self_consumption_savings_gbp
            * annualisation_factor,
            annual_tariff_arbitrage_savings_gbp=dispatch.tariff_arbitrage_savings_gbp
            * annualisation_factor,
            annual_export_revenue_gbp=dispatch.export_revenue_delta_gbp * annualisation_factor,
            annual_aggregator_vpp_revenue_gbp=vpp_revenue * annualisation_factor,
            include_aggregator_vpp=True,
        ),
    )
```

Import `ResidentialHouseholdDispatchResult` inside the function body to avoid circular import:

```python
from gb_bess_revenue_stack.residential.dispatch import ResidentialHouseholdDispatchResult
```

- [ ] **Step 4: Export helper**

Modify `src/gb_bess_revenue_stack/residential/__init__.py` to export `calculate_residential_household_payback_from_dispatch`.

- [ ] **Step 5: Run tests to verify green**

Run:

```bash
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_residential_bess.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/gb_bess_revenue_stack/residential/models.py src/gb_bess_revenue_stack/residential/__init__.py tests/unit/test_residential_bess.py
git commit -m "feat: annualise residential dispatch into payback"
```

---

### Task 6: Residential Household CSV Loader And Smoke Fixture

**Files:**
- Create: `src/gb_bess_revenue_stack/residential/io.py`
- Create: `tests/fixtures/residential_household_profile.csv`
- Create: `tests/fixtures/residential_tariff.csv`
- Test: `tests/unit/test_residential_io.py`

- [ ] **Step 1: Write failing IO tests**

Add `tests/unit/test_residential_io.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from gb_bess_revenue_stack.residential.io import load_household_profile_csv, load_tariff_csv

pytestmark = pytest.mark.unit


def test_load_household_profile_csv_reads_load_and_pv_fixture() -> None:
    rows = load_household_profile_csv(Path("tests/fixtures/residential_household_profile.csv"))

    assert len(rows) == 4
    assert rows[0].load_kwh == pytest.approx(0.6)
    assert rows[0].pv_generation_kwh == pytest.approx(0)


def test_load_tariff_csv_reads_import_and_export_rates() -> None:
    tariff = load_tariff_csv(Path("tests/fixtures/residential_tariff.csv"))

    rate = tariff.periods[0]

    assert rate.import_rate_gbp_per_kwh == pytest.approx(0.10)
    assert rate.export_rate_gbp_per_kwh == pytest.approx(0.15)
```

- [ ] **Step 2: Add fixtures**

Create `tests/fixtures/residential_household_profile.csv`:

```csv
delivery_start_utc,delivery_end_utc,load_kwh,pv_generation_kwh
2026-01-01T00:00:00Z,2026-01-01T00:30:00Z,0.6,0
2026-01-01T00:30:00Z,2026-01-01T01:00:00Z,0.5,0
2026-01-01T01:00:00Z,2026-01-01T01:30:00Z,0.4,1.2
2026-01-01T01:30:00Z,2026-01-01T02:00:00Z,1.0,0
```

Create `tests/fixtures/residential_tariff.csv`:

```csv
valid_from_utc,valid_to_utc,import_rate_gbp_per_kwh,export_rate_gbp_per_kwh,standing_charge_gbp_per_day
2026-01-01T00:00:00Z,2026-01-01T01:00:00Z,0.10,0.15,0.50
2026-01-01T01:00:00Z,2026-01-01T02:00:00Z,0.40,0.15,0.50
```

- [ ] **Step 3: Run tests to verify red**

Run:

```bash
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_residential_io.py -q
```

Expected: FAIL because `gb_bess_revenue_stack.residential.io` does not exist.

- [ ] **Step 4: Implement CSV loaders**

Create `src/gb_bess_revenue_stack/residential/io.py`:

```python
from __future__ import annotations

import csv
from pathlib import Path

from gb_bess_revenue_stack.residential.profiles import (
    ResidentialHouseholdInterval,
    ResidentialTariffPeriod,
    ResidentialTariffSchedule,
    validate_household_intervals,
)
from gb_bess_revenue_stack.schemas.base import parse_source_datetime


def load_household_profile_csv(path: str | Path) -> list[ResidentialHouseholdInterval]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    intervals = [
        ResidentialHouseholdInterval(
            delivery_start_utc=parse_source_datetime(row["delivery_start_utc"]),
            delivery_end_utc=parse_source_datetime(row["delivery_end_utc"]),
            load_kwh=float(row["load_kwh"]),
            pv_generation_kwh=float(row["pv_generation_kwh"]),
        )
        for row in rows
    ]
    return validate_household_intervals(intervals)


def load_tariff_csv(path: str | Path) -> ResidentialTariffSchedule:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return ResidentialTariffSchedule(
        periods=tuple(
            ResidentialTariffPeriod(
                valid_from_utc=parse_source_datetime(row["valid_from_utc"]),
                valid_to_utc=parse_source_datetime(row["valid_to_utc"]),
                import_rate_gbp_per_kwh=float(row["import_rate_gbp_per_kwh"]),
                export_rate_gbp_per_kwh=float(row["export_rate_gbp_per_kwh"]),
                standing_charge_gbp_per_day=float(row.get("standing_charge_gbp_per_day") or 0),
            )
            for row in rows
        )
    )
```

- [ ] **Step 5: Run tests to verify green**

Run:

```bash
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_residential_io.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/gb_bess_revenue_stack/residential/io.py tests/fixtures/residential_household_profile.csv tests/fixtures/residential_tariff.csv tests/unit/test_residential_io.py
git commit -m "feat: add residential household CSV loaders"
```

---

### Task 7: CLI Smoke Command And Output Artifacts

**Files:**
- Modify: `src/gb_bess_revenue_stack/cli.py`
- Modify: `tests/unit/test_cli.py`
- Test: `tests/unit/test_residential_household_smoke.py`

- [ ] **Step 1: Add failing CLI help test**

Append to `tests/unit/test_cli.py`:

```python
def test_cli_exposes_run_residential_household_smoke_subcommand() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["run-residential-household-smoke", "--help"])

    assert result.exit_code == 0
    assert "--profile-csv" in result.output
    assert "--tariff-csv" in result.output
    assert "--output-dir" in result.output
```

- [ ] **Step 2: Add failing smoke output test**

Create `tests/unit/test_residential_household_smoke.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gb_bess_revenue_stack.cli import app

pytestmark = pytest.mark.unit


def test_residential_household_smoke_writes_summary_and_dispatch(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run-residential-household-smoke",
            "--profile-csv",
            "tests/fixtures/residential_household_profile.csv",
            "--tariff-csv",
            "tests/fixtures/residential_tariff.csv",
            "--output-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["branch_name"] == "residential"
    assert summary["total_bill_savings_gbp"] >= 0
    assert (tmp_path / "dispatch.csv").exists()
```

- [ ] **Step 3: Run tests to verify red**

Run:

```bash
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_cli.py::test_cli_exposes_run_residential_household_smoke_subcommand tests/unit/test_residential_household_smoke.py -q
```

Expected: FAIL because the CLI command does not exist.

- [ ] **Step 4: Implement command**

Modify `src/gb_bess_revenue_stack/cli.py`:

```python
@app.command()
def run_residential_household_smoke(
    profile_csv: Annotated[Path, typer.Option(help="Household load/PV profile CSV.")] = Path("tests/fixtures/residential_household_profile.csv"),
    tariff_csv: Annotated[Path, typer.Option(help="Retail tariff CSV.")] = Path("tests/fixtures/residential_tariff.csv"),
    output_dir: Annotated[Path, typer.Option(help="Output directory.")] = Path("results/runs/residential_household_smoke"),
) -> None:
    """Run a network-free residential household load/PV/tariff smoke solve."""

    profile = load_household_profile_csv(profile_csv)
    tariff = load_tariff_csv(tariff_csv)
    system = get_residential_preset("tesla_powerwall_3")
    result = solve_residential_household_dispatch(
        ResidentialHouseholdDispatchInput(
            system=system,
            intervals=profile,
            tariff=tariff,
            dno_export_limit_kw=3.68,
            initial_soc_kwh=system.battery_capacity_kwh * 0.5,
            terminal_soc_policy="cyclic",
            round_trip_efficiency=0.89,
            allow_grid_charging=True,
            allow_grid_charged_export=False,
        )
    )
    payback = calculate_residential_household_payback_from_dispatch(
        system,
        dispatch=result,
        sample_hours=sum(row.duration_h for row in profile),
        dno_export_limit_kw=3.68,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "branch_name": "residential",
                "system_name": system.name,
                "total_bill_savings_gbp": result.total_bill_savings_gbp,
                "annualised_benefit_gbp": payback.total_annual_benefit_gbp,
                "simple_payback_years": payback.simple_payback_years,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_residential_dispatch_csv(result, output_dir / "dispatch.csv")
    typer.echo(
        f"Solved residential household smoke: savings_gbp={result.total_bill_savings_gbp:.2f}"
    )
```

Also add `_write_residential_dispatch_csv` using `csv.DictWriter`.

- [ ] **Step 5: Run tests to verify green**

Run:

```bash
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_cli.py::test_cli_exposes_run_residential_household_smoke_subcommand tests/unit/test_residential_household_smoke.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/gb_bess_revenue_stack/cli.py tests/unit/test_cli.py tests/unit/test_residential_household_smoke.py
git commit -m "feat: add residential household smoke command"
```

---

### Task 8: Grid-Charged Energy Provenance Hardening

**Files:**
- Modify: `src/gb_bess_revenue_stack/residential/dispatch.py`
- Test: `tests/unit/test_residential_household_dispatch.py`

- [ ] **Step 1: Add failing provenance test**

Append to `tests/unit/test_residential_household_dispatch.py`:

```python
def test_grid_charged_energy_cannot_be_exported_when_disabled() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    intervals = [
        ResidentialHouseholdInterval(
            delivery_start_utc=start,
            delivery_end_utc=start + timedelta(minutes=30),
            load_kwh=0,
            pv_generation_kwh=0,
        ),
        ResidentialHouseholdInterval(
            delivery_start_utc=start + timedelta(minutes=30),
            delivery_end_utc=start + timedelta(hours=1),
            load_kwh=0,
            pv_generation_kwh=0,
        ),
    ]
    tariff = ResidentialTariffSchedule(
        periods=(
            ResidentialTariffPeriod(
                valid_from_utc=start,
                valid_to_utc=start + timedelta(minutes=30),
                import_rate_gbp_per_kwh=0.01,
                export_rate_gbp_per_kwh=0.00,
            ),
            ResidentialTariffPeriod(
                valid_from_utc=start + timedelta(minutes=30),
                valid_to_utc=start + timedelta(hours=1),
                import_rate_gbp_per_kwh=0.01,
                export_rate_gbp_per_kwh=1.00,
            ),
        )
    )

    result = solve_residential_household_dispatch(
        ResidentialHouseholdDispatchInput(
            system=_system(),
            intervals=intervals,
            tariff=tariff,
            dno_export_limit_kw=3.68,
            initial_soc_kwh=0,
            terminal_soc_policy="free",
            round_trip_efficiency=1,
            allow_grid_charging=True,
            allow_grid_charged_export=False,
        )
    )

    assert sum(row.battery_to_export_kwh for row in result.rows) == pytest.approx(0)
```

- [ ] **Step 2: Run test to verify red against conservative Task 3 shortcut**

Run:

```bash
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_residential_household_dispatch.py::test_grid_charged_energy_cannot_be_exported_when_disabled -q
```

Expected: FAIL if the shortcut does not track SOC provenance over time.

- [ ] **Step 3: Add SOC provenance pools**

Modify `src/gb_bess_revenue_stack/residential/dispatch.py`:

- add `soc_grid_kwh[t]`;
- add `soc_pv_kwh[t]`;
- enforce `soc_kwh[t] == soc_grid_kwh[t] + soc_pv_kwh[t]`;
- update `soc_grid_kwh` with `grid_to_battery_kwh`;
- update `soc_pv_kwh` with `pv_to_battery_kwh`;
- split battery discharge into `grid_battery_to_load_kwh`, `pv_battery_to_load_kwh`, `grid_battery_to_export_kwh`, `pv_battery_to_export_kwh`;
- when `allow_grid_charged_export=False`, force `grid_battery_to_export_kwh[t] == 0`;
- keep public row fields aggregated as `battery_to_load_kwh` and `battery_to_export_kwh`.

- [ ] **Step 4: Run dispatch tests to verify green**

Run:

```bash
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_residential_household_dispatch.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/gb_bess_revenue_stack/residential/dispatch.py tests/unit/test_residential_household_dispatch.py
git commit -m "fix: track residential battery energy provenance"
```

---

### Task 9: Documentation And Assumptions Ledger

**Files:**
- Modify: `docs/residential_bess_assumptions.md`
- Modify: `docs/model_boundaries.md`
- Modify: `docs/known_limitations.md`

- [ ] **Step 1: Document the bill-aware calculator**

Add a section to `docs/residential_bess_assumptions.md`:

```markdown
## Bill-Aware Household Dispatch

The residential branch can model half-hour household load, PV generation,
retail import/export tariffs and optional VPP payments. Inputs use kWh and kW.
The model reports a no-battery bill baseline and a battery bill case over the
same intervals.

Value stack:

- self-consumption savings from using battery discharge to serve household load;
- tariff arbitrage savings from grid charging and later load service where enabled;
- export revenue delta from changed PV/battery export;
- VPP fixed and event-linked revenue.

The model uses aware UTC timestamps. Local time and DST conversion must happen
before data enters the model. Missing or duplicate intervals are rejected.
```

- [ ] **Step 2: Update model boundaries**

Add to `docs/model_boundaries.md`:

```markdown
Residential bill-aware dispatch is a household calculator. It is not a supplier
bill replica, a network charging model, or a market registration model. Retail
tariff inputs are user/model assumptions unless linked to a licensed tariff
source. VPP payments are scenario assumptions unless sourced from a specific
contract.
```

- [ ] **Step 3: Update known limitations**

Add to `docs/known_limitations.md`:

```markdown
Residential calculator limitations:

- no degradation cost is applied to cycling in the first bill-aware release;
- no VAT, network charge breakdown, or supplier-specific bill reconstruction is
  attempted;
- VPP participation is scenario-based and does not represent a guaranteed
  contract;
- household load/PV quality is the user's responsibility unless a source
  manifest is attached.
```

- [ ] **Step 4: Commit**

```bash
git add docs/residential_bess_assumptions.md docs/model_boundaries.md docs/known_limitations.md
git commit -m "docs: document residential bill-aware calculator"
```

---

### Task 10: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run targeted residential tests**

Run:

```bash
$env:PYTHONPATH='src'; python -m pytest tests/unit/test_residential_profiles.py tests/unit/test_residential_billing.py tests/unit/test_residential_household_dispatch.py tests/unit/test_residential_vpp.py tests/unit/test_residential_io.py tests/unit/test_residential_household_smoke.py tests/unit/test_residential_bess.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full unit suite**

Run:

```bash
$env:PYTHONPATH='src'; python -m pytest -q
```

Expected: PASS with all non-integration tests.

- [ ] **Step 3: Run lint and format checks**

Run:

```bash
python -m ruff check .
python -m ruff format --check .
```

Expected: both commands exit 0.

- [ ] **Step 4: Run type checks**

Run:

```bash
$env:PYTHONPATH='src'; $cache = Join-Path $env:TEMP 'mypy_cache_residential_bill'; python -m mypy src --cache-dir $cache
```

Expected: `Success: no issues found`.

- [ ] **Step 5: Run smoke command**

Run:

```bash
$env:PYTHONPATH='src'; python -c "from gb_bess_revenue_stack.cli import app; app()" run-residential-household-smoke --output-dir results/runs/residential_household_smoke
```

Expected output includes:

```text
Solved residential household smoke:
```

Expected files:

```text
results/runs/residential_household_smoke/summary.json
results/runs/residential_household_smoke/dispatch.csv
```

- [ ] **Step 6: Commit verification-only artifact changes if fixtures or docs changed during verification**

```bash
git status --short
```

Expected: no unexpected generated files outside ignored result directories.

---

## Self-Review

Spec coverage:

- Household load: Task 1 schemas, Task 3 dispatch constraints, Task 6 CSV loader.
- PV generation: Task 1 schemas, Task 2 baseline, Task 3 dispatch constraints.
- Retail import/export tariff: Task 1 tariff schedule, Task 2 baseline, Task 3 optimiser objective, Task 6 loader.
- VPP payment data: Task 4 event/fixed payment layer and dispatch integration.
- Residential branch separation: all production modules live under `src/gb_bess_revenue_stack/residential/`; commercial and central market-stack modules are not modified.
- Payback-style outputs: Task 5 integrates dispatch results into existing payback output.
- Edge cases: listed explicitly and mapped to schema validation, bill baseline, dispatch constraints, provenance hardening, and docs.

Placeholder scan:

- The plan contains no placeholder tasks. Every task has exact files, tests, commands and expected outcomes.

Type consistency:

- `ResidentialHouseholdInterval`, `ResidentialTariffPeriod`, `ResidentialTariffSchedule`, `ResidentialBillBreakdown`, `ResidentialHouseholdDispatchInput`, `ResidentialHouseholdDispatchResult`, `ResidentialVPPEvent`, `ResidentialVPPSchedule`, and `ResidentialVPPRevenue` are consistently named across tests, exports and implementation steps.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-19-residential-load-pv-tariff-vpp.md`. Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.
