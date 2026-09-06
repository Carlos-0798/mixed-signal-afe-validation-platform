# Project Status

**Last updated:** 2026-09-06<br>
**Current milestone:** Combined calibration, frequency-response, and bounded offline live-monitor increment committed locally at `5dcc2d0`; owner-selected MIT integration locally verified and awaiting commit review<br>
**Release maturity:** Audited `0.1.0b1` private-beta baseline on `main`; the combined increment has not been pushed, merged, tagged, or released<br>
**Highest evidence level:** BENCH_CONTROLLER — MSP430 UART compatibility only<br>
**Verified AFE hardware performance claims:** 0

## Current product baseline

The repository currently provides an installable, controller-neutral Python core for Analog Validation Studio. It includes explicit measurement provenance, device capabilities and safe ranges, test-run conclusion semantics, one CRC implementation, a profile-neutral CRC envelope with a backward-compatible AFE wrapper, the versioned AFE v1 protocol, explicit AFE channel-name mapping, strict non-executable JSON configuration, frozen protocol and replay compatibility data, an executable dependency boundary, the public `DeviceAdapter` lifecycle/safety contract, a configurable deterministic read-only SimulatorAdapter, a strict immutable CSV Replay v1 parser, a read-only CsvReplayAdapter, a shared adapter-neutral read workflow, a profile-neutral bounded byte-stream/sequence foundation, a replaceable serial backend port, deterministic host-tested serial lifecycle, bounded memory-only raw-record provenance, a public serial-profile extension point, independent AFE and read-only MSP430 Equipment Health v1 profiles, a receive-only `SerialAdapter`, an optional packaged pyserial backend that leaves the formal core driver-free, and a Phase 4 machine-readable compatibility freeze.

The SimulatorAdapter models gain, offset, deterministic noise, saturation, Schmitt hysteresis, missing samples, communication faults, and CRC faults while retaining `SYNTHETIC` provenance. CsvReplayAdapter validates an explicit channel map, replays immutable records with independent channel cursors, supports immediate/scaled timing plus pause/resume/speed controls, exposes typed EOF, and forces current `CSV_REPLAY` provenance. The shared workflow now has both frozen finite-read and compatible finite streaming-read entry points. Separate DC and hysteresis runners own output-capable adapter preflight, ordered acquisition, safe cleanup, analysis, and TestRun mapping. Formal calibration, offline frequency-response analysis, versioned structured result exports, both serial business profiles, their receive-only adapter composition, and a narrow MSP430 UART HIL are implemented. Phase 5 adds immutable product request/result/event contracts, a reviewed source/profile catalog, stable user issues, a bounded single-owner cancellable worker, explicit adapter factories, shared services/workflow compilation, stable installed Simulator/Replay/receive-only CLI workflows, deterministic human reports that only present finalized results, a runnable six-step local Dashboard, a one-command reproducible synthetic demo with bounded performance/accessibility/privacy acceptance, and an executable product public-contract freeze. The current combined increment extends that same product path with calibration and frequency-response services, explicit criteria/TestRun mappings, strict coefficient persistence, presentation-only calibration/frequency charts, and a finite `live-monitor.v1` Simulator/Replay workflow with bounded curves, pause/resume, quality totals, and explicit eviction accounting. A validated physical AFE is not yet implemented.

The reviewed Software Phase 5 plan defines a separate `analog_validation_app` product layer, one `analog-validation` command, a bounded single-owner cancellable worker, deterministic HTML/SVG reporting, a local offline Tkinter/ttk Dashboard, a six-step beginner workflow, and an installed-package deterministic demo. All 8 checkpoints are implemented. The final checkpoint freezes product imports, schemas, CLI commands/options and exits, dataclass/function shapes, report/demo fields, worker states, errors/issues, and prior manifest hashes. The workflow defaults to Simulator/AFE, expresses status and criteria in text, prevalidates Replay, and gates Serial behind exact receive-only settings. Architecture tests enforce consumption of the frozen core without copying device/profile or engineering-analysis logic. Software Phase 6 Steps 1–7 now add the release contract, hosted compatibility CI, `0.1.0b1` metadata, a deterministic create-new candidate verifier, an executable beginner tester path, a public-API-only third-party-style read adapter proved from the installed wheel outside the repository, and a complete-history/privacy/license/workbook/claims audit with a four-file private-beta handoff contract.

