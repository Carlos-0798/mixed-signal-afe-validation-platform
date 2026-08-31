# Test plan and evidence labels

## Evidence labels

- `THEORY`: result derived from a documented equation and nominal inputs.
- `SPICE_IDEAL`: result produced by the included idealized LTspice netlists.
- `SYNTHETIC`: data generated in software to test analysis paths.
- `HOST_TEST`: executable Python test result.
- `BENCH`: future physical measurement with recorded wiring and instruments.

Only `BENCH` evidence may support claims about physical hardware. Phase 0 can produce the first four labels only.

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
- Keep real port/HIL commands `NOT RUN` until the separate owner-approved gate;
  host lifecycle tests do not prove OS timing, UART electrical behavior, or a
  controller business profile.

## Deferred bench acceptance

- At least ten DC points per gain setting, with raw data retained.
- Real saturation limits determined before fitting.
- Oscilloscope stability evidence where permitted.
- Theoretical, SPICE, and bench values shown in separate columns.
- No target accuracy stated as achieved until uncertainty and repeatability are evaluated.
