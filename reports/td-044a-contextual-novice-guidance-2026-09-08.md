# TD-044A contextual novice guidance acceptance

**Date:** 2026-09-08<br>
**Scope:** Dashboard display layer only<br>
**Evidence:** `HOST_TEST`; exercised product sources are `SYNTHETIC` and temporary
`CSV_REPLAY` only<br>
**Hardware:** `NOT_RUN`; no serial enumeration/open, MSP430, AFE, instrument, or
bench access

## Problem and resulting behavior

The Dashboard already enforced a safe six-step workflow, but a new user could
still have to infer why Run was disabled and what several engineering fields
meant. The existing generic field hint was physically inside the Replay/Serial
connection frame, so the default Simulator path did not display it at all.

TD-044A adds two presentation-only aids:

1. Configure has a separate **Plain-language field guide** visible for every
   source. It explains the selected source boundary and the active test without
   changing the draft, validation, worker, result, or evidence.
2. The workflow action area states the next usable action. It explains that Run
   requires a valid compiled review and changes to correction guidance after a
   validation failure.

The six test explanations cover finite Read observations, DC input/output fit
and R-squared/RMSE direction, Hysteresis threshold separation, Calibration
reference/observed values and non-applied coefficients, amplitude-only
Frequency Response, and the finite bounded Live Monitor buffer.

## Compatibility and safety

- Guidance reads `DashboardWizardState` and `DashboardWizardDraft`; it does not
  create a parallel permission state machine.
- The helpers and new widget variables are private presentation details. No
  public import, schema, CLI JSON, project, result, coefficient, or manifest
  contract changes.
- Simulator says `SYNTHETIC`; Replay says `CSV_REPLAY`; both explicitly reject
  a hardware-validation interpretation.
- Selecting Serial states that it does not discover or open a port. This phase
  did not exercise that source.
- The page remains vertically scrollable. No horizontal scroll or new minimum
  width was introduced.
- ADR-0004 remains Proposed. No PySide6 dependency, license, or entry-point
  change was made.

## Test-first record

The first focused run failed during collection because the two new private
guidance helpers did not exist. After the minimum implementation, one test
failed because the UI said “a finite set of observations” while the readability
contract required the shorter “finite observations.” The wording was aligned;
the focused widget suite then passed.

## Verification

Final results are recorded after the complete local gate:

- focused fake-toolkit workflow tests: **PASS — 40/40**
- real Windows Tk at 1040×760, standard and forced high contrast, scaling
  1.0/1.25/1.5/1.75/2.0: **PASS — 10/10**
- full pytest: **PASS — 2,670 passed in 51.74 s**
- package statement coverage: **PASS — 15,964/15,964, 100.00%**
- Phase 5 public API golden: **PASS — 15/15; golden unchanged**
- product quality checks: **PASS — 2/2**
- Ruff: **PASS**
- mypy: **PASS — 227 source files**
- `pip check`: **PASS**
- `git diff --check`: **PASS**

The final repository-external composite used a new temporary directory. A
12-point Simulator DC run completed with `SYNTHETIC` evidence and created a new
`result-export.v1` artifact. A copied temporary Replay file completed a two-
sample Read with `CSV_REPLAY` evidence. Both CLI outputs parsed as
`product-cli-output.v2`. The artifacts remain under
`files-mentioned-by-the-user-agent/work/td044a-acceptance-20260908-010508`;
earlier familiarization outputs were not deleted.

## Remaining limits

The added copy is English and does not close localization work. Automated tests
cannot replace a real unfamiliar-user study. Current Tk 8.6.15 screen-reader
support also remains blocked under TD-043B2A. Remote Desktop, below-1040-pixel
layouts, long keyboard-only sessions, and runtime theme changes remain
TD-043B2B work.
