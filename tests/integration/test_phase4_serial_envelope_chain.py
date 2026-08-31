"""Composite Step 3 proof from scripted serial bytes to explicit outcomes."""

from __future__ import annotations

from datetime import datetime, timezone

from analog_validation.errors import ProtocolError
from analog_validation.protocol.envelope import decode_crc_envelope, encode_crc_envelope
from analog_validation.transport import (
    RawRecordStatus,
    SequenceDisposition,
    SequenceTracker,
    SerialConnectionSettings,
    SerialPollStatus,
    SerialSession,
)
from tests.support import MemorySerialBackend

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def test_serial_stream_envelope_sequence_and_raw_outcome_chain() -> None:
    first = encode_crc_envelope(("AFE", "V1", "10")).encode("ascii")
    second = encode_crc_envelope(("AFE", "V1", "12")).encode("ascii")
    damaged = bytearray(encode_crc_envelope(("AFE", "V1", "13")).encode("ascii"))
    damaged[-3] = ord("0") if damaged[-3] != ord("0") else ord("1")
    backend = MemorySerialBackend.scripted(
        reads=(first[:5], first[5:] + second + bytes(damaged)),
    )
    session = SerialSession(
        backend,
        SerialConnectionSettings(
            port_id="MEMORY:CHAIN",
            profile_name="AFE_V1",
            read_chunk_bytes=128,
            max_record_bytes=64,
        ),
        clock=lambda: NOW,
    )
    tracker = SequenceTracker(16)
    session.open()

    partial = session.poll()
    received = session.poll()

    assert partial.status is SerialPollStatus.DATA
    assert partial.records == ()
    assert len(received.records) == 3
    for event in received.records:
        try:
            envelope = decode_crc_envelope(event.raw_bytes, max_record_bytes=64)
            observation = tracker.observe(int(envelope.fields[2]))
            session.event_log.mark_parsed(
                event.event_id,
                parse_result=f"profile=AFE_V1 fields={len(envelope.fields)}",
                sequence=observation,
            )
        except ProtocolError as error:
            session.event_log.mark_rejected(
                event.event_id,
                error_type=type(error).__name__,
                error_message="profile envelope validation failed",
            )

    outcomes = session.event_log.snapshot().events
    session.close()

    assert tuple(event.status for event in outcomes) == (
        RawRecordStatus.PARSED,
        RawRecordStatus.PARSED,
        RawRecordStatus.REJECTED,
    )
    assert outcomes[0].sequence is not None
    assert outcomes[0].sequence.disposition is SequenceDisposition.FIRST
    assert outcomes[1].sequence is not None
    assert outcomes[1].sequence.disposition is SequenceDisposition.GAP
    assert outcomes[1].sequence.missing_count == 1
    assert outcomes[2].sequence is None
    assert tracker.last_sequence == 12
    assert tuple(event.raw_bytes for event in outcomes) == (
        first,
        second,
        bytes(damaged),
    )