Dashboard UX PR #7 delivered modern styling, Setup/Results tabs, adaptive
vertical scrolling and Windows mouse-wheel routing, revision-gated redraws,
explicit result actions, visible READ observations, clearer error/export
feedback, a native format-aware save picker, suffix validation, fresh
destinations, unsaved-result warnings, clearer count bounds, safer button
hierarchy, step-aware keyboard focus, a recruiter-first README, two classified
Simulator screenshots, repository governance, and a reusable interaction
design guide. Its final PR head `c9710fe` passed all eight hosted CI jobs in
Actions run `33933549983` attempt 1.

The local `codex/calibration-workflow` increment now connects the previously
host-tested calibration and amplitude-response cores to the shared product
compiler and worker. Calibration evaluates before/after errors and emits a
strict versioned coefficient artifact. Frequency response acquires explicit
Hz/input/output triples, evaluates an independently reviewed cutoff target and
minimum point count, retains all three references per point, and renders a
logarithmic-frequency gain chart. The bounded live monitor reuses the compatible
streaming-read API and the same reviewed worker for at most 10,000 observations;
its ring buffer, quality totals, pause/resume, display window, CLI, and Dashboard
remain presentation-only and never create an engineering PASS/FAIL. All three
workflows support Simulator/CSV Replay. All evidence is `SYNTHETIC`, `CSV_REPLAY`,
or `HOST_TEST`; no serial port, signal source, oscilloscope, or physical hardware
was accessed. The final local precommit gate passed 2,459 tests with
13,834/13,834 package statements covered, full Ruff/mypy/dependency checks,
15/15 bounded product-quality checks, two byte-identical isolated builds,
fresh base and `[serial]` installs, and installed Simulator/Replay monitor
chains. The live stress published 10,000 synthetic points in 0.177198 seconds
with 1.348 MiB peak traced memory, retained 2,048, and accounted for 7,952
evictions on this host; those timings are not real-time claims. The release
verifier clears inherited `PYTHONPATH` from every clean-install subprocess so an
outer checkout cannot make pip skip the candidate wheel. Following owner
approval, the 109-file increment was committed as `5dcc2d0`. Its formal
release-candidate verification passed; the release audit returned
`PASS_WITH_REVIEW` for eight historical privacy findings, with zero current
privacy findings and zero high-confidence credential findings. These are local
results, not hosted CI or publication approval.

The follow-up MIT integration is a separate, uncommitted working-tree change.
It replaces the previous license placeholder, adds SPDX package metadata, and
checks the license in source and distribution archives. Local regression passed
2,470 tests with 100% package statement coverage, Ruff, and mypy. A managed
Windows application-control policy initially blocked the pip-generated console
launcher under the system temporary directory (`WinError 4551`). The verifier
now creates fresh-install environments beside the caller-selected candidate
destination, still removes them automatically, and retains the real console
launcher gate. The complete base/serial-extra install, normal/Unicode demo, and
external-adapter chain then passed without serial discovery or hardware access.
This does not retroactively change the license findings in the preserved
`5dcc2d0` audit.

Before merge, GitHub's generated merge ref `70c5bf1` was checked in an
independent worktree. It passed 174 focused Dashboard/architecture tests, all
10 bounded product-quality checks, the 2,277-test and 11,911/11,911-statement
gate, Ruff, mypy, deterministic builds, fresh base and serial installations,
the formal release-candidate verifier, and a `PASS_WITH_REVIEW` release audit.
After owner approval, PR #7 was merged with merge commit `b4f0fef`; its tree
matches the independently verified merge tree and the remote feature branch
was retained. Post-merge Actions run `33934417152` reported one non-specific
release-candidate child-process failure on attempt 1. The same command on the
exact `main` commit passed locally with 2,277 tests and 100% package-statement
coverage; a failed-job-only rerun then completed all eight hosted jobs
successfully on attempt 2. All interaction checks remained Simulator/CSV-only
and did not touch a physical serial port.

