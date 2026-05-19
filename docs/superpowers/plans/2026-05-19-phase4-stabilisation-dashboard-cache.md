# Phase 4 Stabilisation And Dashboard Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the Phase 4 release handoff by adding market-stack capture ratios, 24h/48h smoke comparisons, dashboard-ready cache artefacts, and residential documentation reconciliation.

**Architecture:** Keep commercial Phase 4 logic in `gb_bess_revenue_stack.phase4.scenarios`, dashboard artefact writing in `gb_bess_revenue_stack.reporting.dashboard_cache`, and CLI orchestration in `gb_bess_revenue_stack.cli`. Do not mix residential kW/kWh assumptions into the MW/MWh market-stack path.

**Tech Stack:** Python 3.12, Pydantic v2, Pyomo/HiGHS, pandas/pyarrow for dashboard cache Parquet files, Typer CLI, pytest, ruff, mypy.

---

### Task 1: Phase 4 Capture Evaluation

**Files:**
- Modify: `src/gb_bess_revenue_stack/phase4/scenarios.py`
- Test: `tests/unit/test_phase4_scenarios_and_workbook.py`

- [ ] **Step 1: Write the failing test**

Add a test that calls `run_phase4_market_stack_capture_comparison` with a short synthetic market-stack case and asserts that the perfect-foresight total, rolling total, capture ratio and regret are reported.

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/unit/test_phase4_scenarios_and_workbook.py::test_market_stack_capture_comparison_reports_perfect_foresight_ceiling -q`

Expected: import failure because `run_phase4_market_stack_capture_comparison` does not exist.

- [ ] **Step 3: Implement the minimal code**

Add `Phase4MarketStackCaptureResult` and `run_phase4_market_stack_capture_comparison(...)`. The function should solve a perfect-foresight `solve_market_stack(...)`, compare it with a supplied no-leakage rolling run, and report capture ratio as `None` only when the perfect-foresight total is effectively zero.

- [ ] **Step 4: Run test to verify it passes**

Run the same targeted pytest command and expect one passing test.

### Task 2: 24h/48h Smoke Comparisons

**Files:**
- Modify: `src/gb_bess_revenue_stack/phase4/scenarios.py`
- Test: `tests/unit/test_phase4_scenarios_and_workbook.py`

- [ ] **Step 1: Write the failing test**

Add a test for `run_phase4_smoke_window_comparisons(...)` using a two-day stress profile. Assert that the output contains `24h` and `48h` comparisons, with 48 and 96 settlement periods respectively.

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/pytest tests/unit/test_phase4_scenarios_and_workbook.py::test_phase4_smoke_window_comparisons_include_24h_and_48h_windows -q`

Expected: import failure because `run_phase4_smoke_window_comparisons` does not exist.

- [ ] **Step 3: Implement the minimal code**

Add `Phase4SmokeWindowComparison`, slice the price and EAC matrices to the requested day counts, run the rolling policy for each window, and attach capture comparison output.

- [ ] **Step 4: Run test to verify it passes**

Run the same targeted pytest command and expect one passing test.

### Task 3: Dashboard Cache Writer

**Files:**
- Create: `src/gb_bess_revenue_stack/reporting/dashboard_cache.py`
- Modify: `src/gb_bess_revenue_stack/reporting/__init__.py`
- Modify: `src/gb_bess_revenue_stack/cli.py`
- Test: `tests/unit/test_phase4_scenarios_and_workbook.py`
- Test: `tests/unit/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Add a dashboard-cache writer test that expects `manifest.json`, `executive_summary.json`, `policy_capture.parquet`, `revenue_stack.parquet`, `scenario_sweeps.parquet`, and `caveats.json`. Add a CLI smoke test that runs `run-phase4-smoke` into temporary run and dashboard directories.

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/pytest tests/unit/test_phase4_scenarios_and_workbook.py::test_phase4_dashboard_cache_writer_outputs_contract_files tests/unit/test_cli.py::test_run_phase4_smoke_writes_dashboard_cache -q`

Expected: import/CLI failure because the writer and CLI option do not exist.

- [ ] **Step 3: Implement the minimal code**

Create `Phase4DashboardCacheInput` and `write_phase4_dashboard_cache(...)`. The writer should emit the required metadata keys from `docs/dashboard_cache_contract.md`, plus compact Parquet tables for policy capture, revenue stack and scenario sweeps.

- [ ] **Step 4: Run tests to verify they pass**

Run the same targeted pytest command and expect two passing tests.

### Task 4: Residential Documentation Reconciliation

**Files:**
- Modify: `docs/phase_4_plan.md`
- Modify: `docs/superpowers/plans/2026-05-19-residential-load-pv-tariff-vpp.md`

- [ ] **Step 1: Update docs**

Change wording that says the residential branch has not modelled interval load/PV/tariff/VPP dispatch. State that the first bill-aware household dispatch slice is now implemented and that the remaining residential work is scenario-depth, interpretation tests and dashboard/report packaging.

- [ ] **Step 2: Run docs/status checks**

Run: `./.venv/bin/pytest tests/unit/test_docs_and_reference.py tests/unit/test_residential_* -q`

Expected: all selected tests pass.

### Task 5: Full Verification And Split Guidance

**Files:**
- No production files unless verification reveals a real issue.

- [ ] **Step 1: Run full verification**

Run:

```bash
./.venv/bin/ruff check .
./.venv/bin/ruff format --check .
./.venv/bin/mypy src --cache-dir /tmp/gb-bess-mypy-cache-phase4-final
./.venv/bin/pytest -q
```

- [ ] **Step 2: Record coherent split guidance**

Summarise the final WIP into reviewable groups: commercial/Phase 4 core, dashboard cache/reporting, residential branch, docs/tests.
