"""Bounded LF-delimited byte-stream recovery without profile assumptions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from analog_validation.errors import ValidationError

_LF = 0x0A


class StreamIssueKind(str, Enum):
    """A recoverable condition found while extracting complete records."""

    OVERLONG_RECORD = "OVERLONG_RECORD"


@dataclass(frozen=True, slots=True)
class StreamIssue:
    """One rejected byte sequence and the reason it was discarded."""

    kind: StreamIssueKind
    discarded_bytes: int


@dataclass(frozen=True, slots=True)
class StreamFeedResult:
    """Complete raw records and recoverable issues produced by one feed call."""

    records: tuple[bytes, ...]
    issues: tuple[StreamIssue, ...]


@dataclass(frozen=True, slots=True)
class StreamResetResult:
    """State discarded because a transport disconnected or was reset."""

    discarded_bytes: int
    was_discarding_overlong: bool


def _require_positive_limit(max_record_bytes: int) -> int:
    if isinstance(max_record_bytes, bool) or not isinstance(max_record_bytes, int):
        raise ValidationError("max_record_bytes must be an integer")
    if max_record_bytes < 1:
        raise ValidationError("max_record_bytes must be positive")
    return max_record_bytes


def _coerce_bytes(data: bytes | bytearray | memoryview) -> bytes:
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)
    if isinstance(data, memoryview):
        return data.tobytes()
    raise ValidationError("stream data must be bytes-like")


class BoundedLineFramer:
    """Extract LF-terminated records while bounding damaged input growth.

    This layer deliberately knows nothing about ASCII, CSV, CRC, namespaces, or
    message fields. A profile decoder receives each complete raw record and owns
    those business-level checks.
    """

    def __init__(self, max_record_bytes: int) -> None:
        self._max_record_bytes = _require_positive_limit(max_record_bytes)
        self._buffer = bytearray()
        self._discarding_overlong = False
        self._discarded_overlong_bytes = 0

    @property
    def max_record_bytes(self) -> int:
        """Maximum accepted record size, including its LF terminator."""

        return self._max_record_bytes

    @property
    def pending_bytes(self) -> int:
        """Bytes held for the current incomplete or rejected record."""

        if self._discarding_overlong:
            return self._discarded_overlong_bytes
        return len(self._buffer)

    @property
    def discarding_overlong(self) -> bool:
        """Whether bytes are being dropped until the next LF boundary."""

        return self._discarding_overlong

    def feed(self, data: bytes | bytearray | memoryview) -> StreamFeedResult:
        """Consume a chunk and return all complete records in receive order."""

        raw = _coerce_bytes(data)
        records: list[bytes] = []
        issues: list[StreamIssue] = []

        for value in raw:
            if self._discarding_overlong:
                self._discarded_overlong_bytes += 1
                if value == _LF:
                    issues.append(
                        StreamIssue(
                            StreamIssueKind.OVERLONG_RECORD,
                            self._discarded_overlong_bytes,
                        )
                    )
                    self._discarding_overlong = False
                    self._discarded_overlong_bytes = 0
                continue

            self._buffer.append(value)
            if len(self._buffer) > self._max_record_bytes:
                self._discarding_overlong = True
                self._discarded_overlong_bytes = len(self._buffer)
                self._buffer.clear()
                if value == _LF:
                    issues.append(
                        StreamIssue(
                            StreamIssueKind.OVERLONG_RECORD,
                            self._discarded_overlong_bytes,
                        )
                    )
                    self._discarding_overlong = False
                    self._discarded_overlong_bytes = 0
            elif value == _LF:
                records.append(bytes(self._buffer))
                self._buffer.clear()

        return StreamFeedResult(tuple(records), tuple(issues))

    def reset(self) -> StreamResetResult:
        """Discard incomplete state without turning it into a valid record."""

        was_overlong = self._discarding_overlong
        discarded = self.pending_bytes
        self._buffer.clear()
        self._discarding_overlong = False
        self._discarded_overlong_bytes = 0
        return StreamResetResult(discarded, was_overlong)


__all__ = [
    "BoundedLineFramer",
    "StreamFeedResult",
    "StreamIssue",
    "StreamIssueKind",
    "StreamResetResult",
]
