# Test plan and evidence labels

## Evidence labels

- `THEORY`: result derived from a documented equation and nominal inputs.
- `SPICE_IDEAL`: result produced by the included idealized LTspice netlists.
- `SYNTHETIC`: data generated in software to test analysis paths.
- `HOST_TEST`: executable Python test result.
- `BENCH_CONTROLLER`: physical controller bytes, not automatically an external-sensor or AFE measurement.
- `BENCH_DMM` / `BENCH_SCOPE`: future physical measurements with recorded wiring and instruments.

Only a specific `BENCH_*` record may support the physical behavior it directly observed. Controller UART evidence cannot support AFE voltage/gain/bandwidth claims. Phase 0 can produce the first four labels only.

## Phase 0 executable checks

- CRC known vector, empty payload, and round trip.
- Valid telemetry and command round trips.
- CRC mismatch, missing fields, non-ASCII, malformed values, and overlong input rejection.
- Least-squares gain, offset, and R-squared on exact and noisy synthetic points.
- High/low saturation exclusion and insufficient-linear-data rejection.
- Rising/falling Schmitt transition interpolation and hysteresis width.
- LTspice ideal buffer, gain, RC cutoff, and Schmitt topology tasks when the executable is available.

## Phase 1 entry gate

Do not power the analog assembly until the open toolchain, inventory, permission, and wiring items in `ASSUMPTIONS.md` are resolved. Phase 1 records must include actual part suffixes, supply current limit, pre-power continuity checks, measured 3.3 V and VBIAS, DMM model, gain-jumper state, raw DC sweep data, and any observed saturation or instability.

## Software Phase 4 serial host checks

- Use a deterministic in-memory backend before any OS/COM backend.
- Cover fragmented/coalesced records, normal timeout, open/read/close failure,
  disconnect, partial-frame reset, finite reconnect, and overlong recovery.
- Require exact raw bytes, UTC receive time, logical port, explicit profile,
  parse/error outcome, and optional typed sequence observation.
- Enforce per-record, event-count, total-byte, and metadata bounds; record FIFO
  eviction counters and do not persist/upload raw records automatically.
- Run the installed-wheel chain without pyserial to prove simulation/replay and
  core imports remain hardware optional.
- Drive every valid/invalid AFE golden record through the selected AFE serial
  profile; retain exact accepted bytes and stable rejected error families.
- Verify telemetry-only 16-bit continuity, explicit legacy-to-canonical
  Measurement mapping, strict capability transaction aggregation, and state
  rollback if a final raw outcome cannot be retained.
- Drive every repository-owned MSP430 valid/invalid fixture through the
  independent read-only profile; verify `TEL/ACK/STS/CFG/LOG`, 32-bit TEL wrap,
  unknown state rejection, raw sentinel/fault retention, and unavailable-safe
  Measurement mapping.
- Confirm the MSP430 profile has no command encoder, output capability, or
  `SAFE_SHUTDOWN`, and imports no peer-project runtime namespace.
- Construct `SerialAdapter` only from an explicitly matching closed session,
  profile identity/version, record limit, evidence source, and capability
  projector; reject mismatches before I/O.
- Run the same reusable eight-check read-only adapter contract against both AFE
  and MSP430 serial configurations, then drive both through the unchanged
  `ReadWorkflow` with an in-memory backend.
- Retain AFE native capabilities, explicitly alias
  `adcN/dacN/pwmN/dinN` to canonical workflow names, and reject any projector
  that changes identity, channel counts, numeric ranges, or adds commands.
- Bound capability/read polling and queued Measurements; cover timeout, bad CRC,
  overlong input, buffer overflow, profile failure, capability drift, fatal
  session loss, and successful-reconnect capability invalidation.
- Prove read-only MSP430 DC and hysteresis runner preflight returns
  `UNSUPPORTED` with zero reads/writes using a backend that exposes no write
  method.
- Install the built wheel outside the repository without pyserial and run an
  installed-package SerialAdapter -> ReadWorkflow smoke while asserting
  `HOST_TEST`, raw lineage, deterministic close, and zero writes.
- Keep real port/HIL commands `NOT RUN` until the separate owner-approved gate;
  host lifecycle tests do not prove OS timing, UART electrical behavior, or a
  physical controller link.

## Software Phase 4 optional controller HIL checks

- Keep the base wheel usable without pyserial; install the driver only through
  the optional `serial` extra.
- Discover first, require an explicit application-UART port, and never use a
  COM number as a library default or capability inference.
- Use a backend with no public write method; send no command bytes, flash
  nothing, and do not change FRAM.
- Capture through the current `SerialAdapter` and `ReadWorkflow`, not an ad hoc
  parser; persist local create-new evidence with raw bytes/hashes, CRC,
  sequence/uptime, sentinels/faults, timeout, open/close, disconnect/reconnect,
  and zero-write counters.
- Keep Protocol v1 parsing strict. A documented legacy HB line may be classified
  only out of profile, with exact syntax and matching TEL sequence/uptime;
  malformed, unaligned, or other no-CRC lines remain anomalies.
- Label exact firmware `UNCONFIRMED_PASSIVE_ONLY` when passive telemetry has no
  version field. Do not infer external sensors, fan, wiring, 5 V, or AFE status
  from controller connectivity.

## Deferred bench acceptance

- At least ten DC points per gain setting, with raw data retained.
- Real saturation limits determined before fitting.
- Oscilloscope stability evidence where permitted.
- Theoretical, SPICE, and bench values shown in separate columns.
- No target accuracy stated as achieved until uncertainty and repeatability are evaluated.
