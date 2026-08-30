# Project Status

**Last updated:** 2026-08-30<br>
**Current milestone:** Software Phase 3 in progress — 6 of 8 checkpoints complete<br>
**Release maturity:** pre-MVP / core runners plus offline calibration/frequency analysis implemented<br>
**Highest evidence level:** HOST_TEST  
**Verified hardware claims:** 0

## Current product baseline

The repository currently provides an installable, controller-neutral Python core for Analog Validation Studio. It includes explicit measurement provenance, device capabilities and safe ranges, test-run conclusion semantics, one CRC/framing implementation, the versioned AFE v1 profile, strict non-executable JSON configuration, frozen protocol and replay compatibility data, an executable dependency boundary, the public `DeviceAdapter` lifecycle/safety contract, a configurable deterministic read-only SimulatorAdapter, a strict immutable CSV Replay v1 parser, a read-only CsvReplayAdapter, and a shared adapter-neutral read workflow.

The SimulatorAdapter models gain, offset, deterministic noise, saturation, Schmitt hysteresis, missing samples, communication faults, and CRC faults while retaining `SYNTHETIC` provenance. CsvReplayAdapter validates an explicit channel map, replays immutable records with independent channel cursors, supports immediate/scaled timing plus pause/resume/speed controls, exposes typed EOF, and forces current `CSV_REPLAY` provenance. The shared workflow remains a frozen read-only acquisition API. Separate DC and hysteresis runners own output-capable adapter preflight, ordered acquisition, safe cleanup, analysis, and TestRun mapping. Formal calibration and offline frequency-response analysis are implemented; product CLI, dashboard, serial transport, exports, and a validated physical AFE are not yet implemented.

Software Phase 3 Steps 1–6 add the versioned analysis foundation, formal DC and directional hysteresis math, criteria mapping, `analog_validation.runners`, immutable linear calibration, and offline amplitude-response analysis. Calibration keeps observed/reference source lineage and creates derived Measurements instead of rewriting evidence. Frequency response accepts explicit points only and publishes a cutoff only for one explainable crossing. No Step 6 code performs I/O.

## Software Phase 1 checkpoints

| Step | Deliverable | Status | Evidence |
|---:|---|---|---|
| 1 | Installable `src/analog_validation` package and reproducible wheel | Complete | HOST_TEST |
| 2 | Stable public error hierarchy | Complete | HOST_TEST |
| 3 | Provenance-aware immutable Measurement model | Complete | HOST_TEST |
| 4 | Capability, safe range, and TestRun models | Complete | HOST_TEST |
| 5 | Single CRC implementation and bounded ASCII framing | Complete | HOST_TEST |
| 6 | Versioned AFE v1 telemetry, commands, capability exchange, and mappings | Complete | HOST_TEST |
| 7 | Versioned configuration models and safe validation | Complete | HOST_TEST |
| 8 | Golden AFE messages, legacy migration, and Phase 1 closure | Complete | HOST_TEST |

## Software Phase 2 checkpoints

| Step | Deliverable | Status | Evidence |
|---:|---|---|---|
| 1 | `DeviceAdapter`, lifecycle states, safety gates, and typed adapter errors | Complete | HOST_TEST |
| 2 | Reusable adapter contract suite | Complete | HOST_TEST |
| 3 | Deterministic SimulatorAdapter data flow | Complete | HOST_TEST / SYNTHETIC |
| 4 | Simulator non-idealities and controlled faults | Complete | HOST_TEST / SYNTHETIC |
| 5 | Versioned immutable CSV replay schema/parser | Complete | HOST_TEST |
| 6 | CsvReplayAdapter speed, pause, resume, and EOF | Complete | HOST_TEST / CSV_REPLAY |
| 7 | Shared workflow and `UNSUPPORTED` capability degradation | Complete | HOST_TEST / SYNTHETIC / CSV_REPLAY |
| 8 | Phase 2 API freeze, integration, packaging, and closure | Complete | HOST_TEST / SYNTHETIC / CSV_REPLAY |

## Current verification snapshot

| Gate | Result |
|---|---|
| Full pytest suite | 992 passed |
| Formal package statement coverage | 100% of 4,954 statements |
| Phase 3 common analysis semantics | 56 focused tests; 244/244 statements covered |
| Phase 3 DC sweep analysis | 81 focused tests; 325/325 statements covered |
| Phase 3 DC criteria and TestRun mapping | 67 focused tests; 201/201 statements covered |
| Phase 3 safety-gated DC runner | 58 focused tests; 348/348 module statements covered |
| Phase 3 hysteresis analysis, criteria, and runner | 38 focused tests; 892/892 new module statements covered |
| Phase 3 calibration and offline frequency response | 48 focused tests; 705/705 new module statements covered |
| DeviceAdapter lifecycle and safety | 36 tests passed |
| Reusable concrete-adapter contract | 8 shared checks passed against reference, Simulator, and CSV Replay adapters |
| Simulator-specific unit tests | 69 passed; config, generator, channel independence, non-idealities, hysteresis, fault, clock, capability, and reconnect behavior |
| CSV Replay parser | 84 unit + 9 golden cases passed; 233/233 module statements covered |
| CSV Replay adapter | 45 focused unit + 8 shared-contract checks passed; 185/185 module statements covered |
| Shared read workflow | 25 unit + 8 Simulator/CSV integration tests passed; 201/201 workflow statements covered |
| Phase 2 golden compatibility | 7 public API + 4 end-to-end workflow checks passed |
| AFE golden compatibility | 20 valid + 9 invalid cases passed |
| Synthetic integration | 100 frames / 400 explicit `SYNTHETIC` Measurements passed |
| Core dependency boundary | Passed; standard library and own package only |
| Ruff | Passed on the full repository |
| mypy | Passed on `src`, `dashboard`, `tools`, and `tests` — 88 source files |
| Package build and external install | Passed; sdist contains all four Step 6 source/test files, and an external wheel install preserved the frozen 84-symbol top level while exposing 68 analysis and 10 runner symbols |
| Hardware bench validation | Not performed |

