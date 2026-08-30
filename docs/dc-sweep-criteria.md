# DC sweep criteria and TestRun mapping v1

**Criteria schema:** `dc-sweep-criteria.v1`<br>
**Evaluation schema:** `dc-sweep-evaluation.v1`<br>
**Introduced:** Software Phase 3 Step 3<br>
**Hardware validation:** none

## Purpose

Step 2 calculates what the data says. Step 3 separately decides whether those calculated values satisfy an explicit engineering specification.

This separation matters because the same measured fit can pass one product specification and fail another. Changing a tolerance must not silently change the underlying measurements or recompute the line differently.

```text
DCSweepAnalysisResult             DCSweepAcceptanceCriteria
calculator output                 versioned engineering limits
          \                              /
           +------ evaluate_dc_sweep ---+
                          |
                          v
              DCSweepEvaluationResult
              + five criterion records
              + criteria ID/version
              + original analysis
              + evidence-backed TestRunResult
```

## Versioned acceptance criteria

`DCSweepAcceptanceCriteria` requires:

- a non-empty `criteria_id` and `criteria_version`;
- target gain and an inclusive absolute gain tolerance;
- maximum absolute offset;
- minimum R² in `[0, 1]`;
- maximum RMSE;
- minimum included point count of at least two;
- an explicit `V` or `mV` unit for offset and RMSE limits;
- the `dc-sweep-criteria.v1` schema identifier.

All limits must be finite. Tolerances, maximum errors, and RMSE cannot be negative. The criteria voltage unit must exactly match the analysis configuration; the evaluator never guesses or converts a specification.

Criteria values in tests are software fixtures. They are not validated AFE requirements, component tolerances, or safe electrical limits.

## Five deterministic checks

A complete evaluation produces these records in stable order:

| Criterion | Inclusive rule | Unit |
|---|---|---|
| `GAIN` | `target - tolerance <= actual <= target + tolerance` | ratio |
| `ABS_OFFSET` | `abs(offset) <= maximum` | V or mV |
| `R_SQUARED` | `actual >= minimum` | ratio |
| `RMSE` | `actual <= maximum` | V or mV |
| `INCLUDED_POINTS` | `actual >= minimum` | points |

Each `DCSweepCriterionResult` stores its name, actual value, explicit unit, inclusive lower/upper limits, and boolean result. Model validation prevents the boolean from contradicting the stored numbers.

## Outcome mapping

| Analysis | Criteria | Criteria point requirement | Result |
|---|---|---|---|
| incomplete | present or absent | not evaluated | `INCOMPLETE` with every known gap |
| complete | absent | not evaluated | `INCOMPLETE: acceptance-criteria` |
| complete | present | insufficient evidence points | `INCOMPLETE`, not FAIL |
| complete | present | sufficient and all five checks pass | `PASS` |
| complete | present | sufficient and one or more checks fail | `FAIL` |

This distinction prevents missing evidence from becoming a device failure or, worse, an accidental PASS. `UNSUPPORTED`, `ABORTED`, and `ERROR` remain runner responsibilities in later checkpoints.

## Metadata and evidence consistency

The evaluator accepts an existing `TestRunMetadata` and requires:

- `test_type == "dc-sweep"`;
- metadata evidence source exactly matches the analysis;
- metadata raw input IDs exactly match the analysis raw references in stable first-seen order;
- the final `TestRunResult.evidence_record_ids` contains both input and output record IDs for every retained point.

Structural contradictions are rejected rather than converted into `INCOMPLETE`. That includes wrong criteria units, mismatched metadata source, wrong test type, wrong raw IDs, or duplicate analysis record IDs.

## Minimal example

```python
from analog_validation.analysis import (
    DCSweepAcceptanceCriteria,
    evaluate_dc_sweep,
)

criteria = DCSweepAcceptanceCriteria(
    criteria_id="example-dc-limits",
    criteria_version="1.0",
    target_gain=2.0,
    gain_absolute_tolerance=0.05,
    max_abs_offset=20.0,
    min_r_squared=0.99,
    max_rmse=5.0,
    minimum_included_points=3,
)

evaluation = evaluate_dc_sweep(analysis, criteria, metadata)
print(evaluation.test_run_result.outcome.value)
for check in evaluation.criterion_results:
    print(check.criterion.value, check.actual_value, check.passed)
```

The example tolerances are illustrative host-test values, not physical acceptance limits.

## Evidence boundary

A `PASS` means only that the supplied data satisfies the supplied versioned criteria. Its evidence class remains the source of the input records. Therefore:

- `SYNTHETIC` PASS proves deterministic software behavior;
- `CSV_REPLAY` PASS evaluates a file without rerunning hardware;
- only a future documented `BENCH_*` run may support a physical claim;
- Step 3 does not acquire data, control stimulus, connect serial, or verify shutdown.

See [DC sweep analysis v1](dc-sweep-analysis.md), [TestRun semantics](capabilities-and-test-runs.md), and the [Step 3 report](../reports/software-phase3-step3.md).
