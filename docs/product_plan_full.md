# GB BESS Revenue-Stack Optimiser — Revised Product Plan

**Project title:** Open GB BESS Revenue-Stack Optimiser  
**Repository name:** `gb-bess-revenue-stack`  
**Python package:** `gb_bess_revenue_stack`  
**Product standard:** Portfolio-grade, reproducible, public-data research product  
**Version:** 3.0 revised canonical plan  
**Prepared:** 2026-05-16  
**Primary user:** energy-market modeller, graduate analyst, technical portfolio reviewer  
**Target audience:** Aurora Energy Research, LCP Delta, Cornwall Insight, AFRY, Baringa, NESO, Frontier Economics, DESNZ, Climate Change Committee

---

## 1. Product proposition

Build a transparent public-data GB battery energy storage revenue-stack optimiser that demonstrates market-modelling judgement, not merely battery-arbitrage coding.

The product optimises a reference 2-hour GB BESS using:

- Elexon market-index data as a clearly labelled public wholesale-price proxy;
- NESO EAC dynamic-response availability prices as a price-taking availability proxy;
- Capacity Market annuity scenarios, not a half-hourly dispatch product;
- perfect-foresight dispatch as an upper-bound diagnostic;
- rolling-horizon operation as the main realisable policy comparison;
- deterministic scenario sweeps for uncertainty and sensitivity in Release 1;
- degradation and augmentation as scenario assumptions;
- 15-year NPV as illustrative scenario appraisal, not bankability analysis;
- public benchmark reconciliation against Modo-style industry anchors without claiming replication.

The final artefact is a polished open-source repository, cached dashboard, methodology paper and interview demo that answers:

> Under transparent public-data assumptions, how much value can a reference 2-hour GB BESS capture from wholesale proxy and EAC availability revenues, how much of a perfect-foresight ceiling is achievable by a no-leakage rolling policy, and which public-data limitations explain divergence from commercial benchmark narratives?

---

## 2. What changed in this revised plan

This revision incorporates the plan critique and makes the following decisions canonical:

1. **One repository layout:** package path is `src/gb_bess_revenue_stack/`; model outputs go under `results/`; human-readable reports go under `reports/`.
2. **One roadmap:** Release 1 has six implementation phases plus a separate optional Phase 7 stochastic extension.
3. **P1-00 gate:** source, licence and data-shape feasibility is verified before production clients are built.
4. **No-leakage by design:** every canonical dataset carries `event_time_utc`, `known_at_utc`, `retrieved_at_utc`, `source_id`, and `quality_flag` where applicable.
5. **Correct reserve physics:** EAC reserve is modelled through headroom/footroom, not binary dispatch mode. Idle batteries can hold reserve. Upward reserve energy feasibility uses discharge efficiency when reserve is AC-denominated.
6. **EAC wording tightened:** the model is a price-taking EAC availability proxy, not a full auction-clearing model.
7. **Early rolling slice:** an energy-only rolling-horizon slice is built immediately after the deterministic baseline before full EAC rolling is attempted.
8. **Stochastic de-scoped from core Release 1:** Release 1 uses deterministic scenario sweeps and forecast-error sensitivity; stochastic programming is an optional Phase 7 extension only.
9. **Modo comparison reframed:** the benchmark section is a reconciliation scorecard, not validation or replication.
10. **Finance boundary ledger added:** NPV exclusions are explicit so the product is not mistaken for bankable due diligence.

---

## 3. Non-negotiable product boundaries

### 3.1 Release 1 includes

- source/licence/data feasibility gate;
- assumptions ledger and source registry;
- Elexon public data client and wholesale proxy labelling;
- NESO EAC data pipeline and price-taking availability proxy;
- settlement-period and timestamp validation, including daylight-saving edge cases;
- deterministic perfect-foresight dispatch baseline;
- energy-only rolling-horizon vertical slice;
- EAC-aware rolling-horizon policy evaluation;
- deterministic scenario sweeps for price, EAC, CM, degradation, augmentation and forecast error;
- CM annuity scenarios and optional stress-period feasibility sensitivity;
- degradation throughput proxy and post-hoc rainflow audit if stable;
- illustrative NPV scenarios with finance exclusions;
- public benchmark reconciliation scorecard;
- cached Streamlit dashboard;
- methodology paper, reproducibility guide and interview demo script.

