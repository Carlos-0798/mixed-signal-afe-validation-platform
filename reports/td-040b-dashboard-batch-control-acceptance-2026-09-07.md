# TD-040B Dashboard batch control acceptance

**Date:** 2026-09-07
**Evidence:** `HOST_TEST`, with executed product data labeled `SYNTHETIC`
**Hardware access:** none
**Serial discovery/open:** none
**Hardware validation claim:** none

## Scope and contract

TD-040B connects the existing TD-040A batch progress and cancellation types to
the local Dashboard. It does not change the public API, manifest v1/v2 schema,
batch execution rules, artifact hashes, CLI, analysis, or worker cleanup logic.
It does not add READ/LIVE raw persistence, trace overlays, signing, scheduling,
or device access.

The background project thread receives one
`ValidationBatchCancellationToken` and writes immutable
`ValidationBatchProgress` values to a thread-safe queue. Only the Tk owner
thread drains that queue and renders the latest real event. The page reports
phase, current preset ID, one-based number, planned total, and completed
terminal-record count. It does not estimate percentage between events.

The cancel action is enabled only during an active project batch and before a
request has been accepted. It sets the cooperative token once and then stays
disabled while the active worker cleans up. The batch remains busy until its
terminal v2 manifest has been atomically published and transferred to history.
Window close requests the same cancellation and keeps polling until that safe
terminal point before destroying the window.

History rows display `COMPLETE`, `PARTIAL`, `CANCELLED`, or `ERROR` from v2 plus
planned, completed, and not-started counts. A strict v1 manifest stays readable
and is shown as `LEGACY_V1`; the Dashboard does not invent a terminal batch
status that the old file never encoded.

## Test-first record

The first project used the system Python and failed before collection because
that interpreter did not contain pytest. The project virtual environment was
then confirmed to import `analog_validation_app` from this worktree.

The real implementation-before test run produced 9 failures and 10 passes.
Failures showed all intended gaps: no workspace cancellation/progress surface,
no TD-040A publisher arguments, an indeterminate progress widget, no page cancel
action, and close-without-cancel behavior. After the minimal three-file runtime
change, workspace and fake-widget tests passed. The remaining real-Tk assertion
used ttk `cget` for a state query; changing the test to ttk `instate` verified
the intended disabled state without weakening product behavior.

The first complete coverage run passed 2,622 tests with one inherited Tk skip,
but reported 15,604/15,606 statements. Behavior tests were added for canceling
after a current-preset event and for the page action itself, bringing the two
changed Dashboard modules to 419/419 statements. The inherited Tk skip came
from creating several Tcl interpreters in one process; moving each scaling case
to a fresh process made all six real-Tk accessibility/project cases pass.

## Final verification

| Gate | Result |
|---|---|
| Dashboard workspace/widget/project-Tk focus | PASS — 19 passed |
| Real Tk accessibility + project workflows | PASS — 6 passed at scaling 1.0, 1.5, and 2.0 |
| Full pytest with package statement coverage | PASS — 2,623 passed; 15,606/15,606; 100.00% |
| Phase 5 public API golden | PASS — 15 passed; no contract update required |
| Ruff | PASS |
| mypy | PASS — 225 source files |
| `pip check` | PASS |
| `git diff --check` | PASS |

The tests cover live progress marshaling, current-preset cancellation text,
idempotent cancel, cancelled v2 publication with all planned presets explicitly
not started, legacy-v1 display, control enable/disable state, terminal history
refresh, comparison after cancellation, and a close request that does not
destroy the window until a blocked cleanup is released.

All resulting claims remain software-only. `SYNTHETIC`, `CSV_REPLAY`,
`HOST_TEST`, `SPICE_IDEAL`, `BENCH_CONTROLLER`, and `BENCH` remain distinct;
this checkpoint adds no `SPICE_IDEAL`, `BENCH_CONTROLLER`, or `BENCH` evidence.

## Remaining work

TD-040C still owns raw READ/LIVE observation artifacts, curve overlays, and a
signature/authentication trust model. Concurrent scheduling, retries, cloud
history, real Serial reliability, physical AFE validation, and instrument
control remain separate work with separate authorization and evidence.
