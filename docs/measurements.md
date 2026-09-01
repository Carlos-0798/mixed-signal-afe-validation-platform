# Measurement Domain Contract

`analog_validation.Measurement` is the controller-neutral record used by future simulators, CSV replay, serial profiles, analysis, exports, and reports. It is immutable so calibration or filtering cannot overwrite an original observation.

## Required fields

| Field | Rule |
|---|---|
| `record_id` | Non-empty identifier for this record |
| `raw_record_id` | Identifier of the original record; equal to `record_id` for an unmodified raw record |
| `timestamp` | Timezone-aware `datetime`, normalized to UTC |
| `channel` | Non-empty, trimmed channel identifier |
| `value` | Numeric value, or `None` only when explicitly marked missing and invalid |
| `unit` | Controlled `MeasurementUnit`; arbitrary strings are rejected |
| `status` | `VALID`, `SUSPECT`, or `INVALID` |
| `source` | Explicit controlled `EvidenceSource`; there is no default BENCH source |
| `quality_flags` | Immutable set of specific quality conditions |
| `schema_version` | Currently `measurement.v1`; unknown versions are rejected |

## Evidence sources

```text
THEORY
SYNTHETIC
CSV_REPLAY
SPICE_IDEAL
SPICE_MODEL
HOST_TEST
BENCH_DMM
BENCH_CONTROLLER
BENCH_SCOPE
```

Only labels beginning with `BENCH_` are eligible to represent physical evidence. A label alone does not prove that a measurement happened: a valid hardware claim must also retain the test environment, device, wiring, configuration, raw data, and report.

## Status and quality consistency

- `VALID` requires a finite numeric value and no quality flags.
- `SUSPECT` requires at least one quality flag but still retains a finite value.
- `INVALID` requires at least one quality flag.
- A missing value must be `None`, have `MISSING`, and be `INVALID`.
- NaN or infinity must have `NON_FINITE` and be `INVALID`.
- Contradictory combinations are rejected with `ValidationError`.

Current quality flags are `MISSING`, `NON_FINITE`, `SATURATED`, `OUT_OF_RANGE`, `TIME_ANOMALY`, and `COMMUNICATION_ERROR`.

## Raw and derived records

For a raw record:

```text
record_id == raw_record_id
```

For a calibrated or otherwise derived record:

```text
record_id != raw_record_id
```

The derived record receives a new ID and keeps the original ID in `raw_record_id`. The original object is never modified.

## Example

```python
from datetime import datetime, timezone

from analog_validation import (
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
)

measurement = Measurement(
    record_id="synthetic-0001",
    raw_record_id="synthetic-0001",
    timestamp=datetime.now(timezone.utc),
    channel="afe.ch0.output",
    value=1250.0,
    unit=MeasurementUnit.MILLIVOLT,
    status=MeasurementStatus.VALID,
    source=EvidenceSource.SYNTHETIC,
)
```

This object demonstrates software behavior only. Changing `source` to `BENCH_DMM` without corresponding physical evidence would be incorrect data entry, not hardware validation.
