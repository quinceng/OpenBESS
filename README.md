# GB BESS Revenue-Stack Optimiser

This repository contains the Phase 1 foundation for a public-data GB battery revenue-stack optimiser.

Release 1 is a research and portfolio artefact. It uses public sources, explicit source caveats,
known-time metadata and reproducible tests. It is not a commercial trading system or bankability model.

## Phase 1 Scope

- Source feasibility review for Elexon MID, NESO EAC, Capacity Market and public benchmark anchors.
- Typed config and canonical schemas with source, retrieval, quality and known-time metadata.
- Bounded source clients for Elexon MID and NESO EAC summary data.
- Raw cache, processed Parquet writing, dataset manifests and quality reports.
- Network-free unit tests plus optional live integration smoke tests.

## Implemented Modelling Scope

- Phase 2 energy-only perfect-foresight optimiser for a single battery.
- Phase 2.5 rolling-horizon policy wrapper with no-leakage information sets, simple forecast baselines, state carry-forward and capture-ratio reporting.
- Phase 3 price-taking EAC availability proxy and separate Capacity Market annual scenario layer.
- Phase 4 rolling wholesale + EAC policy evaluation, capture-ratio comparison, historical Elexon/NESO smoke sample and deterministic scalar scenario sweeps.
- Cached dashboard reader/UI for `results/dashboard/*` outputs.
- Phase 5 cached degradation proxy, configurable finance scenario appraisal and sourced benchmark reconciliation anchors.
- Residential household payback, dispatch smoke and named scenario sweep examples.

## Setup

```bash
uv sync --all-extras
```

## Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Integration smoke tests are marked and excluded by default:

```bash
GB_BESS_RUN_INTEGRATION=1 uv run pytest -m integration
```

## Source Fetch Examples

```bash
uv run gb-bess fetch-data --source ELEXON_BMRS_MID --start 2024-01-01T00:00Z --end 2024-01-01T01:00Z
uv run gb-bess fetch-data --source NESO_EAC_AUCTION_RESULTS --limit 20
uv run gb-bess run-smoke
uv run gb-bess run-rolling-smoke
uv run gb-bess run-market-stack-smoke
uv run gb-bess run-phase4-smoke
uv run gb-bess run-phase4-smoke --finance-assumptions-yaml configs/finance_assumptions.yaml
uv run gb-bess run-residential-scenario-sweep
uv run streamlit run dashboard/streamlit_app.py
```
