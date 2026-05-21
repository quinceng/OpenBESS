# Phase 6 Review - Dashboard, Methodology and Release Hardening

## Outcome

Phase 6 may proceed with caveat. The release artefact now has a rebuilt
canonical 90-day dashboard cache, explicit no-leakage forecast model comparison
outputs, target-window metadata for the preferred trailing-12-month coverage
path, and public docs that distinguish the canonical OpenBESS cache from the
commercial trailing-12-month branch artefact.

## Built

- Rebuilt the canonical release cache at `results/dashboard/release_90d_historical`.
- Added `forecast_model_comparison.parquet` and
  `forecast_model_comparison.csv` to the dashboard cache contract.
- Added side-by-side previous-day versus trailing-mean forecast baseline
  comparison with MAE, RMSE, rolling revenue, capture ratio and no-leakage
  diagnostics.
- Added `target_window_label`, `target_window_coverage_pct` and
  `target_window_eligible` metadata under `manifest.json` `stack_series`.
- Added `below_trailing_12m_coverage` caveat flag for canonical OpenBESS runs
  that meet the 90-day gate but not the preferred trailing-12-month target.
- Documented that `results/dashboard/commercial_trailing_12m` is a generated
  commercial branch artefact, not the canonical OpenBESS reference cache.

## Release Cache Evidence

Canonical cache:

```text
results/dashboard/release_90d_historical
```

Run ID:

```text
release_cache_elexon_mid_neso_eac_2026_02_01_0000_2026_05_02_0000_utc
```

The rebuilt canonical cache uses `openbess_canonical_1mw_2mwh` over 4,320
settlement periods, equal to 2,160 hours. The primary stack-series window is
`90d`; it is eligible for annualisation and public-index preview use. The target
window is `trailing_12m`; target coverage is 0.2465753425 and is not yet
eligible.

Central rolling policy evidence:

| Metric | Value |
| --- | ---: |
| Perfect-foresight total revenue | GBP 16,958.91 |
| Rolling total revenue | GBP 4,826.43 |
| Capture ratio | 0.2846 |
| Forecast MAE | GBP 27.96/MWh |
| Forecast RMSE | GBP 33.80/MWh |
| Solver failures | 0 |

Forecast model comparison:

| Forecast model | MAE GBP/MWh | RMSE GBP/MWh | Rolling revenue GBP | Capture ratio | Oracle steps |
| --- | ---: | ---: | ---: | ---: | ---: |
| `previous_day_same_period` | 27.96 | 33.80 | 4,826.43 | 0.2846 | 0 |
| `trailing_7_day_mean_by_settlement_period` | 25.45 | 29.84 | 7,291.37 | 0.4299 | 0 |

Both forecast rows report `excluded_future_row_count=196560`,
`excluded_service_cell_count=14052`, `forecast_is_oracle=false` and
`oracle_step_count=0`.

Finance evidence remains scenario appraisal. Annualised rolling revenue is
GBP 19,573.86 and annualised degradation cost is GBP 5,163.63 because the 90-day
coverage gate passes. These values are not bankability claims.

The existing `results/dashboard/commercial_trailing_12m` artefact has
`primary_window_label=trailing_12m`, but it uses
`commercial_phase4_3mw_10mwh`. It is retained as longer-coverage branch evidence,
not as the canonical OpenBESS reference asset cache.

## Acceptance Status

| Requirement | Status |
| --- | --- |
| Dashboard cache rebuilt or selected for canonical release evidence | Complete |
| Forecast comparison explicit and cached | Complete |
| Forecast comparison reports MAE, RMSE and revenue capture | Complete |
| Forecast comparison keeps no-leakage diagnostics visible | Complete |
| 90-day gate remains minimum public annualisation gate | Complete |
| Trailing-12-month target window is explicit in metadata | Complete |
| Commercial trailing-12-month artefact is labelled as branch evidence | Complete |
| Phase 6 review exists | Complete |

## Caveats

- The canonical OpenBESS cache still does not have full trailing-12-month
  coverage. It carries `below_trailing_12m_coverage`.
- The trailing-mean forecast baseline is a transparent diagnostic, not a
  commercial forecasting product.
- The Capacity Market value remains a scenario/reference sidecar.
- Balancing Mechanism counterfactual revenue remains excluded.
- Dashboard outputs remain cached artefacts; the Streamlit app must not run live
  solves or API backfills during normal use.

## Verification

Final Phase 6 release checks were run before the v0.1.1 tag:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
uv run gb-bess run-phase4-smoke --finance-assumptions-yaml configs/finance_assumptions.yaml
uv run gb-bess build-phase4-aligned-cache --start 2026-02-01T00:00:00Z --days 90 --output-dir results/runs/release_cache_90d_historical/aligned_sources
uv run gb-bess run-release-cache --aligned-cache-dir results/runs/release_cache_90d_historical/aligned_sources --output-dir results/runs/release_cache_90d_historical --dashboard-dir results/dashboard/release_90d_historical --target-window-label trailing_12m
```

## Gate Decision

Proceed with caveat.
