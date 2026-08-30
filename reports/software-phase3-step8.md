# Software Phase 3 Step 8 and Closure Report

**Date:** 2026-08-30<br>
**Milestone:** golden compatibility, packaging, and Software Phase 3 closure<br>
**Evidence class:** HOST_TEST / SYNTHETIC / CSV_REPLAY<br>
**Hardware used:** none<br>
**Verified bench claims:** 0

## Outcome

Software Phase 3 is complete: 8 of 8 checkpoints passed. The installable, controller-neutral Python package now contains versioned quality-aware analysis, safety-gated DC and hysteresis runners, immutable calibration, offline amplitude-response analysis, strict structured result export, and executable compatibility baselines.

Step 8 freezes the public surface and representative result meaning, reruns the complete regression and static gates, builds from an isolated environment, installs the wheel outside the repository, and closes the phase documentation. This is host-software completion only; it does not validate an analog circuit, signal source, ADC, controller, serial link, or instrument.

## Completed checkpoints

| Step | Delivered | Evidence |
|---:|---|---|
| 1 | Common immutable analysis vocabulary, lineage, quality policy, and voltage normalization | HOST_TEST |
| 2 | Quality-aware DC pairing, saturation exclusion, fit, residual, and incomplete semantics | HOST_TEST / SYNTHETIC |
| 3 | Versioned DC criteria and evidence-consistent TestRun mapping | HOST_TEST / SYNTHETIC |
| 4 | Controller-neutral DC plan/runner, atomic preflight, partial evidence, and safe cleanup | HOST_TEST |
| 5 | Directional hysteresis analysis, cycle statistics, criteria, runner, and cleanup | HOST_TEST / SYNTHETIC / CSV_REPLAY |
| 6 | Immutable linear calibration and offline amplitude-frequency response | HOST_TEST / SYNTHETIC |
| 7 | Strict deterministic `result-export.v1` JSON/CSV and safe local publication | HOST_TEST |
| 8 | Public API/exact-result freeze, full regression, package/install, and closure | HOST_TEST / SYNTHETIC |

## Frozen compatibility contract

`test-data/golden/phase3_public_api.json` freezes:

- 84 top-level public symbols inherited through Phase 3;
- 68 analysis, 10 runner, and 28 export public symbols;
- 12 Phase 3 schema/version constants and stable export limits/columns;
- eight public enum value sets;
- key public constructor/function parameter shapes;
- six result-export error inheritance relationships;
- exact SHA-256 hashes for the three Phase 3 input/result fixtures.

| Golden file | SHA-256 |
|---|---|
| `phase3_dc_sweep_input_v1.json` | `f84e13470a76698bc1c4c1a8140f41bedfebf6747510a8b8ebd7f8331f676fd7` |
| `phase3_dc_sweep_result_v1.json` | `a137b527303a7a8938b4bba7f74d28f35e9a9ca013474cd5946f4d6da9591547` |
| `phase3_hysteresis_result_v1.json` | `e7534508afea6dcf231387de293408d0a1b247ad3ee4a496b970dba4456f58db` |

The exact DC result fixes gain at 2, offset at 12 mV, and one explicit `HIGH_SATURATION` exclusion. The exact hysteresis result fixes the rising threshold at 1750 mV, falling threshold at 1550 mV, and width at 200 mV. Both are explicitly `SYNTHETIC`; their purpose is software compatibility, not electrical performance.

## Executed verification

| Gate | Actual result |
|---|---|
| Phase 3 public API golden tests | PASS — 8 |
| Phase 3 exact-result golden tests | PASS — 4 |
| Full pytest suite | PASS — 1,047 tests |
| Formal package statement coverage | PASS — 5,594/5,594, 100% |
| Full-repository Ruff | PASS |
| mypy on `src`, `dashboard`, `tools`, and `tests` | PASS — 99 source/test files |
| Formal-core dependency boundary | PASS |
| Local dependency check | PASS — no broken requirements |
| Isolated sdist and wheel build | PASS — `0.1.0.dev0` |
| Required Phase 3 golden data/tests in sdist | PASS — 6/6 |
| Repository-external wheel install | PASS |
| External public namespace smoke | PASS — 84 / 68 / 10 / 28 symbols |
| External exact JSON result parsing | PASS — DC and hysteresis remain `SYNTHETIC PASS` |
| External public runner safety smoke | PASS — DC and hysteresis both `UNSUPPORTED`, zero measurements |
| Installed-package dependency check | PASS — no broken requirements |
| Hardware or instrument test | NOT RUN |

Coverage applies only to the formal `src/analog_validation` package. It does not cover electrical behavior, real serial transport, future CLI/UI/reporting, or the legacy placeholders retained outside the formal core.

## Phase 3 exit criteria

| Criterion | Result |
|---|---|
| Analysis accepts explicit traceable records and rejects unsafe/ambiguous values | PASS |
| Excluded DC/hysteresis points retain reasons and references | PASS |
| PASS/FAIL requires complete evidence plus versioned criteria | PASS |
| Output runners perform capability/config/range/unit/safe-shutdown preflight before I/O | PASS |
| Interrupted and failing runs release owned adapter state and cannot produce PASS | PASS |
| Calibration derives new records without mutating source data | PASS |
| Frequency response has explicit interpolation/incomplete/ambiguous semantics | PASS |
| JSON/CSV exports preserve result, provenance, criteria, points, and limitations | PASS |
| Public Phase 3 API and representative exact results are frozen | PASS |
| Isolated package build, external install, parsing, and safe runner behavior pass | PASS |
| Hardware remains explicitly unverified | PASS — `VERIFIED_BENCH = 0` |

## Safe claims after Phase 3

- implemented a controller-neutral, versioned analysis and test-runner layer;
- retained point-level provenance, quality decisions, exclusions, fit residuals, transitions, and cycle statistics;
- separated acquisition completion, mathematical analysis, acceptance criteria, and TestRun outcome;
- implemented immutable calibration and offline frequency-response calculations;
- exported strict machine-readable JSON/CSV without changing conclusions or evidence source;
- froze public APIs and exact representative synthetic results with executable golden tests;
- verified the package through tests, static checks, isolated build, external install, result parsing, and safe unsupported-runner behavior.

## Explicitly not implemented or verified

- no serial discovery, streaming parser, sequence tracker, retry/reconnect, or controller profile;
- no product CLI, Dashboard workflow, plotting, or human-readable report;
- no finalized calibration/frequency TestRun mapping or dedicated result-export builders;
- no MSP430, RP2040, STM32, USB/UART adapter, ADC, DAC, PWM, AFE, cable, supply, ground, or laboratory instrument was connected;
- no real gain, offset, saturation, threshold, hysteresis, bandwidth, noise, timing, accuracy, repeatability, or shutdown behavior was measured.

## Next milestone

Software Phase 4 has not started. Its first checkpoint must be a separate file-level plan for serial byte streaming, sequence/error recovery, controller-neutral connection settings, AFE/MSP430-compatible profiles, raw-frame evidence, and hardware-optional tests. No serial dependency or hardware assumption should enter the formal core before that plan is reviewed.
