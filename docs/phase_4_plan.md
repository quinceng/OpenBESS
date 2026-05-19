# Phase 4 Plan

Phase 4 extends the no-leakage rolling policy from wholesale-only dispatch to wholesale plus EAC availability revenue.

## Started

- Rolling market-stack policy using the existing forecast and information-set pattern.
- EAC cells are re-indexed to each rolling horizon and excluded when not known at the decision time.
- Executed rows report energy revenue, service revenue, reserve commitments and state-of-charge carry-forward.
- Deterministic scalar sweeps cover wholesale price scaling and EAC price scaling.
- Multi-day synthetic stress-price profiles cover full settlement days rather than tiny toy samples.
- Phase 4 commercial assumptions now include site export limits, capex components and route-to-market fee/eligibility checks.
- The residential branch now has a simple household payback calculator for capex, export-limit, self-consumption, tariff-arbitrage and aggregator/VPP assumptions.
- Market-stack capture evaluation now compares the rolling EAC-aware policy with a perfect-foresight wholesale plus EAC ceiling.
- 24h and 48h smoke-window comparisons run against the longer Phase 4 stress profile when enough periods are available.
- `gb-bess run-phase4-smoke` writes a reproducible commercial rolling revenue-stack run, capture evaluation, smoke-window comparisons, scenario sweep, investor workbook and dashboard cache.
- The cached Streamlit dashboard reads `results/dashboard/*` only and does not import solver or live source-client modules during normal dashboard import.
- Phase 5 cache files now add throughput degradation proxy, illustrative finance scenario appraisal and benchmark reconciliation placeholders with caveat labels.
- The residential branch now has a bill-aware household dispatch slice for interval load, PV, import/export tariffs and optional VPP events.

## Next

- Add forecast-error sweeps once the rolling EAC baseline is stable.
- Add `eac_commitments.parquet` and dashboard data-quality cache files.
- Replace synthetic Phase 4 examples with a small aligned historical Elexon/NESO sample once licence and known-time assumptions are checked.
- Expand the residential branch from the bill-aware household dispatch slice into
  a scenario-depth workstream: shaped household archetypes, smart tariffs, PV
  size sweeps, G98/G99/G100 export-limit scenarios, cycling/degradation
  sensitivities and homeowner/investor summary outputs. The detailed section
  lives in
  `docs/superpowers/plans/2026-05-19-residential-load-pv-tariff-vpp.md`.

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

- `stress_prices.csv`;
- `rolling_market_stack_run.json`;
- `policy_capture.json`;
- `smoke_window_comparisons.json`;
- `phase4_scenario_sweep.json`;
- `summary.json`;
- `gb_bess_investor_phase4_workbook.xlsx`.

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
- `caveats.json`.
