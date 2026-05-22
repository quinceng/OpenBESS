# Phase 4 Review - Rolling EAC-Aware Revenue Stack

## Outcome

Phase 4 may proceed with caveat. The rolling wholesale plus EAC policy, scenario
sweeps, forecast-error sweeps and cached dashboard artefacts are implemented.
The next real release gate is no longer the tiny packaged smoke fixture; it is
the 90-day historical release cache.

## Built

- No-leakage rolling market-stack policy using known-at-filtered Elexon MID and
  NESO EAC inputs.
- Rolling-vs-perfect-foresight capture comparison for wholesale plus EAC.
- 24h, 48h and 7d comparison helpers when enough rows are available.
- Deterministic wholesale/EAC scalar sweeps.
- Forecast-error sweeps for biased or scaled wholesale forecasts.
- Aligned source-cache builder and release-cache runner.
- Dashboard cache outputs for policy capture, revenue stack, scenario sweeps,
  forecast-error sweeps, EAC commitments, data quality, stack series, source
  snapshot and assumptions ledger.

## Release Cache Evidence

The longer aligned release cache gate has been exercised at three scales:

| Gate | Periods | Hours | Result |
| --- | ---: | ---: | --- |
| 7d aligned cache | 336 | 168 | Pass |
| 30d aligned cache | 1440 | 720 | Pass |
| 90-day historical release cache | 4320 | 2160 | Pass with caveat |

The 90-day historical release cache used the canonical
`openbess_canonical_1mw_2mwh` asset over `2026-02-01T00:00:00Z` to
`2026-05-02T00:00:00Z`. The release run reported rolling revenue of
GBP 4,826.43, perfect-foresight revenue of GBP 16,958.91 and a capture ratio of
0.2846. Solver failures were zero.

The default 90-day run starting `2026-04-01T00:00:00Z` extended beyond available
history and returned only 2394 periods. Public annualisation should therefore
use an explicit historical start until source coverage is continuous enough for
the default rolling window.

## Acceptance Status

| Requirement | Status |
| --- | --- |
| Rolling EAC-aware policy uses only known inputs | Complete |
| Capture comparison is written and tested | Complete |
| Scenario sweeps are available in release cache | Complete |
| Forecast-error sweeps are implemented and cached | Complete |
| Longer 7d and 30d aligned gates run | Complete |
| 90d historical release gate run | Complete |
| Phase 4 review is written | Complete |

## Caveats

- EAC source gaps remain visible in the aligned manifest; the 90-day historical
  cache retained 2828 periods with EAC source gaps rather than silently filling
  them.
- Unsupported EAC product labels are quarantined.
- The 90-day gate is sufficient for Release 1 public annualisation, but not a
  substitute for trailing-12-month or calendar-year coverage.
- Balancing Mechanism counterfactual revenue remains excluded.

## Gate Decision

Proceed with caveat.

