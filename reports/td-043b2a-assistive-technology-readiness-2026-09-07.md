# TD-043B2A assistive-technology readiness

Date: 2026-09-07<br>
Status: **PARTIAL — adapter complete; current candidate runtime blocked**<br>
Evidence: **HOST_TEST only**

## Outcome

TD-043B2A does not close Dashboard screen-reader support. It adds an honest
capability gate and prepares metadata for a future compatible Tk runtime, but
the current Windows/Python 3.12 candidate uses Tk 8.6.15 and cannot expose the
application controls through the official Tk accessibility API.

Keyboard focus and programmatic accessibility are different contracts. Tab can
move between Tk widgets inside the process while Windows UI Automation still
sees no useful control name, role, value, or focus target. A screen reader uses
the latter information to explain the interface.

## Read-only candidate audit

The audit created the normal local Dashboard with its default Simulator state.
It did not call port discovery, open a serial port, create an adapter, access a
device, or change Windows accessibility settings.

| Check | Actual result | Disposition |
|---|---|---|
| Python | 3.12.10 | Recorded host fact |
| Tcl/Tk patch level | 8.6.15 | Recorded host fact |
| `tk accessible check_screenreader` | Rejected as an unknown/ambiguous `tk` subcommand | Metadata API unavailable |
| UI Automation descendants | 43 total | External Windows inspection |
| Named descendants | 6, all title bar/system menu/minimize/maximize/close objects | No named application control |
| Application descendants | 37 unnamed `ControlType.Pane` objects | Screen-reader Dashboard support blocked |
| Named/focusable application fields or actions | 0 | Screen-reader Dashboard support blocked |

The six named objects belong to Windows window chrome, not Source, Profile,
Test, Replay path, Continue, Validate, Run, issues, progress, results, or
artifacts.

## Implemented compatibility layer

`src/analog_validation_app/dashboard/accessibility.py` now:

- reads the actual Tcl/Tk patch level;
- tests the official `tk accessible` capability without changing OS state;
- reports one immutable capability result instead of inferring support from Tk
  focus behavior;
- fails closed and performs no metadata calls on Tk 8.6;
- on a capable runtime, assigns stable role, name, description, and help text;
- sends `set_acc_value` plus `emit_selection_change` only when a dynamic text
  value has changed.

The Dashboard registers its workflow notebook, critical form controls, action
buttons, run/live/issue/result status labels, observation table, and artifact
summary. Fake-toolkit tests freeze the exact Tk command contract for a future
Tk 9.1 runtime. They prove application wiring, not Windows or Narrator output.

No public product model, CLI JSON schema, manifest, project file, result file,
public API golden, evidence rule, or historical artifact changed.

## Test-first record

The first targeted run failed during collection with:

```text
ModuleNotFoundError: No module named 'analog_validation_app.dashboard.accessibility'
```

This was the expected failure because the tests were written before the new
module. After the capability model, bridge, widget metadata, and dynamic status
updates were implemented, the targeted Dashboard/accessibility set passed 54
tests. The new accessibility module separately reached 61/61 statements.

## Formal gates

| Gate | Result |
|---|---|
| Full pytest | PASS — 2,655 passed in 49.42 s |
| Package statement coverage | PASS — 15,805/15,805, 100.00% |
| Dashboard/accessibility target | PASS — 54 passed |
| New module focused coverage | PASS — 61/61 statements |
| Phase 5 public API golden | PASS — 15/15; golden unchanged |
| Product quality acceptance | PASS — 15/15 checks; `HOST_SOFTWARE_ONLY`; `hardware_validation=false` |
| Ruff | PASS |
| mypy | PASS — 218 source files |
| `pip check` | PASS |
| `git diff --check` | PASS |
| Current Tk metadata API | FAIL/UNAVAILABLE — Tk 8.6.15 |
| Windows UI Automation application semantics | FAIL — 37 unnamed application panes |
| Narrator and assistive-technology user chain | NOT RUN — programmatic prerequisite failed |

## Evidence boundary

| Evidence class | Use in this stage |
|---|---|
| `HOST_TEST` | Unit, fake-toolkit, real Tk, UI Automation, regression, static and quality gates |
| `SYNTHETIC` | Existing Simulator paths exercised by the regression and quality suite |
| `CSV_REPLAY` | Existing temporary/fixture Replay paths exercised by the regression suite |
| `SPICE_IDEAL` | Not produced |
| `BENCH_CONTROLLER` | Not produced or extended |
| `BENCH` | Not produced |

No software, Tk, UI Automation, or Simulator result is hardware validation.

## Remaining decision

TD-043B2A remains open until a distributable GUI runtime exposes meaningful
programmatic controls and passes Windows UI Automation, Narrator dynamic-status
events, error recovery, complete keyboard operation, and a real assistive-
technology user chain.

The next recommended slice is a time-bounded runtime decision spike:

1. determine whether the supported Windows Python distribution can ship and
   reproduce Tk 9.1 without weakening installation or deterministic-build
   gates;
2. run this existing metadata adapter against that candidate and inspect the
   resulting UI Automation tree;
3. if that route is not supportable, write an architecture decision comparing
   a GUI framework with established Windows accessibility peers while keeping
   all business workflows, evidence contracts, CLI, and controller-neutral
   boundaries unchanged.

TD-043B2B separately retains Remote Desktop, long keyboard-only real-user
sessions, localization, widths below 1040 pixels, and live theme switching.

## Sources used for the gate

- [Tcl/Tk 9.1 `tk accessible` manual](https://www.tcl-lang.org/man/tcl9.1/TkCmd/accessible.html)
- [Microsoft: Testing for accessibility](https://learn.microsoft.com/en-us/windows/win32/winauto/accessibility-testingtools)
- [Microsoft: Expose basic accessibility information](https://learn.microsoft.com/en-us/windows/apps/design/accessibility/basic-accessibility-information)
