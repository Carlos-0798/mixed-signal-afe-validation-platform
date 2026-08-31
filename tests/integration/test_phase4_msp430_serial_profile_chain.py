"""Memory serial -> MSP430 profile -> canonical read-only measurements."""

from __future__ import annotations

from datetime import datetime, timezone

from analog_validation.domain import EvidenceSource, MeasurementStatus, QualityFlag
from analog_validation.profiles import (
    MSP430_HEALTH_V1_SERIAL_IDENTITY,
    Msp430HealthV1SerialProfile,
)
from analog_validation.protocol.msp430_health_v1 import (
    Msp430Ack,
    Msp430DeviceState,
    Msp430Message,
    Msp430Telemetry,
    encode_msp430_message,
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


def encoded(message: Msp430Message) -> bytes:
    return encode_msp430_message(message).encode("ascii")


def test_memory_serial_to_read_only_msp430_profile_chain() -> None:
    normal = Msp430Telemetry(
        0xFFFFFFFF, 1000, 421, 418, 5012, 186, 932, 650,
        Msp430DeviceState.COOLING_HIGH, 0,
    )
    unavailable = Msp430Telemetry(
        0, 2000, -32768, -32768, 0, 0, 0, 0,
        Msp430DeviceState.FAULT, 0x0015,
    )
    records = (encoded(normal), encoded(unavailable), encoded(Msp430Ack(77, True)))
    damaged = bytearray(
        encoded(
            Msp430Telemetry(
                1, 3000, 422, 419, 5000, 180, 900, 500,
                Msp430DeviceState.NORMAL, 0,
            )
        )
    )
    damaged[-3] = ord("0") if damaged[-3] != ord("0") else ord("1")
    expected_raw = (*records, bytes(damaged))
    stream = b"".join(expected_raw)
    backend = MemorySerialBackend.scripted(reads=(stream[:19], stream[19:]))
    settings = SerialConnectionSettings(
        port_id="MEMORY:MSP430-CHAIN",
        profile_name=MSP430_HEALTH_V1_SERIAL_IDENTITY.name,
        read_chunk_bytes=512,
        max_record_bytes=MSP430_HEALTH_V1_SERIAL_IDENTITY.max_record_bytes,
    )
    session = SerialSession(backend, settings, clock=lambda: NOW)
    profile = Msp430HealthV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)

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
    assert len(results) == 4
    assert tuple(result.event.raw_bytes for result in results) == expected_raw
    assert tuple(result.event.status for result in results) == (
        RawRecordStatus.PARSED,
        RawRecordStatus.PARSED,
        RawRecordStatus.PARSED,
        RawRecordStatus.REJECTED,
    )
    assert results[0].event.sequence is not None
    assert results[0].event.sequence.disposition is SequenceDisposition.FIRST
    assert results[1].event.sequence is not None
    assert results[1].event.sequence.disposition is SequenceDisposition.IN_ORDER
    assert len(results[0].measurements) == len(results[1].measurements) == 5
    assert all(item.status is MeasurementStatus.VALID for item in results[0].measurements)
    assert [item.value for item in results[1].measurements] == [
        None, None, None, None, 0.0
    ]
    assert QualityFlag.MISSING in results[1].measurements[0].quality_flags
    assert results[2].measurements == ()
    assert results[2].event.sequence is None
    assert results[3].event.error_type == "CrcMismatch"
    assert profile.last_telemetry_sequence == 0
    assert profile.capabilities.is_read_only
    assert not profile.capabilities.supports_safe_shutdown
    assert backend.open_calls == [settings]
    assert backend.close_calls == 1
