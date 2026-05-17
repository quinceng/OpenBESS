# Phase 1 Review

## Summary

Phase 1 foundation is built to a usable standard. The next phase may proceed with caveat: Capacity Market duration-specific storage derating remains scenario/reference data until an official selected-year source is added.

## Built

- Python package skeleton under `src/gb_bess_revenue_stack/`.
- `pyproject.toml`, lockfile, dependency groups, `ruff`, `mypy`, `pytest` and CI workflow.
- Typed config models for run, asset, data, solver and market settings.
- Canonical schema models for settlement periods, wholesale price points, EAC auction results and Capacity Market scenarios.
- GB settlement-period generator with spring/autumn DST tests.
- Bounded Elexon MID and NESO EAC clients with mocked unit tests and opt-in live smoke tests.
- Raw immutable content-addressed cache.
- Processed dataset manifest model and Parquet writer.
- Wholesale quality checks for duplicates, missing periods and negative-price preservation.
- Source registry, assumptions ledger, implementation conventions and data-source docs carried into the implementation repo.
- P1-00 source feasibility review.
- Tiny reference data for Capacity Market scenario anchors.

## Intentionally Not Built

- Phase 2 optimiser and smoke optimisation.
- Full annual historical data refresh.
- Live dashboard.
- Counterfactual BM revenue.
- Full EAC auction clearing or strategic bidding.
- Official central Capacity Market storage derating pipeline.

## Source Assumptions Changed

- `A-WHOLESALE-001`: Elexon MID source is verified for public proxy use with `delivery_end_utc` conservative known-at policy.
- `A-EAC-002` and `A-EAC-004`: NESO EAC summary resource is verified for product labels, `GBP/MW/h` clearing prices and MW cleared volume.
- `A-CM-002`: official auction parameters and T-4 clearing-price source are verified, but duration-specific 2h storage derating remains caveated unless an official selected-year derating source is added.

## Tests

- Passing: network-free unit suite for config, schemas, source parsers, cache, manifests, quality checks, docs/reference artefacts and DST handling.
- Failing: none known at review authoring.
- Not run by default: live integration tests, because they call external services and are opt-in through `GB_BESS_RUN_INTEGRATION=1`.

## Data Quality

- Coverage: committed fixtures/reference data only; production raw and processed data paths are gitignored.
- Missing data: validation flags missing settlement periods instead of filling them.
- Known source issues: EAC records lack publication timestamps; known-at policy is conservative.

## Modelling Caveats

- MID is a public wholesale proxy, not a day-ahead execution price.
- EAC is source data for a later price-taking availability proxy, not auction clearing.
- CM is annual scenario revenue and should not alter dispatch in central runs.

## Runtime

- Phase 1 runtime is limited to source parsing and validation. Optimisation runtime gates begin in later phases.

## Gate Decision

Proceed with caveat.

## Scope Moved

- Moved to Phase 2: deterministic energy-only optimiser.
- Moved to Phase 3: CM annuity scenario integration and EAC optimisation constraints.
- Moved to Phase 5: public benchmark reconciliation anchors.
- Moved to future work: official automated storage derating workbook ingestion if needed.
