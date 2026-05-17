# Assumptions Ledger

This ledger records numerical and modelling assumptions that affect project outputs. It should be updated whenever a value, policy or boundary changes.

## Status Definitions

| Status | Meaning |
|---|---|
| `research_anchor` | Mentioned in source research and useful for orientation, but not verified enough for central results. |
| `phase1_required` | Must be verified during P1-00 before central use. |
| `central_default` | Approved for central Release 1 runs after source review. |
| `sensitivity_only` | May be used in labelled sensitivity runs, not central result. |
| `diagnostic_only` | Used only to expose artefacts or compare methods. |
| `excluded` | Explicitly outside Release 1. |

## Assumption Register

| ID | Area | Assumption or policy | Unit | Status | Source ID | Sensitivity range | Caveat |
|---|---|---|---|---|---|---|---|
| A-TIME-001 | Time | Canonical processing uses timezone-aware UTC. | policy | central_default | PROJECT_CONVENTION | none | Local time is display only. |
| A-TIME-002 | Time | Delivery intervals are start-inclusive and end-exclusive. | policy | central_default | PROJECT_CONVENTION | none | Required for settlement-period alignment. |
| A-TIME-003 | Rolling | Rolling inputs must satisfy `known_at_utc <= decision_time_utc`. | policy | central_default | PROJECT_CONVENTION | none | Conservative known-at proxy required if source lacks publication time. |
| A-ASSET-001 | Asset | Reference asset is 2-hour BESS. | hours | phase1_required | PROJECT_CONVENTION | 1h, 2h, 4h | Central MW/MWh values to be set in config. |
| A-ASSET-002 | Asset | Market variables are AC MW and SoC is internal MWh. | policy | central_default | PROJECT_CONVENTION | none | Must be visible in methodology. |
| A-EFF-001 | Efficiency | If only round-trip efficiency is provided, split using square root. | fraction | central_default | PROJECT_CONVENTION | charge/discharge asymmetric case | Conversion must be recorded in manifest. |
| A-WHOLESALE-001 | Wholesale | Elexon BMRS MID is central public wholesale proxy unless replaced by verified better source. | GBP/MWh | phase1_required | ELEXON_BMRS_MID | N2EXMIDP, APXMIDP | Must not be labelled day-ahead execution price. |
| A-WHOLESALE-002 | Wholesale | Negative prices are valid observations. | policy | central_default | PROJECT_CONVENTION | none | Missing prices require explicit quality flag. |
| A-EAC-001 | EAC | EAC model is price-taking availability proxy. | policy | central_default | NESO_EAC_AUCTION_RESULTS | none | Not auction clearing or strategic bidding. |
| A-EAC-002 | EAC | DC/DM/DR are expected central candidates if source fields verify labels, directions and windows. | policy | phase1_required | NESO_EAC_AUCTION_RESULTS | product subsets | Do not hard-code durations before verification. |
| A-EAC-003 | EAC | BR/QR/SR are source-gated optional products. | policy | sensitivity_only | NESO_EAC_AUCTION_RESULTS | include/exclude by product | Include only if definitions, units and windows are verified. |
| A-EAC-004 | EAC | Availability prices are converted to GBP/MW/h. | GBP/MW/h | phase1_required | NESO_EAC_AUCTION_RESULTS | source-unit alternatives | Conversion must be tested. |
| A-EAC-005 | EAC | Idle reserve holding is physically allowed subject to power and SoC feasibility. | policy | central_default | PROJECT_CONVENTION | none | Reserve eligibility is not tied to scheduled dispatch mode. |
| A-EAC-006 | EAC | Upward reserve AC MW requires stored energy divided by discharge efficiency. | MWh | central_default | PROJECT_CONVENTION | alternative convention diagnostic | Assumes delivered AC reserve convention. |
| A-EAC-007 | EAC | Downward reserve AC MW requires empty capacity multiplied by charge efficiency. | MWh | central_default | PROJECT_CONVENTION | alternative convention diagnostic | Assumes imported AC reserve convention. |
| A-EAC-008 | EAC | Product block constancy is enforced only where source verification supports it. | policy | phase1_required | NESO_EAC_MARKET_RULES | no-block sensitivity | Do not invent block rules. |
| A-CM-001 | Capacity Market | CM revenue is annual, not settlement-period dispatch revenue. | policy | central_default | CM_OFFICIAL_AUCTION_PARAMETERS | none | Must not alter central dispatch objective. |
| A-CM-002 | Capacity Market | CM revenue uses duration-, auction- and delivery-year-specific derating. | fraction | phase1_required | CM_OFFICIAL_AUCTION_PARAMETERS | low/central/high | No-derating is diagnostic only. |
| A-CM-003 | Capacity Market | 2h BESS derating values 27.15 percent T-1 and 20.94 percent T-4 are research anchors from 2024/25 article. | fraction | research_anchor | MODO_CM_DERATING_2024_25_ANCHOR | official verified values | Not timeless constants. |
| A-POLICY-001 | Policy | Perfect foresight is an upper-bound diagnostic. | policy | central_default | PROJECT_CONVENTION | none | Not implementable. |
| A-POLICY-002 | Policy | Rolling state is updated from executed actions only. | policy | central_default | PROJECT_CONVENTION | none | Planned future actions cannot update SoC. |
| A-POLICY-003 | Policy | Rolling terminal policy defaults to explicit target/band/penalty, not free terminal SoC. | policy | central_default | PROJECT_CONVENTION | terminal policy sweep | Free terminal is diagnostic only. |
| A-DEG-001 | Degradation | Central degradation is ex-post throughput proxy. | GBP/MWh throughput | sensitivity_only | PROJECT_CONVENTION | low/central/high cost | Not calibrated electrochemical model. |
| A-DEG-002 | Degradation | Endogenous degradation shadow price is optional sensitivity. | GBP/MWh throughput | sensitivity_only | PROJECT_CONVENTION | on/off, cost range | Do not mix with ex-post central results in same headline. |
| A-FIN-001 | Finance | NPV is illustrative scenario appraisal. | policy | central_default | PROJECT_CONVENTION | discount-rate sweep | Not bankability or investment advice. |
| A-FIN-002 | Finance | Forward revenues may repeat a historical year or use decay scenarios. | policy | sensitivity_only | PROJECT_CONVENTION | low/central/high decay | Assumption, not forecast. |
| A-BM-001 | Balancing Mechanism | Deterministic BM counterfactual revenue is excluded. | policy | excluded | PROJECT_CONVENTION | observed appendix only | Public data cannot infer hypothetical acceptances. |
| A-BENCH-001 | Benchmark | Public benchmark comparison is reconciliation. | policy | central_default | PUBLIC_BENCHMARK_ANCHORS | none | Not replication or validation. |
| A-DASH-001 | Dashboard | Dashboard reads cached artefacts only. | policy | central_default | PROJECT_CONVENTION | none | No live heavy solves or API backfill. |

## Update Rules

When an assumption becomes central:

1. Verify the source and licence.
2. Record the exact value, unit and date.
3. Add or update source registry entry.
4. Add tests if the assumption affects model equations.
5. Add sensitivity range if uncertainty materially affects outputs.
6. Reference the assumption ID in config or manifest metadata.
