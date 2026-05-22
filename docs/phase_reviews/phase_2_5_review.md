# Phase 2.5 Review - Energy-Only Rolling Slice

## Outcome

Phase 2.5 is implemented. The codebase now has a realisable rolling-policy layer on top of the Phase 2 energy-only optimiser, with explicit no-leakage controls, simple forecast baselines, state carry-forward, policy evaluation metrics and a repeatable smoke command.

## What Changed

- Added `gb_bess_revenue_stack.policies.information_set` to define what each decision is allowed to know.
- Added `gb_bess_revenue_stack.policies.forecasts` with previous-day, trailing-mean and oracle diagnostic forecast models.
- Added `gb_bess_revenue_stack.policies.rolling` to solve repeated windows, execute only the first block and update SoC from realised execution.
- Added `gb_bess_revenue_stack.policies.evaluation` to compute capture ratio, regret, forecast errors and terminal artefact diagnostics.
- Extended the Phase 2 optimiser input with an explicit terminal SoC target mode, so rolling windows can return to a reference SoC without using a free terminal drain.
- Added `gb-bess run-rolling-smoke` to generate cached Phase 2.5 smoke outputs.

## Acceptance Status

| Requirement | Status |
| --- | --- |
| Information set filters by known time | Complete |
| Forecasts avoid future realised prices | Complete |
| Rolling engine carries executed SoC forward | Complete |
| Capture ratio and regret are computed on the same realised data | Complete |
| Free terminal SoC artefact is detected | Complete |
| Controlled solver failure is tested | Complete |
| Report and cached smoke outputs are written | Complete |

## Risk Notes

- The current smoke sample is intentionally small; larger historical backtests should be added before treating any capture ratio as meaningful.
- Forecast baselines are deterministic and auditable, but not sophisticated.
- The terminal target mode is an equality target. Later phases may need a band or penalty version to avoid over-constraining long or noisy windows.

## Handoff To Phase 3

The rolling interface is stable enough for Phase 3 to add EAC service inputs. The next phase should plug EAC availability and price assumptions into the same information-set, rolling-solve and evaluation pattern rather than creating a separate policy loop.
