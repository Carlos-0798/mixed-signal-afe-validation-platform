# Bounded Live Monitoring

**Implemented:** post-beta local product increment, 2026-09-05  
**Schema:** `live-monitor.v1`  
**Current sources:** deterministic Simulator, strict CSV Replay, and explicit receive-only Serial
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
| Combined Serial runtime budget | 55 seconds | Includes cadence plus the worst-case capability/read poll budget |
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

Run a finite, primary-channel-only serial monitor after reviewing the exact
port, profile, and required primary channel:

```powershell
analog-validation serial monitor `
  --port COM4 `
  --profile msp430-equipment-health `
  --profile-version 1 `
  --primary-channel msp430.health.bus_voltage `
  --unit mV `
  --cycles 20 `
  --sample-interval 0.02 `
  --read-timeout 0.05 `
  --max-polls 4 `
  --confirm-read-only `
  --json
```

This is a syntax example, not permission to open `COM4`. Confirm the actual
port, wiring, voltage domain, firmware/profile, and device ownership first.
Serial monitor defaults to one primary channel. Secondary analog or boolean
state channels are opt-in and must be declared by the selected device profile.

An AFE that reports two native ADC channels can expose an input/output pair only
through the explicit product contract below:

```powershell
analog-validation serial monitor `
  --port COM4 `
  --profile afe `
  --profile-version 1 `
  --primary-channel afe.ch0.input `
  --secondary-channel afe.ch0.output `
  --secondary `
  --no-state `
  --unit mV `
  --cycles 20 `
  --sample-interval 0.02 `
  --read-timeout 0.05 `
  --max-polls 4 `
  --expected-device-id afe-controller-01 `
  --afe-adc-alias adc0=afe.ch0.input `
  --afe-adc-alias adc1=afe.ch0.output `
  --confirm-read-only `
  --json
```

The example is intentionally strict. The reported capability `device_id` must
equal `afe-controller-01`, and the aliases must cover every ADC channel in the
completed capability response exactly once. An identity mismatch, missing
alias, extra alias, repeated source, or repeated destination fails before the
first telemetry measurement is read. Without aliases, the established AFE v1
projection remains unchanged: `adcN` is interpreted as `afe.chN.input`.

`expected_device_id` is a protocol/profile label, not authentication and not a
verified USB or factory serial number. Likewise, an alias records the reviewed
software meaning of a native channel; it cannot prove that the physical wire is
connected to the claimed signal. The MSP430 profile uses a static capability
snapshot, so pinning its current `device_id` checks the selected software
contract rather than querying a firmware-unique identity.

The JSON document contains the terminal worker/product state plus a
`live_monitor` snapshot with counts and retained points. It has no finalized
analysis bundle, criteria, or hardware-validation claim.

## Dashboard workflow

Choose **Simulator**, **CSV Replay**, or **Serial (read-only)**, then choose
**Live monitor**. Configure
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

For Serial, Review also shows the conservative receive-wait budget and the
combined cadence-plus-receive bound. Selecting a source never opens a port.
The port is constructed and opened only after explicit Review, Run, and the
receive-only confirmation.

Review also shows an optional expected capability ID and any AFE ADC aliases.
After a successful run, the CLI JSON and Dashboard observation summary display
the actual capability ID/profile that the adapter accepted. These values are
protocol evidence only and are never presented as proof of physical wiring or
device authenticity.

## Current safety and evidence boundary

The product catalog now exposes `LIVE_MONITOR` for `SERIAL_READ_ONLY`, but only
through the same explicit port/profile selection and receive-only confirmation
used by bounded `READ`. The software rejects a configuration when:

- cadence alone exceeds 55 seconds;
- cycles multiplied by enabled channels exceed 10,000 measurements; or
- cadence plus the conservative worst-case serial poll budget exceeds 55
  seconds.

The budget assumes one bounded capability operation plus one bounded receive
operation per requested measurement. It is deliberately conservative and is
not a real-time or throughput guarantee. Automatic reconnect remains disabled;
a disconnect fails closed and requires a new reviewed run.

No real serial port, MSP430, signal generator, oscilloscope, or physical AFE was
used to implement or verify this increment. Host tests used an in-memory serial
backend and covered successful records, bad CRC recovery within the poll bound,
timeout, disconnect, cancellation, cleanup, and zero application writes.
Simulator timing is host scheduling, not hard real-time behavior. CSV Replay
timing does not prove how the original data was acquired.

## Before real-device monitoring can support a reliability claim

The receive-only software path is enabled, but real-device reliability still
needs an owner-approved test procedure and physical evidence:

1. explicit device/profile identity and channel/unit mapping;
2. receive-only control-line and port-open risk review for the exact adapter;
3. physical disconnect behavior and a deliberate reconnect policy review;
4. a measured data-rate budget, timing observations, and dropped-record
   accounting;
5. 30-minute and 2-hour soak tests with memory and CPU observations;
6. evidence labels that distinguish controller telemetry from calibrated bench
   measurements; and
7. user-approved physical wiring and instrument access.

Only that future evidence may support real-device reliability or physical AFE
claims.
