# OpenBESS

OpenBESS is a public-data research implementation for modelling GB battery
energy storage system revenue stacks. It combines source-aware data ingestion,
optimisation models, rolling-policy evaluation, dashboard-ready artefacts and a
named OpenBESS Stack Index preview.

The project is designed as a transparent portfolio artefact: assumptions are
explicit, source boundaries are documented and tests are network-free by
default. It is not a trading system, bankability model or investment advice.

## What It Models

OpenBESS follows a GB BESS revenue-stack story:

```text
Elexon BMRS MID wholesale proxy
  -> NESO EAC price-taking availability proxy
  -> Capacity Market annual scenario
  -> degradation-adjusted rolling policy view
  -> finance and public-benchmark reconciliation artefacts
```

The current Stack Index work publishes a preview series for cached runs with
component splits for wholesale proxy value, EAC availability value, Capacity
Market scenario placeholders and degradation-adjusted value. Coverage gates make
short samples explicit: annualised finance and benchmark values are suppressed
until the cache has enough aligned periods for a credible public view.

## Implemented Scope

- Source feasibility, source registry and known-time metadata for Elexon MID,
  NESO EAC, Capacity Market and public benchmark anchors.
- Typed battery, market, source and dispatch schemas.
- Energy-only perfect-foresight optimisation and rolling-horizon policy
  evaluation with no-leakage information sets.
- Price-taking EAC availability proxy and separate Capacity Market annual
  scenario layer.
- Rolling wholesale-plus-EAC policy evaluation with historical fixture smoke
  tests and deterministic scenario sweeps.
- Cache-backed Streamlit dashboard that reads generated artefacts without
  importing solvers or live source clients.
- OpenBESS Stack Index preview exports in CSV and Parquet.
- Residential household battery payback, bill-aware dispatch and named scenario
  sweep examples.

## Repository Map

- `src/gb_bess_revenue_stack/` - package source code.
- `dashboard/` - cache-only Streamlit dashboard reader and UI.
- `configs/` - public assumptions and reference asset presets.
- `data/reference/` - small public reference tables.
- `docs/` - methodology, assumptions, source boundaries and release notes.
- `reports/` - lightweight reproducible smoke-output summaries.
- `tests/` - unit and optional live integration tests.

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

## Example Commands

```bash
uv run gb-bess fetch-data --source ELEXON_BMRS_MID --start 2024-01-01T00:00Z --end 2024-01-01T01:00Z
uv run gb-bess fetch-data --source NESO_EAC_AUCTION_RESULTS --limit 20
uv run gb-bess run-smoke
uv run gb-bess run-rolling-smoke
uv run gb-bess run-market-stack-smoke
uv run gb-bess run-phase4-smoke --finance-assumptions-yaml configs/finance_assumptions.yaml
uv run gb-bess build-stack-series --cache-dir results/dashboard --output-dir results/dashboard
uv run gb-bess run-residential-scenario-sweep
uv run streamlit run dashboard/streamlit_app.py
```

## Documentation

Start with:

- `docs/openbess_stack_index.md` for the public index methodology.
- `docs/methodology.md` for model equations and known-at policy.
- `docs/source_registry.yaml` for source status and caveats.
- `docs/model_boundaries.md` and `docs/known_limitations.md` for what the
  model deliberately does not claim.
- `docs/reproducibility.md` and `docs/quality_gates.md` for verification.
