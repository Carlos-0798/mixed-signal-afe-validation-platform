"""Bounded in-memory provenance for complete raw transport records."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import Any

from .errors import RawEventError, RawEventLimitError, RawEventNotFound
from .sequence import SequenceObservation

DEFAULT_MAX_RAW_EVENTS = 1024
DEFAULT_MAX_RAW_LOG_BYTES = 256 * 1024
MAX_RAW_EVENT_BYTES = 4096
MAX_RAW_EVENTS = 10_000
MAX_RAW_LOG_BYTES = 2 * 1024 * 1024
MAX_RAW_METADATA_CHARS = 128
MAX_RAW_RESULT_CHARS = 512

RAW_EVENT_PRIVACY_NOTICE = (
    "Raw records may contain device identifiers, configuration, or fault state. "
    "This bounded log is memory-only and is never persisted or uploaded automatically."
)


class RawRecordStatus(str, Enum):
    """Processing state of one complete, bounded raw record."""

    PENDING_PROFILE = "PENDING_PROFILE"
    PARSED = "PARSED"
    REJECTED = "REJECTED"


def _bounded_text(name: str, value: object, *, max_chars: int) -> str:
    if not isinstance(value, str):
        raise RawEventError(f"{name} must be a string")
    if not value or value != value.strip():
        raise RawEventError(f"{name} must be non-empty without outer whitespace")
    if len(value) > max_chars:
        raise RawEventLimitError(f"{name} exceeds {max_chars} characters")
    if any(not character.isprintable() or character in "\r\n" for character in value):
        raise RawEventError(f"{name} must contain printable single-line text")
    return value


def _positive_integer(name: str, value: object, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RawEventError(f"{name} must be an integer")
    if not 1 <= value <= maximum:
        raise RawEventLimitError(f"{name} must be between 1 and {maximum}")
    return value


def _utc_datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise RawEventError("received_at must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise RawEventError("received_at must be timezone-aware")
    return value.astimezone(timezone.utc)


def _raw_bytes(value: object) -> bytes:
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, bytearray):
        raw = bytes(value)
    elif isinstance(value, memoryview):
        raw = value.tobytes()
    else:
        raise RawEventError("raw_bytes must be bytes-like")
    if not raw:
        raise RawEventError("raw_bytes must be non-empty")
    if len(raw) > MAX_RAW_EVENT_BYTES:
        raise RawEventLimitError(
            f"raw_bytes exceeds the {MAX_RAW_EVENT_BYTES}-byte event limit"
        )
    return raw


@dataclass(frozen=True, slots=True)
class RawRecordEvent:
    """One complete record plus explicit profile-processing provenance."""

    event_id: int
    received_at: datetime
    port_id: str
    profile_name: str
    raw_bytes: bytes
    status: RawRecordStatus = RawRecordStatus.PENDING_PROFILE
    parse_result: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    sequence: SequenceObservation | None = None

    def __post_init__(self) -> None:
        event_id = _positive_integer("event_id", self.event_id, maximum=2**63 - 1)
        received_at = _utc_datetime(self.received_at)
        port_id = _bounded_text(
            "port_id", self.port_id, max_chars=MAX_RAW_METADATA_CHARS
        )
        profile_name = _bounded_text(
            "profile_name", self.profile_name, max_chars=MAX_RAW_METADATA_CHARS
        )
        raw = _raw_bytes(self.raw_bytes)
        if not isinstance(self.status, RawRecordStatus):
            raise RawEventError("status must be a RawRecordStatus")
        if self.sequence is not None and not isinstance(
            self.sequence, SequenceObservation
        ):
            raise RawEventError("sequence must be a SequenceObservation")

        if self.status is RawRecordStatus.PENDING_PROFILE:
            if any(
                value is not None
                for value in (
                    self.parse_result,
                    self.error_type,
                    self.error_message,
                    self.sequence,
                )
            ):
                raise RawEventError("pending raw events cannot contain parse outcomes")
        elif self.status is RawRecordStatus.PARSED:
            _bounded_text(
                "parse_result",
                self.parse_result,
                max_chars=MAX_RAW_RESULT_CHARS,
            )
            if self.error_type is not None or self.error_message is not None:
                raise RawEventError("parsed raw events cannot contain errors")
        else:
            _bounded_text(
                "error_type", self.error_type, max_chars=MAX_RAW_METADATA_CHARS
            )
            _bounded_text(
                "error_message",
                self.error_message,
                max_chars=MAX_RAW_RESULT_CHARS,
            )
            if self.parse_result is not None or self.sequence is not None:
                raise RawEventError(
                    "rejected raw events cannot contain a parse result or sequence"
                )

        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "received_at", received_at)
        object.__setattr__(self, "port_id", port_id)
        object.__setattr__(self, "profile_name", profile_name)
        object.__setattr__(self, "raw_bytes", raw)


@dataclass(frozen=True, slots=True)
class RawEventSnapshot:
    """Immutable view of retained records and cumulative eviction counters."""

    events: tuple[RawRecordEvent, ...]
    retained_bytes: int
    dropped_events: int
    dropped_bytes: int


class BoundedRawEventLog:
    """Thread-safe FIFO raw-record log with explicit count and byte limits."""

    def __init__(
        self,
        *,
        max_events: int = DEFAULT_MAX_RAW_EVENTS,
        max_total_bytes: int = DEFAULT_MAX_RAW_LOG_BYTES,
    ) -> None:
        self._max_events = _positive_integer(
            "max_events", max_events, maximum=MAX_RAW_EVENTS
        )
        self._max_total_bytes = _positive_integer(
            "max_total_bytes", max_total_bytes, maximum=MAX_RAW_LOG_BYTES
        )
        self._events: deque[RawRecordEvent] = deque()
        self._retained_bytes = 0
        self._dropped_events = 0
        self._dropped_bytes = 0
        self._next_event_id = 1
        self._lock = RLock()

    @property
    def max_events(self) -> int:
        """Maximum number of records retained at once."""

        return self._max_events

    @property
    def max_total_bytes(self) -> int:
        """Maximum sum of retained raw-record byte lengths."""

        return self._max_total_bytes

    def append_received(
        self,
        *,
        received_at: datetime,
        port_id: str,
        profile_name: str,
        raw_bytes: bytes | bytearray | memoryview,
    ) -> RawRecordEvent:
        """Append a complete record in the explicit pending-profile state."""

        raw = _raw_bytes(raw_bytes)
        if len(raw) > self._max_total_bytes:
            raise RawEventLimitError("raw record exceeds this log's total byte limit")
        with self._lock:
            event = RawRecordEvent(
                event_id=self._next_event_id,
                received_at=received_at,
                port_id=port_id,
                profile_name=profile_name,
                raw_bytes=raw,
            )
            self._next_event_id += 1
            self._events.append(event)
            self._retained_bytes += len(raw)
            self._evict_to_bounds()
            return event

    def mark_parsed(
        self,
        event_id: int,
        *,
        parse_result: str,
        sequence: SequenceObservation | None = None,
    ) -> RawRecordEvent:
        """Replace one retained pending event with its successful outcome."""

        return self._replace_event(
            event_id,
            status=RawRecordStatus.PARSED,
            parse_result=parse_result,
            sequence=sequence,
        )

    def mark_rejected(
        self,
        event_id: int,
        *,
        error_type: str,
        error_message: str,
    ) -> RawRecordEvent:
        """Replace one retained pending event with its rejection outcome."""

        return self._replace_event(
            event_id,
            status=RawRecordStatus.REJECTED,
            error_type=error_type,
            error_message=error_message,
        )

    def snapshot(self) -> RawEventSnapshot:
        """Return an immutable, receive-ordered view without exposing the deque."""

        with self._lock:
            return self._snapshot_unlocked()

    def clear(self) -> RawEventSnapshot:
        """Return and clear retained data and eviction counters.

        Event identifiers remain monotonic so a stale identifier cannot be
        mistaken for a newly received record.
        """

        with self._lock:
            previous = self._snapshot_unlocked()
            self._events.clear()
            self._retained_bytes = 0
            self._dropped_events = 0
            self._dropped_bytes = 0
            return previous

    def _replace_event(self, event_id: int, **changes: Any) -> RawRecordEvent:
        identifier = _positive_integer("event_id", event_id, maximum=2**63 - 1)
        with self._lock:
            for index, event in enumerate(self._events):
                if event.event_id == identifier:
                    if event.status is not RawRecordStatus.PENDING_PROFILE:
                        raise RawEventError("raw event already has a parse outcome")
                    updated = replace(event, **changes)
                    self._events[index] = updated
                    return updated
        raise RawEventNotFound("raw event is missing or has been evicted")

    def _evict_to_bounds(self) -> None:
        while (
            len(self._events) > self._max_events
            or self._retained_bytes > self._max_total_bytes
        ):
            removed = self._events.popleft()
            size = len(removed.raw_bytes)
            self._retained_bytes -= size
            self._dropped_events += 1
            self._dropped_bytes += size

    def _snapshot_unlocked(self) -> RawEventSnapshot:
        return RawEventSnapshot(
            tuple(self._events),
            self._retained_bytes,
            self._dropped_events,
            self._dropped_bytes,
        )


__all__ = [
    "DEFAULT_MAX_RAW_EVENTS",
    "DEFAULT_MAX_RAW_LOG_BYTES",
    "MAX_RAW_EVENTS",
    "MAX_RAW_EVENT_BYTES",
    "MAX_RAW_LOG_BYTES",
    "MAX_RAW_METADATA_CHARS",
    "MAX_RAW_RESULT_CHARS",
    "RAW_EVENT_PRIVACY_NOTICE",
    "BoundedRawEventLog",
    "RawEventSnapshot",
    "RawRecordEvent",
    "RawRecordStatus",
]
