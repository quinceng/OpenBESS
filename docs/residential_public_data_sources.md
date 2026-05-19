# Residential Public Data Sources

The residential branch can now build a reference household from public or
free-to-access data. These defaults are a reproducible fallback. They are not a
claim about a specific home, supplier contract, DNO approval or VPP contract.

## Source Coverage

| Input | Public/free source | Branch treatment |
|---|---|---|
| Annual household load | DESNZ Subnational electricity consumption statistics 2024 | London and Great Britain annual mean and median domestic consumption anchors |
| Half-hour load shape | London Datastore Low Carbon London, UKPN smart meter aggregates, SSEN/Weave aggregate smart meter data, Elexon Profile Class 1/2 profiles | Source registry only; generated fallback profile is flat and explicitly labelled |
| PV generation | European Commission JRC PVGIS | API URL helper using lat/lon, kWp, loss, tilt and azimuth assumptions |
| Retail import tariff | Ofgem April-June 2026 price-cap average and Octopus public tariff API | Flat public-reference import tariff default, overridable by supplier/API data |
| Retail export tariff | Octopus public export tariff page and Ofgem SEG framework | Octopus Outgoing fixed rate default with SEG floor sensitivity |
| VPP/flexibility payments | NESO DFS Winter 2024/25 review and Centre for Sustainable Energy household DFS examples | Low/central/high scenario payments, not guaranteed contract income |
| Export limit | ENA G98/G99/G100 connection rules | Default 3.68 kW single-phase export limit unless site paperwork overrides it |

## London Reference Household

The default London reference household is anchored to the 2024 DESNZ regional
workbook:

| Metric | Value |
|---|---:|
| Mean domestic electricity, all meters | 3,240.671 kWh/year |
| Median domestic electricity, all meters | 2,357.400 kWh/year |
| Mean domestic electricity per household | 3,302.319 kWh/year |
| Default modelled annual load | 3,302.319 kWh/year |

The branch also stores a Great Britain reference:

| Metric | Value |
|---|---:|
| Mean domestic electricity, all meters | 3,322.736 kWh/year |
| Median domestic electricity, all meters | 2,471.100 kWh/year |
| Mean domestic electricity per household | 3,463.408 kWh/year |

## Tariff Defaults

The public-reference flat tariff uses:

- import unit rate: GBP 0.2467/kWh;
- standing charge: GBP 0.5721/day;
- export unit rate: GBP 0.12/kWh;
- SEG floor sensitivity: GBP 0.041/kWh.

The import rate and standing charge are the Ofgem average Direct Debit standard
variable electricity price-cap rates for 1 April to 30 June 2026. They are GB
averages, not a London-specific supplier tariff. The export rate is Octopus
Outgoing fixed as published on the Octopus export tariff page. The SEG value is
Octopus SEG as a public flat export sensitivity; Ofgem requires SEG tariffs to
be above zero but suppliers choose the rate and terms.

## PV Defaults

The London reference PV assumptions are intentionally minimal:

- latitude: 51.5074;
- longitude: -0.1278;
- PV capacity: 4.0 kWp;
- tilt: 35 degrees;
- PVGIS aspect: 0 degrees, meaning south-facing;
- system loss: 14%.

Use `build_pvgis_hourly_url(...)` to create a PVGIS hourly API request. The
branch does not silently call PVGIS inside dispatch because a real scenario
should preserve the exact PVGIS URL, retrieval time and input assumptions.

## VPP Defaults

VPP income is scenario-based:

| Case | Event reward | Reference events/year | Annual scenario |
|---|---:|---:|---:|
| Low | GBP 1/event | 12 | GBP 12/year |
| Central | GBP 3/event | 12 | GBP 36/year |
| High | GBP 5/event | 12 | GBP 60/year |

CSE reports typical household DFS savings of around GBP 1-5 per event in 2025.
NESO's Winter 2024/25 DFS review provides public market-level event, bid and
payment statistics. These values are useful for sensitivity testing, but they do
not represent a guaranteed household VPP contract.

## Source Anchors

- DESNZ subnational electricity: https://www.gov.uk/government/statistics/regional-and-local-authority-electricity-consumption-statistics
- DESNZ summary report: https://www.gov.uk/government/statistics/subnational-electricity-and-gas-consumption-summary-report-2024/subnational-electricity-and-gas-consumption-summary-report-2024--2
- London Datastore Low Carbon London: https://data.london.gov.uk/dataset/smartmeter-energy-use-data-in-london-households/
- UKPN smart meter data: https://ukpowernetworks.opendatasoft.com/pages/smart-meters/
- SSEN/Weave aggregate data: https://data.ssen.co.uk/showcases/weave-half-hourly-energy-consumption
- Elexon profile classes: https://www.elexon.co.uk/knowledgebase/profile-classes/
- PVGIS: https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis_en
- PVGIS API: https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/api-non-interactive-service_en
- Ofgem April-June 2026 price cap: https://www.ofgem.gov.uk/news/changes-energy-price-cap-between-1-april-and-30-june-2026
- Octopus API docs: https://docs.octopus.energy/rest/guides/endpoints/
- Octopus export tariffs: https://octopus.energy/export-tariffs/
- Ofgem SEG: https://www.ofgem.gov.uk/environmental-and-social-schemes/smart-export-guarantee-seg/electricity-suppliers
- NESO DFS Winter 2024/25 review: https://www.neso.energy/document/363911/download
- CSE DFS household rewards: https://www.cse.org.uk/advice/how-much-could-you-earn-demand-flexibility-service/
- ENA connection guidance: https://www.energynetworks.org/industry/connecting-to-the-networks/connecting-generation-to-the-electricity-networks
