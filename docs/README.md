# Project Documentation Index

This directory contains public methodology, assumptions, source-boundary and
release documentation for OpenBESS. Local planning, review and release-process
notes can exist in the same working tree, but are ignored from the public repo.

## Core docs

- `implementation_conventions.md`: binding units, time, sign, AC/DC, settlement-period, solver and run-manifest conventions.
- `model_boundaries.md`: what each market/model module does and does not claim.
- `assumptions_ledger.md`: initial assumption register with source, unit, caveat, sensitivity and verification status.
- `source_registry.yaml`: machine-readable source registry seed.
- `data_sources.md`: human-readable source notes.
- `commercial_bess_assumptions.md`: commercial capex, export-limit and route-to-market assumptions.
- `residential_bess_assumptions.md`: separate residential branch boundary, household BESS defaults and payback calculator assumptions.
- `residential_public_data_sources.md`: public/free UK and London residential source registry and reference household assumptions.

## Release docs

- `release_notes_v0.1.1.md`: latest Release 1 patch note covering Phase 6 hardening.
- `finance_boundaries.md`: finance scenario inclusions, exclusions and required caveat wording.
- `known_limitations.md`: durable limitations that must stay visible in methodology, dashboard and README.
- `reproducibility.md`: intended reproducibility workflow for a clean clone.
- `dashboard_cache_contract.md`: required shape and metadata for cached dashboard artefacts.

## Process docs

- `adr/README.md`: architecture-decision-record guidance.

## Maintenance rule

When implementation decisions change, update the relevant doc in this directory in the same change as the code/config change. The assumptions ledger and source registry should be treated as first-class project artefacts, not after-the-fact report material.
