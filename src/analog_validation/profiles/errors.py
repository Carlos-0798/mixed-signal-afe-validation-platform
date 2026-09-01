"""Serial-profile contract failures that are not malformed wire records."""

from analog_validation.errors import AnalogValidationError


class SerialProfileError(AnalogValidationError):
    """Base class for expected serial-profile integration failures."""


class SerialProfileStateError(SerialProfileError):
    """A profile was called with incompatible state, identity, or provenance."""


__all__ = ["SerialProfileError", "SerialProfileStateError"]
