"""Public package for Analog Validation Studio.

The package is controller-neutral: importing it must not require a serial
driver, GUI toolkit, board SDK, or physical hardware.
"""

from .domain import (
    MEASUREMENT_SCHEMA_VERSION,
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
    QualityFlag,
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
    "MEASUREMENT_SCHEMA_VERSION",
    "AnalogValidationError",
    "CapabilityError",
    "ConfigurationError",
    "CrcMismatch",
    "EvidenceSource",
    "FrameTooLong",
    "FramingError",
    "Measurement",
    "MeasurementStatus",
    "MeasurementUnit",
    "ProtocolError",
    "QualityFlag",
    "UnsupportedProtocolVersion",
    "ValidationError",
    "__version__",
]