### 3.2 Release 1 excludes

- deterministic Balancing Mechanism counterfactual revenue for a hypothetical asset;
- full EAC auction-clearing simulation or strategic bid construction;
- endogenous GB price engine or whole-system dispatch model;
- RL trading agent;
- exact rainflow counting inside the MILP;
- electrochemical cell model;
- full PyPSA-GB calibration;
- zonal-pricing simulator;
- commercial bankability conclusion;
- Modo/Aurora/LCP replication claim;
- stochastic programming as a core deliverable.

### 3.3 Optional extensions after Release 1

- Phase 7 stochastic programming extension if rolling/EAC core is stable;
- observed BM appendix for real units using public BOA/BOD/PN/FPN data, clearly labelled ex-post;
- PyPSA-GB spread/cannibalisation sensitivity appendix;
- RNP/15-minute settlement sensitivity;
- global sensitivity analysis after local sensitivities are stable.

---

## 4. Success criteria

### 4.1 Technical correctness

- Energy balance conserves MWh with explicit charge/discharge efficiency.
- No SoC, power, import/export, reserve or terminal constraints are violated.
- Objective terms reduce dimensionally to pounds sterling.
- EAC reserve headroom/footroom allows idle reserve holding and does not force active dispatch.
- Upward AC reserve requires `MW × h / eta_discharge` stored energy above `soc_min`.
- Downward AC reserve requires `MW × h × eta_charge` empty capacity below `soc_max`.
- Perfect-foresight revenue is labelled as an upper bound, not a trading strategy.
- Rolling policies use no data with `known_at_utc > decision_time_utc`.
- CM is counted as an annual scenario value, not repeated per settlement period.
- Benchmark comparisons are reconciliations, not pass/fail validation tests.

### 4.2 Software quality

- `src/` layout with typed production code under `src/gb_bess_revenue_stack/`.
- No production logic hidden in notebooks.
- All external inputs validated through schemas.
- All network calls have bounded timeouts and retries.
- Every run has a manifest containing config hash, data snapshot hash, git commit if available, solver name/version/status, objective, wall time, MIP gap if relevant, and output paths.
- CI runs lint, format check, type check, unit tests and tiny-fixture regression tests.
- Dashboard loads from `results/dashboard/` without live API calls or solver requirements.

### 4.3 Portfolio signal

- README gives a one-screen explanation, headline chart and honest caveat.
- A reviewer can understand data sources, modelled markets, non-goals and main results in under 10 minutes.
- Methodology paper explains equations, assumptions, no-leakage validation, finance boundaries and benchmark reconciliation.
- The project visibly distinguishes itself from generic arbitrage repos through GB market interpretation and disciplined public-data limits.

---

## 5. Canonical repository layout

```text
gb-bess-revenue-stack/
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env.example
├── Makefile or justfile
├── ruff.toml
├── mypy.ini or pyrightconfig.json
├── pytest.ini
│
├── configs/
│   ├── asset_2h_50mw.yaml
│   ├── markets_gb.yaml
│   ├── solver_highs.yaml
│   ├── scenarios_cm.yaml
│   ├── scenarios_degradation.yaml
│   ├── scenarios_finance.yaml
│   └── scenarios_policy.yaml
│
├── docs/
│   ├── product_plan.md
│   ├── assumptions_ledger.md
│   ├── source_registry.yaml
│   ├── data_sources.md
│   ├── source_research_notes.md
│   ├── implementation_conventions.md
│   ├── model_boundaries.md
│   ├── finance_boundaries.md
│   ├── quality_gates.md
│   ├── methodology.md
│   ├── known_limitations.md
│   ├── reproducibility.md
│   ├── validation_memo.md
│   ├── interview_demo_script.md
│   ├── phase_reviews/
│   └── adr/
│
├── src/gb_bess_revenue_stack/
│   ├── __init__.py
│   ├── cli.py
│   ├── config/
│   ├── data/
│   ├── schemas/
│   ├── markets/
│   ├── optimisation/
│   ├── policies/
│   ├── degradation/
│   ├── finance/
│   ├── validation/
│   ├── visualisation/
│   └── utils/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── regression/
│   ├── fixtures/
│   └── conftest.py
│
├── dashboard/
│   ├── streamlit_app.py
│   ├── pages/
│   └── assets/
│
├── data/
│   ├── raw/          # gitignored
│   ├── processed/    # gitignored except tiny fixtures
│   └── reference/    # small committed reference files only
│
├── results/
│   ├── runs/         # gitignored except selected public fixtures
│   └── dashboard/    # compact cached dashboard artefacts if licence permits
│
├── reports/
│   ├── data_quality/
│   ├── phase_2_baseline/
│   ├── phase_2_5_rolling_slice/
│   ├── phase_3_eac_availability/
│   ├── phase_4_policy_sweeps/
│   ├── phase_5_finance_reconciliation/
│   └── release/
│
└── notebooks/
    └── README.md     # exploratory only; no production source of truth
```

