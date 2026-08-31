# Software Phase 4 Step 6 Verification Report

**Date:** 2026-08-30 (America/New_York)<br>
**Checkpoint:** receive-only SerialAdapter and shared product-chain integration<br>
**Status:** complete within HOST_TEST scope<br>
**Physical serial/hardware access:** not run<br>
**Verified AFE hardware claims:** 0

**Implementation commit:** `d1c6bd11b25a81ec3e07c66008082442b485a6ff`

## Outcome

Step 6 is complete. Analog Validation Studio now has one receive-only
`SerialAdapter` composition that can place either the independent AFE v1
profile or the independent MSP430 Equipment Health v1 profile behind the same
frozen `DeviceAdapter` and `ReadWorkflow` contracts.

For a beginner, the new adapter is the controlled doorway between validated
serial messages and the rest of the product. The transport separates bytes,
the selected profile understands one device language, and the adapter exposes
only the safe, common read interface. Analysis and workflows still do not need
to know a COM number, packet field, controller register, or board SDK.

The checkpoint used only deterministic in-memory serial backends. It did not
enumerate or open a Windows COM port, use pyserial, access the connected MSP430,
send a command, flash firmware, change FRAM, inspect wiring, or measure an AFE.

## Implemented boundary

- `analog_validation.serial_adapters.SerialAdapterConfig` freezes explicit
  profile name/version plus finite poll and Measurement-buffer limits;
- `SerialAdapter` composes one closed `SerialSession`, one matching
  `SerialProfile`, and one explicit capability projector;
- profile/session/config name, version, and maximum-record limits must agree
  before I/O;
- public reads reuse the existing adapter lifecycle, capability, channel, unit,
  and evidence-source checks;
- raw events remain available as an immutable bounded snapshot, while the
  adapter separately exposes its retained native capability snapshot;
- transport open/read/close/reconnect failures become stable adapter errors
  with their original cause chained;
- every capability/read operation has a finite poll budget, and queued derived
  Measurements have a finite upper bound;
- successful reconnect clears profile state, queued Measurements, and both
  native/projected capability trust, then requires explicit reconfirmation.

The new public namespace is separate from the frozen Phase 2 top-level exports.
An architecture test prevents it from importing analysis, exports, runners,
workflows, Dashboard code, or pyserial.

## Receive-only safety contract

`SerialAdapter` v1 deliberately has no backend-write method, no public device
command method, and no generic escape hatch. Its projected commands may contain
only `READ_MEASUREMENT` and `READ_DIGITAL_STATE`, and it always exposes
`supports_safe_shutdown=False`.

AFE profile-native capability records may describe future DAC or PWM channels.
Step 6 preserves that native description for audit, but the adapter does not
gain a write path from it. The projector must not add commands, change device or
profile identity, drop/duplicate declared channel counts, or change numeric
ranges. A violating projector is rejected before the snapshot is trusted.

The independent MSP430 profile remains static and read-only. Its fan PWM value
is telemetry, not an AFE stimulus. DC-sweep and hysteresis runner tests use a
backend with no `write` method and confirm both runners return `UNSUPPORTED`
before any read or write.

## Explicit AFE capability projection

| Profile-native channel | Adapter/workflow channel |
|---|---|
| `adcN` | `afe.chN.input` |
| `dacN` | `afe.chN.dac` |
| `pwmN` | `afe.chN.pwm` |
| `dinN` | `afe.chN.threshold` |

This projection is separate from the historical telemetry mapper. It avoids
silently rewriting frozen wire records and keeps the native snapshot available
for debugging and future command-policy review.

AFE capabilities are received passively from a complete
`CAP DEVICE/CHANNEL/END` transaction. Step 6 sends no `CAP_REQ`; active
capability request/response belongs to a later explicitly reviewed write path.
MSP430 supplies its static read-only capabilities when the adapter connects.

## Product-chain proof

The AFE integration test executes:

```text
ValidationConfig
 -> SerialAdapter
 -> SerialSession / bounded raw events
 -> AfeV1SerialProfile
 -> native and projected DeviceCapabilities
 -> canonical analog/digital Measurements
 -> unchanged ReadWorkflow
 -> structured export-ready result with raw-record lineage
```

Two telemetry records supply two analog and two digital samples. All
Measurements remain `HOST_TEST`, and the raw event IDs are preserved. No new
generic workflow file format was invented in this checkpoint; a future exporter
must be separately versioned instead of being added implicitly.

The MSP430 integration test sends unavailable temperature/INA219 values through
the same adapter and workflow. The acquisition completes structurally, but the
affected Measurements remain `value=None`, `INVALID`, and missing. Completion
therefore does not convert unavailable device data into zero or an engineering
PASS.

## Executed verification

