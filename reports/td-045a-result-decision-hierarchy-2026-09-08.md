# TD-045A result decision hierarchy acceptance

**Date:** 2026-09-08<br>
**Scope:** Dashboard result interpretation only<br>
**Evidence:** `HOST_TEST`<br>
**Hardware and serial:** `NOT_RUN`; no port enumeration/open, controller, AFE,
instrument, or bench access

## Product outcome

The previous result card contained the necessary facts but gave completion,
PASS/FAIL, evidence, limitations, and issues equal visual weight. A new user
could notice PASS without understanding its evidence boundary.

TD-045A introduces a first-read decision summary in this order:

1. product run result;
2. engineering decision;
3. exact evidence class and its meaning;
4. `NO_NEW_HARDWARE_VALIDATION` plus the first unverified item;
5. the next safe action.

The detailed result remains directly below and retains the summary, complete
limitations, complete not-verified list, and structured issue recovery. No
result field was removed.

## Contract and evidence safety

The implementation reads the existing immutable `DashboardState`. It does not
recalculate criteria, infer a new TestRun, alter evidence, or change export,
project, manifest, CLI, schema, or public API contracts.

`COMPLETED` is explicitly separate from PASS/FAIL. An observation-only result
with no outcome displays `NO ENGINEERING DECISION — no PASS/FAIL was recorded`.
SYNTHETIC, CSV_REPLAY, THEORY, SPICE_IDEAL, SPICE_MODEL, HOST_TEST,
BENCH_CONTROLLER, BENCH_DMM, and BENCH_SCOPE each keep their exact name and a
bounded interpretation. The BENCH variants in this stage were synthetic
immutable state fixtures used to test display copy; they are `HOST_TEST`, not
new physical evidence.

## Test-first record

The first focused run failed during collection because the decision-summary
helper did not exist. After the minimum implementation, one assertion exposed
unnecessarily long FAIL wording, and pytest warned because an imported enum
name began with `Test`. The copy was shortened and the test import was aliased;
the focused suite then passed without warnings.

## Verification

| Gate | Result |
|---|---|
| Result/workflow/real-Tk target | PASS — 85 tests |
| Evidence/status/outcome interpretation matrix | PASS — 9 combinations plus idle and issue recovery |
| Full pytest | PASS — 2,693 passed in 102.65 s |
| Package statement coverage | PASS — 16,034/16,034, 100.00% |
| Phase 5 API golden + product quality | PASS — 17/17 |
| Ruff | PASS |
| mypy | PASS — 227 source files |
| `pip check` | PASS |
| `git diff --check` | PASS |

## Remaining work

This stage improves interpretation but does not replace real-user comprehension
testing. The interface remains English-only, and current Tk 8.6.15 screen-reader
support remains blocked under TD-043B2A. Result comparison and project history
still use their existing layouts and may be assessed as a separate product
workflow rather than folded into this result-card change.
