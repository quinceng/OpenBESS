# Phase 3 Review - EAC Availability and Capacity Market

## Outcome

Phase 3 is implemented as a first revenue-stack layer. The model now supports energy dispatch plus price-taking EAC availability commitments and a separate annual Capacity Market scenario calculation.

## Built

- Source-label-preserving EAC service registry.
- EAC price matrix aligned to settlement periods.
- Explicit missing-data states for source gaps, not-procured products and rows not known at decision time.
- Pyomo reserve variables for upward and downward availability.
- Power headroom and footroom constraints.
- SoC deliverability constraints using the AC reserve convention.
- Block-constant reserve commitments when a verified block id/rule is present.
- EAC availability revenue component extraction.
- Capacity Market YAML scenario loader and annual revenue calculator.
- `gb-bess run-market-stack-smoke`.
- Phase 3 report and cached smoke outputs.
- Service boundary ledger.

## Acceptance Status

| Requirement | Status |
| --- | --- |
| EAC price pipeline validates known-time and missing data | Complete |
| Service registry stores source labels and source-backed rules | Complete |
| Correct reserve formulation passes tests | Complete |
| Service revenue includes period duration | Complete |
| All services off reproduces Phase 2 | Complete |
| Energy and service components sum to total | Complete |
| Capacity Market is separate from dispatch | Complete |
| Phase 3 report and review are written | Complete |

## Caveats

- The cached smoke run is synthetic and small.
- A full month historical EAC + wholesale run remains dependent on preparing an aligned historical dataset.
- CM derating values remain labelled research anchors until official duration-, auction- and delivery-year-specific values are selected.
- EAC auction clearing, strategic bidding, acceptance probability, activation settlement, performance penalties and BM counterfactual revenue remain out of scope.

## Handoff To Phase 4

Phase 4 can build on `solve_market_stack` and the EAC price matrix to run 24h/48h rolling windows. Runtime benchmarks should cover energy-only, energy plus one EAC product, energy plus verified central EAC products, and one-month perfect-foresight runs.
