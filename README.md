# Analog Validation Studio

> Controller-neutral software for repeatable analog front-end validation, automated test execution, and evidence-aware reporting.

[![CI](https://github.com/Carlos-0798/mixed-signal-afe-validation-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/Carlos-0798/mixed-signal-afe-validation-platform/actions/workflows/ci.yml)

**Private beta · Python 3.10+ · offline by default · hardware work deferred**

Analog Validation Studio is the software product inside the broader
**Configurable Analog Front-End & Validation Platform** project. It turns
Simulator, CSV Replay, and explicitly selected receive-only serial data into
reviewed acquisition jobs, engineering analyses, and traceable reports. The
design keeps device profiles replaceable so the product is not tied to one
microcontroller or laboratory.

This is an independent personal engineering project. Compatibility profiles
allow peer products to exchange evidence without merging their ownership,
runtime, or product identity.

The current engineering focus is repeated DC gain/offset/linearity validation
of existing measurement files: reuse criteria, check data quality, and hand off
reviewable results. Five controlled software cases and an independent reference
exercise that chain; quantitative human time savings and reduced operator-error
rates have not been measured. The human comparison in the
[task-value evaluation](docs/TASK_VALUE_VALIDATION_PLAN.md) is deferred and does
not block the current feature-frozen software product.

> **Evidence boundary:** the screenshots and demo below use deterministic
> `SYNTHETIC` data. No configurable AFE has been built or bench-validated, so
> this repository makes zero AFE hardware-performance claims. A prior
> `BENCH_CONTROLLER` record validates only a narrow, receive-only MSP430 UART
> compatibility path; it does not validate the future AFE, sensors, wiring, or
> instruments.

## Product at a glance

| Area | Current state |
|---|---|
| Product version | `mixed-signal-afe-validation-platform 0.1.0b1` |
| Delivery stage | Feature-frozen `0.1.0b1` local candidate; Software Phase 6 release engineering — 7/8 checkpoints |
| Interfaces | Installed CLI, local Tk Dashboard, JSON/CSV exports, text/Markdown/HTML/SVG reports |
| Data sources | Deterministic Simulator, strict CSV Replay, receive-only serial profiles |
| Workflows | Bounded read/live monitoring plus DC gain/offset/linearity, directional hysteresis, linear calibration, and amplitude-frequency response |
| Test management | Versioned local projects/presets, bounded offline batches, immutable run manifests with retained Replay inputs, verified history, and run comparison |
| Extension model | Public `DeviceAdapter` and serial-profile contracts |
| Latest local freeze gate | 2,709 tests and 16,356/16,356 statements; external snapshot build, fresh wheel install, byte-identical demos, installed Replay history, and 15/15 product-quality checks passed |
| Latest merged delivery | Dashboard UX PR #7 merged to `main`; post-merge CI passed all eight jobs |
| Hardware claim | `NO_NEW_HARDWARE_VALIDATION` — physical AFE not built or measured |

[Detailed status](docs/PROJECT_STATUS.md) ·
[Feature-freeze acceptance](reports/feature-freeze-and-consolidation-2026-09-08.md) ·
[Replay input visibility](reports/td-040c1b-dashboard-input-visibility-2026-09-08.md) ·
[Batch review summary](reports/td-046b-batch-review-summary-2026-09-08.md) ·
[Result decision hierarchy](reports/td-045a-result-decision-hierarchy-2026-09-08.md) ·
[Source selection and Replay flow](reports/td-044b-source-selection-replay-flow-2026-09-08.md) ·
[Contextual novice guidance](reports/td-044a-contextual-novice-guidance-2026-09-08.md) ·
[Accessible runtime decision](reports/td-043b2a2-runtime-decision-2026-09-07.md) ·
[Assistive-technology readiness](reports/td-043b2a-assistive-technology-readiness-2026-09-07.md) ·
[Combined precommit review](reports/calibration-frequency-live-precommit-review-2026-09-06.md) ·
[Current milestone handoff](reports/PROJECT_MILESTONE_UPDATE_2026-09-04.md) ·
[Serial device-contract verification](reports/serial-device-contract-readiness-2026-09-06.md) ·
[Live-monitor verification](reports/live-monitor-product-workflow-2026-09-05.md) ·
[Installation](docs/INSTALLATION.md) ·
[Tester guide](docs/USER_TESTING_GUIDE.md) ·
[Changelog](CHANGELOG.md)

## Product preview

![Analog Validation Studio showing a completed synthetic DC analysis](media/dashboard-dc-result.png)

The local Dashboard makes the six-step Source → Test → Configure → Review →
Run → Result workflow visible. It does not open a file, port, or output merely
because a source is selected.

![Analog Validation Studio showing the synthetic evidence boundary and no-hardware-validation claim](media/dashboard-dc-evidence.png)

The result view separates product completion from engineering outcome and
shows provenance, excluded points, limitations, and the explicit hardware
claim. Both images were captured from the current Windows application using
the Simulator; see the [media evidence register](media/README.md).

## Why this project exists

Analog validation often becomes a collection of one-off scripts, board-specific
commands, manually edited spreadsheets, and ambiguous screenshots. This project
builds a reusable product boundary around that work:

- **Repeatability:** immutable requests, deterministic Simulator data, strict
  replay files, fixed CRC vectors, and versioned schemas.
- **Safety:** review-before-run, capability and range preflight, bounded jobs,
  cooperative cancellation, cleanup-before-conclusion, and receive-only serial
  product paths.
- **Evidence integrity:** `SYNTHETIC`, `CSV_REPLAY`, `HOST_TEST`,
  `BENCH_CONTROLLER`, and future bench evidence remain distinguishable.
- **Extensibility:** adapters and profiles isolate controllers, instruments,
  transports, and future hardware from analysis and presentation code.
- **Auditability:** reports preserve criteria, metrics, point disposition,
  lineage, limitations, versions, and SHA-256 identities without recalculating
  a finalized conclusion.

## What is implemented

| Product layer | Implemented capability |
|---|---|
| Domain and protocol | Immutable measurements/capabilities/test runs; bounded ASCII framing; CRC-16/CCITT-FALSE; AFE v1 and MSP430 Equipment Health v1 receive-only parsing |
| Sources and adapters | Deterministic Simulator, immutable CSV Replay, bounded serial lifecycle, public adapter/profile contracts |
| Test execution | Shared finite read and streaming-read workflows; safety-gated DC and hysteresis runners; bounded single-owner worker |
| Analysis | Unit normalization, saturation/quality exclusion, OLS gain/offset/R²/RMSE, hysteresis thresholds/width, calibration, offline frequency response |
| Product surfaces | Installed `analog-validation` CLI, guided Dashboard with Projects & history, reviewed background batches, bounded live curves, calibration-coefficient manager, deterministic demo, structured exports, human-readable reports |
| Release engineering | Hosted matrix CI, compatibility manifests, reproducible wheel/sdist checks, isolated base/serial installs, privacy and evidence audits |

Full feature-level evidence is maintained in
[Project Status](docs/PROJECT_STATUS.md) and
[Requirements Traceability](docs/REQUIREMENTS_TRACEABILITY.md). The
[feature-freeze policy](docs/FEATURE_FREEZE.md) describes the current frozen
scope, deferred work, and local acceptance boundary. The freeze changes no
release, visibility, license, or hardware status.

Not yet complete: real-device/long-duration live acquisition, phase-response
analysis, instrument-controlled physical sweeps, a validated configurable AFE,
reference-controller output hardware, and v1.0 publication. The implemented
live view is a finite Simulator/CSV Replay workflow, not a hard-real-time or
physical-device claim.

## 60-second software demo

Requirements: Python 3.10 or later. The primary verified development
environment uses Python 3.12.

~~~powershell
git clone https://github.com/Carlos-0798/mixed-signal-afe-validation-platform.git
cd mixed-signal-afe-validation-platform
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\analog-validation.exe demo --output .\work\portfolio-demo
.\.venv\Scripts\analog-validation.exe dashboard
~~~

The demo executes the reviewed 24-point synthetic DC product chain and creates
12 deterministic machine, replay, report, chart, and manifest artifacts in a
new directory. It requires no serial driver, physical device, network service,
or laboratory instrument.

For development:

~~~powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe src tools tests examples
~~~

Optional serial support is isolated behind `.[serial]` and remains receive-only
at the product boundary. Read [pyserial and physical-port safety](docs/pyserial-backend.md)
before selecting a real port.

## Reusable offline test projects

A project turns reviewed one-off commands into a reusable six-preset test suite
and keeps each execution in a new, verifiable run directory:

~~~powershell
.\.venv\Scripts\analog-validation.exe project create `
  --output .\work\afe-project.json `
  --project-id afe-demo `
  --name "AFE Demo Project"
.\.venv\Scripts\analog-validation.exe project run `
  --input .\work\afe-project.json `
  --output .\work\run-001 `
  --run-id run-001
~~~

The run records an exact project snapshot, each executed preset's configuration
SHA-256, finalized outcomes/metrics, evidence class, and result artifact hashes.
History and comparison commands verify those files before presenting them and
never recalculate PASS/FAIL. The Dashboard comparison guide also distinguishes
matched, one-sided, and not-started results and warns when evidence labels differ;
the sign of `candidate - baseline` does not classify improvement or regression.
Saved projects deliberately exclude Serial
settings; selecting a real port always requires a fresh explicit review. See
the [test-project and history guide](docs/test-projects-and-history.md).

## Architecture

~~~mermaid
flowchart LR
    Sources["Simulator · CSV Replay · receive-only Serial · future instruments"]
    Adapters["Public adapters and versioned profiles"]
    Core["Measurements · capabilities · reviewed requests"]
    Execution["Worker · workflows · safety-gated runners"]
    Analysis["DC · hysteresis · calibration · frequency response"]
    Evidence["JSON/CSV · text/MD/HTML/SVG · Dashboard"]

    Sources --> Adapters --> Core --> Execution --> Analysis --> Evidence
    AFE["Future configurable AFE"] -. electrical/protocol contract .-> Sources
    MSP["Independent MSP430 product"] -. public compatibility profile .-> Adapters
~~~

The analysis layer never depends on a COM name, board register, SDK call, or
pin map. The Dashboard presents finalized data and does not own CRC, fitting,
saturation exclusion, threshold calculation, or PASS/FAIL logic.

[Architecture](docs/PRODUCT_ARCHITECTURE.md) ·
[Architecture decisions](docs/adr/README.md) ·
[Public adapter example](docs/PUBLIC_ADAPTER_EXAMPLE.md) ·
[Phase 5 public contract](docs/phase5-public-api.md)

## Source and compatibility matrix

| Source/profile | Product operation | Evidence | Current boundary |
|---|---|---|---|
| Simulator / `afe/1` | Read, bounded live monitor, synthetic DC, hysteresis, calibration, frequency response | `SYNTHETIC` | Default, deterministic, no hardware |
| CSV Replay | Read, bounded live monitor, DC, hysteresis, calibration, frequency response | `CSV_REPLAY` | Strict local file; historical source is not promoted |
| AFE v1 serial | Bounded receive-only read/live observation | Depends on declared capture | Default input projection plus optional exact-ID/full-ADC input-output mapping; memory-tested only; future physical AFE not validated |
| MSP430 Equipment Health v1 | Bounded receive-only read/live observation | `HOST_TEST` or narrow `BENCH_CONTROLLER` capture | Independent peer product; no command encoder or write surface |
| Third-party adapter | Shared public read workflow | Adapter-declared and checked | Demonstrated from an installed wheel using only public API |
| Future instruments/controllers | Planned adapter/profile | Future explicit bench class | Requires safety review and separate evidence |

The MSP430 Equipment Health Controller and this project are independent
products. They are not intended to merge, and neither is part of the
OSU Lab Bench Monitor Senior Capstone.

## Verification and claim discipline

| Gate | Verified result |
|---|---|
| Local calibration + frequency-response + bounded live/device-contract + project/history Dashboard increment | TD-046B passes 2,696 tests and 100% statement coverage across 16,210 package statements; full Ruff, mypy, dependency, public-API golden, diff, and real Windows Tk 1040×760 standard/high-contrast five-scaling checks pass; formal commit-bound candidate/audit and hosted CI have not run for this uncommitted extension |
| Merged `main` software baseline | 2,277 tests passed; 11,911/11,911 package statements covered; Ruff and mypy passed |
| Hosted Dashboard gate | PR head `c9710fe` passed eight jobs in run `33933549983`; merged `main` commit `b4f0fef` passed eight post-merge jobs in run `33934417152` attempt 2 |
| Reproducible candidate baseline | Local/hosted four-file `0.1.0b1` candidate matched byte-for-byte at audited commit `f6721b5` |
| Release audit | `PASS_WITH_REVIEW`; zero current-tree privacy findings, eight legacy-history review items, zero high-confidence credentials |
| Dashboard validation | Simulator/CSV interaction, data entry, adaptive scrolling, fresh save paths, navigation, single-job and project-batch cooperative cancellation, cleanup-before-close, history refresh, first-paint, and keyboard/scaling checks |
| Physical controller evidence | One prior five-frame receive-only MSP430 UART capture with zero application writes; exact firmware and peripherals unverified |
| AFE hardware bench tests | Not run |

These rows do not imply 100% branch coverage, production readiness, electrical
safety certification, or validated AFE performance. Historical checkpoint
reports retain the exact counts and evidence available when they were written.

[Executed reports](reports/README.md) ·
[Step 7 release audit](reports/software-phase6-step7.md) ·
[Windows Dashboard QA](reports/dashboard-ux-windows-qa-2026-09-02.md) ·
[Known limitations](docs/KNOWN_LIMITATIONS.md)

## Roadmap

| Stage | Status | Exit condition |
|---|---|---|
| Software Phases 0–5 | Complete | Core, adapters, analyses, CLI/Dashboard/reports/demo, compatibility freeze |
| Post-beta product workflows | In local validation | Calibration, amplitude response, bounded live monitoring, and local project/history automation share the reviewed product path |
| Software Phase 6 | 7/8 | Dashboard UX delivered; owner-controlled history, license, visibility, tag, and release decisions remain |
| Hardware design preparation | Deferred | Confirmed requirements, tools, instruments, components, safety review |
| Breadboard AFE | Not started | Power/protection/buffer/gain/filter/Schmitt tests with raw bench evidence |
| Automated hardware validation | Not started | Replaceable reference controller/instrument adapters and repeatable datasets |
| PCB/productization | Not started | Bench-stable design, schematic/PCB reviews, bring-up and reliability evidence |

No hardware purchasing or construction is required to evaluate the current
software product.

## Repository map

~~~text
src/analog_validation/      controller-neutral domain, protocol, adapters, analysis
src/analog_validation_app/  product services, CLI, Dashboard, reports, worker
tests/                      unit, golden, integration, architecture, product gates
test-data/golden/           frozen compatibility vectors and exact results
examples/public_adapter/    external public-API-only extension example
docs/                       product, protocol, safety, user, and architecture guides
reports/                    executed checkpoints with evidence limitations
simulation/                 LTspice tasks and ideal-model evidence
hardware/                   deferred design and procurement planning
media/                      classified software visuals; future bench media is separate
~~~

## Documentation

- Start here: [Installation](docs/INSTALLATION.md),
  [CLI](docs/product-cli.md), [Dashboard](docs/dashboard.md),
  [test projects and history](docs/test-projects-and-history.md),
  [interaction design guide](docs/SOFTWARE_INTERACTION_DESIGN_GUIDE.md),
  [software demo](docs/software-demo.md), and
  [beginner testing](docs/USER_TESTING_GUIDE.md).
- Engineering: [Theory](docs/theory.md),
  [protocol](docs/protocol.md), [CRC/framing](docs/framing-and-crc.md),
  [DC analysis](docs/dc-sweep-analysis.md),
  [hysteresis](docs/hysteresis-analysis-and-runner.md),
  [bounded live monitoring](docs/live-monitoring.md), and
  [result exports](docs/result-exports.md).
- Product governance: [Project status](docs/PROJECT_STATUS.md),
  [product plan](docs/PRODUCT_PLAN.md),
  [requirements traceability](docs/REQUIREMENTS_TRACEABILITY.md),
  [security policy](SECURITY.md), [contributing](CONTRIBUTING.md), and
  [publication checklist](docs/PUBLICATION_CHECKLIST.md).
- Portfolio handoff: [GitHub and LinkedIn copy preview](docs/PORTFOLIO_COPY.md)
  with an explicit claims gate and owner-approval sequence.

## Safety, privacy, and publication

- The default product path is offline and Simulator-first.
- Serial is opt-in, explicitly configured, and receive-only at the application
  boundary; operating-system drivers may still affect control lines.
- Existing result files are never overwritten by default.
- Reports, screenshots, and release manifests must retain provenance and
  limitation labels.
- Publication requires a separate owner decision for repository visibility,
  Git-history review, release/tag, social preview, and LinkedIn copy.
  The owner-selected MIT license is implemented; future license changes remain
  owner-controlled.

See [Security](SECURITY.md), [publication checklist](docs/PUBLICATION_CHECKLIST.md),
[assumptions](ASSUMPTIONS.md), [test/evidence policy](docs/test-plan.md), and
[risk register](docs/risk-register.md).

## License

Licensed under the [MIT License](LICENSE), selected by the project owner.
See [Third-Party Notices](THIRD_PARTY_NOTICES.md) for separately licensed
dependencies. Repository visibility and publishing a Release remain separate
owner-controlled actions.
