# Dashboard keyboard and Tk isolation acceptance

Evidence: HOST_TEST and visible Windows software interaction only.
Branch: `codex/calibration-workflow`; committed base: `bf8c4c6`.
This report covers an uncommitted working-tree increment, not a release candidate.

## Scope and fixes

- Added Ctrl+A/Ctrl+Shift+A-key-symbol handling and Shift+Up/Down range selection
  to project tables. Ranges can expand, shrink, and stop at the first/last row;
  pointer/ordinary navigation and changed table contents reset stale anchors.
- Moved each Windows real-Tk scaling test into a fresh subprocess. Callback
  exceptions, process failures, missing Tk and timeouts fail on Windows;
  non-Windows skips remain an explicit platform boundary.
- The first focused run had 13 passes and 3 failures. The test was generating
  keyboard events before the clipped history table owned focus. Scrolling the
  table into view and asserting focus fixed the test interaction sequence.
  No failure was converted into a skip.

## Final verification

| Gate | Result |
|---|---|
| Unified full pytest and coverage | 2,591 passed in 34.59 s; no skips |
| Package statement coverage | 15,324/15,324; 100% |
| Windows real-Tk scales | 1.0, 1.5 and 2.0 passed in isolated processes, included above |
| Ruff | PASS |
| mypy | PASS; 225 source files |
| Dependency check | PASS; no broken requirements |
| Whitespace/diff check | PASS |

Coverage is executed-statement evidence, not a guarantee of absence of defects.
Earlier checkpoint build/install and product-quality results remain historical;
they were not rerun for this keyboard-only acceptance. Formal commit-bound
release-candidate, audit and hosted CI have not run for this increment.

## Visible Windows interaction

Using the actual Dashboard window and native file dialogs:

1. Loaded two existing synthetic run manifests; history showed two runs.
2. Selected the first row, extended with Shift+Down, shrank with Shift+Up,
   and selected both with Ctrl+A; visible highlights matched each operation.
3. Compared the selected runs: four changed presets; the shared DC preset
   remained unchanged with equal acquisition and inclusion counts.
4. Opened the existing six-preset project and saved a copy to a new path.
   Original and copy SHA-256 matched:
   `1aeb70545850299f040d07e08f765e704abc60e81cd596c2e984d0d6daa52cd7`.
5. Closed the test window. A subsequent window inventory confirmed it was gone;
   stderr was empty, stdout reported safe closure, SIMULATOR and worker IDLE.

Local artifacts are retained under
`C:\avs-dev\keyboard-acceptance-a34e784eb89144da8f3268776c2c5d9d`.
Existing manifests were replayed for this visible comparison; this was not a
new physical acquisition. Fresh batch execution is covered by the Tk tests.

## Boundaries

TD-041 is closed for the tested Windows software scope. Earlier reports retain
their original findings. No serial ports or hardware were accessed; no commit,
push, PR mutation, merge, tag or release was performed. The Codex `Bad Request`
message is a separate unresolved client/service diagnostic, not a pytest result.
