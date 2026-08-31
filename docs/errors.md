# Error Handling Contract

Analog Validation Studio exposes expected product-domain failures through `analog_validation.errors`. These exceptions let adapters, CLI commands, and the future Dashboard choose an appropriate response without parsing English error-message text.

## Hierarchy

```text
AnalogValidationError
├── ValidationError
├── ProtocolError
│   ├── FramingError
│   ├── FrameTooLong
│   ├── CrcMismatch
│   └── UnsupportedProtocolVersion
├── CapabilityError
├── ConfigurationError
├── ReplayError
│   ├── ReplayFormatError
│   │   └── UnsupportedReplayVersion
│   ├── ReplayLimitError
│   └── ReplayEndOfData
└── AdapterError
    ├── AdapterConnectionError
    ├── AdapterStateError
    └── AdapterDataError
```

| Error | Intended meaning |
|---|---|
| `AnalogValidationError` | Base class for an expected product-domain failure |
| `ValidationError` | Input or domain data failed validation |
| `ProtocolError` | Base class for an unacceptable protocol record |
| `FramingError` | Record envelope, encoding, delimiter, or field shape is invalid |
| `FrameTooLong` | Serialized record exceeds its protocol limit |
| `CrcMismatch` | Received and calculated CRC values differ |
| `UnsupportedProtocolVersion` | Record is valid enough to identify a version, but that version is unsupported |
| `CapabilityError` | Selected device did not declare the requested operation |
| `ConfigurationError` | Configuration is missing, inconsistent, or outside allowed policy |
| `ReplayError` | Base class for replay access, format, or resource-limit failures |
| `ReplayFormatError` | Replay CSV violates its declared structure or record semantics |
| `ReplayLimitError` | Replay input exceeds a byte, field, or record-count limit |
| `UnsupportedReplayVersion` | Replay input declares an unsupported schema version |
| `ReplayEndOfData` | One configured replay channel has no remaining records; this is an expected EOF condition |
| `AdapterError` | Base class for an expected adapter operation failure |
| `AdapterConnectionError` | Adapter-specific connect or disconnect failed |
| `AdapterStateError` | Operation is not permitted in the current lifecycle state |
| `AdapterDataError` | Adapter returned the wrong model, channel, unit, or evidence source |

## Catching errors

Catch the narrowest useful family first:

```python
from analog_validation import CrcMismatch, ProtocolError

try:
    read_record()
except CrcMismatch as error:
    mark_record_corrupt(str(error))
except ProtocolError as error:
    reject_record(str(error))
```

The future CLI/Dashboard may catch `AnalogValidationError` at its outer boundary and convert it into a concise user-facing message. Unexpected exceptions such as programming bugs must not be silently relabeled as user errors.

When wrapping a lower-level failure, use Python exception chaining:

```python
try:
    text = payload.decode("ascii")
except UnicodeDecodeError as error:
    raise FramingError("record must contain ASCII only") from error
```

This preserves a readable product message and the original diagnostic cause.

## Migration boundary

Software Phase 1 completed the one-time migration to `analog_validation.errors`. The retired `dashboard.protocol` and `dashboard.models` files no longer provide a second error or model surface. New adapters, profiles, runners, CLI commands, and the future Dashboard must use the formal exception hierarchy.

Software Phase 2 Step 1 adds stable adapter error families. The base adapter preserves known `AnalogValidationError` subclasses and wraps unexpected hook failures with exception chaining, so callers receive a stable product error without losing the original diagnostic cause.

Software Phase 2 Step 5 adds a separate replay family so malformed local datasets, bounded-resource rejection, and unsupported replay versions do not masquerade as live device or wire-protocol failures.

Software Phase 2 Step 6 adds `ReplayEndOfData` so normal replay completion is distinguishable from a malformed file, adapter state error, or unexpected I/O failure. Pause remains an `AdapterStateError` because data still exists but reads are temporarily disallowed.

These error types describe software behavior only. They do not certify hardware ranges, wiring safety, communication reliability, or physical measurements.

## Phase 4 transport-local errors

