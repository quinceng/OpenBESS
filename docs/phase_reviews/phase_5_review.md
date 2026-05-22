# Phase 5 Review - Finance, Degradation and Benchmark Cache

## Outcome

Phase 5 may proceed with caveat. The degradation proxy, finance cashflows,
finance sensitivity rows and benchmark reconciliation outputs are implemented
as an illustrative scenario appraisal, not a bankability model.

## Built

- Throughput-based degradation summary with equivalent-cycle estimate.
- Configurable finance assumptions loaded from YAML.
- Fifteen-year cashflow table with annual market revenue, Capacity Market
  sidecar revenue, degradation cost, fixed O&M, augmentation capex, NPV and
  simple payback.
- Named low/central/high finance sensitivity rows written to
  `finance_sensitivities.parquet` and `finance_sensitivities.csv`.
- Public benchmark reconciliation rows with source URL, access date,
  methodology status and caveat labels.
- Capacity Market source metadata, source status and sidecar caveat carried into
  finance summary and assumptions ledger.
- Dashboard reader and Streamlit view-model support for finance sensitivities.

## Release Cache Evidence

The 90-day historical release cache generated Phase 5 outputs from the
canonical OpenBESS 1MW/2MWh reference asset. Annualisation was allowed because
the 90d stack-series coverage gate passed. The finance summary reported an
annualised rolling revenue of GBP 19,573.86 and annualised degradation cost of
GBP 5,163.63 before configured finance sensitivities.

The Capacity Market value remains a scenario/reference sidecar. The T-4
2028/29 two-hour BESS derating currently uses the Modo research anchor, while
official Capacity Market auction publications are kept as clearing-price and
scheme context. It is not a central official storage-derating result.

## Acceptance Status

| Requirement | Status |
| --- | --- |
| Degradation proxy is cached | Complete |
| Finance outputs state illustrative scenario appraisal | Complete |
| Cashflows include fixed O&M, CM sidecar and augmentation | Complete |
| Low/central/high finance sensitivities are cached | Complete |
| Benchmark reconciliation is sourced and caveated | Complete |
| CM source discipline is visible in artefacts | Complete |
| Phase 5 review is written | Complete |

## Caveats

- Finance output excludes debt, tax, grid charges, insurance, route-to-market
  fees and site-specific contracts unless they are added explicitly.
- Fixed O&M and augmentation assumptions are public-sensitivity placeholders,
  not audited GB project estimates.
- Public benchmark anchors are reconciliation context only and must not become
  calibration targets.
- Annualised finance fields remain suppressed/null until stack-series coverage
  gates pass.

## Gate Decision

Proceed with caveat.

