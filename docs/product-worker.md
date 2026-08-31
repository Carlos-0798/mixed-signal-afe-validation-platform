# Product job worker

**Implemented:** Software Phase 5 Step 2, 2026-08-31<br>
**Evidence:** HOST_TEST and repository-external in-memory smoke<br>
**Hardware claim:** none

## What problem it solves

A validation job may take seconds or minutes. If the CLI or future Dashboard
runs that work directly on its main thread, the interface can freeze and the
user cannot cancel safely. If several parts of the program open the same adapter,
it becomes unclear who must close it after an error.

`ProductJobWorker` solves the orchestration problem: one owner runs one job on
one background thread, publishes bounded progress, accepts a cooperative cancel
request, captures the terminal result or safe issue, and always asks the owned
service to clean up. It is infrastructure, not a measurement algorithm.

## Public contracts

| Contract | Meaning |
|---|---|
| `ProductJobServiceFactory(request)` | Creates one resource-owning service inside the worker thread |
| `ProductJobService.run(...)` | Performs one job and returns one validated `ProductJobResult` |
| `ProductJobService.cleanup()` | Releases every resource the service acquired |
| `ProductCancellationToken` | Read-only cancellation signal available to the service |
| `ProductJobEvent` | Immutable state/progress/issue record for polling consumers |
| `ProductJobWorker` | Owns lifecycle, thread, queue, result, issue, and cleanup policy |

The service factory must release any partially created resource itself if it
raises before returning a service. Once it returns, cleanup ownership transfers
to the worker.

## State and result are different

Worker states are `IDLE`, `STARTING`, `RUNNING`, `CANCELLING`, `SUCCEEDED`,
`FAILED`, and `CANCELLED`.

`SUCCEEDED` does not mean the circuit passed. It means the software operation
ended without worker or cleanup failure. The returned product result may be:

- `COMPLETED` with engineering outcome `PASS` or `FAIL`;
- `INCOMPLETE` when evidence is insufficient;
- `UNSUPPORTED` when the selected source lacks a required capability;
- `CANCELLED` or `ERROR` on interrupted or failed work.

Future presenters must read both contracts. Showing PASS from worker state alone
would be a product defect.

## Why cancellation is cooperative

Python threads cannot be force-killed safely. Stopping a thread between “device
write” and “safe shutdown,” or while a file is being published, could leave a
resource in an unknown state. Instead:

1. the owner calls `cancel()`;
2. the token becomes set immediately;
3. the service checks or waits on the token at finite safe checkpoints;
4. the worker runs cleanup;
5. the owner uses bounded `join()`/`close()` to confirm termination.

A non-cooperative service can cause a join timeout, which is reported explicitly.
The worker does not claim that a timed-out thread or resource was cleaned.

## Bounded event queue

Each event has a UTC time, job ID, increasing index, state, bounded printable
message, optional progress, and an optional safe issue only for `FAILED`.

The queue defaults to 256 events and cannot exceed 4,096. If full, it discards
the oldest event and increments `dropped_event_count`. This is intentional
backpressure for a slow CLI/GUI poller and prevents unbounded memory growth.

## Cleanup and failure precedence

Cleanup runs after normal completion, cancellation, expected service errors,
unexpected errors, and invalid service results. If cleanup itself fails, that
failure overrides apparent PASS or cancellation and the published terminal state
is `FAILED`; an existing result is converted to `ERROR`. This fail-closed rule
prevents “test passed” from hiding a leaked or unknown resource state.

## Verified host behavior

The Step 2 suite covers:

- normal start, progress, result, cleanup, and thread termination;
- duplicate start and closed-worker rejection;
- cancellation during factory startup, service run, token wait, and completion;
- PASS-to-cancel race downgrading;
- factory/run/cleanup expected and unexpected failures;
- bad service/result/request/progress contracts;
- bounded queue eviction with monotonic event indexes;
- bounded join/close timeout and later recovery;
- context-manager cleanup, self-join rejection, and thread-start failure;
- defensive stale/missing internal state failing closed;
- dependency checks proving no direct device/analysis/serial/GUI imports.

These are deterministic host tests using injected services. No COM port,
MSP430, AFE, instrument, Tk window, or physical wiring was used.

## Next use

Step 3 will inject real application services for Simulator and CSV Replay and
drive the same worker from stable CLI commands. Later, the Dashboard main thread
will poll the same immutable events; widgets will never call adapters directly.

See the [product layer](product-layer.md),
[Phase 5 plan](SOFTWARE_PHASE_5_PLAN.md), and
[Step 2 evidence report](../reports/software-phase5-step2.md).
