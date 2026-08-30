# Software Phase 4 Step 2 — Neutral CRC Envelope and AFE Compatibility

**Date:** 2026-08-30<br>
**Checkpoint:** 2 of 8<br>
**Implementation commit:** `95c1432febdce70007daba013cae4cce47cf8556`<br>
**Evidence class:** HOST_TEST<br>
**Hardware used:** none<br>
**Serial ports opened:** none

## Outcome

Step 2 is complete. The formal package now separates device-neutral ASCII
token/CRC record handling from the historical AFE namespace requirement. The
existing AFE framing API delegates to the neutral implementation but retains
its public names, signatures, errors, length behavior, and exact serialized
bytes.

The checkpoint also freezes an explicit AFE channel-name mapping between the
historical telemetry vocabulary and the canonical Simulator/ReadWorkflow
vocabulary. Existing records are not silently renamed. A composite integration
test now takes irregular mixed AFE/MSP-shaped byte chunks through the Step 1
bounded stream and the Step 2 neutral envelope in receive order.

## Implemented boundaries

### Profile-neutral envelope

`analog_validation.protocol.envelope` provides:

- immutable payload fields without CRC or terminator;
- printable unquoted ASCII tokens with no comma or whitespace;
- LF output plus LF, CRLF, or already-delimited complete-record input;
- explicit rejection of bare/embedded line endings and non-ASCII input;
- strict four-character uppercase CRC-16/CCITT-FALSE;
- configurable positive record limit with a 128-byte default;
- typed `FramingError`, `FrameTooLong`, and `CrcMismatch` behavior;
- no namespace, message-family, sequence-width, unit, state, or capability
  interpretation.

### Backward-compatible AFE wrapper

`analog_validation.protocol.framing` now adds only the historical AFE shape
requirements over the neutral envelope:

- payload starts with `AFE`;
- payload includes at least namespace, type, and sequence;
- `Frame`, `MAX_RECORD_BYTES`, `encode_frame()`, and `decode_frame()` remain the
  same frozen public interface;
- Phase 1–3 top-level and `protocol.__all__` manifests remain unchanged.

The old 20 valid AFE records parse and re-encode byte-for-byte. The nine invalid
records retain their frozen error families. The deterministic synthetic stream
and all Phase 1–3 compatibility tests continue to pass.

### AFE channel mapping

`afe-channel-map.v1` freezes:

| Role | Canonical | Legacy telemetry v1 |
|---|---|---|
| input | `afe.chN.input` | `afe.chN.input_mv` |
| output | `afe.chN.output` | `afe.chN.output_mv` |
| gain | `afe.chN.gain` | `afe.chN.gain` |
| threshold | `afe.chN.threshold` | `afe.chN.threshold` |

Conversion requires typed source and target naming modes. Channel indices are
strict integers from 0 through 255. Unknown roles, wrong vocabulary, aliases,
and malformed names are rejected. The existing
`telemetry_to_measurements()` output remains legacy-compatible.

## Interoperability fixture scope

`profile_neutral_envelope_v1.json` contains one AFE-shaped and two
MSP430-shaped exact token/CRC records. The MSP430 shapes are derived only from
the peer project's documented UART Protocol v1 interface at commit
`151fdcfa60661bce1ba04af13c1d3509706f7d4a`; no source module or runtime
dependency was imported.

These fixtures prove only that the common envelope can carry the documented
byte shapes. They do not parse temperature, sentinel, fault, state, status, or
command semantics. That independent read-only business profile remains Step 5.

## Executed verification

| Gate | Actual result |
|---|---|
| Pre-change full regression | PASS — 1,079 tests |
| Step 2 new tests | PASS — 51 |
| Old AFE golden records | PASS — 20 valid + 9 invalid |
| Mixed Step 1 stream -> Step 2 envelope chain | PASS |
| Full pytest suite | PASS — 1,130 tests |
| Formal package statement coverage | PASS — 5,846/5,846, 100% |
| Envelope/channel-map/AFE-wrapper coverage | PASS — 176/176, 100% |
| Phase 2/3 public and exact-result compatibility | PASS |
| Full-repository Ruff | PASS |
| mypy on `src`, `dashboard`, `tools`, and `tests` | PASS — 110 files |
| Local dependency check | PASS — no broken requirements |
| Isolated sdist and wheel build | PASS — `0.1.0.dev0` |
| New modules/tests/golden fixture in artifacts | PASS |
| Repository-external wheel install | PASS |
| Installed-package envelope/mapping/stream/32-bit smoke | PASS |
| Serial, controller, or instrument test | NOT RUN |

## Corrected development checks

The first new focused run reported 153 passes and two failed test assertions.
One test had a manually mistyped CRC expectation; the implementation correctly
calculated `146F`. The other test expected a low-level Unicode encoding cause,
but the preserved token validator correctly rejected the non-ASCII token
earlier with `FramingError`. The test expectations were corrected and the
focused suite passed 155/155 before the composite integration case was added.

The first final mypy run then found one unannotated empty `issues` list in the
new integration test. It was typed as `list[StreamIssue]`; the affected 51 tests,
Ruff, and mypy all passed on rerun. Neither correction changed product behavior
or hid a failed legacy/production assertion.

## Evidence boundary

This checkpoint proves host-side bytes, token, CRC, naming conversion, frozen
AFE compatibility, package construction, and installed-package behavior. It
does not prove:

- OS serial discovery, timing, timeout, disconnect, or reconnect;
- UART baud rate, voltage levels, grounding, cable quality, or EMI behavior;
- AFE firmware/device interoperability;
- MSP430 business-profile parsing or formal Analog Studio HIL;
- any temperature, voltage, current, gain, threshold, bandwidth, or hardware
  performance.

The connected MSP430 LaunchPad was not accessed. No command was sent, no
firmware was flashed, and no FRAM or device state was changed.

## Next checkpoint

Step 3 will define a replaceable serial backend port and bounded raw-event
model, then test discovery/open/read/timeout/disconnect/limited-reconnect/close
behavior with an in-memory backend. Physical COM access remains deferred to the
owner-approved optional Step 7 HIL gate.
