# Software Phase 3 Step 7 Verification Report

**Date:** 2026-08-30<br>
**Checkpoint:** Versioned CSV/JSON result export<br>
**Result:** COMPLETE — host-software scope only<br>
**Highest evidence source used:** HOST_TEST<br>
**Verified bench claims:** 0

## 1. Outcome

Step 7 is complete. The installable package now provides:

- immutable `result-export.v1` schema, value, criterion, point, source-schema, and bundle models;
- typed builders for finalized DC sweep and hysteresis evaluations;
- deterministic JSON and four-column row-oriented CSV representations of the same bundle;
- strict bounded parsers and exact JSON/CSV round trips;
- typed format, limit, path, existing-destination, and unsupported-version errors;
- atomic UTF-8 local-file publication with no overwrite by default.

The export layer copies existing analysis and TestRun conclusions. It performs no fit, threshold estimation, criteria evaluation, adapter I/O, or evidence-source promotion.

## 2. Frozen result semantics

Every bundle contains one `TestRunResult`, at least one source-schema reference, and at least one limitation. It may also contain criteria identity/results, metrics, and point records.

The constructor verifies:

- point indexes and evidence IDs use one exact contiguous order;
- record IDs are unique and raw-record IDs match TestRun metadata;
- every point source matches the TestRun evidence source;
- excluded/invalid points retain reasons while included points do not invent reasons;
- PASS/FAIL has criteria plus point evidence and agrees with every criterion result;
- all exported numeric values are finite JSON scalars.

The DC builder preserves fit/count metrics, criteria, both references per point, predictions/residuals, quality flags, and saturation/component reasons. The hysteresis builder preserves cycle/direction, analog/state references, point quality/reasons, criteria, and complete threshold/width statistics. If the source evaluation is incomplete, no missing fit or threshold summary is fabricated.

## 3. Format and file boundaries

JSON uses stable field order, UTC `Z` timestamps, strict keys, and a trailing newline. CSV uses exactly:

```text
format_version,row_type,row_index,payload
```

CSV row types are ordered `RUN`, `SCHEMA`, `CRITERION`, `METRIC`, `POINT`, and `LIMITATION`; each payload is a strict compact JSON object. Both formats reject duplicate/missing/extra fields, duplicate JSON keys, NaN/Infinity, malformed Unicode, NUL, unsupported versions, documents over 2,000,000 bytes, and reconstructed domain inconsistencies. CSV additionally rejects more than 100,000 rows and wrong row order/index.

Writers require an existing parent directory, use a same-directory temporary file, flush before publication, deny an existing destination by default, protect against creation races, and remove temporary files after success/failure. `overwrite=True` is the only path that replaces an existing result.

## 4. Files added or changed

Formal code:

- `src/analog_validation/exports/__init__.py`
- `src/analog_validation/exports/_files.py`
- `src/analog_validation/exports/builders.py`
- `src/analog_validation/exports/csv_v1.py`
- `src/analog_validation/exports/errors.py`
- `src/analog_validation/exports/json_v1.py`
- `src/analog_validation/exports/models.py`

Tests:

- `tests/unit/test_result_exports.py`
- `tests/unit/test_result_export_builders.py`

Product evidence and presentation:

- `docs/result-exports.md`
- `docs/architecture.md`
- `docs/SOFTWARE_PHASE_3_PLAN.md`
- `docs/PROJECT_STATUS.md`
- `docs/REQUIREMENTS_TRACEABILITY.md`
- `docs/TECHNICAL_DEBT.md`
- `docs/DEVELOPMENT_ENVIRONMENT.md`
- `docs/PRODUCT_PLAN.md`
- `dashboard/reporting/csv_export.py`
- `README.md`

## 5. Executed verification

| Gate | Actual result |
|---|---|
| Focused Step 7 pytest | PASS — 43 tests |
| Export package coverage | PASS — 640/640 statements, 100% |
| Full pytest suite | PASS — 1,035 tests |
| Formal package coverage | PASS — 5,594/5,594 statements, 100% |
| Ruff | PASS — full repository |
| mypy | PASS — 97 source/test files |
| `pip check` | PASS — no broken requirements |
| Isolated sdist and wheel build | PASS — `0.1.0.dev0` |
| sdist Step 7 source/test presence | PASS |
| Repository-external wheel install | PASS |
| External public API smoke | PASS — top level 84, analysis 68, runners 10, exports 28 symbols |
| External JSON/CSV round trip | PASS |
| Hardware or instrument test | NOT RUN |

## 6. Acceptance mapping

| Planned boundary | Evidence |
|---|---|
| PASS and FAIL results | Generic bundle tests plus strict criterion/outcome consistency |
| INCOMPLETE and UNSUPPORTED results | Deterministic JSON/CSV round-trip tests |
| Excluded/invalid points | DC saturation and hysteresis quality/state builder tests |
| Evidence source never promoted | Source identity checks and all-outcome round trips |
| NaN/Infinity rejected | Model and JSON parser tests |
| Stable ordering | Repeated dump equality and strict row/field-order reconstruction |
| Bad/missing/non-file path | Typed safe-failure tests |
| Existing destination and publication race | Default no-overwrite tests |
| Explicit overwrite | Temporary-directory JSON/CSV tests only |
| Package usability | External wheel imports and both-format round trip |

## 7. Evidence limits and remaining assumptions

Not verified in this checkpoint:

- any physical AFE, MSP430, ADC, DAC, UART, cable, supply, ground, or instrument;
- real gain, offset, saturation, threshold, hysteresis, bandwidth, accuracy, or repeatability;
- a product CLI, dashboard, human-readable report, chart, database, signature, or cloud upload;
- export builders for calibration/frequency results that do not yet have finalized TestRun evaluation mappings;
- long-term backward compatibility of Phase 3 formats before the Step 8 golden freeze.

Focused fixtures use `HOST_TEST` and `SYNTHETIC`; both test software behavior, not electrical performance.

## 8. Next checkpoint

Software Phase 3 Step 8 will freeze Phase 3 public exports, schema/enum/signature/error meaning, and exact representative results. It will rerun golden compatibility, full quality gates, isolated packaging, repository-external smoke, documentation checks, and the Phase 3 closure review. Serial transport, CLI/dashboard work, hardware acquisition, and BENCH claims remain outside Step 8.
