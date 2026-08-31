# Project Status

**Last updated:** 2026-08-31<br>
**Current milestone:** Software Phase 5 in progress — checkpoint 1 of 8 complete<br>
**Release maturity:** pre-MVP / product contracts and installable CLI foundation complete<br>
**Highest evidence level:** BENCH_CONTROLLER — MSP430 UART compatibility only<br>
**Verified AFE hardware performance claims:** 0

## Current product baseline

The repository currently provides an installable, controller-neutral Python core for Analog Validation Studio. It includes explicit measurement provenance, device capabilities and safe ranges, test-run conclusion semantics, one CRC implementation, a profile-neutral CRC envelope with a backward-compatible AFE wrapper, the versioned AFE v1 protocol, explicit AFE channel-name mapping, strict non-executable JSON configuration, frozen protocol and replay compatibility data, an executable dependency boundary, the public `DeviceAdapter` lifecycle/safety contract, a configurable deterministic read-only SimulatorAdapter, a strict immutable CSV Replay v1 parser, a read-only CsvReplayAdapter, a shared adapter-neutral read workflow, a profile-neutral bounded byte-stream/sequence foundation, a replaceable serial backend port, deterministic host-tested serial lifecycle, bounded memory-only raw-record provenance, a public serial-profile extension point, independent AFE and read-only MSP430 Equipment Health v1 profiles, a receive-only `SerialAdapter`, an optional packaged pyserial backend that leaves the formal core driver-free, and a Phase 4 machine-readable compatibility freeze.

The SimulatorAdapter models gain, offset, deterministic noise, saturation, Schmitt hysteresis, missing samples, communication faults, and CRC faults while retaining `SYNTHETIC` provenance. CsvReplayAdapter validates an explicit channel map, replays immutable records with independent channel cursors, supports immediate/scaled timing plus pause/resume/speed controls, exposes typed EOF, and forces current `CSV_REPLAY` provenance. The shared workflow remains a frozen read-only acquisition API. Separate DC and hysteresis runners own output-capable adapter preflight, ordered acquisition, safe cleanup, analysis, and TestRun mapping. Formal calibration, offline frequency-response analysis, versioned structured result exports, both serial business profiles, their receive-only adapter composition, and a narrow MSP430 UART HIL are implemented. Phase 5 Step 1 now adds immutable product request/result contracts, a reviewed source/profile catalog, stable user issues, and an installed `analog-validation version/profiles` entry point; an owning worker, test-running CLI workflows, dashboard, human-readable reports, and a validated physical AFE are not yet implemented.

The reviewed Software Phase 5 plan defines a separate `analog_validation_app` product layer, one `analog-validation` command, a bounded single-owner cancellable worker, deterministic HTML/SVG reporting, a local offline Tkinter/ttk Dashboard, a six-step beginner workflow, and an installed-package deterministic demo. Step 1 of 8 is implemented: the product-layer identity/contracts/catalog/issue boundary and minimal CLI are real, while worker/workflows/reports/UI remain planned. Architecture tests enforce consumption of the frozen core without copying device/profile or engineering-analysis logic.

Software Phase 3 is complete. Steps 1–7 add the versioned analysis foundation, formal DC and directional hysteresis math, criteria mapping, `analog_validation.runners`, immutable linear calibration, offline amplitude-response analysis, and `result-export.v1`. Step 8 freezes the 84-symbol Phase 2 top level, 68 analysis exports, 10 runner exports, 28 export symbols, 12 Phase 3 schemas, public enums/signatures/errors, and exact representative DC/hysteresis results. The golden values remain HOST_TEST/SYNTHETIC software evidence.

Software Phase 4 Step 1 adds `analog_validation.transport`: a device/profile-neutral bounded LF stream state machine and modular sequence tracker. It handles fragmented/coalesced chunks, bounded overlong discard/recovery, disconnect reset, first/in-order/gap/duplicate/out-of-order classification, and AFE 16-bit/MSP430 32-bit wrap under HOST_TEST. No serial backend, COM access, controller profile, SerialAdapter, or HIL claim was added.

