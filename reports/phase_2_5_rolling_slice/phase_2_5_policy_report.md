# Phase 2.5 Policy Report - Energy-Only Rolling Slice

## Scope

Phase 2.5 turns the Phase 2 perfect-foresight energy-only optimiser into a realisable rolling-policy evaluator. The policy now builds an explicit information set at each decision time, forecasts only from rows known at that time, solves a short dispatch window, executes only the configured first block, then carries the realised battery state into the next solve.

The implementation is intentionally energy-only. EAC service logic, availability commitments and scenario sweeps remain Phase 3+ work.

## Implemented Policy Components

- Information-set builder: filters source data by `known_at_utc <= decision_time_utc` and stores a deterministic hash of the data available to each decision.
- Forecast interface: supports previous-day same-period, trailing mean by settlement period and an oracle diagnostic forecast that is clearly marked as non-deployable.
- Rolling engine: reuses the Phase 2 optimiser, executes only the first configured block, carries SoC from executed rows and stores a per-step trace.
- Evaluation: reports realised revenue, planned revenue, capture ratio, regret, solver failures and forecast MAE/RMSE.
- Terminal policy diagnostics: keeps `free` terminal SoC as a diagnostic mode, keeps `cyclic` compatibility, and adds explicit `target` terminal SoC support for reference-SoC rolling runs.

## Smoke Run

Command:

```bash
uv run gb-bess run-rolling-smoke --output-dir reports/phase_2_5_rolling_slice/smoke_outputs
```

The smoke run uses a two-hour synthetic energy-only sample. Day 1 acts as already-known history. Day 2 is the evaluation window. The deployable baseline is `previous_day_same_period`, so the forecast can reproduce the day-2 shape without reading future realised day-2 prices.

| Metric | Value |
| --- | ---: |
| Perfect-foresight revenue | GBP 90.00 |
| Rolling realised revenue | GBP 90.00 |
| Rolling planned revenue | GBP 90.00 |
| Capture ratio | 1.000 |
| Regret | GBP 0.00 |
| Solver failures | 0 |
| Forecast MAE | GBP 0.00/MWh |
| Forecast RMSE | GBP 0.00/MWh |

Cached outputs:

- `reports/phase_2_5_rolling_slice/smoke_outputs/perfect_foresight_dispatch.json`
- `reports/phase_2_5_rolling_slice/smoke_outputs/rolling_run.json`
- `reports/phase_2_5_rolling_slice/smoke_outputs/policy_evaluation.json`

## Step Trace

| Decision time | Action | SoC start | SoC end | Realised revenue |
| --- | --- | ---: | ---: | ---: |
| 2024-01-02 00:00 UTC | Charge 1 MW | 1.0 MWh | 1.5 MWh | GBP -5.00 |
| 2024-01-02 00:30 UTC | Charge 1 MW | 1.5 MWh | 2.0 MWh | GBP -5.00 |
| 2024-01-02 01:00 UTC | Discharge 1 MW | 2.0 MWh | 1.5 MWh | GBP 50.00 |
| 2024-01-02 01:30 UTC | Discharge 1 MW | 1.5 MWh | 1.0 MWh | GBP 50.00 |

## Terminal SoC Result

The rolling smoke run uses `terminal_soc_policy="target"` with a 1.0 MWh reference target. This avoids using a free end-of-window battery drain for headline metrics and avoids the receding-window issue where a rolling optimiser can keep postponing discharge if the terminal target always resets to the current SoC.

`free` terminal mode remains available only as a diagnostic. The unit tests include a designed fixture that proves it can create an artificial end-drain benefit.

## Verification

Phase 2.5 has network-free tests for:

- future rows being excluded from decision-time information sets;
- forecasts being unable to use rows not known at the decision time;
- SoC carry-forward using executed actions rather than planned tail actions;
- rolling oracle behaviour on synthetic energy-only cases;
- explicit terminal target enforcement;
- free-terminal artefact detection;
- controlled solver-failure handling;
- capture ratio and regret calculation;
- reproducible per-step records.

## Limitations

- The smoke run is deliberately tiny and synthetic, so it proves plumbing and accounting rather than commercial performance.
- Forecast baselines are transparent but simple. They are placeholders for richer forecasting in later phases.
- The oracle forecast is diagnostic only and must not be used as a deployable policy.
- The rolling interface is ready for EAC extension, but EAC prices, availability matrices and service constraints are not implemented in this phase.
