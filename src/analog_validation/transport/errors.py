"""Transport-local failures for serial lifecycle and bounded raw evidence."""

from analog_validation.errors import AnalogValidationError


class SerialTransportError(AnalogValidationError):
    """Base class for expected serial transport failures."""


class SerialStateError(SerialTransportError):
    """A serial operation is not allowed in the current lifecycle state."""


class SerialDiscoveryError(SerialTransportError):
    """A backend could not provide a valid port inventory."""


class SerialOpenError(SerialTransportError):
    """A backend could not open the selected serial port."""


class SerialReadError(SerialTransportError):
    """A bounded serial read or receive-side operation failed."""


class SerialCloseError(SerialTransportError):
    """A backend reported a failure while closing the serial port."""


class SerialReconnectError(SerialTransportError):
    """A disconnected serial session exhausted its finite reconnect budget."""


class SerialBackendTimeout(SerialTransportError):
    """Backend signal that a bounded read completed without data."""


class SerialBackendDisconnected(SerialTransportError):
    """Backend signal that the open port disconnected during a read."""


class RawEventError(AnalogValidationError):
    """Base class for bounded raw-event model failures."""


class RawEventLimitError(RawEventError):
    """A raw event or log configuration exceeds a resource bound."""


class RawEventNotFound(RawEventError):
    """A raw event is missing or has already been evicted."""


__all__ = [
    "RawEventError",
    "RawEventLimitError",
    "RawEventNotFound",
    "SerialBackendDisconnected",
    "SerialBackendTimeout",
    "SerialCloseError",
    "SerialDiscoveryError",
    "SerialOpenError",
    "SerialReadError",
    "SerialReconnectError",
    "SerialStateError",
    "SerialTransportError",
]
