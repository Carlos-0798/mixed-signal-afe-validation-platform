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

## Reusable contract tests

`tests/contracts/adapter_contract.py` defines `ReadOnlyAdapterContract`. A concrete adapter test supplies only an `AdapterContractSpec`:

```python
class TestExampleAdapterContract(ReadOnlyAdapterContract):
    contract_spec = AdapterContractSpec(
        factory=ExampleAdapter,
        evidence_source=EvidenceSource.SYNTHETIC,
        analog_channel="adc0",
        analog_unit=MeasurementUnit.VOLT,
    )
```

Pytest then inherits the same eight checks for initial state/provenance, read-only connection, explicit and cached capabilities, premature-read rejection, typed measurement output, unknown-channel classification, idempotent shutdown, and disconnect/reconnect behavior.

The Step 2 `ContractReferenceAdapter` is only a HOST_TEST fixture proving that the suite is collectible and reusable. It is not a SimulatorAdapter, physical device, or product data source. Step 3 now runs the same suite against the real SimulatorAdapter; Step 6 must do the same for CSV Replay.

## Deterministic SimulatorAdapter

Step 3 adds the first concrete product adapter. Its default public behavior is intentionally small:

- profile `afe`, version `1`;
- device ID `simulator-afe-1`;
- one read-only channel, `afe.ch0.input`;
- unit `mV`, declared range 0–3300 mV;
- `READ_MEASUREMENT` is the only supported command;
- source is always `SYNTHETIC`;
- default seed is 430 and interval is 100 ms;
- default clock starts at the fixed UTC epoch `2026-01-01T00:00:00Z`;
- reconnecting restarts the deterministic sequence.

`SimulatorConfig` is immutable and versioned as `simulator-config.v1`. A test or future application may inject a timezone-aware clock; the adapter converts it to UTC and advances timestamps by the configured interval. Same seed, clock, interval, and read order produce identical Measurements.

The AFE formula previously owned by `tools/telemetry_simulator.py` now lives in the formal adapter module. The tool, the 100-frame hash regression, and the adapter reuse that single generator. This preserves the existing AFE wire stream while removing duplicate behavior.

Step 3 does not provide configurable gain, offset, noise, saturation, hysteresis, dropped data, CRC errors, stimulus output, or hardware emulation. Those are Step 4 requirements and must remain explicit rather than being silently implied by the word “simulator.”

## What this does not prove

The state machine and tests prove host-software behavior only. `SAFE_SHUTDOWN` means the adapter software path completed; it does not prove that a physical relay, DAC, PWM pin, power rail, or external circuit actually reached a safe voltage. That requires later firmware and bench evidence.
