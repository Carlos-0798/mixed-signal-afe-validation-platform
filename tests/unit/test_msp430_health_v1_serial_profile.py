"""State, provenance, and failure behavior for the read-only MSP430 profile."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

import pytest

from analog_validation.domain import EvidenceSource, MeasurementStatus
from analog_validation.errors import ValidationError
from analog_validation.profiles import (
    MSP430_HEALTH_V1_SEQUENCE_BITS,
    MSP430_HEALTH_V1_SERIAL_IDENTITY,
    Msp430HealthV1SerialProfile,
    SerialProfile,
    SerialProfileStateError,
)
from analog_validation.protocol.msp430_health_v1 import (
    MSP430_HEALTH_PROFILE_NAME,
    MSP430_HEALTH_PROFILE_VERSION,
    Msp430Ack,
    Msp430DeviceState,
    Msp430Message,
    Msp430Telemetry,
    encode_msp430_message,
)
from analog_validation.transport import (
    BoundedRawEventLog,
    RawEventError,
    RawRecordEvent,
    RawRecordStatus,
    SequenceDisposition,
    SequenceObservation,
)

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def telemetry(sequence: int = 10, *, faults: int = 0) -> Msp430Telemetry:
    return Msp430Telemetry(
        sequence,
        1000,
        421,
        418,
        5012,
        186,
        932,
        650,
        Msp430DeviceState.COOLING_HIGH,
        faults,
    )


def append_raw(
    log: BoundedRawEventLog,
    raw: bytes,
    *,
    profile_name: str = MSP430_HEALTH_PROFILE_NAME,
) -> RawRecordEvent:
    return log.append_received(
        received_at=NOW,
        port_id="MEMORY:MSP430",
        profile_name=profile_name,
        raw_bytes=raw,
    )


def append_message(
    log: BoundedRawEventLog,
    message: Msp430Message,
    *,
    profile_name: str = MSP430_HEALTH_PROFILE_NAME,
) -> RawRecordEvent:
    return append_raw(
        log,
        encode_msp430_message(message).encode("ascii"),
        profile_name=profile_name,
    )


class FailingOutcomeLog(BoundedRawEventLog):
    fail_parsed = False
    fail_rejected = False

    def mark_parsed(
        self,
        event_id: int,
        *,
        parse_result: str,
        sequence: SequenceObservation | None = None,
    ) -> RawRecordEvent:
        if self.fail_parsed:
            raise RawEventError("injected parsed-outcome failure")
        return super().mark_parsed(
            event_id,
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
        if self.fail_rejected:
            raise RawEventError("injected rejected-outcome failure")
        return super().mark_rejected(
            event_id,
            error_type=error_type,
            error_message=error_message,
        )


def test_identity_evidence_and_capabilities_are_explicitly_read_only() -> None:
    profile = Msp430HealthV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)

    assert isinstance(profile, SerialProfile)
    assert profile.identity is MSP430_HEALTH_V1_SERIAL_IDENTITY
    assert profile.identity.name == MSP430_HEALTH_PROFILE_NAME
    assert profile.identity.version == MSP430_HEALTH_PROFILE_VERSION
    assert profile.identity.sequence_bits == MSP430_HEALTH_V1_SEQUENCE_BITS == 32
    assert profile.identity.max_record_bytes == 128
    assert profile.evidence_source is EvidenceSource.HOST_TEST
    assert profile.capabilities.is_read_only
    assert not profile.capabilities.supports_safe_shutdown
    assert profile.last_telemetry_sequence is None


@pytest.mark.parametrize("source", [cast(Any, "HOST_TEST"), EvidenceSource.SYNTHETIC])
def test_constructor_rejects_implicit_or_incompatible_evidence(source: Any) -> None:
    with pytest.raises(SerialProfileStateError, match="evidence_source"):
        Msp430HealthV1SerialProfile(evidence_source=source)


def test_telemetry_maps_measurements_and_tracks_32_bit_wrap() -> None:
    profile = Msp430HealthV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog()

    first = profile.process_record(append_message(log, telemetry(0xFFFFFFFF)), log)
    wrapped = profile.process_record(append_message(log, telemetry(0)), log)

    assert first.accepted and wrapped.accepted
    assert len(first.measurements) == len(wrapped.measurements) == 5
    assert all(item.status is MeasurementStatus.VALID for item in first.measurements)
    assert first.event.sequence is not None
    assert first.event.sequence.disposition is SequenceDisposition.FIRST
    assert wrapped.event.sequence is not None
    assert wrapped.event.sequence.disposition is SequenceDisposition.IN_ORDER
    assert profile.last_telemetry_sequence == 0
    assert first.event.parse_result is not None
    assert "measurements=5" in first.event.parse_result
    assert "unavailable=0" in first.event.parse_result


def test_gap_duplicate_and_out_of_order_are_explainable() -> None:
    profile = Msp430HealthV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog()
    results = [
        profile.process_record(append_message(log, telemetry(sequence)), log)
        for sequence in (0, 3, 3, 2)
    ]

    assert [result.event.sequence.disposition for result in results if result.event.sequence] == [
        SequenceDisposition.FIRST,
        SequenceDisposition.GAP,
        SequenceDisposition.DUPLICATE,
        SequenceDisposition.OUT_OF_ORDER,
    ]
    assert cast(SequenceObservation, results[1].event.sequence).missing_count == 2
    assert profile.last_telemetry_sequence == 3


def test_response_records_parse_without_advancing_telemetry_continuity() -> None:
    profile = Msp430HealthV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog()
    first = profile.process_record(append_message(log, telemetry(10)), log)
    response = profile.process_record(append_message(log, Msp430Ack(99, True)), log)

    assert first.accepted and response.accepted
    assert response.event.sequence is None
    assert response.measurements == ()
    assert response.event.parse_result is not None
    assert "message=Msp430Ack" in response.event.parse_result
    assert profile.last_telemetry_sequence == 10


def test_unavailable_record_reports_count_without_turning_zeros_into_data() -> None:
    profile = Msp430HealthV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog()
    message = Msp430Telemetry(
        1, 1000, -32768, -32768, 0, 0, 0, 0, Msp430DeviceState.FAULT, 0x0015
    )

    result = profile.process_record(append_message(log, message), log)

    assert result.accepted
    assert [item.value for item in result.measurements] == [None, None, None, None, 0.0]
    assert result.event.parse_result is not None
    assert "unavailable=4" in result.event.parse_result
    assert result.message == message


def test_protocol_rejection_retains_raw_bytes_and_does_not_advance_sequence() -> None:
    profile = Msp430HealthV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog()
    profile.process_record(append_message(log, telemetry(10)), log)
    damaged = bytearray(encode_msp430_message(telemetry(11)).encode("ascii"))
    damaged[-3] = ord("0") if damaged[-3] != ord("0") else ord("1")

    result = profile.process_record(append_raw(log, bytes(damaged)), log)

    assert not result.accepted
    assert result.event.status is RawRecordStatus.REJECTED
    assert result.event.raw_bytes == bytes(damaged)
    assert result.event.error_type == "CrcMismatch"
    assert result.message is None
    assert result.measurements == ()
    assert profile.last_telemetry_sequence == 10


def test_reset_reports_prior_high_water_and_has_no_transaction_records() -> None:
    profile = Msp430HealthV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog()
    profile.process_record(append_message(log, telemetry(44)), log)

    reset = profile.reset()

    assert reset.previous_sequence == 44
    assert reset.discarded_records == 0
    assert profile.last_telemetry_sequence is None
    assert profile.reset().previous_sequence is None


def test_wrong_or_stale_event_context_is_not_mislabeled_as_wire_damage() -> None:
    profile = Msp430HealthV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog()
    event = append_message(log, telemetry())

    with pytest.raises(SerialProfileStateError, match="event must"):
        profile.process_record(cast(Any, object()), log)
    with pytest.raises(SerialProfileStateError, match="event_log must"):
        profile.process_record(event, cast(Any, object()))

    other_log = BoundedRawEventLog()
    wrong_profile = append_message(other_log, telemetry(), profile_name="other")
    with pytest.raises(SerialProfileStateError, match="profile_name must"):
        profile.process_record(wrong_profile, other_log)

    with pytest.raises(SerialProfileStateError, match="not retained"):
        profile.process_record(event, BoundedRawEventLog())

    profile.process_record(event, log)
    with pytest.raises(SerialProfileStateError, match="already"):
        profile.process_record(log.snapshot().events[0], log)


def test_state_rolls_back_when_raw_log_cannot_store_parsed_outcome() -> None:
    profile = Msp430HealthV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = FailingOutcomeLog()
    profile.process_record(append_message(log, telemetry(10)), log)
    event = append_message(log, telemetry(12))
    log.fail_parsed = True

    with pytest.raises(RawEventError, match="injected"):
        profile.process_record(event, log)

    assert profile.last_telemetry_sequence == 10
    assert event.status is RawRecordStatus.PENDING_PROFILE


def test_state_rolls_back_when_raw_log_cannot_store_rejection() -> None:
    profile = Msp430HealthV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = FailingOutcomeLog()
    profile.process_record(append_message(log, telemetry(10)), log)
    event = append_raw(log, b"not-a-valid-record\n")
    log.fail_rejected = True

    with pytest.raises(RawEventError, match="injected"):
        profile.process_record(event, log)

    assert profile.last_telemetry_sequence == 10
    assert event.status is RawRecordStatus.PENDING_PROFILE


def test_unexpected_mapping_contract_failure_propagates_as_profile_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = Msp430HealthV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog()
    profile.process_record(append_message(log, telemetry(10)), log)
    event = append_message(log, telemetry(11))

    def fail_mapping(*args: object, **kwargs: object) -> tuple[()]:
        del args, kwargs
        raise ValidationError("injected mapping failure")

    monkeypatch.setattr(
        "analog_validation.profiles.msp430_health_v1.msp430_telemetry_to_measurements",
        fail_mapping,
    )

    with pytest.raises(SerialProfileStateError, match="mapping violated"):
        profile.process_record(event, log)

    assert profile.last_telemetry_sequence == 10
    assert event.status is RawRecordStatus.PENDING_PROFILE
