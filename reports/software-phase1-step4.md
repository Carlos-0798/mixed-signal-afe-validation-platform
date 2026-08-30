# Software Phase 1 Step 4 Report

**Date:** 2026-08-29  
**Milestone:** explicit capabilities, safe ranges, and test-run conclusions  
**Evidence class:** HOST_TEST  
**Hardware evidence:** None

## Outcome

Software Phase 1 Step 4 is complete. The formal package now contains versioned, controller-neutral models for explicit device capabilities and finalized test runs.

The capability model does not infer behavior from a board name or USB identity. The test-run model distinguishes complete PASS/FAIL conclusions from INCOMPLETE, UNSUPPORTED, ABORTED, and ERROR attempts. Missing requirements cannot be represented as PASS.

## Added domain types

- `DeviceCommand` with six stable controller-neutral command values;
- `SafeRange` and `ChannelRange` with explicit units and finite inclusive bounds;
- immutable `DeviceCapabilities` with ADC/DAC/PWM/digital-input channels, exact safe-range coverage, supported commands, safe-shutdown agreement, and `capabilities.v1` schema;
- automatic-output validation that distinguishes `CapabilityError` from unsafe `ConfigurationError`;
- `TestRunOutcome` with PASS, FAIL, INCOMPLETE, UNSUPPORTED, ABORTED, and ERROR;
- immutable `TestRunMetadata` with test/config/software/device/profile/time/source/input traceability and `test-run.v1` schema;
- immutable `TestRunResult` with evidence and missing-requirement references.

## Executed verification

| Check | Actual result |
|---|---|
| Full pytest suite | PASS: 144 tests |
| Formal package coverage | PASS: 100% of 421 executable statements |
| Ruff on `src` and all `tests` | PASS |
| mypy on `src` and all `tests` | PASS: no issues in 17 source files |
| Stable command and outcome enum values | PASS |
| Safe-range numeric, finite, unit, and boundary rules | PASS |
| Exact channel/range coverage and duplicate rejection | PASS |
| Command/channel/safe-shutdown consistency | PASS |
| Unsupported capability versus unsafe configuration errors | PASS |
| Test-run UTC normalization and version rejection | PASS |
| PASS/FAIL evidence requirement | PASS |
| INCOMPLETE/UNSUPPORTED missing-requirement rule | PASS |
| Immutable copies of caller-provided collections | PASS |
| Isolated sdist and wheel build | PASS |
| Repository-external wheel install and public API import | PASS |
| Installed-package dependency check | PASS: no broken requirements |

The external wheel smoke test constructed an empty, read-only `DeviceCapabilities` record and imported `TestRunOutcome.UNSUPPORTED` from the installed public package. Its actual output was `capabilities.v1 UNSUPPORTED`.

## Evidence and safety limit

All results above are HOST_TEST evidence. No AFE circuit, breadboard, PCB, MSP430, reference controller, ADC, DAC, PWM output, serial link, DMM, oscilloscope, or laboratory instrument was used.

The numeric ranges in unit tests are synthetic examples. They do not establish that 0–3.3 V or any other range is safe for future hardware. Hardware profiles may only publish limits after datasheet review, wiring review, and the required physical acceptance gates.

The existence of a `SAFE_SHUTDOWN` field is also not proof that a future device actually reaches a safe state. That behavior requires adapter, firmware, fault-injection, and bench verification in later phases.

## Remaining Phase 1 work

- migrate CRC and framing into the formal package;
- define the AFE v1 protocol profile and capability message shape;
- establish versioned configuration models and host-side validation;
- migrate legacy users, add golden protocol data, and close Phase 1 documentation.
