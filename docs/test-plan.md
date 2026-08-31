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

## Software Phase 4 compatibility closure checks

- Freeze exact `__all__` exports for transport, envelope, channel mapping,
  MSP430 protocol, profiles, serial adapters, and optional pyserial integration.
- Freeze new schema strings, serial-profile identities, public enum/flag
  members, primary constructor/function parameter shapes, and owned error
  inheritance relationships.
- Hash prior AFE/envelope/MSP430 fixtures plus one exact Phase 4 composite; do
  not hash the manifest itself.
- Rebuild AFE and MSP430 product chains from an independently defined
  structural backend using only public interfaces.
- Preserve 16/32-bit sequence wrap, canonical channels, raw lineage, typed CRC
  rejection, unavailable sentinel/fault mapping, `HOST_TEST` provenance,
  deterministic close, and absence of a write method.
- Rerun every Phase 1–3 golden contract before accepting the Phase 4 freeze.
- Require full pytest, 100% formal+optional package coverage, Ruff, mypy,
  dependency checks, isolated sdist/wheel build, archive-content inspection,
  and clean base/serial wheel installations.
- Keep the Step 7 physical UART capture separate; Step 8 discovery/build/install
  checks must not be reported as a repeated HIL or AFE/peripheral validation.

## Software Phase 5 product-layer checks

- **Step 1 complete:** keep `analog_validation_app` above the frozen core and
  optional OS backend; reject imports from the core back into the product layer
  and copied protocol/analysis implementations in the product package.
- **Step 1 complete:** run CLI help/version/profile commands from an installed
  base wheel without pyserial and without importing Tk or opening a display;
  verify unknown-command exit/output behavior and the module entry point.
- **Step 1 complete:** freeze bounded job/result/catalog/issue/CLI-output schema
  identities, require limitations, and reject output-capable product requests.
- Freeze versioned product request/result/event contracts, bounded field sizes,
  worker states, public errors, CLI commands, stdout/stderr rules, and exit
  codes before calling the complete CLI stable. Event/worker and workflow
  commands remain future checks.
- Verify one worker owns one job and all success, cancellation, service-failure,
  cleanup-failure, window-close, and Ctrl+C paths release resources and never
  promote incomplete evidence to PASS.
- Bound the worker event queue, event text, job duration/record count, and join
  wait; a slow Dashboard must not cause unbounded memory or an orphan thread.
- Exercise Simulator, CSV Replay, and receive-only SerialAdapter product chains
  through the same application service. Serial tests use an in-memory backend
  unless a separate physical-HIL authorization is recorded.
- Require explicit port, profile, duration/record bounds, and read-only review
  for `observe`; do not expose a write method, raw command box, automatic port
  choice, or capability inference from a USB name.
- Build human report and chart view models only from finalized product/core
  results. Do not refit points, recalculate thresholds, or change outcome or
  provenance in presentation code.
- Freeze self-contained local HTML/SVG output with no remote resources; display
  evidence, limitations, not-verified items, versions, input identifiers, and
  artifact hashes using text as well as visual status.
- Test Dashboard state/presenter headlessly. Keep Tk imports inside the widget
  boundary and route all UI updates through main-thread polling of immutable
  bounded events.
- Verify create-new output by default, explicit overwrite behavior, hostile
  paths/text/Unicode, sensitive raw-data exclusion, and no network activity.
- Run the deterministic installed-package demo in a new directory and compare
  exact machine/result/report/plot manifest hashes.
- Before Phase 5 closure, require full pytest and coverage, Ruff, mypy,
  dependency checks, sdist/wheel inspection, base/serial external installs,
  CLI/demo smoke, and a real Windows Dashboard launch/close smoke or an honest
  `NOT RUN` record.
- Keep the earlier controller UART HIL in its own report. Product UI tests and
  screenshots are not AFE, peripheral, electrical-safety, timing, or long-run
  hardware evidence.

## Deferred bench acceptance

- At least ten DC points per gain setting, with raw data retained.
- Real saturation limits determined before fitting.
- Oscilloscope stability evidence where permitted.
- Theoretical, SPICE, and bench values shown in separate columns.
- No target accuracy stated as achieved until uncertainty and repeatability are evaluated.