---

## 6. Data and source architecture

### 6.1 P1-00 feasibility gate

Before production code, verify:

- exact Elexon/BMRS MID endpoint, fields, units, rate limits and query shape for the wholesale proxy. Research anchor: `/balancing/pricing/market-index`, providers `N2EXMIDP` and `APXMIDP`, fields such as `startTime`, `settlementDate`, `settlementPeriod`, `price` and `volume`;
- NESO EAC file/source format, product labels, delivery windows, timestamps, prices and volumes. Research anchor: NESO EAC auction results data portal, daily CSV/API resources, UTC `deliveryStart`/`deliveryEnd`, NESO Open Data Licence;
- whether EAC publication/known times are available or require conservative assumptions, including product-specific auction-session/gate-closure timing rather than a generic delivery-date rule;
- CM clearing-price and derating-factor source availability by delivery year, auction and duration. Research anchor values for the 2024/25 auction-cycle article: 2h BESS T-1 27.15%, 2h BESS T-4 20.94%; final config must use official/source-verified values;
- public Modo anchor availability and reuse limitations;
- raw and processed data volumes;
- data licences and redistribution constraints;
- smallest viable historical sample for tests and dashboard.

Gate output: `docs/phase_reviews/p1_00_source_feasibility.md`.

### 6.2 Canonical time/provenance fields

Every canonical dataset must include, where meaningful:

- `event_time_utc`: time the market event or delivery period refers to;
- `delivery_start_utc` and `delivery_end_utc` where interval-based;
- `known_at_utc` or `publication_time_utc`: when the value was knowable to a decision-maker;
- `retrieved_at_utc`: when this project fetched the record;
- `source_id`: source registry identifier;
- `source_url` or source file reference;
- `source_record_id` if available;
- `schema_version`;
- `quality_flag`;
- `quality_notes`.

If exact `known_at_utc` is unavailable, use a conservative documented proxy and mark `known_at_policy` in the manifest.

### 6.3 Data-quality flags

Do not collapse all missing data to zero or unavailable. Distinguish:

- `ok`;
- `missing_market_not_procured`;
- `missing_source_gap`;
- `api_error`;
- `parse_error`;
- `unknown_product_label`;
- `outlier_review`;
- `interpolated_for_sensitivity_only`;
- `excluded_from_release_result`.

Negative prices and zero EAC prices are valid observations unless the source says otherwise.

### 6.4 Cache and manifest standard

Processed data is stored as Parquet with a JSON manifest including:

- dataset name and schema version;
- source registry IDs;
- retrieval time;
- period coverage;
- row count;
- missing and duplicate counts;
- timezone convention;
- data hash;
- transformation version;
- known-at policy;
- validation status.

---

## 7. Market modelling boundaries

### 7.1 Wholesale proxy

The wholesale module's central public-data source is `ELEXON_BMRS_MID`: Elexon/BMRS Market Index Data from `/balancing/pricing/market-index`, unless P1-00 replaces it with a better licensed/verified source. Store provider-level source labels such as `N2EXMIDP` or `APXMIDP`; a sensible default is `N2EXMIDP` with `APXMIDP` as a sensitivity if coverage is adequate.

MID must be described precisely: it is Market Index Data from appointed Market Index Data Providers reflecting GB short-term markets and used in imbalance-price calculation. It is a transparent wholesale proxy, not a claim to have traded day-ahead/intraday execution prices. Do not label it EPEX/N2EX day-ahead unless licensed data is actually used.

