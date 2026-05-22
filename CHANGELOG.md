# Changelog

## Unreleased

- Promoted the canonical `openbess_canonical_1mw_2mwh` dashboard cache to the
  trailing-12-month window after the manifest passed the preferred coverage
  gate.
- Added release-cache stage timing plus a `trailing12m` profile that skips
  supplementary diagnostics while preserving required gate outputs.
- Polished the README release story with trailing-12-month headline evidence,
  key results and the canonical dashboard cache command.
- Added dashboard cache directory selection via `GB_BESS_DASHBOARD_CACHE_DIR`.
- Kept 90-day canonical-asset runs labelled as `OpenBESS Stack Index Preview`
  until the `trailing_12m` target-window gate passes.
- Promoted stable phase/process evidence docs while keeping detailed local
  implementation plans ignored.
- Reconciled verified Elexon MID and NESO EAC source assumptions in the
  assumptions ledger.

## 0.1.1 - 2026-05-21

- Added Phase 6 no-leakage forecast model comparison artefacts for previous-day and trailing-mean wholesale forecast baselines.
- Added trailing-12-month target-window metadata while keeping the 90-day historical canonical cache as the Release 1 minimum annualisation gate.
- Added Phase 6 release review evidence and reproducibility notes distinguishing the commercial trailing-12-month branch artefact from the canonical OpenBESS cache.

## 0.1.0 - 2026-05-20

- Added OpenBESS Stack Index preview artefacts, reference asset presets and public methodology documentation.
- Added Phase 4 historical Elexon/NESO smoke fixtures and cache-backed dashboard artefacts.
- Added Phase 5 degradation, finance scenario appraisal and benchmark reconciliation cache outputs.
- Added residential payback, bill-aware dispatch smoke and named scenario sweep examples.
- Added release hardening checks for dashboard cache boundaries, source caveats and reproducibility.
