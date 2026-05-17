# Architecture Decision Records

Use ADRs for decisions that materially affect reproducibility, modelling claims or long-term structure.

## When to Write an ADR

Write an ADR when deciding:

- source replacement or exclusion;
- solver stack;
- schema changes;
- EAC product inclusion;
- known-at policy;
- terminal SoC policy;
- finance boundary changes;
- dashboard cache schema;
- stochastic extension entry decision.

Do not write ADRs for routine implementation details.

## Filename Format

```text
0001-short-decision-name.md
0002-next-decision.md
```

## Template

```markdown
# ADR N: Decision Title

## Status

Accepted, superseded, or proposed.

## Context

What decision is needed and why it matters.

## Decision

The chosen option.

## Alternatives Considered

- Alternative:

## Consequences

- Positive:
- Negative:
- Follow-up:

## Source and Assumption Links

- Source IDs:
- Assumption IDs:
```
