# Project Status

**Last updated:** 2026-08-30<br>
**Current milestone:** Software Phase 2 in progress — 5 of 8 checkpoints<br>
**Release maturity:** pre-MVP / verified simulator and replay parser<br>
**Highest evidence level:** HOST_TEST  
**Verified hardware claims:** 0

## Current product baseline

The repository currently provides an installable, controller-neutral Python core for Analog Validation Studio. It includes explicit measurement provenance, device capabilities and safe ranges, test-run conclusion semantics, one CRC/framing implementation, the versioned AFE v1 profile, strict non-executable JSON configuration, frozen protocol and replay compatibility data, an executable dependency boundary, the public `DeviceAdapter` lifecycle/safety contract, a configurable deterministic read-only SimulatorAdapter, and a strict immutable CSV Replay v1 parser.

The SimulatorAdapter models gain, offset, deterministic noise, saturation, Schmitt hysteresis, missing samples, communication faults, and CRC faults while retaining `SYNTHETIC` provenance. CSV Replay v1 can now validate complete local datasets without modifying them, but `CsvReplayAdapter` playback, test runners, product CLI, dashboard, serial transport, and a validated physical AFE are not yet implemented.

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
| 6 | CsvReplayAdapter speed, pause, resume, and EOF | Planned | — |
| 7 | Shared workflow and `UNSUPPORTED` capability degradation | Planned | — |
| 8 | Phase 2 integration, packaging, and closure | Planned | — |

## Current verification snapshot

| Gate | Result |
|---|---|
| Full pytest suite | 545 passed |
| Formal package statement coverage | 100% of 1,841 statements |
| DeviceAdapter lifecycle and safety | 36 tests passed |
| Reusable concrete-adapter contract | 8 shared checks passed against both reference and Simulator adapters |
| Simulator-specific unit tests | 69 passed; config, generator, channel independence, non-idealities, hysteresis, fault, clock, capability, and reconnect behavior |
| CSV Replay parser | 84 unit + 9 golden cases passed; 233/233 module statements covered |
| AFE golden compatibility | 20 valid + 9 invalid cases passed |
| Synthetic integration | 100 frames / 400 explicit `SYNTHETIC` Measurements passed |
| Core dependency boundary | Passed; standard library and own package only |
| Ruff | Passed on the full repository |
| mypy | Passed on `src`, `dashboard`, `tools`, and `tests` |
| Package build and external install | Passed; golden AFE parse/re-encode and safe configuration round trips returned true, output remained false |
| Hardware bench validation | Not performed |

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

Not safe to claim now:

- built or validated the physical analog front end;
- demonstrated ADC/DAC accuracy or UART reliability on hardware;
- verified any 0–3.3 V hardware range;
- completed an MSP430 hardware integration;
- released a software MVP or production-ready product.

## Next checkpoint

Software Phase 2 Step 6 will implement `CsvReplayAdapter` sequential playback, speed scaling, pause/resume, explicit EOF, and current `CSV_REPLAY` provenance. It must preserve original timestamps/references and pass the same shared read-only adapter contract as Simulator.

## GitHub and LinkedIn presentation policy

- Update the repository README and this status page only after a checkpoint passes its real quality gates.
- Keep implemented, planned, and hardware-verified features visibly separate.
- Link every numerical claim to a report or reproducible test command.
- Present this as an independent personal product project; do not merge it with the OSU Lab Bench Monitor Capstone or the separate MSP430 equipment-health project.
- Prepare final LinkedIn wording only after the repository has a stable public demo and the owner has reviewed what will be public.
