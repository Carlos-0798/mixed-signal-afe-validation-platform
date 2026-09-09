# TD-044B source selection and Replay flow acceptance

**Date:** 2026-09-08<br>
**Scope:** Dashboard setup and local-file interaction<br>
**Evidence:** `HOST_TEST`<br>
**Hardware and serial:** `NOT_RUN`; no port enumeration/open, controller, AFE,
instrument, or bench access

## Product outcome

TD-044B removes three obstacles from the first-use setup path:

1. Source and Test selectors show readable names instead of internal enum text.
2. CSV Replay and Serial display only their own source fields.
3. CSV Replay provides a native local-file picker; Cancel preserves the current
   path.

Display aliases are deliberately separate from stored values. For example,
**Simulator — synthetic data** maps exactly to `SIMULATOR`, and **Frequency
response** maps exactly to `FREQUENCY_RESPONSE_ANALYSIS`. Callbacks, wizard
state, project presets, CLI JSON, API values, and artifacts retain the stable
enums. Unknown display names fail rather than silently selecting a different
mode.

## File and permission boundary

The new picker returns a path string only. It does not parse or read the file.
The existing Review step remains the sole complete `csv-replay.v1` loading and
validation boundary. Selecting Source or cancelling the picker changes no
evidence, creates no output, and grants no serial or hardware permission.

The Serial section was exercised only through injected/headless state. Real Tk
checks exercised the shared source layout with CSV Replay. No discovery
callback was invoked and no port was opened.

## Test-first record

The first focused run failed during collection because the display-name and
reverse-mapping helpers did not yet exist. Tests froze exact round trips,
unknown-label rejection, mutually exclusive source sections, successful path
selection, Cancel preservation, invalid callback rejection, native dialog
options, and application callback wiring before the minimum implementation was
completed.

## Verification

| Gate | Result |
|---|---|
| Dashboard source/setup target | PASS — 94 tests |
| Real Windows Tk | PASS — 10/10 at 1040×760, standard/high contrast, scaling 1.0/1.25/1.5/1.75/2.0 |
| Phase 5 public API golden | PASS — 15/15; golden unchanged |
| Full pytest | PASS — 2,684 passed in 65.98 s |
| Package statement coverage | PASS — 16,013/16,013, 100.00% |
| Product quality acceptance | PASS — 2/2 |
| Ruff | PASS |
| mypy | PASS — 227 source files |
| `pip check` | PASS |
| `git diff --check` | PASS |

## Remaining work

The interface is still English-only, and profile identities and channel names
remain technical because they are exact contract values. Current Tk 8.6.15
screen-reader support remains blocked under TD-043B2A. These limits are kept
separate from the completed first-use source-selection flow.