The model is price-taking. It does not model bid/ask spread, traded volumes, imbalance exposure or route-to-market fees in the central dispatch result.

### 7.2 EAC price-taking availability proxy

The EAC module models price-taking availability commitments against exogenous clearing prices. It is not a full EAC auction model.

Boundary ledger:

| Element | Release 1 treatment |
|---|---|
| DC/DM/DR availability prices | Modelled from verified EAC data |
| BR/QR/SR reserve products | Source-gated optional extension inside Phase 3/4 only if product definitions, directions, units and service windows are verified |
| MW commitment decision | Modelled |
| Energy headroom/footroom | Modelled |
| Capacity sharing with energy dispatch | Modelled |
| Product delivery/block structure | Modelled if verified in P1-00; do not assume one window length for all products |
| Frequency Response service windows | Expected to be longer windows such as EFA blocks if verified; encode in reference data |
| Quick Reserve service windows | Expected 30-minute windows if QR is included and verified |
| Product publication/known time | Required for rolling policy; conservative proxy if unknown |
| Gate-closure/submission timing | Required for no-leakage if modelling a decision before auction results; verify product-specific EAC rules |
| Procurement volume cap | Optional sensitivity, not central unless defensible |
| Service stacking/splitting | Conservative exclusivity by default unless public rules/data support stacking |
| Availability revenue | Modelled in £/MW/h or converted source units; no efficiency factor applied directly to availability price |
| Utilisation/activation energy | Excluded centrally unless sourced; optional sensitivity uses physical efficiency and delivered AC convention |
| Acceptance probability | Excluded from central case |
| Strategic bidding/auction clearing | Excluded |
| Performance penalties | Excluded or sensitivity only |
| BM dispatch | Excluded from EAC module |

### 7.3 Capacity Market

CM is modelled as scenario data by auction, delivery year, derating factor and asset duration. It is included as annual revenue in finance/NPV, not as a half-hourly dispatch market.

Revenue uses derated capacity, never full nameplate MW unless explicitly labelled as a no-derating diagnostic:

```text
cm_revenue_year = contracted_nameplate_mw
                  * cm_derating_factor[duration, auction, delivery_year]
                  * clearing_price_gbp_per_kw_year
                  * 1000
```

Research anchor values from a 2024/25 Modo article are 2h BESS derating of 27.15% for T-1 and 20.94% for T-4. Treat these as example scenario anchors only; Phase 1 must verify official/current auction-cycle values before central runs.

Optional stress-period feasibility can be modelled as a sensitivity using a defined stress-window SoC floor or deliverability test. Do not imply full CM penalty modelling unless implemented.

### 7.4 Balancing Mechanism

BM is not included as deterministic counterfactual revenue. Optional observed-BM analysis may reconstruct actual public actions for real units and explain why counterfactual acceptance cannot be inferred from public data alone.

### 7.5 Modo/public benchmark comparison

Benchmarking is a reconciliation exercise. The model should explain divergence from public benchmark anchors by component and data boundary, not pass/fail against a commercial index.

---

## 8. Optimisation formulation

### 8.1 Sets

- `T`: settlement periods or model timesteps;
- `S_up`: services requiring upward/export/discharge capability;
- `S_down`: services requiring downward/import/charge capability;
- `B`: service delivery blocks if verified;
- `K`: deterministic scenario sweep cases.

### 8.2 Core parameters

- `P_export_max_mw`;
- `P_import_max_mw`;
- `E_max_mwh`;
- `soc_min_mwh`, `soc_max_mwh`;
- `eta_charge`, `eta_discharge`;
- `duration_h[t]`;
- `price_gbp_per_mwh[t]`;
- `eac_price_gbp_per_mw_h[s,t]`;
- `service_duration_h[s]`;
- `service_window_id[s,t]` and block duration where verified;
- `cm_derating_factor[duration, auction, delivery_year]` for finance/CM scenarios;
- `known_at_utc` metadata for all market inputs;
- market gate timing metadata where a rolling decision depends on auction submission/results timing;
- `terminal_soc_policy` with explicit target/penalty settings;
- degradation and finance parameters as scenario inputs only.

### 8.3 Variables

