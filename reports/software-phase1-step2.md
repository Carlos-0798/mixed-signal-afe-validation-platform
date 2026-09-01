# Software Phase 1 Step 2 Report

**Date:** 2026-08-29  
**Milestone:** stable public error hierarchy  
**Evidence class:** HOST_TEST  
**Hardware evidence:** None

## Outcome

Software Phase 1 Step 2 is complete. The formal `analog_validation` package now exposes stable exception families for validation, protocol framing, record length, CRC, protocol version, device capability, and configuration failures.

This boundary lets later adapters and user interfaces catch a Python type instead of comparing human-readable message strings.

## Public errors

- `AnalogValidationError`;
- `ValidationError`;
- `ProtocolError`;
- `FramingError`;
- `FrameTooLong`;
- `CrcMismatch`;
- `UnsupportedProtocolVersion`;
- `CapabilityError`;
- `ConfigurationError`.

## Executed verification

| Check | Actual result |
|---|---|
| Full pytest suite | PASS: 39 tests |
| Formal package coverage | PASS: 100% of 14 executable statements |
| Ruff on `src` and `tests/unit` | PASS |
| mypy on `src` and `tests/unit` | PASS: no issues in 5 source files |
| Every specialized error caught by root | PASS |
| Protocol specialization catch semantics | PASS |
| Non-protocol family separation | PASS |
| Human-readable message preservation | PASS |
| Chained low-level cause preservation | PASS |

## Deliberate boundary

The old `dashboard.protocol.ProtocolError`, `FrameTooLong`, and `CrcMismatch` are not migrated in this step. CRC and framing move together in Step 5 so that the repository does not maintain two supposedly authoritative protocol implementations.

No serial driver, GUI, controller, AFE circuit, wiring, ADC, or laboratory instrument was used or validated.
