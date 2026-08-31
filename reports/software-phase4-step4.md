# Software Phase 4 Step 4 — AFE v1 Serial Profile

**Date:** 2026-08-30<br>
**Checkpoint:** 4 of 8<br>
**Implementation commit:** `dd4ca666d7903c622eec103441524cbb3c174790`<br>
**Evidence class:** HOST_TEST<br>
**Hardware used:** none<br>
**Serial ports opened:** none<br>
**pyserial required:** no

## Outcome

Step 4 is complete. The formal package now exposes a controller-neutral serial
profile contract plus an independent `AfeV1SerialProfile`. The AFE profile
connects Step 3 raw events to the frozen AFE v1 decoder, 16-bit telemetry
continuity, canonical Measurement channels, multi-record capability exchange,
and explicit parsed/rejected raw outcomes.

The implementation uses only the scripted in-memory backend. It did not access
the connected MSP430, any COM port, firmware, FRAM, AFE circuit, external
component, wire, supply, or laboratory instrument.

## Implemented boundaries

### Generic profile extension point

`analog_validation.profiles` adds:

- immutable `SerialProfileIdentity` with explicit name/version/sequence width/
  record limit;
- generic `SerialProfile` and `SerialProfileRecord` contracts;
- reset diagnostics for sequence and incomplete multi-record state;
- typed profile-state failures separate from malformed wire records.

The dependency-direction test confirms that transport cannot import profiles or
higher product layers, while profiles cannot import adapters, analysis,
runners, or workflows.

### AFE v1 implementation

The AFE identity is `afe`, version `1`, 16-bit sequence, 128-byte maximum. The
profile reuses the existing protocol implementation rather than reimplementing
CRC, field validation, capability safety, or Measurement construction.

Telemetry crosses the explicit `LEGACY_TELEMETRY_V1 -> CANONICAL` channel
mapping and retains typed units, received UTC time, quality, fault state, raw
record identity, and caller-selected evidence source. Commands are decoded but
do not produce Measurements.

Telemetry alone advances continuity. Command sequences and the repeated
capability-response sequence are correlation values. Capability `DEVICE`,
`CHANNEL`, and `END` records are aggregated strictly and publish a snapshot only
after the whole response is valid.

### Error and recovery behavior

Expected protocol failures become bounded `REJECTED` raw outcomes and do not
publish derived data. Caller/state problems remain exceptions instead of being
misrepresented as bad device input. Failed raw-log finalization restores prior
sequence/capability state. Reset explicitly reports the telemetry high-water
mark and incomplete records it discarded.

Capability output retains the frozen AFE wire vocabulary
`adcN/dacN/pwmN/dinN`, preserving existing command-safety behavior. A future
SerialAdapter must project adapter-facing channel names explicitly instead of
guessing or mutating this contract.

## Composite proof

The Step 4 memory integration exercises:

```text
fragmented/coalesced bytes
 -> SerialSession + bounded LF records
 -> PENDING_PROFILE raw log
 -> AfeV1SerialProfile
 -> 16-bit 65535-to-0 wrap
 -> canonical Measurements
 -> completed read-only capabilities
 -> CRC REJECTED without sequence advance
```

Exact input bytes remain attached to all accepted and rejected outcomes.

## Executed verification

| Gate | Actual result |
|---|---|
| Pre-change full regression | PASS — 1,218 tests |
| Step 4 added tests | PASS — 59 |
| Generic profile contract/invariants | PASS |
| AFE telemetry canonical mapping and provenance | PASS |
| 16-bit first/in-order/gap/duplicate/out-of-order/wrap | PASS |
| Command correlation excluded from telemetry continuity | PASS |
| Capability aggregation, recovery, and safety regression | PASS |
| Raw-log outcome failure rollback | PASS |
| 20 valid AFE golden records through serial profile | PASS — exact re-encode |
| 9 invalid AFE golden records through serial profile | PASS — error contracts retained |
| Memory backend -> session -> AFE profile composite chain | PASS |
| Full pytest suite | PASS — 1,277 tests |
| Formal package statement coverage | PASS — 6,499/6,499, 100% |
| Step 4 formal package increase | PASS — 225/225 statements, 100% |
| Frozen Phase 1–3 API and results | PASS |
| Core standard-library and one-way dependency boundary | PASS |
| Full-repository Ruff | PASS |
| mypy on `src`, `dashboard`, `tools`, and `tests` | PASS — 127 files |
| Local dependency check | PASS — no broken requirements |
| Isolated sdist/wheel build | PASS — `0.1.0.dev0` |
| Four profile runtime modules in wheel | PASS |
| New golden/profile tests in sdist | PASS |
| Repository-external wheel install and `pip check` | PASS |
| Installed raw -> AFE profile -> canonical Measurement smoke | PASS |
| Installed smoke without pyserial | PASS — `serial` module absent |
| OS serial, controller, instrument, or BENCH test | NOT RUN |

## Corrected development checks

The first focused mypy run rejected a covariant profile type variable because
the immutable result generic is invariant. The public protocol was corrected to
use an invariant message type; no runtime behavior was changed.

The first focused coverage run passed all tests but measured 99.56% for the new
namespace because the internal non-printable identity branch had not been
executed. A direct embedded-newline case was added; the authoritative full run
then covered all 6,499 formal statements. Ruff also identified one unused test
import and one preferred import form during development; both were corrected
before the final gate. Intermediate diagnostics were not relabeled as passes.

## Evidence boundary

This checkpoint supports a claim of host-tested AFE v1 serial-profile software
compatibility. It does not support a claim of:

- physical AFE or controller validation;
- real UART/COM/pyserial operation;
- measured gain, offset, cutoff, hysteresis, saturation, ADC/DAC, noise, or
  protection performance;
- physical safe shutdown;
- MSP430 Equipment Health protocol compatibility;
- inherited evidence from the peer MSP430 project.

`VERIFIED_BENCH` remains zero.

## Next checkpoint

Step 5 will implement this repository's independent, read-only
`msp430-equipment-health.v1` profile from the peer project's frozen public UART
contract and copied interoperability fixtures. It will use 32-bit telemetry
sequence semantics, preserve unavailable sentinels/faults, expose no stimulus
or safe-shutdown capability, import no MSP430 repository code, and still avoid
physical COM access.
