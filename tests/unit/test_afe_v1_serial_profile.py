"""Focused behavior tests for the stateful AFE v1 serial profile."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

import pytest

from analog_validation.domain import (
    DeviceCommand,
    EvidenceSource,
    MeasurementStatus,
    MeasurementUnit,
    QualityFlag,
)
from analog_validation.errors import ConfigurationError, ValidationError
from analog_validation.profiles import (
    AFE_V1_SEQUENCE_BITS,
    AFE_V1_SERIAL_IDENTITY,
    AfeV1SerialProfile,
    SerialProfile,
    SerialProfileRecord,
    SerialProfileStateError,
)
from analog_validation.protocol import (
    AFE_PROFILE_NAME,
    AFE_PROFILE_VERSION,
    AfeCapabilityChannel,
    AfeCapabilityDevice,
    AfeCapabilityEnd,
    AfeCommand,
    AfeCommandKind,
    AfeMessage,
    AfeTelemetry,
    CapabilityChannelKind,
    encode_afe_message,
    validate_command_capability,
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


def telemetry(**changes: Any) -> AfeTelemetry:
    values: dict[str, Any] = {
        "seq": 10,
        "time_ms": 1000,
        "channel": 0,
        "input_mv": 500,
        "output_mv": 1500,
        "gain_milli": 3000,
        "threshold": 1,
        "fault_flags": 0,
    }
    values.update(changes)
    return AfeTelemetry(**values)


def append_raw(
    log: BoundedRawEventLog,
    raw: bytes,
    *,
    profile_name: str = AFE_PROFILE_NAME,
) -> RawRecordEvent:
    return log.append_received(
        received_at=NOW,
        port_id="MEMORY:AFE",
        profile_name=profile_name,
        raw_bytes=raw,
    )


def append_message(
    log: BoundedRawEventLog,
    message: AfeMessage,
    *,
    profile_name: str = AFE_PROFILE_NAME,
) -> RawRecordEvent:
    return append_raw(
        log,
        encode_afe_message(message).encode("ascii"),
        profile_name=profile_name,
    )


def process_message(
    profile: AfeV1SerialProfile,
    log: BoundedRawEventLog,
    message: AfeMessage,
) -> SerialProfileRecord[AfeMessage]:
    return profile.process_record(append_message(log, message), log)


class FailingOutcomeLog(BoundedRawEventLog):
    """Event log whose final mutation can be failed after membership checks."""

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


def test_identity_and_port_contract_are_explicit_and_runtime_checkable() -> None:
    profile = AfeV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)

    assert isinstance(profile, SerialProfile)
    assert profile.identity is AFE_V1_SERIAL_IDENTITY
    assert profile.identity.name == AFE_PROFILE_NAME
    assert profile.identity.version == AFE_PROFILE_VERSION
    assert profile.identity.sequence_bits == AFE_V1_SEQUENCE_BITS == 16
    assert profile.identity.max_record_bytes == 128
    assert profile.evidence_source is EvidenceSource.HOST_TEST
    assert profile.last_telemetry_sequence is None
    assert profile.pending_capability_records == ()


def test_evidence_source_is_explicit_and_never_inferred_from_a_port() -> None:
    bench = AfeV1SerialProfile(evidence_source=EvidenceSource.BENCH_CONTROLLER)
    assert bench.evidence_source is EvidenceSource.BENCH_CONTROLLER

    with pytest.raises(SerialProfileStateError, match="EvidenceSource"):
        AfeV1SerialProfile(evidence_source=cast(Any, "HOST_TEST"))
    with pytest.raises(SerialProfileStateError, match="HOST_TEST or BENCH_CONTROLLER"):
        AfeV1SerialProfile(evidence_source=EvidenceSource.SYNTHETIC)


def test_telemetry_maps_to_canonical_channels_and_host_provenance() -> None:
    profile = AfeV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog()

    result = process_message(profile, log, telemetry())

    assert result.accepted
    assert result.event.status is RawRecordStatus.PARSED
    assert result.event.parse_result == (
        "profile=afe version=1 message=AfeTelemetry measurements=4"
    )
    assert result.event.sequence is not None
    assert result.event.sequence.disposition is SequenceDisposition.FIRST
    assert profile.last_telemetry_sequence == 10
    assert tuple(item.channel for item in result.measurements) == (
        "afe.ch0.input",
        "afe.ch0.output",
        "afe.ch0.gain",
        "afe.ch0.threshold",
    )
    assert tuple(item.value for item in result.measurements) == (500.0, 1500.0, 3.0, 1.0)
    assert tuple(item.unit for item in result.measurements) == (
        MeasurementUnit.MILLIVOLT,
        MeasurementUnit.MILLIVOLT,
        MeasurementUnit.RATIO,
        MeasurementUnit.BOOLEAN,
    )
    assert {item.source for item in result.measurements} == {
        EvidenceSource.HOST_TEST
    }
    assert {item.timestamp for item in result.measurements} == {NOW}
    assert len({item.raw_record_id for item in result.measurements}) == 1
    assert next(iter({item.raw_record_id for item in result.measurements})).startswith(
        "serial-20260830T120000"
    )
    assert all(item.status is MeasurementStatus.VALID for item in result.measurements)
    assert result.capabilities is None


def test_fault_telemetry_remains_suspect_instead_of_becoming_valid() -> None:
    profile = AfeV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog()

    result = process_message(profile, log, telemetry(fault_flags=0x0001))

    assert all(
        item.status is MeasurementStatus.SUSPECT for item in result.measurements
    )
    assert all(
        item.quality_flags == frozenset({QualityFlag.DEVICE_FAULT})
        for item in result.measurements
    )


def test_only_telemetry_uses_continuity_tracking() -> None:
    profile = AfeV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog()

    command = process_message(
        profile,
        log,
        AfeCommand(100, AfeCommandKind.GET_STATUS, channel=0),
    )
    first = process_message(profile, log, telemetry(seq=65535))
    wrapped = process_message(profile, log, telemetry(seq=0))
    gap = process_message(profile, log, telemetry(seq=3))
    duplicate = process_message(profile, log, telemetry(seq=3))
    old = process_message(profile, log, telemetry(seq=2))

    assert command.event.sequence is None
    assert command.event.parse_result == "profile=afe version=1 message=AfeCommand"
    assert [
        cast(SequenceObservation, item.event.sequence).disposition
        for item in (first, wrapped, gap, duplicate, old)
    ] == [
        SequenceDisposition.FIRST,
        SequenceDisposition.IN_ORDER,
        SequenceDisposition.GAP,
        SequenceDisposition.DUPLICATE,
        SequenceDisposition.OUT_OF_ORDER,
    ]
    assert cast(SequenceObservation, gap.event.sequence).missing_count == 2
    assert profile.last_telemetry_sequence == 3


def test_capability_records_aggregate_and_keep_frozen_wire_channel_semantics() -> None:
    profile = AfeV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog()
    commands = frozenset(DeviceCommand)
    records: tuple[AfeMessage, ...] = (
        AfeCapabilityDevice(77, "sim-afe-1", commands),
        AfeCapabilityChannel(
            77,
            CapabilityChannelKind.ADC,
            0,
            0,
            3300,
            MeasurementUnit.MILLIVOLT,
        ),
        AfeCapabilityChannel(
            77,
            CapabilityChannelKind.DAC,
            0,
            0,
            3300,
            MeasurementUnit.MILLIVOLT,
        ),
        AfeCapabilityChannel(
            77,
            CapabilityChannelKind.PWM,
            0,
            0,
            1,
            MeasurementUnit.RATIO,
        ),
        AfeCapabilityChannel(77, CapabilityChannelKind.DIGITAL_INPUT, 0),
        AfeCapabilityEnd(77, 4),
    )

    results = [process_message(profile, log, message) for message in records]
    capabilities = results[-1].capabilities

    assert all(result.accepted for result in results)
    assert all(result.event.sequence is None for result in results)
    assert capabilities is not None
    assert results[-1].event.parse_result is not None
    assert "capability_exchange=complete" in results[-1].event.parse_result
    assert capabilities.device_id == "sim-afe-1"
    assert capabilities.adc_channels == ("adc0",)
    assert capabilities.dac_channels == ("dac0",)
    assert capabilities.pwm_channels == ("pwm0",)
    assert capabilities.digital_input_channels == ("din0",)
    assert capabilities.automated_output_allowed
    assert profile.pending_capability_records == ()

    safe_command = AfeCommand(
        90,
        AfeCommandKind.SET_STIMULUS_MV,
        channel=0,
        value=1650,
    )
    validate_command_capability(safe_command, capabilities)
    unsafe_command = AfeCommand(
        91,
        AfeCommandKind.SET_STIMULUS_MV,
        channel=0,
        value=-1,
    )
    with pytest.raises(ConfigurationError, match="outside"):
        validate_command_capability(unsafe_command, capabilities)


@pytest.mark.parametrize(
    ("messages", "match"),
    [
        (
            (AfeCapabilityChannel(1, CapabilityChannelKind.DIGITAL_INPUT, 0),),
            "before DEVICE",
        ),
        ((AfeCapabilityEnd(1, 0),), "before DEVICE"),
        (
            (
                AfeCapabilityDevice(1, "first"),
                AfeCapabilityDevice(2, "second"),
            ),
            "before the prior response END",
        ),
        (
            (
                AfeCapabilityDevice(1, "device"),
                AfeCapabilityChannel(2, CapabilityChannelKind.DIGITAL_INPUT, 0),
            ),
            "sequence numbers do not match",
        ),
        (
            (
                AfeCapabilityDevice(1, "device"),
                AfeCapabilityChannel(1, CapabilityChannelKind.DIGITAL_INPUT, 0),
                AfeCapabilityEnd(1, 0),
            ),
            "entry count does not match",
        ),
        (
            (
                AfeCapabilityDevice(
                    1,
                    "device",
                    frozenset({DeviceCommand.READ_MEASUREMENT}),
                ),
                AfeCapabilityEnd(1, 0),
            ),
            "invalid capability response",
        ),
    ],
)
def test_invalid_capability_transactions_are_rejected_and_state_recovers(
    messages: tuple[AfeMessage, ...], match: str
) -> None:
    profile = AfeV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog()

    results = [process_message(profile, log, message) for message in messages]

    assert results[-1].event.status is RawRecordStatus.REJECTED
    assert results[-1].event.error_type == "ProtocolError"
    assert results[-1].event.error_message is not None
    assert match in results[-1].event.error_message
    assert not results[-1].accepted
    assert profile.pending_capability_records == ()

    recovered = process_message(profile, log, telemetry(seq=5))
    assert recovered.accepted
    assert cast(SequenceObservation, recovered.event.sequence).disposition is (
        SequenceDisposition.FIRST
    )


def test_protocol_rejection_is_bounded_and_does_not_advance_sequence() -> None:
    profile = AfeV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog()
    good = process_message(profile, log, telemetry(seq=10))
    damaged = bytearray(encode_afe_message(telemetry(seq=11)).encode("ascii"))
    damaged[-3] = ord("0") if damaged[-3] != ord("0") else ord("1")

    rejected = profile.process_record(append_raw(log, bytes(damaged)), log)

    assert good.accepted
    assert not rejected.accepted
    assert rejected.event.status is RawRecordStatus.REJECTED
    assert rejected.event.error_type == "CrcMismatch"
    assert rejected.event.error_message is not None
    assert "CRC mismatch" in rejected.event.error_message
    assert rejected.event.sequence is None
    assert profile.last_telemetry_sequence == 10


def test_reset_reports_discarded_sequence_and_capability_state() -> None:
    profile = AfeV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog()
    process_message(profile, log, telemetry(seq=44))
    process_message(profile, log, AfeCapabilityDevice(9, "device"))

    reset = profile.reset()

    assert reset.previous_sequence == 44
    assert reset.discarded_records == 1
    assert profile.last_telemetry_sequence is None
    assert profile.pending_capability_records == ()
    assert profile.reset().previous_sequence is None


def test_profile_rejects_wrong_or_stale_event_context_without_relabeling_bytes() -> None:
    profile = AfeV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog()
    event = append_message(log, telemetry())

    with pytest.raises(SerialProfileStateError, match="event must"):
        profile.process_record(cast(Any, object()), log)
    with pytest.raises(SerialProfileStateError, match="event_log must"):
        profile.process_record(event, cast(Any, object()))

    wrong_log = BoundedRawEventLog()
    wrong_profile = append_message(wrong_log, telemetry(), profile_name="other")
    with pytest.raises(SerialProfileStateError, match="profile_name must be afe"):
        profile.process_record(wrong_profile, wrong_log)

    separate_log = BoundedRawEventLog()
    with pytest.raises(SerialProfileStateError, match="not retained"):
        profile.process_record(event, separate_log)

    profile.process_record(event, log)
    with pytest.raises(SerialProfileStateError, match="already"):
        profile.process_record(log.snapshot().events[0], log)


def test_state_rolls_back_if_raw_log_cannot_store_a_parsed_outcome() -> None:
    profile = AfeV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = FailingOutcomeLog()
    process_message(profile, log, telemetry(seq=10))
    process_message(profile, log, AfeCapabilityDevice(77, "device"))
    pending_before = profile.pending_capability_records
    event = append_message(log, telemetry(seq=12))
    log.fail_parsed = True

    with pytest.raises(RawEventError, match="injected"):
        profile.process_record(event, log)

    assert profile.last_telemetry_sequence == 10
    assert profile.pending_capability_records == pending_before
    assert event.status is RawRecordStatus.PENDING_PROFILE


def test_state_rolls_back_if_raw_log_cannot_store_a_rejection() -> None:
    profile = AfeV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = FailingOutcomeLog()
    process_message(profile, log, telemetry(seq=10))
    process_message(profile, log, AfeCapabilityDevice(77, "device"))
    pending_before = profile.pending_capability_records
    event = append_raw(log, b"not-an-afe-frame\n")
    log.fail_rejected = True

    with pytest.raises(RawEventError, match="injected"):
        profile.process_record(event, log)

    assert profile.last_telemetry_sequence == 10
    assert profile.pending_capability_records == pending_before
    assert event.status is RawRecordStatus.PENDING_PROFILE


def test_unexpected_mapping_contract_failure_is_not_mislabeled_as_wire_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = AfeV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog()
    process_message(profile, log, telemetry(seq=10))
    event = append_message(log, telemetry(seq=11))

    def fail_mapping(*args: object, **kwargs: object) -> str:
        del args, kwargs
        raise ValidationError("injected mapping contract failure")

    monkeypatch.setattr(
        "analog_validation.profiles.afe_v1.convert_afe_channel",
        fail_mapping,
    )

    with pytest.raises(SerialProfileStateError, match="mapping violated"):
        profile.process_record(event, log)

    assert profile.last_telemetry_sequence == 10
    assert event.status is RawRecordStatus.PENDING_PROFILE
