# Known limitations — `0.1.0b1`

These limits are part of the product contract, not hidden footnotes.

## Release and distribution

- This is private beta candidate preparation, not v1.0 or production-ready.
- No Git tag, GitHub Release, PyPI publication, signed installer, automatic
  update channel, or public download has been approved.
- The owner selected the MIT License; it is included in `LICENSE`. Licensing
  does not imply that a public release or a hardware test has been performed.
- CI artifacts have bounded retention and are not a permanent distribution
  channel.

## Supported environments

- Host tests cover current GitHub Windows/Ubuntu runners with Python 3.10,
  3.12, and 3.14; this does not imply every OS/Python minor combination.
- The full deterministic candidate job is verified on Windows/Python 3.12.
- The current Windows/Python 3.12 candidate uses Tk 8.6.15. That runtime has no
  `tk accessible` API, and a Windows UI Automation audit exposed the 37
  application descendants only as unnamed panes. The Dashboard is therefore
  not supported for screen-reader operation in this candidate. A runtime-gated
  Tk 9.1 metadata adapter is present, but it cannot become verified support
  until a compatible runtime passes UI Automation, Narrator, dynamic-status,
  and real-user tests. The CLI is the current text interface; it has not yet had
  a formal screen-reader user study.
- TD-043B2A2 selected PySide6 Essentials/Qt Widgets as a Proposed migration
  candidate after an isolated UI Automation prototype succeeded. It is not a
  production dependency: package size, LGPL/third-party notices, deterministic
  installation, accessibility events, Narrator/NVDA, and feature parity still
  require approval and verification.
- macOS and Linux GUI behavior, all display servers, and other
  assistive-technology combinations are not verified.
- Windows installations can still fail when a user chooses a path that is too
  deep for legacy path limits; use a short beta root.

## Product behavior

- The required product path is local and single-user. There is no server,
  account, database, cloud synchronization, telemetry upload, collaboration,
  or remote report hosting.
- The Dashboard is a local optional Tk shell; CLI workflows remain the required
  headless path.
- DC, hysteresis, linear calibration, and frequency response have finalized
  TestRun/export/report product mappings for Simulator and CSV Replay.
- Bounded live monitoring is available for Simulator, CSV Replay, and the
  receive-only Serial source. It ends after a reviewed finite cycle count,
  retains at most 10,000 recent points, and intentionally produces no
  engineering PASS/FAIL or analysis export. The Serial path has only
  memory-backend evidence in this increment.
- Frequency response is amplitude-only and consumes explicit frequency/input/
  output-amplitude points. It does not estimate frequency from waveforms,
  calculate phase, perform FFTs, control a signal source or oscilloscope, or
  validate physical bandwidth.
- Calibration coefficient loading is validation/inspection only. Automatic
  application to later data, firmware persistence, traceable-instrument
  records, expiry, revocation, and bench calibration remain unimplemented.
- Timing targets are usability measurements, not hard real-time guarantees or
  long-duration soak evidence.
- Live pause/resume is cooperative at safe checkpoints. Host scheduling,
  visible-window rendering, and expected ring-buffer eviction do not prove
  transport timing, physical sampling cadence, or loss-free device operation.
- The product is not a safety controller, medical device, calibration
  laboratory system, or certified measurement instrument.
- Versioned projects, presets, bounded sequential batches, explicit history,
  and two-run comparison are available through the public API, CLI, and the
  Dashboard Projects & history tab. The UI supports adding the current setup
  as a preset, saving a new project copy, real per-preset progress, cooperative
  batch cancellation, cleanup-before-close, and terminal history refresh.
  In-place preset editing and graphical trace overlays remain deferred.
- Project history is local files, not a database. Users choose every project,
  run destination, and manifest input; there is no automatic discovery,
  retention policy, synchronization, multi-user locking, or cloud backup.
- Run history preserves an exact project snapshot and configuration/result
  SHA-256 values. These detect changes relative to the manifest but are not a
  signature, authenticated author identity, trusted timestamp, or access-control
  system.
- READ and LIVE_MONITOR history currently records terminal status, evidence,
  counts, limitations, and bounded metrics rather than publishing raw
  observation streams. Analysis workflows retain their strict result artifacts.
- Batch execution is sequential and local. There is no concurrent scheduler,
  retry policy, dependency graph, unattended real-device queue, or remote agent.

## Serial and controller compatibility

- pyserial is optional and absent from the base wheel.
- The product serial boundary is receive-only, but OS port open can still
  affect control lines; physical use needs a separate approved procedure.
- `SERIAL_READ_ONLY` supports bounded `READ` and finite `LIVE_MONITOR`. Serial
  monitoring defaults to one primary channel, rejects a combined cadence and
  worst-case receive-wait budget above 55 seconds, performs no automatic
  reconnect, and fails closed on timeout or disconnect. No real port was opened
  to implement or verify this increment.
- Without an explicit product mapping, the established AFE v1 capability
  projection still advertises native `adcN` as `afe.chN.input`; an unadvertised
  output trace remains `UNSUPPORTED` before telemetry acquisition.
- AFE v1 can opt into a versioned dual-trace mapping only when an exact expected
  capability `device_id` is supplied and every device-advertised native ADC is
  mapped exactly once to a unique canonical `afe.chM.input|output` channel. A
  mismatch or incomplete/extra mapping stops before measurement telemetry.
- The reported capability ID is unauthenticated and may be stale, duplicated,
  spoofed, or misconfigured. It is not a physical serial number. The mapping is
  reviewed software metadata and cannot prove physical wiring. The MSP430
  profile currently exposes a static host capability identity rather than a
  firmware-unique value.
- One narrow MSP430 controller UART/Profile capture exists. It does not verify
  exact firmware, long-duration reliability, physical reconnect, external
  sensors, fan, INA219 behavior, wiring, or the future AFE.
- MSP430 compatibility is through a public profile between independent peer
  products. Neither repository is a component or subordinate of the other.

## Hardware evidence

- Configurable AFE hardware has not been purchased, assembled, wired, powered,
  or bench-measured in this software release path.
- Verified AFE gain, offset, saturation, cutoff, hysteresis, ADC/DAC accuracy,
  noise, protection, bandwidth, safety, and reliability claims remain zero.
- `SYNTHETIC`, `CSV_REPLAY`, `HOST_TEST`, package, CI, and demo PASS results do
  not become `BENCH_*` evidence.
- No OSU Lab Bench Monitor Capstone material or claim is part of this product.