Software Phase 3 is complete. Steps 1–7 add the versioned analysis foundation, formal DC and directional hysteresis math, criteria mapping, `analog_validation.runners`, immutable linear calibration, offline amplitude-response analysis, and `result-export.v1`. The current local calibration/frequency/live product extensions expand the public top-level/analysis/export namespaces to 92/84/38 symbols, 17 Phase 3 schemas, 10 enum sets, and 44 frozen public call shapes; the additive top-level names include the compatible streaming-read entry point rather than new engineering analysis. Exact representative DC/hysteresis results remain unchanged; all golden values remain HOST_TEST/SYNTHETIC software evidence.

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
| Calibration + frequency + bounded live-monitor increment full pytest suite | 2,459 passed in the final local precommit code/coverage gate |
| Combined increment package statement coverage | 100% of 13,834 statements |
| Combined increment static/dependency checks | Full Ruff PASS; mypy PASS across 218 source files; `pip check` PASS |
| Combined increment product-quality acceptance | 15/15 PASS; 10,000-record Replay 0.495200 s/13.102 MiB and 10,000-point live buffer 0.177198 s/1.348 MiB on this Windows/Python 3.12 host |
| Combined increment build/install | PASS — two byte-identical isolated builds; fresh base and `[serial]` installs; injected serial substitute only; inherited `PYTHONPATH` scrubbed |
| Installed frequency workflow | PASS — default 1000 Hz model/target returned PASS, 63 Measurements, 21 points, 3 references/point and five report artifacts; 2000/1000 Hz mismatch returned engineering FAIL/exit 1 at 1948.014806 Hz |
| Installed bounded live monitor | PASS — Simulator 15 total/3 retained/12 evicted; CSV Replay 3 total/3 retained/0 evicted; engineering outcome `none`; no port discovery |
| Merged `main` full pytest baseline | 2,277 passed before the unmerged calibration increment |
| Merged `main` package statement baseline | 100% of 11,911 statements |
| Dashboard UX PR #7 | MERGED — final head `c9710fe` passed eight jobs in run `33933549983`; merge commit `b4f0fef` passed eight post-merge jobs in run `33934417152` attempt 2 |
| Verified merge candidate and audit | PASS / `PASS_WITH_REVIEW` — tested merge ref `70c5bf1`; current-tree privacy findings 0; eight legacy-history review items retained for owner review |
| Interaction-safety delivery | PASS and merged — adaptive scrolling, native format-aware save selection, suffix validation, fresh result destinations, unsaved-result recovery, button hierarchy, and step focus; physical port discovery/open/write all 0 |
| Phase 6 hosted CI | PASS — Windows/Ubuntu with Python 3.10, 3.12, and 3.14; quality/build/base/serial jobs passed |
| Phase 6 beta metadata | PASS — import, CLI, wheel, public manifests, README, and changelog aligned at `0.1.0b1`; no license/tag/Release selected |
| Phase 6 deterministic candidate | PASS — local and hosted Windows/Python 3.12 outputs for commit `0c04aee` were byte-identical; manifest records only HOST_TEST/SYNTHETIC evidence and zero AFE bench claims |
| Phase 6 private-beta tester path | PASS — hosted commit `5dc10db` wheel hash/base install/version/two byte-identical demos/report/create-new/Replay checks passed in a new short repository-external Python 3.12 environment; Dashboard and Serial were explicitly NOT_RUN |
| Phase 6 public adapter proof | PASS — commit `2c01e7d` example imports only installed top-level public API; fresh base wheel + external `python -I` run completed three SYNTHETIC reads, cleanup, and zero writes; local/hosted candidates are byte-identical |
| Phase 6 final candidate audit | `PASS_WITH_REVIEW` — commit `f6721b5`; exact private binary beta `READY`; candidate/current tree/workbook/license/claims passed; 8 legacy history review items, 0 high-confidence credentials; local/hosted four-file bundle byte-identical; CI run `33451305940` passed |
| Phase 5 public compatibility | 4 namespaces, 15 schemas, 10 enum sets, 40 dataclasses, 40 signatures, 24 errors, 25 issue mappings, 24 CLI paths, 8 exits, 13 serialized groups, and 6 hashes frozen after the calibration/frequency/live extensions |
| Phase 5 Step 7 reproducible demo and product quality | 186 focused tests; two installed demos in normal/Unicode paths were byte-identical; 10,000-record Replay, 10,000-event bounded queue, privacy/offline, and real Tk scaling/focus smoke passed |
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
| Ruff | Rule check passed on the full repository; historical files retain formatting-only debt |
| mypy | Passed on `src`, `tools`, `tests`, and public adapter example — 204 files |
| Package build and external installs | Passed; two isolated builds were byte-identical after deterministic sdist metadata normalization; fresh base and `[serial]` installs passed, base remained headless/driver-free, normal/Unicode demos were byte-identical, and serial used only an injected substitute with zero real-port operations |
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
| 2 | Bounded single-owner cancellable worker | Complete | HOST_TEST / external base-wheel smoke |
| 3 | Stable test-running CLI workflows | Complete | HOST_TEST / SYNTHETIC / CSV_REPLAY / external base-wheel install |
| 4 | Evidence-visible human reports and deterministic charts | Complete | HOST_TEST / SYNTHETIC / external base-wheel install |
| 5 | Dashboard state, presenter, and desktop shell | Complete | HOST_TEST / external base-wheel install / real Windows Tk smoke |
| 6 | Beginner workflow and read-only serial wiring | Complete | HOST_TEST / SYNTHETIC / CSV_REPLAY / memory-serial zero-write / external base-wheel install |
| 7 | Reproducible demo and product-quality acceptance | Complete | HOST_TEST / SYNTHETIC / repository-external base-wheel install / real Windows Tk smoke |
| 8 | Public compatibility freeze and software Beta closure | Complete | HOST_TEST / SYNTHETIC / repository-external base and `[serial]` installs |

