# Phase 3 EAC Availability Report

## Scope

Phase 3 extends the energy-only optimiser with a GB-specific revenue-stack layer:

- EAC is modelled as a price-taking availability proxy.
- Reserve commitments share battery power headroom and footroom with scheduled energy dispatch.
- Reserve commitments must also be physically deliverable from the current SoC.
- Capacity Market revenue is calculated as an annual scenario layer and is not added to period dispatch rows.

The central Release 1 model still excludes auction clearing, strategic bidding, acceptance probability, activation settlement, performance penalties, BM counterfactuals and full commercial finance.

## Implemented Components

- `markets/eac_services.py`: source-label-preserving EAC service registry.
- `markets/eac_prices.py`: product-by-period EAC price matrix with explicit `available`, `source_gap`, `not_procured` and `not_known_at_decision_time` states.
- `optimisation/constraints_reserve.py`: reserve headroom, footroom and SoC deliverability helper formulas.
- `optimisation/market_stack_model.py`: Pyomo energy + reserve availability co-optimisation.
- `optimisation/revenue_terms.py`: service availability revenue terms.
- `markets/capacity_market.py`: CM scenario loading, validation and annual revenue calculation.
- `configs/scenarios_cm.yaml`: labelled CM scenario assumptions.

## Smoke Run

Command:

```bash
uv run gb-bess run-market-stack-smoke --output-dir reports/phase_3_eac_availability/smoke_outputs
```

The smoke run uses the existing two-hour synthetic wholesale fixture plus one synthetic upward DCL availability product. This is a deterministic plumbing and accounting test, not a commercial revenue forecast.

| Metric | Value |
| --- | ---: |
| Energy dispatch revenue | GBP 90.00 |
| EAC availability revenue | GBP 25.00 |
| Total dispatch revenue | GBP 115.00 |
| Solver objective | GBP 115.00 |
| Solver failures | 0 |
| CM annual scenario revenue | GBP 271,500.00 |

Cached outputs:

- `reports/phase_3_eac_availability/smoke_outputs/market_stack_result.json`
- `reports/phase_3_eac_availability/smoke_outputs/eac_price_matrix.json`
- `reports/phase_3_eac_availability/smoke_outputs/cm_annual_summary.json`

## Reserve Formulation

The model adds reserve variables by service and period:

- `reserve_up_mw[service, period]`
- `reserve_down_mw[service, period]`

Power sharing:

- discharge plus upward reserve cannot exceed export power.
- charge plus downward reserve cannot exceed import power.

Energy deliverability:

- upward reserve uses `reserve_mw * service_duration_h / eta_discharge`.
- downward reserve uses `reserve_mw * service_duration_h * eta_charge`.

Availability revenue is:

```text
price_gbp_per_mw_h * committed_mw * period_duration_h
```

Efficiency is not applied to the availability price.

## Data Policy

- Zero price is a valid observation.
- Not-procured products are separate from source gaps.
- Source/API gaps are not silently zero-filled.
- Rows with `known_at_utc` after the decision time are excluded from decision-time matrices.
- Unknown product labels remain quarantined by the Phase 1 parser/registry logic.

## Capacity Market

CM revenue is annual:

```text
contracted_nameplate_mw * derating_factor * clearing_price_gbp_per_kw_year * 1000
```

The current scenarios are labelled research anchors. No-derating diagnostics are rejected for central results. CM does not alter period dispatch.

## Limitations

- The committed smoke output is synthetic. A full one-month historical EAC + wholesale run still needs an aligned historical dataset refresh.
- Dynamic response service durations and block rules remain source-backed reference assumptions, not hard-coded optimiser constants.
- Quick/Slow Reserve products are present in the source registry but are not central Release 1 products until their public rules are audited.
- Activation energy and performance penalties remain out of central scope.
