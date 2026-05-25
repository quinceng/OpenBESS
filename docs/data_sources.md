# Data Sources

This document explains the intended source architecture and the Phase 1 verification work required before production clients are built.

## 1. Source Principles

Every source used in central results must have:

- source ID in `source_registry.yaml`;
- access method;
- licence/reuse note;
- field schema;
- unit convention;
- timestamp convention;
- known/publication time policy;
- caveat text;
- fixture sample for tests where practical.

Research notes are starting evidence, not implementation authority. Phase 1 must verify live endpoints and file resources.

## 2. Wholesale Proxy

Intended source:

```text
ELEXON_BMRS_MID
```

Purpose:

- transparent public wholesale-price proxy;
- input to energy-only dispatch and market-stack optimisation;
- possible provider sensitivity between `N2EXMIDP` and `APXMIDP`.

Required Phase 1 checks:

- confirm endpoint path and query parameters;
- confirm provider labels and data coverage;
- confirm price units;
- confirm volume unit or ignore volume with caveat;
- confirm date-range and rate limits;
- confirm licence/citation stance;
- fetch a tiny fixture range.

Required wording:

```text
Elexon BMRS Market Index Data is used as a public short-term wholesale proxy.
It is not labelled as day-ahead auction execution price.
```

## 3. EAC Auction Results

Intended source:

```text
NESO_EAC_AUCTION_RESULTS
```

Purpose:

- EAC price-taking availability proxy;
- product coverage diagnostics;
- product/direction/source-label preservation;
- rolling known-time policy.

Required Phase 1 checks:

- identify exact data portal resource IDs;
- decide latest-file versus archive ingestion;
- confirm UTC delivery fields;
- confirm product labels;
- confirm direction labels;
- confirm clearing-price units;
- convert source prices to GBP/MW/h;
- classify missing product not procured versus source gap;
- verify publication or conservative known-at policy;
- verify whether volume fields can support optional procurement-cap sensitivity.

Central EAC products should be the smallest verified set. If only one product is verified well enough, Release 1 should use one product rather than overclaim a full service suite.

Known-time maintenance rule:

- central rolling EAC policy remains conservative until product-specific
  publication time, auction gate timing and result-release timing are verified;
- at least one central EAC product should be prioritised for verified
  known-time evidence before making stronger EAC contribution or capture claims;
- if product-specific evidence is unavailable, EAC rolling outputs must state the
  conservative known-at policy used and avoid implying pre-auction tradability.

Longer release caches use an aligned Elexon and NESO delivery window. Elexon
MID rows are filtered to one provider and to settlement starts inside the
requested interval. NESO EAC rows are queried by delivery-window overlap and
paginated. Missing EAC cells in release mode are exposed as data-quality
caveats rather than hidden by backfilling.

## 4. EAC Rules and Timing

Intended sources:

```text
NESO_EAC_MARKET_RULES
NESO_FREQ_RESPONSE_MARKET_INFO_2023
```

Purpose:

- product duration;
- delivery-window granularity;
- block commitment;
- gate timing and publication guardrails;
- stacking/exclusivity assumptions.

Implementation rule:

Do not hard-code service duration, block length or gate timing from memory. Store verified values in reference data or config with source IDs.

## 5. Capacity Market

Intended source:

```text
CM_OFFICIAL_AUCTION_PARAMETERS
```

Purpose:

- annual CM scenario revenue;
- duration-specific derating;
- delivery-year scenario labels.

Research anchor:

```text
MODO_CM_DERATING_2024_25_ANCHOR
```

The Modo article values are useful examples but should not be central defaults unless official sources cannot be obtained and the caveat is explicit.

Required Phase 1 checks:

- official clearing price by auction and delivery year;
- official derating factor by duration, auction and delivery year;
- public reuse/citation constraints;
- selected central, low and high scenarios.

## 6. Public Benchmark Anchors

Intended source:

```text
PUBLIC_BENCHMARK_ANCHORS
```

Purpose:

- final reconciliation scorecard;
- public context for why project outputs differ from commercial narratives.

Rules:

- each anchor needs URL, date and methodology note if known;
- unknown commercial treatment must be labelled unknown;
- anchors are not test targets;
- anchors must not be used as forecast inputs unless available at the decision time and explicitly justified.

## 7. Deferred BM Future Research

Potential future source:

```text
ELEXON_BM_OBSERVED_OPTIONAL
```

Release 1 rule:

- no deterministic BM counterfactual revenue in the central optimiser;
- no BM revenue in central results, finance outputs or headline stack series;
- public benchmark differences caused by BM are explained as a boundary, not
  filled with unsupported counterfactuals.

Future research requirements before any BM revenue extension:

- observed BM replay for real units using public BOA/BOD/PN/FPN-style evidence;
- acceptance-probability or bid-stack model with documented feature set and
  source coverage;
- out-of-sample validation against observed acceptances;
- uncertainty bands around any counterfactual revenue estimate;
- explicit separation from central Release 1 revenue until empirically
  validated.

## 8. Raw and Processed Data

Raw data path:

```text
data/raw/{source_id}/{dataset}/{retrieval_date}/{hash}.{json|csv|xlsx}
```

Processed data path:

```text
data/processed/{dataset}/{schema_version}/{start_date}_{end_date}.parquet
```

Raw and processed data are gitignored except tiny fixtures.

## 9. Manifest Requirements

Every processed dataset has a JSON manifest with:

- dataset name;
- schema version;
- source IDs;
- source URLs or files;
- retrieved time;
- period coverage;
- row count;
- duplicate count;
- missing count;
- timezone convention;
- data hash;
- transformation version;
- known-at policy;
- validation status.

## 10. Fixture Strategy

Fixtures should be small and committed only where licence permits.

Minimum fixtures:

- one valid wholesale sample;
- one wholesale sample with negative price;
- one corrupted wholesale sample;
- one EAC sample with known product labels;
- one EAC sample with unknown label for quarantine/failure tests;
- one DST settlement-period fixture;
- one CM scenario fixture.
