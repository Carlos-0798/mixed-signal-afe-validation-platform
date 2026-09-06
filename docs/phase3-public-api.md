# Frozen Software Phase 3 compatibility

**Freeze schema:** `phase3-public-api-golden.v1`<br>
**Evidence:** HOST_TEST / SYNTHETIC<br>
**Hardware evidence:** none

## Why a compatibility freeze exists

Ordinary unit tests ask whether today's implementation behaves correctly. A golden compatibility test asks a different question: did a public name, schema value, enum, call shape, error family, or representative engineering result change since the checkpoint was approved?

That distinction matters for a reusable product. A future MSP430 adapter, another controller, CLI, dashboard, or external user should be able to upgrade internal code without discovering that a field silently disappeared or that the same input now means something different.

The freeze is not a promise that every internal line will remain unchanged. Private helpers and implementation details may be refactored as long as the public contract and exact approved results remain stable. An intentional breaking change must upgrade the applicable schema/version, update migration documentation, and replace—not silently rewrite—the golden expectation.

## Frozen files

| File | Purpose |
|---|---|
| `test-data/golden/phase3_public_api.json` | Public exports, schemas, constants, enums, signatures, errors, and golden-file hashes |
| `test-data/golden/phase3_dc_sweep_input_v1.json` | One explicit synthetic DC input/configuration/criteria fixture |
| `test-data/golden/phase3_dc_sweep_result_v1.json` | Exact exported DC PASS with one retained high-saturation point |
| `test-data/golden/phase3_hysteresis_result_v1.json` | Exact exported one-cycle hysteresis PASS |
| `tests/golden/test_phase3_public_api_golden.py` | Reconstructs and checks the public manifest |
| `tests/golden/test_phase3_results_golden.py` | Rebuilds both results and compares exact JSON text |

SHA-256 values for the three input/result fixtures are stored in `phase3_public_api.json`. The manifest does not hash itself, avoiding a circular hash.

## Public surface frozen

The manifest freezes exact `__all__` values for:

- `analog_validation` — 92 symbols after the additive frequency-source and
  streaming-read extensions;
- `analog_validation.analysis` — 84 symbols;
- `analog_validation.runners` — 10 symbols;
- `analog_validation.exports` — 38 symbols.

It also freezes:

- 17 Phase 3 schema versions, including calibration/frequency-response criteria
  and evaluation plus coefficient persistence;
- calibration and cutoff method identifiers;
- CSV result columns and result resource limits;
- 10 analysis enum value sets;
- the parameter name/kind/default shape of primary analysis, criteria, plan, runner, calibration, frequency, and export entry points;
- all 6 result-export error inheritance relationships;
- implementation ownership inside `analog_validation.*`, not legacy `dashboard.*`.

The manifest keeps analysis/evaluator/export names in the explicit
`analog_validation.analysis`, `.runners`, and `.exports` namespaces. The
top-level additive frequency-source extension contains only the public
read-only Simulator adapter/configuration and its schema constant; it does not
move analysis logic into the adapter surface.

The current local post-beta calibration, frequency-response, and bounded
live-monitor extensions are
additive to those explicit namespaces. They freeze `CalibrationAcceptanceCriteria`,
`CalibrationCriterionName`, `evaluate_calibration`,
`build_calibration_export`, and the strict `calibration-coefficients.v1`
load/dump/write functions, plus `FrequencyResponseAcceptanceCriteria`,
`FrequencyResponseCriterionName`, `evaluate_frequency_response`, and
`build_frequency_response_export`. The top-level manifest also freezes the
compatible public `run_streaming_read_workflow` entry point used by bounded
live monitoring. It adds no analysis schema or hardware-control surface. The
existing DC and hysteresis fixture bytes remain unchanged.

## Exact result meaning

### DC fixture

The frozen synthetic DC fixture uses four input/output pairs. Three eligible pairs produce:

```text
gain = 2.0
offset = 12.0 mV
R² = 1.0
RMSE = 0.0 mV
```

The 3300 mV output is retained as `EXCLUDED` with `point:HIGH_SATURATION`. Five versioned criteria pass, every record/raw ID remains present, and the exported evidence source remains `SYNTHETIC`.

### Hysteresis fixture

The frozen synthetic rising/falling cycle produces midpoint estimates:

```text
mean high threshold = 1750.0 mV
mean low threshold  = 1550.0 mV
mean width          = 200.0 mV
```

All eight points remain included, five criteria pass, and all sixteen analog/state references remain `SYNTHETIC`.

These values freeze software meaning. They are not AFE measurements, comparator specifications, accuracy claims, or evidence that the thresholds are physically achievable.

## Change procedure

When a golden test fails:

1. determine whether the change is an accidental regression or an intentional contract change;
2. inspect the exact name/value/field/result difference;
3. fix accidental drift without editing golden data;
4. for an intentional compatible addition, document why old consumers remain valid;
5. for an intentional breaking change, introduce a new schema/version and migration note;
6. regenerate/review golden files only after the owner accepts the change;
7. rerun full tests, coverage, static checks, isolated build, and external installation.

Never update a golden file merely to make a failing test green.

## Remaining boundary

This freeze covers Software Phase 3 only. It does not freeze serial transport, controller profiles, CLI commands, Dashboard behavior, human reports, firmware, or any physical electrical interface. Those contracts belong to later phases and need their own evidence before being added.
