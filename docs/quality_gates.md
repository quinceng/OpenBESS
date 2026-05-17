# Quality Gates

This document defines the gates that determine whether a phase can proceed and whether Release 1 is public-ready.

## 1. Gate Philosophy

The project should fail early on source, unit, timestamp and modelling-boundary issues. A result is not release-quality unless a reviewer can trace it from chart to run manifest, config, source snapshot and model convention.

## 2. Repository Gate

Required before optimisation code:

- `src/gb_bess_revenue_stack/` package exists;
- `pyproject.toml` and lockfile exist;
- test runner works from a clean install;
- lint and format tooling configured;
- type checking configured;
- no local absolute paths in committed config;
- no secrets in repo;
- notebooks are exploratory only.

## 3. Source Feasibility Gate

Required output:

```text
docs/phase_reviews/p1_00_source_feasibility.md
```

The review must decide for each source:

- verified;
- usable with caveat;
- fallback required;
- excluded from Release 1.

Minimum checks:

- endpoint or file access method;
- field names;
- units;
- timezone convention;
- known/publication time availability;
- licence and reuse;
- data volume;
- rate limits or download limits;
- smallest viable fixture sample.

No production data client should be built for a source before the gate records an access method and schema expectation.

## 4. Data Quality Gate

Every processed dataset must have:

- schema version;
- source ID;
- source URL or source file reference;
- retrieval timestamp;
- period coverage;
- row count;
- duplicate count;
- missing period count;
- timezone convention;
- data hash;
- transformation version;
- known-at policy;
- validation status.

Validation must distinguish:

- valid zero price;
- negative price;
- product not procured;
- source gap;
- API error;
- parse error;
- unknown product label;
- interpolation used for sensitivity only.

Central release outputs must not silently fill missing market data with zero.

## 5. Optimisation Correctness Gate

Energy-only model must pass:

- zero flat price produces no movement;
- flat positive price with cyclic terminal SoC produces no profitable movement;
- low-high price pattern charges then discharges;
- negative-positive price pattern handles negative prices correctly;
- insufficient spread below losses avoids cycling;
- cyclic terminal SoC prevents final artificial dump;
- SoC bounds hold within tolerance;
- no simultaneous scheduled charge/discharge in binary mode;
- objective equals extracted revenue within tolerance;
- `duration_h` is included exactly once in each revenue term.

Market-stack model must pass:

- all services off reproduces Phase 2 objective;
- idle battery can hold upward reserve;
- idle battery can hold downward reserve;
- reserve cannot exceed power headroom/footroom;
- upward reserve includes `/ eta_discharge` stored-energy requirement;
- downward reserve includes `* eta_charge` footroom requirement;
- service revenue includes `duration_h`;
- block constraints apply only where verified;
- CM does not alter central dispatch.

## 6. No-Leakage Gate

Rolling-policy tests must include deliberate future-marker fixtures. The model must prove:

- future wholesale rows are excluded;
- future EAC rows are excluded;
- forecasts train only on rows known at decision time;
- scenario-generation training data respects known-time rules;
- oracle diagnostics cannot be selected as central policy;
- rolling state updates from executed actions only.

Every rolling run must report the number of excluded future rows and the known-at policy used.

## 7. Runtime Gate

Before entering Phase 4, record runtime benchmarks for:

- energy-only 24h solve;
- energy-only 48h solve;
- energy plus one EAC product 24h solve;
- energy plus one EAC product 48h solve;
- one-month perfect-foresight market-stack run.

If runtime is too slow for rolling evaluation, reduce product set, horizon length or scenario count before adding more market complexity.

## 8. Finance Gate

Finance outputs must prove:

- CM is counted once per year;
- derating is duration-, auction- and delivery-year-specific;
- NPV matches hand-calculated fixtures;
- augmentation capex appears in the correct year;
- finance boundary metadata is included;
- scenario labels propagate to dashboard outputs.

The finance page and methodology must say scenario appraisal, not bankability.

## 9. Benchmark Reconciliation Gate

Benchmark artefacts must:

- store source URL;
- store source date;
- store methodology note or unknown-method flag;
- distinguish project treatment from benchmark treatment;
- describe expected divergence driver;
- avoid pass/fail wording.

Benchmark values must not be unit-test targets.

## 10. Dashboard Gate

Dashboard must:

- load without raw data;
- load without solver installed;
- avoid live API calls;
- read from `results/dashboard/` and reference files only;
- show units on every chart;
- show source labels and caveats;
- fail gracefully if cache files are missing;
- expose run/config/source metadata.

## 11. CI Gate

Core CI should run:

- install;
- import smoke test;
- ruff check;
- ruff format check;
- type check;
- unit tests;
- tiny regression tests;
- dashboard import smoke test.

Network and long-running integration tests should be marked and excluded from default CI unless scheduled separately.

## 12. Phase Review Gate

Each phase is incomplete until its phase review exists under `docs/phase_reviews/`.

The review must state:

- what was built;
- what was intentionally not built;
- source assumptions changed;
- tests passing and failing;
- data-quality issues;
- open modelling caveats;
- whether the next phase may proceed;
- scope moved to kill list or Phase 7.

## 13. Release Gate

Release 1 is public-ready only when:

- clean clone can install;
- unit tests pass;
- tiny smoke optimisation runs;
- cached dashboard opens;
- methodology agrees with code equations;
- README caveats match model boundaries;
- source registry and assumptions ledger are populated;
- dashboard charts include units and caveats;
- benchmark page says reconciliation;
- finance page says scenario appraisal;
- stochastic is absent from core claims unless Phase 7 was completed.
