# Implementation Conventions

This document defines binding conventions for implementation. If code, configs, tests or reports disagree with this file, the implementation must be corrected or this file must be updated with an explicit rationale.

## 1. Scope

These conventions apply to:

- canonical datasets;
- configuration files;
- optimisation inputs and outputs;
- policy evaluation;
- dashboard cache artefacts;
- methodology and README wording.

They are deliberately conservative. The project is a public-data research product, not a commercial trading or bankability model.

## 2. Units

Use these units in schemas, configs and chart labels.

| Quantity | Canonical unit | Notes |
|---|---:|---|
| Power | MW | Positive values are magnitudes unless explicitly signed. |
| Energy | MWh | State of charge is internal stored MWh. |
| Duration | hours | Settlement-period duration is explicit as `duration_h`. |
| Wholesale price | GBP/MWh | Applied to delivered/exported or imported AC energy. |
| EAC availability price | GBP/MW/h | Convert source units before optimisation. |
| Capacity Market price | GBP/kW/year | Converted to annual GBP using derated MW times 1000. |
| Revenue and cost | GBP | All objective terms must reduce to GBP. |
| Discount rate | fraction per year | Example: 0.08 means 8 percent. |
| Efficiency | fraction | Bounded in `(0, 1]`. |

Do not mix GBP/MWh and GBP/MW/h. Every service revenue term must include `duration_h` after price conversion.

## 3. Time

All canonical processing uses timezone-aware UTC timestamps.

Use local GB time only for display fields and charts.

Interval convention:

- `delivery_start_utc` is inclusive;
- `delivery_end_utc` is exclusive;
- `duration_h = (delivery_end_utc - delivery_start_utc).total_seconds() / 3600`.

Settlement-period handling must support daylight-saving transition dates:

- spring transition days may have fewer local-clock periods;
- autumn transition days may have more local-clock periods;
- UTC interval order is the source of truth.

No implementation may assume every day has exactly 48 settlement periods unless the input has already been validated as such for a specific synthetic fixture.

## 4. Known-Time Discipline

Rolling policies must obey:

```text
known_at_utc <= decision_time_utc
```

This applies to wholesale prices, EAC prices, benchmark inputs if ever used, forecast training data and scenario-generation training data.

Each rolling solve must record:

- `decision_time_utc`;
- input dataset IDs;
- input data snapshot hash;
- known-at policy;
- number of rows excluded because they were not yet known;
- forecast creation time;
- terminal SoC policy.

If exact publication time is not available, use a conservative documented policy and mark it as `known_at_policy` in the manifest. Conservative means later than the earliest plausible publication time, not earlier.

## 5. Sign Convention

Optimisation variables are non-negative magnitudes unless named as signed values.

Canonical variables:

- `charge_mw[t] >= 0`: AC import used for charging;
- `discharge_mw[t] >= 0`: AC export from discharging;
- `net_export_mw[t] = discharge_mw[t] - charge_mw[t]`;
- `soc_mwh[t]`: internal stored energy;
- `reserve_up_mw[s,t] >= 0`: upward/export/discharge capability held for service `s`;
- `reserve_down_mw[s,t] >= 0`: downward/import/charge capability held for service `s`.

Revenue from energy dispatch:

```text
energy_revenue_gbp[t] =
    price_gbp_per_mwh[t]
    * (discharge_mw[t] - charge_mw[t])
    * duration_h[t]
```

Negative prices are valid observations. Missing prices are not silently converted to zero.

## 6. AC/DC Convention

Market-facing power is AC MW. State of charge is internal stored MWh.

Energy balance:

```text
soc[t+1] = soc[t]
         + eta_charge * charge_mw[t] * duration_h[t]
         - discharge_mw[t] * duration_h[t] / eta_discharge
```

If a config provides round-trip efficiency only, default conversion is:

```text
eta_charge = eta_discharge = sqrt(round_trip_efficiency)
```

The conversion must be written to the run manifest.

## 7. Wholesale Proxy Convention

Central public-data wholesale source:

```text
source_id = ELEXON_BMRS_MID
price_source_type = MID
is_proxy = true
```

MID must be labelled as a public wholesale proxy and not described as day-ahead auction execution price. Provider labels such as `N2EXMIDP` and `APXMIDP` must be preserved.

Charts and reports should use wording such as:

```text
Wholesale proxy: Elexon BMRS Market Index Data, provider N2EXMIDP
```

## 8. EAC Availability Convention

EAC is modelled as a price-taking availability proxy.

Central Release 1 does not:

- clear EAC auctions;
- construct strategic bids;
- model acceptance probability;
- model performance penalties except as labelled sensitivity;
- infer BM revenue.

Availability revenue:

```text
service_revenue_gbp[s,t] =
    eac_price_gbp_per_mw_h[s,t]
    * committed_mw[s,t]
    * duration_h[t]
```

Do not apply efficiency directly to availability price. Efficiency belongs in reserve energy feasibility and any activation-energy sensitivity.

## 9. Reserve Physics

Power headroom and footroom:

```text
discharge_mw[t] + sum_s reserve_up_mw[s,t] <= P_export_max_mw
charge_mw[t]    + sum_s reserve_down_mw[s,t] <= P_import_max_mw
```

Scheduled charge/discharge binary mode may prevent simultaneous scheduled operation. It must not control reserve eligibility. An idle battery can hold reserve if power and energy constraints are satisfied.

Assuming reserve commitments are denominated as delivered AC MW:

```text
soc_mwh[t] - soc_min_mwh >= reserve_up_mw[s,t] * service_duration_h[s] / eta_discharge
soc_max_mwh - soc_mwh[t] >= reserve_down_mw[s,t] * service_duration_h[s] * eta_charge
```

Any alternative convention must be explicit in config, result schemas and methodology.

## 10. Terminal SoC

Perfect-foresight backtests default to cyclic terminal SoC:

```text
soc[last] = soc[first]
```

Rolling policies must use an explicit terminal policy:

- target equality;
- target band;
- linear deviation penalty;
- continuation-value approximation.

Free terminal SoC is allowed only for labelled diagnostic runs. It must not feed headline capture ratios.

## 11. Solver Defaults

Default solver stack:

- Pyomo model construction;
- HiGHS via `highspy` for open-source reproducibility;
- optional commercial solvers only if the same result schema and tests pass.

Every solve manifest must include:

- solver name and version;
- status and termination condition;
- objective value;
- best bound if available;
- MIP gap if applicable;
- time limit;
- wall time;
- model dimensions;
- config hash;
- data snapshot hash;
- code version or git commit if available.

Solver failure, infeasibility and unboundedness must fail loudly. CLI boundaries may convert these into user-facing errors, but production logic should not hide them.

## 12. Annualisation

When annualising a partial historical sample, the method must be explicit:

- `sample_scaled`: multiply by annual hours divided by sample hours;
- `calendar_year`: actual complete year;
- `scenario_repeated_year`: repeat a historical year as a finance assumption.

Do not compare annualised partial-sample values to external annual benchmarks without displaying the annualisation method.

## 13. Run Artefacts

Every canonical run should produce:

- machine-readable result table;
- run manifest;
- source manifest references;
- config snapshot or config hash;
- solver diagnostics;
- caveat flags;
- schema version.

The dashboard may only read curated artefacts under `results/dashboard/`; it must not run heavy optimisation or perform live API backfills.
