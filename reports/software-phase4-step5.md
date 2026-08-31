# Software Phase 4 Step 5 Verification Report

**Date:** 2026-08-30 (America/New_York)<br>
**Checkpoint:** independent read-only MSP430 Equipment Health v1 profile<br>
**Status:** complete within HOST_TEST scope<br>
**Physical serial/hardware access:** not run<br>
**Verified AFE hardware claims:** 0

**Implementation commit:** `c446afa4637ef083704102b6e4bbcdfdec256195`

## Outcome

Step 5 is complete. Analog Validation Studio now contains its own read-only
`msp430-equipment-health.v1` interoperability implementation. It was derived
from the peer product's public UART Protocol v1 document at commit
`151fdcfa60661bce1ba04af13c1d3509706f7d4a`; no peer runtime module, firmware,
Dashboard, test count, HIL result, or repository history was copied into this
product.

The implementation parses device-output `TEL`, `ACK`, `STS`, `CFG`, and `LOG`
records. It deliberately provides no command encoder, performs no port I/O, and
advertises no output or safe-shutdown capability.

## Implemented boundary

- `protocol/msp430_health_v1.py` defines immutable typed device-output records,
  strict field/range/state/CRC parsing, exact output re-encoding, fault-bit
  names, raw availability properties, and Measurement mapping;
- `profiles/msp430_health_v1.py` defines explicit profile identity, 32-bit TEL
  continuity, typed raw parsed/rejected outcomes, mapping, reset, and rollback;
- `test-data/golden/msp430_equipment_health_v1.json` records the exact public
  interface reference plus 10 valid and 11 invalid repository-owned fixtures;
- focused unit, golden, integration, and architecture tests cover the new
  parser/profile without importing the peer project's runtime namespace;
- the existing `analog_validation.profiles` extension point now exports both
  independent AFE and MSP430 profile implementations.

The MSP430 wire record itself has no version token. Version selection is
therefore explicit profile context, not inferred from `TEL`, COM number, USB
identity, or a board name.

## Availability and unit semantics

| Wire condition | Domain outcome |
|---|---|
| temperature `-32768` | `value=None`, `INVALID`, `MISSING` |
| DS18B20 missing/CRC | DS Measurement unavailable; raw deci-degree value retained |
| NTC range fault | NTC Measurement unavailable with `OUT_OF_RANGE`; raw retained |
| sensor disagreement | otherwise available temperature is `SUSPECT + DEVICE_FAULT` |
| INA219 communication fault | bus voltage/current are missing and invalid with communication/device flags |
| zero electrical fields without INA219 fault | valid true zero |
| fan PWM | read-only ratio; never an AFE stimulus |

`Msp430Telemetry` always retains raw temperature, voltage, current, power, PWM,
state, and the complete 16-bit fault field. `power_mw` also follows the INA219
availability property, but Measurement v1 does not define a watt/milliwatt
unit. Step 5 therefore does not mislabel it as `UNITLESS`; TD-031 records the
future schema decision.

The static `DeviceCapabilities` record contains only `READ_MEASUREMENT`, has no
DAC/PWM output channels, and sets `supports_safe_shutdown=False`. Its input
ranges are Protocol v1 representable software bounds, not measured electrical
safety limits, calibrated sensor limits, or detected hardware.

## Executed verification

| Gate | Result |
|---|---|
| Step 5 focused tests | PASS — 120 tests |
| Added architecture independence gate | PASS — 1 test |
| New protocol/profile module coverage | PASS — 416/416 statements, 100% |
| Valid independent fixtures | PASS — 10/10 exact parse/re-encode |
| Invalid independent fixtures | PASS — 11/11 typed error family/meaning |
| Temperature sentinel and INA219 fault mapping | PASS — false zeros excluded |
| 32-bit TEL continuity and `4294967295 -> 0` | PASS |
| ACK/STS/CFG/LOG correlation excluded from TEL continuity | PASS |
| Memory backend -> session -> MSP430 profile composite chain | PASS |
| Peer runtime namespace import gate | PASS |
| Full pytest suite | PASS — 1,398 tests |
| Formal package statement coverage | PASS — 6,916/6,916, 100% |
| Frozen Phase 1–3 API and exact results | PASS |
| Full-repository Ruff | PASS |
| mypy on `src`, `dashboard`, `tools`, and `tests` | PASS — 133 files |
| Local dependency check | PASS — no broken requirements |
| Isolated sdist/wheel build | PASS — `0.1.0.dev0` |
| MSP430 protocol/profile modules in wheel | PASS — 2/2 |
| Step 5 fixture/test artifacts in sdist | PASS — 5/5 |
| Repository-external wheel install and `pip check` | PASS |
| Installed raw -> MSP430 profile -> unavailable-safe Measurement smoke | PASS |
| Installed smoke without pyserial | PASS — `serial` module absent |
| COM port, MSP430 board, command, firmware, FRAM, or BENCH operation | NOT RUN |

The authoritative import resolved to the external environment's
`site-packages/analog_validation/__init__.py`, outside the repository; the
personal absolute path is intentionally omitted. The smoke generated two records through the installed
encoder, crossed `4294967295 -> 0`, verified four unavailable Measurements plus
valid zero PWM, and confirmed read-only/no-safe-shutdown capabilities.

## Corrected development checks

The first full regression after implementation passed 1,397 tests and failed
one explicit `profiles.__all__` assertion because that same-Phase-4 contract
still listed only AFE exports. The expected list was updated to include the new
MSP430 identity, sequence-width constant, and profile class. The authoritative
rerun passed all 1,398 tests with 100% package coverage; no Phase 1–3 frozen API
manifest changed.

The first focused coverage run passed all 119 then-current focused tests but
showed two uncovered statements in the Unicode-string framing rejection. A
direct non-ASCII string case was added. The authoritative focused run passed
120 tests and covered both new modules completely.

The wheel built and installed successfully on the first attempt. The first
external smoke then failed because the smoke command itself contained two
hand-written, incorrect CRC values (`C692` and `C676`); the installed profile
correctly rejected them and reported expected CRC values `7147` and `AAAA`.
The smoke was rerun in the same clean installed environment using the installed
formal encoder and passed. The failed smoke is not relabeled as a product pass.

## Evidence and ownership boundary

This checkpoint supports only a claim of host-tested byte/model compatibility
with the frozen public MSP430 UART Protocol v1 interface. It does not support a
claim of:

- real COM/pyserial/UART timing, reconnect, baud, voltage, grounding, or cable
  compatibility;
- current board firmware identity or current COM assignment;
- MSP430 external DS18B20, NTC, INA219, MOSFET, fan, or 5 V bench behavior;
- any AFE gain, cutoff, hysteresis, saturation, ADC/DAC, protection, or physical
  safe-shutdown behavior;
- ownership of the peer project's 176 tests, FRAM evidence, LaunchPad HIL, or
  two-hour soak result;
- a merge, parent/child relationship, or shared product identity between the
  two independent repositories.

No port was opened, no device command was sent, no board was flashed, and no
FRAM or wiring state was changed. `VERIFIED_BENCH` remains zero.

## Next checkpoint

Step 6 will implement `SerialAdapter` over the existing session/raw/profile
ports and pass it through the shared `DeviceAdapter` and `ReadWorkflow`
contracts with an in-memory backend. It must explicitly project AFE capability
names and prove the read-only MSP430 path returns `UNSUPPORTED` with zero writes
for output-controlled DC and hysteresis runners. Real port access remains an
owner-approved Step 7 action.