- `charge_mw[t] >= 0`;
- `discharge_mw[t] >= 0`;
- `soc_mwh[t]`;
- optional `is_discharging[t]` for scheduled dispatch simultaneity prevention;
- `reserve_up_mw[s,t] >= 0`;
- `reserve_down_mw[s,t] >= 0`;
- optional block commitment variables if service block structure requires constancy.

### 8.4 Energy balance

```text
soc[t+1] = soc[t]
         + eta_charge * charge_mw[t] * duration_h[t]
         - discharge_mw[t] * duration_h[t] / eta_discharge
```

Activation energy is excluded from the central EAC availability case unless a sourced activation sensitivity is enabled.

### 8.5 Scheduled dispatch simultaneity

Binary mode may be used to prevent simultaneous scheduled charge/discharge:

```text
discharge_mw[t] <= P_export_max_mw * is_discharging[t]
charge_mw[t]    <= P_import_max_mw * (1 - is_discharging[t])
```

This binary does not govern reserve eligibility. Reserve can be held while idle.

### 8.6 Reserve headroom and footroom

Canonical Release 1 reserve formulation:

```text
discharge_mw[t] + sum_s reserve_up_mw[s,t] <= P_export_max_mw
charge_mw[t]    + sum_s reserve_down_mw[s,t] <= P_import_max_mw
```

Equivalent net-position formulations are allowed if easier to test, but must preserve idle reserve capability.

### 8.7 Reserve energy feasibility

Assuming reserve commitments are denominated as delivered AC MW:

```text
soc_mwh[t] - soc_min_mwh >= reserve_up_mw[s,t] * service_duration_h[s] / eta_discharge
soc_max_mwh - soc_mwh[t] >= reserve_down_mw[s,t] * service_duration_h[s] * eta_charge
```

If a future implementation uses a different convention, the convention must be explicit in config, result schemas and methodology.

### 8.8 Terminal SoC

Perfect-foresight backtests default to cyclic terminal SoC:

```text
soc[last] = soc[first]
```

Rolling-horizon solves must use an explicit terminal policy. Default Release 1 policy:

- target: return to the starting SoC or a configured reference SoC at the end of each optimisation window;
- enforcement: soft linear penalty or target band, not a fully free terminal state;
- diagnostic: run a free-terminal comparison only to quantify end-of-window artefacts;
- optional later improvement: continuation-value approximation based on a simple future price proxy.

Free terminal SoC is allowed only for labelled diagnostic runs and must never feed headline capture-ratio claims.

### 8.9 Objective

For a dispatch horizon, central objective maximises:

```text
sum_t price[t] * (discharge_mw[t] - charge_mw[t]) * duration_h[t]
+ sum_{s,t} eac_price[s,t] * committed_mw[s,t] * duration_h[t]
```

Central Release 1 dispatch is gross of degradation. Degradation is accounted for ex-post in Phase 5 finance/reconciliation. A labelled sensitivity may include a linear throughput shadow price in the dispatch objective, but headline policy results must state whether degradation was endogenous or ex-post.

CM is outside the dispatch objective unless a labelled stress-feasibility sensitivity is being run.

---

## 9. Policy simulation and uncertainty design

### 9.1 Perfect foresight

Purpose: upper-bound benchmark and model-debug harness. It can use realised prices over the evaluation horizon, but must never be described as implementable.

### 9.2 Energy-only rolling slice

Immediately after the deterministic energy-only baseline, build a thin rolling-horizon slice with:

- one simple forecast baseline;
- `known_at_utc <= decision_time_utc` checks;
- SoC state carried from executed actions only;
- capture ratio against energy-only perfect foresight.

This reduces later Phase 4 risk.

### 9.3 Rolling EAC policy

After EAC availability proxy is implemented, extend the rolling policy to wholesale + EAC using the same information-set discipline.

### 9.4 Forecast baselines

Start with simple, auditable baselines:

- yesterday same settlement period;
- trailing mean by settlement period/EFA block;
- last known EAC clearing result by product/block;
- public day-ahead proxy if verified.

Every forecast record stores `forecast_created_at_utc`, target interval, training window, model name and source metadata.

### 9.5 Deterministic scenario sweeps in Release 1

Release 1 uncertainty is handled through deterministic sweeps:

