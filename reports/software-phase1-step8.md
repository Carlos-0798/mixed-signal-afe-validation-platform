# Software Phase 1 Step 8 and Closure Report

**Date:** 2026-08-29<br>
**Milestone:** golden compatibility, legacy migration, and Software Phase 1 closure<br>
**Evidence class:** HOST_TEST<br>
**Hardware used:** none

## Outcome

Software Phase 1 is complete. The repository now has one installable, versioned, controller-neutral core for domain data, capability and safety semantics, CRC/framing, the AFE v1 profile, and strict configuration. Step 8 froze public compatibility behavior, migrated the remaining Phase 0 protocol users, added a deterministic integration pipeline, and made the formal-core dependency boundary executable.

This is a core-foundation milestone, not the software MVP. DeviceAdapter, full simulation/replay workflows, runners, CLI, Dashboard, serial transport, and hardware remain later phases.

## Frozen compatibility contract

| Artifact | Purpose | Cases |
|---|---|---:|
| `afe_v1_valid.csv` | Exact supported wire records | 20 |
| `expected_frames.json` | Expected model type and field meaning | 20 |
| `afe_v1_invalid.csv` | Base64 inputs, expected error family, message pattern | 9 |
| `crc16_ccitt_false.json` | CRC algorithm vectors | 5 |

Every valid record must parse to the frozen model meaning and re-encode byte-for-byte. Invalid records cover bad CRC, unsupported version, field count, lowercase fault flags, threshold range, unsupported command, unknown message type, non-ASCII bytes, and the 128-byte length boundary.

## Deterministic synthetic pipeline

The repository test now performs this 100-frame flow:

```text
fixed seed generator
  -> AfeTelemetry
  -> AFE v1 encode + CRC
  -> AFE v1 parse
  -> exact object equality
  -> four Measurement records per frame
  -> explicit SYNTHETIC and non-BENCH assertions
```

- seed: `430`;
- interval: `10 ms`;
- frames: `100`;
- derived Measurements: `400`;
- frozen stream SHA-256: `dad90b14abfed3d2a645902458d40b204242f233766d13abdc7fc6b5894cbb94`.

The hash detects accidental generator or wire-format drift. It does not make the synthetic values physical evidence.

## One-time legacy migration

- `tools/telemetry_simulator.py` now imports `AfeTelemetry` and `encode_afe_message` from the formal package;
- the repository-root `sys.path` injection was removed;
- obsolete unversioned `dashboard/protocol.py` was removed;
- obsolete shared `dashboard/models.py` was removed;
- the superseded unversioned protocol regression file was replaced by formal unit/golden/integration tests;
- legacy DC and hysteresis result dataclasses were localized beside those legacy algorithms until their planned Software Phase 3 migration;
- `src/analog_validation` is verified not to import serial, GUI, board SDK, `dashboard`, `tools`, or any third-party runtime dependency.

Historical reports and the Phase 0 audit retain old filenames as dated evidence; they are not current API documentation.

## Executed verification

| Gate | Result |
|---|---|
| Full pytest suite | PASS — 324 tests |
| Formal package statement coverage | PASS — 1,211/1,211, 100% |
| Golden protocol tests | PASS — 30 tests: manifest + 20 valid + 9 invalid |
| Synthetic integration | PASS — 100 frames and 400 Measurements |
| Architecture boundary | PASS — 2 tests |
| Current DC/hysteresis regression | PASS |
| Full-repository Ruff | PASS |
| mypy on `src dashboard tools tests` | PASS — 44 source files |
| Local dependency check | PASS — no broken requirements |
| Isolated sdist/wheel build | PASS |
| Golden CSV/JSON and architecture/golden/integration tests in sdist | PASS |
| Repository-external wheel install/import | PASS |
| Installed AFE/configuration smoke | PASS — `0.1.0.dev0 True True True False` |
| Installed-package dependency check | PASS — no broken requirements |

Coverage applies only to the formal `src/analog_validation` package. Legacy analysis regression files, tools, documents, future adapters, runners, UI, firmware, and hardware are outside that percentage.

## Phase 1 exit criteria

| Criterion | Result |
|---|---|
| One formal `src/analog_validation` core | PASS |
| No duplicate Phase 0 protocol/shared models | PASS |
| Stable versions and error families | PASS |
| Strict non-executable configuration | PASS |
| AFE wire/model compatibility frozen | PASS |
| Deterministic 100-frame integration in pytest | PASS |
| Core free of serial, GUI, board SDK, and third-party runtime imports | PASS |
| Host quality gates and external install | PASS |
| Hardware state remains deferred/unverified | PASS |

## Explicitly not verified or implemented

- no complete SimulatorAdapter or CsvReplayAdapter;
- no DeviceAdapter lifecycle or contract test;
- no serial streaming, retry, timeout, or sequence tracker;
- no test runner, calibration workflow, frequency-response workflow, CLI, Dashboard, or end-user report;
- no controller firmware or MSP430 compatibility profile;
- no physical AFE, wiring, ADC/DAC/PWM, instrument, voltage, accuracy, noise, timing, or shutdown evidence.

## Next milestone

Software Phase 2 will establish a common DeviceAdapter contract, move the deterministic generator behind a complete SimulatorAdapter, implement immutable CSV replay, and verify capability degradation through adapter contract tests. It remains software-only.
