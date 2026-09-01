# DC sweep runner v1

`analog_validation.runners` is the orchestration layer that joins the existing adapter, analysis, criteria, and TestRun contracts. Software Phase 3 Step 4 adds `dc-sweep-runner.v1` without changing the frozen Phase 2 top-level API.

This is host-software behavior. The reference output adapter used by the tests is a Python fixture, not a DAC, MSP430, instrument, or physical AFE.

## Beginner mental model

The earlier checkpoints created three separate pieces:

1. `DeviceAdapter` is the guarded doorway to a data source or future device.
2. DC analysis is the calculator for gain, offset, R², RMSE, and point decisions.
3. DC criteria are the grading sheet that can produce PASS or FAIL only from complete evidence.

The runner is the lab procedure that puts those pieces in the correct order. It does not replace their validation rules and does not contain board-specific branches.

```text
validate plan/config/metadata
          |
          v
connect read-only -> confirm capabilities -> full safety preflight
          |                                      |
          | missing capability                   | supported
          v                                      v
  UNSUPPORTED, zero I/O                    arm explicitly
                                                 |
                           set -> settle -> read input/output
                                                 |
                                      repeat all planned points
                                                 |
                                  safe shutdown -> disconnect
                                                 |
                                      analyze -> apply criteria
```

Analysis and PASS/FAIL happen only after the adapter has been released successfully. A cleanup failure therefore overrides an otherwise apparent PASS and produces `ERROR`.

## Public models

### `DCSweepPlan`

The immutable plan records:

- stable plan ID and version;
- explicit stimulus channel;
- explicit V or mV unit;
- ordered finite setpoints;
- repetition count for every setpoint;
- the versioned `DCSweepAnalysisConfig`;
- optional versioned `DCSweepAcceptanceCriteria`.

The stimulus, measured input, and measured output channels must be distinct. The plan, analysis, and criteria units must agree. `expected_points` and `expected_measurements` expose the exact planned acquisition size.

### `DCSweepAcquisitionStep`

One step links a setpoint index and repetition index to the exact input and output Measurement record IDs. This means a later report can reconstruct which records belonged to each command without replacing the original Measurements.

### `DCSweepRunnerResult`

The result preserves:

- the original plan;
- observed capabilities when available;
- every collected Measurement, including a possible final unpaired input;
- every completed setpoint/read pair;
- optional analysis and evaluation;
- one final `TestRunResult` with exact evidence and raw-record IDs.

The model rejects duplicate IDs, source mismatches, wrong units, wrong alternating channel order, corrupted step order, mismatched metadata, and PASS/FAIL without an evaluation.

## Safety gates before output

`run_dc_sweep(...)` accepts only a disconnected `DeviceAdapter`. Before `set_stimulus` can run, it verifies all of the following:

1. the plan, ValidationConfig, metadata, settle callback, and abort callback are typed correctly;
2. `allow_output=true` is explicit;
3. configuration and metadata evidence sources match the adapter;
4. configuration/profile/test metadata are internally consistent;
5. stimulus and analysis channels are enabled with explicit matching units;
6. every setpoint is inside the configuration safe range;
7. the adapter advertises both measured input channels and `READ_MEASUREMENT`;
8. the adapter advertises the requested DAC/PWM channel and output command;
9. the adapter advertises `SAFE_SHUTDOWN`;
10. configured safe ranges fit inside the reported device ranges;
11. metadata device identity matches the confirmed capabilities.

All setpoints are checked before the first write. The runner never infers capability or range from a board name.

## Outcome rules

| Situation | Outcome | May contain partial Measurements? | May claim PASS? |
|---|---|---:|---:|
| Required command/channel/unit/safe shutdown is absent | `UNSUPPORTED` | No | No |
| Explicit abort or keyboard interruption | `INCOMPLETE` | Yes | No |
| Adapter reaches typed end-of-data early | `INCOMPLETE` | Yes | No |
| Read, callback, connection, configuration, or adapter error | `ERROR` | Yes | No |
| Safe shutdown or disconnect fails | `ERROR` | Yes | No |
| Complete acquisition but analysis/criteria are incomplete | `INCOMPLETE` | Complete set | No |
| Complete acquisition, successful cleanup, complete criteria evaluation | `PASS` or `FAIL` | Complete set | Yes |

`ERROR` and `INCOMPLETE` retain collected evidence IDs. They do not run a partial linear fit. Missing requirements use stable codes such as `runner-aborted`, `acquisition-end-of-data`, `execution-error:AdapterError`, and `cleanup-error:AdapterError`.

## Waiting, repetition, and interruption

The runner calls the injected `settle(seconds)` function after every setpoint. The duration comes from `ValidationConfig.timeouts.settle_s`. Production callers may use the default `time.sleep`; tests inject a no-wait recorder so they remain deterministic and fast.

The abort callback is checked before each output and again after settling. If it requests an abort, the runner stops acquisition, disconnects through the adapter safety lifecycle, and returns `INCOMPLETE`.

The v1 runner does not yet enforce a real-time total deadline or command timeout. Those timeout values remain configuration data for future transport-aware adapters; this limitation is explicit rather than simulated.

## Read-only adapters remain read-only

`SimulatorAdapter` and `CsvReplayAdapter` do not advertise output or safe-shutdown commands. Step 4 integration tests pass both through the same runner and verify:

- `UNSUPPORTED` is returned;
- no Measurement is consumed;
- no setpoint is issued;
- the adapter is disconnected;
- source remains `SYNTHETIC` or `CSV_REPLAY`.

The output-capable reference adapter exists only inside the test suite with `HOST_TEST` provenance. This protects the product architecture from quietly turning a read-only simulator into a pretend physical controller.

## Evidence boundary

- A runner `PASS` means only that the supplied HOST_TEST records met the supplied fixture criteria after the host lifecycle completed.
- Successful invocation of `safe_shutdown` proves a Python call path, not a physical voltage or relay state.
- Numeric ranges and criteria in tests are fixtures, not validated AFE specifications.
- No serial port, ADC, DAC, PWM, MSP430, instrument, wiring, or physical AFE was used.
- Verified hardware claims remain zero.

See [adapter safety](adapters.md), [DC analysis](dc-sweep-analysis.md), [DC criteria](dc-sweep-criteria.md), [TestRun semantics](capabilities-and-test-runs.md), and the [Step 4 report](../reports/software-phase3-step4.md).
