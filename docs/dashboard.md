# Local Dashboard

**Implemented:** Software Phase 5 Step 5, 2026-08-31
**State schema:** `dashboard-state.v1`
**Session schema:** `dashboard-session.v1`
**Default source:** Simulator
**Hardware claim:** `NO_NEW_HARDWARE_VALIDATION`

## What is available now

The local Dashboard is a real, launchable Tkinter/ttk desktop shell for Analog
Validation Studio. It is intentionally headless-first: the state, actions,
presenter, worker polling, cancellation, and close behavior can all be tested
without creating a window. Tk is imported only after the user explicitly runs:

```powershell
analog-validation dashboard
```

The Step 5 window is a safe product shell, not yet the Step 6 test wizard. It
shows the reviewed default Simulator/AFE selection and keeps Run disabled. It
does not open a serial port, read a CSV file, create an adapter, publish a file,
start a network listener, or calculate an engineering result.

## Why the layers are separate

```text
immutable DashboardState
          ^
          |
DashboardPresenter  <- copies catalog / worker event / result / report view
          ^
          |
DashboardController <- polls worker, requests cancel, performs bounded close
          ^
          |
Tk/ttk widgets       <- render text/table and emit callbacks only
          ^
          |
Dashboard app        <- lazy Tk import, main-thread polling, window lifecycle
```

This prevents a button or plotting widget from becoming a second implementation
of profile parsing, linear fitting, hysteresis thresholds, PASS/FAIL, or device
control. The engineering core remains the only owner of those decisions.

## Six visible regions

1. **Source / Profile** — exact source and profile identity, connection text,
   and declared evidence class.
2. **Configuration / Safe review** — selected job and the current read-only
   boundary. Step 5 explicitly says that execution is not wired yet.
3. **Progress** — worker state, text message, count/total, retained event count,
   dropped-event count, and a safe Cancel button.
4. **Plot / finalized point table** — copied report points and dispositions. It
   does not fit, filter, or recalculate data.
5. **Result / Evidence** — product status, engineering outcome, evidence source,
   limitations, not-verified statements, and structured what/why/next-step
   issues.
6. **Artifacts** — filename, media type, size, and hash. Absolute local paths are
   not copied into the default state.

No meaning is conveyed by color alone. `SYNTHETIC`, `CSV_REPLAY`, `HOST_TEST`,
`BENCH_CONTROLLER`, worker state, outcome, and not-verified boundaries all have
visible text.

## Thread and close safety

- The presenter records its creating thread and rejects state updates from any
  other thread.
- The existing product worker retains exclusive ownership of a job and its
  resources.
- Tk's owner thread polls the worker's bounded immutable event queue; a worker
  thread never calls a widget.
- Cancel is cooperative and moves through the worker's existing cancellation
  token and cleanup path.
- Window close calls the worker's bounded `close()`, which requests cancel and
  joins before the window is destroyed.
- A close timeout remains visible as a structured issue; the UI does not claim
  safe closure or silently abandon the owned job.

An integration test uses the real `ProductJobWorker` with a cooperative blocking
service and confirms window-close controller behavior reaches `CANCELLED`, joins,
and runs cleanup. A separate Windows smoke created the real Tk window, displayed
the default Simulator/AFE state, and auto-closed safely while pyserial remained
unloaded.

## Current limitations and Step 6 boundary

- There are no editable workflow fields or Run action yet.
- The six-step beginner path — source, test, configuration, safety review, run,
  export — is Step 6.
- CSV validation and receive-only serial selections will be connected in Step 6.
- Real serial use will still require an exact port/profile, bounded records/time,
  and an explicit read-only confirmation.
- The Dashboard does not expand the earlier narrow MSP430 UART compatibility
  evidence and does not validate any physical AFE behavior.

See the [product layer](product-layer.md), [CLI guide](product-cli.md),
[human-report guide](human-reports.md), and
[Step 5 evidence report](../reports/software-phase5-step5.md).
