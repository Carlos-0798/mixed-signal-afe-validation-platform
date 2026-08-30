# Software Phase 4 Step 1 — Transport Stream and Sequence Foundation

**Date:** 2026-08-30<br>
**Checkpoint:** 1 of 8<br>
**Evidence class:** HOST_TEST<br>
**Hardware used:** none

## Outcome

Step 1 is complete. The formal package now contains a profile-neutral bounded byte-stream state machine and a profile-configurable modular sequence tracker. They establish the transport boundary needed by future AFE and MSP430 profiles without adding a serial dependency, opening a COM port, importing either device's business logic, or changing the frozen Phase 1–3 public namespaces.

## What was implemented

`analog_validation.transport.stream` provides:

- arbitrary bytes-like chunk input;
- fragmented and coalesced LF-delimited record recovery;
- raw byte preservation, including CRLF, non-ASCII data, and empty records;
- an exact record-length limit that includes LF;
- bounded overlong-record discard until the next LF;
- structured overlong issues with discarded-byte counts;
- deterministic reset information for disconnect/reconnect handling.

`analog_validation.transport.sequence` provides:

- profile-selected sequence widths from 2 through 64 bits;
- explicit `FIRST`, `IN_ORDER`, `GAP`, `DUPLICATE`, and `OUT_OF_ORDER` results;
- missing-record counts;
- modular wrap handling for AFE 16-bit and MSP430 32-bit sequences;
- a conservative half-range rule;
- a high-water mark that is not moved backward by duplicates or old frames.

## Why this is a separate layer

The byte-stream state machine recognizes only LF and a length limit. It deliberately does not validate ASCII, CSV, CRC, namespaces, sequence field locations, telemetry units, or device capabilities. Those responsibilities belong to independent profiles. This allows AFE and MSP430 to share transport mechanics while remaining separate products with separate message semantics.

## Compatibility and safety boundaries

- Existing `analog_validation.protocol.encode_frame()` and `decode_frame()` behavior is unchanged.
- Frozen Phase 1–3 top-level and protocol `__all__` manifests are unchanged.
- No `pyserial`, board SDK, COM-port name, VID/PID, pin map, register, or firmware dependency was added.
- No output command, ARM state, safe-shutdown claim, device capability, or Measurement was created.
- No MSP430 test, soak, FRAM, or hardware evidence was imported as Analog Validation Studio evidence.
- No physical AFE or controller behavior was verified.

## Verification

| Gate | Result |
|---|---|
| Step 1 focused tests | PASS — 32 |
| Step 1 module coverage | PASS — 158/158 statements, 100% |
| Full regression | PASS — 1,079 |
| Formal package coverage | PASS — 5,752/5,752 statements, 100% |
| Full-repository Ruff | PASS |
| mypy on `src`, `dashboard`, `tools`, and `tests` | PASS — 104 source/test files |
| sdist and wheel build | PASS — transport package included |
| Repository-external wheel install/smoke | PASS — bounded feed and 32-bit wrap |
| Hardware or serial test | NOT RUN |

The first baseline invocation reached 1,040 passes and seven setup errors because the requested `work/` pytest parent directory did not exist. No product assertion failed. After creating that generated, ignored parent directory, the authoritative unchanged baseline completed 1,047/1,047. The final post-implementation run completed 1,079/1,079 with full formal-package coverage.

The first external-install location was nested too deeply under the repository and pip failed while writing temporary metadata because Windows long-path support was unavailable. The build itself had succeeded and included all three transport files, but that install was not accepted. A new clean virtual environment under the shorter system temporary path installed the wheel successfully and passed bounded-record plus 32-bit wrap smoke tests. One initial smoke expression also used an incorrectly escaped newline literal; its diagnostic output was retained and the corrected byte construction passed in the same clean installed environment.

## Evidence boundary

This checkpoint proves Python byte-stream recovery and modular sequence classification under host tests. It does not prove UART electrical behavior, baud accuracy, OS serial discovery, timeout timing, reconnect behavior on a physical device, AFE protocol interoperability, MSP430 profile interoperability, or any sensor/analog/fan measurement.

## Next checkpoint

Step 2 will separate the profile-neutral token/CRC envelope from the currently AFE-specific framing wrapper, preserve every frozen AFE v1 byte/error contract, and define an explicit channel-name mapping before either real serial profile is implemented.