- wholesale price scaling or alternative proxy;
- EAC price scaling and missing-data policy;
- CM price and derating;
- rolling horizon length;
- forecast error level;
- efficiency;
- degradation cost;
- augmentation timing/cost;
- discount rate;
- revenue-decay factor.

### 9.6 Stochastic programming outside core

Stochastic programming is Phase 7 only. It may proceed only if:

- core rolling policy is implemented and no-leakage tests pass;
- EAC model solves 24h/48h windows reliably;
- scenario generation has diagnostics;
- deterministic equivalent validates on toy cases;
- adding stochastic does not delay Release 1.

---

## 10. Degradation and finance design

### 10.1 Degradation

Release 1 uses a transparent throughput degradation proxy primarily as ex-post accounting on solved dispatch trajectories:

```text
throughput_mwh[t] = charge_mw[t] * duration_h[t] + discharge_mw[t] * duration_h[t]
degradation_cost[t] = c_throughput_gbp_per_mwh * throughput_mwh[t]
```

Default headline dispatch remains gross of degradation to keep the operational policy and finance adjustment clearly separated. Add an optional `include_degradation_shadow_price=true` sensitivity only after the baseline is stable; that sensitivity subtracts the linear throughput cost in the objective and is reported separately from central results.

Post-hoc rainflow audit is used to report cycle-depth distribution if stable. Do not claim cell-physics accuracy.

### 10.2 Finance boundary ledger

Included in illustrative NPV scenarios:

- modelled dispatch revenue;
- EAC availability proxy revenue;
- CM annuity scenario;
- degradation proxy cost;
- augmentation capex scenario;
- fixed O&M only if explicitly sourced;
- discount-rate sensitivity;
- revenue-decay scenario.

Excluded unless explicitly added later:

- grid use-of-system charges;
- connection charges;
- route-to-market fees;
- tolling/PPA structures;
- debt sizing and interest;
- tax;
- insurance;
- land lease;
- warranty terms;
- availability guarantees;
- imbalance exposure;
- curtailment/outage modelling;
- merchant risk premium;
- construction delay and development costs.

The NPV output is scenario appraisal, not investment advice or bankability due diligence.

---

## 11. Benchmark reconciliation design

The final comparison against public Modo-style anchors must be a reconciliation scorecard.

Minimum reconciliation categories:

| Component | Project treatment | Benchmark treatment if known | Expected divergence driver |
|---|---|---|---|
| Wholesale | MID/public proxy or licensed source if available | N2EX/EPEX/other benchmark method | Price-source and execution difference |
| EAC/response | Price-taking availability proxy | Commercial benchmark method | Auction/asset/performance differences |
| BM | Excluded from central model | Often material in benchmark revenue | Public data cannot infer counterfactual acceptances |
| CM | Scenario annuity | Asset-specific agreements | Derating/contract/site differences |
| Degradation | Scenario/proxy | Usually not directly comparable | Parameter and warranty differences |
| Availability/outages | Mostly excluded | Asset-level treatment may apply | Public visibility limitation |
| Asset sample | Reference 2h BESS | Index inclusion rules | Fleet composition difference |

The methodology should say: “This reconciles public-data model outputs against public benchmark narratives; it does not validate replication of a proprietary model.”

---

## 12. Dashboard and communication product

The dashboard is a cached explainer, not a live optimiser.

Required pages:

1. Executive overview: headline revenue stack and capture ratio.
2. Data audit: sources, coverage, quality flags, known-at policy.
3. Energy-only and EAC rolling policy comparison.
4. EAC availability proxy: product prices, commitments, feasibility caveats.
5. Degradation and finance scenarios.
6. Benchmark reconciliation and limitations.
7. Optional appendices only if implemented.

Dashboard acceptance:

- no solver required;
- no live API calls;
- all charts have units and source labels;
- caveats visible without reading the paper;
- missing cached outputs fail gracefully;
- every cached artefact has a `run_id`, source snapshot hash, config hash, created-at timestamp and schema version;
- refresh cadence is documented: manual rebuild for portfolio release, optional scheduled rebuild only after data clients and licences are stable;
- reviewer understands the product in under 60 seconds.

---

## 13. Canonical roadmap

### Phase 1 — Foundation, source feasibility and data platform

Includes P1-00 source/licence feasibility gate, source registry, source research notes, implementation conventions, assumptions ledger, canonical schemas, data clients, cache and quality reports.

