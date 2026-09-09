# Serial Device Contract Readiness

**Date:** 2026-09-06<br>
**Branch baseline:** `codex/calibration-workflow` at committed parent `bf8c4c6`<br>
**Change state:** local and uncommitted<br>
**Evidence:** `HOST_TEST` with in-memory Serial backends<br>
**Physical serial/AFE validation:** not run

## Outcome

The receive-only product path now supports two optional, explicit controls that
prepare a real AFE integration without guessing device or channel meaning:

1. exact comparison of an expected capability `device_id` before measurement
   reads; and
2. `serial-channel-alias.v1`, a bounded AFE v1 mapping from every advertised
   native `adcN` channel to one unique canonical `afe.chM.input|output`
   observation.

The established no-alias behavior remains `adcN` → `afe.chN.input`. The new
mapping cannot add channels, ranges, write commands, or safe-shutdown support.

## Fail-closed behavior

The software rejects the reviewed job when any of these conditions occurs:

- the reported capability ID differs from the optional expected ID;
- aliases are supplied without an expected ID or for a non-AFE profile;
- an alias has an unknown shape, a leading-zero index, or an index outside
  0–255;
- a native or canonical channel is repeated;
- the aliases do not cover the advertised ADC set exactly; or
- a mapped ADC name collides with another projected channel category.

Profile misuse and malformed aliases fail before a backend is constructed.
Identity mismatch and incomplete/extra coverage fail after the bounded
capability response but before the first measurement telemetry read.

## Product surfaces

- `SerialSourceConfig` carries a versioned expected-ID/mapping contract.
- `SerialChannelAlias.parse()` provides deterministic
  `native=canonical` parsing for CLI and Dashboard use.
- `observe` and `serial monitor` expose `--expected-device-id` and repeatable
  `--afe-adc-alias` options.
- Dashboard Review shows the exact ID and mappings before Run.
- Successful CLI human/JSON and Dashboard observation views show the accepted
  capability device/profile identity and readable channels.
- The public Phase 5 contract freezes 17 schemas, 41 dataclass shapes, 41 public
  signatures, 26 CLI paths, and the new identity/mapping bounds.

## Verification executed

| Gate | Result |
|---|---|
| Focused factory/live/CLI/Dashboard/public-contract suite | 248 passed |
| Full pytest and statement-coverage gate | 2,508 passed; 14,006/14,006 package statements; 100% |
| Ruff | Passed |
| mypy | Passed across 218 source files |
| Dependency consistency | `pip check` passed |
| Product-quality acceptance | 15/15 passed |
| 10,000-point live buffer | 0.175368 s; 1.338 MiB traced peak; 2,048 retained; 7,952 evictions accounted |
| 10,000-record Replay | 0.509990 s; 13.102 MiB traced peak |
| Distribution build | Wheel and sdist built successfully from the local tree |
| Repository-external base-wheel install | Version `0.1.0b1`, public alias import, `serial monitor --help`, and invalid-alias fail-fast checks passed |

The timing values describe this one Windows 11 / CPython 3.12.10 host run. They
are not real-time, cross-platform, serial-throughput, or device-reliability
claims.

## Evidence boundary

- No serial port was enumerated or opened.
- No MSP430 or AFE controller was read, reset, flashed, or written.
- Tests used injected in-memory backends and made zero application write calls.
- A matching `device_id` is not authentication; a device or configuration can
  duplicate, spoof, or misreport it.
- An ADC alias is reviewed host metadata. It does not prove firmware behavior,
  PCB routing, jumper placement, physical wiring, signal identity, accuracy, or
  voltage safety.
- The MSP430 profile currently uses a static host capability snapshot; its ID
  is not a unique value reported by the attached firmware.
- AFE hardware-performance claims remain zero.

## Deferred closure

Before a real-device reliability claim, the project still needs exact firmware
and wiring confirmation, a device-specific receive-only/open-control-line risk
review, passive short-run evidence, deliberate disconnect/reconnect behavior,
measured data-rate/drop accounting, and 30-minute/2-hour soak tests. Those steps
require separate user authorization and `BENCH` evidence.

Formal commit-bound release-candidate/audit and hosted CI were not run because
this checkpoint is intentionally local and uncommitted. No push, merge, tag,
Release, package publication, GitHub metadata change, or hardware access
occurred.
