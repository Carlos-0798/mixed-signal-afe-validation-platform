# Software Phase 1 Step 7 Validation Report

**Date:** 2026-08-29<br>
**Scope:** versioned configuration model, strict JSON I/O, output-safety gates, and device-capability matching<br>
**Evidence class:** HOST_TEST<br>
**Hardware used:** none

## Result

Software Phase 1 Step 7 is complete. The formal package now has immutable configuration models for profile identity, channel role, unit, enabled state, output safety range, timeouts, evidence source, configuration version, and schema version.

The parser accepts strict UTF-8 JSON as data only. It does not import configuration as Python and does not use `eval`, `exec`, shell execution, YAML object constructors, or templates.

## Implemented controls

- exact required/optional field validation at every JSON object level;
- duplicate and unknown field rejection;
- controlled profile, evidence, role, and unit values;
- rejection of malformed UTF-8, `NaN`, and infinities;
- 1 MiB configuration-file size limit and `.json` extension check;
- finite, internally consistent timeouts;
- explicit `allow_output` gate, disabled by default;
- configured output range nested inside the device-advertised range;
- required device output command and `SAFE_SHUTDOWN` capability;
- no device I/O in the configuration package.

## Executed verification

| Gate | Command | Result |
|---|---|---|
| Step 7 focused tests | `python -m pytest tests/unit/test_config_models.py tests/unit/test_config_validation.py --cov=analog_validation.config --cov-report=term-missing` | PASS — 80 tests; 311/311 statements |
| Full suite with package coverage | `python -m pytest --cov=analog_validation --cov-report=term-missing` | PASS — 304 tests; 1,211/1,211 statements |
| Static lint | `python -m ruff check src dashboard/protocol.py tools tests` | PASS |
| Static typing | `python -m mypy src dashboard tools tests` | PASS — no issues in 43 source files |
| Local dependency check | `python -m pip check` | PASS — no broken requirements |
| Isolated sdist and wheel build | `python -m build` with a temporary output directory | PASS |
| Source-distribution contents | Step 7 tests and read-only example present | PASS |
| Repository-external wheel install | fresh temporary virtual environment, `pip install --no-deps` | PASS |
| Installed configuration round trip | schema, equality, and output-default smoke check | PASS — `validation-config.v1 True False` |
| Installed-package dependency check | external `python -m pip check` | PASS — no broken requirements |

Coverage is statement coverage of the formal `src/analog_validation` package. It is not a physical test-coverage or product-completeness claim.

## Beginner explanation

A configuration file is a contract between the user, the software, and a future device adapter. The user can ask for a channel and define a narrower software safety limit, but the selected device must separately advertise that channel, a compatible unit and range, the needed output command, and safe shutdown. The narrowest valid limit wins.

Even after those checks pass, Step 7 performs no output. Future hardware use still requires verified wiring, power, common ground, polarity, measured ranges, and tested shutdown behavior.

## Demonstrated failure handling

Tests deliberately rejected missing fields, extra fields, duplicate JSON keys, executable-looking strings, invalid UTF-8, non-standard numbers, wrong enums, unsafe timeouts, mismatched units, absent channels, over-wide output limits, absent output commands, and absent safe shutdown.

## Not performed

- no serial port or instrument connection;
- no MSP430, ADC, DAC, PWM, GPIO, or AFE hardware use;
- no voltage, timing, accuracy, noise, or shutdown measurement;
- no claim that example 0–3.3 V ranges are physically safe;
- no production adapter, runner, CLI, or dashboard.

## Next step

Software Phase 1 Step 8 will freeze AFE business-message golden vectors, finish the one-time legacy migration, add the deterministic 100-frame integration test to the formal suite, and produce the Phase 1 closure report.
