# Demo Walkthrough

This walkthrough keeps the public demo aligned with the project boundaries.

## 30-Second Pitch

This is a transparent public-data GB BESS revenue-stack optimiser. It models wholesale proxy and NESO EAC availability revenues for a reference battery, compares perfect-foresight upper bounds with no-leakage rolling operation, adds Capacity Market and finance scenarios, and reconciles results against public benchmark anchors while making the public-data limitations explicit.

## 90-Second Demo Flow

1. Open the README headline chart.
2. State that the model is public-data and source-labelled.
3. Show the dashboard executive overview.
4. Point out perfect foresight versus rolling capture ratio.
5. Show the data audit page and known-at policy.
6. Show the EAC availability proxy page and reserve feasibility caveat.
7. Show finance scenario page and exclusions.
8. Show benchmark reconciliation page and explain why disagreement is expected.

## Expected Questions

### Why use MID instead of day-ahead prices?

MID is a public short-term market index proxy available through Elexon/BMRS. The project labels it as a proxy and does not claim executable day-ahead or intraday trading revenue.

### Why include perfect foresight?

It is an upper-bound diagnostic and model-debugging benchmark. The implementable comparison is the rolling policy with known-time filters.

### How do you prevent future leakage?

Canonical datasets carry `known_at_utc` or a documented known-at policy. Rolling information sets reject rows where `known_at_utc > decision_time_utc`, and tests include deliberate future-marker fixtures.

### How does EAC reserve modelling work?

EAC is a price-taking availability proxy. The model reserves power headroom or footroom and checks stored-energy feasibility. Idle batteries can hold reserve if power and SoC constraints allow it.

### Why exclude BM?

Public data can show observed BM actions for real units, but it cannot reliably infer whether a hypothetical battery would have been accepted. Central Release 1 avoids fictional counterfactual BM revenue.

### Why not stochastic programming?

The core research question can be answered with deterministic rolling policies and scenario sweeps. Stochastic programming is an optional extension only after no-leakage rolling and EAC models are stable.

### What does the finance module prove?

It proves nothing bankable. It converts modelled revenues into illustrative scenario appraisal with explicit exclusions and sensitivities.

### Why might results differ from Modo or other public benchmarks?

Differences can come from price source, BM exclusion, EAC treatment, asset sample, degradation, availability, CM assumptions and proprietary methodology. The project reconciles these differences instead of claiming replication.

## Demo Discipline

Do not say:

- "This replicates Modo."
- "This is bankable."
- "This optimises BM revenue."
- "This clears the EAC auction."
- "This is a trading engine."

Do say:

- "public-data proxy";
- "price-taking availability";
- "upper-bound diagnostic";
- "no-leakage rolling policy";
- "scenario appraisal";
- "benchmark reconciliation."
