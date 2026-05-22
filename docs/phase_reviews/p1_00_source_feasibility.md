# P1-00 Source Feasibility Review

## Gate Decision

Production client build may proceed with caveats.

The Elexon MID and NESO EAC sources are accessible through stable public APIs and have enough schema metadata for Phase 1 clients, fixtures, cache manifests and validation. Capacity Market values are usable for labelled scenario/reference data, but duration-specific storage derating must remain caveated until the implementation selects an official auction-guideline workbook or other official source for the specific auction/delivery year. Public benchmark anchors are deferred to the reconciliation phase and are not test targets.

## Elexon BMRS MID

- Access: verified through `https://data.elexon.co.uk/bmrs/api/v1/balancing/pricing/market-index`.
- Documentation: `https://bmrs.elexon.co.uk/api-documentation/endpoint/balancing/pricing/market-index`.
- Sample: `from=2024-01-01T00:00Z`, `to=2024-01-01T01:00Z`, `format=json` returned HTTP 200.
- Fields: `startTime`, `dataProvider`, `settlementDate`, `settlementPeriod`, `price`, `volume`.
- Providers: `APXMIDP` and `N2EXMIDP` present in the sample response.
- Units: `price` treated as `GBP/MWh`; `volume` is preserved as a source field but is not used by central optimisation.
- Timestamp convention: `startTime` is UTC RFC3339 with `Z`.
- Known-at policy: `delivery_end_utc` conservative proxy until a more precise publication-time rule is justified.
- Licence: Elexon BMRS API terms. Raw production data should remain local; committed fixtures must be tiny.
- Decision: verified for public wholesale-proxy use. It must always be labelled MID/public proxy, not day-ahead execution price.

## NESO EAC Auction Results

- Access: verified through NESO Data Portal CKAN package `eac-auction-results`.
- Dataset page: `https://www.neso.energy/data-portal/eac-auction-results`.
- Package API: `https://api.neso.energy/api/3/action/package_show?id=eac-auction-results`.
- Selected resource: `NESO Response-Reserve Results Summary`, resource ID `596f29ac-0387-4ba4-a6d3-95c243140707`.
- Supplementary resource: `NESO Response-Reserve Results By Unit`, resource ID `a63ab354-7e68-44c2-ad96-c6f920c30e85`.
- Fields: `auctionID`, `auctionProduct`, `serviceType`, `deliveryStart`, `deliveryEnd`, `clearedVolume`, `clearingPrice`, `linkedServiceWindowID`.
- Product labels: `DCH`, `DCL`, `DMH`, `DML`, `DRH`, `DRL`, `NQR`, `NSR`, `PQR`, `PSR`.
- Direction mapping: derived conservatively from product label prefixes/suffixes and stored in code; unknown labels are quarantined.
- Units: `clearingPrice` metadata says `GBP/MW/h`; `clearedVolume` metadata says `MW`.
- Timestamp convention: source metadata states UTC; CSV values may omit trailing `Z`, so parser normalises source timestamps to UTC.
- Known-at policy: source records do not include publication time; Phase 1 uses `delivery_start_utc` as a conservative proxy. Phase 4 must revisit this if modelling pre-auction commitment decisions.
- Licence: NESO Open Data Licence.
- Rate-limit caveat: NESO API guidance recommends CKAN requests at no more than 1 request per second and datastore requests at no more than 2 per minute.
- Decision: verified for a price-taking EAC availability dataset with publication-time caveat.

## Capacity Market

- Auction parameters: verified from GOV.UK final auction parameters for T-1 delivery 2025/26 and T-4 delivery 2028/29.
- Licence: GOV.UK page is under Open Government Licence v3.0 unless otherwise stated.
- Clearing price anchor: the 2024 T-4 Delivery Year 2028/29 Auction Monitor Report states a clearing price of `GBP60.00/kW/year` and aggregate capacity agreements of `43055.073 MW`.
- Derating source: official duration-specific storage derating remains a caveat for central CM scenarios. The repository includes research-anchor 2h BESS derating values from Modo only as labelled reference scenarios.
- Decision: usable with caveat. CM must remain annual scenario revenue and must not alter central dispatch.

## Public Benchmarks

- Candidate anchors: public Modo or similar battery revenue publications, selected during Phase 5 reconciliation.
- Reuse caveats: verify URL, publication date, methodology note and reuse/citation constraints per anchor.
- Decision: usable only as reconciliation context. Benchmark values are not unit-test targets.

## Fallbacks

- If Elexon MID terms, availability or provider coverage become unsuitable, replace the wholesale source only after updating `source_registry.yaml`, `data_sources.md`, assumptions ledger and fixtures.
- If NESO EAC publication time cannot be verified, rolling EAC policies must use the conservative known-at policy or restrict claims to ex-post availability analysis.
- If official duration-specific CM derating cannot be sourced for the selected auction year, CM scenarios stay labelled sensitivity/reference outputs.
