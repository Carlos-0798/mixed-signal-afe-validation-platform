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
└── ConfigurationError
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

The legacy `dashboard.protocol` exceptions remain unchanged until Software Phase 1 Step 5 migrates CRC and framing into the formal package. Maintaining this explicit boundary prevents two partially migrated protocol implementations from being treated as one verified API.

These error types describe software behavior only. They do not certify hardware ranges, wiring safety, communication reliability, or physical measurements.
