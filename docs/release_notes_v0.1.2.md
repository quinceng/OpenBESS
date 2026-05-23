# OpenBESS v0.1.2 Release Note

Release date: 2026-05-23

OpenBESS v0.1.2 promotes the canonical reference asset from the historical
90-day preview cache to the preferred trailing-12-month public evidence cache.
It remains a public-data research artefact, not trading software, investment
advice, a bankability model, an official market index or a proprietary
benchmark replication.

## Highlights

- Promoted `openbess_canonical_1mw_2mwh` to the trailing-12-month historical
  window from `2025-05-20T00:00:00Z` to `2026-05-20T00:00:00Z`.
- Recorded 17,520 settlement periods, 365 daily rolling-policy steps, zero
  solver failures and 100% `trailing_12m` target-window coverage.
- Reported GBP 49,438.74 perfect-foresight upper-bound value, GBP 17,402.24
  previous-day rolling-policy value and 35.20% capture ratio for the canonical
  reference asset.
- Added `GB_BESS_DASHBOARD_CACHE_DIR` so the Streamlit dashboard can inspect
  named generated caches such as `results/dashboard/release_trailing_12m_historical`.
- Added release-cache stage timing and the `trailing12m` profile, which keeps
  required gate outputs while skipping supplementary diagnostics for the
  long-running full-year release job.
- Made dashboard cache manifests record a Git-derived `code_version` by default,
  with `GB_BESS_CODE_VERSION` available when a release job needs an explicit
  stamp.
- Hardened the release-cache CLI option exposure test against Rich/Typer help
  rendering differences in headless GitHub Actions runs.

## Verification

The release branch passed:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy src`
- `uv run pytest`
- `GB_BESS_DASHBOARD_CACHE_DIR=results/dashboard/release_trailing_12m_historical uv run python -c "import dashboard.streamlit_app"`
- `uv run gb-bess run-phase4-smoke --finance-assumptions-yaml configs/finance_assumptions.yaml --output-dir results/runs/release_smoke_v0_1_2 --dashboard-dir results/dashboard/release_smoke_v0_1_2`

The canonical trailing-12-month cache was generated before this release tag with:

```bash
uv run gb-bess build-phase4-aligned-cache \
  --start 2025-05-20T00:00:00Z \
  --days 365 \
  --output-dir results/runs/release_cache_trailing_12m_historical/aligned_sources

uv run gb-bess run-release-cache \
  --aligned-cache-dir results/runs/release_cache_trailing_12m_historical/aligned_sources \
  --output-dir results/runs/release_cache_trailing_12m_historical \
  --dashboard-dir results/dashboard/release_trailing_12m_historical \
  --profile trailing12m \
  --target-window-label trailing_12m
```

## Scope

This release does not add stochastic programming, Balancing Mechanism
counterfactual optimisation, full EAC auction clearing or bankability
underwriting. Phase 7 stochastic work remains optional and should only start
after Release 1 core evidence stays green.
