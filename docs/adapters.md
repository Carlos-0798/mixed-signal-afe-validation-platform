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

The Step 2 `ContractReferenceAdapter` is only a HOST_TEST fixture proving that the suite is collectible and reusable. It is not a SimulatorAdapter, physical device, or product data source. Step 3 runs the suite against the real SimulatorAdapter, and Step 6 runs the same eight checks against CsvReplayAdapter.

## Configurable deterministic SimulatorAdapter

Steps 3 and 4 add the first concrete product adapter. Its public behavior is intentionally read-only:

- profile `afe`, version `1`;
- device ID `simulator-afe-1`;
- two read-only analog channels, `afe.ch0.input` and `afe.ch0.output`;
- one read-only boolean channel, `afe.ch0.threshold`;
- analog unit `mV`, declared input range 0–3300 mV;
- `READ_MEASUREMENT` and `READ_DIGITAL_STATE` are the only supported commands;
- source is always `SYNTHETIC`;
- default seed is 430 and interval is 100 ms;
- default clock starts at the fixed UTC epoch `2026-01-01T00:00:00Z`;
- reconnecting restarts the deterministic sequence.

`SimulatorConfig` is immutable and versioned as `simulator-config.v1`. It controls gain, offset, Gaussian-noise standard deviation, lower/upper saturation limits, Schmitt low/high thresholds, and an optional deterministic fault cadence. A test or future application may inject a timezone-aware clock; the adapter converts it to UTC and advances timestamps by the configured interval.

Each public channel has its own deterministic sample stream. Reading one channel therefore does not move another channel forward. Same seed, configuration, clock, and per-channel read sequence produce identical Measurements. The output uses `gain × input + offset + noise`, then clamps to configured limits. Clamping returns `SUSPECT` plus `SATURATED`; Schmitt state changes only at the configured upper/lower thresholds and holds inside the band.

Fault mode is explicit and singular: `MISSING_SAMPLE` returns an `INVALID` Measurement with `MISSING` and `COMMUNICATION_ERROR`; `COMMUNICATION_ERROR` raises `AdapterError`; `CRC_ERROR` raises `CrcMismatch`. The selected cadence is counted independently per channel and consumes the affected sample so recovery remains reproducible.

The AFE formula previously owned by `tools/telemetry_simulator.py` now lives in the formal adapter module. The tool, the 100-frame hash regression, and the adapter reuse that single generator. This preserves the existing AFE wire stream while removing duplicate behavior.

The simulator does not provide a DAC/PWM stimulus output, analog circuit solver, electrical timing model, or hardware emulation. The configured formula and faults are test fixtures rather than physical measurements.

## CsvReplayAdapter

Step 5 defines the immutable dataset and strict parser; Step 6 adds the read-only `CsvReplayAdapter` that consumes only an already validated `CsvReplayDataset`. Configuration is immutable and versioned as `csv-replay-adapter-config.v1`.

Every channel must be declared explicitly as analog or digital with an exact unit. Analog channels additionally require an explicit `SafeRange`. These ranges describe what the replay fixture is allowed to present through the software capability interface; they are not measured electrical limits or hardware proof. The adapter never guesses a channel role, unit, or range from numeric file content.

Playback behavior is deliberately deterministic:

- each channel has an independent cursor, so reading one channel does not consume another;
- `IMMEDIATE` returns the next record without waiting;
- `SCALED` delays between consecutive records of the same channel by `timestamp delta / speed_multiplier`;
- the first record on a channel has no preceding delay;
- `pause()` blocks reads without consuming a record, and `resume()` continues from the same cursor;
- `set_speed_multiplier()` changes future scaled delays and accepts only finite values greater than zero;
- `channel_at_end()` reports one channel's state, `at_end` reports whether all configured channels are exhausted, and a read beyond the end raises `ReplayEndOfData`;
- disconnect/reconnect resets all cursors, pause state, and runtime speed to the immutable configuration.

Replayed Measurements preserve the source row's timestamp, value, unit, status, quality flags, and original record reference. Their new ID is namespaced by replay dataset, and current source is always `CSV_REPLAY`. A file row that declares `BENCH_DMM` remains visible through the immutable `adapter.dataset` audit object but cannot elevate the replayed Measurement into bench evidence.

Timing uses an injectable sleeper. Host tests therefore verify exact requested delays without waiting in real time. This verifies software scheduling arithmetic, not Windows real-time performance or hardware timing. See [CSV Replay v1](csv-replay-v1.md).

## What this does not prove

The state machine and tests prove host-software behavior only. `SAFE_SHUTDOWN` means the adapter software path completed; it does not prove that a physical relay, DAC, PWM pin, power rail, or external circuit actually reached a safe voltage. That requires later firmware and bench evidence.
