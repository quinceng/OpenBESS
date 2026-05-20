# Methodology

This document is the methodology contract for Release 1. During implementation it should evolve from a contract into the final methodology paper by adding source verification outcomes, result figures and run IDs.

The public series methodology for named OpenBESS outputs is documented in
[`openbess_stack_index.md`](openbess_stack_index.md). This document remains the
detailed equations and implementation contract behind that public methodology.

## 1. Research Question

The project estimates the revenue stack available to a reference GB BESS under transparent public-data assumptions. It compares perfect-foresight upper-bound dispatch with no-leakage rolling policies and explains divergence from public benchmark narratives.

## 2. Scope

Modelled centrally:

- wholesale proxy dispatch;
- EAC price-taking availability;
- Capacity Market annual scenarios;
- degradation proxy;
- finance scenario appraisal;
- benchmark reconciliation.

Excluded centrally:

- deterministic BM counterfactual;
- full EAC auction clearing;
- strategic bidding;
- proprietary benchmark replication;
- bankability conclusion.

## 3. Data

Core datasets:

- Elexon BMRS Market Index Data for wholesale proxy prices;
- NESO EAC auction results for availability proxy prices;
- official Capacity Market parameters where verified;
- public benchmark anchors for reconciliation only.

Every canonical dataset carries source, retrieval, schema and known-time metadata where applicable.

## 4. Battery Dispatch Model

For timestep `t`:

```text
soc[t+1] = soc[t]
         + eta_charge * charge_mw[t] * duration_h[t]
         - discharge_mw[t] * duration_h[t] / eta_discharge
```

Bounds:

```text
0 <= charge_mw[t] <= P_import_max_mw
0 <= discharge_mw[t] <= P_export_max_mw
soc_min_mwh <= soc_mwh[t] <= soc_max_mwh
```

Optional scheduled dispatch mode:

```text
discharge_mw[t] <= P_export_max_mw * is_discharging[t]
charge_mw[t]    <= P_import_max_mw * (1 - is_discharging[t])
```

Energy objective:

```text
sum_t price_gbp_per_mwh[t]
      * (discharge_mw[t] - charge_mw[t])
      * duration_h[t]
```

## 5. EAC Availability Proxy

EAC revenue is price-taking availability revenue:

```text
service_revenue_gbp[s,t] =
    eac_price_gbp_per_mw_h[s,t]
    * committed_mw[s,t]
    * duration_h[t]
```

Power feasibility:

```text
discharge_mw[t] + sum_s reserve_up_mw[s,t] <= P_export_max_mw
charge_mw[t]    + sum_s reserve_down_mw[s,t] <= P_import_max_mw
```

Energy feasibility under delivered AC reserve convention:

```text
soc_mwh[t] - soc_min_mwh >= reserve_up_mw[s,t] * service_duration_h[s] / eta_discharge
soc_max_mwh - soc_mwh[t] >= reserve_down_mw[s,t] * service_duration_h[s] * eta_charge
```

## 6. Perfect Foresight and Rolling Policy

Perfect foresight uses realised future data and is an upper bound.

Rolling policy uses only data satisfying:

```text
known_at_utc <= decision_time_utc
```

Rolling state is updated from executed actions only.

Capture ratio:

```text
capture_ratio = realised_rolling_revenue / perfect_foresight_revenue
```

Regret:

```text
regret = perfect_foresight_revenue - realised_rolling_revenue
```

## 7. Capacity Market

CM annual revenue:

```text
cm_revenue_year =
    contracted_nameplate_mw
    * cm_derating_factor
    * clearing_price_gbp_per_kw_year
    * 1000
```

CM is not a settlement-period dispatch product.

## 8. Degradation

Central degradation proxy:

```text
throughput_mwh[t] =
    charge_mw[t] * duration_h[t]
    + discharge_mw[t] * duration_h[t]

degradation_cost_gbp[t] =
    c_throughput_gbp_per_mwh * throughput_mwh[t]
```

This is a sensitivity and finance adjustment, not a cell-physics model.

## 9. Finance

NPV:

```text
NPV = - initial_capex
      + sum_y annual_net_cashflow[y] / (1 + discount_rate)^y
```

Finance outputs are scenario appraisal and exclude debt, tax, grid charges, insurance, route-to-market fees and site-specific contracts unless explicitly added.

## 10. Benchmark Reconciliation

Benchmark comparison is a reconciliation scorecard with:

- project treatment;
- public benchmark treatment if known;
- expected divergence driver;
- confidence label;
- source URL and date.

It is not validation against a proprietary model.

## 11. Release Evidence

Final methodology should include:

- verified source details;
- data coverage table;
- quality flags;
- selected config values;
- solver and runtime summary;
- headline charts;
- scenario table;
- limitations and future work.
