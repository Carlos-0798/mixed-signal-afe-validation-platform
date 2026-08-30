# Device Adapter Contract

Software Phase 2 introduces one public device port for every future data source. The upper application layer calls `DeviceAdapter`; a concrete adapter decides whether the data comes from a simulator, CSV file, serial controller, MSP430 compatibility profile, or instrument.

## Why the boundary exists

Without this boundary, a DC sweep or report could accidentally depend on a COM port, board register, vendor SDK, or file layout. The adapter keeps those details outside the reusable domain and analysis code.

```text
same application workflow
          |
          v
    DeviceAdapter
      /   |    \
Simulator CSV  future Serial/MSP430/instrument
```

## Lifecycle

| State | Meaning | Output allowed? |
|---|---|---|
| `DISCONNECTED` | No logical source is open | No |
| `CONNECTED_READ_ONLY` | Source is open; capabilities are not trusted yet | No |
| `CAPABILITIES_CONFIRMED` | Explicit channels, commands, units, and safe ranges are cached | No |
| `ARMED` | Matching configuration and output safety gates passed | Yes, within both ranges |
| `RUNNING` | At least one approved stimulus operation completed | Yes, within both ranges |
| `SAFE_SHUTDOWN` | Adapter completed or logically required its safe-state path | No |

`connect()` never arms output. `arm()` requires a typed `ValidationConfig`, `allow_output=true`, matching profile/version, matching evidence source, declared output command, device safe range, configured safe range, and `SAFE_SHUTDOWN` capability.

## Public operations

- `connect()` and `disconnect()` manage source ownership;
- `get_capabilities()` performs explicit capability negotiation and caching;
- `read_measurement()` and `read_digital_state()` return formal `Measurement` objects;
- `arm()` performs host-side authorization but does not produce output;
- `set_stimulus()` applies one value only after all gates pass;
- `run_command()` invokes an explicitly advertised non-stimulus profile command; output-affecting operations must use the armed `set_stimulus()` path;
- `safe_shutdown()` is idempotent and clears output authorization.

The base class validates returned channel, unit, and evidence source. A SimulatorAdapter must return `SYNTHETIC`; a replay adapter must return `CSV_REPLAY`. Neither can silently return `BENCH_*` evidence.

## What this does not prove

The state machine and tests prove host-software behavior only. `SAFE_SHUTDOWN` means the adapter software path completed; it does not prove that a physical relay, DAC, PWM pin, power rail, or external circuit actually reached a safe voltage. That requires later firmware and bench evidence.
