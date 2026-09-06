"""AFE v1 business parsing over retained raw serial records."""

from __future__ import annotations

from dataclasses import replace
from threading import RLock

from analog_validation.domain import DeviceCapabilities, EvidenceSource, Measurement
from analog_validation.errors import ProtocolError, ValidationError
from analog_validation.protocol.afe_channels import (
    AfeChannelNaming,
    convert_afe_channel,
)
from analog_validation.protocol.afe_v1 import (
    AFE_PROFILE_NAME,
    AFE_PROFILE_VERSION,
    AfeCapabilityChannel,
    AfeCapabilityDevice,
    AfeCapabilityEnd,
    AfeCapabilityMessage,
    AfeMessage,
    AfeTelemetry,
    capability_messages_to_domain,
    parse_afe_message,
    telemetry_to_measurements,
)
from analog_validation.protocol.framing import MAX_RECORD_BYTES
from analog_validation.transport import (
    BoundedRawEventLog,
    RawRecordEvent,
    RawRecordStatus,
    SequenceTracker,
)

from .core import (
    SerialProfileIdentity,
    SerialProfileRecord,
    SerialProfileResetResult,
)
from .errors import SerialProfileStateError

AFE_V1_SEQUENCE_BITS = 16
AFE_V1_SERIAL_IDENTITY = SerialProfileIdentity(
    name=AFE_PROFILE_NAME,
    version=AFE_PROFILE_VERSION,
    sequence_bits=AFE_V1_SEQUENCE_BITS,
    max_record_bytes=MAX_RECORD_BYTES,
)

_ALLOWED_SERIAL_EVIDENCE = frozenset(
    {EvidenceSource.HOST_TEST, EvidenceSource.BENCH_CONTROLLER}
)


