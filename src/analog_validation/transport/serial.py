"""Driver-neutral serial lifecycle with bounded reads and finite reconnects."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol

from .errors import (
    SerialBackendDisconnected,
    SerialBackendTimeout,
    SerialCloseError,
    SerialDiscoveryError,
    SerialOpenError,
    SerialReadError,
    SerialReconnectError,
    SerialStateError,
)
from .events import (
    MAX_RAW_EVENT_BYTES,
    BoundedRawEventLog,
    RawRecordEvent,
)
from .stream import BoundedLineFramer, StreamIssue, StreamResetResult

DEFAULT_BAUD_RATE = 115_200
DEFAULT_READ_CHUNK_BYTES = 512
DEFAULT_READ_TIMEOUT_SECONDS = 0.25
DEFAULT_MAX_RECONNECT_ATTEMPTS = 2
MAX_BAUD_RATE = 4_000_000
MAX_READ_CHUNK_BYTES = 65_536
MAX_READ_TIMEOUT_SECONDS = 60.0
MAX_RECONNECT_ATTEMPTS = 10
MAX_SERIAL_TEXT_CHARS = 128

Clock = Callable[[], datetime]


class SerialParity(str, Enum):
    """Supported serial parity selections without backend-specific constants."""

    NONE = "NONE"
    EVEN = "EVEN"
    ODD = "ODD"


class SerialStopBits(str, Enum):
    """Supported serial stop-bit selections."""

    ONE = "ONE"
    ONE_POINT_FIVE = "ONE_POINT_FIVE"
    TWO = "TWO"


class SerialSessionState(str, Enum):
    """Logical state owned by the driver-neutral session."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"


class SerialPollStatus(str, Enum):
    """Outcome of one bounded poll call."""

    DATA = "DATA"
    TIMEOUT = "TIMEOUT"
    RECONNECTED = "RECONNECTED"


