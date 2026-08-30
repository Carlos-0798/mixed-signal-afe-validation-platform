# Common Analysis Semantics

**Schema:** `analysis-common.v1`<br>
**Current evidence:** HOST_TEST<br>
**Hardware validation:** none

This document explains the common analysis foundation introduced in Software Phase 3 Step 1. It does not calculate gain, fit a line, evaluate hysteresis, or produce PASS/FAIL.

## 1. Why another model is needed

A `Measurement` tells us what was recorded: value, unit, source, status, quality flags, timestamp, and identity. An analysis also needs to record what it decided to do with that measurement.

For example, a saturated value must not simply disappear before a line fit. The product must retain the source record and state that the record was excluded because it was saturated. This makes later reports reviewable and prevents a visually good result from hiding rejected data.

## 2. Measurement status and analysis disposition are different

| Measurement status | Meaning at acquisition | Default analysis disposition |
|---|---|---|
| `VALID` | no known quality problem | `INCLUDED` |
| `SUSPECT` | finite value with one or more quality flags | `EXCLUDED` |
| `INVALID` | unusable or explicitly invalid record | `INVALID` |

An explicit `AnalysisQualityPolicy` may allow selected finite `SUSPECT` flags. The default policy allows none. `MISSING` and `NON_FINITE` can never be allowlisted, and an `INVALID` record can never become included.

The policy itself is saved inside each `MeasurementDecision`. Therefore an included suspect record cannot exist without an explicit policy that allows all of its flags.

## 3. Stable exclusion reasons

`PointExclusionReason` separates overall status from the concrete problem:

| Reason | Source condition |
|---|---|
| `MISSING_VALUE` | `QualityFlag.MISSING` |
| `NON_FINITE_VALUE` | `QualityFlag.NON_FINITE` |
| `INVALID_STATUS` | overall status is `INVALID` |
| `SUSPECT_STATUS` | suspect record is excluded by policy |
| `SATURATED` | `QualityFlag.SATURATED` |
| `OUT_OF_RANGE` | `QualityFlag.OUT_OF_RANGE` |
| `TIME_ANOMALY` | `QualityFlag.TIME_ANOMALY` |
| `COMMUNICATION_ERROR` | `QualityFlag.COMMUNICATION_ERROR` |
| `DEVICE_FAULT` | `QualityFlag.DEVICE_FAULT` |

The public decision model verifies that reasons match the actual flags. A caller cannot label saturated data as a time anomaly or omit one of an invalid record's quality problems.

## 4. Record lineage and provenance

`AnalysisRecordReference` copies only immutable identity fields from a `Measurement`:

- `record_id` and `raw_record_id`;
- UTC timestamp;
- channel;
- unchanged `EvidenceSource`.

It never upgrades `SYNTHETIC` or `CSV_REPLAY` to `BENCH_*`. `MeasurementBatch` additionally requires a non-empty collection, unique record IDs, and one common evidence source. Mixed-source records must be separated or explicitly reconciled before analysis rather than silently combined.

## 5. Voltage normalization

`normalize_voltage` accepts only finite numeric values and explicit `V` or `mV` units. It performs only these conversions:

```text
V -> mV: value × 1000
mV -> V: value ÷ 1000
```

Current, resistance, ADC counts, booleans, unknown strings, NaN, and infinity are rejected. The function does not guess a unit from magnitude or channel name.

## 6. Minimal example

```python
from datetime import datetime, timezone

from analog_validation import (
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
)
from analog_validation.analysis import (
    PointDisposition,
    assess_voltage_measurement,
)

record = Measurement(
    record_id="synthetic-output-1",
    raw_record_id="synthetic-output-1",
    timestamp=datetime(2026, 8, 30, tzinfo=timezone.utc),
    channel="afe.ch0.output",
    value=1.25,
    unit=MeasurementUnit.VOLT,
    status=MeasurementStatus.VALID,
    source=EvidenceSource.SYNTHETIC,
)

decision = assess_voltage_measurement(record)
assert decision.normalized_value == 1250.0
assert decision.disposition is PointDisposition.INCLUDED
assert decision.reference.source is EvidenceSource.SYNTHETIC
```

The analysis API is exposed from `analog_validation.analysis`. It is deliberately not added to the frozen Phase 2 top-level `analog_validation.__all__`, so existing Phase 2 callers retain their exact public surface.

## 7. Current boundary

Step 1 supplies reusable vocabulary and validation only; this module itself does not pair records, fit a line, define engineering tolerances, or control output. Step 2 now builds the first pure calculation layer on top of it in [DC sweep analysis v1](dc-sweep-analysis.md). Versioned engineering tolerances, TestRun conclusions, runners, and output control remain later Phase 3 checkpoints.
