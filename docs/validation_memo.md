# Validation and Reconciliation Memo

This project uses validation to mean internal correctness, data-quality evidence and transparent reconciliation. It does not mean replication of proprietary commercial models.

## 1. Validation Categories

| Category | Purpose | Example evidence |
|---|---|---|
| Schema validation | Ensure input data shape and units are correct. | Pydantic/pandera checks, corrupt fixtures. |
| Physical validation | Ensure battery constraints are obeyed. | SoC, power, reserve feasibility tests. |
| Economic validation | Ensure objective terms and outputs are dimensionally correct. | Objective equals extracted revenue. |
| Policy validation | Ensure rolling policy is no-leakage and stateful. | Future-marker tests, step records. |
| Reconciliation | Explain divergence from public benchmarks. | Component scorecard and caveat flags. |

## 2. What Counts as a Passing Model

A model output is credible only if:

- source data is traceable;
- data quality checks pass or caveats are explicit;
- units reduce correctly;
- constraints hold within tolerance;
- solver status is acceptable;
- run manifest exists;
- policy information set is auditable;
- caveats match the model boundary.

## 3. What Does Not Count

These are not validation:

- matching a public benchmark by tuning assumptions;
- hiding missing data with zeros;
- comparing perfect foresight against commercial realised revenue as if they were equivalent;
- using future realised data inside a rolling forecast;
- presenting one annualised month as a full market result without annualisation caveat.

## 4. Benchmark Reconciliation Standard

Benchmark rows must include:

- component;
- project treatment;
- benchmark treatment if known;
- expected divergence driver;
- source URL;
- source date;
- methodology note or unknown-method flag;
- confidence label.

Recommended confidence labels:

- `high`: source and divergence mechanism are clear;
- `medium`: source is clear but benchmark method is partial;
- `low`: benchmark method or component definition is uncertain.

## 5. Reconciliation Categories

Minimum categories:

- wholesale price source and execution difference;
- EAC availability proxy versus commercial treatment;
- BM exclusion;
- CM derating and contract/site difference;
- degradation proxy difference;
- availability and outage visibility;
- asset sample and duration difference;
- finance boundary difference.

## 6. Release Wording

Use:

```text
benchmark reconciliation
public benchmark anchor
expected divergence driver
component-level comparison
```

Avoid:

```text
validated against Modo
replicates commercial benchmark
passed benchmark test
commercial-grade forecast
bankable return
```

## 7. Required Tests

Validation and reconciliation code must test:

- benchmark anchors require URL and date unless marked manual note;
- reconciliation output cannot be marked pass/fail replication;
- missing benchmark method is labelled unknown;
- component totals reconcile to project total where applicable;
- benchmark data cannot enter rolling forecasts by default.
