# Software Phase 1 Step 5 Report

**Date:** 2026-08-29  
**Milestone:** single CRC implementation and bounded ASCII CSV framing  
**Evidence class:** HOST_TEST  
**Hardware evidence:** None

## Outcome

Software Phase 1 Step 5 is complete. CRC-16/CCITT-FALSE and generic AFE ASCII CSV framing now live in the installable `analog_validation.protocol` package. Repository source contains one CRC function definition.

The Phase 0 `dashboard.protocol` module remains a temporary compatibility façade for telemetry and command business parsing, but it reexports the formal CRC/framing objects rather than maintaining copies. Existing legal telemetry and command records continue to pass their regression tests.

## Added or migrated

- `protocol/crc.py` with explicit polynomial, initial value, and xor-out constants;
- `protocol/framing.py` with a frozen `Frame`, strict printable ASCII tokens, LF/CRLF handling, 128-byte limit, uppercase CRC envelope, and typed errors;
- five fixed CRC vectors in `test-data/golden/crc16_ccitt_false.json`;
- an sdist manifest that includes unit tests and golden test data without adding them to the runtime wheel;
- formal root-package exports for CRC and framing;
- a temporary legacy façade that points to the same implementation objects;
- beginner documentation explaining layers, safety limits, and recovery boundaries.

## Executed verification

| Check | Actual result |
|---|---|
| Full pytest suite | PASS: 184 tests |
| Formal package coverage | PASS: 100% of 523 executable statements |
| Legacy telemetry/command regression | PASS: all 12 existing protocol tests |
| CRC golden vectors | PASS: 5 vectors, including `123456789 -> 29B1` |
| Exact serialized limit | PASS: 128 bytes accepted; 129 bytes rejected |
| ASCII/token/terminator/CRC boundary tests | PASS |
| Specific `FramingError` / `FrameTooLong` / `CrcMismatch` behavior | PASS |
| Legacy façade object identity | PASS: CRC, encode, decode, Frame are formal objects |
| Source implementation search | PASS: one `def crc16_ccitt_false`, in `protocol/crc.py` |
| Synthetic telemetry compatibility pipeline | PASS: 20/20 parsed, sequence 0–19 |
| Ruff on formal package, protocol façade, tools, and tests | PASS |
| mypy on `src`, `dashboard`, `tools`, and `tests` | PASS: no issues in 36 source files |
| Isolated sdist and wheel build | PASS |
| Source archive reproducibility content | PASS: unit tests and CRC golden JSON included |
| Repository-external wheel install | PASS |
| Installed public CRC + encode/decode smoke | PASS: output `29B1 ('AFE', 'CHECK', '1')` |
| Installed-package dependency check | PASS: no broken requirements |

## Verification anomaly retained for traceability

The first repository-external smoke command failed before importing the package because nested PowerShell/Python quoting produced a Python `SyntaxError` (`'(' was never closed`). The wheel build and installation had already succeeded, but that command was not counted as product verification.

The smoke check was rerun in the same external virtual environment with unambiguous quoting. It imported the wheel's public API, calculated `29B1`, completed an encode/decode round trip, and passed `pip check`.

## Compatibility and intentional tightening

- Existing valid Phase 0 telemetry and command records remain accepted.
- The encoder and decoder now enforce the documented “printable ASCII without whitespace” rule rather than accepting some internal whitespace/control characters.
- A bare CR is rejected; LF and CRLF remain accepted.
- A caller that already removed the record delimiter may still pass one complete record without a terminator.
- Profile-specific field types and ranges remain in the legacy façade until Step 6.

## Evidence and safety limit

All evidence is HOST_TEST. The 20-frame pipeline used `source=SYNTHETIC`. No UART port, cable, voltage level, MCU, AFE circuit, timing, electromagnetic environment, baud-rate tolerance, packet-loss recovery, or firmware CRC implementation was tested.

The 128-byte single-record decoder is not a streaming serial receiver. Buffering partial frames, handling concatenated frames, discarding an overlong frame through the next LF, retry policy, and sequence tracking remain later transport work.

## Remaining Phase 1 work

- define the versioned AFE v1 telemetry, command, and capability profile;
- map profile records to the new domain models;
- establish versioned configuration models and validation;
- add business-message golden files, migrate legacy callers, and close Phase 1 documentation.
