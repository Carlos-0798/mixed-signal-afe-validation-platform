# Dashboard Projects and History — Local Acceptance, 2026-09-06

## Decision and scope

The existing offline project API/CLI now has a working `Projects & history`
Dashboard page. This is a local, uncommitted feature increment on
`codex/calibration-workflow`, based on `bf8c4c6`; it is not a release approval.
No hardware, serial ports, GitHub mutations, commits, pushes, or releases were
performed for this increment. Prior checkpoint reports remain historical.

## Delivered

- Create/open/save-as versioned local projects using native file dialogs.
- Capture the current Setup configuration as a new named preset; offline
  validation rejects saved Serial permissions and resolves replay paths.
- Select presets, explicitly review exact inputs, then run the bounded
  sequential batch on a background thread. The UI receives completion via
  a bounded mailbox; the worker does not call Tk.
- Prevent simultaneous single-test and project-batch resource ownership.
- Invalidate stale reviews after edits; require dirty projects to be saved
  before running; never overwrite existing projects or run directories.
- Load explicit run manifests, recheck artifact integrity, display history,
  and compare two same-project runs without recalculating engineering verdicts.
- Defer normal window closure until the active batch finishes; confirm before
  discarding unsaved project changes. Clearing history only clears the view.

## Verified evidence

| Gate | Result |
|---|---|
| Full pytest regression | 2,590 passed, no skips, 31.62 seconds |
| Package statement coverage | 15,287/15,287, 100% |
| Ruff | PASS |
| mypy, configured CI target paths | PASS, 225 files |
| Dependency consistency | PASS |
| Product quality acceptance | 15/15 PASS |
| Windows Tk actual-control chain | PASS at scaling 1.0, 1.5, 2.0 |
| Wheel and sdist build | PASS |
| Fresh external base-wheel install | PASS, dependency check and real CLI launcher |
| Installed isolated Dashboard | Hidden launch and safe close PASS |
| Installed project CLI | create, inspect, six-preset run, selected-two run, history, compare PASS |
| Formal commit-bound candidate/audit; hosted CI | NOT RUN for this dirty increment |

The actual-control tests create projects, run batches, load generated history,
compare, check keyboard-focus availability, and close using the window protocol.
Windows are withdrawn: this is automated Tk integration evidence, not a new
human acceptance of visual appearance or perceived smoothness.

An intermediate full run exposed Tcl cleanup on a non-UI thread when cyclic
collection finalized destroyed test windows during subsequent worker tests.
The real-Tk test now controls cyclic collection and finalizes on its UI thread.
After that isolation correction, the complete suite passed without skips.
An exploratory `mypy .` also included generated `build/lib` copies and was not
the valid gate; the CI's explicit source/test/tool/example targets passed.

Build/install evidence was generated in new task-specific directories under
`C:\avs-dev`, outside the repository. All generated measurements remain
`SYNTHETIC`; software testing is `HOST_TEST`, not physical AFE validation.

## Manual acceptance next

1. Open `Projects & history`, create a starter project in a new local folder.
   Expect six named presets and no device connection.
2. Select DC and frequency presets; choose a new run directory and review.
   Change the run ID after review: Run must refuse stale approval until reviewed again.
3. Run the reviewed batch. Expect a responsive page, disabled conflicting
   actions, completion history, and persisted manifest/result files.
4. Run a second batch under a different ID/directory. Select both histories
   and compare; inspect outcomes and copied metric deltas, not a new verdict.
5. Add current Setup as a preset. Expect unsaved status and a save-as requirement;
   canceling a file dialog must not erase the current project.
6. Close with unsaved changes and decline discard. Expect the window to remain.
   Clear history view and verify the saved files still exist.

## Explicit limitations

Batch activity is indeterminate: per-preset percentage and cancellation are not
implemented. Normal close waits for the finite batch. There is no raw READ/LIVE
history export, trace overlay, in-place preset editor, hardware batch execution,
or newly validated hardware behavior. These are separate follow-up increments.

See [workflow guide](../docs/test-projects-and-history.md) for exact operations.
