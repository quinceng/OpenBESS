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
- Finance assumptions can be loaded from YAML through the Phase 4 smoke CLI.
- Benchmark reconciliation cache writes sourced public anchor rows with URL,
  access date, methodology status and caveat labels.
- Dashboard cache writes `eac_commitments.parquet` and `data_quality.json`.
- Cached dashboard displays Phase 5 outputs when the files are present.

## Next

- Replace tiny partial-sample annualisation with a longer aligned historical
  Elexon/NESO cache once source timing and licence assumptions are verified.
- Add deeper finance sensitivity cases: fixed O&M, augmentation timing and
  Capacity Market annual contribution.

## Boundaries

- Finance output must say `illustrative scenario appraisal`.
- Finance output must not claim bankability, investment advice or proprietary
  benchmark replication.
- Benchmark rows are reconciliation context only and must not become model
  calibration targets.
