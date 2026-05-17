# Phase 2 Baseline Method

## Purpose

Phase 2 builds the energy-only deterministic BESS dispatch baseline. It is a perfect-foresight upper-bound benchmark for wholesale arbitrage only. It is not a trading strategy and does not include EAC, Capacity Market, degradation, BM revenue or rolling forecast uncertainty.

## Model

The model chooses half-hourly charge and discharge quantities for one reference battery. Market-facing power is AC MW and state of charge is internal MWh.

The state equation is:

```text
soc[t+1] = soc[t]
         + eta_charge * charge_mw[t] * duration_h[t]
         - discharge_mw[t] * duration_h[t] / eta_discharge
```

The objective is:

```text
max sum_t price_gbp_per_mwh[t]
        * (discharge_mw[t] - charge_mw[t])
        * duration_h[t]
```

The default release mode uses binary charge/discharge exclusivity so scheduled charging and discharging cannot occur in the same period. The default terminal condition is cyclic SoC, meaning the final SoC must equal the initial SoC.

## Inputs

Phase 2 consumes canonical `WholesalePricePoint` records from Phase 1. Each record must include UTC interval timestamps, `duration_h`, source labels, proxy labels and known-time metadata.

Tiny smoke runs use `tests/fixtures/phase2_toy_prices.csv`. Historical/public runs should use processed Elexon MID data and must label the price source as a public wholesale proxy.

## Historical Sample

`historical_sample_summary.json` records a live Elexon MID APXMIDP sample for `2024-01-01` to `2024-01-02`. The sample solves with the default 50 MW / 100 MWh reference asset, cyclic terminal SoC and binary charge/discharge exclusivity.

A single one-month API request returned HTTP 400 during Phase 2 execution. Full-month public refresh should therefore use a chunked Phase 1 data workflow rather than assuming an arbitrary long date range is accepted by the source endpoint.

## Outputs

The result schema records:

- charge MW;
- discharge MW;
- start and end SoC;
- net export MW;
- period revenue;
- cumulative revenue;
- solver status and objective;
- annualised GBP/MW/year;
- charged and discharged MWh;
- equivalent throughput cycles;
- average buy and sell prices.

## Validation Cases

The synthetic test suite covers:

- flat zero price;
- low-high spread;
- negative-positive prices;
- insufficient spread below losses;
- cyclic terminal condition;
- free-terminal diagnostic end-drain artefact;
- no simultaneous scheduled charge and discharge;
- objective equals extracted revenue.

## Caveats

Perfect foresight is an upper bound. Free terminal SoC is diagnostic only. Annualised partial-sample revenue must not be compared to external annual benchmarks without displaying the annualisation method.
