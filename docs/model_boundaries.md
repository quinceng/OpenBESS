# Model Boundaries

This document states what the project models, what it excludes and how results must be described. It protects the project from accidental overclaiming.

## 1. Central Claim

This project is a transparent, reproducible GB public-data BESS revenue-stack optimiser. It demonstrates:

- physical battery dispatch modelling;
- price-taking EAC availability treatment;
- no-leakage rolling policy evaluation;
- deterministic scenario appraisal;
- public benchmark reconciliation.

## 2. Central Non-Claim

This project does not:

- replicate commercial battery dispatch products;
- infer counterfactual BM acceptances;
- clear EAC auctions;
- forecast endogenous GB power prices;
- prove bankable returns;
- provide investment advice.

Named OpenBESS outputs, including the OpenBESS Stack Index, must carry
`not_a_market_index`. They are not official market indices, proprietary-model
replications or bankable revenue assessments.

## 3. Asset Boundary

Central asset:

- one reference GB battery energy storage asset;
- default 2-hour duration;
- configurable MW, MWh, efficiency and SoC limits;
- no site-specific grid, outage, warranty or contract modelling in central Release 1.

The reference asset is a modelling object, not a claim about any named unit.

## 4. Wholesale Boundary

Central treatment:

- Elexon BMRS Market Index Data as a public short-term wholesale proxy;
- price-taking dispatch;
- explicit proxy labelling;
- provider label preserved.

Excluded centrally:

- licensed day-ahead or intraday auction execution unless separately obtained and licensed;
- bid/ask spread;
- imbalance exposure;
- route-to-market fees;
- traded volume constraints;
- endogenous price impact.

Allowed sensitivity:

- alternative public or licensed price source if Phase 1 verifies access, licence and schema.

## 5. EAC Boundary

Central treatment:

- price-taking availability proxy using verified NESO EAC result data;
- service registry preserving source labels and product mappings;
- reserve headroom/footroom;
- reserve energy feasibility;
- verified block/commitment rules where public sources support them;
- missing-data classification.

Excluded centrally:

- auction clearing;
- strategic bidding;
- acceptance probability;
- unit portfolio competition;
- performance penalties;
- activation energy settlement unless separately sourced;
- BM revenue.

BR, QR and SR products are source-gated. They may be included only if product definitions, directions, service windows and units are verified.

## 6. Capacity Market Boundary

Central treatment:

- annual scenario revenue;
- duration-specific derating;
- auction and delivery-year labels;
- separate finance/revenue-stack reporting.

Excluded centrally:

- settlement-period dispatch revenue;
- penalty modelling;
- stress event settlement details;
- site-specific contract terms.

No-derating CM revenue is a diagnostic only and must never be a central case.

## 7. Balancing Mechanism Boundary

Central Release 1 excludes deterministic BM counterfactual revenue.

Optional observed-BM appendix may:

- reconstruct public observed actions for real units;
- explain BOA/BOD/PN/FPN mechanics;
- show why counterfactual acceptance is not inferable from public data alone.

Optional observed-BM appendix must not feed the central optimiser revenue stack.

## 8. Forecast and Policy Boundary

Perfect foresight:

- upper-bound diagnostic;
- not deployable;
- may use realised future data for model debugging and ceiling estimates.

Rolling policy:

- main realisable policy comparison;
- no input with `known_at_utc > decision_time_utc`;
- simple, auditable forecast baselines;
- state updated from executed actions only.

Forecast models are not commercial forecasting products. Their role is to test operational policy mechanics under transparent assumptions.

## 9. Degradation Boundary

Central treatment:

- ex-post throughput degradation proxy;
- optional linear shadow-price sensitivity;
- post-hoc rainflow audit if stable.

Excluded centrally:

- electrochemical cell model;
- warranty-specific degradation model;
- exact rainflow counting inside the MILP;
- universal LFP or NMC degradation claims.

## 10. Finance Boundary

Central treatment:

- illustrative scenario appraisal;
- 15-year cash-flow examples if implemented;
- discount-rate, revenue-decay, degradation and augmentation sensitivities.

Excluded centrally:

- debt sizing;
- tax;
- insurance;
- land lease;
- grid charges;
- route-to-market fees;
- warranties;
- construction delay;
- merchant risk premium;
- bankability conclusion.

Required wording:

```text
The finance module is illustrative scenario appraisal. It is not investment advice, bankability analysis or a substitute for commercial due diligence.
```

## 11. Benchmark Boundary

Benchmark comparison is reconciliation, not validation or replication.

Allowed:

- public benchmark anchors with source URL/date/methodology note;
- component-by-component divergence explanation;
- confidence labels.

Not allowed:

- pass/fail tests against commercial benchmark values;
- claims to replicate Modo, Aurora, LCP, AFRY or any proprietary index;
- use of benchmark values as forecast input unless known before the decision time and explicitly justified.

## 12. Dashboard Boundary

Dashboard is a cached explainer.

The headline OpenBESS dashboard cache is
`results/dashboard/release_trailing_12m_historical` when its manifest records
the canonical reference asset, `primary_window_label=trailing_12m`,
`target_window_eligible=true`, and no `below_trailing_12m_coverage` caveat.
`results/dashboard/release_90d_historical` is retained as historical preview
evidence only.

Allowed:

- select precomputed scenario;
- filter dates in cached output;
- toggle revenue components;
- display caveats and source metadata.

Not allowed:

- annual MILP solve;
- rolling backtest solve;
- stochastic solve;
- live API backfill;
- hidden data mutation.

## 13. Residential and Commercial Branch Boundary

Residential BESS modelling is a separate branch namespace. It uses household
kW/kWh units, residential product presets, DNO export-limit assumptions and
aggregator/VPP eligibility. Residential defaults must not be mixed into the
central MW/MWh market-stack optimiser.

Commercial BESS modelling is a separate branch namespace. It uses MW/MWh units
and site export-limit assumptions. It should grow separately from residential
modelling and from the central optimiser internals until a deliberate integration
decision is made.
Generated branch artefacts such as
`results/dashboard/commercial_trailing_12m` must not be described as the
canonical OpenBESS reference asset cache.

Residential branch outputs must describe normal household direct market bidding
as ineligible unless effective export capability reaches the relevant direct
access threshold. Aggregator/VPP participation is the default market-access route
for household systems.

Residential bill-aware dispatch is a household calculator. It may model
interval load, PV generation, retail import/export tariffs, DNO export limits and
aggregator/VPP event payments, but it must not be presented as a supplier bill
replica or a direct-market bidding model. It excludes supplier-specific bill
reconstruction, VAT treatment, network-charge detail and bankability conclusions
unless those assumptions are added explicitly.
