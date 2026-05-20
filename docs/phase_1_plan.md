# Phase 1 Implementation Plan — Foundation, Source Feasibility and Data Platform

**Project:** Open GB BESS Revenue-Stack Optimiser  
**Repository:** `gb-bess-revenue-stack`  
**Canonical package:** `src/gb_bess_revenue_stack/`  
**Public product name:** OpenBESS

---

## 1. Phase objective

Create the engineering and data foundation for the whole product. Phase 1 prevents wrong market assumptions, licence mistakes, timestamp leakage, schema drift and undocumented numerical parameters from entering the model.

Phase 1 is complete only when:

- source feasibility has been verified;
- canonical schemas include event/known/retrieval metadata;
- sample public data can be fetched, validated and cached;
- every processed dataset has a manifest;
- later phases can consume data without hitting live APIs.

---

## 2. Release outputs

Build:

- `pyproject.toml` with dependency groups and quality tooling;
- `src/gb_bess_revenue_stack/config/` for Pydantic settings;
- `src/gb_bess_revenue_stack/schemas/` for canonical data contracts;
- `src/gb_bess_revenue_stack/data/` for source clients, cache and manifests;
- `docs/source_registry.yaml`;
- `docs/data_sources.md`;
- `docs/source_research_notes.md`;
- `docs/implementation_conventions.md`;
- `docs/assumptions_ledger.md`;
- `docs/model_boundaries.md`;
- `docs/phase_reviews/p1_00_source_feasibility.md`;
- tiny committed fixture datasets under `tests/fixtures/` or `data/reference/`;
- network-free unit tests and marked integration smoke tests;
- CI for lint, type check, unit tests and import smoke tests.

---

## 3. P1-00 source/licence/data feasibility gate

Do this before production client implementation.

### 3.1 Verify Elexon wholesale proxy source

Research anchor from Firecrawl: Elexon/BMRS `Market Index Data (MID) price time series`, endpoint `/balancing/pricing/market-index`.

Check:

- exact endpoint URL and dataset name: `ELEXON_BMRS_MID` unless P1-00 changes it;
- data providers available and selected, especially `N2EXMIDP` and `APXMIDP`;
- fields returned, expected to include `startTime`, `dataProvider`, `settlementDate`, `settlementPeriod`, `price`, and `volume`;
- units, especially `price` in £/MWh and volume unit from docs/sample response;
- timezone/timestamp fields and RFC3339 query formatting;
- query limits, pagination and rate limits;
- whether CSV/JSON is available;
- public-use caveats;
- whether data is MID/market-index proxy rather than day-ahead auction price or imbalance trading strategy.

Acceptance:

- `docs/source_registry.yaml` has an Elexon wholesale-proxy source entry;
- `docs/data_sources.md` states what the price source is and is not;
- sample fetch proves field names and units.

### 3.2 Verify NESO EAC source

Research anchors:

- NESO Data Portal EAC auction results page states DC/DM/DR response services and BR/QR/SR reserve services are procured via EAC; daily results are published; `deliveryStart`/`deliveryEnd` are UTC; rights are NESO Open Data Licence; update frequency is daily.
- NESO EAC sandbox API guide states Quick Reserve uses 30-minute service windows while Frequency Response services use longer windows, e.g. EFA blocks, and that validations include unit capacities, price limits, volume limits, basket limits and splitting.

Check:

- file, CKAN/datapackage, datastore or API access method;
- exact resource IDs and whether latest daily files or archive files are used;
- delivery start/end fields and UTC convention;
- publication/known time if present;
- product labels, including whether central Release 1 uses only DC/DM/DR or also source-gated BR/QR/SR;
- direction labels and high/low/up/down mapping;
- clearing-price units and whether source is per MW/h, per service window, or another basis;
- procured/accepted volume fields if present;
- service-window granularity by product: do not assume one block length for all products;
- data volume and file format;
- licence and reuse caveats.

Acceptance:

- EAC source entry exists;
- unknown product and direction labels are documented;
- block/commitment structure is either verified or explicitly marked unknown for conservative modelling.

### 3.3 Verify Capacity Market sources

Research anchor from Modo's 12 August 2024 article for the 2024/25 auction cycle: 2h BESS derating is reported as 27.15% in T-1 and 20.94% in T-4. Treat these as example anchors, not timeless constants.

Check:

- official clearing-price source by auction/delivery year;
- official derating-factor source by storage duration, auction and delivery year;
- whether the selected source is official NESO/Delivery Body guidance/workbook or a secondary research article;
- public reuse permissions;
- whether assumptions are central, high, low, historical scenario anchors, or diagnostic no-derating cases.

Acceptance:

- CM scenario examples have source URL, auction type, delivery year and duration.

### 3.4 Verify benchmark anchor sources

Check:

