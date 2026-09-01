"""Deterministic 100-frame synthetic AFE v1 integration pipeline."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from analog_validation import MAX_RECORD_BYTES, EvidenceSource
from analog_validation.protocol import (
    AfeTelemetry,
    encode_afe_message,
    parse_afe_message,
    telemetry_to_measurements,
)
from tools.telemetry_simulator import generate

EXPECTED_STREAM_SHA256 = (
    "dad90b14abfed3d2a645902458d40b204242f233766d13abdc7fc6b5894cbb94"
)


def test_one_hundred_synthetic_frames_round_trip_and_preserve_provenance() -> None:
    messages = list(generate(count=100, interval_ms=10, seed=430))
    records = [encode_afe_message(message) for message in messages]
    parsed = [parse_afe_message(record) for record in records]

    assert len(messages) == len(records) == len(parsed) == 100
    assert parsed == messages
    assert all(isinstance(message, AfeTelemetry) for message in parsed)
    assert all(len(record.encode("ascii")) <= MAX_RECORD_BYTES for record in records)
    assert hashlib.sha256("".join(records).encode("ascii")).hexdigest() == (
        EXPECTED_STREAM_SHA256
    )

    start = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    measurements = tuple(
        measurement
        for index, message in enumerate(messages)
        for measurement in telemetry_to_measurements(
            message,
            received_at=start + timedelta(milliseconds=message.time_ms),
            raw_record_id=f"synthetic-{index:03d}",
            source=EvidenceSource.SYNTHETIC,
        )
    )
    assert len(measurements) == 400
    assert all(item.source is EvidenceSource.SYNTHETIC for item in measurements)
    assert not any(item.is_bench_evidence for item in measurements)
    assert {item.raw_record_id for item in measurements} == {
        f"synthetic-{index:03d}" for index in range(100)
    }
