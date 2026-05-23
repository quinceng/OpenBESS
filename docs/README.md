# Project Documentation Index

This directory contains public methodology, assumptions, source-boundary,
release and process-evidence documentation for OpenBESS.

For headline dashboard review, use
`results/dashboard/release_trailing_12m_historical`. The
`results/dashboard/release_90d_historical` cache is retained only as historical
preview evidence.

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

- `release_notes_v0.1.2.md`: latest tagged Release 1 patch note covering the trailing-12-month cache promotion.
- `../CHANGELOG.md`: current release changes and follow-on unreleased notes.
- `finance_boundaries.md`: finance scenario inclusions, exclusions and required caveat wording.
- `known_limitations.md`: durable limitations that must stay visible in methodology, dashboard and README.
- `reproducibility.md`: intended reproducibility workflow for a clean clone.
- `dashboard_cache_contract.md`: required shape and metadata for cached dashboard artefacts.
- `release_checklist.md`: checklist used before publishing Release 1 artefacts.
- `quality_gates.md`: source, optimisation, no-leakage, finance and dashboard release gates.
- `validation_memo.md`: definition of validation, reconciliation and non-claim wording.

## Process docs

- `adr/README.md`: architecture-decision-record guidance.
- `product_plan.md`: compact public product plan and Release 1 scope boundary.
- `source_research_notes.md`: research anchors that preceded the Phase 1 source gate.
- `phase_reviews/`: public gate reviews for source feasibility and completed phases.

Detailed phase implementation plans such as `docs/phase_1_plan.md`, extended
product-plan drafts such as `docs/product_plan_full.md`, and positioning notes
such as `docs/strategic_positioning.md` remain local working notes unless they
are deliberately rewritten as stable public process evidence. Phase reviews are
the public process record.

## Maintenance rule

When implementation decisions change, update the relevant doc in this directory in the same change as the code/config change. The assumptions ledger and source registry should be treated as first-class project artefacts, not after-the-fact report material.
