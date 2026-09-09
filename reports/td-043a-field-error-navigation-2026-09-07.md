# TD-043A field-level error navigation acceptance

**Date:** 2026-09-07<br>
**Scope:** local Dashboard validation and recovery only<br>
**Primary evidence:** `HOST_TEST`<br>
**Hardware claim:** `NO_NEW_HARDWARE_VALIDATION`

## Result

TD-043A is complete in the uncommitted `codex/calibration-workflow` working
tree. A validation failure can now carry one internal stable field key from the
form or shared workflow configuration boundary to the Dashboard. When that key
matches an editable control, the UI:

1. keeps the existing severity, issue code, what-happened, possible-cause, and
   safe-next-step text;
2. names the field that needs correction;
3. scrolls the control into the visible page;
4. moves keyboard focus to it, including when the wizard remains on Configure;
5. applies a rose error border that does not replace the text explanation; and
6. clears the border after correction or navigation.

An unknown or non-field failure keeps the existing issue-card behavior. The UI
does not parse English error messages to guess a control.

## Compatibility boundary

- `user-issue.v1` and `user_issue_to_dict()` are unchanged.
- `dashboard-state.v1`, `dashboard-wizard.v1`, and `dashboard-session.v1` are
  unchanged.
- CLI JSON, project v1, preset v1, run-manifest v1/v2, result exports, and
  historical artifacts are unchanged.
- `ProductFieldError` is an internal `ProductRequestError` subtype and is not
  added to the package or error-module `__all__` contract.
- The Phase 5 public API golden remained byte-for-byte exact: 15/15 tests
  passed without regenerating the golden.

Multi-field constraints point to the value that a user should edit next. For
example, duplicate primary/secondary channels point to the secondary channel,
equal replay bounds point to the maximum, and invalid frequency bounds point to
the target cutoff. These mappings are raised by validation code, not derived
from display text.

## Test-first record

The first command used the system Python and stopped before collection because
that interpreter had no `pytest`. The project `.venv` was then verified to
import `analog_validation_app` from this exact worktree.

The first intentional red run in the project environment produced **15 failed,
90 passed**. The failures proved that field keys, application exposure,
focus/highlight behavior, fallback behavior, and safe form-callback handling did
not yet exist.

After the minimum implementation, those tests passed **105/105**. Expanding to
all Dashboard tests then found **7 failed, 205 passed** because several existing
test doubles still implemented the established two-argument widget `render`
call. The early failure also left a test cleanup thread waiting, so the run was
interrupted rather than reported as complete. The implementation was changed to
preserve the two-argument call and place the hint in internal widget state.

The corrected Dashboard suite passed **212/212**. The first full run passed all
**2,635 functional tests** but correctly failed the coverage gate at **99.77%**:
36 lines were exercised only inside fresh Tk subprocesses or were defensive
branches. Direct unit tests were added for the same behavior; the threshold was
not lowered.

## Final local gates

| Gate | Result |
|---|---|
| Dashboard-focused unit/integration tests | PASS — 212 passed |
| Real Windows Tk field recovery | PASS — scaling 1.0, 1.25, 1.5, 1.75, and 2.0 in fresh processes |
| Full pytest and package statement coverage | PASS — 2,641 passed; 15,748/15,748 statements; 100.00% |
| Phase 5 public API golden | PASS — 15/15; golden unchanged |
| Product quality acceptance | PASS — 15/15 checks; scope `HOST_SOFTWARE_ONLY` |
| Ruff | PASS |
| mypy | PASS — 225 source files |
| Dependency consistency | PASS — no broken requirements |
| Patch whitespace | PASS — `git diff --check` |

The real Tk chain selected CSV Replay but supplied no path. Review rejected it
before Run, focused and revealed **Replay CSV path**, displayed
`Invalid.TEntry`, and restored `TEntry` after navigation. It did not enumerate
or open a serial port and did not create an output artifact.

## Evidence classification

| Evidence class | TD-043A use |
|---|---|
| `SYNTHETIC` | Existing Simulator regression paths passed; this is software evidence only. |
| `CSV_REPLAY` | Existing strict replay paths and a missing-path UI rejection passed; no new hardware meaning is inferred. |
| `HOST_TEST` | Primary classification for unit, integration, real Windows Tk, quality, and static gates. |
| `SPICE_IDEAL` | `NOT_RUN`; no circuit simulation was part of this stage. |
| `BENCH_CONTROLLER` | `NOT_RUN`; no controller or physical serial port was accessed. |
| `BENCH` | `NOT_RUN`; no AFE, instrument, wiring, or physical measurement was accessed. |

## Remaining work

TD-043B retains the separate accessibility and environment studies: Windows
screen-reader announcements, high-contrast themes, layouts below the current
1180-pixel minimum, Remote Desktop, long keyboard-only sessions with real users,
localization, and non-Windows GUI behavior. Current focus and scaling automation
does not certify those areas.

This stage made no commit, push, PR change, merge, tag, Release, package
publication, visibility/license/history change, serial enumeration/open, device
access, laboratory action, or hardware purchase.
