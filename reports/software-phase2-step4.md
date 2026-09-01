# Software Phase 2 Step 4 Report

**Date:** 2026-08-30<br>
**Milestone:** configurable simulator non-idealities and controlled faults<br>
**Evidence class:** HOST_TEST and SYNTHETIC<br>
**Hardware used:** none

## Outcome

Software Phase 2 Step 4 is complete. `SimulatorAdapter` now provides a deterministic, read-only software model for gain, offset, noise, saturation, Schmitt hysteresis, missing samples, communication failures, and CRC failures.

This is a controllable test fixture for developing the future workflows. It is not an analog circuit solver, hardware emulator, instrument reading, or physical AFE validation.

## Implemented behavior

- immutable `SimulatorConfig` controls gain, offset in mV, Gaussian-noise standard deviation, saturation limits, Schmitt thresholds, fault type, and fault cadence;
- all numeric configuration is finite, range-checked, and normalized to floats;
- three distinct public channels are declared:
  - `afe.ch0.input` — source waveform in mV;
  - `afe.ch0.output` — configured transfer function in mV;
  - `afe.ch0.threshold` — Schmitt state in boolean units;
- output follows `gain × input + offset + seeded noise`, then clamps to the configured lower/upper limits;
- a clamped output is `SUSPECT` with the `SATURATED` quality flag;
- Schmitt state switches high at the upper threshold, low at the lower threshold, and holds its previous state inside the band;
- every channel owns an independent seeded stream and read index, so reading one channel does not advance another;
- reconnecting resets samples, noise, hysteresis state, and fault cadence;
- every produced Measurement remains explicitly `SYNTHETIC`.

## Controlled-fault semantics

| Mode | Public result |
|---|---|
| `NONE` | normal configured sample |
| `MISSING_SAMPLE` | `INVALID` Measurement with `MISSING` and `COMMUNICATION_ERROR` |
| `COMMUNICATION_ERROR` | stable `AdapterError` |
| `CRC_ERROR` | stable `CrcMismatch` |

The cadence is deterministic and counted per channel. An affected read consumes its scheduled sample; the following successful read therefore represents the next time point.

`CRC_ERROR` models the error path exposed to upper software. It does not claim that a corrupted byte stream passed through a physical UART; streaming serial transport is a later phase.

## Compatibility preserved

- the existing `afe.ch0.input` values, timestamps, and `simulator-00000000` record-ID pattern remain compatible;
- the frozen AFE telemetry generator and CLI formula were not changed;
- the 100-frame encoded stream still passes the frozen SHA-256 regression:

```text
dad90b14abfed3d2a645902458d40b204242f233766d13abdc7fc6b5894cbb94
```

- the adapter remains controller-neutral and read-only: it advertises no DAC, PWM, or automated physical output.

## Executed verification

| Gate | Result |
|---|---|
| Simulator unit tests | PASS — 69 |
| Shared contract against SimulatorAdapter | PASS — 8 |
| Focused simulator module coverage | PASS — 208/208 statements, 100% |
| Full pytest suite | PASS — 445 tests |
| Formal package statement coverage | PASS — 1,601/1,601, 100% |
| Frozen 100-frame AFE integration | PASS — unchanged hash |
| Full-repository Ruff | PASS |
| mypy on `src dashboard tools tests` | PASS — 54 source files |
| Local dependency check | PASS — no broken requirements |
| Isolated sdist and wheel build | PASS |
| Repository-external wheel install | PASS |
| Installed public API saturation/missing/threshold smoke | PASS |
| Installed-package dependency check | PASS — no broken requirements |

## Beginner explanation

The simulator separates a mathematical expectation from evidence:

1. input is a repeatable synthetic waveform;
2. gain and offset model the ideal transfer relationship;
3. seeded noise adds the same pseudo-random deviations whenever the seed is repeated;
4. saturation represents the inability of an output to exceed its configured limits;
5. hysteresis remembers state so noise inside the threshold band does not cause rapid toggling;
6. controlled faults let the future runner prove that it reports bad data safely.

Determinism is essential for automated regression: when code changes, a changed result can be attributed to the code or configuration rather than uncontrolled randomness.

## Explicit evidence boundary

No serial port, MSP430, STM32, RP2040, ADC, DAC, PWM, function generator, oscilloscope, multimeter, analog component, wiring, voltage, or physical shutdown was used. The configured gain, noise, limits, and thresholds are software inputs, not measured component values. `VERIFIED_BENCH` remains zero.

## Next checkpoint

Software Phase 2 Step 5 will define and strictly parse a versioned immutable CSV replay format. It must preserve explicit units, UTC timestamps, source, quality, original-record identity, and an unambiguous end condition without modifying source files or guessing missing fields.
