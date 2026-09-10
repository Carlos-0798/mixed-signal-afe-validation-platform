# Project Status

**Last updated:** 2026-09-09<br>
**Current milestone:** TD-050/TD-051/TD-052 locally complete; feature expansion paused for job-search preparation<br>
**Synchronization stage:** Owner-authorized private development-branch and existing Draft PR update; no new hosted CI or merge result claimed<br>
**Release maturity:** `0.1.0b1` local candidate; untagged and unreleased<br>
**Highest evidence level:** BENCH_CONTROLLER — MSP430 UART compatibility only<br>
**Verified AFE hardware performance claims:** 0

## Current execution priority

The 2026-09-08 feature freeze remains a historical baseline. The owner then
authorized themes/readability (TD-050), the runtime/UI review (TD-051), and a
focused expansion of file input compatibility (TD-052); all three are locally
complete. The current increment maps ordinary voltage tables into
the existing offline replay/analysis/report chain, with reusable templates and
preserved source bytes. Generic serial text and additional device protocols are
future work. See [the freeze policy](FEATURE_FREEZE.md),
[the voltage import guide](voltage-data-import.md), and
[the original consolidation report](../reports/feature-freeze-and-consolidation-2026-09-08.md).

The owner has now requested a documented pause and job-search preparation,
followed by committing and pushing the existing private development branch and
updating its existing Draft PR. This authorization does not include marking
the PR Ready, merging, tagging, publishing a Release, or changing visibility.
The [resume checkpoint](PROJECT_RESUME_CHECKPOINT_2026-09-09.md) records the
preserved state and follow-up route. TD-053 remains deferred until real source
samples justify a specific next input format or protocol.

The primary product task remains repeated DC gain/offset/linearity validation of
existing analog signal-chain datasets, from input preparation to reviewable reports.
Five frozen synthetic cases and an independent reference establish the current
software automation chain. Quantitative human benchmarking is optional future
evidence and no longer blocks product work.

Five frozen synthetic cases and an independent rational reference now agree
with the CLI, reports and project-history path; 258 targeted checks passed.
See [the TD-048 dry-run report](../reports/td-048-casepack-software-dry-run-2026-09-08.md).
The human baseline pilot remains NOT_RUN and is now DEFERRED; existing throughput,
coverage and machine timings are not measurements of manual time saved. TD-040C1A
now makes each executed offline CSV Replay project preset retain a verifiable
input copy, so later history review no longer depends on the original path still
existing. TD-051 subsequently introduced manifest v4 preparation-failure records;
strict v1/v2/v3 remain readable without rewriting. Dashboard history exposes retained inputs on single-row
selection without opening files or changing the two-row comparison flow. TD-047A display work
is not scheduled; the runtime migration remains deferred.
Phase 6 remains 7/8; external actions beyond the private synchronization scope
still need explicit owner authorization.

## Current product baseline

The repository currently provides an installable, controller-neutral Python core for Analog Validation Studio. It includes explicit measurement provenance, device capabilities and safe ranges, test-run conclusion semantics, one CRC implementation, a profile-neutral CRC envelope with a backward-compatible AFE wrapper, the versioned AFE v1 protocol, explicit AFE channel-name mapping, strict non-executable JSON configuration, frozen protocol and replay compatibility data, an executable dependency boundary, the public `DeviceAdapter` lifecycle/safety contract, a configurable deterministic read-only SimulatorAdapter, a strict immutable CSV Replay v1 parser, a read-only CsvReplayAdapter, a shared adapter-neutral read workflow, a profile-neutral bounded byte-stream/sequence foundation, a replaceable serial backend port, deterministic host-tested serial lifecycle, bounded memory-only raw-record provenance, a public serial-profile extension point, independent AFE and read-only MSP430 Equipment Health v1 profiles, a receive-only `SerialAdapter`, an optional packaged pyserial backend that leaves the formal core driver-free, and a Phase 4 machine-readable compatibility freeze.

