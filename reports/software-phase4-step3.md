# Software Phase 4 Step 3 — Driver-Neutral Serial Lifecycle and Raw Events

**Date:** 2026-08-30<br>
**Checkpoint:** 3 of 8<br>
**Implementation commit:** `362c82d5cf736e6d9726624536da2af09a14de13`<br>
**Evidence class:** HOST_TEST<br>
**Hardware used:** none<br>
**Serial ports opened:** none<br>
**pyserial required/installed by package:** no

## Outcome

Step 3 is complete. The formal package now defines a replaceable
`SerialBackend` port and a driver-neutral `SerialSession` for discovery, open,
bounded read, normal timeout, disconnect cleanup, finite per-incident reconnect,
and deterministic logical close. The session composes the Step 1 bounded LF
framer with a new bounded, memory-only raw-record event log, but deliberately
does not interpret AFE or MSP430 business fields.

All acceptance paths use a deterministic in-memory backend with scripted data
and failure injection. No COM port, MSP430 board, UART driver, command, firmware,
FRAM, external component, or physical signal was accessed.

## Implemented boundaries

### Replaceable serial port

`SerialBackend` defines four operations:

- discover a tuple of logical port identities;
- open with an immutable, fully validated settings object;
- read no more than the requested number of bytes within the requested timeout;
- close the underlying resource.

The formal core has no pyserial or OS-driver import. The test-only
`MemorySerialBackend` is packaged in the sdist for reproducible source tests but
is not included in the runtime wheel.

### Serial lifecycle

`SerialSession` enforces `CLOSED`/`OPEN` state and produces explicit `DATA`,
`TIMEOUT`, or `RECONNECTED` poll results. A timeout does not discard a partial
record. Disconnect does discard partial/overlong state before attempting at
most the configured 0–10 reconnects. A successful reconnect returns without a
second read so one public poll remains finite and old/new connections cannot
share a frame.

Backend read/contract/receive failures always clear the framer, attempt backend
cleanup, and leave logical state closed. Close is idempotent. Even when the
backend close operation fails, the session remains logically closed and raises
the stable `SerialCloseError` family.

### Raw-record provenance

Every complete bounded record enters `BoundedRawEventLog` as immutable
`PENDING_PROFILE` evidence with exact bytes, normalized UTC receive time,
logical port, explicit profile, and monotonic event ID. A future profile must
replace it explicitly with either:

- `PARSED`, including a bounded summary and optional `SequenceObservation`; or
- `REJECTED`, including a bounded type/message and no sequence advance.

The default log retains at most 1,024 events and 256 KiB. Hard ceilings are
10,000 events, 2 MiB total bytes, and 4,096 bytes per record. FIFO eviction
preserves dropped-event and dropped-byte counters. Raw data is memory-only and
is never persisted or uploaded automatically.

Overlong input is reported by the framer and discarded through LF. It is not
copied into the event log because doing so would defeat the raw-log byte bound.

### Error boundary

The new `analog_validation.transport` error families remain subclasses of
`AnalogValidationError` without changing the frozen Phase 1–3 top-level API.
Stable discovery/open/read/close/reconnect errors use exception chaining for
developer diagnostics. Backend timeout and disconnect are explicit control
signals; raw event validation, limit, and missing/evicted update failures have
their own typed family.

## Composite proof

The Step 3 integration test performs this host-only chain:

```text
scripted partial/coalesced bytes
    -> SerialSession bounded poll
    -> BoundedLineFramer complete records
    -> PENDING_PROFILE raw events
    -> neutral CRC envelope
    -> 16-bit SequenceTracker
    -> PARSED or REJECTED raw outcomes
```

Two valid records produce FIRST then GAP observations. One damaged CRC record
becomes `REJECTED` and does not advance sequence continuity. Exact bytes remain
available for all three outcomes.

## Executed verification

| Gate | Actual result |
|---|---|
| Pre-change full regression | PASS — 1,130 tests |
| Step 3 new tests | PASS — 88 |
| Settings, ports, lifecycle, timeout and failure injection | PASS |
| Disconnect/reset and 0/1/2-attempt reconnect cases | PASS |
| Partial/coalesced/overlong stream recovery | PASS |
| Raw state, eviction, counters, UTC and privacy limits | PASS |
| CRC envelope -> sequence -> raw outcome integration | PASS |
| Full pytest suite | PASS — 1,218 tests |
| Formal package statement coverage | PASS — 6,274/6,274, 100% |
| Step 3 formal package increase | PASS — 428/428 statements, 100% |
| New errors/events/serial modules | PASS — 425/425 statements, 100% |
| Frozen Phase 1–3 API and golden compatibility | PASS |
| Core standard-library dependency boundary | PASS |
| Full-repository Ruff | PASS |
| mypy on `src`, `dashboard`, `tools`, and `tests` | PASS — 119 files |
| Local dependency check | PASS — no broken requirements |
| Isolated sdist and wheel build | PASS — `0.1.0.dev0` |
| Runtime modules in wheel and test backend in sdist | PASS |
| Repository-external wheel install and `pip check` | PASS |
| Installed backend -> raw -> CRC -> PARSED -> close smoke | PASS |
| Installed smoke without pyserial | PASS — `serial` module absent |
| OS serial, controller, instrument, or BENCH test | NOT RUN |

## Corrected development checks

The first focused invocation found one unused test-helper import and one
integration import that attempted to use the deliberately frozen
`analog_validation.protocol` facade instead of the new neutral-envelope module.
Pytest stopped during collection, so no pass was claimed. Both test imports were
corrected without changing the frozen facade.

The next focused run completed 83 passes and four failed assertions. The
session correctly closed after invalid backend output/clock data, but its broad
receive boundary rewrapped already-typed `SerialReadError` messages as a generic
processing error. The implementation was corrected to preserve typed internal
read errors while still closing deterministically; all 87 then-current Step 3
tests passed.

The first full coverage run passed 1,217 tests but identified three unexecuted
lines in the unexpected event-sink failure branch. A dedicated failing event-log
test was added. The authoritative final run passed 1,218 tests and all 6,274
formal statements. These diagnostics are retained rather than presenting an
intermediate run as final evidence.

## Evidence boundary

This checkpoint proves host-side interface, state, resource, failure-recovery,
raw provenance, installation, and composition behavior. It does not prove:

- Windows/Linux/macOS port enumeration, permission, or driver behavior;
- pyserial configuration, OS timeout accuracy, or real disconnect timing;
- a real COM-port open/read/reconnect/close lifecycle;
- AFE or MSP430 profile semantics, capability exchange, or Measurements;
- UART baud accuracy, voltage levels, grounding, cable quality, or EMI behavior;
- any hardware gain, offset, cutoff, threshold, ADC, sensor, current, power,
  temperature, fan, or protection performance.

The connected MSP430 LaunchPad was not accessed. Peer-project evidence was not
imported or counted. `VERIFIED_BENCH` remains zero.

## Next checkpoint

Step 4 will implement an independent AFE v1 serial profile over these generic
records. It will provide explicit profile identity, 16-bit sequence mapping,
capability-message handling, and record/error mapping while reusing the existing
AFE golden data. It will continue to use the in-memory backend; physical port
access remains deferred to the separately approved optional Step 7 gate.
