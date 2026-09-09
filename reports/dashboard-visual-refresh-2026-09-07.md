# Dashboard visual refresh acceptance

**Date:** 2026-09-07<br>
**Evidence:** `HOST_TEST`, with displayed default data labeled `SYNTHETIC`<br>
**Hardware access:** none<br>
**Serial discovery/open:** none<br>
**Hardware validation claim:** none

## Resulting display system

The Setup & run, Results & evidence, and Projects & history pages now share one
native ttk **Precision Lab Console** theme. Deep graphite surfaces separate the
application, cards, and editable fields. Cyan identifies the active step,
primary actions, focus, and real progress. Green identifies the declared
evidence boundary, amber is reserved for warnings, and rose identifies
cancellation or failure actions.

The header states `LOCAL / OFFLINE`, `READ-ONLY DEFAULT`, and
`EVIDENCE LABELED`. These text labels remain the authority; color never changes
the evidence class or replaces status text. Tables have stronger headings,
30-pixel rows, and explicit selection colors. Project actions use compact
primary/secondary/cancel styles instead of stretching unrelated buttons across
the page.

The refresh changes only Tk construction and presentation. It does not modify
the Dashboard state schemas, wizard state machine, worker, project batch
semantics, manifest v1/v2, CLI, public API, analysis, export, or artifact hash
rules. It adds no fake measurement rows, idle animation, network resource,
background timer, serial discovery, or device interaction.

## Test-first record

Before implementation, the focused contract run produced five expected
failures. They showed the old light background, 27-pixel table rows, unstyled
project tables/progress/cancel control, and missing header boundary labels.
After the shared styles and page wiring were added, the same run passed all five
tests. The complete Dashboard-focused suite then passed 200 tests.

The first pixel-capture helper failed because Pillow is not installed in the
project environment. No product dependency was added. The review used the
Windows built-in drawing API instead and captured all three actual Tk pages
from a Simulator-only, no-action session.

## Verification

| Gate | Result |
|---|---|
| Focused red/green display contract | PASS — 5 passed after the expected five-failure baseline |
| Dashboard unit/integration slice | PASS — 200 passed |
| Fresh-process real Windows Tk | PASS — scaling 1.0, 1.25, 1.5, 1.75, and 2.0; critical controls remain inside the viewport |
| Full pytest with package statement coverage | PASS — 2,627 passed; 15,639/15,639; 100.00% |
| Phase 5 public API golden | PASS — 15 passed; no API update required |
| Ruff | PASS |
| mypy | PASS — 225 source files |
| `pip check` | PASS |
| `git diff --check` | PASS |

The real-Tk checks verify palette application, semantic progress/table styles,
the three persistent boundary labels, focus traversal, and successful layout
creation at each scaling value. The screenshots are visual review aids; the
automated assertions remain the repeatable acceptance source.

All results are software-only. `SYNTHETIC`, `CSV_REPLAY`, `HOST_TEST`,
`SPICE_IDEAL`, `BENCH_CONTROLLER`, and `BENCH` remain distinct. This work adds
no `SPICE_IDEAL`, `BENCH_CONTROLLER`, or `BENCH` evidence.

## Remaining visual limits

- The host operating system still owns the native window frame and may apply a
  different title-bar color.
- Automated real-Tk checks currently run on Windows. Linux and macOS pixel
  comparison remains a future portability task.
- Existing repository marketing screenshots are retained unchanged; replacing
  published media should be a separate reviewed documentation change.
