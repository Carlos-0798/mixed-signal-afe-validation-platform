# Product layer contracts, CLI foundation, and job worker

**Implemented:** Software Phase 5 Steps 1–2, 2026-08-31<br>
**Evidence:** HOST_TEST and repository-external package installation<br>
**Hardware claim:** none

## Why this layer exists

`analog_validation` is the engineering core: it owns measurements, protocols,
adapters, analysis, criteria, and result meaning. `analog_validation_app` is the
product-facing layer: it translates a user's request into a controlled product
operation and translates expected failures into understandable guidance.

Keeping these responsibilities separate matters because a CLI or future GUI
should never become a second implementation of CRC, gain fitting, saturation
exclusion, or hysteresis math. There must be one engineering truth, with multiple
replaceable user interfaces above it.

```text
user / future Dashboard
          |
          v
analog-validation CLI
          |
          v
analog_validation_app     request, catalog, issue, worker, future services
          |
          v
analog_validation         protocols, adapters, analysis, results
```

The dependency is one-way. The core and optional pyserial backend may not import
the product layer. Architecture tests reject copied protocol or analysis
implementations in `analog_validation_app`; the Step 2 worker additionally may
not import adapters, profiles, serial code, analysis, exports, or GUI modules.

## Versioned product contracts

| Contract | Purpose | Important safety rule |
|---|---|---|
| `product-job.v1` | Immutable user job intent | `allow_output` must be `false`; profile name and version are explicit |
| `product-result.v1` | Immutable terminal product state | Source and evidence must agree; limitations are mandatory and bounded |
| `product-job-event.v1` | Immutable worker state/progress event | Index is positive and monotonic; text and queue are bounded; only failures carry a safe issue |
| `product-catalog.v1` | Reviewed sources and profiles | Lookup is exact; an unknown profile is rejected rather than guessed |
| `user-issue.v1` | Stable user-facing failure explanation | Expected errors map by type; unexpected internal details are not exposed |
| `product-cli-output.v1` | Deterministic machine-readable CLI output | JSON identifies schema and software version; hardware claim is explicitly `NONE` where applicable |

A product result is an engineering conclusion only when its finalized core
outcome is `PASS` or `FAIL`. `CANCELLED`, `INCOMPLETE`, `UNSUPPORTED`, and `ERROR`
cannot be displayed as successful validation.

## Worker lifecycle and ownership

`ProductJobWorker` is generic orchestration shared by the future CLI and
Dashboard. It does not know how to parse a profile, fit a line, open a serial
port, or draw a widget. A caller injects a `ProductJobService` factory; the
worker thread creates exactly one service, runs it, and calls `cleanup()` on
every path after creation.

```text
IDLE -> STARTING -> RUNNING -> SUCCEEDED
                    |  |        FAILED
                    |  +-----> CANCELLED
                    v
                CANCELLING
```

The diagram is a simplified lifecycle: factory, run, contract, or cleanup
failures end in `FAILED`; a cancellation request during startup or running ends
in `CANCELLED` after cleanup. Only one active job may exist. A second `start()`
is rejected instead of silently replacing the owner.

Cancellation is cooperative. The worker sets a thread-safe token, and a service
checks it at safe finite checkpoints. Python cannot safely kill an arbitrary
thread while it owns a file, adapter, or COM handle, so `join()` and `close()`
have explicit upper bounds and report timeout rather than pretending cleanup
happened. The non-daemon worker thread also prevents process exit from silently
abandoning a live resource owner.

Events use a bounded FIFO snapshot. When a slow future UI falls behind, the
oldest event is dropped and a cumulative dropped count is retained; memory does
not grow without limit. Event indexes remain globally increasing, so consumers
can detect a missed update.

Worker state and engineering outcome are deliberately separate:

- `SUCCEEDED` means orchestration ended normally; inspect the result, which may
  still be `INCOMPLETE` or `UNSUPPORTED`;
- a cancellation observed before terminal publication cannot produce PASS;
- a cleanup failure overrides apparent success and produces `FAILED`/`ERROR`;
- expected errors become bounded `UserIssue` guidance, while detailed exception
  text stays in the developer-only diagnostic field.

## Reviewed catalog

| Source | Evidence allowed by the contract | Jobs declared in Step 1 | Notes |
|---|---|---|---|
| `SIMULATOR` | `SYNTHETIC` | read, DC analysis, hysteresis analysis | Default; never a physical measurement |
| `CSV_REPLAY` | `CSV_REPLAY` | read, DC analysis, hysteresis analysis | Local replay; preserves lineage |
| `SERIAL_READ_ONLY` | `HOST_TEST` or `BENCH_CONTROLLER` | read only | Requires optional serial extra; exposes no product write command |

Two exact profile identities are reviewed:

- `afe/1` supports Simulator, CSV Replay, and receive-only serial sources.
- `msp430-equipment-health/1` is an independent peer-product telemetry profile
  and supports receive-only serial source only.

Catalog support states a software compatibility boundary. It does not prove that
a physical AFE, MSP430 firmware image, sensor, fan, wiring, or instrument works.

## Current CLI

After installation:

```powershell
analog-validation --help
analog-validation version
analog-validation version --json
analog-validation profiles
analog-validation profiles --json
python -m analog_validation_app profiles
```

The current CLI deliberately exposes only product identity and reviewed
profiles. It does not yet run Simulator, replay, analysis, report, Dashboard, or
serial jobs. Step 2 supplies the reusable worker, but concrete services and
test-running commands belong to Step 3.

For an unknown command the CLI exits with code `2`, writes no result to stdout,
and explains:

1. what happened;
2. a possible cause;
3. a safe next step.

The default path does not print a Python traceback. This makes expected mistakes
actionable while keeping unexpected internal details out of normal user output.

## Installation and evidence boundary

The current wheel was installed in a fresh directory outside the repository with
`--no-deps`. `help`, `version`, `profiles`, and the module entry point ran while
`pyserial` was absent; neither `serial`, `analog_validation_pyserial`, nor
`tkinter` was imported. An installed in-memory service also ran through the
worker, published progress, cleaned up, reached `SUCCEEDED`, and left no live
product worker thread. No COM port was enumerated or opened, and no window was
created.

This proves packaging, dependency isolation, deterministic CLI behavior, and
host-side product-contract logic. It does not add hardware evidence. The earlier
receive-only MSP430 UART capture remains a separate, narrowly scoped
`BENCH_CONTROLLER` result.

## Next checkpoint

Software Phase 5 Step 3 will implement concrete application services and stable
test-running CLI workflows above this worker. Simulator and CSV Replay remain
the default no-hardware paths; serial tests use an injected memory backend and
must not open a real port without a separate explicit owner-approved action.
