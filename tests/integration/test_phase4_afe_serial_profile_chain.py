"""Step 4 composite proof from memory serial bytes through AFE domain outputs."""

from __future__ import annotations

from datetime import datetime, timezone

from analog_validation.domain import DeviceCommand, EvidenceSource, MeasurementUnit
from analog_validation.profiles import AFE_V1_SERIAL_IDENTITY, AfeV1SerialProfile
from analog_validation.protocol import (
    AfeCapabilityChannel,
    AfeCapabilityDevice,
    AfeCapabilityEnd,
    AfeMessage,
    AfeTelemetry,
    CapabilityChannelKind,
    encode_afe_message,
)
from analog_validation.transport import (
    RawRecordStatus,
    SequenceDisposition,
    SerialConnectionSettings,
    SerialPollStatus,
    SerialSession,
)
from tests.support import MemorySerialBackend

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def encoded(message: AfeMessage) -> bytes:
    return encode_afe_message(message).encode("ascii")


def test_memory_serial_to_afe_profile_measurement_capability_and_error_chain() -> None:
    records = (
        encoded(AfeTelemetry(65535, 1000, 0, 500, 1500, 3000, 0, 0)),
        encoded(AfeTelemetry(0, 1010, 0, 510, 1530, 3000, 1, 0)),
        encoded(
            AfeCapabilityDevice(
                77,
                "memory-afe",
                frozenset({DeviceCommand.READ_MEASUREMENT}),
            )
        ),
        encoded(
            AfeCapabilityChannel(
                77,
                CapabilityChannelKind.ADC,
                0,
                0,
                3300,
                MeasurementUnit.MILLIVOLT,
            )
        ),
        encoded(AfeCapabilityEnd(77, 1)),
    )
    damaged = bytearray(
        encoded(AfeTelemetry(1, 1020, 0, 520, 1560, 3000, 1, 0))
    )
    damaged[-3] = ord("0") if damaged[-3] != ord("0") else ord("1")
    expected_raw = (*records, bytes(damaged))
    stream = b"".join(expected_raw)
    backend = MemorySerialBackend.scripted(reads=(stream[:17], stream[17:]))
    settings = SerialConnectionSettings(
        port_id="MEMORY:AFE-CHAIN",
        profile_name=AFE_V1_SERIAL_IDENTITY.name,
        read_chunk_bytes=512,
        max_record_bytes=AFE_V1_SERIAL_IDENTITY.max_record_bytes,
    )
    session = SerialSession(backend, settings, clock=lambda: NOW)
    profile = AfeV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)

    session.open()
    partial = session.poll()
    received = session.poll()
    results = tuple(
        profile.process_record(event, session.event_log) for event in received.records
    )
    session.close()

    assert partial.status is SerialPollStatus.DATA
    assert partial.records == ()
    assert received.status is SerialPollStatus.DATA
    assert len(results) == 6
    assert tuple(result.event.raw_bytes for result in results) == expected_raw
    assert tuple(result.event.status for result in results) == (
        RawRecordStatus.PARSED,
        RawRecordStatus.PARSED,
        RawRecordStatus.PARSED,
        RawRecordStatus.PARSED,
        RawRecordStatus.PARSED,
        RawRecordStatus.REJECTED,
    )
    assert results[0].event.sequence is not None
    assert results[0].event.sequence.disposition is SequenceDisposition.FIRST
    assert results[1].event.sequence is not None
    assert results[1].event.sequence.disposition is SequenceDisposition.IN_ORDER
    assert len(results[0].measurements) == len(results[1].measurements) == 4
    assert results[4].capabilities is not None
    assert results[4].capabilities.adc_channels == ("adc0",)
    assert results[4].capabilities.is_read_only
    assert results[5].event.error_type == "CrcMismatch"
    assert profile.last_telemetry_sequence == 0
    assert backend.open_calls == [settings]
    assert backend.close_calls == 1