- public Modo methodology and public revenue anchors;
- whether numeric anchors can be extracted manually or programmatically;
- reuse/citation constraints;
- methodology date/version.

Acceptance:

- benchmark anchors are treated as public observations with caveats, not test targets.

### 3.5 Gate decision

Write `docs/phase_reviews/p1_00_source_feasibility.md` with:

- source verified;
- source failed;
- modelling implication;
- fallback decision;
- whether Phase 1 client build may proceed.

---

## 4. Repository and tooling setup

Use:

- Python 3.11 or 3.12;
- `uv` for dependency locking;
- `ruff` for lint/format;
- `mypy` or `pyright` for types;
- `pytest` and `hypothesis`;
- `pydantic` and `pydantic-settings`;
- `pandas`, `pyarrow`, `numpy`;
- `httpx` or `requests` with `tenacity`;
- `pyomo` and `highspy` for later phases;
- `streamlit` and `plotly` in optional dashboard group.

Quality gates:

- no local paths in committed config;
- no secrets;
- all network calls have timeouts;
- all retries are bounded;
- no production logic in notebooks;
- every module crossing package boundaries is typed.

---

## 5. Implementation conventions document

Create `docs/implementation_conventions.md` before Phase 2 coding. It must define:

- currency and energy units: £, £/MWh, £/MW/h, £/kW/year, MW, MWh and MW × hours;
- Elexon MID source convention: `ELEXON_BMRS_MID`, provider labels, proxy caveat and `price_gbp_per_mwh` mapping;
- EAC price-unit conversion rules and distinction between availability revenue and utilisation/activation energy;
- Capacity Market convention: £/kW/year clearing price, nameplate MW, derated MW, real/nominal treatment and `cm_derating_factor` source;
- AC/DC convention: market variables are delivered/imported AC MW unless explicitly stated; SoC is internal stored MWh;
- charge/discharge sign convention and net-export sign;
- UTC-first timestamp handling, local time only for display;
- settlement-period mapping, including daylight-saving days with 46/50 periods;
- interval convention: `delivery_start_utc` inclusive and `delivery_end_utc` exclusive;
- rolling decision-time and known-time rule: no input with `known_at_utc > decision_time_utc`;
- default rolling terminal SoC policy and diagnostic-only free terminal rule;
- solver defaults, time limits, gap tolerances and runtime budget targets.

---

## 6. Canonical schemas

Create schemas before clients.

### 6.1 Common provenance fields

Every canonical record type should include:

- `event_time_utc` where point-in-time;
- `delivery_start_utc` / `delivery_end_utc` where interval-based;
- `known_at_utc` or `publication_time_utc`;
- `retrieved_at_utc`;
- `source_id`;
- `source_url` or source file reference;
- `source_record_id` if available;
- `schema_version`;
- `quality_flag`;
- `quality_notes`.

If exact `known_at_utc` is unavailable, set a conservative proxy and store `known_at_policy` in the manifest.

### 6.2 `SettlementPeriodIndex`

Fields:

- `delivery_start_utc`;
- `delivery_end_utc`;
- `timestamp_local` for presentation only;
- `settlement_date`;
- `settlement_period`;
- `duration_hours`;
- common provenance fields.

Validation:

- UTC timestamps must be timezone-aware;
- duration must be positive;
- duplicate periods fail validation;
- missing periods are reported, not silently filled;
- March and October daylight-saving transitions have tests.

### 6.3 `WholesalePricePoint`

Fields:

- settlement index fields;
- `price_gbp_per_mwh`;
- `price_source_type`: `MID`, `EPEX_LICENSED`, `N2EX_LICENSED`, `SYNTHETIC_TEST`, or controlled extension;
- `is_proxy`;
- common provenance fields.

Validation:

- negative prices are valid;
- missing prices are explicit;
- `MID` implies `is_proxy=True`;
- source labels must appear in chart/report metadata.

### 6.4 `EACAuctionResult`

Fields:

- `product_source_label`;
- `product_model_label`;
- `direction_source_label`;
- `direction_model_label`: `upward`, `downward`, `both`, `unknown`;
- `delivery_start_utc`;
- `delivery_end_utc`;
- `known_at_utc` or `publication_time_utc`;
- `clearing_price_gbp_per_mw_h`;
- `procured_mw` if present;
- `accepted_mw` if present;
- `block_id` if verified;
- common provenance fields.

Validation:

- delivery end must exceed start;
- product and direction mappings are versioned;
- unknown labels fail central release validation unless explicitly quarantined;
- zero/negative prices are preserved;
- missing product because not procured is distinct from source/API failure.

### 6.5 `CapacityMarketScenario`

Fields:

- `scenario_name`;
- `auction_type`;
- `delivery_year`;
- `clearing_price_gbp_per_kw_year`;
- `derating_factor`;
- `asset_duration_hours`;
- `contracted_mw_nameplate`;
- `contracted_mw_derated`;
- `source_id`;
- `source_url`;
- `source_date`;
- `notes`.

