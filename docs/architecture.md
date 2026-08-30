# Software architecture

The AFE Validation Platform is the product. It is not an accessory or subordinate module of the MSP430 Equipment Health Controller. The analog base unit must operate without a microcontroller; optional controllers and host adapters automate it through versioned public interfaces.

```text
Independent AFE Base Unit
  +-- manual configuration and analog/digital outputs
  +-- optional Reference Validation Controller
  +-- optional MSP430 / other 3.3 V MCU integration
  +-- controller-neutral Python Host Software
```

```text
Simulator / CSV Replay / future Serial / Instrument
            |
            v
 analog_validation.adapters  ---> lifecycle / capability / safety port
            |
            v
 analog_validation.protocol  ---> versioned AFE v1 records
            |
            v
 analog_validation.replay    ---> strict immutable CSV Replay v1
            |
            v
 analog_validation.domain    ---> provenance / capability / TestRun
            |
            v
 analog_validation.workflows ---> shared read preflight / acquisition
            |
            +----> future analysis runners
            +----> future CLI / Dashboard / reports
```

`src/analog_validation/` is the only formal product core. An executable architecture test rejects third-party, serial, GUI, board-SDK, `dashboard`, or `tools` imports from that package. The remaining `dashboard/measurements/` files are explicitly legacy Phase 0 analysis algorithms awaiting Software Phase 3 migration; they are not dependencies of the formal core.

`DeviceAdapter` uses template methods: public methods own lifecycle, capability, configuration, unit, provenance, and output-safety checks; concrete adapters implement protected source-specific hooks. `connect()` reaches only `CONNECTED_READ_ONLY`. Output remains impossible until capabilities are confirmed and a matching `allow_output=true` configuration passes both configured and device safe ranges. See `adapters.md`.

The Step 4 `SimulatorAdapter` is the first concrete adapter. It is read-only, uses only standard-library dependencies, exposes explicit input/output mV channels plus a boolean Schmitt-state channel, and returns only `SYNTHETIC` Measurements. Configured non-idealities and fault injection remain software evidence. The repository-local telemetry CLI imports its formal generator; the formal package never imports the tool.

Step 5 adds `analog_validation.replay` as a separate file-format boundary that validates a complete CSV Replay v1 dataset. Step 6 adds `CsvReplayAdapter` as the lifecycle/playback boundary. It requires an explicit channel map, exposes read-only capabilities, keeps independent per-channel cursors, supports immediate or scaled timing, and returns current Measurements only as `CSV_REPLAY`. The immutable dataset remains available for audit lookup, including any untrusted declared source.

Step 7 adds `analog_validation.workflows` above the adapter port. `run_read_workflow` accepts one immutable request regardless of source, owns connect/capability/read/disconnect for that call, and checks every command/channel/unit before the first read. It distinguishes completed acquisition, unsupported capability, early end-of-data, and execution errors. It deliberately performs no gain, linearity, hysteresis, calibration, or PASS/FAIL analysis; those remain future runners built on its Measurements.

Hardware, reference-controller firmware, integration profiles, and host tools are separate boundaries. Firmware remains a later-phase placeholder. Public integration with the independent MSP430 project is one future supported profile, limited to documented protocol and electrical interfaces; no application code, ownership, or product identity is shared. See `PRODUCT_ARCHITECTURE.md`.
