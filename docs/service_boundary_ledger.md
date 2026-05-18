# Service Boundary Ledger

Phase 3 models EAC as a price-taking availability proxy. It does not model auction clearing, strategic bidding, acceptance probability, activation settlement, BM counterfactual revenue or performance penalties in central Release 1 outputs.

| Element | Release 1 treatment |
| --- | --- |
| EAC clearing or availability price | Exogenous input |
| Asset MW commitment | Decision variable |
| Power headroom and footroom | Modelled |
| Energy deliverability | Modelled using AC reserve convention |
| Delivery/block constancy | Enforced only when source data carries a block id and the registry marks the rule as verified |
| Frequency response windows | Stored in reference data, not hidden in constraints |
| Quick/Slow Reserve | Source-gated; not a central result unless definitions, units and windows are verified |
| Product publication/known time | Preserved and used by rolling/no-leakage filters |
| Procurement volume | Optional cap where source volume is present |
| Service stacking/splitting | Conservative single-asset sharing through headroom/footroom constraints |
| Availability revenue | Price x committed MW x period duration; efficiency is not applied to price |
| Activation/utilisation energy | Excluded from central Release 1 |
| Capacity Market | Annual scenario revenue only; not period dispatch revenue |
