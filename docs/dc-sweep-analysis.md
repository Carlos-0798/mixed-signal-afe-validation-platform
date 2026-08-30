# DC sweep analysis v1

**Schema:** `dc-sweep-analysis.v1`  
**Introduced:** Software Phase 3 Step 2  
**Evidence produced by current tests:** `HOST_TEST` over `SYNTHETIC` or `CSV_REPLAY` records  
**Hardware validation:** none

## Purpose

`analog_validation.analysis.dc_sweep` turns an already acquired input/output sweep into a traceable linear analysis. It is controller-neutral: the function does not know whether records came from a simulator, a replay file, or a future device adapter.

The module answers “what line best describes the eligible points?” It does **not** answer “did the device pass?” Step 3 will add versioned acceptance criteria, and Step 4 will add a safety-gated runner.

## Beginner mental model

Think of a DC sweep as a laboratory worksheet with two columns:

1. the applied or observed input voltage `x`;
2. the corresponding output voltage `y`.

Before drawing a best-fit line, the software must check every row. A row can be used, excluded with an explanation, or invalid because one component record is unusable. The row is never deleted, so a later reviewer can see exactly why the answer was calculated from some points but not others.

```text
MeasurementBatch
      |
      +--> pair input/output records by within-channel order
      |
      +--> normalize explicit V or mV values
      |
      +--> apply quality policy and inclusive saturation limits
      |
      +--> enough valid, distinct input points?
               | no                         | yes
               v                            v
        incomplete result             ordinary least squares
        + exact missing gaps          + gain / offset / R²
        + every original point        + RMSE / max residual
                                      + prediction/residual per used point
```

## Input contract

`DCSweepAnalysisConfig` freezes:

- distinct input and output channel names;
- finite `low_output_limit < high_output_limit`;
- one normalized voltage unit, `V` or `mV`;
- an engineering minimum of three included points by default;
- an explicit `AnalysisQualityPolicy`;
- the `dc-sweep-analysis.v1` schema identifier.

`MeasurementBatch` already guarantees a non-empty collection, unique record IDs, and one unchanged evidence source. The DC pairing layer additionally rejects unexpected channels, a missing side, or unequal input/output counts. Pairing is ordinal within each channel because current acquisition records do not yet contain a shared setpoint identifier.

## Quality and saturation decisions

Each component record first receives the common Step 1 quality decision. The default policy excludes every `SUSPECT` record and never includes `INVALID`, missing, or non-finite data. A finite suspect flag can be allowed only by an explicit immutable policy.

Numeric saturation is then evaluated against output limits:

- `output <= low_output_limit` becomes `LOW_SATURATION`;
- `output >= high_output_limit` becomes `HIGH_SATURATION`;
- both boundaries are intentionally inclusive;
- an allowlisted quality flag does not override numeric saturation.

A point may also record `INPUT_NOT_INCLUDED` or `OUTPUT_NOT_INCLUDED`. Component-level decisions retain the more detailed quality reasons such as missing value, time anomaly, or communication error.

## Completeness rule

Two distinct points determine a mathematical line, but the default engineering minimum is three included points. With only two points there is no independent point left to reveal curvature or an outlier. The minimum is configurable down to two for deliberate demonstrations or compatibility use.

The analysis returns no fit when either requirement is missing:

- included point count is below the configured minimum;
- fewer than two distinct normalized input values remain.

`missing_requirements` records exact machine-readable gaps such as `included-points:2/3` or `distinct-input-values:1/2`. This state is “analysis incomplete,” not PASS or FAIL.

## Linear calculations

For included points, ordinary least squares fits:

```text
predicted_y = gain * x + offset
residual    = measured_y - predicted_y
```

The result stores:

- `gain`: slope in output-unit per input-unit; using one normalized unit makes this a voltage ratio;
- `offset`: y-intercept in the configured normalized voltage unit;
- `r_squared`: fraction of output variation described by the line, bounded to `[0, 1]` for numerical stability;
- `rmse`: square root of the mean squared residual;
- `max_abs_residual`: largest absolute point error;
- `used_points`: number of included point pairs.

An exact constant output has zero residual and a defined `R² = 1`. Constant input is rejected before fitting because slope would be undefined.

## Provenance and immutability

Every `DCSweepPointResult` contains both immutable `MeasurementDecision` objects. Through them it preserves input and output `record_id`, `raw_record_id`, UTC timestamp, channel, original unit, normalized value, status, quality flags, and evidence source. Excluded points have no fitted prediction or residual. Included points receive those values only after a complete fit.

No input `Measurement` or `MeasurementBatch` is mutated, and source labels are never promoted. A synthetic result remains synthetic; a replay result remains replay evidence.

## Minimal example

```python
from analog_validation.analysis import (
    DCSweepAnalysisConfig,
    MeasurementBatch,
    analyze_dc_sweep,
)

config = DCSweepAnalysisConfig(
    input_channel="afe.ch0.input",
    output_channel="afe.ch0.output",
    low_output_limit=100.0,
    high_output_limit=3200.0,
)

result = analyze_dc_sweep(MeasurementBatch(tuple(measurements)), config)
if result.is_complete:
    print(result.fit.gain, result.fit.offset)
else:
    print(result.missing_requirements)
```

The numeric limits above are an example software configuration, not verified hardware limits.

## Explicit non-goals for Step 2

- no PASS/FAIL or tolerance comparison;
- no stimulus generation or output authorization;
- no adapter lifecycle or data acquisition;
- no serial port, MSP430, instrument, or AFE access;
- no calibration or hardware accuracy claim;
- no deletion or relabeling of original evidence.

See the [common analysis semantics](analysis-common.md), [Phase 3 plan](SOFTWARE_PHASE_3_PLAN.md), and [Step 2 verification report](../reports/software-phase3-step2.md).

