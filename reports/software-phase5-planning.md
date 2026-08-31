# Software Phase 5 Planning Checkpoint

**Date:** 2026-08-31<br>
**Milestone:** file-level product workflow and presentation plan<br>
**Evidence class:** HOST_TEST<br>
**Hardware used:** none

## Outcome

The Software Phase 5 file-level implementation plan is complete and ready for
incremental execution. Implementation remains 0 of 8 checkpoints. This planning
change does not add a product CLI, owning worker, Dashboard, report generator,
demo, serial operation, or hardware behavior.

The plan converts the previously broad “CLI/Dashboard/reports” milestone into
eight bounded steps with named files, dependency direction, safety/privacy
rules, user-visible acceptance criteria, and a final compatibility gate. The
next implementation checkpoint is Step 1 only.

## Baseline audit

The audit found six important facts:

1. `src/analog_validation` already owns the engineering truth: versioned domain
   data, protocols, adapters, analysis, runners, TestRun conclusions, and
   structured exports;
2. `analog_validation_pyserial` is an optional receive-only OS backend with no
   public write method, while the core remains importable without pyserial;
3. `pyproject.toml` currently has no product console entry point;
4. the root `dashboard/` directory contains Phase 0 placeholders and weaker
   legacy analysis comparisons, not an installed product Dashboard;
5. no component currently owns a cancellable job, event queue, CLI/UI shared
   product request, human report, or end-to-end product demo;
6. the current Windows virtual environment imports Tk/Tcl 8.6, but no window was
   created or tested by this planning checkpoint.

These facts rule out building widgets directly over profiles or serial sessions.
The product layer must be added above the frozen core and must own resources
through a testable application service and worker boundary.

## Frozen planning decisions

- add a separate `src/analog_validation_app` product package;
- keep `analog_validation` free of GUI, pyserial, product-layer, and third-party
  runtime dependencies;
- use one installed `analog-validation` command, with Dashboard as a subcommand;
- share immutable product request/result/event models and application services
  between CLI and Dashboard;
- use a bounded single-owner worker with cooperative cancellation, bounded I/O,
  deterministic cleanup, and no PASS after cancellation or cleanup failure;
- default to Simulator, require explicit file mapping for Replay, and require
  explicit port/profile/bounds/read-only review for Serial;
- keep the packaged Simulator, Replay, and MSP430 paths read-only: the default
  demo collects deterministic synthetic input/output records through the read
  workflow and analyzes them offline; it does not pretend to execute stimulus,
  and output runners remain `UNSUPPORTED` without a future reviewed adapter;
- expose no arbitrary command, raw terminal, automatic COM selection, or write
  escape hatch in Phase 5;
- use local standard-library Tkinter/ttk for the first Dashboard and isolate Tk
  inside the widget boundary;
- generate self-contained local HTML and deterministic SVG rather than adding
  network resources or a PDF dependency;
- build report/presentation views from finalized results without recalculating
  metrics, thresholds, or outcomes;
- retire the superseded root Dashboard placeholders in Step 1 after keeping the
  formal Phase 3 compatibility tests green;
- close Phase 5 only after installed-package CLI/demo, worker race/fault,
  report, Dashboard-controller, build, and compatibility gates pass.

The complete file tree, state machine, CLI shape, safety policy, quality gates,
and step acceptance criteria are recorded in
`docs/SOFTWARE_PHASE_5_PLAN.md`.

## Planned checkpoints

| Step | Deliverable | Current status |
|---:|---|---|
| 1 | Product contracts, catalog, issue mapping, and CLI skeleton | Planned |
| 2 | Single-owner cancellable job worker | Planned |
| 3 | Stable Simulator/Replay/read-only Serial CLI workflows | Planned |
| 4 | Evidence-visible human reports and deterministic charts | Planned |
| 5 | Headless Dashboard state/presenter and Tk desktop shell | Planned |
| 6 | Beginner wizard, worker wiring, and bounded read-only serial entry | Planned |
| 7 | Installed deterministic demo plus performance/privacy/accessibility acceptance | Planned |
| 8 | Public compatibility freeze, build/install gates, and closure | Planned |

## Requirements and debt alignment

The plan directly covers `SW-FR-040` through `SW-FR-046` and the Phase 5 parts
of `SW-NFR-001`, `003`, `006`–`011`. It does not change their implementation or
verification status. Planning details were linked into the traceability matrix
without claiming that accepted requirements are implemented.

Open technical debt remains open:

- TD-009: human-readable reports and complete analysis-type mappings;
- TD-014: unified product CLI;
- TD-025: owning/cancellable worker and later physical disconnect evidence;
- TD-033: Phase 0 Dashboard placeholders and legacy-only tests.

CI and release-candidate work remain TD-013 / Software Phase 6 rather than being
silently absorbed into this phase.

## Executed baseline verification

| Gate | Final result |
|---|---|
| Full pytest suite | PASS — 1,526 tests |
| Formal + optional package coverage | PASS — 7,325/7,325 statements, 100% |
| Full-repository Ruff | PASS |
| mypy on `src`, `dashboard`, `tools`, and `tests` | PASS — 148 files |
| Dependency consistency | PASS — no broken requirements |
| Tk dependency feasibility | PASS — Tk/Tcl 8.6 import only; no window created |
| Document relative-link check | PASS after this report was created |
| Patch whitespace check | PASS |
| Hardware or physical serial validation | NOT RUN |

An intermediate relative-link check correctly identified the newly added
README link before this report file existed. The final check was rerun after the
report was created; no missing relative link remained. This was documentation
construction order, not a product test failure.

The software gates prove only that the completed Phase 4 implementation remains
healthy after the planning/documentation change. They do not prove that any
planned Phase 5 feature exists. Wheel/build/external-install evidence remains
the Phase 4 closure evidence and was not relabeled as a Phase 5 product result.

## Evidence and safety boundary

No serial port, controller, AFE, ADC, DAC, PWM, sensor, fan, external supply,
instrument, or wiring was accessed. Tk import is environment feasibility only
and does not prove that a Dashboard window, accessibility behavior, cancellation,
or user workflow works.

The earlier five-record MSP430 result remains a separate narrow
`BENCH_CONTROLLER` UART/profile compatibility result. It does not become Phase 5
evidence and does not validate exact firmware, external peripherals, physical
reconnect, long-duration timing, or any AFE performance. Verified AFE hardware
performance claims remain zero.

The Analog Validation Studio and MSP430 Equipment Health Controller remain
independent peer products with separate repositories, versions, evidence, and
release paths. Phase 5 consumes the public read-only profile; it does not copy
or absorb the controller project.

## Next checkpoint

After owner continuation, Software Phase 5 Step 1 will add only the
`analog_validation_app` package foundation, product request/result/catalog and
user-issue contracts, the installed CLI skeleton, and architecture tests. It
will retire the superseded Phase 0 Dashboard placeholders after confirming the
formal analysis/golden baseline remains intact.

Step 1 will not implement the worker, report generator, Dashboard window,
beginner wizard, physical serial observation, output control, or hardware
validation.