### Phase 2 — Deterministic dispatch baseline

Build energy-only perfect-foresight optimiser, solver abstraction, post-processing and synthetic validation.

### Phase 2.5 — Energy-only rolling vertical slice

Build minimal rolling engine, forecast baseline and no-leakage tests before adding EAC complexity.

### Phase 3 — EAC availability proxy and Capacity Market scenarios

Add price-taking EAC availability proxy, correct reserve headroom/footroom, service energy feasibility, verified block constraints if applicable, CM annuity scenarios.

### Phase 4 — Rolling EAC policy and deterministic scenario sweeps

Extend rolling policy to wholesale + EAC, compare capture ratios, run deterministic sensitivity sweeps and forecast-error analysis.

### Phase 5 — Degradation, finance, benchmark reconciliation and observed BM appendix

Add degradation proxy, rainflow audit if stable, NPV scenarios, finance boundary ledger, Modo reconciliation scorecard and optional observed-BM appendix.

### Phase 6 — Dashboard, methodology and release

Package the product: cached dashboard, README, methodology paper, reproducibility guide, limitations, release checklist and interview script.

### Phase 7 — Optional stochastic extension

Only after Release 1 core quality gates pass. Not required for Release 1.

---

## 14. MVP and kill list

### Must ship for Release 1

- source feasibility and assumptions ledger;
- validated wholesale proxy data pipeline;
- deterministic energy-only optimiser;
- energy-only rolling slice with no-leakage tests;
- EAC price-taking availability proxy with corrected reserve physics;
- rolling wholesale + EAC policy comparison;
- deterministic scenario sweeps;
- cached dashboard;
- methodology paper and benchmark reconciliation.

### Should ship

- CM annuity scenarios;
- degradation throughput sensitivity;
- NPV scenario module;
- post-hoc rainflow audit if stable.

### Could ship

- observed BM appendix;
- global sensitivity;
- PyPSA-GB appendix;
- RNP/15-minute settlement sensitivity.

### Will not ship in core Release 1

- stochastic programming;
- deterministic BM counterfactual;
- full EAC auction clearing;
- endogenous price engine;
- RL;
- electrochemical degradation model;
- live optimiser dashboard.

---

## 15. Risk register

### Risk: source data is unusable or licence-constrained

Mitigation: P1-00 feasibility gate before production client build; scope adjustment if data cannot support intended claim.

### Risk: MID is mislabelled as day-ahead price

Mitigation: encode `price_source_type` and `is_proxy`; use chart labels saying wholesale proxy unless licensed data is used.

### Risk: hidden future leakage

Mitigation: `known_at_utc` schema fields from Phase 1; central information-set builder; tests with deliberately impossible future values.

### Risk: reserve physics are wrong

Mitigation: headroom/footroom canonical formulation; upward reserve discharge-efficiency test; idle reserve test.

### Risk: EAC overclaiming

Mitigation: price-taking availability wording; service boundary ledger; no auction-clearing claim.

### Risk: stochastic scope creep

Mitigation: Phase 7 only; deterministic scenario sweeps in Release 1.

### Risk: finance output looks bankable

Mitigation: finance boundary ledger; scenario wording; no investment-advice framing.

### Risk: dashboard hides caveats

Mitigation: caveat panels and data-audit page; dashboard loads only cached outputs.

---

## 16. Final product definition

Release 1 is complete when a reviewer can:

- clone the repository;
- install dependencies;
- run unit tests and a tiny smoke optimisation;
- inspect the source registry and assumptions ledger;
- verify data provenance and known-at policy;
- understand the corrected dispatch/reserve formulation;
- compare perfect-foresight and rolling results;
- open the cached dashboard;
- read the methodology paper;
- see benchmark reconciliation and caveats;
- understand exactly what is excluded from BM, EAC, stochastic and finance.

Central claim:

> This is a transparent, reproducible GB public-data BESS revenue-stack optimiser that demonstrates correct physical dispatch modelling, price-taking EAC availability treatment, no-leakage rolling evaluation, scenario-based finance, and honest benchmark reconciliation.

Central non-claim:

> This does not replicate commercial battery dispatch models, infer counterfactual BM acceptances, clear EAC auctions, forecast endogenous GB prices, or prove bankable returns.
