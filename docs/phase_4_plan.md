# Phase 4 Plan

Phase 4 extends the no-leakage rolling policy from wholesale-only dispatch to wholesale plus EAC availability revenue.

## Started

- Rolling market-stack policy using the existing forecast and information-set pattern.
- EAC cells are re-indexed to each rolling horizon and excluded when not known at the decision time.
- Executed rows report energy revenue, service revenue, reserve commitments and state-of-charge carry-forward.
- Deterministic scalar sweeps cover wholesale price scaling and EAC price scaling.

## Next

- Add capture-ratio evaluation against perfect-foresight market-stack results.
- Add 24h and 48h smoke runs over a larger fixture.
- Add scenario outputs suitable for the dashboard cache contract.
- Add forecast-error sweeps once the rolling EAC baseline is stable.
