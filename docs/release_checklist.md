# Release Checklist

Use this checklist before publishing Release 1.

## 1. Repository

- Clean clone installs from lockfile.
- Package imports without side effects.
- CLI help works.
- No secrets or local paths are committed.
- Notebooks are not production source of truth.
- Licence file exists.

## 2. Quality

- Ruff check passes.
- Ruff format check passes.
- Type check passes.
- Unit tests pass.
- Tiny regression tests pass.
- Dashboard import smoke test passes.
- Marked network tests are documented.

## 3. Sources

- Source registry is populated.
- Assumptions ledger is populated.
- P1-00 source feasibility review exists.
- All central source URLs are valid or archived.
- Licences and redistribution caveats are documented.
- Known-at policy exists for rolling inputs.

## 4. Data

- Processed datasets have manifests.
- Raw and processed data policy is documented.
- Tiny fixtures exist where licence permits.
- Phase 4 default smoke sample is historical and aligned across Elexon MID and NESO EAC rows.
- Short Phase 4 smoke windows record explicit skipped-window reasons.
- Default Phase 4 fixture hash is pinned in unit tests; fixture edits must update the digest intentionally.
- DST tests pass.
- Missing-data classifications are visible.
- Negative prices are preserved.

## 5. Optimisation

- Energy balance tests pass.
- SoC bounds tests pass.
- Objective equals extracted revenue.
- Service revenue includes duration.
- Reserve headroom/footroom tests pass.
- Idle reserve tests pass.
- Upward reserve efficiency test passes.
- CM does not alter central dispatch.

## 6. Rolling Policy

- No-leakage tests pass.
- Future-marker fixtures fail if leakage is introduced.
- Rolling state uses executed actions only.
- Terminal SoC policy is explicit.
- Free-terminal diagnostic is excluded from central headline.
- Capture ratio calculation is tested.

## 7. Finance

- Finance boundary doc is complete.
- NPV hand-calculation tests pass.
- CM counted once per year.
- Derating source and delivery year are visible.
- Excluded finance items are shown in dashboard or README.
- Outputs say scenario appraisal, not bankability.

## 8. Benchmark Reconciliation

- Benchmark anchors have URL and date.
- Unknown benchmark methods are labelled unknown.
- Reconciliation scorecard exists.
- No pass/fail replication wording appears.
- BM exclusion is explained.

## 9. Dashboard

- Dashboard runs from cached outputs.
- Dashboard does not call live APIs.
- Dashboard does not require solver.
- Dashboard import guard blocks solver and source-client imports.
- Dashboard cache includes EAC commitments and data-quality summary files.
- All charts have units.
- Caveats are visible without opening methodology.
- Missing cache files fail gracefully.

## 10. Documentation

- README first screen explains the product.
- Methodology includes equations and boundaries.
- Reproducibility guide is accurate.
- Known limitations are visible.
- Residential scenario sweep caveats are visible.
- Interview demo script exists.
- Phase reviews exist for completed phases.
- README, dashboard and methodology tell the same story.

## 11. Final Tag

- Version number chosen.
- Changelog or release note written.
- Release artefacts rebuilt.
- Final smoke test run after artefact rebuild.
- Git tag created if using git release flow.
