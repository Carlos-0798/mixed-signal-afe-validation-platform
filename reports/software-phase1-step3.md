# Software Phase 1 Step 3 Report

**Date:** 2026-08-29  
**Milestone:** provenance, quality, and measurement domain model  
**Evidence class:** HOST_TEST  
**Hardware evidence:** None

## Outcome

Software Phase 1 Step 3 is complete. The formal package now contains an immutable, controller-neutral `Measurement` model with explicit source, status, quality, unit, UTC time, schema version, and raw-record traceability.

The implementation refuses to default missing provenance to BENCH evidence. Missing and non-finite values must be explicitly marked invalid with matching quality flags.

## Added domain types

- `EvidenceSource` with nine controlled evidence classes;
- `QualityFlag` for missing, non-finite, saturation, range, time, and communication conditions;
- `MeasurementStatus` with `VALID`, `SUSPECT`, and `INVALID`;
- `MeasurementUnit` with twelve controlled units;
- immutable, slotted `Measurement`;
- `MEASUREMENT_SCHEMA_VERSION = "measurement.v1"`.

## Executed verification

| Check | Actual result |
|---|---|
| Full pytest suite | PASS: 85 tests |
| Formal package coverage | PASS: 100% of 141 executable statements |
| Ruff on `src` and `tests/unit` | PASS |
| mypy on `src` and `tests/unit` | PASS: no issues in 9 source files |
| Evidence-source enum stability | PASS |
| BENCH/non-BENCH classification | PASS |
| Immutability and raw-reference behavior | PASS |
| Timezone rejection and UTC normalization | PASS |
| Unknown unit/source/status/quality rejection | PASS |
| Missing and non-finite consistency | PASS |
| Status/quality consistency | PASS |
| Unknown schema rejection | PASS |
| Isolated sdist and wheel build | PASS |
| Repository-external wheel install and Measurement construction | PASS |

## Evidence limit

`EvidenceSource.BENCH_*` is a controlled label, not proof that bench work occurred. Hardware evidence still requires physical execution, environment and wiring records, raw data, and an appropriate report. No AFE circuit, MSP430, ADC, serial link, DMM, oscilloscope, or laboratory instrument was used in this step.

## Remaining Phase 1 work

- capability and test-run models;
- CRC/framing migration;
- AFE v1 profile;
- configuration model and validation;
- final migration, golden data, coverage, and documentation closure.
