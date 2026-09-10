# TD-046B batch Review summary acceptance

Status: **COMPLETE — local and uncommitted**<br>
Date: 2026-09-08<br>
Evidence: `HOST_TEST` with Simulator-produced `SYNTHETIC` results and bounded
`CSV_REPLAY` configuration fixtures. No serial port, MSP430, AFE, or laboratory
instrument was discovered, opened, or operated.

## Product outcome

The **Projects & history** page now makes the accepted batch Review inspectable
before Run:

- the exact project ID and run ID are visible;
- the full resolved create-new destination is visible;
- selected presets appear in their actual project execution order;
- Source and Test use the same readable names as the rest of the Dashboard;
- each row retains its exact `SYNTHETIC` or `CSV_REPLAY` evidence label; and
- Run consumes the Review and clears the frozen table before live progress and
  terminal history become authoritative.

The summary is derived from the existing accepted Review object. It does not
create another authorization or execution state machine.

## Contract and compatibility boundary

- Project, manifest v1/v2, comparison v1, result, evidence, and artifact schemas
  are unchanged.
- Existing manifest v1 files remain fully readable and are never rewritten.
- CLI output, exit codes, public API golden, batch execution, cancellation,
  cleanup, atomic publication, create-new refusal, hashes, and PASS/FAIL are
  unchanged.
- Rendering the Review does not read the Replay file. Existing Review/Run
  boundaries continue to control validation and resource use.
- `SYNTHETIC`, `CSV_REPLAY`, `HOST_TEST`, `SPICE_IDEAL`, `BENCH_CONTROLLER`, and
  `BENCH` remain distinct evidence classes.

## Test-first and failure record

The first targeted test run failed during collection because the requested
`_batch_review_text` presentation function did not exist. This froze the new
display contract before implementation.

After the summary model and widgets were added, one unit assertion failed
because the label used `Create-new` while the established project wording and
test expected lowercase `create-new`. The UI copy was aligned with the existing
term. No runtime, execution, manifest, or compatibility defect was found.

Tests cover absence before Review, exact preset order, identities, resolved
destination, readable labels, both software evidence classes, consumption after
Run, widget styling, and all five supported Windows Tk scaling values.

## Executed verification

| Gate | Result |
| --- | --- |
| Workspace/widget and five-scaling real-Tk focused tests | **24 passed in 10.41 s** |
| Changed Dashboard modules | **600/600 statements, 100%** |
| Full pytest suite | **2,696 passed in 50.87 s** |
| Full package statement coverage | **16,210/16,210, 100.00%** |
| Phase 5 public API golden + product quality | **17 passed in 1.60 s** |
| Standard/high-contrast accessibility smoke + project real-Tk matrix | **15 passed in 22.59 s** |
| Ruff | **PASS** |
| mypy | **PASS across 227 source files** |
| `pip check` | **PASS — no broken requirements** |
| `git diff --check` | **PASS** |

The real Tk project workflow ran in fresh Windows processes at scaling 1.0,
1.25, 1.5, 1.75, and 2.0. It asserted the exact two-preset frozen Review and its
clearing after Run. The new CSV Replay unit case uses a temporary path only to
freeze configuration/evidence text; it does not enumerate or open a serial port
or make a hardware claim.

## Files changed in TD-046B

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
than 1040-pixel layout, and localization remain unchanged.

No commit, push, PR mutation, tag, release, package publication, history rewrite,
reset, checkout, clean, or hardware action was performed.
