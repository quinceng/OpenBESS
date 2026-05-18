# Product Plan

This document is the compact repo-facing product plan. The full governing plan is `../GB_BESS_Optimisation_Product_Plan.md`.

## 1. Product

Build a transparent public-data GB battery energy storage revenue-stack optimiser for a reference BESS asset.

The product answers:

```text
Under transparent public-data assumptions, how much value can a reference
2-hour GB BESS capture from wholesale proxy and EAC availability revenues,
how much of a perfect-foresight ceiling is achievable by a no-leakage rolling
policy, and which public-data limitations explain divergence from commercial
benchmark narratives?
```

## 2. Audience

Primary reviewers:

- energy-market modeller;
- graduate analyst;
- technical portfolio reviewer;
- GB power-market consultant;
- public-sector energy analyst.

The project should be understandable in under 10 minutes and inspectable in depth.

## 3. Release 1 Includes

- source/licence/data feasibility gate;
- source registry and assumptions ledger;
- Elexon BMRS MID wholesale proxy pipeline;
- NESO EAC price-taking availability proxy where verified;
- deterministic perfect-foresight dispatch;
- energy-only rolling-horizon vertical slice;
- EAC-aware rolling policy;
- deterministic scenario sweeps;
- Capacity Market annual scenarios;
- degradation proxy and finance scenario appraisal;
- public benchmark reconciliation;
- cached dashboard;
- methodology and reproducibility docs.

## 4. Release 1 Excludes

- deterministic BM counterfactual revenue;
- full EAC auction clearing;
- strategic bidding;
- acceptance probability;
- endogenous price simulation;
- RL trading agent;
- electrochemical cell model;
- bankability conclusion;
- proprietary benchmark replication;
- live optimiser dashboard;
- stochastic programming as core requirement.

## 5. Product Standards

The release must be:

- reproducible from a clean clone;
- explicit about public-data limits;
- traceable from chart to source and config;
- tested on physical and economic invariants;
- honest about benchmark divergence;
- narrow enough to finish.

## 6. Strategic Edge

The project is not a live commercial flexibility platform. Its durable edge is:

- transparency;
- explainability;
- open/public-data methodology;
- transparent GB BESS revenue-stack modelling for investors, analysts and public-data due diligence;
- clean audit trail from result to source, assumption and config;
- fast experimentation;
- investor and analyst tooling rather than live retail flexibility control.

## 7. MVP Release Path

The minimum credible Release 1 is:

1. verified source feasibility;
2. validated wholesale proxy data;
3. energy-only deterministic optimiser;
4. energy-only rolling policy;
5. one verified EAC product in market-stack optimisation;
6. rolling comparison with no-leakage evidence;
7. finance/reconciliation on saved trajectories;
8. cached dashboard and methodology.

Additional EAC products, observed BM, global sensitivity and stochastic programming are optional only after the core path is stable.

## 8. Public Wording

Use:

- public-data research model;
- wholesale proxy;
- price-taking EAC availability proxy;
- perfect-foresight upper bound;
- no-leakage rolling policy;
- benchmark reconciliation;
- finance scenario appraisal.

Avoid:

- commercial trading engine;
- Modo replication;
- bankable return;
- auction-clearing model;
- BM optimiser;
- investment recommendation.