Software Phase 4 Step 3 adds a separate family exported from
`analog_validation.transport`. Keeping it in the transport namespace preserves
the frozen Phase 1–3 top-level API while still making every error a subclass of
`AnalogValidationError`:

```text
AnalogValidationError
├── SerialTransportError
│   ├── SerialStateError
│   ├── SerialDiscoveryError
│   ├── SerialOpenError
│   ├── SerialReadError
│   ├── SerialCloseError
│   ├── SerialReconnectError
│   ├── SerialBackendTimeout
│   └── SerialBackendDisconnected
└── RawEventError
    ├── RawEventLimitError
    └── RawEventNotFound
```

`SerialBackendTimeout` is handled as a normal no-data poll outcome;
`SerialBackendDisconnected` triggers bounded reconnect processing. They are
control signals from a replaceable backend, not evidence that a physical port
was tested. Backend exception details remain available through Python exception
chaining but are not copied automatically into persistent or user-visible raw
records.

See [serial transport and raw-event boundary](serial-transport.md) for the
lifecycle, retry, privacy, and resource-limit contract.

## Phase 4 profile-local errors

Software Phase 4 Step 4 adds `SerialProfileError` and
`SerialProfileStateError` under `analog_validation.profiles`. They describe a
wrong selected identity, mismatched/stale raw event, invalid result contract, or
unsupported evidence-source use. Expected wire problems remain the existing
`ProtocolError` family and are recorded as `REJECTED`; programming/profile-state
problems propagate instead of being mislabeled as bad device input. If raw-log
finalization fails, prior profile state is restored and the raw-log error
propagates.

Step 5 reuses the same split for the independent MSP430 profile. CRC, framing,
field count/type/range, unknown TEL state, and unsupported device-record family
are `ProtocolError` outcomes retained as raw `REJECTED` events. Wrong profile,
stale event/log, mapping-contract failure, and outcome-storage failure remain
profile/program state errors and are not presented as device faults. The wire
`fault_flags` field is device telemetry data, not a Python exception family.

See [serial profiles and independent AFE/MSP430 integrations](serial-profiles.md).

## Phase 4 SerialAdapter error translation

Software Phase 4 Step 6 keeps transport/profile details below the existing
`DeviceAdapter` public boundary:

- session open, close, fatal poll, and visible reconnect boundaries become
  `AdapterConnectionError` with the original transport exception chained;
- bounded poll exhaustion, invalid/changing capabilities, projector failure,
  invalid profile output, evidence mismatch, and measurement-buffer overflow
  become `AdapterDataError`;
- unsupported channels or commands continue to use the existing
  `CapabilityError` preflight rather than being mislabeled as communication
  failures;
- expected bad wire records remain raw `REJECTED` events and polling can
  continue within the configured finite budget.

A successful low-level reconnect is not hidden as a successful read. The
adapter clears buffered Measurements and capability trust, returns to
`CONNECTED_READ_ONLY`, and raises a visible connection error so the caller must
confirm capabilities again. These behaviors are HOST_TEST results from an
in-memory backend, not OS/UART reliability claims.

## Phase 5 product and report errors

The upward-only `analog_validation_app.errors` namespace owns expected product
orchestration failures without changing the core hierarchy. Step 4 adds this
report branch:

```text
ProductAppError
└── ProductReportError
    ├── ProductReportFormatError
    ├── ProductReportLimitError
    └── ProductReportPathError
        └── ProductReportExistsError
```

Format/limit and result-loader errors map to the stable `INPUT_DATA` user issue.
An unusable publication parent or atomic-write failure maps to `OUTPUT_PATH`,
while an existing destination maps to `OUTPUT_EXISTS`. The ordering matters
because `ProductReportExistsError` is also a path error; it must retain the more
specific no-overwrite guidance.

Unexpected renderer defects are not relabelled as malformed user data. Normal
CLI mode emits a bounded `user-issue.v1`; `--debug` remains the explicit path to
developer diagnostics. See [human reports](human-reports.md) and
[product CLI](product-cli.md).
