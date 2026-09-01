# Software Phase 4 Step 7 Verification Report

**Date:** 2026-08-30 (America/New_York)<br>
**Checkpoint:** optional pyserial backend and MSP430 receive-only HIL<br>
**Status:** complete with an exact-firmware-identity limitation<br>
**Physical scope:** MSP430 LaunchPad/eZ-FET UART receive path only<br>
**Verified AFE hardware claims:** 0

**Implementation commit:** `ccff7c322af7adf5dc97ca64545060abe1342898`

## Outcome

Step 7 is complete. Analog Validation Studio now has an optional, packaged
`analog_validation_pyserial` integration and a repository-owned passive HIL
tool. The accepted capture opened `MSP Application UART1 (COM4)` once, received
five consecutive CRC-valid MSP430 telemetry records through the product's
`SerialAdapter` and `ReadWorkflow`, then closed the port. No application command
or application byte was sent.

This is a narrow physical interoperability result. It is not AFE validation,
external-sensor validation, fan testing, or proof of the exact firmware image.

## What was implemented

- optional `serial` package extra: `pyserial>=3.5,<4`;
- independently packaged `analog_validation_pyserial.PySerialBackend`;
- lazy dependency loading, so the base product still imports without pyserial;
- logical-port discovery that excludes hardware IDs and USB serial numbers;
- exact baud/data/parity/stop mapping, finite per-read timeout, and bounded byte
  count;
- pre-open inactive DTR/RTS requests and disabled software/hardware flow control;
- receive/disconnect mapping into the existing driver-neutral session contract;
- idempotent close with no public driver-object or write escape hatch;
- create-new, Git-ignored `msp430-receive-only-hil.v1` evidence capture;
- strict distinction between CRC Protocol v1 records and documented legacy
  `HB` diagnostic lines.

The formal `src/analog_validation` core continues to import only the standard
library and its own package. The pyserial package is a separate, lower-level
integration namespace and may not import profiles, adapters, workflows,
analysis, runners, exports, Dashboard code, or tools.

## Accepted physical capture

Local evidence file (intentionally not committed):

`work/evidence/msp430-read-only-hil-20260831T021336Z.json`

| Property | Observed result |
|---|---|
| Evidence schema | `msp430-receive-only-hil.v1` |
| SHA-256 | `3BD8E67F80E59B78611611F0C29680D25DDDD1AE5D2FF99C7FBDAC960E2457C7` |
| File size | 25,457 bytes |
| Selected port | `COM4` — `MSP Application UART1 (COM4)` |
| Serial settings | 115200 baud, 8-N-1, 512-byte read bound, 128-byte record bound |
| Capture duration | 2026-08-31 02:13:36Z to 02:13:41Z |
| Product outcome | `PROTOCOL_COMPATIBLE_RECEIVE_ONLY` |
| Workflow | `COMPLETED`, source `BENCH_CONTROLLER` |
| Telemetry | 5 requested / 5 parsed |
| Derived Measurements | 25 |
| CRC | 5/5 telemetry records `VALID` |
| Telemetry sequence | 27917, 27918, 27919, 27920, 27921 |
| Sequence anomalies | 0 |
| Uptime | 27,917,000 through 27,921,000 ms; +1,000 ms per frame |
| Known legacy heartbeat | 5/5 exact syntax and aligned to TEL sequence/uptime |
| Unexpected rejected records | 0 |
| Empty bounded reads | 9 (normal timeout behavior while waiting for 1 Hz telemetry) |
| Open / close | 1 / 1 |
| Disconnect / reconnect | 0 / 0; recovery was not deliberately exercised |
| Application write calls / bytes | 0 / 0 |

All five telemetry records reported state `FAULT` and fault mask `0x0015`:

- `DS18B20_MISSING`;
- `NTC_RANGE`;
- `INA219_COMM`.

Both temperatures were the raw unavailable sentinel `-32768`; bus voltage,
current, and power fields were zero while `INA219_COMM` was set; PWM was zero.
The profile therefore mapped the unavailable temperature, voltage, and current
channels to `value=None`, `INVALID`, and `MISSING` rather than treating raw zero
or the sentinel as a physical reading. This is consistent with a board lacking
those external devices, but it is not proof of wiring state.

## Legacy heartbeat finding and corrected assessment

The first physical capture completed the workflow but was conservatively
classified `ACQUIRED_WITH_ANOMALIES` because every CRC-valid `TEL` was preceded
by a no-CRC `HB` line. Its immutable local evidence is:

