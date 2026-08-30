"""Public package for Analog Validation Studio.

The package is controller-neutral: importing it must not require a serial
driver, GUI toolkit, board SDK, or physical hardware.
"""

from .domain import (
    CAPABILITY_SCHEMA_VERSION,
    MEASUREMENT_SCHEMA_VERSION,
    TEST_RUN_SCHEMA_VERSION,
    ChannelRange,
    DeviceCapabilities,
    DeviceCommand,
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
    QualityFlag,
    SafeRange,
    TestRunMetadata,
    TestRunOutcome,
    TestRunResult,
)
from .errors import (
    AnalogValidationError,
    CapabilityError,
    ConfigurationError,
    CrcMismatch,
    FrameTooLong,
    FramingError,
    ProtocolError,
    UnsupportedProtocolVersion,
    ValidationError,
)
from .version import __version__

__all__ = [
    "CAPABILITY_SCHEMA_VERSION",
    "MEASUREMENT_SCHEMA_VERSION",
    "TEST_RUN_SCHEMA_VERSION",
    "AnalogValidationError",
    "CapabilityError",
    "ChannelRange",
    "ConfigurationError",
    "CrcMismatch",
    "DeviceCapabilities",
    "DeviceCommand",
    "EvidenceSource",
    "FrameTooLong",
    "FramingError",
    "Measurement",
    "MeasurementStatus",
    "MeasurementUnit",
    "ProtocolError",
    "QualityFlag",
    "SafeRange",
    "TestRunMetadata",
    "TestRunOutcome",
    "TestRunResult",
    "UnsupportedProtocolVersion",
    "ValidationError",
    "__version__",
]