## Software Phase 6 checkpoints

Software Phase 6 remains at 7 of 8 checkpoints: Step 8 is deliberately
owner-gated because repository visibility, final licensing, tagging, and a
public Release require separate approval. The local calibration/frequency/live
increment does not change that publication decision.

| Step | Deliverable | Status | Evidence |
|---:|---|---|---|
| 1 | Release contract, version strategy, support scope, and stop conditions | Complete | HOST_TEST planning record |
| 2 | Read-only hosted CI and cross-version clean-install gates | Complete | HOST_TEST / hosted Windows and Ubuntu |
| 3 | `0.1.0b1` version, package metadata, changelog, and golden alignment | Complete | HOST_TEST / SYNTHETIC / isolated build |
| 4 | Deterministic build, clean install, and release manifest | Complete | HOST_TEST / SYNTHETIC / local + hosted clean installs |
| 5 | Installation, tester, troubleshooting, and feedback documentation | Complete | HOST_TEST / SYNTHETIC / CSV_REPLAY / hosted-wheel external install |
| 6 | Public-API-only external adapter proof | Complete | HOST_TEST / SYNTHETIC / external fresh-wheel isolated run |
| 7 | Privacy, license, history, claims, and candidate audit | Complete | HOST_TEST / complete-history audit / local + hosted four-file identity / owner-review items retained |
| 8 | Owner review, history/visibility/license/tag/Release, and v1.0 decision | Owner-gated | PR #7 merge complete; remaining publication decisions not authorized |

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
- implemented a bounded single-owner product worker with immutable monotonic events, cooperative cancellation, finite join/close, deterministic post-factory cleanup, and fail-closed result/issue handling under injected host-side races and faults.
- implemented installed Simulator and CSV Replay read/DC/hysteresis workflows that reuse formal analysis/criteria/export logic, expose stable JSON and exit codes, and preserve evidence limitations;
- implemented discovery-only ports and an exact bounded receive-only observe boundary with no application write surface; Step 3 serial proof used a memory backend, not a physical port.
- implemented bounded presentation-only `human-report.v1` views that copy finalized outcomes, evidence, schemas, metrics, criteria, limitations, record lineage, and not-verified statements without analysis logic;
- implemented deterministic plain text, Markdown, self-contained HTML, and SVG reports for DC/hysteresis plus atomic create-new publication and exact artifact hashes;
- installed the base wheel outside the repository and generated/parsed all five report artifacts without pyserial/Tk import, serial access, network access, or hardware operation.
- implemented immutable bounded `dashboard-state.v1`, owner-thread presentation, a headless polling/cancel/close controller, and rendering-only six-region widgets without duplicating profile or engineering logic;
- launched and safely auto-closed the local Windows Tk Dashboard with Simulator/AFE defaults, text-visible status, `NO_NEW_HARDWARE_VALIDATION`, and no pyserial import, serial access, file output, or network listener;
- redesigned the Dashboard with modern styled cards, Setup/Results tabs,
  visible scrolling, revision-gated redraws, explicit result actions, and
  presentation-only READ rows without changing the frozen Phase 5 contract;
