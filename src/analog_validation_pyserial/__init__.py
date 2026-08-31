"""Optional pyserial integration for the driver-neutral product core.

Importing this package does not import pyserial.  The dependency is resolved
only when a backend operation needs it, so the base product remains usable on
machines without a serial driver.
"""

from .backend import PySerialBackend
from .errors import (
    PySerialBackendError,
    PySerialBackendStateError,
    PySerialUnavailableError,
)

__all__ = [
    "PySerialBackend",
    "PySerialBackendError",
    "PySerialBackendStateError",
    "PySerialUnavailableError",
]
