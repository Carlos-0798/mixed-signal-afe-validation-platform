# Software Phase 5 Step 2 Report

**Date:** 2026-08-31<br>
**Milestone:** bounded single-owner cancellable product job worker<br>
**Evidence class:** HOST_TEST and repository-external in-memory package smoke<br>
**Hardware/serial/display operation:** none<br>
**Verified AFE hardware performance claims:** 0

**Implementation commit:**
`cbca879547957e399f73e54ff7bf26250c15e687`

## Outcome

Software Phase 5 Step 2 is complete; Phase 5 implementation is now 2 of 8
checkpoints. The product layer can safely own one long-running job, publish
bounded immutable progress, request cooperative cancellation, capture a result
or safe issue, and deterministically clean the injected service.

This checkpoint adds generic orchestration only. It does not yet connect a CLI
command to Simulator, CSV Replay, analysis, report generation, or a real serial
port. It neither reads nor validates the connected MSP430 and adds no AFE or
other physical evidence.

## Delivered contracts and behavior

| Component | Delivered behavior |
|---|---|
| `product-job-event.v1` | Immutable UTC event with positive index, bounded printable message, RUNNING-only progress, and FAILED-only safe issue |
| `ProductWorkerState` | Explicit `IDLE/STARTING/RUNNING/CANCELLING/SUCCEEDED/FAILED/CANCELLED` lifecycle |
| `ProductCancellationToken` | Thread-safe read-only cancellation flag, bounded wait, and typed cooperative stop checkpoint |
| `ProductJobService` | Injected `run`/`cleanup` contract; device and workflow logic remain outside the worker |
| `ProductJobWorker` | One active job, non-daemon owner thread, bounded FIFO events, result/issue capture, finite join/close, context-manager shutdown |
| failure policy | Factory/run/contract failures become stable issues; cleanup failure overrides apparent success/cancel; developer details remain separate |
| architecture boundary | Worker cannot directly import adapters, profiles, protocol, analysis, exports, serial backend, or Tkinter |

The worker creates the service inside its own thread. Once a service is returned,
that thread owns both execution and cleanup. If a factory raises before returning,
the factory itself remains responsible for releasing anything it only partially
constructed; this is an explicit factory contract rather than hidden worker
guesswork.

## Cancellation and terminal semantics

Cancellation is cooperative because forcibly terminating a Python thread can
interrupt file publication, adapter lifecycle, or a future safe-shutdown
sequence at an unsafe point. `cancel()` sets a token; the service must observe it
at bounded checkpoints. `join()` and `close()` have finite validated timeouts and
report a typed timeout if a non-cooperative service remains alive.

Worker state is not an engineering conclusion. `SUCCEEDED` means orchestration
ended normally; the product result may still be `INCOMPLETE` or `UNSUPPORTED`.
A cancellation observed before terminal publication converts an apparent PASS
to `CANCELLED/ABORTED`. A cleanup failure converts an existing result to
`ERROR` and publishes worker `FAILED`, so resource uncertainty cannot be hidden
behind a green result.

## Executed verification

| Gate | Actual result |
|---|---|
| Dedicated worker tests | PASS — 56 tests |
| Step 2 net suite increase | PASS — 80 tests, including events and architecture |
| Phase 5 focused product tests | PASS — 207 tests |
| Product package coverage | PASS — 773/773 statements, 100% |
| Full pytest suite | PASS — 1,725 tests |
| Formal + optional + product coverage | PASS — 8,098/8,098 statements, 100% |
| Phase 1–4 golden compatibility | PASS — unchanged within the full suite |
| Full-repository Ruff | PASS |
| mypy on `src`, `tools`, and `tests` | PASS — 149 files |
| Dependency consistency | PASS — no broken requirements |
| Patch whitespace | PASS |
| Isolated sdist/wheel build | PASS — `0.1.0.dev0` |
| Archive inspection | PASS — worker, tests/source metadata, `py.typed`, and one console entry point present |
| External base-wheel worker smoke | PASS — in-memory service progressed, cleaned up, reached `SUCCEEDED`, and left no live product thread |
| Optional import isolation | PASS — no `serial`, `analog_validation_pyserial`, or `tkinter` import |
| Documentation relative links | PASS — 105 Markdown files checked, zero missing relative targets |
| Physical port, UI window, or hardware test | NOT RUN |

