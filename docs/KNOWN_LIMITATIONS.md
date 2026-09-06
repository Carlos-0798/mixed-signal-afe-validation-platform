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
- macOS, Linux GUI behavior, screen readers, all display servers, and every
  assistive-technology combination are not verified.
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
- Bounded live monitoring is available for Simulator and CSV Replay only. It
  ends after a reviewed finite cycle count, retains at most 10,000 recent
  points, and intentionally produces no engineering PASS/FAIL or analysis
  export.
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

## Serial and controller compatibility

- pyserial is optional and absent from the base wheel.
- The product serial boundary is receive-only, but OS port open can still
  affect control lines; physical use needs a separate approved procedure.
- `SERIAL_READ_ONLY` supports bounded `READ`, not `LIVE_MONITOR`; no real port
  was opened to implement or verify the live-view increment.
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
