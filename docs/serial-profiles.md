# Serial Profiles and AFE v1 Integration

**Implemented:** Software Phase 4 Step 4<br>
**Schema:** `serial-profile.v1`<br>
**Evidence:** HOST_TEST<br>
**Physical serial or AFE validation:** none

## 1. What this layer solves

A serial connection only delivers bytes. It cannot tell the product whether a
record is AFE telemetry, an MSP430 status record, a capability declaration, or
damaged input. Step 4 adds the business-language layer between the generic
transport and a future `SerialAdapter`:

```text
SerialBackend / in-memory backend
              |
              v
SerialSession + bounded LF framer
              |
              v
PENDING_PROFILE RawRecordEvent
              |
              v
explicit SerialProfile selection
              |
       +------+------+
       |             |
       v             v
 AFE v1 profile   future MSP430 profile
       |
       v
typed message + canonical Measurements + profile-native capabilities
```

For a beginner, the separation is similar to three checks on a delivered
package:

1. transport confirms that one bounded package arrived;
2. the profile reads the language and validates its grammar;
3. the future adapter decides how the validated information is offered to the
   rest of the product.

Keeping these checks separate means a new controller adds a profile instead of
changing CRC, raw logging, analysis, or AFE business rules.

## 2. Generic profile contract

The public `analog_validation.profiles` namespace defines four core values:

| Contract | Purpose |
|---|---|
| `SerialProfileIdentity` | Explicit name, version, sequence width, record limit, and schema |
| `SerialProfile` | Replaceable interface implemented by each business protocol |
| `SerialProfileRecord` | Accepted/rejected raw outcome plus typed derived data |
| `SerialProfileResetResult` | Sequence and incomplete-transaction state discarded at a boundary |

Profile selection is never guessed from a COM number, board name, USB ID, or
manufacturer. A session event's `profile_name` must match the selected identity,
and the wire decoder must independently validate the version inside the record.

`SerialProfileRecord` has two valid shapes:

- accepted: the raw event is `PARSED`, a typed message is present, and optional
  Measurements or a completed capability snapshot may be present;
- rejected: the raw event is `REJECTED`, contains the stable error type/message,
  and contains no derived data.

A pending event, mismatched log, wrong profile, already-processed event, or
internal mapping failure is a caller/program state error. It is not relabeled
as damaged device input.

## 3. Frozen AFE v1 serial identity

`AfeV1SerialProfile` declares:

| Field | Value |
|---|---|
| Profile name | `afe` |
| Wire version | `1` |
| Sequence width | 16 bits |
| Maximum record | 128 bytes including LF |
| Profile schema | `serial-profile.v1` |

It reuses the existing AFE v1 parser, encoder, capability aggregator,
Measurement mapper, CRC implementation, and explicit channel-name conversion.
It does not duplicate those rules and contains no MSP430 fields.

## 4. Telemetry mapping

One accepted `AfeTelemetry` record produces four Measurements. The historical
mapper remains unchanged, then the serial profile crosses the frozen
`afe-channel-map.v1` boundary explicitly:

| Historical mapper output | Serial/profile product output |
|---|---|
| `afe.chN.input_mv` | `afe.chN.input` |
| `afe.chN.output_mv` | `afe.chN.output` |
| `afe.chN.gain` | `afe.chN.gain` |
| `afe.chN.threshold` | `afe.chN.threshold` |

The unit remains a separate typed field, so removing `_mv` from the canonical
channel name does not remove the millivolt unit. Fault-bearing telemetry remains
`SUSPECT + DEVICE_FAULT`; the profile never turns it into valid data.

The constructor requires an explicit evidence source. Step 4 uses
`HOST_TEST`. `BENCH_CONTROLLER` is available for a future physical adapter, but
selecting that enum does not by itself prove a physical test; the later HIL gate
must supply the actual port/configuration/raw evidence.

## 5. Why only telemetry advances the sequence tracker

AFE v1 uses the same 16-bit field for two different purposes:

- `TEL` uses it as stream continuity;
- command and capability records use it as transaction correlation.

A capability response deliberately repeats one sequence on `DEVICE`, every
`CHANNEL`, and `END`. Feeding every record to one continuity tracker would
incorrectly report the valid response as several duplicate frames. Step 4
therefore applies `FIRST`, `IN_ORDER`, `GAP`, `DUPLICATE`, `OUT_OF_ORDER`, and
wrap handling only to telemetry. Capability aggregation separately requires
all records in one response to carry the same sequence.

This is a semantic decision, not a missing check.

## 6. Capability transaction and safety meaning

The profile accumulates:

```text
DEVICE -> zero or more CHANNEL records -> END
```

It publishes `DeviceCapabilities` only after `END` validates the sequence,
entry count, channel ranges, command-mask consistency, and safe-shutdown flag.
An orphan `CHANNEL/END`, a second `DEVICE` before completion, mismatched
sequence, wrong count, or inconsistent command/channel declaration rejects the
current raw record and clears the incomplete transaction so later input can
recover.

The completed snapshot intentionally retains the frozen AFE wire names
`adcN`, `dacN`, `pwmN`, and `dinN`. Existing
`validate_command_capability()` therefore keeps exactly the same safety meaning.
Step 6 must perform an explicit adapter-facing projection where needed; it must
not silently reinterpret a DAC, PWM, or ADC channel. The telemetry
legacy-to-canonical conversion and capability wire-to-adapter projection are
different boundaries.

## 7. Error and state behavior

Expected wire/profile failures such as bad CRC, invalid ASCII, excess length,
unsupported AFE version, bad field count, or invalid capability transaction:

1. do not produce Measurements or capabilities;
2. become `REJECTED` in the bounded raw log;
3. preserve exact raw bytes;
4. do not advance telemetry continuity.

Programming/contract failures propagate as typed profile or raw-log errors. If
the raw log cannot store a final parsed/rejected outcome, the profile restores
its prior sequence and capability state. This prevents internal state from
claiming progress that the provenance log did not retain.

`reset()` is used at a future session/disconnect boundary. It clears telemetry
continuity and incomplete capability records and reports what was discarded.

## 8. Host-only composite proof

The Step 4 integration test uses `MemorySerialBackend` and performs:

```text
fragmented + coalesced scripted bytes
 -> SerialSession
 -> exact PENDING raw records
 -> AfeV1SerialProfile
 -> canonical Measurements
 -> completed read-only capability snapshot
 -> typed CRC rejection
```

It verifies 16-bit `65535 -> 0` wrap, exact raw-byte retention, canonical
channels, a completed capability exchange, and a bad CRC that does not advance
sequence state. No OS serial module or physical port is involved.

All 20 historical valid AFE golden records also cross the new path and re-encode
to the exact same bytes. All 9 invalid records retain their original error
families and matching error meaning.

## 9. Evidence boundary and next step

Step 4 proves deterministic software parsing, mapping, aggregation, state
recovery, package content, and in-memory transport composition. It does not
prove:

- an OS or pyserial backend;
- UART baud, voltage levels, timing, grounding, cable, or EMI behavior;
- any AFE circuit, ADC/DAC, gain, cutoff, threshold, saturation, or protection;
- MSP430 protocol compatibility;
- physical safe shutdown.

Step 5 will add the peer, read-only `msp430-equipment-health.v1` profile from its
published interface contract and independent fixtures. It will not import the
MSP430 repository or merge either product.