class AfeV1SerialProfile:
    """Stateful AFE v1 serial profile with fail-closed capability aggregation.

    Telemetry sequence values form the continuity stream. Command sequences and
    the repeated sequence on a multi-record capability response are transaction
    correlation values, so they are validated by their message/transaction
    rules instead of being misclassified as duplicate telemetry.
    """

    def __init__(self, *, evidence_source: EvidenceSource) -> None:
        if not isinstance(evidence_source, EvidenceSource):
            raise SerialProfileStateError("evidence_source must be an EvidenceSource")
        if evidence_source not in _ALLOWED_SERIAL_EVIDENCE:
            raise SerialProfileStateError(
                "AFE serial evidence_source must be HOST_TEST or BENCH_CONTROLLER"
            )
        self._evidence_source = evidence_source
        self._sequence = SequenceTracker(AFE_V1_SEQUENCE_BITS)
        self._capability_records: list[AfeCapabilityMessage] = []
        self._lock = RLock()

    @property
    def identity(self) -> SerialProfileIdentity:
        """Return the frozen AFE v1 serial identity."""

        return AFE_V1_SERIAL_IDENTITY

    @property
    def evidence_source(self) -> EvidenceSource:
        """Return explicit provenance; the profile never infers or upgrades it."""

        return self._evidence_source

    @property
    def initial_capabilities(self) -> None:
        """Require a complete AFE capability response from the byte stream."""

        return None

    @property
    def last_telemetry_sequence(self) -> int | None:
        """Return the accepted telemetry high-water mark."""

        return self._sequence.last_sequence

    @property
    def pending_capability_records(self) -> tuple[AfeCapabilityMessage, ...]:
        """Return incomplete capability transaction state for diagnostics."""

        with self._lock:
            return tuple(self._capability_records)

    def process_record(
        self,
        event: RawRecordEvent,
        event_log: BoundedRawEventLog,
    ) -> SerialProfileRecord[AfeMessage]:
        """Decode, map, and record one AFE raw-event outcome exactly once."""

        self._validate_event(event, event_log)
        with self._lock:
            previous_sequence = self._sequence.last_sequence
            previous_capabilities = tuple(self._capability_records)
            try:
                message = parse_afe_message(event.raw_bytes)
                measurements: tuple[Measurement, ...] = ()
                capabilities: DeviceCapabilities | None = None
                observation = None
                if isinstance(message, AfeTelemetry):
                    observation = self._sequence.observe(message.seq)
                    measurements = self._map_telemetry(message, event)
                elif isinstance(
                    message,
                    (AfeCapabilityDevice, AfeCapabilityChannel, AfeCapabilityEnd),
                ):
                    capabilities = self._consume_capability(message)
                parse_result = self._parse_summary(message, measurements, capabilities)
            except ProtocolError as error:
                self._capability_records.clear()
                try:
                    rejected = event_log.mark_rejected(
                        event.event_id,
                        error_type=type(error).__name__,
                        error_message=str(error),
                    )
                except Exception:
                    self._restore_state(previous_sequence, previous_capabilities)
                    raise
                return SerialProfileRecord(self.identity, rejected, None)
            except Exception:
                self._restore_state(previous_sequence, previous_capabilities)
                raise

            try:
                parsed = event_log.mark_parsed(
                    event.event_id,
                    parse_result=parse_result,
                    sequence=observation,
                )
            except Exception:
                self._restore_state(previous_sequence, previous_capabilities)
                raise
            return SerialProfileRecord(
                self.identity,
                parsed,
                message,
                measurements,
                capabilities,
            )

    def reset(self) -> SerialProfileResetResult:
        """Clear telemetry continuity and incomplete capability response state."""

        with self._lock:
            previous_sequence = self._sequence.reset()
            discarded = len(self._capability_records)
            self._capability_records.clear()
            return SerialProfileResetResult(previous_sequence, discarded)

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
        message: AfeTelemetry,
        event: RawRecordEvent,
    ) -> tuple[Measurement, ...]:
        raw_record_id = (
            f"serial-{event.received_at.strftime('%Y%m%dT%H%M%S%fZ')}-{event.event_id}"
        )
        legacy = telemetry_to_measurements(
            message,
            received_at=event.received_at,
            raw_record_id=raw_record_id,
            source=self.evidence_source,
        )
        try:
            return tuple(
                replace(
                    measurement,
                    channel=convert_afe_channel(
                        measurement.channel,
                        source=AfeChannelNaming.LEGACY_TELEMETRY_V1,
                        target=AfeChannelNaming.CANONICAL,
                    ),
                )
                for measurement in legacy
            )
        except ValidationError as error:
            raise SerialProfileStateError(
                "AFE telemetry channel mapping violated the frozen profile contract"
            ) from error

    def _consume_capability(
        self,
        message: AfeCapabilityMessage,
    ) -> DeviceCapabilities | None:
        if isinstance(message, AfeCapabilityDevice):
            if self._capability_records:
                self._capability_records.clear()
                raise ProtocolError(
                    "capability DEVICE arrived before the prior response END"
                )
            self._capability_records.append(message)
            return None

        if not self._capability_records:
            raise ProtocolError("capability CHANNEL/END arrived before DEVICE")
        header = self._capability_records[0]
        assert isinstance(header, AfeCapabilityDevice)
        if message.seq != header.seq:
            self._capability_records.clear()
            raise ProtocolError("capability response sequence numbers do not match")

        if isinstance(message, AfeCapabilityChannel):
            self._capability_records.append(message)
            return None

        complete = (*self._capability_records, message)
        self._capability_records.clear()
        return capability_messages_to_domain(complete)

    def _restore_state(
        self,
        previous_sequence: int | None,
        previous_capabilities: tuple[AfeCapabilityMessage, ...],
    ) -> None:
        self._sequence.reset()
        if previous_sequence is not None:
            self._sequence.observe(previous_sequence)
        self._capability_records[:] = previous_capabilities

    @staticmethod
    def _parse_summary(
        message: AfeMessage,
        measurements: tuple[Measurement, ...],
        capabilities: DeviceCapabilities | None,
    ) -> str:
        message_type = type(message).__name__
        details = [
            f"profile={AFE_PROFILE_NAME}",
            f"version={AFE_PROFILE_VERSION}",
            f"message={message_type}",
        ]
        if measurements:
            details.append(f"measurements={len(measurements)}")
        if capabilities is not None:
            details.append("capability_exchange=complete")
        return " ".join(details)


__all__ = [
    "AFE_V1_SEQUENCE_BITS",
    "AFE_V1_SERIAL_IDENTITY",
    "AfeV1SerialProfile",
]
