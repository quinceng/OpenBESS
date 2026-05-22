# Source Research Notes

These notes summarise the research anchors used to shape the plan. They are not a substitute for the Phase 1 P1-00 feasibility gate.

## 1. Elexon BMRS Market Index Data

Research anchor:

```text
https://bmrs.elexon.co.uk/api-documentation/endpoint/balancing/pricing/market-index
```

Findings to verify in Phase 1:

- endpoint path: `/balancing/pricing/market-index`;
- providers include `N2EXMIDP` and `APXMIDP`;
- expected fields include `startTime`, `dataProvider`, `settlementDate`, `settlementPeriod`, `price` and `volume`;
- query parameters include date range, settlement-period filters, data providers and format.

Implementation implication:

- central source ID is `ELEXON_BMRS_MID`;
- label as Market Index Data wholesale proxy;
- do not describe as licensed day-ahead or intraday execution price.

## 2. NESO EAC Auction Results

Research anchor:

```text
https://www.neso.energy/data-portal/eac-auction-results
```

Findings to verify in Phase 1:

- daily auction results are published;
- response services DC, DM and DR are expected central candidates;
- reserve services BR, QR and SR are source-gated optional candidates;
- date-time fields such as delivery start/end are expected to be UTC;
- rights are expected to use NESO Open Data Licence;
- data portal exposes downloadable resources and API/resource URLs.

Implementation implication:

- ingest through a stable resource/API method rather than manual scraping where possible;
- preserve source product and direction labels;
- attach known-time or conservative known-time policy;
- classify product-not-procured separately from source gaps.

## 3. EAC Service Windows and Co-Optimised Baskets

Research anchor:

```text
https://sandbox.eac.neso.production.n-side.com/docs/market-participant/api/baskets/creating-co-optimised-baskets
```

Findings to verify in Phase 1:

- Quick Reserve uses 30-minute windows in the sandbox guide;
- frequency response services use longer windows such as EFA blocks in the sandbox guide;
- validations include unit capacities, price limits, volume limits, basket limits and splitting.

Implementation implication:

- do not assume one service-window length for all products;
- encode verified product duration/block rules in reference data;
- avoid full auction-clearing claims.

## 4. Frequency Response Gate Timing

Research anchor:

```text
https://www.neso.energy/document/321111/download
```

Findings to verify in Phase 1:

- cited SFFR report uses six EFA blocks;
- gate opens 14 days before service day;
- gate closes at 11:00 on the EFA day immediately preceding service day;
- auction results time is no later than 17:00 in the cited report.

Implementation implication:

- treat these as guardrails, not universal EAC rules;
- verify selected product timing before using it for no-leakage rolling policy;
- if exact publication time is unavailable, use a conservative documented proxy.

## 5. Capacity Market Derating Anchors

Research anchor:

```text
https://modoenergy.com/research/en/gb-capacity-market-2025-bess-derating-factors-confirmed-target-capacity
```

Findings to verify in Phase 1:

- the cited 2024/25 article reports 2h BESS derating of 27.15 percent in T-1;
- the cited 2024/25 article reports 2h BESS derating of 20.94 percent in T-4;
- T-1 and T-4 delivery years differ.

Implementation implication:

- CM revenue must use duration-, auction- and delivery-year-specific derating;
- Modo values are research anchors, not timeless defaults;
- central config should prefer official Delivery Body or other official source values.

## 6. Before Coding

P1-00 must confirm:

1. exact BMRS MID endpoint, provider choice, schema, rate limits and licence stance;
2. exact NESO EAC resource IDs, field names, product labels, UTC fields and known-time policy;
3. exact CM clearing price and derating sources for selected delivery years;
4. whether EAC block, stacking and procurement-cap constraints are publicly supportable;
5. which researched values become defaults, sensitivities or excluded assumptions.