def _bounded_text(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise SerialStateError(f"{name} must be a string")
    if not value or value != value.strip():
        raise SerialStateError(f"{name} must be non-empty without outer whitespace")
    if len(value) > MAX_SERIAL_TEXT_CHARS:
        raise SerialStateError(
            f"{name} exceeds {MAX_SERIAL_TEXT_CHARS} characters"
        )
    if any(not character.isprintable() or character in "\r\n" for character in value):
        raise SerialStateError(f"{name} must contain printable single-line text")
    return value


def _bounded_integer(
    name: str,
    value: object,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SerialStateError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise SerialStateError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class SerialPortInfo:
    """Minimal discovered-port identity, deliberately excluding hardware IDs."""

    port_id: str
    description: str | None = None

    def __post_init__(self) -> None:
        port_id = _bounded_text("port_id", self.port_id)
        description = self.description
        if description is not None:
            description = _bounded_text("description", description)
        object.__setattr__(self, "port_id", port_id)
        object.__setattr__(self, "description", description)


@dataclass(frozen=True, slots=True)
class SerialConnectionSettings:
    """Validated, backend-neutral parameters for one selected profile and port."""

    port_id: str
    profile_name: str
    baud_rate: int = DEFAULT_BAUD_RATE
    data_bits: int = 8
    parity: SerialParity = SerialParity.NONE
    stop_bits: SerialStopBits = SerialStopBits.ONE
    read_chunk_bytes: int = DEFAULT_READ_CHUNK_BYTES
    max_record_bytes: int = 128
    read_timeout_seconds: float = DEFAULT_READ_TIMEOUT_SECONDS
    max_reconnect_attempts: int = DEFAULT_MAX_RECONNECT_ATTEMPTS

    def __post_init__(self) -> None:
        port_id = _bounded_text("port_id", self.port_id)
        profile_name = _bounded_text("profile_name", self.profile_name)
        baud_rate = _bounded_integer(
            "baud_rate", self.baud_rate, minimum=1, maximum=MAX_BAUD_RATE
        )
        data_bits = _bounded_integer(
            "data_bits", self.data_bits, minimum=5, maximum=8
        )
        if not isinstance(self.parity, SerialParity):
            raise SerialStateError("parity must be a SerialParity")
        if not isinstance(self.stop_bits, SerialStopBits):
            raise SerialStateError("stop_bits must be a SerialStopBits")
        read_chunk_bytes = _bounded_integer(
            "read_chunk_bytes",
            self.read_chunk_bytes,
            minimum=1,
            maximum=MAX_READ_CHUNK_BYTES,
        )
        max_record_bytes = _bounded_integer(
            "max_record_bytes",
            self.max_record_bytes,
            minimum=1,
            maximum=MAX_RAW_EVENT_BYTES,
        )
        if isinstance(self.read_timeout_seconds, bool) or not isinstance(
            self.read_timeout_seconds, (int, float)
        ):
            raise SerialStateError("read_timeout_seconds must be a number")
        timeout = float(self.read_timeout_seconds)
        if not math.isfinite(timeout) or not 0 < timeout <= MAX_READ_TIMEOUT_SECONDS:
            raise SerialStateError(
                "read_timeout_seconds must be finite and greater than zero up to "
                f"{MAX_READ_TIMEOUT_SECONDS}"
            )
        reconnects = _bounded_integer(
            "max_reconnect_attempts",
            self.max_reconnect_attempts,
            minimum=0,
            maximum=MAX_RECONNECT_ATTEMPTS,
        )
        object.__setattr__(self, "port_id", port_id)
        object.__setattr__(self, "profile_name", profile_name)
        object.__setattr__(self, "baud_rate", baud_rate)
        object.__setattr__(self, "data_bits", data_bits)
        object.__setattr__(self, "read_chunk_bytes", read_chunk_bytes)
        object.__setattr__(self, "max_record_bytes", max_record_bytes)
        object.__setattr__(self, "read_timeout_seconds", timeout)
        object.__setattr__(self, "max_reconnect_attempts", reconnects)


class SerialBackend(Protocol):
    """Replaceable low-level serial operations used by :class:`SerialSession`."""

    def discover_ports(self) -> tuple[SerialPortInfo, ...]:
        """Return the currently visible ports without opening them."""

        ...

    def open(self, settings: SerialConnectionSettings) -> None:
        """Open the selected port with the exact validated settings."""

        ...

    def read(self, max_bytes: int, timeout_seconds: float) -> bytes:
        """Return at most ``max_bytes`` or raise a documented backend signal."""

        ...

    def close(self) -> None:
        """Release backend resources; repeated cleanup calls must be tolerated."""

        ...


@dataclass(frozen=True, slots=True)
class SerialPollResult:
    """Complete records and stream issues from one bounded session poll."""

    status: SerialPollStatus
    records: tuple[RawRecordEvent, ...] = ()
    issues: tuple[StreamIssue, ...] = ()
    reset: StreamResetResult | None = None
    reconnect_attempts: int = 0


class SerialSession:
    """Own serial state while leaving driver choice and profile parsing outside."""

    def __init__(
        self,
        backend: SerialBackend,
        settings: SerialConnectionSettings,
        *,
        event_log: BoundedRawEventLog | None = None,
        clock: Clock | None = None,
    ) -> None:
        if not isinstance(settings, SerialConnectionSettings):
            raise SerialStateError("settings must be SerialConnectionSettings")
        self._backend = backend
        self._settings = settings
        self._event_log = event_log or BoundedRawEventLog()
        if self._event_log.max_total_bytes < settings.max_record_bytes:
            raise SerialStateError(
                "event log byte limit must be at least max_record_bytes"
            )
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        if not callable(self._clock):
            raise SerialStateError("clock must be callable")
        self._framer = BoundedLineFramer(settings.max_record_bytes)
        self._state = SerialSessionState.CLOSED

    @property
    def settings(self) -> SerialConnectionSettings:
        """Immutable settings used for both initial open and reconnect."""

        return self._settings

    @property
    def state(self) -> SerialSessionState:
        """Current logical lifecycle state."""

        return self._state

    @property
    def pending_bytes(self) -> int:
        """Number of incomplete or overlong bytes held by the stream framer."""

        return self._framer.pending_bytes

    @property
    def event_log(self) -> BoundedRawEventLog:
        """Bounded memory-only log receiving all complete records."""

        return self._event_log

    def discover_ports(self) -> tuple[SerialPortInfo, ...]:
        """Discover and validate unique port identities while disconnected."""

        self._require_closed("discover ports")
        try:
            ports = self._backend.discover_ports()
        except Exception as error:
            raise SerialDiscoveryError("serial port discovery failed") from error
        if not isinstance(ports, tuple) or any(
            not isinstance(port, SerialPortInfo) for port in ports
        ):
            raise SerialDiscoveryError(
                "serial backend returned an invalid port inventory"
            )
        identities = tuple(port.port_id for port in ports)
        if len(set(identities)) != len(identities):
            raise SerialDiscoveryError("serial backend returned duplicate port IDs")
        return ports

    def open(self) -> None:
        """Open exactly once, cleaning backend state after every failure."""

        self._require_closed("open")
        self._framer.reset()
        try:
            self._backend.open(self._settings)
        except Exception as error:
            self._cleanup_backend()
            self._state = SerialSessionState.CLOSED
            raise SerialOpenError("serial port open failed") from error
        self._state = SerialSessionState.OPEN

    def poll(self) -> SerialPollResult:
        """Perform one bounded read without sleeping or parsing a device profile."""

        self._require_open("poll")
        try:
            chunk = self._backend.read(
                self._settings.read_chunk_bytes,
                self._settings.read_timeout_seconds,
            )
        except SerialBackendTimeout:
            return SerialPollResult(SerialPollStatus.TIMEOUT)
        except SerialBackendDisconnected:
            return self._reconnect()
        except Exception as error:
            self._abort_session()
            raise SerialReadError("serial bounded read failed") from error

        try:
            raw = self._coerce_backend_chunk(chunk)
            if not raw:
                return SerialPollResult(SerialPollStatus.TIMEOUT)
            feed = self._framer.feed(raw)
            records = tuple(self._record_event(record) for record in feed.records)
            return SerialPollResult(
                SerialPollStatus.DATA,
                records=records,
                issues=feed.issues,
            )
        except SerialReadError:
            self._abort_session()
            raise
        except Exception as error:
            self._abort_session()
            raise SerialReadError("serial receive processing failed") from error

    def close(self) -> StreamResetResult:
        """Close idempotently and always clear incomplete receive state."""

        reset = self._framer.reset()
        if self._state is SerialSessionState.CLOSED:
            return reset
        close_error: Exception | None = None
        try:
            self._backend.close()
        except Exception as error:  # noqa: BLE001 - replaceable backend boundary
            close_error = error
        finally:
            self._state = SerialSessionState.CLOSED
        if close_error is not None:
            raise SerialCloseError("serial port close failed") from close_error
        return reset

    def _record_event(self, raw: bytes) -> RawRecordEvent:
        return self._event_log.append_received(
            received_at=self._utc_now(),
            port_id=self._settings.port_id,
            profile_name=self._settings.profile_name,
            raw_bytes=raw,
        )

    def _utc_now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime):
            raise SerialReadError("serial receive clock must return a datetime")
        if value.tzinfo is None or value.utcoffset() is None:
            raise SerialReadError(
                "serial receive clock must return a timezone-aware datetime"
            )
        return value.astimezone(timezone.utc)

    def _coerce_backend_chunk(self, chunk: object) -> bytes:
        if isinstance(chunk, bytes):
            raw = chunk
        elif isinstance(chunk, bytearray):
            raw = bytes(chunk)
        elif isinstance(chunk, memoryview):
            raw = chunk.tobytes()
        else:
            raise SerialReadError("serial backend must return bytes-like data")
        if len(raw) > self._settings.read_chunk_bytes:
            raise SerialReadError("serial backend exceeded the bounded read size")
        return raw

    def _reconnect(self) -> SerialPollResult:
        reset = self._framer.reset()
        self._cleanup_backend()
        self._state = SerialSessionState.CLOSED
        attempts = 0
        for attempts in range(1, self._settings.max_reconnect_attempts + 1):
            try:
                self._backend.open(self._settings)
            except Exception:  # noqa: BLE001 - replaceable backend boundary
                self._cleanup_backend()
                continue
            self._state = SerialSessionState.OPEN
            return SerialPollResult(
                SerialPollStatus.RECONNECTED,
                reset=reset,
                reconnect_attempts=attempts,
            )
        raise SerialReconnectError(
            f"serial reconnect attempts exhausted after {attempts} attempts"
        )

    def _abort_session(self) -> StreamResetResult:
        reset = self._framer.reset()
        self._cleanup_backend()
        self._state = SerialSessionState.CLOSED
        return reset

    def _cleanup_backend(self) -> Exception | None:
        try:
            self._backend.close()
        except Exception as error:  # noqa: BLE001 - best-effort cleanup boundary
            return error
        return None

    def _require_closed(self, operation: str) -> None:
        if self._state is not SerialSessionState.CLOSED:
            raise SerialStateError(f"cannot {operation} while serial session is open")

    def _require_open(self, operation: str) -> None:
        if self._state is not SerialSessionState.OPEN:
            raise SerialStateError(f"cannot {operation} while serial session is closed")


__all__ = [
    "DEFAULT_BAUD_RATE",
    "DEFAULT_MAX_RECONNECT_ATTEMPTS",
    "DEFAULT_READ_CHUNK_BYTES",
    "DEFAULT_READ_TIMEOUT_SECONDS",
    "MAX_BAUD_RATE",
    "MAX_READ_CHUNK_BYTES",
    "MAX_READ_TIMEOUT_SECONDS",
    "MAX_RECONNECT_ATTEMPTS",
    "MAX_SERIAL_TEXT_CHARS",
    "Clock",
    "SerialBackend",
    "SerialConnectionSettings",
    "SerialParity",
    "SerialPollResult",
    "SerialPollStatus",
    "SerialPortInfo",
    "SerialSession",
    "SerialSessionState",
    "SerialStopBits",
]
