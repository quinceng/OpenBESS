# Known Limitations

These limitations are part of the product, not footnotes to hide. They should
appear in the README, methodology and dashboard where relevant.

The current headline cache has trailing-12-month coverage for one historical
year. That removes the older 90-day preview limitation for the mainline
reference cache, but it does not create multi-year evidence or a forward market
forecast.

## 1. Public-Data Price Proxy

The central wholesale source is a public proxy. It does not prove executable day-ahead or intraday trading revenue.

Implication:

- wholesale outputs should be interpreted as transparent proxy results;
- benchmark divergence may come from price-source and execution differences.

## 2. Perfect Foresight

Perfect foresight uses realised future data and is not deployable.

Implication:

- it is an upper bound and debugging harness;
- it should not be presented as achievable strategy revenue.

## 3. Rolling Forecast Simplicity

Rolling policies use simple auditable forecasts.

Implication:

- forecast quality is intentionally modest;
- the project demonstrates information-set discipline, not commercial forecasting performance.

## 4. EAC Price-Taking Approximation

EAC is modelled as price-taking availability against exogenous clearing prices.

Implication:

- no strategic bidding;
- no auction clearing;
- no acceptance probability;
- no guarantee that a real asset would receive the modelled commitments.

## 5. EAC Source and Timing Dependence

EAC product definitions, publication times and delivery windows must be verified from public sources.

Implication:

- if known-time metadata is weak, rolling policy results need stronger caveats;
- central product set should stay narrow.

## 6. Balancing Mechanism Exclusion

Central Release 1 excludes deterministic BM counterfactual revenue.

Implication:

- outputs may be lower than benchmarks that include BM;
- optional observed-BM appendix is ex-post only.

## 7. Capacity Market Simplification

CM is annual scenario revenue using derating assumptions.

Implication:

- no settlement-period CM dispatch product;
- no penalty model;
- no site-specific agreement modelling.

## 8. Degradation Approximation

Central degradation uses a throughput proxy.

Implication:

- not cell-chemistry accurate;
- not warranty specific;
- useful for sensitivity, not physical degradation truth.

## 9. Finance Scope

Finance outputs are illustrative scenario appraisal.

Implication:

- no debt, tax, insurance, grid charges or contract structure unless explicitly added;
- not investment advice;
- not bankability due diligence.

## 10. Benchmark Comparability

Public benchmarks may use proprietary data, asset samples and component definitions.

Implication:

- comparison is explanatory reconciliation;
- disagreement is expected and should be decomposed, not tuned away.

## 11. Runtime and Solver Scale

Rolling market-stack optimisation may become expensive as products, horizons and scenarios grow.

Implication:

- keep Release 1 product set narrow;
- cache dashboard artefacts;
- avoid live heavy solves.

## 12. Historical Scope

The public release may use selected historical periods.

Implication:

- annualisation methods must be labelled;
- partial samples should not be overgeneralised.

## 13. Residential Calculator Limitations

The residential calculator is a household decision aid, not a supplier billing
engine or contract recommendation.

Implication:

- first-release bill-aware dispatch does not apply an explicit degradation cost
  to cycling;
- VAT, supplier-specific adjustments, network charge structures and detailed
  settlement reconstruction are excluded;
- aggregator/VPP participation is scenario-based and does not guarantee a real
  contract, dispatch call or event payment;
- household load and PV inputs are only as reliable as the source data supplied
  with the scenario.

## 14. Public Residential Reference Data

Public residential assumptions are reproducible proxies, not private household
telemetry.

Implication:

- London and Great Britain load defaults are annual averages, not actual
  half-hourly household behaviour;
- the flat generated reference load profile is a fallback only and should be
  replaced by London Datastore, UKPN/SSEN aggregate shapes, Elexon profile
  coefficients or customer smart-meter data for serious scenario work;
- Ofgem and Octopus public tariffs can change, so tariff assumptions need source
  dates and reruns;
- PVGIS output depends on roof, location and system assumptions that must be
  recorded with each run.
