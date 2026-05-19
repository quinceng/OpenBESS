# Residential BESS Branch Assumptions

The residential branch is separate from the central utility-scale market-stack
optimiser. It is for UK household BESS presets, household capex treatment and
residential market-access eligibility.

## Branch Boundary

Residential modelling uses kW/kWh units and household export limits. It must not
change the central optimiser's MW/MWh asset model, rolling policy or market-stack
logic.

Commercial modelling has its own `gb_bess_revenue_stack.commercial` namespace.
That namespace uses MW/MWh units and should be expanded separately from the
residential branch.

## Residential Product Presets

Product capacity and inverter defaults are anchored to official product pages
where available. Cost ranges are user-supplied branch assumptions. Component
splits are modelling defaults chosen so that total capex lands inside the
supplied installed-capex range. These are not procurement quotes.

| Preset key | Product | Battery capacity | Inverter treatment | Inverter power default | Installed capex range | Default total capex |
|---|---:|---:|---|---:|---:|---:|
| `tesla_powerwall_3` | Tesla Powerwall 3 | 13.5 kWh | Integrated inverter | 11.04 kW | GBP 7,499-9,000 | GBP 8,249.50 |
| `givenergy_9_5_module` | GivEnergy 9.5 kWh module | 9.5 kWh | Battery-only; compatible external inverter included | 3.6 kW | GBP 5,800-6,500 | GBP 6,150 |
| `givenergy_all_in_one_2` | GivEnergy All-in-One 2 | 13.5 kWh | Integrated inverter | 6.0 kW | GBP 6,200-7,300 | GBP 6,750 |
| `enphase_iq_battery_5p` | Enphase IQ Battery 5P | 5.0 kWh | Integrated AC-coupled system | 3.84 kW | GBP 3,500-4,500 | GBP 4,000 |

Capex rule:

```text
total capex = battery cost + installation cost + effective inverter cost
```

For integrated-inverter systems, effective inverter cost is zero even if an
external inverter cost field is present. For battery-only systems, a compatible
external inverter cost is required and included.

## UK Residential Market Access

Default market-access assumptions:

| Assumption | Default |
|---|---:|
| DNO export limit | 3.68 kW |
| Aggregator/VPP participation | Allowed |
| Direct NESO/National Grid threshold | 1,000 kW |
| UKPN/London direct local flexibility threshold | 10 kW |

Revenue-route treatment:

- self-consumption and behind-the-meter arbitrage are limited by inverter power;
- export is limited by the lower of inverter power and DNO export limit;
- residential participation in flexibility markets is allowed through an
  aggregator/VPP route by default;
- normal residential systems are not eligible for direct NESO bidding under the
  default 3.68 kW export cap and 1,000 kW direct-access threshold;
- direct UKPN/London local flexibility is only eligible when the effective export
  capability reaches the 10 kW branch threshold.

These are modelling assumptions for branch development, not legal advice or
market-registration guidance.

## Household Calculator

The residential calculator is a simple annual payback view. It does not invoke
the main optimiser and does not mix household kW/kWh assumptions into the
commercial MW/MWh branch.

Inputs:

- battery cost, installation cost and inverter cost from the selected household
  system preset or user-defined system;
- DNO export limit;
- annual self-consumption savings;
- annual tariff-arbitrage savings;
- annual export revenue;
- annual aggregator/VPP participation revenue, included only when enabled and
  the aggregator route is eligible.

Outputs:

- battery capacity, inverter power and effective export limit;
- total capex;
- annual benefit split by self-consumption, tariff arbitrage, export and
  aggregator/VPP participation;
- total annual benefit;
- simple payback years, blank when annual benefit is zero.

## Bill-Aware Household Dispatch

The residential branch also supports an interval household calculator for load,
PV, retail import/export tariffs and optional aggregator/VPP events. This path
uses kW/kWh household units and remains separate from the commercial branch and
the central wholesale/EAC optimiser.

Interval inputs:

- household load in kWh per interval;
- PV generation in kWh per interval;
- import and export tariff rates in GBP/kWh;
- optional daily standing charge in GBP/day;
- DNO/site export limit in kW;
- battery capacity, power, round-trip efficiency and initial state of charge;
- optional VPP events with required export energy, minimum SoC and event
  payment assumptions.

Dispatch outputs:

- readable interval timestamps;
- grid import, export, PV self-consumption, battery charge/discharge and SoC;
- no-battery bill and battery bill;
- self-consumption, tariff-arbitrage, export and VPP value components;
- annualised payback-style outputs when the sample period is shorter than a
  year.

The bill-aware calculator is a household decision aid, not a supplier billing
replica. It does not reconstruct VAT, standing-charge variants, supplier-specific
settlement adjustments or all network charge structures. Standing charge is
reported as part of the no-battery comparator but is treated as non-controllable
by dispatch.

## Public Reference Assumptions

When actual household data is unavailable, the residential branch exposes public
reference assumptions through
`gb_bess_revenue_stack.residential.public_assumptions`.

The default London reference household uses public 2024 DESNZ domestic
electricity aggregates:

- annual mean domestic consumption per meter: 3,240.671 kWh;
- annual median domestic consumption per meter: 2,357.400 kWh;
- annual mean domestic consumption per household: 3,302.319 kWh.

The Great Britain reference household uses:

- annual mean domestic consumption per meter: 3,322.736 kWh;
- annual median domestic consumption per meter: 2,471.100 kWh;
- annual mean domestic consumption per household: 3,463.408 kWh.

Default public tariff assumptions are:

- import unit rate: GBP 0.2467/kWh;
- standing charge: GBP 0.5721/day;
- export unit rate: GBP 0.12/kWh;
- SEG export sensitivity: GBP 0.041/kWh.

These are public proxy values, not actual customer tariffs. VPP values are low,
central and high scenarios of GBP 12, GBP 36 and GBP 60 per year respectively.
The export-limit default remains 3.68 kW unless site-specific DNO paperwork is
available.

See `docs/residential_public_data_sources.md` for source anchors and caveats.

## Specification Anchors

- Tesla Powerwall 3: https://www.tesla.com/en_GB/powerwall
- GivEnergy 9.5 kWh module: https://givenergy.com/resource-hub/datasheets/giv-bat-9-5-datasheet/
- GivEnergy All In One 2: https://givenergy.com/hardware/all-in-one-2/
- Enphase IQ Battery 5P: https://enphase.com/store/storage/gen3/iq-battery-5p