Software Phase 4 Step 2 adds `analog_validation.protocol.envelope`, keeping the original AFE `Frame`/encode/decode API as a thin compatibility wrapper. A three-record golden fixture proves exact AFE-shaped and non-namespaced MSP430-shaped token/CRC round trips without interpreting MSP430 business fields. `afe-channel-map.v1` freezes explicit legacy-to-canonical channel conversion while leaving historical telemetry Measurements unchanged. A mixed-profile fragmented stream now passes through the Step 1 framer and Step 2 envelope in one integration test. No OS serial backend, COM access, device profile, or physical I/O was added.

Software Phase 4 Step 3 adds `SerialBackend`, `SerialConnectionSettings`, `SerialSession`, transport-local typed errors, and `BoundedRawEventLog`. A test-only memory backend covers discovery, partial/coalesced reads, normal timeout, open/read/close failures, disconnect/reset, finite reconnect, overlong recovery, event eviction, UTC, privacy limits, and explicit `PENDING_PROFILE/PARSED/REJECTED` outcomes. A composite path reaches neutral CRC and sequence classification without adding business parsing. The formal core still has no pyserial/OS-driver import; no physical port or board was accessed.

Software Phase 4 Step 4 adds `analog_validation.profiles` and `AfeV1SerialProfile`. The profile explicitly declares `afe`/version `1`, 16-bit sequence, and the 128-byte limit; maps telemetry through the frozen canonical channel boundary; aggregates strict capability transactions; records typed parse/reject outcomes; and rolls state back if raw provenance cannot be finalized. All 20 valid and 9 invalid historical AFE records pass through the new profile path. A fragmented/coalesced in-memory chain reaches canonical Measurements, read-only capabilities, 16-bit wrap, and CRC rejection. No OS serial backend, COM access, MSP430 semantics, or physical I/O was added.

Software Phase 4 Step 5 adds `protocol.msp430_health_v1` and `Msp430HealthV1SerialProfile` from the peer project's frozen public UART Protocol v1 contract at commit `151fdcfa60661bce1ba04af13c1d3509706f7d4a`. It parses device-output `TEL/ACK/STS/CFG/LOG`, tracks only 32-bit TEL continuity, maps unavailable temperatures and INA219-fault zeros to explicit missing/invalid Measurements, and preserves raw sentinels, power, state, and fault bits. Its static capabilities are read-only with no output or safe shutdown; no command encoder exists. Ten valid and eleven invalid repository-owned fixtures plus an in-memory serial chain pass without importing peer runtime code or accessing a physical port.

Software Phase 4 Step 6 adds `analog_validation.serial_adapters`. `SerialAdapter` composes one closed `SerialSession`, one explicitly selected profile, and one explicit capability projector behind the frozen `DeviceAdapter` lifecycle. It is receive-only: there is no write method or device-command escape hatch, projected commands are limited to reads, and safe shutdown is never advertised. AFE capabilities are explicitly aliased to canonical workflow channels while the native snapshot remains available for audit; MSP430 uses its static read-only capability contract. Both configurations pass the reusable eight-check adapter contract and the shared `ReadWorkflow`; reconnect invalidates buffered data and capability trust. DC and hysteresis runners return `UNSUPPORTED` with zero writes for the MSP430 configuration. All evidence uses an in-memory backend and `HOST_TEST`; no COM port or board was accessed.

Software Phase 4 Step 7 adds the separately packaged, lazy-loaded
`analog_validation_pyserial` backend and a bounded repository-owned HIL tool.
The accepted COM4 capture passed five CRC-valid TEL records through the current
`SerialAdapter` and `ReadWorkflow`: sequence 27917–27921 and uptime were
continuous, 25 Measurements retained `BENCH_CONTROLLER`, and application write
calls/bytes were 0/0. Five no-CRC HB lines remained strict profile rejections but
were separately recognized as exact, TEL-aligned legacy diagnostics documented
by the peer interface; malformed/unaligned diagnostics remain anomalies. The
controller reported `FAULT 0x0015` and missing/fault sentinels, so external
sensors were not validated. Passive telemetry carries no firmware-version
field, therefore exact current firmware identity remains unconfirmed. No AFE,
fan, external 5 V, or wiring was tested.

