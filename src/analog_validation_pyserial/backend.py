"""Minimal receive-only pyserial backend for :mod:`analog_validation`.

The public object intentionally implements only discovery, open, bounded read,
and close.  It has no write method and does not expose the underlying pyserial
object.  This limits the integration surface; it does not make an arbitrary
USB/UART driver electrically incapable of toggling control lines while a port
is opened.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from importlib import import_module
from typing import Any

from analog_validation.transport import (
    MAX_READ_CHUNK_BYTES,
    MAX_READ_TIMEOUT_SECONDS,
    MAX_SERIAL_TEXT_CHARS,
    SerialBackendDisconnected,
    SerialConnectionSettings,
    SerialParity,
    SerialPortInfo,
    SerialStopBits,
)

from .errors import PySerialBackendStateError, PySerialUnavailableError

_INSTALL_HINT = (
    "install the optional dependency with "
    "'python -m pip install mixed-signal-afe-validation-platform[serial]'"
)


def _clean_description(value: object) -> str | None:
    """Return bounded display text without reading hardware identifiers."""

    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    normalized = "".join(
        character for character in normalized if character.isprintable()
    )
    if not normalized:
        return None
    return normalized[:MAX_SERIAL_TEXT_CHARS]


class PySerialBackend:
    """Adapt pyserial to the receive-only :class:`SerialBackend` protocol.

    ``driver`` and ``port_enumerator`` are dependency-injection seams for
    deterministic tests.  Product callers normally omit both arguments.
    """

    def __init__(
        self,
        *,
        driver: object | None = None,
        port_enumerator: Callable[[], Iterable[object]] | None = None,
    ) -> None:
        if (driver is None) != (port_enumerator is None):
            raise PySerialBackendStateError(
                "driver and port_enumerator must be supplied together"
            )
        self._driver = driver
        self._port_enumerator = port_enumerator
        self._port: Any | None = None

    @property
    def is_open(self) -> bool:
        """Return the concrete driver's current open state for diagnostics."""

        return self._port is not None and bool(getattr(self._port, "is_open", False))

    def discover_ports(self) -> tuple[SerialPortInfo, ...]:
        """Enumerate logical names and descriptions without opening a port."""

        _, enumerate_ports = self._dependencies()
        ports: list[SerialPortInfo] = []
        for candidate in enumerate_ports():
            port_id = getattr(candidate, "device", None)
            if not isinstance(port_id, str):
                raise PySerialBackendStateError(
                    "pyserial port inventory contains an invalid device name"
                )
            description = _clean_description(getattr(candidate, "description", None))
            ports.append(SerialPortInfo(port_id, description))
        return tuple(ports)

    def open(self, settings: SerialConnectionSettings) -> None:
        """Configure one port completely before performing the actual open."""

        if not isinstance(settings, SerialConnectionSettings):
            raise PySerialBackendStateError("settings must be SerialConnectionSettings")
        if self._port is not None:
            raise PySerialBackendStateError("pyserial backend is already open")

        driver, _ = self._dependencies()
        serial_factory = self._attribute(driver, "Serial")
        byte_sizes = {
            5: self._attribute(driver, "FIVEBITS"),
            6: self._attribute(driver, "SIXBITS"),
            7: self._attribute(driver, "SEVENBITS"),
            8: self._attribute(driver, "EIGHTBITS"),
        }
        parities = {
            SerialParity.NONE: self._attribute(driver, "PARITY_NONE"),
            SerialParity.EVEN: self._attribute(driver, "PARITY_EVEN"),
            SerialParity.ODD: self._attribute(driver, "PARITY_ODD"),
        }
        stop_bits = {
            SerialStopBits.ONE: self._attribute(driver, "STOPBITS_ONE"),
            SerialStopBits.ONE_POINT_FIVE: self._attribute(
                driver, "STOPBITS_ONE_POINT_FIVE"
            ),
            SerialStopBits.TWO: self._attribute(driver, "STOPBITS_TWO"),
        }

        concrete: Any | None = None
        try:
            concrete = serial_factory(
                port=None,
                baudrate=settings.baud_rate,
                bytesize=byte_sizes[settings.data_bits],
                parity=parities[settings.parity],
                stopbits=stop_bits[settings.stop_bits],
                timeout=settings.read_timeout_seconds,
                xonxoff=False,
                rtscts=False,
                write_timeout=0,
                dsrdtr=False,
                inter_byte_timeout=None,
            )
            concrete.dtr = False
            concrete.rts = False
            concrete.port = settings.port_id
            concrete.open()
            if not bool(getattr(concrete, "is_open", False)):
                raise PySerialBackendStateError("pyserial did not report an open port")
        except Exception:
            if concrete is not None:
                try:
                    concrete.close()
                except Exception:  # noqa: BLE001, S110 - preserve primary error
                    pass
            raise
        self._port = concrete

    def read(self, max_bytes: int, timeout_seconds: float) -> bytes:
        """Perform one finite read and map driver loss to the core signal."""

        if self._port is None or not bool(getattr(self._port, "is_open", False)):
            raise PySerialBackendStateError("pyserial backend is not open")
        if (
            isinstance(max_bytes, bool)
            or not isinstance(max_bytes, int)
            or not 1 <= max_bytes <= MAX_READ_CHUNK_BYTES
        ):
            raise PySerialBackendStateError(
                f"max_bytes must be between 1 and {MAX_READ_CHUNK_BYTES}"
            )
        if isinstance(timeout_seconds, bool) or not isinstance(
            timeout_seconds, (int, float)
        ):
            raise PySerialBackendStateError("timeout_seconds must be a number")
        timeout = float(timeout_seconds)
        if not math.isfinite(timeout) or not 0 < timeout <= MAX_READ_TIMEOUT_SECONDS:
            raise PySerialBackendStateError(
                "timeout_seconds must be finite and within the core bound"
            )

        try:
            self._port.timeout = timeout
            raw = self._port.read(max_bytes)
        except Exception as error:
            if self._is_disconnect_error(error):
                raise SerialBackendDisconnected(
                    "pyserial receive failed or the device disconnected"
                ) from error
            raise
        if not isinstance(raw, (bytes, bytearray, memoryview)):
            raise PySerialBackendStateError("pyserial read must return bytes-like data")
        result = bytes(raw)
        if len(result) > max_bytes:
            raise PySerialBackendStateError(
                "pyserial read exceeded the requested byte bound"
            )
        return result

    def close(self) -> None:
        """Close idempotently and clear the private driver reference."""

        concrete = self._port
        self._port = None
        if concrete is not None:
            concrete.close()

    def _dependencies(
        self,
    ) -> tuple[object, Callable[[], Iterable[object]]]:
        if self._driver is not None and self._port_enumerator is not None:
            return self._driver, self._port_enumerator
        try:
            driver = import_module("serial")
            list_ports = import_module("serial.tools.list_ports")
        except (ImportError, ModuleNotFoundError) as error:
            raise PySerialUnavailableError(
                f"optional pyserial dependency is unavailable; {_INSTALL_HINT}"
            ) from error
        enumerate_ports = getattr(list_ports, "comports", None)
        if not callable(enumerate_ports):
            raise PySerialUnavailableError(
                f"pyserial port enumeration API is unavailable; {_INSTALL_HINT}"
            )
        self._driver = driver
        self._port_enumerator = enumerate_ports
        return driver, enumerate_ports

    def _is_disconnect_error(self, error: Exception) -> bool:
        driver, _ = self._dependencies()
        serial_exception = getattr(driver, "SerialException", None)
        exception_types: tuple[type[BaseException], ...] = (OSError,)
        if isinstance(serial_exception, type) and issubclass(
            serial_exception, BaseException
        ):
            exception_types = (OSError, serial_exception)
        return isinstance(error, exception_types)

    @staticmethod
    def _attribute(owner: object, name: str) -> Any:
        value = getattr(owner, name, None)
        if value is None:
            raise PySerialUnavailableError(
                f"pyserial is missing required attribute {name}; {_INSTALL_HINT}"
            )
        return value


__all__ = ["PySerialBackend"]
