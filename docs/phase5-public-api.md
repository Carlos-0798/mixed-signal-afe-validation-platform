# Frozen Software Phase 5 Product Compatibility

**Freeze schema:** `phase5-public-api-golden.v1`<br>
**Current manifest package version:** `0.1.0b1`<br>
**Software evidence:** `HOST_TEST`<br>
**New physical hardware validation in this step:** no<br>
**Verified AFE bench-performance claims:** 0

## Why this freeze exists

Software Phase 5 turned the validated libraries from earlier phases into a
user-facing product layer: one CLI, one optional desktop Dashboard, stable
workflow requests/results, human-readable reports, and a deterministic
portfolio demo. Passing unit tests proves that these pieces work today. The
compatibility freeze adds a second guarantee: a future change cannot silently
rename a public import, alter a schema, change an exit code, remove a CLI
option, reinterpret an issue family, or change an exported artifact field.

This is similar to freezing the shape of a physical connector. Internal wiring
may improve, but existing users must still be able to plug into the documented
pins. Private functions and implementation details remain free to evolve.

## Frozen files

| File | Purpose |
|---|---|
| `test-data/golden/phase5_public_api.json` | Exact product imports, schemas, constants, CLI contract, exit codes, serialized fields, error/issue families, and earlier golden hashes |
| `tests/golden/test_phase5_public_api_golden.py` | Reconstructs the product contract only through public behavior and compares it with the exact manifest |
| `test-data/golden/phase5_human_reports_v1.json` | Exact deterministic text, Markdown, HTML, SVG, and report-manifest artifacts |
| `test-data/golden/phase5_demo_v1.json` | Exact 12-file portfolio-demo manifest and hashes |

The public manifest hashes six earlier/current golden manifests but does not
hash itself, which avoids a circular dependency.

## Public surface frozen

The manifest freezes exports from four explicit namespaces:

- `analog_validation_app`: 185 exports;
- `analog_validation_app.cli`: 13 exports;
- `analog_validation_app.dashboard`: 37 exports;
- `analog_validation_app.dashboard.app`: 8 exports.

It also freezes:

- 15 schema-version constants;
- 10 enum member sets;
- 40 dataclass field contracts, including required/default and keyword-only
  behavior;
- 40 public constructor/function parameter shapes;
- 24 product-error inheritance relationships;
- 25 exception-to-user-issue mappings, including the internal-error fallback;
- product identity, evidence statements, source/profile catalogs, worker
  defaults, report filenames, deterministic-demo identity, and documented
  limitations;
- 13 serialized CLI/report/demo field groups;
- six earlier/current golden-manifest SHA-256 values;
- the absence of a product-level hardware-control/write surface.

## CLI contract

The local parser contract freezes these 24 command paths after the additive
calibration, frequency-response, and bounded live-monitor extensions:

```text
<root>
version
profiles
ports
coefficients
coefficients inspect
simulate
simulate read
simulate dc
simulate hysteresis
simulate calibration
simulate frequency
simulate monitor
replay
replay read
replay dc
replay hysteresis
replay calibration
replay frequency
replay monitor
observe
report
demo
dashboard
```

For every path, the option names, destinations, required flags, argument
counts, and choices are exact compatibility data.

## Calibration, frequency, and live-monitor extensions

The local post-beta calibration increment intentionally adds
`CalibrationJobService`, `make_calibration_service_factory`,
`CALIBRATION_ANALYSIS`, the calibration chart kind, defaulted configuration/UI
fields, and the four command paths shown above. Existing read, DC, hysteresis,
serial, report, demo, and Dashboard commands retain their option behavior.

Machine-readable CLI documents now declare `product-cli-output.v2`. Existing
v1 fields retain their meaning; execution documents add the nullable
`calibration_coefficients` and `coefficient_artifact` members, while structured
error documents add the explicit `hardware_claim` field. A strict v1 consumer
must explicitly add v2 support rather than ignoring the version change. The
separate `calibration-coefficients.v1` file is bounded, deterministic, and
create-new by default; loading validates it but never means it was applied.

The frequency-response increment adds `FrequencyResponseJobService`, its
Simulator factory, `FREQUENCY_RESPONSE_ANALYSIS`, a dedicated report chart,
defaulted configuration/UI fields, and `simulate frequency` / `replay
frequency`. Existing command paths retain their option behavior. Frequency
results use the existing v2 execution document and `result-export.v1`; no
additional nullable CLI artifact field was needed.

The bounded live-monitor increment adds `LIVE_MONITOR`,
`LiveMonitorJobService`, `LiveMonitorSession`, immutable trace/snapshot and
Dashboard panel types, `make_live_monitor_service_factory`, and `simulate
monitor` / `replay monitor`. The manifest freezes its memory, time-window,
interval, duration, and cooperative-control constants. It adds no Serial job,
output permission, analysis bundle, or engineering PASS/FAIL meaning. Existing
CLI documents remain `product-cli-output.v2`; execution documents use the
nullable `live_monitor` field only for this job.

| Exit code | Meaning |
|---:|---|
| 0 | Success |
| 1 | Completed engineering analysis with a failed criterion |
| 2 | Invalid command-line usage |
| 3 | Incomplete result |
| 4 | Requested capability is unsupported |
| 5 | Expected product operation error |
| 70 | Unexpected internal error |
| 130 | User cancellation |

These codes allow scripts and future integrations to react to machine-readable
outcomes without scraping human-facing text.

## Schema and serialized-field rule

Schema versions identify meaning, while serialized-field lists identify shape.
Both are frozen. A consumer can therefore check the version first and then
parse the documented fields without depending on private Python objects. The
freeze covers CLI version/profile/demo payloads, demo workflow/results/safety
metadata, demo artifacts, and human-report artifacts/manifests.

## Change procedure

When a Phase 5 golden test fails:

1. inspect the exact import, schema, field, enum, signature, command option,
   exit code, issue family, constant, or hash that changed;
2. treat unexplained drift as a regression and fix the implementation without
   editing the golden file;
3. for an intentional compatible addition, document why old consumers remain
   valid and add focused tests;
4. for an intentional breaking change, introduce a new schema/contract version
   and provide migration guidance or a compatibility adapter;
5. review evidence, privacy, read-only, and optional-dependency implications;
6. update golden data only after the design change is explicitly accepted;
7. rerun full tests, 100% package statement coverage, Ruff, mypy, dependency
   checks, isolated package builds, and repository-external installations.

Golden files are review artifacts, not snapshots to refresh blindly whenever a
test fails.

## Evidence boundary

Every result created while rebuilding this freeze is deterministic host-software
evidence. The test uses simulator, replay, temporary files, and injected
dependencies only. It does not discover or open a serial port, send bytes,
identify connected firmware, operate an MSP430, or measure an analog circuit.

Accordingly, this freeze supports the Phase 5 **Software Beta** claim only. It
does not prove AFE gain, cutoff frequency, hysteresis, saturation, protection,
ADC/DAC accuracy, bandwidth, noise, wiring, instrument accuracy, or any other
physical-hardware behavior.
