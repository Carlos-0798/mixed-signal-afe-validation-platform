# Software Phase 2 Step 6 Report

**Date:** 2026-08-30<br>
**Milestone:** CsvReplayAdapter playback lifecycle and controls<br>
**Evidence class:** HOST_TEST / CSV_REPLAY<br>
**Hardware used:** none

## Outcome

Software Phase 2 Step 6 is complete. The formal package now exposes a controller-neutral, read-only `CsvReplayAdapter` that consumes a previously validated immutable CSV Replay v1 dataset through the same `DeviceAdapter` port as Simulator.

The adapter supports explicit channel capabilities, independent sequential cursors, immediate or scaled timestamp timing, runtime speed changes, pause/resume, channel and whole-dataset end state, and typed EOF. It passed the shared read-only adapter contract used by the reference fixture and Simulator.

## Design decisions

### Explicit configuration instead of inference

`CsvReplayAdapterConfig` is immutable and versioned as `csv-replay-adapter-config.v1`. Every replay channel has an explicit analog/digital role and unit; analog channels also require a matching `SafeRange`.

The adapter rejects undeclared dataset channels and unit mismatches. It never infers whether a number is analog, digital, volts, millivolts, or an electrical safe range. The configured replay range is a host-software capability boundary, not a validated hardware limit.

### Independent cursors

Each channel advances independently. Reading `afe.ch0.input` does not consume `afe.ch0.output` or a digital state record. This matches the existing Simulator contract and prevents upper-layer read order from silently changing other streams.

### Timing and runtime controls

- `IMMEDIATE` mode never waits;
- `SCALED` mode requests `source timestamp delta / current speed multiplier` between consecutive records on the same channel;
- the first record and equal-timestamp records do not wait;
- speed must be numeric, finite, and greater than zero;
- pause blocks reads without consuming the current record;
- resume continues from the same cursor;
- reconnect resets cursors, pause state, and runtime speed to configuration defaults.

The sleeper is injectable. Tests record requested delays rather than waiting on wall-clock time, so results are deterministic and fast.

### EOF and provenance

`channel_at_end()` reports a specific channel, `at_end` reports all configured channels, and reading an exhausted channel raises `ReplayEndOfData`. EOF is therefore an expected typed condition rather than a fake Measurement, `None`, or a generic error string.

Every returned Measurement preserves the source record's timestamp, value, unit, status, quality flags, and record reference. The new record ID is namespaced as `csv-replay:<dataset>:<record>`, while `raw_record_id` retains the original record ID. Current provenance is always `CSV_REPLAY`. Even a file row declaring `BENCH_DMM` cannot become current bench evidence; that declaration remains available only through the immutable source dataset for audit.

## Stable public API

- `CSV_REPLAY_ADAPTER_CONFIG_SCHEMA_VERSION`;
- `ReplayChannelKind`;
- `ReplayTimingMode`;
- `ReplayChannelConfig`;
- `CsvReplayAdapterConfig`;
- `CsvReplayAdapter`;
- `ReplayEndOfData`.

## Executed verification

| Gate | Result |
|---|---|
| CsvReplayAdapter focused unit tests | PASS — 45 |
| Shared CsvReplayAdapter contract | PASS — 8/8 checks |
| Focused adapter module coverage | PASS — 185/185 statements, 100% |
| Full pytest suite | PASS — 600 tests |
| Formal package statement coverage | PASS — 2,028/2,028, 100% |
| Full-repository Ruff | PASS |
| mypy on `src`, `dashboard`, `tools`, and `tests` | PASS — 61 source files |
| Local dependency check | PASS — no broken requirements |
| Isolated sdist and wheel build | PASS |
| Repository-external wheel install and public API smoke | PASS — pause/resume, read, provenance, EOF |
| Installed-package dependency check | PASS — no broken requirements |

## Beginner explanation

The parser and adapter solve two different problems. The parser proves that the file is complete and unambiguous. The adapter turns that trusted frozen dataset into a controllable data source that the rest of the product can use exactly like Simulator.

Keeping those responsibilities separate means a malformed file fails before playback begins, while pause, speed, and EOF behavior can be tested without repeatedly parsing text. It also lets future test runners depend on one device interface instead of knowing CSV column details.

## Evidence boundary

No serial port, controller, ADC, DAC, PWM, instrument, analog component, wiring, voltage, or physical timing was exercised. Scaled timing tests prove only the requested delay calculation passed to an injected host function. They do not prove real-time Windows scheduling, UART timing, or any hardware behavior.

`VERIFIED_BENCH` remains zero.

## Next checkpoint

Software Phase 2 Step 7 will add one upper-layer workflow that can drive both Simulator and CSV Replay. When a requested operation is unavailable, the workflow must produce an explicit `UNSUPPORTED` result without crashing, pretending the operation ran, or disabling unrelated capabilities.
