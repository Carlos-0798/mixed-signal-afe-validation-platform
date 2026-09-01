# Hysteresis analysis and runner v1

Software Phase 3 Step 5 adds formal directional Schmitt-trigger analysis, versioned acceptance criteria, and a controller-neutral acquisition runner. All current evidence is `HOST_TEST`, `SYNTHETIC`, or `CSV_REPLAY`; no comparator, controller, wire, instrument, or physical threshold has been verified.

## Beginner mental model

A Schmitt trigger intentionally remembers its previous state. On a rising input it changes from 0 to 1 at the upper threshold. On a falling input it changes from 1 to 0 at the lower threshold. Their difference is the hysteresis width:

```text
high threshold - low threshold = hysteresis width
```

With sampled data, the exact crossing happened somewhere between the last sample before the state change and the first sample after it. Version 1 reports the midpoint of that interval. It does not pretend that the midpoint is a directly measured transition voltage.

```text
rising:  1790 mV / state 0 ---- transition ---- 1810 mV / state 1
estimate:                         1800 mV midpoint

falling: 1510 mV / state 1 ---- transition ---- 1490 mV / state 0
estimate:                         1500 mV midpoint

width: 1800 mV - 1500 mV = 300 mV
```

## Formal analysis contract

`HysteresisCycleInput` contains one rising `MeasurementBatch` and one falling batch. Records alternate between the configured analog-input channel and boolean state channel. Every record keeps its original ID, raw ID, UTC timestamp, source, unit, status, and quality flags.

`analyze_hysteresis(...)` enforces:

- at least two input/state points in each direction;
- one evidence source and unique record IDs across all cycles;
- V or mV analog input and boolean state units;
- digital values restricted to exactly 0 or 1;
- monotonically nondecreasing rising inputs;
- monotonically nonincreasing falling inputs;
- exactly one rising `0 -> 1` transition;
- exactly one falling `1 -> 0` transition;
- no reverse transition, chatter, or multiple state changes;
- `high_threshold >= low_threshold`.

Each `HysteresisTransition` stores four references: analog and state records immediately before the change, plus analog and state records immediately after it. It also stores both interval endpoints, the midpoint estimate, unit, direction, states, and the stable method name `adjacent-input-interval-midpoint`.

If a point is missing or excluded by the quality policy, the cycle publishes no partial high/low/width values and identifies a missing requirement. A clean no-transition sweep is also `INCOMPLETE`. Structurally contradictory evidence such as reverse direction, chatter, non-binary state, or `high < low` raises a validation error.

## Repeated cycles and statistics

Every complete cycle retains its own high threshold, low threshold, and width. Only when every requested cycle is complete does `HysteresisSummary` publish:

- cycle count;
- mean high threshold;
- mean low threshold;
- mean width;
- minimum and maximum width;
- width span (`maximum_width - minimum_width`).

This separation matters: averaging cannot repair a missing or invalid cycle.

## Acceptance criteria

`hysteresis-criteria.v1` defines inclusive limits for mean high threshold, mean low threshold, mean width, maximum width span, and minimum complete cycles. `evaluate_hysteresis(...)` produces five explicit criterion results.

PASS or FAIL is possible only when:

1. all cycles are complete;
2. criteria exist and use the analysis unit;
3. the minimum cycle count is satisfied;
4. TestRun metadata names the exact source and raw records.

Missing criteria, incomplete analysis, or too few cycles remains `INCOMPLETE`; it never becomes FAIL and never becomes PASS.

## Runner order and safety

`run_hysteresis(...)` repeats the planned rising points followed by falling points for each cycle:

```text
validate all plan/config/metadata fields and every setpoint
                         |
connect read-only -> confirm capabilities
                         |
check analog read + digital read + output + safe shutdown
            | unsupported                     | supported
            v                                 v
   UNSUPPORTED, zero I/O                 arm explicitly
                                              |
                       set -> settle -> analog read -> state read
                                              |
                                  repeat rising/falling cycles
                                              |
                               safe shutdown -> disconnect
                                              |
                               analyze -> apply criteria
```

Every setpoint is checked against configuration limits before connection. After connection, all required commands, channels, units, device ranges, profile identity, and safe-shutdown support are checked before the first output. Analysis runs only after complete acquisition and successful cleanup.

## Stable outcomes

| Situation | Outcome |
|---|---|
| Complete evidence meets every criterion | `PASS` |
| Complete evidence violates at least one criterion | `FAIL` |
| Abort, interrupt, EOF, no transition, missing point/criteria, or too few cycles | `INCOMPLETE` |
| Required command, channel, unit, output, or safe shutdown is absent | `UNSUPPORTED` with zero acquisition |
| Connection, callback, read, contradictory analysis, shutdown, or disconnect fails | `ERROR` |

Partial records are preserved for audit, but partial analysis is not run. A cleanup failure overrides an apparent successful acquisition.

## Read-only product adapters

The shipped `SimulatorAdapter` and `CsvReplayAdapter` still advertise no stimulus output and no output safe-shutdown command. Integration tests confirm that both return `UNSUPPORTED`, consume zero records, issue zero setpoints, and finish disconnected. The output-capable hysteresis adapter exists only in tests, uses `HOST_TEST`, and models thresholds in Python.

## Evidence boundary

- A HOST_TEST PASS proves deterministic software behavior against fixture criteria only.
- Midpoint interpolation is a documented estimate, not a scope capture or DMM reading.
- Successful invocation of a Python shutdown hook is not proof of a safe physical voltage.
- No MSP430, ADC, DAC, comparator, instrument, wiring, or AFE was used.
- `VERIFIED_BENCH` remains zero.

See [analysis quality](analysis-common.md), [adapter safety](adapters.md), [TestRun semantics](capabilities-and-test-runs.md), [DC runner](dc-sweep-runner.md), and the [Step 5 verification report](../reports/software-phase3-step5.md).
