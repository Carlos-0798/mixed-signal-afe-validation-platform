# TD-040C1B Dashboard Replay Input Visibility Acceptance

**Date:** 2026-09-08<br>
**Evidence:** `HOST_TEST` with bounded `CSV_REPLAY` fixtures<br>
**Hardware validation:** `NO_NEW_HARDWARE_VALIDATION`

## Outcome

TD-040C1B is locally complete. The Projects & history page now makes the
TD-040C1A input-retention result visible without adding another execution path.
Selecting one history row shows its Replay input records; selecting two rows
keeps the existing comparison behavior.

## Interaction contract

- The original eight-column history table and two-row comparison gesture remain
  unchanged. This avoids widening the page and repeating the prior narrow-window
  failure mode.
- A separate read-only table shows preset ID, safe archived path, exact byte
  count, and full SHA-256 for one selected manifest v3 run.
- The guide distinguishes manifest preset references from stored physical files,
  so same-source deduplication is not mistaken for missing inputs.
- No selection explains how to inspect a run. Multiple selection keeps comparison
  intent and clears single-run details.
- v1/v2 explain that they predate retained inputs. An empty v3 explains
  Simulator-only runs and Replay presets that never started.
- The display says that loading or comparing a saved manifest rechecks its
  artifacts. It does not claim that SHA-256 authenticates an author.
- The table does not open the original CSV, rerun a test, modify history, or
  recalculate an engineering conclusion. Evidence remains `CSV_REPLAY`, not
  `BENCH`.

## Test-first evidence

The first focused run failed during collection because
`_history_input_archive_text` did not yet exist. This was the expected red test.
After adding the helper, read-only table, and selection-derived rendering, the
focused unit suite passed 20 tests. Additional v1/v2, multiple-selection, table
content, and style assertions increased the final focused result to 25 tests.

## Final verification

| Gate | Result |
|---|---|
| Project page plus real Tk focused tests | PASS — 25 tests |
| Modified widget statement coverage | PASS — 361/361, 100.00% |
| Windows Tk layout | PASS — 1040×760 at 100%, 125%, 150%, 175%, and 200% scaling |
| Full pytest and package statement coverage | PASS — 2,709 tests; 16,356/16,356, 100.00% |
| Ruff | PASS — all repository paths |
| mypy | PASS — 218 source files |
| pip dependency consistency | PASS — no broken requirements |
| `git diff --check` | PASS — exit 0; only the generated API golden line-ending normalization warning remains |

The fresh-process Tk tests exercise the Projects workflow and horizontal bounds.
Fake-toolkit tests assert the exact v3 table values and all selection/schema
guidance states. No port enumeration, physical device, AFE, or instrument was
used.

## Remaining product work

TD-040C1 still tracks two separate possibilities: persisting READ/LIVE output
observations and explicitly rerunning from an archived input. Neither is needed
to understand or verify the input archive in the current product. Curve overlays
and manifest authentication remain separate lower-priority work.
