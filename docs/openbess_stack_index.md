# OpenBESS Stack Index

The OpenBESS Stack Index Preview is a public-data educational series for a
reference GB battery energy storage asset. It is not an official market index,
not investment advice, not a proprietary benchmark replication and not a
bankable revenue forecast.

The public-facing name is OpenBESS Stack Index, but every named output must
carry `not_a_market_index` until and unless a future governance process creates
an independently maintained index. Preview outputs should be labelled as a
preview unless the coverage gates below pass.

## Reference Assets

The series is built from explicit reference assets, not from named operational
units. The central reference asset is the GB BESS modelling asset defined in the
repo assumptions and reference-asset configuration. It exists to make public
data treatment reproducible across runs.

Reference assets are modelling objects. They are not claims about any specific
site, route-to-market contract, warranty, grid connection, outage profile or
commercial optimiser.

In stack-series cache rows, `asset_id` identifies the asset actually solved in
the cache. `openbess_canonical_1mw_2mwh` is valid only for canonical reference
runs, not for every smoke run or commercial fixture.

## Stack Sequence

The OpenBESS Stack Index sequence is:

1. Elexon BMRS MID wholesale proxy.
2. NESO EAC price-taking availability proxy.
3. Capacity Market annual scenario.
4. Degradation adjustment.

The GB sequence therefore runs wholesale proxy -> EAC -> CM -> degradation. A
rolling-policy run may only use source rows satisfying:

```text
known_at_utc <= decision_time_utc
```

Balancing Mechanism counterfactual revenue is excluded. Observed BM analysis may
be documented separately, but counterfactual acceptance and revenue are not
inferable from public data alone and do not enter the central stack series.

## Public Data Treatment

Wholesale value uses the Elexon BMRS MID wholesale proxy. This is a public
short-term price proxy, not a licensed exchange execution price.

EAC value uses the NESO EAC price-taking availability proxy. It applies accepted
auction-result prices to transparent availability assumptions and does not clear
EAC auctions, model strategic bidding or infer acceptance probability.

Capacity Market value is a Capacity Market annual scenario. CM is reported as an
annual scenario value and must not be treated as settlement-period dispatch
revenue.

Degradation is a transparent throughput cost or scenario adjustment. It is not
an electrochemical cell model or warranty model.

The educational simple-market preset may be used for demonstration, teaching
and smoke testing. It must be labelled as educational and must not be promoted
as a production market model.

## Coverage Gates

Window eligibility is tracked for:

- `7d`;
- `30d`;
- `90d`;
- `ytd`;
- `trailing_12m`.

Each window records observed periods, expected periods, coverage percentage,
annualisation eligibility, public-index eligibility and caveat flags. Public
eligibility requires the configured coverage threshold to pass.
The `ytd` expected period count is calendar year-to-date from the cache
`created_at_utc`, with the same 90-day minimum floor used for public
annualisation.

Annualisation is allowed only for eligible longer windows. The 90d gate is the
minimum public annualisation gate; shorter windows can be shown as preview or
diagnostic samples but should not be annualised as public headline values.
Annualised finance and benchmark model fields are suppressed/null until coverage gates pass.
Trailing 12m is the preferred public window once available.

If a window is annualised from a partial sample, outputs must carry
`partial_sample_annualised` and explain that the value depends on the observed
sample mix. Partial annualisation is useful for diagnostics, not a public claim
of full-year performance.

## Published Artefacts

The published artefacts for the dashboard and release bundle may include:

- `stack_series.parquet`;
- `stack_series.csv`;
- `revenue_stack.parquet` and `revenue_stack.csv`;
- `policy_capture.parquet` and `policy_capture.csv`;
- `forecast_error_sweeps.parquet` and `forecast_error_sweeps.csv`;
- dashboard manifest and caveats;
- window eligibility metadata;
- reference-asset metadata;
- finance and Capacity Market assumptions ledger;
- source snapshot and known-at policy metadata.

The CSV and parquet exports must be generated from the same dataframe. CSV
serialises list-like caveat fields such as `caveat_flags` as JSON strings.

The Capacity Market value is a per MW per year scenario sidecar. It is carried
in stack-series rows and finance outputs, but it does not enter settlement
period optimisation or dispatch revenue.

Forecast error sweeps show how rolling-policy value changes when wholesale
forecasts are biased or scaled. They are sensitivity rows and should not be
presented as a separate market component.

## Non-Claims

OpenBESS Stack Index outputs do not claim to:

- be an official market index;
- be investment advice;
- prove bankable returns;
- replicate Modo, Aurora, LCP, AFRY or any proprietary model;
- forecast endogenous GB power prices;
- infer Balancing Mechanism counterfactual revenue;
- clear EAC auctions;
- represent site-specific commercial terms.
