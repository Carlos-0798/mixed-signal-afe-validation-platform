# Software Phase 3 Step 4 verification report

**Date:** 2026-08-30<br>
**Checkpoint:** controller-neutral, safety-gated DC sweep runner<br>
**Evidence:** HOST_TEST / SYNTHETIC / CSV_REPLAY semantics only<br>
**Hardware verified:** 0

## Outcome

Step 4 is complete. The installable package now exposes a separate `analog_validation.runners` namespace with immutable DC plan, acquisition-step, and runner-result models plus `run_dc_sweep(...)`.

The runner performs all host-side permission, identity, capability, channel, unit, setpoint-range, and safe-shutdown checks before output or acquisition. It owns one disconnected adapter, preserves complete or partial evidence, always attempts adapter cleanup, and invokes analysis/criteria only after cleanup succeeds.

## Delivered behavior

- `dc-sweep-runner.v1` schema and five-symbol runners public namespace;
- ordered finite setpoints with per-setpoint repetitions;
- explicit stimulus/input/output channels and V/mV unit agreement;
- versioned analysis and optional criteria embedded in the plan;
- injected settle and abort callbacks;
- exact setpoint/repetition-to-record lineage for every completed pair;
- exact raw/evidence IDs for complete and partial TestRun results;
- full static and connected capability preflight before I/O;
- output authorization through the frozen `ValidationConfig` and `DeviceAdapter` gates;
- disconnect-owned safe shutdown on success, abort, EOF, read failure, and callback failure;
- cleanup failure overriding an apparent PASS with `ERROR`;
- analysis and criteria evaluation only after complete acquisition and successful cleanup;
- unchanged read-only Simulator and CSV Replay behavior.

## Outcome semantics exercised

| Condition | Result |
|---|---|
| Complete HOST_TEST acquisition meets criteria | PASS |
| Complete HOST_TEST acquisition violates criteria | FAIL |
| Explicit abort, keyboard interrupt, early EOF, missing criteria, or incomplete analysis | INCOMPLETE |
| Missing read/output/channel/unit/safe-shutdown capability | UNSUPPORTED with zero acquisition |
| Connection, callback, read, analysis, shutdown, or disconnect fault | ERROR |

No partial or cleanup-failed attempt can produce PASS or FAIL.

## Verification results

| Gate | Actual result |
|---|---|
| Focused Step 4 tests | PASS — 58 tests |
| Focused runners namespace coverage | PASS — 350/350 statements, 100% |
| `dc_sweep.py` coverage | PASS — 348/348 statements, 100% |
| Full pytest suite | PASS — 906 tests |
| Formal package coverage | PASS — 3,352/3,352 statements, 100% |
| Ruff | PASS — full repository |
| mypy | PASS — 78 source files |
| Local dependency check | PASS — no broken requirements |
| Isolated sdist/wheel build | PASS |
| sdist content | PASS — runner module plus unit/integration tests present |
| Repository-external wheel install | PASS |
| External wheel dependency check | PASS |
| External runner smoke | PASS — PASS/FAIL/INCOMPLETE/ERROR/UNSUPPORTED and cleanup precedence |
| Frozen Phase 2 top-level API | PASS — 84 symbols |
| Existing analysis namespace | PASS — 27 symbols |
| New runners namespace | PASS — 5 symbols |

## Test-only reference boundary

The output-capable `ReferenceOutputAdapter` is defined only in the Step 4 tests and uses `HOST_TEST` provenance. It calculates deterministic values in Python and records lifecycle calls. It is not shipped as a product adapter and is not evidence for a DAC, PWM output, ADC, MSP430, instrument, or AFE.

The formal `SimulatorAdapter` and `CsvReplayAdapter` remain read-only. Integration tests send both through the runner and confirm `UNSUPPORTED`, zero Measurements, empty evidence IDs, preserved source labels, and final `DISCONNECTED` state.

## Safety and evidence limits

- Calling a Python `safe_shutdown` hook does not prove a physical output reached a safe voltage.
- Test safe ranges and acceptance limits are fixtures, not measured hardware specifications.
- No serial transport, board SDK, controller, instrument, wire, power rail, or analog circuit was used.
- The runner does not yet enforce wall-clock command or total-test deadlines; transport-aware timeout enforcement remains future work.
- Supplied TestRun timestamps are explicit metadata and are not fabricated from a hardware clock.
- `HOST_TEST`, `SYNTHETIC`, and `CSV_REPLAY` results cannot support hardware performance claims.
- Verified bench claims remain zero.

## Next checkpoint

Software Phase 3 Step 5 will implement formal directional hysteresis analysis and a safety-gated hysteresis runner. It must preserve rising/falling record references, transition intervals, repeated-cycle statistics, explicit incomplete/error states, and the same cleanup-before-conclusion rule.