The SimulatorAdapter models gain, offset, deterministic noise, saturation, Schmitt hysteresis, missing samples, communication faults, and CRC faults while retaining `SYNTHETIC` provenance. CsvReplayAdapter validates an explicit channel map, replays immutable records with independent channel cursors, supports immediate/scaled timing plus pause/resume/speed controls, exposes typed EOF, and forces current `CSV_REPLAY` provenance. The shared workflow now has both frozen finite-read and compatible finite streaming-read entry points. Separate DC and hysteresis runners own output-capable adapter preflight, ordered acquisition, safe cleanup, analysis, and TestRun mapping. Formal calibration, offline frequency-response analysis, versioned structured result exports, both serial business profiles, their receive-only adapter composition, and a narrow MSP430 UART HIL are implemented. Phase 5 adds immutable product request/result/event contracts, a reviewed source/profile catalog, stable user issues, a bounded single-owner cancellable worker, explicit adapter factories, shared services/workflow compilation, stable installed Simulator/Replay/receive-only CLI workflows, deterministic human reports that only present finalized results, a runnable six-step local Dashboard, a one-command reproducible synthetic demo with bounded performance/accessibility/privacy acceptance, and an executable product public-contract freeze. The current combined increment extends that same product path with calibration and frequency-response services, explicit criteria/TestRun mappings, strict coefficient persistence, presentation-only calibration/frequency charts, and a finite `live-monitor.v1` Simulator/Replay workflow with bounded curves, pause/resume, quality totals, and explicit eviction accounting. The previously validated Serial extension adds the same finite observation path to receive-only Serial with a primary-only safe default, explicit confirmation, a conservative 55-second combined runtime bound, and memory-backend failure/cleanup tests. It also adds optional exact capability-ID pinning and a versioned AFE native-ADC observation map that can expose a reviewed input/output pair only after full capability coverage. No physical serial port was opened, and a validated physical AFE is not yet implemented.

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
workflows support Simulator/CSV Replay; bounded live monitoring additionally has
a receive-only Serial path verified against memory backends. That path can
optionally compare the reported capability ID exactly and, for AFE v1, map every
advertised native ADC to a unique canonical input/output observation. Identity
or mapping failures stop before telemetry; the accepted identity is visible in
CLI JSON/human output and the Dashboard observation summary. All evidence is
`SYNTHETIC`, `CSV_REPLAY`, or `HOST_TEST`; no serial port, signal source,
oscilloscope, or physical hardware was accessed. The final local precommit gate
passed 2,459 tests with
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

The follow-up MIT integration is present in the current baseline as `bf8c4c6`.
It replaces the previous license placeholder, adds SPDX package metadata, and
checks the license in source and distribution archives. Its local regression
passed 2,470 tests with 100% package statement coverage, Ruff, and mypy. A managed
Windows application-control policy initially blocked the pip-generated console
launcher under the system temporary directory (`WinError 4551`). The verifier
now creates fresh-install environments beside the caller-selected candidate
destination, still removes them automatically, and retains the real console
launcher gate. The complete base/serial-extra install, normal/Unicode demo, and
external-adapter chain then passed without serial discovery or hardware access.
This does not retroactively change the license findings in the preserved
`5dcc2d0` audit.

The previously validated Serial live-monitor/device-contract extension exposes finite
receive-only monitoring through the same compiler, worker, CLI, and Dashboard.
It requires an exact profile, port, and primary channel; defaults to one trace;
requires explicit receive-only confirmation; and rejects a cadence plus worst-
case receive-wait budget above 55 seconds before Run. It can optionally pin the
reported capability ID and fully map AFE native ADCs to unique canonical
input/output observations. In-memory AFE and MSP430 chains cover success, bad
CRC, timeout/disconnect, cancellation, cleanup, unsupported capabilities,
identity/mapping failures, input/output dual trace, and zero application write
calls. That checkpoint's full gate passed 2,508 tests with 14,006/14,006 package
statements, Ruff, mypy, pip dependency consistency, 15/15 product-quality
checks, wheel/sdist build, and an isolated installed-CLI device-contract smoke.
No real port or hardware was accessed.

The subsequent project/history increment added a reusable test-management layer without copying
any analysis. Strict `validation-project.v1` files hold up to 32 immutable
Simulator/CSV Replay presets and refuse persisted Serial settings. An explicit
run executes all or selected presets sequentially through the existing reviewed
compiler/service/worker and atomically creates a new history directory. Each
directory includes the exact project snapshot and hash, per-preset canonical
configuration hash, copied terminal/outcome/evidence/metric facts, and strict
result/coefficient artifacts where applicable. History loads at most 64 explicit
manifest paths and verifies every referenced artifact; it never scans a drive.
Two-run comparison detects project/configuration/status/outcome/evidence/count/
metric changes without recalculating PASS/FAIL. The Dashboard now adds a
Projects & history tab for new/open/save-as projects, current-form preset capture,
reviewed background batches, explicit history loading, and tabular comparisons.
Single tests and batches are mutually exclusive. The core API, CLI, and
Dashboard now share per-preset progress, cooperative cancellation,
cleanup-before-stop behavior, and versioned partial history. The project page
shows real phase/current/total/completed state, disables its cancel action after
the first request, waits for cleanup and atomic manifest publication on close,
and refreshes terminal v2 history; v1 rows remain readable and are labeled
`LEGACY_V1` rather than assigned a new status. New v3 runs also retain each
executed Replay preset's bounded input copy, byte count, and hash; v1/v2 retain
their original shapes. Trace overlays remain deferred. SHA-256 supplies relative
integrity, not authenticated authorship.

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

