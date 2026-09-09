# Dashboard novice and product evaluation

**Date:** 2026-09-07<br>
**Evidence:** `HOST_TEST`, `SYNTHETIC`, and temporary `CSV_REPLAY`<br>
**Hardware/serial access:** none<br>
**Hardware validation claim:** none

## Evaluation question

This review treated the application as an unfamiliar user would: start with no
loaded project, follow visible actions, make common input mistakes, return to
edit a reviewed configuration, run software data, save a result, repeat a save,
open project/history tools, cancel a batch, and inspect what remains visible at
common Windows scaling values. Code review and the complete regression suite
then checked whether the dark-theme change altered callbacks, state ownership,
cleanup, evidence, or create-new behavior.

## Product assessment

The six-step Source → Test → Configure → Review → Run → Result structure is
understandable without remembering hidden commands. Each step explains what is
happening, why it matters, and what must be checked next. Simulator is the
default and selecting a source alone opens no file or port. Primary actions,
secondary navigation, and cancellation are visually distinct while retaining
their text labels and keyboard focus.

The workflow prevents the most consequential state errors. Invalid input stays
in Configure and presents what happened, a possible cause, and a safe next
step. Run remains disabled until Review succeeds. Returning from Review revokes
the prior run authorization. A completed result switches to Results, preserves
its evidence label, and refuses to overwrite an existing export. Missing Replay
input fails before worker start. Project batch cancellation remains cooperative
and waits for cleanup and manifest publication.

The visual palette has strong calculated contrast for normal text: body text
14.50:1, muted text 7.15:1, cyan state text 7.97:1, green evidence text 8.89:1,
rose cancellation text 5.78:1, primary-button text 8.83:1, and selected-row text
8.55:1. Disabled text is 3.93:1 and is never the only explanation of state.
These calculations are useful design evidence, not a WCAG certification.

## Defects found and fixed

### Project actions outside the visible window — fixed

At the 1180×780 minimum window, wide history-table columns forced four third-
column actions beyond the right edge: **Save project as**, **Choose directory
name**, **Cancel batch safely**, and **Clear view**. The problem reproduced at
scaling 1.0, 1.25, 1.5, 1.75, and 2.0. This was especially serious for safe
cancellation because a pointer user could not see the control.

A failing real-Tk regression produced three failures in the original 1.0/1.5/
2.0 matrix. The table now derives a bounded initial column width from its column
count, retains a 90-pixel minimum and horizontal scrolling, and lets every
critical action remain inside the viewport. Five-scale coordinate checks now
cover all project buttons and the main workflow controls.

### AFE-specific new-project defaults — fixed

The blank Projects page prefilled `afe-project`, `AFE test project`, and
`afe-project.json`. Those values were valid but made a controller-neutral
product look tied to one device family. New projects now start as
`validation-project`, `Analog validation project`, and
`validation-project.json`. Existing files, CLI examples, schemas, histories,
and AFE compatibility are unchanged.

## Regression results

| Gate | Result |
|---|---|
| UI-driven first-use Simulator DC chain | PASS — invalid input, correction, Review, back/edit invalidation, Run, `SYNTHETIC` result, create-new export, repeat-save rejection |
| UI-driven temporary CSV Replay chain | PASS — missing file rejected before Run; corrected Replay completed as `CSV_REPLAY` |
| Dashboard-focused unit/integration suite | PASS — 204 passed |
| Real Windows main/project geometry and focus | PASS — scaling 1.0, 1.25, 1.5, 1.75, and 2.0 |
| Full pytest and package statement coverage | PASS — 2,627 passed; 15,639/15,639; 100.00% |
| Phase 5 public API golden | PASS — 15/15; no contract change |
| Ruff / mypy / dependency / diff | PASS — mypy checked 225 files |

No prior stale-review, hidden-error, unsafe overwrite, fake-result, cross-thread
Tk, cancellation, cleanup-before-close, manifest, or evidence-label problem
reappeared in the exercised paths. The dark theme changed presentation and
geometry only; it did not change the analysis or job lifecycle.

## Remaining usability risks

1. Validation issues do not yet identify a structured `field_id`, move focus to
   the exact invalid input, or visually mark that field. A novice may need to
   scan a dense configuration section after reading the safe-next-step text.
2. Screen-reader announcements, Windows high-contrast mode, Remote Desktop,
   displays narrower than the 1180-pixel minimum, and long keyboard-only
   sessions still need real-user or target-environment evaluation.
3. The interface is English-only and retains necessary engineering vocabulary
   such as channel identity, R-squared, RMSE, evidence class, and manifest.
   Guidance reduces recall but does not replace domain onboarding.
4. This evaluation used deterministic software sources. It does not evaluate
   serial-device discovery, physical controls, instrument latency, wiring, or
   bench safety.

`SYNTHETIC`, `CSV_REPLAY`, `HOST_TEST`, `SPICE_IDEAL`, `BENCH_CONTROLLER`, and
`BENCH` remain distinct. Nothing in this review upgrades software evidence to a
hardware claim.
