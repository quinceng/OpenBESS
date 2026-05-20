# OpenBESS

[![CI](https://github.com/quinceng/OpenBESS/actions/workflows/ci.yml/badge.svg)](https://github.com/quinceng/OpenBESS/actions/workflows/ci.yml)

OpenBESS is an open source research project for modelling the value of battery
energy storage in Great Britain. A battery energy storage system is often
called a BESS. It stores electricity when charging and returns electricity to
the grid or a site when discharging.

The project focuses on revenue stacks. A revenue stack is the combined income a
battery could earn from more than one market route. In this repository the main
routes are wholesale price exposure, availability payments for grid services,
Capacity Market scenarios, and simple degradation adjustments.

OpenBESS is designed to be transparent. The assumptions are written down, the
data sources are labelled, and the tests run without live network calls by
default. It is not trading software, investment advice, or a bankability model.

## What The Project Does

OpenBESS builds a public data view of battery value in Great Britain.

It starts with Elexon BMRS Market Index Data. Elexon runs public electricity
market reporting for Great Britain. BMRS means Balancing Mechanism Reporting
Service. Market Index Data is used here as a wholesale proxy, which means it is
a public signal for short term wholesale prices rather than a record of trades
made by this model.

It then adds NESO EAC availability value. NESO is the National Energy System
Operator. EAC means Enduring Auction Capability. In this project the EAC layer
is treated as a price taking availability proxy. That means the model assumes
published auction prices are given and estimates whether a battery could make
capacity available, rather than trying to predict or clear the auction itself.

The project also includes Capacity Market scenarios. The Capacity Market pays
eligible capacity for being available during system stress events. OpenBESS
keeps this as a separate annual scenario so it does not get mixed up with
shorter term wholesale and EAC values.

Finally, the project compares idealised operation with rolling policy results.
A rolling policy is a practical simulation that moves through time step by step
and only uses information that would have been available at that point. This is
used to avoid look ahead bias, which happens when a model accidentally uses
future information.

## OpenBESS Stack Index

The OpenBESS Stack Index is a preview metric for a reference Great Britain
battery. It reports a rolling value view with separate components for wholesale
proxy value, EAC availability value, Capacity Market scenarios, and a
degradation adjusted view.

The index is intentionally cautious. Short data samples are labelled as short
samples. Annualised finance outputs and public benchmark comparisons are held
back until the cache contains enough aligned periods to make those claims more
credible.

## Current Scope

The repository currently includes public source research, source metadata, and
known time handling for Elexon MID, NESO EAC, Capacity Market assumptions, and
public benchmark anchors.

It includes typed schemas for batteries, market data, source records, and
dispatch results. A schema is a structured definition of what fields a record
must contain and what type each field should have.

It includes optimisation models for energy dispatch and reserve availability.
Optimisation means choosing the best feasible battery schedule under a set of
constraints. Constraints are rules such as power limits, state of charge limits,
and reserve headroom requirements.

It includes a cache backed Streamlit dashboard. Streamlit is a Python tool for
building simple data applications. Cache backed means the dashboard reads saved
files rather than calling live data sources or solving models when the page
loads.

It also includes residential battery examples, including household bill
simulation, payback scenarios, and named sensitivity runs.

## Repository Layout

The package source code lives in `src/gb_bess_revenue_stack/`.

The dashboard lives in `dashboard/`.

Public assumptions and reference asset presets live in `configs/`.

Small public reference tables live in `data/reference/`.

Methodology, assumptions, source boundaries, and release notes live in `docs/`.

Lightweight reproducible smoke output summaries live in `reports/`.

Unit tests and optional live integration tests live in `tests/`.

## Setup

Install the project and its optional development dependencies with uv.

```bash
uv sync --all-extras
```

## Checks

Run these checks before publishing changes.

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Ruff checks code style and common Python mistakes. Mypy checks Python type
hints. Pytest runs the test suite.

Integration tests can call live public services, so they are switched off by
default.

```bash
GB_BESS_RUN_INTEGRATION=1 uv run pytest -m integration
```

## Useful Commands

These commands run the main network free examples.

```bash
uv run gb-bess run-smoke
uv run gb-bess run-rolling-smoke
uv run gb-bess run-market-stack-smoke
uv run gb-bess run-phase4-smoke --finance-assumptions-yaml configs/finance_assumptions.yaml
uv run gb-bess build-phase4-aligned-cache --days 7
uv run gb-bess run-release-cache --aligned-cache-dir results/runs/release_cache/aligned_sources
uv run gb-bess build-stack-series --cache-dir results/dashboard --output-dir results/dashboard
uv run gb-bess run-residential-scenario-sweep
uv run streamlit run dashboard/streamlit_app.py
```

To fetch a small public NESO EAC sample, run this command.

```bash
uv run gb-bess fetch-data --source NESO_EAC_AUCTION_RESULTS --limit 20
```

## Where To Read Next

Start with `docs/openbess_stack_index.md` for the public index methodology.

Read `docs/methodology.md` for the model equations and known time policy.

Read `docs/source_registry.yaml` for source status and caveats.

Read `docs/model_boundaries.md` and `docs/known_limitations.md` for what the
model deliberately does not claim.

Read `docs/reproducibility.md` and `docs/quality_gates.md` for the verification
workflow.

## Licence

OpenBESS is released under the Apache License 2.0.