## Software Phase 3 checkpoints

| Step | Deliverable | Status | Evidence |
|---:|---|---|---|
| Plan | File-level architecture, scope, safety boundary, and exit gates | Complete | HOST_TEST planning record |
| 1 | Common analysis vocabulary and quality policy | Complete | HOST_TEST |
| 2 | Provenance-aware DC sweep analysis | Complete | HOST_TEST / SYNTHETIC |
| 3 | Versioned DC criteria and TestRun mapping | Complete | HOST_TEST / SYNTHETIC |
| 4 | Controller-neutral, safety-gated DC sweep runner | Complete | HOST_TEST |
| 5 | Directional hysteresis analysis and runner | Complete | HOST_TEST / SYNTHETIC / CSV_REPLAY |
| 6 | Calibration and offline frequency response | Complete | HOST_TEST / SYNTHETIC |
| 7 | Versioned CSV/JSON result export | Planned | — |
| 8 | Golden compatibility, packaging, and closure | Planned | — |

## Public claim boundary

Safe to claim now:

- designed and tested a controller-neutral Python protocol/domain foundation;
- implemented CRC-16/CCITT-FALSE and bounded ASCII framing;
- implemented a versioned AFE v1 profile with strict host-side validation;
- implemented strict versioned JSON configuration with explicit output gates;
- froze AFE v1 wire/model/error compatibility and a deterministic 100-frame pipeline;
- removed the Phase 0 protocol/shared-model duplicate surface;
- implemented explicit provenance and capability/safety semantics;
- maintained reproducible automated host tests and engineering reports.
- implemented a controller-neutral adapter lifecycle with explicit host-side capability, configuration, unit, provenance, and output-safety gates.
- implemented a deterministic read-only SimulatorAdapter that returns only explicit `SYNTHETIC` Measurements and shares the frozen AFE generation formula.
- implemented configurable gain, offset, deterministic noise, upper/lower saturation, Schmitt hysteresis, missing samples, communication errors, and CRC errors in the simulator.
- implemented immutable CSV Replay v1 records/datasets, bounded read-only parsing, explicit completion counts, and stable replay error families.
- implemented read-only CsvReplayAdapter playback with explicit channel capabilities, preserved source references, forced `CSV_REPLAY` provenance, independent cursors, scaled timing, pause/resume, speed control, and typed EOF.
- implemented one versioned read workflow for Simulator and CSV Replay with immutable requests/results, atomic capability degradation, explicit incomplete-data reporting, and guaranteed lifecycle cleanup.
- froze public imports, schema values, enum values, signature shapes, error bases, replay hashes, and complete Simulator/CSV/UNSUPPORTED workflow meaning in machine-readable compatibility files.
- implemented a versioned common analysis foundation with immutable record lineage, explicit point dispositions/reasons, one-source batches, default-deny suspect quality handling, and strict finite V/mV normalization.
- implemented versioned provenance-aware DC sweep pairing, point-level inclusive saturation/quality exclusion, explicit incomplete-analysis gaps, and ordinary least-squares metrics with retained predictions and residuals.
- implemented versioned DC acceptance criteria and per-rule results, mapping only complete evidence-consistent evaluations to PASS/FAIL while preserving missing criteria/data as INCOMPLETE.
- implemented a versioned controller-neutral DC plan/runner with all-setpoint permission/capability/range/unit/safe-shutdown preflight, injected settle/abort behavior, repetition ordering, partial-evidence retention, and cleanup-before-evaluation semantics.
- verified that the test-only output reference can exercise host lifecycle logic while the product Simulator and CSV Replay adapters remain zero-acquisition `UNSUPPORTED` for output.
- implemented versioned directional hysteresis point/transition/cycle models, adjacent-interval midpoint estimates, repeated-cycle statistics, and criteria-gated conclusions.
- implemented a safety-gated rising/falling hysteresis runner and verified that missing points/transitions stay incomplete while direction conflicts, chatter, non-binary states, and inverted thresholds are rejected.

Not safe to claim now:

- built or validated the physical analog front end;
- demonstrated ADC/DAC accuracy or UART reliability on hardware;
- verified any 0–3.3 V hardware range;
- completed an MSP430 hardware integration;
- released a software MVP or production-ready product.

## Next checkpoint

Software Phase 3 Step 6 is complete. Step 7 will add immutable, versioned CSV/JSON result export with stable ordering, provenance, criteria, metrics, point decisions, and safe no-overwrite behavior. Real hardware remains later work.

## GitHub and LinkedIn presentation policy

- Update the repository README and this status page only after a checkpoint passes its real quality gates.
- Keep implemented, planned, and hardware-verified features visibly separate.
- Link every numerical claim to a report or reproducible test command.
- Present this as an independent personal product project; do not merge it with the OSU Lab Bench Monitor Capstone or the separate MSP430 equipment-health project.
- Prepare final LinkedIn wording only after the repository has a stable public demo and the owner has reviewed what will be public.
