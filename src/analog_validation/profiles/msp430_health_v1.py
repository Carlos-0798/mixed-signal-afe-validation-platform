"""Read-only MSP430 Equipment Health v1 profile over retained raw records."""

from __future__ import annotations

from threading import RLock

from analog_validation.domain import DeviceCapabilities, EvidenceSource, Measurement
from analog_validation.errors import ProtocolError, ValidationError
from analog_validation.protocol.msp430_health_v1 import (
    MSP430_HEALTH_MAX_RECORD_BYTES,
    MSP430_HEALTH_PROFILE_NAME,
    MSP430_HEALTH_PROFILE_VERSION,
    MSP430_HEALTH_V1_READ_ONLY_CAPABILITIES,
    Msp430Message,
    Msp430Telemetry,
    msp430_telemetry_to_measurements,
    parse_msp430_message,
)
from analog_validation.transport import (
    BoundedRawEventLog,
    RawRecordEvent,
    RawRecordStatus,
    SequenceTracker,
)

from .core import SerialProfileIdentity, SerialProfileRecord, SerialProfileResetResult
from .errors import SerialProfileStateError

MSP430_HEALTH_V1_SEQUENCE_BITS = 32
MSP430_HEALTH_V1_SERIAL_IDENTITY = SerialProfileIdentity(
    name=MSP430_HEALTH_PROFILE_NAME,
    version=MSP430_HEALTH_PROFILE_VERSION,
    sequence_bits=MSP430_HEALTH_V1_SEQUENCE_BITS,
    max_record_bytes=MSP430_HEALTH_MAX_RECORD_BYTES,
)

_ALLOWED_SERIAL_EVIDENCE = frozenset(
    {EvidenceSource.HOST_TEST, EvidenceSource.BENCH_CONTROLLER}
)


class Msp430HealthV1SerialProfile:
    """Parse peer-product output without exposing any control operation."""

    def __init__(self, *, evidence_source: EvidenceSource) -> None:
        if not isinstance(evidence_source, EvidenceSource):
            raise SerialProfileStateError("evidence_source must be an EvidenceSource")
        if evidence_source not in _ALLOWED_SERIAL_EVIDENCE:
            raise SerialProfileStateError(
                "MSP430 serial evidence_source must be HOST_TEST or BENCH_CONTROLLER"
            )
        self._evidence_source = evidence_source
        self._sequence = SequenceTracker(MSP430_HEALTH_V1_SEQUENCE_BITS)
        self._lock = RLock()

    @property
    def identity(self) -> SerialProfileIdentity:
        """Return the explicitly selected MSP430 Protocol v1 identity."""

        return MSP430_HEALTH_V1_SERIAL_IDENTITY

    @property
    def evidence_source(self) -> EvidenceSource:
        """Return caller-selected provenance without upgrading it."""

        return self._evidence_source

    @property
    def capabilities(self) -> DeviceCapabilities:
        """Return the static read-only host contract, not detected hardware."""

        return MSP430_HEALTH_V1_READ_ONLY_CAPABILITIES

    @property
    def initial_capabilities(self) -> DeviceCapabilities:
        """Return the same static contract through the generic profile port."""

        return self.capabilities

    @property
    def last_telemetry_sequence(self) -> int | None:
        """Return the accepted TEL continuity high-water mark."""

        return self._sequence.last_sequence

    def process_record(
        self,
        event: RawRecordEvent,
        event_log: BoundedRawEventLog,
    ) -> SerialProfileRecord[Msp430Message]:
        """Parse one device-output record and retain its exact outcome."""

        self._validate_event(event, event_log)
        with self._lock:
            previous_sequence = self._sequence.last_sequence
            try:
                message = parse_msp430_message(event.raw_bytes)
                measurements: tuple[Measurement, ...] = ()
                observation = None
                if isinstance(message, Msp430Telemetry):
                    measurements = self._map_telemetry(message, event)
                    observation = self._sequence.observe(message.sequence)
                parse_result = self._parse_summary(message, measurements)
            except ProtocolError as error:
                try:
                    rejected = event_log.mark_rejected(
                        event.event_id,
                        error_type=type(error).__name__,
                        error_message=str(error),
                    )
                except Exception:
                    self._restore_sequence(previous_sequence)
                    raise
                return SerialProfileRecord(self.identity, rejected, None)
            except Exception:
                self._restore_sequence(previous_sequence)
                raise

            try:
                parsed = event_log.mark_parsed(
                    event.event_id,
                    parse_result=parse_result,
                    sequence=observation,
                )
            except Exception:
                self._restore_sequence(previous_sequence)
                raise
            return SerialProfileRecord(
                self.identity,
                parsed,
                message,
                measurements,
            )

    def reset(self) -> SerialProfileResetResult:
        """Clear only TEL continuity; response correlation is stateless."""

        with self._lock:
            return SerialProfileResetResult(self._sequence.reset(), 0)

    def _validate_event(
        self,
        event: RawRecordEvent,
        event_log: BoundedRawEventLog,
    ) -> None:
        if not isinstance(event, RawRecordEvent):
            raise SerialProfileStateError("event must be a RawRecordEvent")
        if not isinstance(event_log, BoundedRawEventLog):
            raise SerialProfileStateError("event_log must be a BoundedRawEventLog")
        if event.profile_name != self.identity.name:
            raise SerialProfileStateError(
                f"event profile_name must be {self.identity.name}"
            )
        if event.status is not RawRecordStatus.PENDING_PROFILE:
            raise SerialProfileStateError("raw event already has a profile outcome")
        if event not in event_log.snapshot().events:
            raise SerialProfileStateError(
                "raw event is not retained by the supplied event log"
            )

    def _map_telemetry(
        self,
        message: Msp430Telemetry,
        event: RawRecordEvent,
    ) -> tuple[Measurement, ...]:
        raw_record_id = (
            f"serial-{event.received_at.strftime('%Y%m%dT%H%M%S%fZ')}-{event.event_id}"
        )
        try:
            return msp430_telemetry_to_measurements(
                message,
                received_at=event.received_at,
                raw_record_id=raw_record_id,
                source=self.evidence_source,
            )
        except ValidationError as error:
            raise SerialProfileStateError(
                "MSP430 telemetry mapping violated the profile contract"
            ) from error

    def _restore_sequence(self, previous_sequence: int | None) -> None:
        self._sequence.reset()
        if previous_sequence is not None:
            self._sequence.observe(previous_sequence)

    @staticmethod
    def _parse_summary(
        message: Msp430Message,
        measurements: tuple[Measurement, ...],
    ) -> str:
        details = [
            f"profile={MSP430_HEALTH_PROFILE_NAME}",
            f"version={MSP430_HEALTH_PROFILE_VERSION}",
            f"message={type(message).__name__}",
        ]
        if measurements:
            unavailable = sum(item.value is None for item in measurements)
            details.extend(
                (
                    f"measurements={len(measurements)}",
                    f"unavailable={unavailable}",
                )
            )
        return " ".join(details)


__all__ = [
    "MSP430_HEALTH_V1_SEQUENCE_BITS",
    "MSP430_HEALTH_V1_SERIAL_IDENTITY",
    "Msp430HealthV1SerialProfile",
]
