# Bounded Live Monitoring

**Implemented:** post-beta local product increment, 2026-09-05  
**Schema:** `live-monitor.v1`  
**Current sources:** deterministic Simulator and strict CSV Replay  
**Evidence:** `SYNTHETIC`, `CSV_REPLAY`, and `HOST_TEST` only  
**Physical AFE claim:** none

## What this workflow does

Live monitoring shows recently acquired values while one finite read job is
running. It is useful for checking changing input, output, and boolean state
channels without turning the Dashboard into an unbounded data logger.

The current workflow deliberately has an end. The user chooses a finite cycle
count and interval before Review. The product then:

1. validates the exact source, profile, channels, units, cycle count, interval,
   time window, and memory bound;
2. creates one reviewed immutable `LIVE_MONITOR` job;
3. reads each enabled channel once per cycle through the public
   `DeviceAdapter` contract;
4. publishes immutable points into a bounded in-memory ring buffer;
5. copies a trailing time window to the Dashboard or CLI presentation; and
6. closes the adapter before publishing the terminal product result.

This is live presentation, not an engineering analysis. A successfully
completed monitor job reports product status `COMPLETED` and engineering
outcome `none`; it never invents a PASS or FAIL.

The enabled channels are read sequentially inside each logical cycle. The
cycle groups values for presentation, but it is not a simultaneous-sampling or
time-alignment guarantee. Phase, inter-channel skew, and synchronization remain
outside the evidence supported by this workflow.

## Why the implementation is bounded

An application that stores every point forever eventually consumes all
available memory. A continuously updating UI can also become slower if it
redraws the complete history after every sample. The current design separates
three limits:

| Limit | Current bound | Purpose |
|---|---:|---|
| Finite requested duration | 55 seconds | Keeps the interactive CLI/worker join bounded |
| Total measurements per job | 10,000 | Prevents a form entry from creating an unbounded acquisition |
| Retained live points | 1–10,000; default 2,048 | Caps in-memory presentation state |
| Visible trailing window | 0.1–3,600 seconds | Changes only what is drawn, not what was acquired |
| Interval between cycles | 0–60 seconds | Rejects invalid or unexpectedly long waits |

When the ring buffer is full, the oldest retained point is evicted and an
`evicted_points` counter increases. This is not the same as a transport failure
or a dropped worker event:

- **buffer eviction** is expected memory management after a valid point was
  acquired;
- **dropped worker events** mean the bounded UI event queue replaced an older
  progress notification;
- **invalid/suspect measurements** are measurement-quality states and remain
  counted separately.

Keeping those meanings separate prevents a normal memory policy from being
misreported as missing physical data.

## Pause and resume

Pause is cooperative. The worker stops only at a safe checkpoint between
bounded read operations. It does not terminate a Python thread while that
thread may own an adapter or file. Resume wakes the same reviewed job; it does
not construct a new source or silently restart the cycle count.

The Dashboard exposes separate **Pause live view** and **Resume live view**
buttons. Their enabled states are derived from the immutable live panel:

- running: Pause enabled, Resume disabled;
- paused: Pause disabled, Resume enabled;
- idle or finished: both disabled.

Changing the visible time window is presentation-only. It does not alter the
sample interval, measurements, evidence, or terminal result.

## CLI examples

Run a finite six-cycle, three-channel synthetic monitor:

```powershell
analog-validation simulate monitor `
  --cycles 6 `
  --sample-interval 0.1 `
  --time-window 1 `
  --max-buffer-points 12 `
  --json
```

Use only the primary analog trace:

```powershell
analog-validation simulate monitor `
  --cycles 10 `
  --no-secondary `
  --no-state
```

Replay mode uses the same channel and bound contract:

```powershell
analog-validation replay monitor `
  --input .\telemetry.csv `
  --cycles 10 `
  --sample-interval 0 `
  --time-window 5 `
  --max-buffer-points 30 `
  --json
```

The JSON document contains the terminal worker/product state plus a
`live_monitor` snapshot with counts and retained points. It has no finalized
analysis bundle, criteria, or hardware-validation claim.

## Dashboard workflow

Choose **Simulator** or **CSV Replay**, then choose **Live monitor**. Configure
the enabled channels, cycle count, interval, time window, and maximum retained
points. Review shows the calculated finite duration and explicitly states that
no background acquisition continues after the job.

During Run, the Results tab shows:

- current running/paused/finished state;
- acquired, retained, visible, evicted, valid, suspect, and invalid counts;
- a bounded multi-channel chart with elapsed time on the horizontal axis;
- pause/resume controls; and
- a presentation-only trailing-window selector.

The chart copies immutable measurements. It does not fit, filter, resample, or
change their quality status. Boolean channels are drawn as high/low state
traces; analog channels keep their declared unit in the legend.

## Current safety and evidence boundary

The current product catalog enables `LIVE_MONITOR` only for Simulator and CSV
Replay. `SERIAL_READ_ONLY` still exposes only the existing bounded `READ` job.
This prevents a new real-port behavior from being enabled merely because the UI
can draw a curve.

No serial port, MSP430, signal generator, oscilloscope, or physical AFE was used
to implement or verify this increment. Simulator timing is host scheduling, not
hard real-time behavior. CSV Replay timing does not prove how the original data
was acquired.

## Before real-device monitoring can be enabled

Real-device closure needs a separately reviewed adapter and test procedure:

1. explicit device/profile identity and channel/unit mapping;
2. receive-only control-line and port-open risk review;
3. disconnect, reconnect, timeout, cancellation, and cleanup tests;
4. a measured data-rate budget and dropped-record accounting;
5. 30-minute and 2-hour soak tests with memory and CPU observations;
6. evidence labels that distinguish controller telemetry from calibrated bench
   measurements; and
7. user-approved physical wiring and instrument access.

Only that future evidence may support real-device reliability or physical AFE
claims.
