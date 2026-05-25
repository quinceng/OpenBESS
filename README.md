# OpenBESS

[![CI](https://github.com/quinceng/OpenBESS/actions/workflows/ci.yml/badge.svg)](https://github.com/quinceng/OpenBESS/actions/workflows/ci.yml)

OpenBESS is a transparent public-data research model for Great Britain battery
energy storage revenue stacks. It combines Elexon BMRS Market Index Data as a
wholesale proxy, NESO EAC price-taking availability value, Capacity Market
scenario sidecars, degradation adjustments and no-leakage rolling policy
evaluation.

It is designed for technical review: assumptions are written down, source
snapshots are labelled, dashboard outputs are cached, and the default test suite
runs without live network calls. It is not trading software, investment advice,
a bankability model, an official market index or a proprietary benchmark
replication.

Release evidence and generated outputs live in the release notes and
reproducibility docs, not in this README.

## Author

OpenBESS is authored and maintained by Quincy Ng (`quinceng`).

## Contribution

OpenBESS contributes an open, auditable baseline for analysing Great Britain
battery energy storage revenue stacks from public data. For energy-industry
readers, it makes source provenance, modelling assumptions and known-at-time
policy handling inspectable so methods can be compared against a shared open
reference rather than only against undisclosed internal models.

For research, education and commercial analysis, OpenBESS provides a
reproducible starting point for studying storage economics, data governance,
dispatch constraints and scenario comparison. Its purpose is to improve technical
transparency and comparability; it is not a substitute for site-specific
commercial due diligence, procurement advice, financing analysis or trading
operations.

## Research Question

OpenBESS asks:

```text
How much perfect-foresight value is lost under auditable public-data rolling
policies for a reference GB BESS, and how much of that loss is attributable to
forecast error versus market-boundary exclusions?
```

The falsifiable quantity is the difference between public-boundary
perfect-foresight revenue and realised public-data rolling-policy revenue. Each
released cache should report that gap as both GBP and capture ratio. Claims about
forecast error or market-boundary exclusions require explicit public diagnostics;
otherwise those gaps remain labelled limitations rather than proven causes.

## What The Model Does

OpenBESS models a reference GB BESS against a deliberately narrow public-data
stack:

1. Elexon BMRS MID wholesale proxy value.
2. NESO EAC price-taking availability value.
3. Capacity Market annual scenario value.
4. Throughput-based degradation adjustment.

It compares perfect-foresight dispatch with rolling policies that only use data
known at the decision time:

```text
known_at_utc <= decision_time_utc
```

The rolling policy evidence is intentionally auditable rather than operational
or decision-grade.
Release notes and methodology docs describe the forecast baselines and
supplementary diagnostics for each published cache.

## OpenBESS Reference Revenue Stack

The OpenBESS Reference Revenue Stack is a reference view of Great Britain battery revenue
components computed from public-source cache files. It is published as an open
methodology and reproducible artefact for technical comparison, not as an
official market index, a tradable benchmark or a replication of any proprietary
index.

The label identifies the cache family and coverage gate that produced an
artefact; it is not a claim of persistent multi-year market performance.

The reference stack is intentionally cautious. Short data samples stay labelled as
preview evidence. Annualised summary figures and public benchmark anchor
comparisons remain caveated because they are scenario comparisons, not
proprietary benchmark replication or bankability analysis.

OpenBESS is intended for analysts, researchers, students and engineering teams
who want a documented public-data starting point for GB BESS revenue analysis.
It is not intended to inform investment, financing, procurement or trading
decisions.

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

It includes a cache-backed Streamlit dashboard. Streamlit is a Python tool for
building simple data applications. Cache backed means the dashboard reads saved
files rather than calling live data sources or solving models when the page
loads.

## Related Branch Modules

The repository also contains residential and commercial branch modules. These
are separate from the central OpenBESS reference asset story. Residential
examples cover household bill simulation, illustrative payback calculations and
named sensitivity runs; commercial examples cover site/export-limit assumptions
and related scenario fixtures.

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

These commands run the central network-free examples.

```bash
uv run gb-bess run-smoke
uv run gb-bess run-rolling-smoke
uv run gb-bess run-market-stack-smoke
```

Related branch examples are also network-free.

```bash
uv run gb-bess run-residential-scenario-sweep
```

## Dashboard

Optional local viewer for cached outputs:

```bash
uv run streamlit run dashboard/streamlit_app.py
```

For cache rebuilds or selecting named caches, see `docs/reproducibility.md`.

To fetch a small public NESO EAC sample, run this command.

```bash
uv run gb-bess fetch-data --source NESO_EAC_AUCTION_RESULTS --limit 20
```

## Where To Read Next

Start with `docs/openbess_reference_revenue_stack.md` for the public methodology.
The latest tagged release note is `docs/release_notes_v0.1.2.md`.
`CHANGELOG.md` records current release changes.

Read `docs/methodology.md` for the model equations and known time policy.

Read `docs/source_registry.yaml` for source status and caveats.

Read `docs/model_boundaries.md` and `docs/known_limitations.md` for what the
model deliberately does not claim.

Read `docs/reproducibility.md` for the verification workflow.

## Licence

OpenBESS is released under the Apache License 2.0.
