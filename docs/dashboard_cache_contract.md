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
results/dashboard/policy_capture.parquet
results/dashboard/eac_commitments.parquet
results/dashboard/scenario_sweeps.parquet
results/dashboard/finance_cashflows.parquet
results/dashboard/benchmark_reconciliation.json
results/dashboard/data_quality.json
results/dashboard/caveats.json
```

Phase 4 currently writes the implemented subset needed for the cached explainer:

```text
results/dashboard/manifest.json
results/dashboard/executive_summary.json
results/dashboard/revenue_stack.parquet
results/dashboard/policy_capture.parquet
results/dashboard/scenario_sweeps.parquet
results/dashboard/caveats.json
```

`eac_commitments.parquet`, `finance_cashflows.parquet`,
`benchmark_reconciliation.json` and `data_quality.json` remain follow-on cache
files for later dashboard and finance/reconciliation work.

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
- `partial_sample_annualised` where applicable.

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

## 8. Tests

Dashboard tests should verify:

- import smoke test passes;
- app can load minimal fixture cache;
- missing cache file is handled gracefully;
- no network clients are called during normal dashboard load;
- no solver package is required for dashboard import.
