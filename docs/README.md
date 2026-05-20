# Project Documentation Index

This directory contains the durable methodology, assumptions, source-boundary
and release documentation for OpenBESS.

## Core docs

- `implementation_conventions.md`: binding units, time, sign, AC/DC, settlement-period, solver and run-manifest conventions.
- `model_boundaries.md`: what each market/model module does and does not claim.
- `quality_gates.md`: phase gates, data-quality gates, optimisation checks, CI expectations and release checks.
- `assumptions_ledger.md`: initial assumption register with source, unit, caveat, sensitivity and verification status.
- `source_registry.yaml`: machine-readable source registry seed.
- `data_sources.md`: human-readable source notes and Phase 1 verification instructions.
- `source_research_notes.md`: compact research-anchor notes that explain source choices.
- `strategic_positioning.md`: durable product edge and differentiation memory.
- `phase_4_plan.md`: rolling EAC policy and deterministic sweep handoff plan.
- `phase_5_plan.md`: degradation, finance scenario appraisal and benchmark reconciliation handoff plan.
- `commercial_bess_assumptions.md`: commercial capex, export-limit and route-to-market assumptions.
- `residential_bess_assumptions.md`: separate residential branch boundary, household BESS defaults and payback calculator assumptions.
- `residential_public_data_sources.md`: public/free UK and London residential source registry and reference household assumptions.

## Release docs

- `finance_boundaries.md`: finance scenario inclusions, exclusions and required caveat wording.
- `validation_memo.md`: validation and reconciliation standard for this project.
- `known_limitations.md`: durable limitations that must stay visible in methodology, dashboard and README.
- `reproducibility.md`: intended reproducibility workflow for a clean clone.
- `dashboard_cache_contract.md`: required shape and metadata for cached dashboard artefacts.
- `release_checklist.md`: final public-release checklist.

## Process docs

- `phase_reviews/README.md`: required structure for phase review notes.
- `adr/README.md`: architecture-decision-record guidance.

## Maintenance rule

When implementation decisions change, update the relevant doc in this directory in the same change as the code/config change. The assumptions ledger and source registry should be treated as first-class project artefacts, not after-the-fact report material.
