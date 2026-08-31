# Known limitations — `0.1.0b1`

These limits are part of the product contract, not hidden footnotes.

## Release and distribution

- This is private beta candidate preparation, not v1.0 or production-ready.
- No Git tag, GitHub Release, PyPI publication, signed installer, automatic
  update channel, or public download has been approved.
- No public license has been selected. The repository remains all rights
  reserved; a tester may use only the separately agreed private-test scope.
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
- DC and hysteresis have finalized TestRun/export/report mappings. Calibration
  and frequency-response math exist, but do not yet have dedicated product
  TestRun/export/report workflows.
- Timing targets are usability measurements, not hard real-time guarantees or
  long-duration soak evidence.
- The product is not a safety controller, medical device, calibration
  laboratory system, or certified measurement instrument.

## Serial and controller compatibility

- pyserial is optional and absent from the base wheel.
- The product serial boundary is receive-only, but OS port open can still
  affect control lines; physical use needs a separate approved procedure.
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
