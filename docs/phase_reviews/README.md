# Phase Reviews

Each phase must end with a review note in this directory. A phase is not complete until its review exists.

## Required Files

```text
p1_00_source_feasibility.md
phase_1_review.md
phase_2_review.md
phase_2_5_review.md
phase_3_review.md
phase_4_review.md
phase_5_review.md
phase_6_review.md
phase_7_review.md
```

Only create `phase_7_review.md` if the optional stochastic extension is attempted.

## Review Template

```markdown
# Phase N Review

## Summary

Short statement of what was completed and whether the next phase may proceed.

## Built

- Item built.

## Intentionally Not Built

- Item deferred or excluded.

## Source Assumptions Changed

- Assumption/source update with reference to assumptions ledger ID.

## Tests

- Passing:
- Failing:
- Not run and why:

## Data Quality

- Coverage:
- Missing data:
- Known source issues:

## Modelling Caveats

- Caveat:

## Runtime

- Relevant runtime measurements:

## Gate Decision

Proceed, proceed with caveat, pause, or rescope.

## Scope Moved

- Moved to kill list:
- Moved to Phase 7:
- Moved to future work:
```

## P1-00 Source Feasibility Template

```markdown
# P1-00 Source Feasibility Review

## Gate Decision

State whether production client build may proceed.

## Elexon BMRS MID

- Access:
- Fields:
- Units:
- Timestamp convention:
- Known-at policy:
- Licence:
- Decision:

## NESO EAC Auction Results

- Access:
- Fields:
- Product labels:
- Direction mapping:
- Units:
- Timestamp convention:
- Known-at policy:
- Licence:
- Decision:

## Capacity Market

- Clearing price source:
- Derating source:
- Delivery years:
- Licence:
- Decision:

## Public Benchmarks

- Candidate anchors:
- Reuse caveats:
- Decision:

## Fallbacks

- Fallback source or scope decision:
```
