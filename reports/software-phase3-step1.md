# Software Phase 3 Step 1 Report

**Date:** 2026-08-30<br>
**Milestone:** common analysis vocabulary and quality policy<br>
**Evidence class:** HOST_TEST<br>
**Hardware used:** none

## Outcome

Software Phase 3 Step 1 is complete. The formal package now has a controller-neutral `analog_validation.analysis` namespace with versioned record lineage, one-source measurement batches, explicit analysis dispositions, exact point exclusion reasons, a default-deny suspect-quality policy, and strict V/mV normalization.

This checkpoint does not implement DC fitting, saturation-limit analysis, hysteresis calculation, PASS/FAIL criteria, automatic stimulus, serial transport, or hardware behavior.

## Delivered

- `analysis-common.v1` schema identifier;
- `PointDisposition`: `INCLUDED`, `EXCLUDED`, and `INVALID`;
- nine stable `PointExclusionReason` values covering status and every current quality flag;
- immutable `AnalysisQualityPolicy` with an explicit suspect-flag allowlist;
- immutable `AnalysisRecordReference` preserving record/raw IDs, UTC, channel, and evidence source;
- immutable `MeasurementBatch` requiring non-empty, unique-ID, one-source input;
- immutable `MeasurementDecision` preserving policy, normalized value, quality flags, disposition, and exact reasons;
- strict finite V/mV conversion with no magnitude- or channel-based unit inference;
- public `analog_validation.analysis` exports without changing the frozen Phase 2 top-level exports.

## Important consistency guarantees

| Rule | Result |
|---|---|
| VALID record has quality flags | Rejected |
| SUSPECT/INVALID record has no quality flags | Rejected |
| INVALID record marked INCLUDED/EXCLUDED | Rejected |
| EXCLUDED record omits or mislabels a disallowed flag | Rejected |
| INCLUDED suspect record lacks an allowlisting policy | Rejected |
| Missing/non-finite flag is allowlisted | Rejected |
| Batch has duplicate record IDs or mixed sources | Rejected |
| Non-voltage/unknown unit is normalized | Rejected |
| NaN/Inf is normalized | Rejected |
| Synthetic/replay source is relabeled as bench | Not possible through these models |

## Executed verification

| Gate | Result |
|---|---|
| Focused Step 1 tests | PASS — 56 |
| Focused analysis coverage | PASS — 244/244 statements, 100% |
| Full pytest suite | PASS — 700 tests |
| Formal package coverage | PASS — 2,474/2,474 statements, 100% |
| Phase 2 public API/workflow golden compatibility | PASS — unchanged within full suite |
| Formal-core dependency boundary | PASS |
| Full-repository Ruff | PASS |
| mypy on `src`, `dashboard`, `tools`, and `tests` | PASS — 70 source files |
| Local dependency consistency | PASS — no broken requirements |
| Isolated sdist and wheel build | PASS |
| Analysis module and focused test present in sdist | PASS |
| Repository-external wheel install and analysis smoke | PASS |
| Installed-package dependency consistency | PASS |

The external smoke confirmed the installed wheel preserves the 84-symbol Phase 2 top-level API while exposing the new 10-symbol `analog_validation.analysis` namespace. It exercised valid conversion, default suspect exclusion, explicit policy inclusion, one-source batching, mixed-source rejection, and unchanged `SYNTHETIC` provenance outside the repository.

## Beginner interpretation

Step 1 creates the labels and safety rules used by later math. Think of it as preparing a laboratory worksheet before calculating anything: every row keeps its identity, every rejected row needs a reason, and units must be converted explicitly. This prevents Step 2 from fitting whatever numbers happen to remain after an invisible filter.

## Evidence boundary

All verification is host software evidence. No serial port, controller, ADC, DAC, PWM, instrument, AFE, wiring, voltage, accuracy, bandwidth, timing, or physical shutdown behavior was used or verified. `BENCH_*` records were constructed only to test source classification; they are not measurements. Verified hardware claims remain zero.

## Next checkpoint

Software Phase 3 Step 2 will implement provenance-aware DC sweep point pairing, configurable low/high saturation exclusion, ordinary least-squares gain/offset, R², RMSE, maximum absolute residual, per-point predictions/residuals, and point-level inclusion/exclusion records. It will not yet produce PASS/FAIL or control outputs.
