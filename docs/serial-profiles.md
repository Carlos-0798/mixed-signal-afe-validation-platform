# Serial Profiles and AFE v1 Integration

**Implemented:** Software Phase 4 Steps 4–5<br>
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
 AFE v1 profile   MSP430 Health v1 profile
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

## 9. Independent MSP430 Equipment Health v1 profile

Step 5 adds a second business profile without putting MSP430 fields into AFE
messages. Its selected identity is:

| Field | Value |
|---|---|
| Profile name | `msp430-equipment-health` |
| Interface version | `1` |
| Sequence width | 32 bits |
| Maximum record | 128 bytes including LF |
| Interface source | peer `docs/protocol.md` at `151fdcfa60661bce1ba04af13c1d3509706f7d4a` |

Unlike AFE records, the MSP430 wire record does not carry a version token.
The caller must therefore select this exact profile/version explicitly; a
`TEL` prefix, COM number, USB identity, or board name is not version discovery.

The independent parser accepts device-output `TEL`, `ACK`, `STS`, `CFG`, and
`LOG` records. It deliberately supplies no `CMD` encoder and exposes no control
operation. Only `TEL.sequence` enters continuity tracking; request sequences in
responses remain correlation values. A `4294967295 -> 0` transition is therefore
an in-order 32-bit wrap.

### Availability mapping

The typed `Msp430Telemetry` always preserves the raw integer fields and all 16
fault bits. Mapping then applies availability rules:

| Wire condition | Product Measurement meaning |
|---|---|
| temperature `-32768` | `value=None`, `INVALID`, `MISSING` |
| DS18B20 missing/CRC fault | DS value unavailable; raw deci-degree value retained in the message |
| NTC range fault | NTC value unavailable with `OUT_OF_RANGE`; raw value retained |
| sensor disagreement | otherwise available temperature values are `SUSPECT + DEVICE_FAULT` |
| INA219 communication fault | bus voltage and current are `None + INVALID + MISSING + COMMUNICATION_ERROR`; raw zero fields remain in the message |
| zero electrical fields without INA219 fault | valid numeric zero, not automatically missing |
| fan PWM | read-only ratio from 0 to 1; never treated as an AFE stimulus |

`power_mw` is preserved on the typed message and participates in the same
`ina219_available` decision. Measurement v1 has no watt/milliwatt unit, so Step
5 does not mislabel power as `UNITLESS`. A future controlled Measurement-schema
extension may add it without changing the frozen wire profile.

The static capability descriptor contains only `READ_MEASUREMENT`, no DAC/PWM
output channels, and `supports_safe_shutdown=False`. Its numeric input ranges
describe the Protocol v1 representable software envelope; they are not detected
sensor specifications, calibrated limits, or safe electrical input ratings.

### Independent fixtures

`test-data/golden/msp430_equipment_health_v1.json` belongs to this repository.
It records its public interface source and explicitly excludes peer runtime
code, serial I/O, hardware behavior, and inherited test evidence. Ten valid
records cover every device-output family, sentinels, uint32 boundaries, and a
numeric LOG state that must be preserved. Eleven invalid records freeze bad
CRC, framing, field count/type/range, unknown TEL state, unsupported CMD, and
resource-limit behavior.

The in-memory composite proof performs fragmented/coalesced bytes ->
`SerialSession` -> exact raw events -> MSP430 profile -> Measurements -> typed
CRC rejection. It does not import the peer `dashboard`, firmware, or tools.

## 10. Evidence boundary and next step

Steps 4–5 prove deterministic software parsing, mapping, aggregation, state
recovery, independent interoperability fixtures, and in-memory transport
composition. They do not
prove:

- an OS or pyserial backend;
- UART baud, voltage levels, timing, grounding, cable, or EMI behavior;
- any AFE circuit, ADC/DAC, gain, cutoff, threshold, saturation, or protection;
- OS-level or physical MSP430 serial compatibility;
- physical safe shutdown.

Step 6 will wrap the transport and either selected profile in one
`SerialAdapter`, project profile-native capabilities explicitly, and exercise
the existing `DeviceAdapter`/`ReadWorkflow` contracts with an in-memory backend.
It will not access a physical port; owner-approved read-only HIL remains Step 7.
