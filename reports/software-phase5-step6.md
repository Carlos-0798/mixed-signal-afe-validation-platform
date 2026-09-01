# Software Phase 5 Step 6 Report

**Date:** 2026-08-31<br>
**Milestone:** reviewed six-step beginner workflow and worker/service wiring<br>
**Evidence class:** HOST_TEST / SYNTHETIC / CSV_REPLAY / installed-package GUI smoke<br>
**Physical serial or hardware operation:** none<br>
**Verified AFE hardware performance claims:** 0

**Implementation commit:**
`f9f694fd5857182b0dca5fcfc8ffbbf6ff414246`

## Outcome

Software Phase 5 Step 6 is complete; Phase 5 implementation is now 6 of 8
checkpoints. The local Dashboard is no longer an idle shell. It now provides the
fixed Source → Test → Configure → Review → Run → Result/Export workflow and sends
only a reviewed immutable request through the existing single-owner worker.

The Step 6 implementation does not add a second engineering path. CLI and
Dashboard compile `product-workflow-config.v1` through the same
`prepare_product_job()` function and reuse the existing adapters, read workflow,
DC/hysteresis analysis, criteria, result exports, cancellation, and cleanup.
The interface displays configuration and conclusions but does not parse wire
records, fit data, calculate thresholds, or decide PASS/FAIL.

## Delivered behavior

| Area | Delivered behavior |
|---|---|
| shared compiler | One strict Simulator/Replay/Serial configuration produces the request, service factory, output slot, and visible review lines used by CLI or Dashboard |
| beginner wizard | Six immutable steps with what/why/confirm guidance, typed field conversion, bounded values, explicit transitions, and stale-review invalidation |
| reviewed Run | The worker accepts the exact reviewed request; worker start precedes the UI RUN transition so a rejected start cannot trap the wizard |
| Simulator | Default source; deterministic read/DC/hysteresis path; always visible `SYNTHETIC` limitation |
| CSV Replay | Full dataset is loaded and validated during Review, before worker start; the immutable dataset is bound to the reviewed job |
| Serial | Exact port/profile/channel/bounds plus receive-only confirmation; discovery enumerates only; port construction/open is deferred until Run |
| cancellation | Cooperative cancellation reaches `CANCELLED`, runs cleanup, and cannot expose an analysis export |
| result/export | Finalized report view and points are copied without recalculation; JSON/CSV writes are create-new and refuse overwrite |
| Tk boundary | Widgets render state and emit callbacks only; Tk remains a lazy explicit import and no network listener is created |

## Executed verification

| Gate | Actual result |
|---|---|
| Step 6 focused tests | PASS — 181 tests |
| Architecture and composite workflow gates | PASS — 19 tests |
| Full pytest suite | PASS — 2,131 tests |
| Statement coverage | PASS — 11,219/11,219 statements, 100% |
| Extra branch diagnostic | PASS at the recorded non-blocking threshold — 99.91%; 14 partial branches remain in older modules |
| New Step 6 workflow/Dashboard module branch coverage | PASS — 100% |
| Ruff | PASS — full rule check; all 20 Step 6 Python files already formatted |
| mypy | PASS — 184 source/tool/test files |
| Phase 1–4 compatibility | PASS — retained in the full suite |
| Isolated sdist/wheel build | PASS — version `0.1.0.dev0` |
| Repository-external base-wheel install | PASS |
| Installed base import | PASS — neither `tkinter` nor `serial` loaded |
| Installed CLI smoke | PASS — 24-point Simulator DC, `SYNTHETIC`, engineering `PASS`, `NO_PERFORMANCE_VALIDATION` |
| Installed real Windows Tk smoke | PASS — default window rendered and auto-closed safely |
| Physical COM/MSP430/instrument/AFE test | NOT RUN |

The formal coverage gate remains statement coverage, as in prior checkpoints.
The additional branch run is reported separately rather than being rounded to
100%. All new Step 6 workflow and Dashboard modules had no missing branch; the
14 partial branches are tracked as TD-035 for later classification.

## Composite-chain evidence

### CLI and Dashboard equivalence

An integration test sent the same 24-point Simulator DC configuration and fixed
job identity through both entry points. After removing only the two expected
runtime timestamps, the parsed `result-export.v1` documents were exactly equal.
This checks the complete chain, not just matching status text.

### Replay preflight

A missing Replay file was rejected during Review. The worker remained `IDLE`,
Run stayed unavailable, and no adapter or external resource was started. This
keeps bad data errors separate from execution failures.

### Receive-only MSP430-shaped host path

A repository-owned encoded MSP430 TEL record was supplied by a memory backend
whose write operation raises immediately. Review caused zero opens. Run caused
one memory-backend open, one close, successful mapped evidence, and zero write
calls. This proves the reviewed application path has no application write use;
it is not a physical-port or firmware result.

### Cancellation and export boundary

An injected cooperative blocking service was cancelled through the Dashboard.
The service cleanup signal completed, the worker ended `CANCELLED`, and export
remained unavailable. A cancelled job was not converted into PASS.

### Widget and real-window evidence

The fake toolkit exercised each Step 6 callback and state render path. A separate
installed-package smoke created a real Windows Tk window with Simulator/AFE
defaults and safely auto-closed it. The real-window smoke did not automate every
interactive field or keyboard path; those broader usability checks remain Step
7 work.

## Build and external-install evidence

| Artifact | Size | SHA-256 |
|---|---:|---|
| `mixed_signal_afe_validation_platform-0.1.0.dev0-py3-none-any.whl` | 240,076 bytes | `a91b90a7a71876fb07dd4978945e9db0d736fd22b339fd7732b0ed993697b7fa` |
| `mixed_signal_afe_validation_platform-0.1.0.dev0.tar.gz` | 420,257 bytes | `a2531723dba196999cb7cb362a3fc315a8b2a548ba5e09153c2e8c5da56f1bc5` |

The wheel was installed without dependencies into a fresh virtual environment
outside the repository. Base-package import stayed headless. The installed CLI
then ran the formal product chain against deterministic synthetic observations,
and the installed Dashboard completed a real Tk startup/close lifecycle.
Generated archives and the temporary environment are local verification
artifacts, not committed release binaries.

## Safety and evidence boundary

- The MSP430 connected to the computer was not enumerated, opened, read, reset,
  flashed, written, or otherwise operated during Step 6.
- No physical COM port, AFE, ADC, DAC, comparator, breadboard, wiring, instrument,
  or laboratory resource was accessed.
- There is no Dashboard transmit control, command console, arbitrary serial
  escape hatch, or application-level write call.
- An OS serial driver may still alter control lines when a real port opens, so
  future physical operation requires a separate review and authorization.
- `SYNTHETIC`, `CSV_REPLAY`, and memory `HOST_TEST` evidence cannot validate
  physical gain, offset, saturation, threshold, bandwidth, accuracy, or safety.
- The earlier Phase 4 five-frame `BENCH_CONTROLLER` result remains a separate
  narrow compatibility record and was not repeated or broadened.

## Remaining work and next gate

Step 6 does not provide the one-command reproducible portfolio demo, full
performance/accessibility/privacy acceptance, a release compatibility freeze,
CI, v1.0, real COM worker reliability, or physical AFE validation.

The next checkpoint is Software Phase 5 Step 7 only: build the deterministic
installed-package demo and test bounded data volume, keyboard/accessibility
behavior, scaling, path/Unicode handling, privacy, no-network operation, and
reproducible artifacts. It requires no physical hardware by default.