Software Phase 4 Step 8 freezes 121 exports across seven namespaces, three
schemas, stable profile identities, 12 enum/flag sets, 21 public call shapes, 17
error relationships, and five fixture hashes. Two exact external-backend
composites protect AFE/MSP430 session→profile→adapter→workflow behavior,
16/32-bit wrap, CRC rejection, unavailable mapping, raw lineage, deterministic
close, `HOST_TEST` provenance, and the no-write boundary. Full regression,
isolated build, and base/serial clean installations passed. Step 8 opened no
port and did not repeat or broaden the Step 7 HIL.

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
| Full pytest suite | 1,645 passed |
| Formal + optional + product package statement coverage | 100% of 7,714 statements |
| Phase 5 Step 1 product layer | Product contracts/catalog/issues/CLI and one-way dependency checks passed; clean base-wheel commands run without pyserial or display access |
| Phase 4 golden compatibility | 13 checks; 121 exports, 3 schemas, 12 enum/flag sets, 21 signatures, 17 errors, 5 fixture hashes, and exact AFE/MSP external-backend results frozen |
| Phase 4 optional pyserial backend and receive-only HIL | 127/127 optional-package statements covered; base/serial external installs passed; 5/5 CRC-valid continuous TEL through COM4, 25 Measurements, zero writes, exact firmware unconfirmed |
| Phase 4 receive-only SerialAdapter | 74 new tests; 282/282 added statements covered; AFE/MSP shared contracts, workflows, bounded failure handling, reconnect invalidation, and zero-write runner degradation passed |
| Phase 4 MSP430 Equipment Health v1 profile | 121 new tests; 416/416 new-module statements covered; 10 valid + 11 invalid independent fixtures passed |
| Phase 4 AFE v1 serial profile | 59 new tests; 225/225 added statements covered; exact 20-valid/9-invalid golden migration passed |
| Phase 4 serial lifecycle/raw-event boundary | 88 new tests; 428/428 added statements covered |
| Phase 4 stream/sequence foundation | 32 focused tests; 158/158 statements covered |
| Phase 4 neutral envelope/channel mapping | 51 new tests; envelope/mapping/framing 176/176 statements covered |
| Phase 3 common analysis semantics | 56 focused tests; 244/244 statements covered |
| Phase 3 DC sweep analysis | 81 focused tests; 325/325 statements covered |
| Phase 3 DC criteria and TestRun mapping | 67 focused tests; 201/201 statements covered |
| Phase 3 safety-gated DC runner | 58 focused tests; 348/348 module statements covered |
| Phase 3 hysteresis analysis, criteria, and runner | 38 focused tests; 892/892 new module statements covered |
| Phase 3 calibration and offline frequency response | 48 focused tests; 705/705 new module statements covered |
| Phase 3 versioned result export | 43 focused tests; 640/640 export statements covered |
| Phase 3 golden compatibility | 8 public API + 4 exact-result checks passed |
| DeviceAdapter lifecycle and safety | 36 tests passed |
| Reusable concrete-adapter contract | 8 shared checks passed against reference, Simulator, CSV Replay, AFE SerialAdapter, and MSP430 SerialAdapter configurations |
| Simulator-specific unit tests | 69 passed; config, generator, channel independence, non-idealities, hysteresis, fault, clock, capability, and reconnect behavior |
| CSV Replay parser | 84 unit + 9 golden cases passed; 233/233 module statements covered |
| CSV Replay adapter | 45 focused unit + 8 shared-contract checks passed; 185/185 module statements covered |
| Shared read workflow | 25 unit + 8 Simulator/CSV integration tests passed; 201/201 workflow statements covered |
| Phase 2 golden compatibility | 7 public API + 4 end-to-end workflow checks passed |
| AFE golden compatibility | 20 valid + 9 invalid cases passed |
| Synthetic integration | 100 frames / 400 explicit `SYNTHETIC` Measurements passed |
| Core dependency boundary | Passed; standard library and own package only |
| Ruff | Passed on the full repository |
| mypy | Passed on `src`, `tools`, and `tests` — 147 source/test files |
| Package build and external install | Passed; current sdist/wheel contain the product package and one console entry point; fresh base install ran help/version/profiles without pyserial or optional imports |
| Physical controller UART | PASS with limitations — receive-only COM4 Protocol v1 compatibility; exact firmware, disconnect recovery, external peripherals, and AFE are unverified |
| AFE hardware bench validation | Not performed |

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
| 7 | Versioned CSV/JSON result export | Complete | HOST_TEST |
| 8 | Golden compatibility, packaging, and closure | Complete | HOST_TEST / SYNTHETIC |