The first row is the latest complete local acceptance. The remaining rows
retain evidence from earlier checkpoints; their test counts, audits, and
hosted runs are not fresh results for the current synchronization.

| Gate | Result |
|---|---|
| Private synchronization gate, 2026-09-09 | 3,048 tests passed, 17,567/17,567 statements covered, Ruff/mypy/dependency checks and 15/15 product-quality checks passed. One cross-platform regression was added; product runtime files are unchanged from TD-052. [Preparation report](../reports/private-github-sync-2026-09-09.md); current-head hosted CI remains separately visible on PR #10. |
| TD-052 latest local acceptance, including completed TD-050/TD-051 | 3,047 tests passed with no failures or skips; 17,567/17,567 package statements covered; Ruff, 252-file mypy, dependency checks, 15/15 product-quality checks, 23 installed CLI commands, installed GUI acceptance, and 100 runtime-file identity checks passed. Evidence: HOST_TEST with SYNTHETIC fixtures and CSV_REPLAY workflows; no new hardware or hosted-matrix claim. See [TD-052 report](../reports/td-052-voltage-import-2026-09-09.md). |
| TD-040C1B Dashboard input visibility | One selected v3 history row shows Replay preset/path/bytes/full SHA-256 and same-source reference/file counts; v1/v2, empty v3 and multiple-selection states explain the boundary without changing the eight-column history or comparison semantics; 25 project-page/real-Tk tests, five Windows scaling levels, 2,709 full tests and 16,356/16,356 statements passed; `HOST_TEST` with bounded `CSV_REPLAY` fixtures, no hardware validation |
| TD-040C1A Replay input archival | Manifest v3 archives the exact bounded input before each executed Replay preset and runs from that staging copy; same-source presets share one file, not-started presets remain unopened, and history verifies path/size/SHA-256 while v1/v2 remain exact-readable; 2,708 passed, 16,325/16,325 statements, Ruff, 218-file mypy, pip consistency and diff check passed; independent CLI JSON/stderr/source-mutation chain passed; `HOST_TEST/CSV_REPLAY`, no hardware validation |
| TD-046B batch Review decision summary | Before Run, Projects & history shows the exact frozen project/run identities, create-new destination, project-order presets, readable Source/Test labels, and per-preset `SYNTHETIC`/`CSV_REPLAY` evidence; the view clears when Run consumes Review and changes no execution/schema/API contract; 2,696 passed, 16,210/16,210 statements, API/quality 17/17, real Tk project five-scaling and standard/high-contrast matrices retained; `HOST_TEST`/`SYNTHETIC` with bounded `CSV_REPLAY` configuration fixtures |
| TD-046A project first-use and empty-state guidance | Projects & history derives the next action and Save/Add/Review/Run/Compare/Clear availability from the existing workspace state; current Setup preview preserves `SYNTHETIC`/`CSV_REPLAY` and rejects persisted Serial, while zero/one/multiple history states, unsaved changes and stale Review are explicit; 2,695 passed, 16,168/16,168 statements, API/quality 17/17, real Tk project five-scaling and standard/high-contrast matrices retained; `HOST_TEST`/`SYNTHETIC` only |
| TD-045B project history comparison guidance | Projects & history names baseline/candidate identity and batch states, snapshot drift, matched/one-sided/not-started coverage, exact evidence-label matches/mismatches, changed preset IDs, and arithmetic delta direction without assigning improvement/regression; 2,694 passed, 16,091/16,091 statements, API/quality 17/17, real Tk project five-scaling and standard/high-contrast matrices retained; `HOST_TEST`/`SYNTHETIC` only |
| TD-045A result decision hierarchy | Results separates product terminal status, engineering PASS/FAIL, exact evidence meaning, claim boundary, first unverified item, and safe next action; observation-only paths show `NO ENGINEERING DECISION`; 2,693 passed, 16,034/16,034 statements, API/quality 17/17, real Tk five-scaling standard/high-contrast matrix retained; `HOST_TEST` only |
| TD-044B source selection and Replay flow | Readable Source/Test aliases round-trip to stable enums; Replay/Serial controls are mutually exclusive; native Replay picker preserves Cancel and does not read before Review; 2,684 passed, 16,013/16,013 statements, API golden 15/15, real Tk 1040×760 standard/high-contrast five-scaling matrix 10/10; `HOST_TEST` only |
| TD-044A contextual novice guidance | Configure now exposes source boundaries and plain-language definitions for all six tests; action guidance follows the existing wizard state and explains next/blocked behavior; 2,670 passed, 15,964/15,964 statements, API golden 15/15, real Tk 1040×760 standard/high-contrast five-scaling matrix 10/10; private presentation helpers only, no schema/API/manifest change; `HOST_TEST` with `SYNTHETIC`/temporary `CSV_REPLAY` CLI acceptance |
| TD-043B2A2 accessible runtime decision | COMPLETE decision spike: local `_tkinter` ABI is 8.6; stable CPython Windows Tk 9.0.4 lacks `tk accessible`; Tk 9.1 beta rejected as the production candidate; isolated PySide6 Essentials 6.10.1 exposed six named/typed controls, three UIA-focusable actions/inputs and a changing status property; 74.5 MB wheel and ~206.3 MiB prototype footprint recorded; ADR-0004 remains Proposed with no production dependency/license change; `HOST_TEST` only |
| TD-043B2A assistive-technology capability gate | 2,655 passed; 15,805/15,805 statements; 15/15 public golden; Tk 8.6.15 lacks `tk accessible`; Windows UI Automation exposed 37 unnamed application panes and no named/focusable application control; runtime-gated Tk 9.1 metadata and deduplicated status-event adapter added; Dashboard screen-reader support remains blocked; `HOST_TEST` only |
| TD-043B1 narrow/high-contrast Dashboard | 2,648 passed; 15,819/15,819 statements; 100.00%; exact Phase 5 public golden 15/15; 1040×760 Windows Tk Setup/Results/Projects at scaling 1.0/1.25/1.5/1.75/2.0; standard and forced high-contrast style paths; `HOST_TEST` only |
| TD-043A field-level error navigation | 2,641 passed; 15,748/15,748 statements; 100.00%; exact Phase 5 public golden 15/15; Windows Tk scaling 1.0/1.25/1.5/1.75/2.0 verified error focus/highlight/reveal/clear; `HOST_TEST` only |
| Dashboard novice/product display evaluation | 2,627 passed; 15,639/15,639 statements; 100.00%; real Windows Tk scaling 1.0/1.25/1.5/1.75/2.0 with critical-action boundary checks; Ruff/mypy/pip/public-API/diff gates passed; `HOST_TEST` with `SYNTHETIC`/temporary `CSV_REPLAY` only |
| TD-040B full pytest and package statement coverage | 2,623 passed; 15,606/15,606 statements; 100.00%; `HOST_TEST` only |
| TD-040B focused Dashboard batch control | 19/19 workspace/widget/real-project-Tk tests passed; both changed Dashboard modules 419/419 statements |
| TD-040B real Windows Tk isolation | 6/6 accessibility and project workflows passed at scaling 1.0/1.5/2.0, each in a fresh process |
| TD-040B compatibility/static checks | Phase 5 public API golden unchanged and 15/15 passed; Ruff PASS; mypy PASS across 225 source files; `pip check` PASS; `git diff --check` PASS |
| TD-040A full pytest and package statement coverage | 2,620 passed; 15,555/15,555 statements; 100.00%; `HOST_TEST` only |
| TD-040A focused cancellation/cleanup/v1-v2 chain | 11/11 passed: pre-first, between-preset, running-worker and finish-boundary cancellation; cleanup error; CLI exits 130/5; strict v1 round trip |
| TD-040A real CLI Simulator chain | COMPLETE with 6 planned/completed records; progress isolated to stderr; stdout parsed as JSON; history load passed; existing output collision returned 5 and left manifest SHA-256 unchanged |
| TD-040A static/dependency checks | Ruff PASS; mypy PASS across 225 source files; `pip check` PASS; `git diff --check` PASS |
| Current local project/history Dashboard expansion full pytest suite | 2,591 passed in 34.59 s after keyboard/isolation fixes; no skipped tests; see `reports/dashboard-keyboard-isolation-acceptance-2026-09-06.md` |
| Current local project/history package statement coverage | 100% of 15,324 statements |
| Current local project/history focused and CLI chain | 63 focused tests plus 15 public-golden checks passed; editable create/inspect/all-six run/selected-two run/history/compare smoke passed with no Serial/device access |
| Current local project/history static/dependency checks | Full Ruff PASS; mypy PASS across 225 source files; `pip check` PASS |
| Current local project/history product-quality acceptance | 15/15 PASS; 10,000-record Replay 0.683011 s/13.102 MiB and 10,000-point live buffer 0.284917 s/1.355 MiB on this Windows/Python 3.12 host |
| Current local project/history build/install | PASS — wheel and sdist built; a fresh repository-external base-wheel install exposed the public project API and completed create/inspect/six-preset run/selected run/history/compare with `pip check` PASS |
| Receive-only Serial live-monitor/device-contract pre-project baseline | 2,508 passed in its local code/coverage gate |
| Receive-only Serial/device-contract package statement baseline | 100% of 14,006 statements |
| Receive-only Serial/device-contract static/dependency baseline | Full Ruff PASS; mypy PASS across 218 source files; `pip check` PASS |
| Receive-only Serial/device-contract product-quality baseline | 15/15 PASS; 10,000-record Replay 0.509990 s/13.102 MiB and 10,000-point live buffer 0.175368 s/1.338 MiB on this Windows/Python 3.12 host |
| Receive-only Serial/device-contract build/install baseline | PASS — wheel and sdist built; a repository-external base install exposed version `0.1.0b1`, public alias types, new Serial options, and invalid-alias fail-fast behavior; no port opened |
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
| Phase 6 beta metadata | PASS — import, CLI, wheel, public manifests, README, and changelog aligned at `0.1.0b1`; the later owner-selected MIT license does not create a tag or Release |
| Phase 6 deterministic candidate | PASS — local and hosted Windows/Python 3.12 outputs for commit `0c04aee` were byte-identical; manifest records only HOST_TEST/SYNTHETIC evidence and zero AFE bench claims |
| Phase 6 private-beta tester path | PASS — hosted commit `5dc10db` wheel hash/base install/version/two byte-identical demos/report/create-new/Replay checks passed in a new short repository-external Python 3.12 environment; Dashboard and Serial were explicitly NOT_RUN |
| Phase 6 public adapter proof | PASS — commit `2c01e7d` example imports only installed top-level public API; fresh base wheel + external `python -I` run completed three SYNTHETIC reads, cleanup, and zero writes; local/hosted candidates are byte-identical |
| Phase 6 final candidate audit | `PASS_WITH_REVIEW` — commit `f6721b5`; exact private binary beta `READY`; candidate/current tree/workbook/license/claims passed; 8 legacy history review items, 0 high-confidence credentials; local/hosted four-file bundle byte-identical; CI run `33451305940` passed |
| Current product public compatibility | 5 namespaces, 22 schemas, 10 enum sets, 49 dataclasses, 60 signatures, 29 errors, 30 issue mappings, 32 CLI paths, 8 exits, 22 serialized groups, and 6 hashes frozen after the local project/history extension |
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
- added optional exact capability-ID pinning plus `serial-channel-alias.v1` for
  complete, unique AFE native-ADC to canonical input/output observation
  mapping; mismatches stop before measurement telemetry and cannot add commands
  or channels.
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

