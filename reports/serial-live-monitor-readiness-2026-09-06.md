# Receive-only Serial Live Monitor — Local Readiness Record

**Date:** 2026-09-06

**Scope:** local host software only

**Evidence:** `HOST_TEST`, `SYNTHETIC`, and `CSV_REPLAY`

**Hardware claim:** `NO_NEW_HARDWARE_VALIDATION`

**Repository state:** uncommitted extension on local baseline `bf8c4c6`

## Outcome

The finite `LIVE_MONITOR` product workflow now supports the explicit
`SERIAL_READ_ONLY` source through the same reviewed compiler, single-owner
worker, CLI, and Dashboard used by the offline sources. The implementation is
ready for code review and commit preparation. It is not evidence that any real
controller, serial link, AFE, wiring, or measurement path works.

## Product behavior implemented

- The source catalog offers bounded `READ` and `LIVE_MONITOR` for
  `SERIAL_READ_ONLY`.
- The CLI exposes `analog-validation serial monitor` and requires the exact
  profile, port, primary channel, and `--confirm-read-only` acknowledgement.
- The Dashboard enables the relevant serial controls for live monitoring and
  uses finite Serial defaults: 20 cycles, 20 ms cadence, 50 ms read timeout,
  four polls, and one primary trace.
- Selecting the MSP430 Equipment Health v1 profile in the Dashboard pre-fills
  `msp430.health.bus_voltage` in mV as an editable starting point.
- Secondary analog and state traces are opt-in. Adapter capability preflight
  must advertise every requested channel and operation before telemetry is
  acquired.
- The review page displays cadence time, conservative worst-case receive-wait
  time, and their combined bound.
- The worker join budget is derived from the same reviewed bound.

## Safety and resource bounds

For a Serial live job, the software computes:

```text
cadence = (cycles - 1) * sample_interval
receive_wait = (1 + cycles * enabled_channels) * max_polls * read_timeout
combined_bound = cadence + receive_wait
```

The extra operation conservatively covers capability acquisition. A request is
rejected before Run when the combined bound exceeds 55 seconds. The adapter has
no application-level write surface. Automatic reconnect remains disabled;
timeouts and disconnects fail closed. Cancellation is cooperative and the
owned serial session is closed during cleanup.

This is a software upper-bound calculation, not a physical timing guarantee.

## Verification executed

| Gate | Result |
|---|---|
| Serial live focused product/CLI/Dashboard/adapter/public-contract regression | 304 passed before final cross-suite additions |
| Final full pytest and coverage gate | 2,485 passed; 13,881/13,881 package statements; 100% statement coverage |
| Ruff | Passed |
| mypy | Passed across 218 source files |
| Dependency consistency | `pip check` passed |
| Product-quality acceptance | 15/15 passed |
| Distribution build | Wheel and sdist built successfully |
| Fresh installed-package smoke | Version `0.1.0b1` and `serial monitor --help` succeeded from a repository-external virtual environment |

The memory-backed Serial cases cover:

- successful finite AFE primary-channel acquisition;
- successful finite MSP430 bus-voltage acquisition;
- damaged CRC rejection followed by recovery within the reviewed poll budget;
- timeout and disconnect failure;
- cancellation and deterministic port cleanup;
- missing optional-channel capability returning `UNSUPPORTED` with zero
  measurements;
- deferred construction so Review opens no backend;
- one open/one close on completed runs; and
- zero application write calls.

The latest bounded product-quality run processed 10,000 synthetic live points
in 0.182947 seconds with 1.355 MiB peak traced memory, retained 2,048 points, and
accounted for all 7,952 evictions. A 10,000-record Replay used 13.102 MiB peak
traced memory and completed in 0.514069 seconds. These host timings are not
real-time or hardware-performance claims.

## Explicitly not verified

- No COM port was enumerated or opened in this increment.
- No MSP430 or other controller was read, reset, flashed, or written.
- No physical AFE, ADC/DAC, sensor, signal source, oscilloscope, wiring, or
  protection circuit was measured.
- Real device identity, baud compatibility, sustained data rate, OS-driver
  control-line behavior, cable removal, reconnection, and 30-minute/2-hour soak
  behavior remain unverified.
- At this initial Serial-live checkpoint, the default AFE v1 projection exposed
  only `afe.chN.input`; an unadvertised output request returned `UNSUPPORTED`
  before telemetry. A later local device-contract increment added an optional
  exact-ID/full-ADC observation map without changing this default. See
  `serial-device-contract-readiness-2026-09-06.md` for the newer evidence.

## Next controlled step

After the combined feature stage is ready for submission, run the formal
commit-bound release-candidate and release-audit gates. A later, separately
authorized hardware step may then perform a short passive receive-only check
against an exact known controller/profile before any soak testing. The
subsequent local device-contract checkpoint uses an explicit versioned mapping
rather than an undocumented alias. Real-device closure remains separately
authorized and unverified.
