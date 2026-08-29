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

## Deferred bench acceptance

- At least ten DC points per gain setting, with raw data retained.
- Real saturation limits determined before fitting.
- Oscilloscope stability evidence where permitted.
- Theoretical, SPICE, and bench values shown in separate columns.
- No target accuracy stated as achieved until uncertainty and repeatability are evaluated.