## Software Phase 4 checkpoints

| Step | Deliverable | Status | Evidence |
|---:|---|---|---|
| Plan | Serial/profile architecture, peer-project boundary, safety and exit gates | Complete | HOST_TEST planning record |
| 1 | Profile-neutral bounded byte stream and modular sequence tracking | Complete | HOST_TEST |
| 2 | Profile-neutral CRC envelope, AFE compatibility wrapper, and channel mapping | Complete | HOST_TEST |
| 3 | Serial discovery, lifecycle, timeout, reconnect and raw logs | Complete | HOST_TEST |
| 4 | AFE v1 serial profile | Complete | HOST_TEST |
| 5 | Independent read-only MSP430 Equipment Health v1 profile | Complete | HOST_TEST |
| 6 | Receive-only SerialAdapter and shared workflow integration | Complete | HOST_TEST |
| 7 | Optional owner-approved read-only MSP430 HIL | Complete with identity limitation | BENCH_CONTROLLER — UART compatibility only |
| 8 | Phase 4 golden compatibility, build and closure | Complete | HOST_TEST |

## Software Phase 5 checkpoints

| Step | Deliverable | Status | Evidence |
|---:|---|---|---|
| Plan | Product-layer files, safety boundaries, workflow order, and exit gates | Complete | HOST_TEST planning record |
| 1 | Product contracts, reviewed catalog, user issues, and installable CLI skeleton | Complete | HOST_TEST / external base-wheel install |
| 2 | Bounded single-owner cancellable worker | Next | Not run |
| 3 | Stable test-running CLI workflows | Planned | Not run |
| 4 | Evidence-visible human reports and deterministic charts | Planned | Not run |
| 5 | Dashboard state, presenter, and desktop shell | Planned | Not run |
| 6 | Beginner workflow and read-only serial wiring | Planned | Not run |
| 7 | Reproducible demo and product-quality acceptance | Planned | Not run |
| 8 | Public compatibility freeze and software Beta closure | Planned | Not run |

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
- implemented immutable `result-export.v1` bundles, typed DC/hysteresis builders, deterministic strict JSON/CSV round trips, source/record/criteria/point consistency checks, and atomic no-overwrite file publication.
- froze Phase 3 public namespaces, 12 schemas, stable constants, 8 enum sets, key signatures, export error families, golden hashes, and exact synthetic DC/hysteresis result meaning.
- implemented a profile-neutral bounded LF byte-stream state machine with raw-byte preservation, bounded overlong discard/recovery, disconnect reset, and structured issues.
- implemented profile-configurable modular sequence tracking with explicit continuity results and tested 16/32-bit wrap behavior.
- implemented a namespace-neutral token/CRC envelope while preserving the frozen AFE wrapper, bytes, errors, and public contracts.
- froze explicit `afe-channel-map.v1` legacy/canonical conversion and verified the Step 1 byte-stream to Step 2 envelope composite path.
- implemented a replaceable serial backend port and deterministic discovery/open/bounded-read/timeout/disconnect/finite-reconnect/close lifecycle without importing an OS driver.
- implemented bounded memory-only raw-record provenance with exact bytes, UTC, explicit profile, parse/error outcome, optional sequence observation, eviction counters, and privacy limits.
- verified the installed wheel can run backend→raw→CRC→PARSED→close without pyserial while preserving all Phase 1–3 golden contracts.
- implemented the public serial-profile contract and AFE v1 profile with explicit identity, canonical telemetry mapping, 16-bit continuity, strict capability aggregation, typed raw outcomes, and rollback-safe state.
- verified all historical AFE golden records and an installed raw→profile→Measurement smoke without pyserial; these remain HOST_TEST rather than hardware evidence.
- implemented the independent read-only MSP430 Equipment Health v1 parser/profile with 32-bit TEL continuity, typed response records, sentinel/fault-aware Measurements, raw field retention, and no command/output capability.
- froze 10 valid and 11 invalid repository-owned MSP430 interoperability records and verified a fragmented in-memory serial chain without importing the peer project's runtime code.
- implemented one receive-only `SerialAdapter` composition for both AFE and MSP430 profiles, with explicit identity matching, bounded polling/buffering, raw provenance, stable error translation, and fail-closed capability invalidation after reconnect.
- explicitly projected AFE wire capability names to canonical workflow channels while retaining the native snapshot and preventing output-command escalation.
- passed the same reusable adapter contract and shared workflow with both serial profiles, and proved read-only MSP430 DC/hysteresis runner degradation is `UNSUPPORTED` with zero writes.
- implemented an optional pyserial backend with lazy dependency loading, exact
  line-setting mapping, bounded reads, privacy-minimal discovery, deterministic
  close, and no public write path.
