# Reproducibility Guide

This guide defines the clean-clone workflow for this repository. Commands may
be adjusted during implementation, but each release must preserve the same
reproducibility story.

## 1. Environment

Target:

- Python 3.11 or 3.12;
- `uv` for dependency management;
- deterministic lockfile committed;
- open-source solver path using HiGHS.

Expected setup:

```bash
uv sync --all-extras
```

## 2. Core Checks

Expected quality checks:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

If pyright is selected instead of mypy, document that in `pyproject.toml` and CI.

## 3. Tiny Smoke Test

Release must include a network-free tiny optimisation:

```bash
uv run gb-bess run-smoke --config configs/smoke_energy_only.yaml
```

The smoke test should:

- use committed fixture data;
- solve in under a few seconds;
- write a run manifest;
- assert objective equals extracted revenue;
- avoid live API calls.

## 4. Source Fetch Workflow

Data fetching should be explicit and separate from solving:

```bash
uv run gb-bess fetch-data --source ELEXON_BMRS_MID --start YYYY-MM-DD --end YYYY-MM-DD
uv run gb-bess fetch-data --source NESO_EAC_AUCTION_RESULTS --start YYYY-MM-DD --end YYYY-MM-DD
```

Fetch commands must:

- use bounded timeouts;
- use bounded retries;
- write immutable raw files;
- write retrieval metadata;
- avoid overwriting raw files silently.

## 5. Processed Data Workflow

Processing should produce Parquet plus manifest:

```bash
uv run gb-bess build-dataset --dataset wholesale_prices --start YYYY-MM-DD --end YYYY-MM-DD
uv run gb-bess build-dataset --dataset eac_auction_results --start YYYY-MM-DD --end YYYY-MM-DD
```

Processed dataset manifests must include source IDs, hashes and known-at policy.

## 6. Baseline Runs

Energy-only perfect foresight:

```bash
uv run gb-bess run-dispatch --config configs/phase2_energy_only.yaml
```

Energy-only rolling slice:

```bash
uv run gb-bess run-rolling --config configs/phase2_5_energy_rolling.yaml
```

Market-stack run:

```bash
uv run gb-bess run-market-stack --config configs/phase3_market_stack.yaml
```

Scenario sweeps:

```bash
uv run gb-bess run-scenarios --config configs/scenarios_policy.yaml
```

## 7. Dashboard Cache

Dashboard cache is built by the network-free Phase 4 smoke command:

```bash
uv run gb-bess run-phase4-smoke
```

Longer release caches use the aligned public-source cache and release runner.
The expanded command path for the canonical trailing-12-month cache appears
below.

`results/dashboard/release_trailing_12m_historical` is the canonical OpenBESS
reference cache when its manifest primary window is `trailing_12m`,
`target_window_eligible` is `true` and `below_trailing_12m_coverage` is absent.
The current cache uses `openbess_canonical_1mw_2mwh` over 17,520 settlement
periods from `2025-05-20T00:00:00Z` to `2026-05-20T00:00:00Z`.
Use this trailing-12-month cache for headline review. The 90-day cache below is
retained as a historical preview artefact only.

For `v0.1.1`, `results/dashboard/release_90d_historical` remains the 90-day
OpenBESS preview reference cache. It uses the same canonical reference asset and
meets the 90-day public annualisation gate, but it carries
`below_trailing_12m_coverage` because the preferred target window is not fully
covered.

The existing `results/dashboard/commercial_trailing_12m` artefact is a generated
commercial branch artefact using `commercial_phase4_3mw_10mwh`. It demonstrates
longer coverage, but it is not the canonical OpenBESS reference asset cache.

The dashboard should then run from cached files without solver, raw data or live
API calls. To inspect the canonical trailing-12-month cache directly, point the
dashboard reader at the cache directory from this checkout:

```bash
GB_BESS_DASHBOARD_CACHE_DIR=results/dashboard/release_trailing_12m_historical uv run streamlit run dashboard/streamlit_app.py
```

PowerShell equivalent:

```powershell
$env:GB_BESS_DASHBOARD_CACHE_DIR="results/dashboard/release_trailing_12m_historical"
uv run streamlit run dashboard/streamlit_app.py
```

`GB_BESS_DASHBOARD_CACHE_DIR` was introduced post-v0.1.1 to select named
dashboard caches. Without it, the dashboard reads `results/dashboard`, which is
useful for the short network-free smoke cache.

The 90-day preview cache can still be inspected explicitly:

```bash
GB_BESS_DASHBOARD_CACHE_DIR=results/dashboard/release_90d_historical uv run streamlit run dashboard/streamlit_app.py
```

Expanded command path:

```bash
uv run gb-bess build-phase4-aligned-cache \
  --start 2025-05-20T00:00:00Z \
  --days 365 \
  --output-dir results/runs/release_cache_trailing_12m_historical/aligned_sources

uv run gb-bess run-release-cache \
  --aligned-cache-dir results/runs/release_cache_trailing_12m_historical/aligned_sources \
  --output-dir results/runs/release_cache_trailing_12m_historical \
  --dashboard-dir results/dashboard/release_trailing_12m_historical \
  --profile trailing12m \
  --target-window-label trailing_12m
```

Treat that as a long-running release job rather than an interactive smoke
command. The cache is publishable only after the manifest gate above passes.

The `trailing12m` profile keeps the required central rolling policy,
perfect-foresight capture comparison, stack-series windows, source snapshot,
assumptions ledger, finance/degradation summaries and dashboard contract files.
It skips supplementary smoke-window comparisons, scenario sweeps,
forecast-error sweeps and forecast-model comparison rows so the full-year gate
can be run as a release job without recomputing every diagnostic table.
The canonical run uses 48 half-hour settlement periods per daily solve, executes
48 periods per step and evaluates 365 daily steps with the previous-day
same-period forecast.

The dashboard imports only the cache reader/UI layer during normal load. Tests
guard against importing source clients or solver modules from the dashboard.

## 8. Expected Artefacts

Canonical output locations:

```text
results/runs/
results/dashboard/
reports/
```

Each run directory should contain:

- result data;
- manifest;
- config snapshot or hash;
- solver diagnostics;
- source manifest references;
- caveat flags.

## 9. Nondeterminism

Sources of nondeterminism must be documented:

- solver tolerances;
- API data revisions;
- source publication corrections;
- scenario perturbation seeds;
- timestamp retrieval time.

Scenario and stochastic extensions must store random seeds.

## 10. Rebuild Claims

The README should distinguish:

- network-free tiny smoke test;
- cached dashboard use;
- manual data refresh;
- full historical rebuild.

Do not imply reviewers must run annual rolling optimisations to inspect the project.
