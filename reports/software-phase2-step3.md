# Software Phase 2 Step 3 Report

**Date:** 2026-08-30<br>
**Milestone:** deterministic read-only SimulatorAdapter<br>
**Evidence class:** HOST_TEST and SYNTHETIC<br>
**Hardware used:** none

## Outcome

Software Phase 2 Step 3 is complete. The formal package now contains its first concrete product adapter: a deterministic, read-only `SimulatorAdapter` that advertises explicit capabilities and returns provenance-aware `SYNTHETIC` Measurements through the common `DeviceAdapter` API.

The simulator is a repeatable software data source, not a physical AFE model or bench measurement.

## Implemented behavior

- immutable `SimulatorConfig` schema `simulator-config.v1`;
- configurable integer seed, non-negative sample interval, device/profile identity, and channel name;
- default one-channel capability: `afe.ch0.input`, mV, 0–3300 mV;
- read-only `READ_MEASUREMENT` command set with no DAC/PWM or safe-shutdown claim;
- fixed deterministic default epoch and optional injected timezone-aware clock;
- UTC timestamps advanced by the configured interval;
- stable record/raw IDs and explicit `SYNTHETIC` source;
- disconnect/reconnect resets the stream to its deterministic beginning;
- the real SimulatorAdapter inherits all eight shared adapter contract checks.

## Single generator migration

The frozen Phase 1 AFE formula moved from the repository-local CLI tool into `analog_validation.adapters.simulator.generate_afe_telemetry`. The CLI wrapper and the 100-frame integration test now import this formal generator.

The 100-frame encoded stream remains unchanged:

```text
SHA-256 dad90b14abfed3d2a645902458d40b204242f233766d13abdc7fc6b5894cbb94
```

## Executed verification

| Gate | Result |
|---|---|
| Simulator-specific unit tests | PASS — 32 |
| Shared contract against real SimulatorAdapter | PASS — 8 |
| Frozen 100-frame AFE integration | PASS — unchanged hash |
| Full pytest suite | PASS — 408 tests |
| Formal package statement coverage | PASS — 1,491/1,491, 100% |
| Full-repository Ruff | PASS |
| mypy on `src dashboard tools tests` | PASS — 53 source files |
| Local dependency check | PASS — no broken requirements |
| Isolated sdist and wheel build | PASS |
| Simulator module in wheel and five Step 3 artifacts in sdist | PASS |
| Repository-external wheel install and three-point simulator smoke | PASS |
| Installed-package dependency check | PASS — no broken requirements |

## User-facing smoke

With seed 430 and a 10 ms interval, the formal adapter returned:

| Record | Value | Unit | Source | Timestamp offset |
|---|---:|---|---|---:|
| `simulator-00000000` | 800.0 | mV | SYNTHETIC | 0 ms |
| `simulator-00000001` | 879.0 | mV | SYNTHETIC | 10 ms |
| `simulator-00000002` | 953.0 | mV | SYNTHETIC | 20 ms |

The CLI wrapper emitted the matching first three AFE v1 frames and the adapter returned to `DISCONNECTED` after explicit disconnect.

## Explicit evidence boundary

No serial port, microcontroller, ADC, DAC, PWM, instrument, AFE circuit, wiring, voltage, or physical shutdown was used. The current waveform is a deterministic software formula. It does not establish analog accuracy, noise, gain, saturation, hysteresis, timing accuracy, or electrical safety.

## Next checkpoint

Step 4 will add explicit, versioned controls for gain, offset, noise, saturation, hysteresis, and selected controlled faults. Fixed seed/config/clock behavior must remain reproducible, and every output record must remain `SYNTHETIC`.
