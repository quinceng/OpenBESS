# Phase 5 Plan

Phase 5 turns saved Phase 4 trajectories into cached degradation, finance and
benchmark-reconciliation artefacts. It remains scenario appraisal, not
bankability analysis.

## Started

- Throughput-based degradation proxy is computed from rolling dispatch steps.
- Dashboard cache writes `degradation_summary.json`.
- Illustrative 15-year finance cashflows are written to
  `finance_cashflows.parquet`.
- Finance summary writes NPV, simple payback year, annualised revenue,
  degradation cost and explicit non-bankability wording.
- Benchmark reconciliation cache writes a scorecard placeholder that labels
  unknown public-anchor methodology as unknown and avoids replication claims.
- Cached dashboard displays Phase 5 outputs when the files are present.

## Next

- Add hand-calculation tests for NPV and payback on a small deterministic
  fixture.
- Add configurable finance assumptions from a YAML or CLI option instead of
  hard-coded Release 1 defaults.
- Add source-backed public benchmark anchor rows with URL, access date,
  methodology status and caveat labels.
- Add `eac_commitments.parquet`, `data_quality.json` and dashboard views for
  source-quality and EAC commitment detail.
- Replace synthetic annualisation examples with a small aligned historical
  Elexon/NESO cache once source timing and licence assumptions are verified.

## Boundaries

- Finance output must say `illustrative scenario appraisal`.
- Finance output must not claim bankability, investment advice or proprietary
  benchmark replication.
- Benchmark rows are reconciliation context only and must not become unit-test
  targets for model calibration.
