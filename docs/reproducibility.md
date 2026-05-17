# Reproducibility Guide

This guide defines the intended clean-clone workflow for the target repository. Commands may be adjusted during implementation, but the release must preserve the same reproducibility story.

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

Dashboard cache should be built separately:

```bash
uv run gb-bess build-dashboard-cache --config configs/dashboard_cache.yaml
```

The dashboard should then run without solver or raw data:

```bash
uv run streamlit run dashboard/streamlit_app.py
```

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
