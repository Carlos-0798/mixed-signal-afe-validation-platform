# Software Phase 3 Step 5 verification report

**Date:** 2026-08-30<br>
**Checkpoint:** formal directional hysteresis analysis and runner<br>
**Evidence:** HOST_TEST / SYNTHETIC / CSV_REPLAY semantics only<br>
**Hardware verified:** 0

## Outcome

Step 5 is complete. The installable package now provides versioned directional point, transition, cycle, summary, criteria, evaluation, plan, acquisition-step, and runner-result models plus `analyze_hysteresis(...)`, `evaluate_hysteresis(...)`, and `run_hysteresis(...)`.

The formal path preserves all analog/state record references, validates direction and digital state, reports midpoint transition intervals, supports repeated-cycle statistics, and refuses partial or contradictory conclusions. The runner performs complete safety/capability preflight before output and evaluates only after cleanup.

## Delivered behavior

- `hysteresis-analysis.v1`, `hysteresis-criteria.v1`, `hysteresis-evaluation.v1`, and `hysteresis-runner.v1`;
- rising nondecreasing and falling nonincreasing input validation;
- exact boolean 0/1 state validation and direction-specific transitions;
- analog/state record references before and after each transition;
- documented adjacent-interval midpoint estimation;
- per-cycle high/low/width with multi-cycle mean/minimum/maximum/span statistics;
- explicit incomplete no-transition and missing-point behavior;
- explicit rejection of reverse transition, chatter, multiple transitions, and `high < low`;
- five inclusive acceptance checks and criteria-gated TestRun mapping;
- ordered rising/falling repeated-cycle acquisition;
- abort, EOF, execution, analysis, and cleanup precedence;
- zero-I/O `UNSUPPORTED` integration proof for the shipped read-only adapters.

## Verification results

| Gate | Actual result |
|---|---|
| Focused Step 5 tests | PASS — 38 tests |
| New Step 5 module coverage | PASS — 892/892 statements, 100% |
| Full pytest suite | PASS — 944 tests |
| Formal package coverage | PASS — 4,247/4,247 statements, 100% |
| Ruff | PASS — full repository |
| mypy | PASS — 84 source files |
| Local dependency check | PASS — no broken requirements |
| Isolated sdist/wheel build | PASS |
| sdist content | PASS — six Step 5 source/test files present |
| Repository-external wheel install | PASS |
| External wheel dependency check | PASS |
| External public API smoke | PASS — version 0.1.0.dev0; top-level 84, analysis 45, runners 10 symbols |
| Frozen Phase 2 top-level API | PASS — 84 symbols |
| Analysis namespace | PASS — 45 symbols |
| Runners namespace | PASS — 10 symbols |

## Acceptance cases exercised

| Condition | Stable behavior |
|---|---|
| Normal rising/falling transition | Complete midpoint thresholds and width |
| Boundary midpoint | Exact average of adjacent input endpoints |
| Multiple cycles | Per-cycle values plus summary statistics |
| No transition | `INCOMPLETE`, no partial thresholds |
| Missing analog or state point | `INCOMPLETE`, exclusion retained |
| Reverse input order or state transition | Validation error / runner `ERROR` |
| Chatter or multiple transitions | Validation error / runner `ERROR` |
| Non-binary state | Validation error / runner `ERROR` |
| `high < low` | Validation error / runner `ERROR` |
| Missing capabilities | `UNSUPPORTED`, zero acquisition |
| Abort, EOF, cleanup failure | `INCOMPLETE`, `INCOMPLETE`, `ERROR` respectively |

## Test-only reference boundary

`ReferenceHysteresisAdapter` exists only in the unit tests. Its two thresholds and state memory are Python fixture behavior with `HOST_TEST` provenance. It does not ship in the product package and does not emulate analog settling, noise, comparator delay, ADC accuracy, DAC accuracy, wiring, or electrical safety.

The formal Simulator and CSV Replay adapters remain read-only. Step 5 integration tests confirm both return `UNSUPPORTED` with no Measurements consumed and a final disconnected state.

## Safety and evidence limits

- No real stimulus was generated and no physical state was read.
- The midpoint is an interval estimate, not a measured trip point.
- Test acceptance limits are fixtures, not validated product specifications.
- Host-side safe-shutdown call order is not physical safe-state proof.
- No serial transport, board SDK, MSP430, comparator, ADC, instrument, wiring, or power rail was used.
- Real-time command and total-test deadlines remain future transport work.
- Verified bench claims remain zero.

## Next checkpoint

Software Phase 3 Step 6 will add versioned calibration and offline frequency-response analysis. It must preserve derived-record lineage, units, quality decisions, and incomplete-result semantics without requiring hardware.
