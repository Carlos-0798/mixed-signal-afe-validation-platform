# Software Phase 3 Step 3 Report

**Date:** 2026-08-30<br>
**Milestone:** versioned DC criteria and TestRun mapping<br>
**Evidence class:** HOST_TEST / SYNTHETIC<br>
**Hardware used:** none

## Outcome

Software Phase 3 Step 3 is complete. The formal package now keeps DC acceptance criteria separate from analysis, evaluates five explicit numeric rules, and maps only complete, sufficiently evidenced evaluations into `TestRunOutcome.PASS` or `FAIL`.

Missing criteria, incomplete analysis, or insufficient criteria-level point count returns `INCOMPLETE` with exact gaps. Structural contradictions are rejected. This checkpoint does not acquire measurements, control output, access serial hardware, or validate an AFE.

## Delivered

- `dc-sweep-criteria.v1` immutable acceptance criteria;
- `dc-sweep-evaluation.v1` criterion and evaluation result models;
- stable `GAIN`, `ABS_OFFSET`, `R_SQUARED`, `RMSE`, and `INCLUDED_POINTS` names;
- inclusive lower/upper bounds with model-enforced boolean consistency;
- explicit ratio, voltage, and point units in every rule result;
- deterministic PASS/FAIL mapping for complete evaluations;
- explicit `INCOMPLETE` mapping for missing criteria, Step 2 gaps, or criteria point shortage;
- exact TestRun metadata source/test-type/raw-ID consistency checks;
- all retained input/output record IDs copied into TestRun evidence;
- unchanged Phase 2 top-level public API.

## Outcome safety matrix

| Situation | Outcome |
|---|---|
| Complete analysis and all five rules pass | PASS |
| Complete analysis and at least one performance rule fails | FAIL |
| No acceptance criteria | INCOMPLETE |
| Step 2 analysis has missing requirements | INCOMPLETE |
| Analysis has fewer points than criteria requires | INCOMPLETE, not FAIL |
| Criteria unit conflicts with analysis | Validation error |
| Metadata source/type/raw IDs conflict with analysis | Validation error |
| PASS/FAIL without complete evidence IDs | Rejected by TestRun model |

## Executed verification

| Gate | Result |
|---|---|
| Focused Step 3 tests | PASS — 67 |
| Focused criteria coverage | PASS — 201/201 statements, 100% |
| Full pytest suite | PASS — 848 tests |
| Formal package coverage | PASS — 3,002/3,002 statements, 100% |
| Phase 2 public API/workflow golden compatibility | PASS — unchanged within full suite |
| Formal-core dependency boundary | PASS |
| Full-repository Ruff | PASS |
| mypy on `src`, `dashboard`, `tools`, and `tests` | PASS — 74 source files |
| Local dependency consistency | PASS — no broken requirements |
| Isolated sdist and wheel build | PASS |
| Criteria module and focused tests present in sdist | PASS |
| Repository-external wheel install and PASS/FAIL/INCOMPLETE smoke | PASS |
| Installed-package dependency consistency | PASS |

The external smoke preserved the frozen 84-symbol Phase 2 top-level API and exposed the 27-symbol `analog_validation.analysis` namespace. It exercised a synthetic PASS, an out-of-tolerance FAIL, missing-criteria INCOMPLETE, criteria-point-shortage INCOMPLETE, exact evidence IDs, and unchanged `SYNTHETIC` provenance outside the repository.

## Beginner interpretation

Step 2 built the calculator. Step 3 adds a versioned grading sheet. A grade is allowed only when the calculator had enough data and the grading sheet is complete. A software PASS is still qualified by its evidence source; a synthetic PASS proves the decision code, not a real circuit.

## Evidence boundary

All executed cases are host tests using constructed `SYNTHETIC` Measurements. No physical gain, offset, linearity, noise, saturation, ADC accuracy, DAC accuracy, timing, wiring, supply, instrument, controller, or shutdown behavior was measured. The criteria values are examples, not validated product limits. Verified hardware claims remain zero.

## Next checkpoint

Software Phase 3 Step 4 will implement a controller-neutral DC sweep plan and safety-gated runner. It must perform complete capability/range/shutdown preflight before output, inject settling behavior, acquire traceable input/output records, map unsupported/incomplete/error states correctly, and guarantee shutdown on every path. Only a host-test reference output adapter will be used; real hardware remains out of scope.