- completed interactive Windows Simulator READ/DC/hysteresis and valid/invalid
  CSV Replay checks, including no-overwrite export and immediate rerun, without
  enumerating, opening, or writing a physical serial port;
- verified the Dashboard close path against an actual `ProductJobWorker`: cancellation reached `CANCELLED`, finite join completed, and cleanup ran before the window session returned.
- implemented the fixed six-step beginner workflow with what/why/confirm guidance, strict typed configuration, visible DC/hysteresis acceptance criteria, reviewed Run, cooperative Cancel, finalized results, and create-new JSON/CSV export;
- made CLI and Dashboard share `product-workflow-config.v1` compilation and verified equivalent finalized output for the same 24-point Simulator DC request;
- prevalidated Replay before worker start and exercised an MSP430-shaped memory-serial Dashboard run with one open, one close, and zero writes; the connected physical board was not accessed.
- implemented `analog-validation demo --output <new-directory>` through the same reviewed product workflow, worker, formal DC analysis/criteria, result export, and presentation-only reporting path;
- froze 12 exact demo artifacts, including replay/fault examples and a top-level SHA-256 manifest, and reproduced them byte-for-byte from a clean base-wheel install in normal and Unicode destinations;
- passed host-only 10,000-record Replay and 10,000-event bounded performance acceptance, real Windows Tk focus/scaling smoke, no-network trapping, privacy checks, and fail-closed path/output tests.
- froze the Phase 5 product imports, schema versions, enums, dataclasses, public signatures, CLI commands/options/exits, serialized fields, errors, issue mappings, stable constants, and earlier manifests in one executable compatibility contract;
- passed the final 2,189-test/100%-statement gate, isolated build, repository-external base and serial-extra installations, installed byte-identical demos, and installed real-Tk launch/close without operating a physical port.
- implemented a clean-commit release verifier with repeated isolated builds, deterministic sdist metadata, exact artifact hashes, base/serial clean installs, byte-identical normal/Unicode demos, privacy rejection, create-new atomic publication, and explicit zero-hardware evidence fields;
- reproduced the same wheel, sdist, and release manifest bytes locally and on the hosted Windows/Python 3.12 runner for commit `0c04aee` without physical port discovery or hardware operation.

Not safe to claim now:

- built or validated the physical analog front end;
- demonstrated ADC/DAC accuracy or long-duration UART reliability on hardware;
- verified any 0–3.3 V hardware range;
- identified the exact current MSP430 firmware image from passive telemetry;
- validated MSP430 external sensors, INA219, fan, or wiring;
- published a v1.0 release or demonstrated production readiness.

## Next checkpoint

Software Phase 6 Steps 1–7 are complete, and Dashboard UX PR #7 is delivered
to `main` at merge commit `b4f0fef` with a successful eight-job post-merge CI
run. The owner has since selected MIT, now implemented in the local working
tree. Phase 6 Step 8 remains owner-gated: licensing does not authorize a tag,
GitHub Release, package publication, public-history exposure, social preview,
beta-feedback disposition, or LinkedIn handoff. Simulator remains the default.
Real-port reliability and future physical AFE work stay separately gated and
are not inherited by the software release path.

## GitHub and LinkedIn presentation policy

- Update the repository README and this status page only after a checkpoint passes its real quality gates.
- Keep implemented, planned, and hardware-verified features visibly separate.
- Link every numerical claim to a report or reproducible test command.
- Present this as an independent personal product project; do not merge it with the OSU Lab Bench Monitor Capstone or the separate MSP430 equipment-health project.
- Prepare final LinkedIn wording only after the repository has a stable public demo and the owner has reviewed what will be public.
