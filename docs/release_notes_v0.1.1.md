# OpenBESS v0.1.1 Release Note

Release date: 2026-05-21

OpenBESS v0.1.1 is a Release 1 patch that hardens the public dashboard cache,
forecast-policy diagnostics and reproducibility notes after the initial v0.1.0
tag.

## What changed

- Rebuilt the canonical OpenBESS dashboard cache over the 90-day historical
  Elexon MID and NESO EAC window from 2026-02-01 to 2026-05-02 UTC.
- Added `forecast_model_comparison.parquet` and
  `forecast_model_comparison.csv` to compare previous-day and trailing-mean
  no-leakage wholesale forecast baselines.
- Added `target_window_label`, `target_window_coverage_pct` and
  `target_window_eligible` metadata for the preferred `trailing_12m` public
  coverage window.
- Added the `below_trailing_12m_coverage` caveat for canonical OpenBESS runs
  that pass the 90-day annualisation gate but do not yet have full trailing
  12-month coverage.
- Documented that `results/dashboard/commercial_trailing_12m` is branch
  evidence from a commercial asset configuration, not the canonical OpenBESS
  reference cache.
- Kept dashboard cache `schema_version` at `0.1.0` because the cache changes
  are additive.

## Verification

The release branch passed:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy src`
- `uv run pytest`
- `uv run gb-bess run-phase4-smoke --finance-assumptions-yaml configs/finance_assumptions.yaml`
- `uv run gb-bess build-phase4-aligned-cache --start 2026-02-01T00:00:00Z --days 90 --output-dir results/runs/release_cache_90d_historical/aligned_sources`
- `uv run gb-bess run-release-cache --aligned-cache-dir results/runs/release_cache_90d_historical/aligned_sources --output-dir results/runs/release_cache_90d_historical --dashboard-dir results/dashboard/release_90d_historical --target-window-label trailing_12m`
- Dashboard import smoke check without solver imports.

## Scope

This release is a public-data research artefact. It is not trading software,
investment advice, a bankability model, an official market index or a
commercial forecasting product.
