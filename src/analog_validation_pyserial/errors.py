"""Stable failures owned by the optional pyserial integration package."""

from analog_validation.errors import AnalogValidationError


class PySerialBackendError(AnalogValidationError):
    """Base class for expected optional-backend failures."""


class PySerialUnavailableError(PySerialBackendError):
    """The optional pyserial dependency is absent or incomplete."""


class PySerialBackendStateError(PySerialBackendError):
    """The concrete backend was used with an invalid lifecycle or contract."""


__all__ = [
    "PySerialBackendError",
    "PySerialBackendStateError",
    "PySerialUnavailableError",
]