| Gate | Result |
|---|---|
| Step 6 focused unit/contract/integration files | PASS — 73 tests |
| Added architecture dependency gate | PASS — 1 test |
| Step 6 total new tests | PASS — 74 |
| Added formal-package statement coverage | PASS — 282/282, 100% |
| AFE SerialAdapter reusable contract | PASS — 8/8 shared checks |
| MSP430 SerialAdapter reusable contract | PASS — 8/8 shared checks |
| AFE config/adapter/raw/profile/workflow chain | PASS |
| MSP430 unavailable-safe adapter/workflow chain | PASS |
| Bad CRC, overlong, timeout, buffer and capability defenses | PASS |
| Open/read/close failure and reconnect invalidation | PASS |
| MSP430 DC runner degradation | PASS — `UNSUPPORTED`, 0 reads, 0 writes |
| MSP430 hysteresis runner degradation | PASS — `UNSUPPORTED`, 0 reads, 0 writes |
| Full pytest suite | PASS — 1,472 tests |
| Formal package statement coverage | PASS — 7,198/7,198, 100% |
| Full-repository Ruff | PASS |
| mypy on `src`, `dashboard`, `tools`, and `tests` | PASS — 140 files |
| Local dependency check | PASS — no broken requirements |
| Isolated sdist/wheel build | PASS — `0.1.0.dev0` |
| `serial_adapters` modules in wheel | PASS — 3/3 |
| Step 6 test files in sdist | PASS — 4/4 |
| Repository-external wheel install | PASS |
| Installed SerialAdapter -> ReadWorkflow smoke without pyserial | PASS |
| COM port, MSP430 board, command, firmware, FRAM, wiring, or BENCH operation | NOT RUN |

The authoritative full-suite command reached 1,472 passes in 7.75 seconds on
Python 3.12.10 for Windows. Package coverage was exactly 7,198/7,198 statements.

The isolated artifacts were:

| Artifact | Size | SHA-256 |
|---|---:|---|
| `mixed_signal_afe_validation_platform-0.1.0.dev0-py3-none-any.whl` | 151,327 bytes | `191B2F61FF033C47545E0CD3346325705F6B30AA7276417BB7A0A0526C1A06E6` |
| `mixed_signal_afe_validation_platform-0.1.0.dev0.tar.gz` | 262,990 bytes | `A7144153ACF72877038F1567F808108B78DC354FA342E47080FCC16961567B42` |

The external installation path was
`C:\Users\24046\afe-p4s6-external-20260830-2145\Lib\site-packages\analog_validation\__init__.py`.
The environment had no importable `serial` module. The installed wheel decoded
one generated MSP430 record through `SerialAdapter` and `ReadWorkflow`, returned
25.3 °C as `HOST_TEST`, retained one raw event, opened/read/closed once, and had
no backend write method.

## Corrected development checks

The first focused run reported 50 passes and one failed expectation. The test
expected only a naming error for `adc256`, while the implementation correctly
reported that 256 is outside the allowed 0–255 channel index. The expectation
was corrected; production code did not change for that result.

The first integration run reported seven passes and two failed assertions
because the tests read `missing_requirements` from the outer runner result
instead of `result.test_run_result`. The production runner already returned the
correct nested result. The test access path was corrected.

An early focused coverage run passed all then-current behavioral tests but
covered only 92% of the new package. Additional failure-path tests were added
for constructor, projection, profile output, buffer, transport, and reconnect
defenses; the threshold was not lowered. Ruff later found only import ordering
and one import-style rule, which were mechanically fixed.

The first external smoke script contained a hand-written tuple syntax error and
stopped before importing product code. The corrected script passed in the same
clean environment. These harness corrections are recorded rather than hidden
or relabeled as initial product passes.

## Evidence and ownership boundary

This checkpoint supports a claim that the receive-only adapter composition and
AFE/MSP430 public-interface paths are host-tested. It does not support a claim
of:

- Windows COM enumeration, pyserial behavior, OS timing, driver recovery, baud,
  cable, grounding, or UART electrical compatibility;
- current MSP430 firmware identity, current port assignment, external sensors,
  INA219, MOSFET, fan, 5 V behavior, or physical safe shutdown;
- AFE gain, cutoff, hysteresis, saturation, ADC/DAC, protection, noise,
  bandwidth, or any 0–3.3 V hardware range;
- ownership or inheritance of the peer MSP430 project's tests, FRAM/HIL/soak
  evidence, firmware, or product identity;
- a completed CLI, Dashboard, human report, production release, or hardware
  MVP.

No port was opened, no device command was sent, no board was flashed, and no
FRAM or wiring state was changed. `VERIFIED_BENCH` remains zero.

## Next checkpoint

Step 7 is an optional, separately authorized MSP430 receive-only HIL. Before it
can run, the owner must confirm the board's current public interface/firmware
identity and the correct unoccupied port, and the project must add and test a
minimal concrete OS backend. The HIL must record its own raw frames,
configuration, CRC/sequence/uptime, sentinel/fault meaning, timeout, close, and
disconnect behavior. It will send no command, flash nothing, change no FRAM,
and require no external sensor or fan wiring.

If those prerequisites are not safely established, Step 7 will be marked
`NOT RUN`. Step 8 can still freeze the host-compatible Phase 4 API and golden
results without making a physical compatibility claim.