- `work/evidence/msp430-read-only-hil-20260831T021150Z.json`;
- SHA-256
  `ED6DAC29FC2A804C20AB36C5C946BE446AD0316960E38E3B3661C2C3FFA0E188`.

Read-only comparison with the peer project established that this is documented
behavior, not an unexplained damaged frame: its Protocol v1 document says
temporary `BOOT/READY/HB` lines share the UART and are ignored before the
production parser; the current main loop emits `write_status("HB")` immediately
before `send_telemetry()` each second.

The correction did not relax the strict Protocol v1 parser. `HB` remains a
retained `FramingError`/`REJECTED` raw event because it has no CRC. The HIL
assessment now recognizes only the exact documented heartbeat syntax and also
requires matching sequence and uptime in a captured TEL record. New tests prove
that malformed or unaligned heartbeat text still produces
`ACQUIRED_WITH_ANOMALIES`. The second physical capture then passed under that
reviewed rule. The first result is preserved rather than overwritten or hidden.

## Executed software verification

| Gate | Result |
|---|---|
| Optional-backend unit tests | PASS — discovery, line mapping, timeout, read bounds, disconnect, close, missing dependency, and no-write surface |
| HIL-tool integration tests | PASS — full memory chain, known heartbeat, malformed/unaligned heartbeat, failure evidence, missing port, bounds, and no-overwrite |
| Optional package coverage | PASS — 127/127 statements, 100% |
| Full pytest suite | PASS — 1,513 tests |
| Formal + optional package coverage | PASS — 7,325/7,325 statements, 100% |
| Full-repository Ruff | PASS |
| mypy | PASS — 146 files |
| Dependency check | PASS |
| Isolated sdist/wheel build | PASS |
| Wheel contents | PASS — backend and `py.typed` included; serial extra metadata present |
| External base install without pyserial | PASS — imports work, typed missing-dependency gate, no write method |
| External install with serial extra | PASS — pyserial 3.5 and COM4/COM5 discovery |
| Physical receive-only SerialAdapter -> ReadWorkflow | PASS with limitations described above |

The final isolated artifacts were:

| Artifact | Size | SHA-256 |
|---|---:|---|
| `mixed_signal_afe_validation_platform-0.1.0.dev0-py3-none-any.whl` | 156,305 bytes | `04AB18BC3FD3625AD7C23FE408F1E24611D81978BB749F2ED37DB9A85FB41655` |
| `mixed_signal_afe_validation_platform-0.1.0.dev0.tar.gz` | 278,433 bytes | `F2A4131D4A2E58855A0FF3E7591F75961006D41C8772664B1A5F92A4B58C40AB` |

The wheel contains the optional backend and `py.typed` marker plus the serial
extra metadata. The sdist contains the HIL tool and its integration tests.

The first base-wheel smoke command had an invalid hand-written one-line Python
quote and stopped with `SyntaxError` before product behavior was exercised. The
same installed environment was retested through standard input and passed. This
harness correction is retained in the record and is not presented as an
initial product pass.

Likewise, the first one-line archive-content inspection after the final build
had an unterminated quoted string and stopped before reading either artifact.
The already-successful build was not rerun or relabeled; a standard-input
inspection then confirmed all five expected wheel/sdist entries above.

## Safety and evidence boundary

The accepted evidence supports a physical controller-UART compatibility claim
for the five observed records. It does not support a claim that:

- the exact current firmware is `0.3.2-phase6-protocol`; passive Protocol v1
  telemetry carries no firmware version, so identity remains
  `UNCONFIRMED_PASSIVE_ONLY`;
- pyserial, Windows, or the eZ-FET can never produce an RTS/DTR glitch; the
  application requests both inactive before open, but the driver controls the
  electrical transition;
- disconnect/reconnect recovery works on this physical setup; no disconnect was
  intentionally induced;
- external DS18B20, NTC, INA219, MOSFET, fan, 5 V, or wiring was tested;
- the AFE exists or its gain, cutoff, hysteresis, saturation, protection, ADC,
  noise, bandwidth, or voltage range was measured;
- peer-project firmware tests, FRAM tests, or soak evidence belong to this
  repository.

`BENCH_CONTROLLER` here identifies the source of received controller bytes. It
does not promote unavailable external-sensor fields into valid bench
measurements. Verified AFE hardware performance claims remain zero.

## Next checkpoint

Software Phase 4 Step 8 will freeze the new public API and representative
profile/transport/adapter results, rerun release-style compatibility and build
gates, and separate HOST_TEST from the narrow Step 7 BENCH_CONTROLLER evidence
in final Phase 4 documentation. It will not add AFE hardware claims.
