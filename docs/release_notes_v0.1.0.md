# OpenBESS v0.1.0 Release Note

Release date: 2026-05-20

OpenBESS v0.1.0 is the first public research release. It packages the core GB
BESS modelling workflow, the OpenBESS Reference Revenue Stack preview, cached dashboard
artefacts, and reproducible checks.

## Highlights

- Added aligned Elexon MID and NESO EAC release-cache commands.
- Added OpenBESS Reference Revenue Stack CSV and parquet artefacts with coverage gates.
- Added source snapshot, assumptions ledger, data-quality summary, and forecast
  error sweep artefacts.
- Added Capacity Market annual sidecar handling for finance outputs without
  mixing CM into settlement-period dispatch revenue.
- Added dashboard coverage status, caveat display, forecast-error diagnostics,
  and Reference Revenue Stack preview labelling.
- Kept annualised finance and benchmark values suppressed until longer coverage
  gates pass.

## Verification

The release branch passed:

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy src`
- `uv run pytest -q`
- `uv run gb-bess run-phase4-smoke`
- A one-day live release-cache build.
- A seven-day live release-cache build with annualisation suppressed.

## Scope

This release is a public-data research artefact. It is not trading software,
investment advice, a bankability model, or an official market index.