Validation:

- derating factor in `[0, 1]`;
- derated MW equals nameplate times derating unless explicitly overridden;
- CM revenue is annual, not per settlement period.

---

## 7. Data architecture

### 7.1 Raw data

Raw downloads go to:

```text
data/raw/{source_id}/{dataset}/{retrieval_date}/{hash}.{json|csv|xlsx}
```

Raw data is gitignored and immutable.

### 7.2 Processed data

Processed Parquet goes to:

```text
data/processed/{dataset}/{schema_version}/{start_date}_{end_date}.parquet
```

Processed data is gitignored except tiny fixtures.

### 7.3 Reference data

Small stable references go to:

```text
data/reference/
```

Examples:

- service duration map;
- sample CM scenarios;
- benchmark anchor examples;
- toy prices for tests.

### 7.4 Manifests

Every processed dataset has a manifest with:

- dataset;
- schema version;
- source IDs;
- source URLs/files;
- retrieved time;
- period coverage;
- row count;
- missing period count;
- duplicate count;
- timezone convention;
- data hash;
- transformation version;
- known-at policy;
- validation status.

---

## 8. Implementation work packages

### P1-00: Source feasibility gate

Tasks:

- verify Elexon, EAC, CM and benchmark sources, using `docs/source_research_notes.md` as starting evidence;
- record licence/reuse caveats;
- fetch tiny samples manually or with throwaway scripts;
- write feasibility review.

Acceptance:

- no production data client work begins until gate review exists.

### P1-01: Repository bootstrap

Tasks:

- create `src/gb_bess_revenue_stack/` layout;
- add `pyproject.toml`, lockfile, `.gitignore`, `.env.example`;
- add `Makefile` or `justfile`;
- add CI.

Acceptance:

- fresh install and `pytest -m unit` works;
- no secrets or local paths committed.

### P1-02: Configuration layer

Tasks:

- implement `RunConfig`, `AssetConfig`, `DataConfig`, `SolverConfig`, `MarketConfig`;
- load YAML plus environment overrides;
- validate units and value ranges;
- serialise config to run manifest.

Acceptance:

- invalid config fails loudly;
- numerical assumptions are visible.

### P1-03: Source registry and assumptions ledger

Tasks:

- create `docs/source_registry.yaml`;
- create `docs/source_research_notes.md`;
- create `docs/implementation_conventions.md`;
- create `docs/assumptions_ledger.md`;
- reference source IDs from assumptions.

Acceptance:

- every Phase 2/3 parameter has source, unit, caveat and sensitivity range or is labelled placeholder.

### P1-04: Elexon data client

Tasks:

- implement bounded HTTP client;
- fetch wholesale proxy sample;
- cache raw and processed data separately;
- write manifest.

Acceptance:

- mocked tests cover success, timeout, API error, schema drift;
- marked integration test fetches tiny range.

### P1-05: NESO EAC data client

Tasks:

- ingest verified EAC source format;
- parse into canonical schema;
- preserve source labels;
- classify missing/not-procured/source-gap cases.

Acceptance:

- sample EAC data parses;
- timestamps remain UTC;
- unknown labels are quarantined or fail as configured.

### P1-06: Validation and quality reports

Tasks:

- missing/duplicate checks;
- timestamp monotonicity;
- DST checks;
- outlier review;
- schema version checks;
- data quality report generation.

Acceptance:

- deliberately corrupted fixtures fail validation;
- negative prices are retained.

---

## 9. Required tests

- config validation tests;
- schema validation tests;
- common provenance-field presence tests;
- mocked HTTP tests;
- cache round-trip tests;
- manifest generation tests;
- DST transition tests;
- missing versus unavailable classification tests;
- source registry references resolve from assumptions ledger.

---

## 10. Phase completion checklist

Phase 1 is complete when:

- P1-00 feasibility review exists;
- `docs/implementation_conventions.md` exists and covers units/time/sign/AC-DC/terminal/solver conventions;
- source research notes have been converted into `docs/source_research_notes.md` with live-source verification status;
- repository installs from scratch;
- CI passes;
- sample Elexon and EAC data can be fetched and cached;
- processed data has manifests;
- quality reports exist;
- assumptions ledger is populated for Phase 2 and Phase 3;
- no production logic lives in notebooks;
- `docs/phase_reviews/phase_1_review.md` is written.

---

## 11. Handoff to Phase 2

Phase 2 may start when it can consume a canonical `WholesalePricePoint` dataset with:

- UTC interval timestamps;
- explicit duration hours;
- price source labelled proxy/licensed;
- `known_at_utc`/known-at policy present;
- no duplicate periods;
- explicit missing-period handling;
- manifest attached.