The 100% figures are statement-coverage gates for the current Python packages.
They do not prove electrical safety, real-time behavior, OS-driver reliability,
physical disconnect recovery, or AFE performance.

## Fault and race coverage

Host tests exercise:

- normal startup/progress/result/cleanup on the same owned thread;
- a duplicate start while active and a start after close;
- cancellation during factory startup, run, token wait, and terminal race;
- a cancellation requested too late after terminal completion;
- expected and unexpected factory/run/cleanup failures;
- cleanup failure overriding PASS, cancellation, or another run error;
- invalid service objects, non-results, mismatched requests, and illegal progress;
- progress from the wrong thread, token, request, or lifecycle state;
- bounded queue eviction and globally monotonic event indexes;
- join/close timeout followed by later cooperative recovery;
- context-manager close, self-join/self-close rejection, and thread-start failure;
- defensive missing/stale internal state failing closed rather than fabricating a
  terminal success.

No Python worker can guarantee cleanup for code that never cooperates or a
factory that leaks a resource before returning. The explicit timeout and factory
contract make those limitations visible instead of silently claiming success.

## Build and external-install evidence

Final isolated artifacts:

| Artifact | Size | SHA-256 |
|---|---:|---|
| `mixed_signal_afe_validation_platform-0.1.0.dev0-py3-none-any.whl` | 173,678 bytes | `0CA1D15A4347B08F7B7FCE63CF2DCB2C98BB6752225F55F1A4C9692A2C4736E3` |
| `mixed_signal_afe_validation_platform-0.1.0.dev0.tar.gz` | 309,168 bytes | `ED735A8979A1A14E8ED6FB3517CF9C16CCD1390FE950DF1F2A5250D2E8DBBB48` |

The inspected wheel still exposes exactly one console entry point:

```text
analog-validation = analog_validation_app.cli:main
```

The final external environment was a clean short-path virtual environment
outside the repository. The wheel was installed with `--no-deps`. Its
in-memory worker smoke checked progress/event indexes, terminal state, cleanup,
and absence of remaining product-named threads. CLI help/version/profiles and
unknown-command behavior also passed. No COM enumeration, display, network, or
hardware access occurred.

Generated build artifacts and the external virtual environment are local
verification outputs, not committed release binaries.

## Safety and evidence boundary

- The worker has no hardware output method and product requests still require
  `allow_output=false`.
- It imports no profile parser, analysis formula, serial backend, or GUI widget.
- No COM port was discovered/opened and no application byte was sent.
- The connected MSP430 was deliberately not touched during this software-only
  checkpoint.
- The earlier five-record receive-only MSP430 HIL remains separate
  `BENCH_CONTROLLER` evidence and is not repeated or broadened here.
- Physical AFE construction, wiring, voltage limits, accuracy, frequency
  response, hysteresis, and reliability all remain unverified.

## Remaining work and next gate

Step 2 intentionally does not provide:

- concrete Simulator/CSV Replay/Serial product application services;
- CLI commands that execute a validation job;
- Ctrl+C subprocess wiring to the cancellation token;
- reports/charts or Dashboard presenter/widgets;
- long-duration, physical-disconnect, or real-port worker evidence.

The next checkpoint is Phase 5 Step 3 only: implement stable Simulator and CSV
Replay application services/CLI workflows above this worker, preserve read-only
serial boundaries, and freeze human/JSON output, stdout/stderr, exit codes, and
Ctrl+C behavior using host-side/in-memory tests.
