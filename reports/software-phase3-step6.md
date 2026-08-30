# Software Phase 3 Step 6 Verification Report

**Date:** 2026-08-30  
**Checkpoint:** Calibration and offline frequency response  
**Result:** COMPLETE — host-software scope only  
**Highest evidence source used:** HOST_TEST  
**Verified bench claims:** 0

## 1. Outcome

Step 6 is complete. The installable package now provides:

- `calibration-analysis.v1` configuration, point, coefficient, metrics, fit-result, application, and derived-point models;
- `fit_linear_calibration(...)` for ordinary least-squares reference-versus-observed fitting;
- `apply_linear_calibration(...)` for immutable derived Measurement creation;
- `frequency-response-analysis.v1` configuration, frequency decision, point, summary, and result models;
- `analyze_frequency_response(...)` for explicit amplitude ratio, dB, and single-crossing cutoff analysis;
- public exports from `analog_validation.analysis`.

The two modules use only standard-library math and formal domain/analysis models. They do not import adapters, open ports, acquire waveforms, perform FFT, or control hardware.

## 2. Frozen calibration semantics

The fit is:

```text
reference = scale × observed + offset
```

The result keeps observed/reference EvidenceSource values separately, records every included record/raw ID in the coefficients, and reports before/after RMSE, mean absolute error, and maximum absolute error. Insufficient included points or fewer than two distinct observed values returns explicit missing requirements and no partial coefficients.

Applying coefficients creates a new Measurement for every included source record. It preserves `raw_record_id`, UTC timestamp, source, status, and quality flags; changes channel, value, unit, and derived `record_id`; and retains coefficient ID/version in the application point. Tests compare the source batch before and after application.

This is a software calibration mechanism. No test coefficient came from a physical standard or verified instrument.

## 3. Frozen frequency-response semantics

The analysis accepts three equal-length, same-source batches: Hz, input amplitude, and output amplitude. Amplitudes normalize explicitly between V and mV. Included points calculate:

```text
ratio = output / input
gain_db = 20 × log10(ratio)
```

The first included point defines reference gain. The default target is `reference_gain - 3.010299956639812 dB`. One target crossing is interpolated linearly in dB versus `log10(Hz)` and identified by method `linear-db-versus-log10-hz`.

- no crossing produces incomplete result `cutoff-crossing`;
- more than one unique crossing raises an explicit ambiguity error;
- zero/negative amplitude, nonpositive frequency, non-increasing frequency, or non-finite calculations are rejected;
- excluded/invalid component measurements remain in point results and suppress a complete summary.

The result is not an FFT, spectrum, waveform acquisition, or physical bandwidth measurement.

## 4. Files added or changed

Formal code:

- `src/analog_validation/analysis/calibration.py`
- `src/analog_validation/analysis/frequency_response.py`
- `src/analog_validation/analysis/__init__.py`

Tests:

- `tests/unit/test_calibration_analysis.py`
- `tests/unit/test_frequency_response_analysis.py`

Product evidence and presentation:

- `docs/calibration-and-frequency-response.md`
- `docs/calibration.md`
- `docs/architecture.md`
- `docs/SOFTWARE_PHASE_3_PLAN.md`
- `docs/PROJECT_STATUS.md`
- `docs/REQUIREMENTS_TRACEABILITY.md`
- `docs/TECHNICAL_DEBT.md`
- `docs/DEVELOPMENT_ENVIRONMENT.md`
- `docs/PRODUCT_PLAN.md`
- `README.md`

## 5. Executed verification

| Gate | Actual result |
|---|---|
| Focused Step 6 pytest | PASS — 48 tests |
| Step 6 module coverage | PASS — 705/705 statements, 100% |
| Full pytest suite | PASS — 992 tests |
| Formal package coverage | PASS — 4,954/4,954 statements, 100% |
| Ruff | PASS — full repository |
| mypy | PASS — 88 source files |
| `pip check` | PASS — no broken requirements |
| Isolated sdist and wheel build | PASS — `0.1.0.dev0` |
| sdist Step 6 source/test presence | PASS — all four files present |
| Repository-external wheel install | PASS |
| External public API smoke | PASS — top level 84, analysis 68, runners 10 symbols |
| External Step 6 imports | PASS — both analysis functions importable |
| Hardware or instrument test | NOT RUN |

## 6. Acceptance mapping

| Planned boundary | Evidence |
|---|---|
| Coefficient identity/version and numeric boundaries | Constructor and application tests |
| V/mV normalization | Mixed-unit fit and response tests |
| Original records not overwritten | Immutable source snapshot and derived-record tests |
| Observed/reference provenance retained | Separate-source fit test and coefficient lineage assertions |
| Zero input amplitude | Rejected by focused tests |
| Nonpositive ratio | Zero/negative output rejected by focused tests |
| Frequency ordering | Nonpositive, equal, and decreasing frequencies rejected |
| No cutoff crossing | Explicit incomplete result test |
| Multiple cutoff crossings | Explicit ambiguity error test |
| Quality exclusion | Calibration and frequency component-decision tests |

## 7. Evidence limits and remaining assumptions

Not verified in this checkpoint:

- correctness or accuracy of any physical ADC, DAC, AFE, filter, comparator, MSP430, or other controller;
- traceability, uncertainty, or calibration status of a DMM/scope/signal source;
- real cutoff frequency, gain, noise, saturation, hysteresis, or voltage range;
- serial transport, live timing, FFT, instrument control, wiring, grounding, power, or safe shutdown on hardware;
- whether future BENCH data meets any product acceptance criteria.

Future hardware calibration still needs hardware revision, populated components, reference instrument identity/status, supply/reference values, ambient conditions, raw codes, untouched readings, coefficients, residuals, uncertainty, and date.

## 8. Next checkpoint

Software Phase 3 Step 7 will add versioned, stable CSV/JSON result export. It must preserve TestRun metadata, criteria, metrics, point decisions, evidence IDs/source, and limitations; reject NaN/Inf and unsafe paths; and default to no overwrite. It will not add serial transport, hardware acquisition, a product dashboard, or bench claims.
