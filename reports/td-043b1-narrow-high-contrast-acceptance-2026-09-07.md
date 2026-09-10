# TD-043B1 narrow-screen and high-contrast acceptance

**Date:** 2026-09-07<br>
**Scope:** local Dashboard display layer only<br>
**Primary evidence:** `HOST_TEST`<br>
**Hardware claim:** `NO_NEW_HARDWARE_VALIDATION`

## Result

TD-043B1 is complete in the uncommitted `codex/calibration-workflow` working
tree. The supported Dashboard minimum is now 1040×760. Dense setup,
configuration, acceptance, calibration, frequency, monitor, and source groups
use three columns and additional vertical rows. Result tables, explanatory text,
export controls, and coefficient controls use a width budget that stays inside
the same viewport. Required actions are not placed behind horizontal scrolling.

At startup, the Dashboard reads the Windows high-contrast flag. It does not
toggle or write the operating-system setting. When the flag is enabled, ttk
surfaces, text, focus, selection, disabled states, error borders, native scroll
canvases, and live charts use Windows system colors. Source, status, error,
evidence, cancellation, and limitation meanings remain explicit text.

The current host reported high contrast disabled. Automated real-Tk tests also
forced the enabled path so both display modes were exercised. A Windows contrast
change made while the Dashboard is open requires an application restart.

## Product and compatibility boundary

- No state, request, result, issue, project, preset, manifest, report, or CLI
  schema changed.
- `validation-run-manifest.v1` and v2 behavior and historical artifacts are
  unchanged.
- The Phase 5 public API golden remained exact; it was not regenerated.
- The existing two-argument widget render boundary and application state
  machine are unchanged.
- Layout work changes only widget geometry, fixed display widths, canvas colors,
  and the internal style helper's optional high-contrast selection.
- High contrast changes presentation only. It does not change evidence,
  engineering outcomes, worker state, cancellation, cleanup, or export rules.

## Test-first record

The first intentional red run stopped during collection because
`_windows_high_contrast_enabled` did not yet exist. This proved the system-color
contract was absent before implementation.

After the minimum style, detection, three-column layout, and 1040×760 change,
the first focused set passed **47/47**. Expanding acceptance to the Results page
first exposed a test-state mistake: result controls were still intentionally
hidden in the Source step and therefore had one-pixel pre-layout widths. The
test was corrected to render a real Result-step view instead of weakening the
assertion.

That corrected test then failed all ten standard/high-contrast scaling cases
because the old fixed plot columns and two 500-pixel text cards widened the
result page; the rightmost Save and Load actions extended outside 1040 pixels.
The table columns, result text wraps, and save-panel grid were constrained.
Setup, Results, Projects, and widget tests then passed **52/52**.

The first full run passed all **2,648 functional tests** but correctly failed the
coverage gate at **99.99%**: two defensive lines for a Tk facade that rejects
attached state were not executed. A rigid-facade unit case was added; the 100%
threshold was not lowered. The first static run also found a constant-name
`setattr` lint issue and a fake-root typing gap. Direct attribute assignment,
an explicit lint annotation on the tested fallback, and a declared fake-root
field resolved them.

## Final local gates

| Gate | Result |
|---|---|
| Dashboard narrow/high-contrast focused set | PASS — 52 passed |
| Real Windows Tk Setup/Results field recovery and display | PASS — standard and forced high contrast at scaling 1.0, 1.25, 1.5, 1.75, and 2.0; 1040×760 |
| Real Windows Tk Projects/history/keyboard chain | PASS — five scaling levels; 1040×760; temporary Simulator outputs |
| Full pytest and package statement coverage | PASS — 2,648 passed; 15,819/15,819 statements; 100.00% |
| Phase 5 public API golden | PASS — 15/15; golden unchanged by this stage |
| Product quality acceptance | PASS — 15/15 internal checks; 2 test cases; scope `HOST_SOFTWARE_ONLY` |
| Ruff | PASS |
| mypy | PASS — 224 source files |
| Dependency consistency | PASS — no broken requirements |
| Patch whitespace | PASS — `git diff --check` |

The real-Tk chains create fresh Tcl interpreters so one scaling or theme case
cannot contaminate another. Project history used Simulator and new temporary
output directories. The field-recovery chain selected CSV Replay but supplied
no path, so Review rejected it before Run. No serial discovery callback was
invoked.

## Evidence classification

| Evidence class | TD-043B1 use |
|---|---|
| `SYNTHETIC` | Existing Simulator regression and temporary project batch paths passed; software evidence only. |
| `CSV_REPLAY` | Existing strict Replay regressions and missing-path Review rejection passed; no physical source was involved. |
| `HOST_TEST` | Primary classification for unit, integration, Windows Tk, public golden, quality, and static gates. |
| `SPICE_IDEAL` | `NOT_RUN`; circuit simulation was outside this display-layer stage. |
| `BENCH_CONTROLLER` | `NOT_RUN`; no controller or physical serial port was enumerated or opened. |
| `BENCH` | `NOT_RUN`; no AFE, instrument, wiring, or physical measurement was accessed. |

## Remaining work

TD-043B2 retains screen-reader announcement tests, Remote Desktop, long
keyboard-only sessions with real users, localization, widths below 1040 pixels,
runtime response to an OS theme change, and non-Windows GUI behavior. Automated
focus, geometry, and forced system-color checks do not certify those areas.

This stage made no commit, push, PR change, merge, tag, Release, package
publication, visibility/license/history change, serial enumeration/open, device
access, laboratory action, or hardware purchase.
