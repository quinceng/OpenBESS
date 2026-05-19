# Dashboard And Phase 5 Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build a cached Streamlit dashboard that reads only `results/dashboard/*`, then extend the cache with Phase 5 degradation, finance and benchmark reconciliation artefacts.

**Architecture:** Keep dashboard reading in `dashboard/cache_reader.py` with no imports from `gb_bess_revenue_stack` production modules, solver libraries or source clients. Keep Streamlit rendering in `dashboard/streamlit_app.py`. Keep Phase 5 cache construction in `gb_bess_revenue_stack.reporting.dashboard_cache` so the CLI can write richer cache files while the dashboard remains read-only.

**Tech Stack:** Python 3.12, pandas/pyarrow for cached Parquet files, Streamlit for the UI, pytest/ruff/mypy for verification.

---

### Task 1: Cached Dashboard Reader And UI

**Files:**
- Create: `dashboard/cache_reader.py`
- Create: `dashboard/streamlit_app.py`
- Test: `tests/unit/test_dashboard_cache_reader.py`

- [x] **Step 1: Write failing tests**

Add tests that import the dashboard module, load a minimal cache fixture, raise a clear `DashboardCacheError` for missing files, and block imports of `pyomo`, `highspy`, `httpx`, `tenacity`, `gb_bess_revenue_stack.data`, `gb_bess_revenue_stack.optimisation` and `gb_bess_revenue_stack.phase4` during dashboard import.

- [x] **Step 2: Verify RED**

Run:

```bash
./.venv/bin/pytest tests/unit/test_dashboard_cache_reader.py -q
```

Expected: fail because `dashboard/cache_reader.py` and `dashboard/streamlit_app.py` do not exist.

- [x] **Step 3: Implement reader and UI**

Create a reader that loads `manifest.json`, `executive_summary.json`, `policy_capture.parquet`, `revenue_stack.parquet`, `scenario_sweeps.parquet` and `caveats.json`. The UI should display capture ratio, revenue stack split, 24h/48h comparisons, scenario table, caveats and source labels.

- [x] **Step 4: Verify GREEN**

Run the targeted dashboard tests and ensure they pass.

### Task 2: Phase 5 Cache Artefacts

**Files:**
- Modify: `src/gb_bess_revenue_stack/reporting/dashboard_cache.py`
- Modify: `src/gb_bess_revenue_stack/cli.py`
- Test: `tests/unit/test_phase5_dashboard_cache.py`

- [x] **Step 1: Write failing tests**

Add tests that expect `degradation_summary.json`, `finance_summary.json`, `finance_cashflows.parquet` and `benchmark_reconciliation.json` after writing a Phase 4 dashboard cache.

- [x] **Step 2: Verify RED**

Run:

```bash
./.venv/bin/pytest tests/unit/test_phase5_dashboard_cache.py -q
```

Expected: fail because those Phase 5 cache files are not written yet.

- [x] **Step 3: Implement minimal Phase 5 calculations**

Compute throughput from rolling run steps, a simple degradation proxy, illustrative 15-year finance cashflows, NPV/payback, and a benchmark reconciliation scorecard with caveat labels. Label all finance as scenario appraisal, not bankability.

- [x] **Step 4: Verify GREEN**

Run the targeted Phase 5 tests and ensure they pass.

### Task 3: Docs, Release Tracking And Verification

**Files:**
- Modify: `docs/dashboard_cache_contract.md`
- Modify: `docs/phase_4_plan.md`
- Modify: `docs/release_checklist.md`
- Modify: `docs/reproducibility.md`

- [x] **Step 1: Update docs**

Document the dashboard command, cached-only boundary, Phase 5 cache files and remaining lower-priority work: aligned historical sample, residential scenario depth and release hardening.

- [x] **Step 2: Full verification**

Run:

```bash
./.venv/bin/ruff check .
./.venv/bin/ruff format --check .
./.venv/bin/mypy src --cache-dir /tmp/gb-bess-mypy-cache-dashboard-phase5
./.venv/bin/pytest -q
```

- [x] **Step 3: Commit split**

Commit dashboard reader/UI and Phase 5 cache/docs as separate coherent commits if both slices land cleanly.
