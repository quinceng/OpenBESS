# Project Documentation Index

This directory contains public methodology, assumptions, source-boundary and
release documentation for OpenBESS.

For headline dashboard review, use
`results/dashboard/release_trailing_12m_historical`. The
`results/dashboard/release_90d_historical` cache is retained only as historical
preview evidence.

## Core docs

- `openbess_reference_revenue_stack.md`: public methodology and naming/caveat contract for the reference stack.
- `implementation_conventions.md`: public units, time, sign, AC/DC, settlement-period, solver and run-manifest conventions.
- `model_boundaries.md`: what each market/model module does and does not claim.
- `service_boundary_ledger.md`: concise public table of EAC, CM and excluded service-boundary treatments.
- `assumptions_ledger.md`: initial assumption register with source, unit, caveat, sensitivity and verification status.
- `source_registry.yaml`: machine-readable source registry seed.
- `data_sources.md`: human-readable source notes.
- `commercial_bess_assumptions.md`: commercial capex, export-limit and route-to-market assumptions.
- `residential_bess_assumptions.md`: separate residential branch boundary, household BESS defaults and payback calculator assumptions.
- `residential_public_data_sources.md`: public/free UK and London residential source registry and reference household assumptions.

## Release docs

- `release_notes_v0.1.2.md`: latest tagged Release 1 patch note covering the trailing-12-month cache promotion.
- `../CHANGELOG.md`: current release changes and follow-on unreleased notes.
- `finance_boundaries.md`: finance scenario inclusions, exclusions and required caveat wording.
- `known_limitations.md`: durable limitations that must stay visible in methodology, dashboard and README.
- `reproducibility.md`: intended reproducibility workflow for a clean clone.
- `dashboard_cache_contract.md`: required shape and metadata for cached dashboard artefacts.

## Local-only docs

Internal planning, research-question notes, literature notes, phase plans,
phase reviews, source-research notes, validation memos, release checklists and
quality-gate working files are intentionally kept local and ignored by git. The
public research question is stated in the top-level README instead of being
published as a separate internal note.

## Maintenance rule

When implementation decisions change, update the relevant doc in this directory in the same change as the code/config change. The assumptions ledger and source registry should be treated as first-class project artefacts, not after-the-fact report material.
