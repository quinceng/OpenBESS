# Commercial BESS Branch Assumptions

The commercial branch is separate from the residential household calculator. It
uses MW/MWh units and is the branch used for Phase 4 commercial revenue-stack
smoke outputs.

## Commercial System Inputs

- battery capacity in MWh;
- inverter power rating in MW;
- optional site export limit in MW;
- battery capex in GBP/MWh;
- inverter capex in GBP/MW;
- installation cost in GBP;
- grid connection cost in GBP.

The effective export limit is the lower of inverter power and site export limit.
If no site export limit is supplied, inverter power is used.

Capex rule:

```text
total capex =
  battery capacity MWh * battery capex GBP/MWh
  + inverter power MW * inverter capex GBP/MW
  + installation cost GBP
  + grid connection cost GBP
```

## Route To Market

The branch models two high-level routes:

- `direct_markets`: eligible only when effective export capability meets the
  configured direct-market threshold;
- `aggregator_route`: eligible when aggregator participation is enabled.

Each route carries an annual fixed fee and a variable fee percentage. These are
scenario assumptions for commercial appraisal, not market-registration advice.
