"""Controller-neutral contracts implemented by concrete serial profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar, runtime_checkable

from analog_validation.domain import DeviceCapabilities, EvidenceSource, Measurement
from analog_validation.transport import (
    MAX_RAW_EVENT_BYTES,
    MAX_SEQUENCE_BITS,
    MIN_SEQUENCE_BITS,
    BoundedRawEventLog,
    RawRecordEvent,
    RawRecordStatus,
)

from .errors import SerialProfileStateError

SERIAL_PROFILE_SCHEMA_VERSION = "serial-profile.v1"
MAX_PROFILE_IDENTITY_CHARS = 128

MessageT = TypeVar("MessageT")


def _bounded_identity_text(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise SerialProfileStateError(f"{name} must be a string")
    if not value or value != value.strip():
        raise SerialProfileStateError(
            f"{name} must be non-empty without outer whitespace"
        )
    if len(value) > MAX_PROFILE_IDENTITY_CHARS:
        raise SerialProfileStateError(
            f"{name} exceeds {MAX_PROFILE_IDENTITY_CHARS} characters"
        )
    if any(not character.isprintable() or character in "\r\n" for character in value):
        raise SerialProfileStateError(
            f"{name} must contain printable single-line text"
        )
    return value


def _bounded_integer(
    name: str,
    value: object,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SerialProfileStateError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise SerialProfileStateError(
            f"{name} must be between {minimum} and {maximum}"
        )
    return value


@dataclass(frozen=True, slots=True)
class SerialProfileIdentity:
    """Explicit profile selection data shared with a serial session."""

    name: str
    version: str
    sequence_bits: int
    max_record_bytes: int
    schema_version: str = SERIAL_PROFILE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        name = _bounded_identity_text("name", self.name)
        version = _bounded_identity_text("version", self.version)
        sequence_bits = _bounded_integer(
            "sequence_bits",
            self.sequence_bits,
            minimum=MIN_SEQUENCE_BITS,
            maximum=MAX_SEQUENCE_BITS,
        )
        max_record_bytes = _bounded_integer(
            "max_record_bytes",
            self.max_record_bytes,
            minimum=1,
            maximum=MAX_RAW_EVENT_BYTES,
        )
        if self.schema_version != SERIAL_PROFILE_SCHEMA_VERSION:
            raise SerialProfileStateError(
                f"unsupported serial profile schema version: {self.schema_version}"
            )
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "sequence_bits", sequence_bits)
        object.__setattr__(self, "max_record_bytes", max_record_bytes)


@dataclass(frozen=True, slots=True)
class SerialProfileRecord(Generic[MessageT]):
    """One raw event after a concrete profile accepted or rejected it."""

    identity: SerialProfileIdentity
    event: RawRecordEvent
    message: MessageT | None
    measurements: tuple[Measurement, ...] = ()
    capabilities: DeviceCapabilities | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.identity, SerialProfileIdentity):
            raise SerialProfileStateError("identity must be a SerialProfileIdentity")
        if not isinstance(self.event, RawRecordEvent):
            raise SerialProfileStateError("event must be a RawRecordEvent")
        if self.event.profile_name != self.identity.name:
            raise SerialProfileStateError(
                "event profile_name does not match the selected profile identity"
            )
        if not isinstance(self.measurements, tuple) or not all(
            isinstance(item, Measurement) for item in self.measurements
        ):
            raise SerialProfileStateError(
                "measurements must be a tuple of Measurement values"
            )
        if self.capabilities is not None and not isinstance(
            self.capabilities, DeviceCapabilities
        ):
            raise SerialProfileStateError(
                "capabilities must be DeviceCapabilities or None"
            )

        if self.event.status is RawRecordStatus.PENDING_PROFILE:
            raise SerialProfileStateError(
                "serial profile result cannot contain a pending raw event"
            )
        if self.event.status is RawRecordStatus.PARSED:
            if self.message is None:
                raise SerialProfileStateError(
                    "parsed serial profile result requires a message"
                )
        elif self.message is not None or self.measurements or self.capabilities is not None:
            raise SerialProfileStateError(
                "rejected serial profile result cannot contain derived data"
            )

    @property
    def accepted(self) -> bool:
        """Return whether profile parsing and contextual mapping succeeded."""

        return self.event.status is RawRecordStatus.PARSED


@dataclass(frozen=True, slots=True)
class SerialProfileResetResult:
    """State intentionally discarded at a session or profile boundary."""

    previous_sequence: int | None
    discarded_records: int = 0

    def __post_init__(self) -> None:
        if self.previous_sequence is not None and (
            isinstance(self.previous_sequence, bool)
            or not isinstance(self.previous_sequence, int)
            or self.previous_sequence < 0
        ):
            raise SerialProfileStateError(
                "previous_sequence must be a non-negative integer or None"
            )
        _bounded_integer(
            "discarded_records",
            self.discarded_records,
            minimum=0,
            maximum=2**31 - 1,
        )


@runtime_checkable
class SerialProfile(Protocol[MessageT]):
    """Replaceable business parser above transport and below an adapter."""

    @property
    def identity(self) -> SerialProfileIdentity:
        """Return the exact profile/version and transport limits."""

        ...

    @property
    def evidence_source(self) -> EvidenceSource:
        """Return the caller-selected provenance used for derived measurements."""

        ...

    @property
    def initial_capabilities(self) -> DeviceCapabilities | None:
        """Return a static capability contract or require stream negotiation."""

        ...

    def process_record(
        self,
        event: RawRecordEvent,
        event_log: BoundedRawEventLog,
    ) -> SerialProfileRecord[MessageT]:
        """Interpret one retained pending event and record its outcome."""

        ...

    def reset(self) -> SerialProfileResetResult:
        """Discard sequence and incomplete multi-record transaction state."""

        ...


__all__ = [
    "MAX_PROFILE_IDENTITY_CHARS",
    "SERIAL_PROFILE_SCHEMA_VERSION",
    "SerialProfile",
    "SerialProfileIdentity",
    "SerialProfileRecord",
    "SerialProfileResetResult",
]
