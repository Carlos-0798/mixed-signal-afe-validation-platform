# Software Phase 3 Step 2 Report

**Date:** 2026-08-30<br>
**Milestone:** provenance-aware DC sweep analysis<br>
**Evidence class:** HOST_TEST / SYNTHETIC<br>
**Hardware used:** none

## Outcome

Software Phase 3 Step 2 is complete. The formal package now pairs traceable input/output Measurements, applies shared quality decisions, excludes configurable inclusive low/high saturation points, and calculates an ordinary least-squares DC fit when enough distinct eligible inputs remain.

This checkpoint does not create PASS/FAIL conclusions, operate an adapter, authorize an output, access a serial port, or validate physical hardware.

## Delivered

- `dc-sweep-analysis.v1` configuration and result schema;
- ordinal within-channel input/output pairing with structural validation;
- immutable paired-point and point-result records containing both source references;
- explicit `INPUT_NOT_INCLUDED`, `OUTPUT_NOT_INCLUDED`, `LOW_SATURATION`, and `HIGH_SATURATION` reasons;
- configurable finite inclusive saturation limits and minimum included-point count;
- gain, offset, R², RMSE, maximum absolute residual, and used-point count;
- prediction and residual on every included point in a complete fit;
- exact incomplete-analysis gaps without a misleading partial fit;
- public `analog_validation.analysis` exports while preserving the frozen Phase 2 top-level API.

## Important consistency guarantees

| Rule | Result |
|---|---|
| Unexpected channel, missing side, or unequal pair counts | Rejected as structural input error |
| Mixed evidence source or duplicate record ID | Rejected before analysis |
| Unknown, non-voltage, NaN, or infinite usable value | Rejected or retained as an invalid quality decision according to the Measurement contract |
| Output exactly on a low/high limit | Excluded with the corresponding saturation reason |
| Quality-excluded or invalid component | Pair retained with component and DC-level reasons |
| Fewer than the configured included points | Incomplete result with exact gap and no fit |
| Fewer than two distinct included input values | Incomplete result with exact gap and no fit |
| Excluded/invalid point has prediction or residual | Rejected |
| Synthetic or replay evidence becomes bench evidence | Not possible through these models |

## Executed verification

| Gate | Result |
|---|---|
| Focused Step 2 tests | PASS — 81 |
| Focused DC sweep coverage | PASS — 325/325 statements, 100% |
| Full pytest suite | PASS — 781 tests |
| Formal package coverage | PASS — 2,800/2,800 statements, 100% |
| Phase 2 public API/workflow golden compatibility | PASS — unchanged within full suite |
| Formal-core dependency boundary | PASS |
| Full-repository Ruff | PASS |
| mypy on `src`, `dashboard`, `tools`, and `tests` | PASS — 72 source files |
| Local dependency consistency | PASS — no broken requirements |
| Isolated sdist and wheel build | PASS |
| DC sweep module and focused tests present in sdist | PASS |
| Repository-external wheel install and DC analysis smoke | PASS |
| Installed-package dependency consistency | PASS |

The external smoke preserved the frozen 84-symbol Phase 2 top-level API and exposed the 19-symbol `analog_validation.analysis` namespace. It exercised an exact traceable fit, inclusive saturation exclusion, insufficient-data reporting, and unchanged `SYNTHETIC` provenance outside the repository.

The first external-install attempt used a virtual environment nested under the
already long repository path and hit Windows `WinError 206` while creating
package metadata. No success was claimed from that attempt. Repeating the same
wheel installation in a short repository-external virtual environment
succeeded, `pip check` passed, and the import resolved from that environment's
`site-packages`. This was a verification-path limitation, not a package-code
change.

## Beginner interpretation

Step 2 is the calculator, not the judge and not the laboratory operator. It receives a filled-in worksheet, identifies which rows are safe to use, keeps the rejected rows with explanations, and calculates the best-fit line. Step 3 will separately define the engineering limits that decide whether those numbers pass.

## Evidence boundary

All verification is host software evidence. Numeric sweep values are test fixtures. No controller, ADC, DAC, PWM, serial link, instrument, AFE circuit, wiring, real voltage, settling time, accuracy, saturation voltage, or shutdown behavior was used or verified. Verified hardware claims remain zero.

## Next checkpoint

Software Phase 3 Step 3 will add immutable versioned DC acceptance criteria and map a complete analysis into evidence-backed TestRun decisions. A complete acceptable dataset may produce PASS, a complete out-of-tolerance dataset may produce FAIL, and missing criteria or incomplete analysis must never produce PASS. Output control and hardware remain outside Step 3.
