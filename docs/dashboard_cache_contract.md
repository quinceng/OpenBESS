# Dashboard Cache Contract

The dashboard is a cached explainer. It must not run annual optimisation, rolling backtests, stochastic solves or live API backfills during normal use.

## 1. Cache Location

Dashboard artefacts live under:

```text
results/dashboard/
```

The dashboard may also read small committed reference files under:

```text
data/reference/
```

## 2. Required Metadata

Every dashboard artefact must include or reference metadata with:

- `run_id`;
- `created_at_utc`;
- `schema_version`;
- `code_version` or git commit if available;
- `config_hash`;
- `source_snapshot_hash`;
- `input_run_ids`;
- `source_ids`;
- `licence_caveat_flags`;
- `known_at_policy`;
- `degradation_treatment`;
- `central_or_sensitivity`;
- `refresh_cadence`.

## 3. Suggested Files

Suggested cache files:

```text
results/dashboard/manifest.json
results/dashboard/executive_summary.json
results/dashboard/revenue_stack.parquet
results/dashboard/revenue_stack.csv
results/dashboard/policy_capture.parquet
results/dashboard/policy_capture.csv
results/dashboard/eac_commitments.parquet
results/dashboard/scenario_sweeps.parquet
results/dashboard/scenario_sweeps.csv
results/dashboard/finance_cashflows.parquet
results/dashboard/stack_series.parquet
results/dashboard/stack_series.csv
results/dashboard/forecast_error_sweeps.parquet
results/dashboard/forecast_error_sweeps.csv
results/dashboard/benchmark_reconciliation.json
results/dashboard/data_quality.json
results/dashboard/data_quality_summary.csv
results/dashboard/stack_series_windows.csv
results/dashboard/assumptions_ledger.json
results/dashboard/source_snapshot.json
results/dashboard/caveats.json
```

Phase 4/5 currently writes the implemented subset needed for the cached
explainer:

```text
results/dashboard/manifest.json
results/dashboard/executive_summary.json
results/dashboard/revenue_stack.parquet
results/dashboard/revenue_stack.csv
results/dashboard/policy_capture.parquet
results/dashboard/policy_capture.csv
results/dashboard/scenario_sweeps.parquet
results/dashboard/scenario_sweeps.csv
results/dashboard/degradation_summary.json
results/dashboard/finance_summary.json
results/dashboard/finance_cashflows.parquet
results/dashboard/stack_series.parquet
results/dashboard/stack_series.csv
results/dashboard/forecast_error_sweeps.parquet
results/dashboard/forecast_error_sweeps.csv
results/dashboard/benchmark_reconciliation.json
results/dashboard/eac_commitments.parquet
results/dashboard/data_quality.json
results/dashboard/data_quality_summary.csv
results/dashboard/stack_series_windows.csv
results/dashboard/assumptions_ledger.json
results/dashboard/source_snapshot.json
results/dashboard/caveats.json
```

`eac_commitments.parquet` records the executed EAC reserve commitments by
decision step, service label and direction. `data_quality.json` records source
IDs, known-at policy, solver failure count, excluded future rows and service
cell coverage.

`stack_series.parquet` and `stack_series.csv` record the OpenBESS Stack Index
Preview series from the same dataframe. The CSV export serialises
`caveat_flags` as JSON text. Both exports contain row-level stack values and
must preserve `not_a_market_index`.

`forecast_error_sweeps.parquet` and `forecast_error_sweeps.csv` record
deterministic rolling-policy sensitivities for biased or scaled wholesale
forecasts. These rows are diagnostics for forecast imperfection and are not
headline market values.

`assumptions_ledger.json` records the asset, finance, Capacity Market,
known-at and caveat assumptions used by the cache. `source_snapshot.json`
records the source IDs, labels, snapshot hash and input run IDs. Release runs
may pass a richer aligned-source manifest through to `source_snapshot.json`.

The row `asset_id` identifies the asset actually solved in the cache.
`openbess_canonical_1mw_2mwh` is only valid for canonical reference runs, not
every smoke run.

Window eligibility metadata lives in `data_quality.json` under
`stack_series_windows`, including coverage percentages, annualisation
eligibility, public-index eligibility and `expected_period_basis` for each
tracked window. The `ytd` window uses calendar year-to-date from
`created_at_utc` with a 90-day minimum floor, not a duplicate fixed 90-day
window.

## 4. Executive Summary Schema

`executive_summary.json` should include:

- headline period;
- wholesale-only perfect-foresight revenue;
- wholesale-only rolling revenue;
- wholesale plus EAC perfect-foresight revenue;
- wholesale plus EAC rolling revenue;
- capture ratios;
- top caveats;
- source labels;
- links to detailed cache files.

## 5. Caveat Flags

Minimum caveat flags:

- `wholesale_proxy`;
- `perfect_foresight_upper_bound`;
- `rolling_no_leakage_policy`;
- `eac_price_taking_proxy`;
- `bm_excluded`;
- `cm_scenario_only`;
- `finance_scenario_appraisal`;
- `benchmark_reconciliation_not_replication`;
- `not_a_market_index`;
- `partial_sample_annualised` where applicable.

The 90d window is the minimum annualisation and public eligibility gate. Shorter
windows may be displayed as preview diagnostics. Any annualised value from an
incomplete sample must include `partial_sample_annualised`.
Annualised finance and benchmark model fields are suppressed/null until stack-series coverage gates pass.

## 6. Dashboard Failure Behaviour

If a cache file is missing, the dashboard should:

- display a clear missing-cache message;
- show which build command regenerates it;
- continue loading unaffected pages where possible;
- avoid falling back to live API calls or solves.

## 7. Refresh Cadence

Default Release 1 cadence:

```text
manual rebuild before public release
```

Scheduled refresh is out of scope until source clients, licences and runtime budgets are stable.

## 8. Release Cache Commands

Use `uv run gb-bess build-phase4-aligned-cache` to fetch aligned Elexon MID and
NESO EAC source JSON for a requested window. The default is a seven-day release
preview. Use `uv run gb-bess run-release-cache` to run the cached OpenBESS Stack
Index preview and write the dashboard artefacts.

## 9. Tests

Dashboard tests should verify:

- import smoke test passes;
- app can load minimal fixture cache;
- missing cache file is handled gracefully;
- no network clients are called during normal dashboard load;
- no solver package is required for dashboard import.
