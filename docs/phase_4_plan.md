# Phase 4 Plan

Phase 4 extends the no-leakage rolling policy from wholesale-only dispatch to wholesale plus EAC availability revenue.

## Started

- Rolling market-stack policy using the existing forecast and information-set pattern.
- EAC cells are re-indexed to each rolling horizon and excluded when not known at the decision time.
- Executed rows report energy revenue, service revenue, reserve commitments and state-of-charge carry-forward.
- Deterministic scalar sweeps cover wholesale price scaling and EAC price scaling.
- The default Phase 4 smoke path now uses a small aligned historical
  Elexon/NESO fixture rather than synthetic wholesale and EAC examples.
- Phase 4 commercial assumptions now include site export limits, capex components and route-to-market fee/eligibility checks.
- The residential branch now has a simple household payback calculator for capex, export-limit, self-consumption, tariff-arbitrage and aggregator/VPP assumptions.
- Market-stack capture evaluation now compares the rolling EAC-aware policy with a perfect-foresight wholesale plus EAC ceiling.
- 24h and 48h smoke-window comparison helpers remain available when enough
  historical or fixture periods are supplied.
- `gb-bess run-phase4-smoke` writes a reproducible commercial rolling revenue-stack run, capture evaluation, smoke-window comparisons, scenario sweep, investor workbook and dashboard cache.
- The cached Streamlit dashboard reads `results/dashboard/*` only and does not import solver or live source-client modules during normal dashboard import.
- Phase 5 cache files now add throughput degradation proxy, configurable finance scenario appraisal and sourced benchmark reconciliation anchors with caveat labels.
- Dashboard cache files now include EAC commitment detail and a source/data-quality summary.
- The residential branch now has a bill-aware household dispatch slice for interval load, PV, import/export tariffs and optional VPP events.
- Residential release examples now include a named payback scenario sweep for
  flat tariff, smart tariff, PV-rich, G100 export-uplift and low-use/no-VPP
  cases.

## Next

- Add forecast-error sweeps once the rolling EAC baseline is stable.
- Expand the residential branch from the bill-aware household dispatch slice into
  deeper shaped household archetypes, PV size sweeps, cycling/degradation
  sensitivities and homeowner/investor summary outputs.

## Phase 4 Smoke Outputs

Default command:

```bash
uv run gb-bess run-phase4-smoke
```

Default output directory:

```text
results/runs/phase4_revenue_stack/
```

The command writes:

- `historical_prices.csv`;
- `rolling_market_stack_run.json`;
- `policy_capture.json`;
- `smoke_window_comparisons.json`;
- `phase4_scenario_sweep.json`;
- `summary.json`;
- `gb_bess_investor_phase4_workbook.xlsx`.

The default sample is
`elexon_mid_neso_eac_2026_04_01_0000_0230_utc`. It contains Elexon BMRS MID
APXMIDP wholesale proxy rows for 2026-04-01 00:00-02:30 UTC and NESO EAC
auction-result rows whose delivery windows cover every sample settlement
period. It is intentionally tiny for release smoke testing and carries explicit
proxy/known-at caveats in the workbook and dashboard cache.
Because the packaged fixture is shorter than 24h, `smoke_window_comparisons.json`
records the 24h/48h windows as skipped with an `insufficient_periods` reason;
the multi-day stress helper remains covered by unit tests for rolling-window
behaviour. The default smoke validates source alignment and EAC known-at
exclusion; it is not a 24h wholesale forecast-policy performance sample.

This aligned historical Elexon/NESO sample replaces the previous synthetic
Phase 4 example as the default release smoke path.

Default dashboard cache directory:

```text
results/dashboard/
```

Dashboard cache files:

- `manifest.json`;
- `executive_summary.json`;
- `policy_capture.parquet`;
- `revenue_stack.parquet`;
- `scenario_sweeps.parquet`;
- `degradation_summary.json`;
- `finance_summary.json`;
- `finance_cashflows.parquet`;
- `benchmark_reconciliation.json`;
- `eac_commitments.parquet`;
- `data_quality.json`;
- `caveats.json`.