Software Phase 6 Steps 1–7 are complete, and the current product-feature branch
baseline includes the owner-selected MIT license at `bf8c4c6`. Themes (TD-050),
runtime and workflow improvements (TD-051), and voltage-file import (TD-052)
are locally complete. Feature expansion is paused while the owner prepares
job-search materials and synchronizes the private branch and existing Draft PR.
See [the resume checkpoint](PROJECT_RESUME_CHECKPOINT_2026-09-09.md).

When development resumes, use real source samples and observed workflow
friction to select the next bounded TD-053 input extension. READ/LIVE output
persistence, one-click rerun, UI runtime migration, and physical validation
remain separate work; none is required to explain or demonstrate this software
checkpoint. Private branch/Draft PR synchronization is now authorized, while
Phase 6 Step 8 remains
owner-gated: licensing does not authorize a tag, GitHub Release, package
publication, public-history exposure, social preview, beta-feedback disposition,
or LinkedIn handoff. Simulator remains the default. Real-port reliability and
future physical AFE work stay separately gated and are not inherited by the
software release path.

## GitHub and LinkedIn presentation policy

- Update the repository README and this status page only after a checkpoint passes its real quality gates.
- Keep implemented, planned, and hardware-verified features visibly separate.
- Link every numerical claim to a report or reproducible test command.
- Present this as an independent personal product project; do not merge it with the OSU Lab Bench Monitor Capstone or the separate MSP430 equipment-health project.
- Prepare final LinkedIn wording only after the repository has a stable public demo and the owner has reviewed what will be public.