- completed an Analog-owned receive-only COM4 HIL through the current
  SerialAdapter/ReadWorkflow with five CRC-valid continuous TEL records, zero
  application writes, retained sentinels/faults, and explicit firmware/AFE
  limitations.
- froze the Phase 4 public surface, profile identities, schemas, enum members,
  call shapes, error hierarchy, protocol fixtures, and exact AFE/MSP430
  external-backend composites with executable HOST_TEST golden contracts.
- passed release-style regression, 100% package coverage, static checks,
  isolated build, and clean base/serial wheel installation after the freeze.
- implemented immutable, output-denying product job/result contracts, a reviewed exact-match source/profile catalog, stable expected-error-to-user-issue mapping, and deterministic human/JSON product identity output.
- installed the base wheel outside the repository and ran the console/module entry points without pyserial, Tkinter import, serial access, or a display; retired the obsolete root Dashboard source without changing Phase 1–4 golden behavior.

Not safe to claim now:

- built or validated the physical analog front end;
- demonstrated ADC/DAC accuracy or long-duration UART reliability on hardware;
- verified any 0–3.3 V hardware range;
- identified the exact current MSP430 firmware image from passive telemetry;
- validated MSP430 external sensors, INA219, fan, or wiring;
- released a software MVP or production-ready product.

## Next checkpoint

Software Phase 5 Step 1 is complete. The next checkpoint is Step 2 only: add a
bounded event model and single-owner cooperative-cancellation worker around
injected host-side services. Its tests must prove deterministic cleanup, no
orphan threads, monotonic bounded events, and no promotion of cancelled,
incomplete, unsupported, or failed work to PASS. Step 2 will not open a physical
port or implement reports or a Dashboard window.

## GitHub and LinkedIn presentation policy

- Update the repository README and this status page only after a checkpoint passes its real quality gates.
- Keep implemented, planned, and hardware-verified features visibly separate.
- Link every numerical claim to a report or reproducible test command.
- Present this as an independent personal product project; do not merge it with the OSU Lab Bench Monitor Capstone or the separate MSP430 equipment-health project.
- Prepare final LinkedIn wording only after the repository has a stable public demo and the owner has reviewed what will be public.
