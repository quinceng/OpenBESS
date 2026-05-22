# Phase 2 Review

## Summary

Phase 2 builds the deterministic energy-only dispatch baseline. The next phase may proceed once repeated 24h/48h rolling-window runtime is measured in Phase 2.5.

## Built

- Dispatch input builder from Phase 1 wholesale price records.
- Pyomo energy-only model factory.
- Explicit variables, energy-balance constraints, power limits, binary charge/discharge exclusivity and cyclic/free terminal SoC options.
- HiGHS solver wrapper with diagnostics and loud failure on non-optimal termination.
- Stable dispatch result schema with period rows and headline metrics.
- Unit conversion helper for GBP/MWh x MW x hours revenue.
- Tiny network-free smoke CLI: `gb-bess run-smoke`.
- Synthetic validation suite for core economic behaviours.
- Live historical Elexon MID one-day sample summary under `reports/phase_2_baseline/`.
- Phase 2 baseline method note.
- Regression fixture under `tests/fixtures/phase2_toy_prices.csv`.

## Intentionally Not Built

- Rolling horizon policy.
- EAC reserve constraints.
- Capacity Market integration.
- Degradation or finance.
- Benchmark reconciliation.
- Live dashboard or charts beyond method/report artefacts.

## Source Assumptions Changed

- No source assumptions changed from Phase 1.
- Phase 2 uses Phase 1 `WholesalePricePoint` records and preserves the MID public-proxy caveat.

## Tests

- Passing: synthetic optimisation tests, dispatch input validation, result metrics, CLI smoke command exposure and Phase 1 regression tests.
- Failing: none known at review authoring.
- Not run by default: live source integration tests.

## Data Quality

- Missing prices fail before model construction because canonical prices are required floats.
- Duplicate delivery-start timestamps fail in the dispatch input builder.
- Negative prices remain valid and are covered by synthetic tests.

## Modelling Caveats

- Perfect foresight is an upper-bound diagnostic.
- Free terminal SoC is diagnostic only and can inflate value.
- The baseline is wholesale-only and excludes EAC, CM, degradation and BM.

## Runtime

- Tiny synthetic solves run inside the unit-test suite.
- Live Elexon APXMIDP `2024-01-01` to `2024-01-02` sample solved 49 rows in about 0.04 seconds with HiGHS.
- A single one-month Elexon request returned HTTP 400. Full-month baseline refresh should be chunked through the data workflow before public reporting.

## Gate Decision

Proceed with caveat.

## Scope Moved

- Moved to Phase 2.5: repeated rolling-window runtime benchmark and policy wrapper.
- Moved to Phase 3: EAC and CM.
- Moved to Phase 5: finance, degradation and benchmark reconciliation.
