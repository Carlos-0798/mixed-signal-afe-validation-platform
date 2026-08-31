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
Simulator / CSV Replay / receive-only Serial / future Instrument
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
 analog_validation.workflows ---> shared read-only preflight / acquisition

 adapters + config + analysis ---> analog_validation.runners
                                      |
                                      +----> analog_validation_app / future workflows
```

`src/analog_validation/` is the only formal product core. An executable architecture test rejects third-party, serial, GUI, board-SDK, product-layer, or tools imports from that package. Software Phase 3 Step 1 adds `analog_validation.analysis.common` for lineage, quality policy, disposition/reasons, one-source batches, and explicit voltage normalization. Step 2 adds `analysis.dc_sweep` for traceable pairing, inclusive saturation decisions, completeness gaps, and ordinary least-squares metrics. It consumes domain Measurements and does not import adapters or control output. The superseded root `dashboard/measurements/` comparison path was removed in Phase 5 Step 1 after formal goldens confirmed that the core replacement remained intact.

Software Phase 3 Step 3 adds `analysis.dc_criteria`. Criteria remain immutable and versioned separately from the analysis. The evaluator verifies TestRun metadata/source/raw IDs, records five inclusive numeric checks, and maps only complete evidence to PASS/FAIL; missing criteria or data remains INCOMPLETE. This pure decision layer still does not import adapters or perform I/O. See `dc-sweep-criteria.md`.

Software Phase 3 Step 4 adds the separate `analog_validation.runners` orchestration namespace. `run_dc_sweep` owns one disconnected adapter, validates the complete plan/config/metadata and every setpoint, confirms read/output/safe-shutdown capabilities before I/O, executes ordered settle/read pairs, and always disconnects. Analysis and criteria evaluation occur only after cleanup succeeds. Missing capabilities produce zero-I/O `UNSUPPORTED`; abort/EOF remains `INCOMPLETE`; execution or cleanup failure is `ERROR`. See `dc-sweep-runner.md`.

Software Phase 3 Step 5 adds `analysis.hysteresis`, `analysis.hysteresis_criteria`, and `runners.hysteresis`. The pure analysis layer validates direction and exact boolean state, preserves analog/state references around each transition, publishes no partial thresholds, and summarizes only complete repeated cycles. The runner applies the existing default-deny output and cleanup order to rising/falling sweeps. See `hysteresis-analysis-and-runner.md`.

Software Phase 3 Step 6 adds pure `analysis.calibration` and `analysis.frequency_response` modules. Calibration may compare one observed source with a separate reference source, freezes all fit-input lineage in versioned coefficients, reports before/after errors, and creates new derived Measurements on application. Frequency response requires three same-source, equal-length batches with explicit Hz/input/output amplitudes; it computes ratio/dB and one cutoff using linear interpolation in dB versus log10 frequency. Neither module imports adapters, samples waveforms, performs FFT, controls instruments, or upgrades evidence provenance. See `calibration-and-frequency-response.md`.

Software Phase 3 Step 7 adds `analog_validation.exports` after the finalized TestRun boundary. Its typed DC and hysteresis builders copy existing conclusions into the immutable `result-export.v1` bundle; JSON and row-oriented CSV are deterministic representations of the same bundle. The layer preserves source and record lineage, requires limitation text, rejects non-finite or structurally inconsistent documents, and uses atomic local writes with no overwrite by default. It never recalculates metrics or promotes evidence. See `result-exports.md`.

Software Phase 3 Step 8 freezes the explicit `analysis`, `runners`, and `exports` namespaces plus representative exact DC/hysteresis result meaning. The existing 84-symbol Phase 2 top level remains unchanged. Golden tests assert that public Phase 3 implementations originate in `analog_validation.*`; Phase 5 architecture checks additionally reject copied protocol or analysis code in the product package. See `phase3-public-api.md`.

`DeviceAdapter` uses template methods: public methods own lifecycle, capability, configuration, unit, provenance, and output-safety checks; concrete adapters implement protected source-specific hooks. `connect()` reaches only `CONNECTED_READ_ONLY`. Output remains impossible until capabilities are confirmed and a matching `allow_output=true` configuration passes both configured and device safe ranges. See `adapters.md`.

The Step 4 `SimulatorAdapter` is the first concrete adapter. It is read-only, uses only standard-library dependencies, exposes explicit input/output mV channels plus a boolean Schmitt-state channel, and returns only `SYNTHETIC` Measurements. Configured non-idealities and fault injection remain software evidence. The repository-local telemetry CLI imports its formal generator; the formal package never imports the tool.

Step 5 adds `analog_validation.replay` as a separate file-format boundary that validates a complete CSV Replay v1 dataset. Step 6 adds `CsvReplayAdapter` as the lifecycle/playback boundary. It requires an explicit channel map, exposes read-only capabilities, keeps independent per-channel cursors, supports immediate or scaled timing, and returns current Measurements only as `CSV_REPLAY`. The immutable dataset remains available for audit lookup, including any untrusted declared source.

Step 7 adds `analog_validation.workflows` above the adapter port. `run_read_workflow` accepts one immutable request regardless of source, owns connect/capability/read/disconnect for that call, and checks every command/channel/unit before the first read. It distinguishes completed acquisition, unsupported capability, early end-of-data, and execution errors. It deliberately performs no gain, linearity, hysteresis, calibration, or PASS/FAIL analysis; the Phase 3 runner is a separate consumer rather than a change to this frozen read-only API.

Step 8 freezes the Phase 2 boundary through machine-readable exports/schema/enum/signature/error/hash data and exact Simulator/CSV/UNSUPPORTED workflow results. The freeze protects callers and future Phase 3 runners from accidental API or meaning drift while keeping internal implementation replaceable. See `phase2-public-api.md`.

Software Phase 4 Steps 1–7 add lower communication and receive-only composition boundaries without changing the frozen Phase 1–3 public surface. `analog_validation.transport` turns arbitrary bounded byte chunks into complete LF records, tracks profile-selected sequence widths, defines a replaceable serial backend port, owns the deterministic lifecycle, and retains bounded raw outcomes. `analog_validation.protocol.envelope` validates printable tokens, terminators, record length, and CRC without assuming a namespace; the existing AFE `framing.py` delegates to it and adds only the historical `AFE` shape requirement. A versioned `afe-channel-map.v1` provides explicit legacy-to-canonical channel conversion. `analog_validation.profiles` defines the controller-neutral profile port with two independent implementations: AFE telemetry uses 16-bit continuity and canonical Measurement names while its capability records use transaction correlation; MSP430 Equipment Health telemetry uses 32-bit continuity, preserves raw sentinels/faults, maps unavailable values to missing/invalid records, and exposes a static read-only capability contract. `analog_validation.serial_adapters` composes a session/profile pair behind `DeviceAdapter`, while separate optional `analog_validation_pyserial` implements only OS discovery/open/read/close. The Step 6 adapter and Step 7 backend expose no write API or command escape hatch. Transport cannot import profiles, profiles cannot import adapters or higher layers, `serial_adapters` cannot import pyserial or higher layers, and the optional backend cannot import profiles/adapters/workflows/analysis/runners/exports. Step 7 opened COM4 only for the reported five-frame passive HIL; it did not establish AFE or peripheral behavior. See `serial-profiles.md` and `pyserial-backend.md`.

Software Phase 4 Step 8 freezes these boundaries in
`phase4-public-api-golden.v1` and `phase4-composite-golden.v1`. Seven namespaces,
their schemas/identities/enums/signatures/errors, and exact AFE/MSP430
external-backend product chains are checked without requiring inheritance from
an internal backend class. This protects extension points while keeping the
Step 7 physical UART evidence separate from deterministic HOST_TEST results.
See `phase4-public-api.md`.

Software Phase 5 uses a separate upward-only product package,
`analog_validation_app`. Step 1 implements immutable output-denying product
requests/results, exact-match source/profile catalog entries, stable user issues,
and the installed `analog-validation version/profiles` identity surface. It also
retires the Phase 0 root `dashboard/` source and enforces that no CRC, protocol,
profile, or engineering-analysis implementation is copied into the product layer.
Step 2 adds immutable bounded events and a generic single-owner worker. One
non-daemon thread creates, runs, and cleans one injected service; cooperative
cancellation, bounded joins, terminal result/issue capture, and cleanup-failure
override are host-tested. The worker imports no device, protocol, analysis,
serial, export, or GUI implementation. Step 3 adds explicit factories, shared
read/DC/hysteresis services, and stable installed CLI workflows. Step 4 adds a
bounded presentation-only view and deterministic text/Markdown/HTML/SVG/manifest
publisher from finalized result bundles; it imports no analysis, adapter,
serial, GUI, or network code. Step 5 will add the local Tkinter/ttk Dashboard.
CLI and Dashboard must consume the same services and presentation semantics;
neither may parse device records, recalculate engineering results, or open a
serial backend directly. Tk imports remain isolated and delayed, and pyserial
remains optional. See `product-layer.md`, `human-reports.md`, and
`SOFTWARE_PHASE_5_PLAN.md`.

Hardware, reference-controller firmware, integration profiles, and host tools are separate boundaries. Firmware remains a later-phase placeholder. Public integration with the independent MSP430 project now includes one host-tested read-only profile/adapter and one narrow Analog-owned passive UART HIL through the optional OS backend. Exact firmware, long-duration transport, physical disconnect recovery, external peripherals, the AFE electrical interface, application code, ownership, and product identity are not shared or inferred. See `PRODUCT_ARCHITECTURE.md`.
