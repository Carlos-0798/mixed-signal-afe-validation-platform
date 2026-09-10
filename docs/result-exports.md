# Versioned result exports

**Introduced:** Software Phase 3 Step 7<br>
**Schema:** `result-export.v1`<br>
**Formats:** deterministic UTF-8 JSON and row-oriented CSV<br>
**Evidence:** HOST_TEST only; no hardware was measured

## What problem this layer solves

Analysis objects are useful inside Python, but a test result also needs a durable interchange form for a future CLI, dashboard, controller integration, or portfolio demo. `analog_validation.exports` converts a finalized `TestRunResult` plus its already-computed criteria, metrics, point decisions, record references, source schemas, and limitations into one immutable `ResultExportBundle`.

The export layer is intentionally not another analysis layer. It does not fit a line, estimate a threshold, change an outcome, discard an excluded point, or upgrade evidence to `BENCH_*`. A source such as `SYNTHETIC`, `CSV_REPLAY`, or `HOST_TEST` remains exactly that source after JSON/CSV round trip.

## Beginner mental model

Think of the result bundle as a sealed engineering folder:

| Section | What it answers |
|---|---|
| `test_run` | Which test ran, when, with which configuration/profile, and what outcome it already reached? |
| `criteria` | Which versioned limits were used and which checks already passed or failed? |
| `source_schemas` | Which source contracts are needed to interpret the result? |
| `metrics` | What named summary values were already calculated? |
| `points` | Which source records contributed, were excluded, or were invalid, and why? |
| `limitations` | What must a reader not infer from this file? |

`PASS` means only that the selected criteria passed for the attached evidence. It does not mean the evidence came from hardware. The `evidence_source` and limitations remain mandatory context.

## Typed builders

Four builders connect finalized evaluations to the generic bundle:

- `build_dc_sweep_export` preserves fit metrics, DC criteria, input/output references, predictions, residuals, quality flags, and saturation/exclusion reasons;
- `build_hysteresis_export` preserves cycle/direction points, analog/state references, thresholds/width statistics when analysis is complete, criteria, and quality/exclusion reasons;
- `build_calibration_export` preserves observed/reference decisions and lineage, fitted coefficient identity/value, before/after error metrics, explicit criteria, and every point disposition without refitting;
- `build_frequency_response_export` preserves frequency/input/output references, amplitude ratio, gain dB, cutoff metrics, criteria, quality decisions, and incomplete semantics without re-interpolating the curve.

They copy existing values only. If a hysteresis direction contains an excluded or invalid point, the analysis remains incomplete and the builder does not invent threshold metrics.

```python
from analog_validation.exports import (
    build_dc_sweep_export,
    write_result_export_json,
)

# evaluation is an existing DCSweepEvaluationResult from the runner/evaluator.
bundle = build_dc_sweep_export(
    evaluation,
    limitations=(
        "HOST_TEST fixture only; no physical AFE was measured.",
    ),
)

# Existing files are protected unless overwrite=True is explicitly supplied.
path = write_result_export_json("results/dc-run-001.json", bundle)
```

The parent directory must already exist. This prevents a typo from silently creating an unexpected directory tree.

## JSON v1

JSON is the complete machine-oriented representation. It uses stable field order, a trailing newline, explicit UTC timestamps, enum strings, and finite JSON values. The parser rejects:

- duplicate object keys;
- `NaN`, positive/negative infinity, malformed JSON, NUL, or invalid Unicode;
- missing, extra, wrongly typed, or unsupported-version fields;
- documents larger than 2,000,000 UTF-8 bytes;
- any reconstructed domain object that violates TestRun, source, lineage, criteria, or point-state invariants.

Use `dump_result_export_json` / `parse_result_export_json` for memory and `write_result_export_json` / `load_result_export_json` for files.

## CSV v1

CSV uses exactly four columns:

```text
format_version,row_type,row_index,payload
```

The `payload` is a compact strict JSON object. This avoids flattening a point's multiple evidence references, values, quality flags, and reasons into ambiguous repeated columns.

Rows have a fixed section order:

1. one `RUN` row;
2. one or more `SCHEMA` rows;
3. zero or more `CRITERION` rows;
4. zero or more `METRIC` rows;
5. zero or more `POINT` rows;
6. one or more `LIMITATION` rows.

Every row carries `result-export.v1` and a contiguous zero-based `row_index`. The parser rejects unknown row types, wrong order/index, duplicate or missing sections, bad payload fields, unsupported versions, more than 100,000 rows, or the same 2,000,000-byte limit used by JSON.

CSV and JSON reconstruct the same `ResultExportBundle`; CSV is not a second result schema with different meaning.

## File safety

Both writers:

- default to `overwrite=False`;
- write a temporary file in the destination directory and flush it before publication;
- atomically publish a new path, including protection against a destination created during the write;
- replace an existing destination only when the caller explicitly sets `overwrite=True`;
- remove their temporary file after success or failure;
- return typed export format, limit, path, existence, or version errors.

These rules protect result history, but explicit overwrite is still destructive. The current product CLI leaves overwrite disabled; enabling it later would require a visible, reviewed user choice.

## Current boundary

The export layer provides structured interchange, not an end-user report. The
product consumes this stable bundle through `analog-validation report` and the
Dashboard, creating text, Markdown, self-contained HTML, deterministic SVG,
and a hash manifest without changing the bundle's conclusion. PDF, digital
signatures, and long-term database storage remain outside this layer. See
`human-reports.md`.

All Step 7 tests use software fixtures. No AFE, MSP430, ADC, DAC, UART, wire, power supply, DMM, oscilloscope, or laboratory instrument was connected.
