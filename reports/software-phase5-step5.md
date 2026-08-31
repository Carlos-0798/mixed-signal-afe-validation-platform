# Software Phase 5 Step 5 Report

**Date:** 2026-08-31
**Milestone:** safe local Dashboard state, presenter, controller, and desktop shell
**Evidence class:** HOST_TEST / installed-package Windows GUI smoke
**Physical serial or hardware operation:** none
**Verified AFE hardware performance claims:** 0

**Implementation commit:**
`cc1548dce57624d7fab9c93d2113ad79309ac14d`

## Outcome

Software Phase 5 Step 5 is complete; Phase 5 implementation is now 5 of 8
checkpoints. `analog-validation dashboard` launches a real local Tkinter/ttk
window with Source, Configuration, Progress, Plot, Result/Evidence, and
Artifacts regions. It defaults to Simulator with AFE v1 presentation and
returns only after bounded worker closure.

This checkpoint deliberately delivers a safe shell rather than pretending the
Step 6 workflow is ready. Run remains disabled and labelled as awaiting Step 6.
The shell does not enumerate a port, create an adapter/service, calculate an
engineering result, write an artifact, start a network listener, or promote any
hardware claim.

## Delivered architecture

| Layer | Delivered behavior |
|---|---|
| state | Immutable bounded `dashboard-state.v1` panels/actions with explicit `NO_NEW_HARDWARE_VALIDATION` |
| presenter | Owner-thread-only copy of reviewed catalog selection, worker events/result/issues, finalized report view, points, and path-free artifact identities |
| controller | Headless polling, cooperative cancel, bounded close/join, and no adapter/service construction |
| widgets | Rendering-only Tk/ttk six-region layout; callbacks are injected and status is expressed in text rather than color alone |
| app | Lazy Tk import, main-thread lifecycle, safe close result as `dashboard-session.v1`, and clear missing-Tk/display error boundary |
| CLI | Stable `analog-validation dashboard` launch; `demo` remains honestly unavailable |

The Dashboard consumes existing product and report facts. It does not parse a
wire record, fit a line, detect a hysteresis transition, re-evaluate criteria,
or decide PASS/FAIL.

## Executed verification

| Gate | Actual result |
|---|---|
| Phase 5 focused product tests | PASS — 500 tests |
| Product package coverage | PASS — 2,948/2,948 statements, 100% |
| Full pytest suite | PASS — 2,018 tests |
| Formal + optional + product coverage | PASS — 10,273/10,273 statements, 100% |
| Phase 1–4 golden compatibility | PASS — retained inside the full suite |
| Headless Dashboard contracts | PASS — state, presenter, controller, widgets, app, issues, CLI, and architecture tests |
| Actual-worker close integration | PASS — cancel reached `CANCELLED`, finite join completed, and cleanup ran |
| Real Windows Tk smoke | PASS — visible local window opened for approximately 500 ms and closed safely |
| Ruff rule check | PASS — full repository |
| Ruff formatting for Step 5 Python files | PASS — 19 files |
| mypy on `src`, `tools`, and `tests` | PASS — 176 files |
| pip dependency check | PASS — no broken requirements |
| Patch whitespace | PASS |
| Isolated sdist/wheel build | PASS — `0.1.0.dev0` |
| Wheel archive inspection | PASS — 88 entries; six Dashboard modules, `py.typed`, and one console entry point present |
| Sdist archive inspection | PASS — 241 entries; Dashboard modules and typed marker present |
| Repository-external base-wheel install | PASS — headless import, module CLI, and real Tk launch/close |
| Physical serial, MSP430 action, instruments, or AFE test | NOT RUN |

The focused tests exposed and the implementation corrected two ordering defects
before this checkpoint was accepted. First, cancel originally synchronized the
presenter before asking the worker to cancel, so the UI could briefly retain a
stale running state. The controller now requests worker cancellation first and
then polls the authoritative state. Second, a controller timeout issue could be
cleared by the next worker synchronization; polling now occurs before the
controller presents that issue. Both sequences have regression tests.

The repository-wide formatter still proposes historical formatting-only edits
tracked in TD-034. Ruff's rule checker passed, and all 19 Step 5 Python files
passed the formatter without mixing that repository-wide cleanup into this
feature.

## Build and external-install evidence

| Artifact | Size | SHA-256 |
|---|---:|---|
| `mixed_signal_afe_validation_platform-0.1.0.dev0-py3-none-any.whl` | 222,366 bytes | `fb958128000450764f78240cbf9ee1481448ce0970d9b46f1864c0b689938df6` |
| `mixed_signal_afe_validation_platform-0.1.0.dev0.tar.gz` | 395,585 bytes | `054b622b7ddf133bdc5bbe3cfe75d89509ce37ea84fd296c9af49f96c1fc04e7` |

The wheel was installed without dependencies into a fresh virtual environment
under `%LOCALAPPDATA%\Temp`, outside the repository. Importing
`analog_validation_app` and `analog_validation_app.dashboard` reported
`dashboard-state.v1` while both `tkinter_loaded` and `pyserial_loaded` remained
false. The installed module entry point returned `product-cli-output.v1` for
`version`.

The explicit installed-package Dashboard smoke then opened a real Windows Tk
window and returned this bounded session result:

```text
closed_safely=true
source_mode=SIMULATOR
profile_identity=afe/1
worker_state=IDLE
hardware_claim=NO_NEW_HARDWARE_VALIDATION
schema_version=dashboard-session.v1
tkinter_loaded=true
pyserial_loaded=false
```

The external working-directory entries were unchanged before and after the
window lifecycle. The host's application-control policy previously blocked
temporary-directory console-wrapper executables, so the installed package was
invoked through `python -m analog_validation_app`; this reaches the same packaged
CLI entry implementation without claiming that the temporary `.exe` wrapper was
permitted.

Generated archives and the external virtual environment are local verification
artifacts, not committed release binaries.

## Safety and evidence boundary

- The connected MSP430 was not enumerated, opened, read, reset, flashed, or
  written during Step 5.
- No COM port, AFE, breadboard, ADC, comparator, instrument, or laboratory
  resource was accessed.
- The real window proves only local software lifecycle and presentation.
- Simulator remains a `SYNTHETIC` source; opening a window does not change it to
  BENCH evidence.
- The presenter retains finalized engineering outcomes and cannot promote a
  failed, incomplete, unsupported, aborted, or cancelled result to PASS.
- Dashboard artifacts contain reviewed names/hashes rather than absolute paths
  or raw serial frames.
- The earlier Phase 4 receive-only MSP430 result remains a separate narrow
  `BENCH_CONTROLLER` record and was neither repeated nor broadened.

## Remaining work and next gate

Step 5 does not provide the six-step beginner workflow, an enabled Run action,
live serial operation, a one-command portfolio demo, CI, v1.0 release, or
physical AFE validation.

The next checkpoint is Software Phase 5 Step 6 only: connect source selection,
test selection, configuration, evidence/safety review, run, and view/export to
the existing reviewed services and single-owner worker. Simulator remains the
default. Any Serial path must require an explicit port/profile, bounded time and
record count, and receive-only confirmation; it must not add a raw command box
or write control. A new physical controller smoke would require separate
authorization and a separate report.
