# TD-046A project first-use guidance acceptance

Status: **COMPLETE — local and uncommitted**<br>
Date: 2026-09-08<br>
Evidence: `HOST_TEST` with Simulator-produced `SYNTHETIC` results and bounded
test fixtures. No serial port, MSP430, AFE, or laboratory instrument was
discovered, opened, or operated.

## Product outcome

The **Projects & history** page now presents one continuous first-use path:

- before a project exists, the guide explains Create starter versus Open;
- the current Setup preview names the readable source and test, states that
  preset capture does not run anything, and preserves `SYNTHETIC` or
  `CSV_REPLAY` evidence meaning;
- a Serial Setup states that it cannot be persisted and that no port is
  discovered or opened by the project page;
- unsaved project changes require Save as before Review or switching projects;
- Review freezes the visible preset order, run ID, and destination; changing any
  of them makes Run unavailable and asks for Review again;
- zero, one, and multiple history runs receive different instructions; and
- Save, Add preset, Review, Run, Compare, and Clear follow the existing
  workspace permissions instead of accepting clicks that can only fail.

The page polls these presentation facts through the existing Tk owner-thread
render loop. It does not create a second project state machine.

## Contract and compatibility boundary

- Project, manifest v1/v2, comparison v1, result, evidence, and artifact schemas
  are unchanged.
- The CLI, public API golden, serialized fields, exit codes, batch cancellation,
  progress, create-new publication, hashes, and PASS/FAIL behavior are unchanged.
- `reviewed_batch_matches()` centralizes the same exact project/selection/path/
  run-ID equality that `run()` already enforced; the UI consumes that predicate.
- Existing history files remain read-only and are never scanned automatically.
- `SYNTHETIC`, `CSV_REPLAY`, `HOST_TEST`, `SPICE_IDEAL`, `BENCH_CONTROLLER`, and
  `BENCH` remain distinct evidence boundaries.

## Test-first and failure record

The first targeted run failed during collection because the new guidance
functions did not exist. After implementation, one test failed because four
pre-existing history round-trip assertions had been inserted under the new test
and lost access to their local `paths` variable; they were restored to the
original test.

The first real Windows Tk run then failed at all five scaling values. ProjectPage
is constructed before the main Setup form receives its first rendered enum
values, so the initial Setup snapshot correctly rejected an empty operation.
The project page now treats this narrow `ProductRequestError` as a temporary
preview-unavailable state, disables preset capture, and recovers on the next
valid owner-thread render. It does not hide Review, Run, or worker errors.

Tests also cover an invalid output path, incomplete Setup preview, stale Review,
unsaved project, Simulator/Replay/Serial preview text, empty/one/multiple history,
all action availability states, cooperative cancellation, keyboard selection,
and cleanup-before-close.

## Executed verification

| Gate | Result |
| --- | --- |
| Workspace/widget and five-scaling real-Tk focused tests | **23 passed in 9.57 s** |
| Changed Dashboard modules | **558/558 statements, 100%** |
| Full pytest suite | **2,695 passed in 53.37 s** |
| Full package statement coverage | **16,168/16,168, 100.00%** |
| Phase 5 public API golden + product quality | **17 passed in 1.82 s** |
| Standard/high-contrast accessibility smoke + project real-Tk matrix | **15 passed in 25.70 s** |
| Ruff | **PASS** |
| mypy | **PASS across 227 source files** |
| `pip check` | **PASS — no broken requirements** |
| `git diff --check` | **PASS** |

The real Tk project workflow ran in fresh Windows processes at scaling 1.0,
1.25, 1.5, 1.75, and 2.0. It directly asserted the initial action locks,
`SYNTHETIC` Setup preview, Review and Run transitions, post-run relock, one-run
history instruction, two-run Compare availability, keyboard range selection,
visible controls at 1040×760, cancellation, and cleanup-before-close.

## Files changed in TD-046A

- `src/analog_validation_app/dashboard/project_workspace.py`
- `src/analog_validation_app/dashboard/project_widgets.py`
- `tests/unit/test_dashboard_projects.py`
- `tests/integration/test_dashboard_project_workflow.py`
- `CHANGELOG.md`
- `README.md`
- `docs/PROJECT_STATUS.md`
- `docs/TECHNICAL_DEBT.md`
- `docs/UX_DESIGN_AUDIT.md`
- `docs/dashboard.md`
- `docs/test-projects-and-history.md`
- `reports/README.md`
- this report

## Remaining boundaries

TD-040C remains open for raw READ/LIVE observation persistence, trace overlay,
and a separately designed trust/signature model. The Tk 8.6.15 screen-reader
limitation, Proposed ADR-0004 runtime decision, real-user novice study, smaller
than 1040-pixel layout, and localization remain unchanged. None was mixed into
this phase.

No commit, push, PR mutation, tag, release, package publication, history rewrite,
reset, checkout, clean, or hardware action was performed.
