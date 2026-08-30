"""Public package for Analog Validation Studio.

The package is controller-neutral: importing it must not require a serial
driver, GUI toolkit, board SDK, or physical hardware.
"""

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
    "AnalogValidationError",
    "CapabilityError",
    "ConfigurationError",
    "CrcMismatch",
    "FrameTooLong",
    "FramingError",
    "ProtocolError",
    "UnsupportedProtocolVersion",
    "ValidationError",
    "__version__",
]
