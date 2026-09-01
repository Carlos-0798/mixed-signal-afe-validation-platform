"""Stable exception hierarchy for Analog Validation Studio.

User interfaces and adapters may catch a specific error family to select an
appropriate recovery path. Human-readable messages remain attached to the
normal Python exception rather than being coupled to a GUI or transport.
"""


class AnalogValidationError(Exception):
    """Base class for expected product-domain failures."""


class ValidationError(AnalogValidationError):
    """Input or domain data failed validation."""


class ProtocolError(AnalogValidationError):
    """A protocol record cannot be accepted or interpreted."""


class FramingError(ProtocolError):
    """A record violates the protocol envelope or field framing rules."""


class FrameTooLong(ProtocolError):
    """A serialized record exceeds the protocol length limit."""


class CrcMismatch(ProtocolError):
    """A record's received CRC does not match its calculated CRC."""


class UnsupportedProtocolVersion(ProtocolError):
    """A syntactically valid record uses an unsupported protocol version."""


class CapabilityError(AnalogValidationError):
    """A requested operation is not declared by the selected device."""


class ConfigurationError(AnalogValidationError):
    """A product configuration is missing, inconsistent, or unsafe."""


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
]
