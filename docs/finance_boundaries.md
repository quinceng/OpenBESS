# Finance Boundaries

This document defines what the finance module includes, excludes and must say in user-facing output.

## 1. Required Wording

Use this wording in methodology, dashboard and README:

```text
The finance module is illustrative scenario appraisal. It is not investment
advice, bankability analysis or a substitute for commercial due diligence.
```

## 2. Included in Release 1 Scenario Appraisal

| Item | Treatment | Notes |
|---|---|---|
| Wholesale proxy revenue | From solved dispatch trajectories | Source-labelled and caveated. |
| EAC availability proxy revenue | From solved market-stack trajectories | Availability only unless activation sensitivity is explicitly added. |
| Capacity Market revenue | Annual scenario | Uses duration-specific derating. |
| Degradation cost | Throughput proxy | Ex-post central treatment; endogenous shadow price optional sensitivity. |
| Calendar fade | Scenario if implemented | Must state assumption source or project convention. |
| Augmentation capex | Scenario if implemented | Correct cash-flow year and discounting required. |
| Fixed O&M | Only if sourced | Otherwise exclude visibly. |
| Discount rate | Sensitivity | Low/central/high ranges should be explicit. |
| Revenue decay | Scenario assumption | Not a forecast. |

## 3. Excluded Unless Explicitly Added Later

- grid use-of-system charges;
- connection charges;
- route-to-market fees;
- tolling or PPA structures;
- debt sizing and interest;
- tax;
- insurance;
- land lease;
- warranty terms;
- availability guarantees;
- imbalance exposure;
- outages and curtailment;
- construction delay;
- development costs;
- merchant risk premium;
- asset-specific commercial contracts.

The dashboard should show these exclusions near NPV outputs, rather than only in the methodology.

## 4. Cash-Flow Schema

Annual finance outputs should contain:

- `scenario_name`;
- `year_index`;
- `calendar_year` if applicable;
- `wholesale_revenue_gbp`;
- `eac_availability_revenue_gbp`;
- `cm_revenue_gbp`;
- `degradation_cost_gbp`;
- `fixed_om_gbp`;
- `augmentation_capex_gbp`;
- `other_included_costs_gbp`;
- `annual_net_cashflow_gbp`;
- `discount_rate`;
- `discount_factor`;
- `discounted_cashflow_gbp`;
- `cumulative_npv_gbp`;
- `boundary_version`;
- `caveat_flags`.

## 5. NPV Convention

Formula:

```text
NPV = - initial_capex
      + sum_y annual_net_cashflow[y] / (1 + discount_rate)^y
```

Rules:

- year indexing must be explicit;
- capex timing must be explicit;
- augmentation capex must appear in the correct year;
- real versus nominal treatment must be stated;
- CM revenue must appear once per year;
- partial-year annualisation must be labelled.

## 6. Degradation Treatment

Central:

```text
degradation_cost[t] =
    c_throughput_gbp_per_mwh
    * (charge_mw[t] + discharge_mw[t])
    * duration_h[t]
```

Rules:

- degradation cost is non-negative;
- zero cost reproduces base finance result;
- high degradation cost should visibly affect sensitivity outputs;
- do not claim cell-physics accuracy.

## 7. Scenario Labels

Finance scenario labels must identify:

- revenue source scenario;
- CM scenario;
- degradation scenario;
- augmentation scenario;
- discount-rate scenario;
- revenue-decay scenario;
- whether degradation was ex-post or endogenous.

Avoid generic labels such as `base`, `high` or `low` without a parameter table.

## 8. Dashboard Presentation

Finance dashboard page must show:

- NPV range by scenario;
- annual cash-flow stack;
- CM contribution separately from dispatch revenue;
- degradation and augmentation sensitivity;
- finance exclusions;
- scenario assumptions table;
- warning that outputs are scenario appraisal.

## 9. Tests

Minimum tests:

- one-year NPV hand calculation;
- multi-year discounting hand calculation;
- augmentation capex timing;
- CM counted once per year;
- zero degradation cost reproduces base result;
- scenario labels propagate;
- excluded-items metadata exists.
