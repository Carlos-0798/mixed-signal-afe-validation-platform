"""Tests for bounded memory-only raw-record provenance."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest

from analog_validation.transport import (
    MAX_RAW_EVENT_BYTES,
    MAX_RAW_EVENTS,
    MAX_RAW_LOG_BYTES,
    MAX_RAW_METADATA_CHARS,
    MAX_RAW_RESULT_CHARS,
    RAW_EVENT_PRIVACY_NOTICE,
    BoundedRawEventLog,
    RawEventError,
    RawEventLimitError,
    RawEventNotFound,
    RawRecordEvent,
    RawRecordStatus,
    SequenceTracker,
)

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def make_event(**overrides: object) -> RawRecordEvent:
    values: dict[str, object] = {
        "event_id": 1,
        "received_at": NOW,
        "port_id": "MEMORY:AFE",
        "profile_name": "AFE_V1",
        "raw_bytes": b"AFE,1\n",
    }
    values.update(overrides)
    return RawRecordEvent(**cast(Any, values))


def test_pending_event_normalizes_timezone_and_bytes_without_parsing() -> None:
    eastern = timezone(timedelta(hours=-4))

    event = make_event(
        received_at=datetime(2026, 8, 30, 8, 0, tzinfo=eastern),
        raw_bytes=bytearray(b"AFE,1\n"),
    )

    assert event.received_at == NOW
    assert event.raw_bytes == b"AFE,1\n"
    assert isinstance(event.raw_bytes, bytes)
    assert event.status is RawRecordStatus.PENDING_PROFILE
    assert event.parse_result is None
    assert event.error_type is None
    assert event.error_message is None
    assert event.sequence is None


def test_all_bytes_like_inputs_and_immutable_event_are_supported() -> None:
    event = make_event(raw_bytes=memoryview(b"X\n"))

    assert event.raw_bytes == b"X\n"
    with pytest.raises(FrozenInstanceError):
        event.port_id = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("overrides", "error", "match"),
    [
        ({"event_id": 0}, RawEventLimitError, "event_id"),
        ({"event_id": True}, RawEventError, "event_id"),
        ({"received_at": "now"}, RawEventError, "datetime"),
        (
            {"received_at": datetime(2026, 8, 30, 12, 0)},  # noqa: DTZ001
            RawEventError,
            "timezone-aware",
        ),
        ({"port_id": 7}, RawEventError, "port_id"),
        ({"port_id": ""}, RawEventError, "port_id"),
        ({"port_id": " COM1"}, RawEventError, "port_id"),
        ({"port_id": "COM\n1"}, RawEventError, "port_id"),
        (
            {"profile_name": "P" * (MAX_RAW_METADATA_CHARS + 1)},
            RawEventLimitError,
            "profile_name",
        ),
        ({"raw_bytes": "X\n"}, RawEventError, "bytes-like"),
        ({"raw_bytes": b""}, RawEventError, "non-empty"),
        (
            {"raw_bytes": b"X" * (MAX_RAW_EVENT_BYTES + 1)},
            RawEventLimitError,
            "event limit",
        ),
        ({"status": "PARSED"}, RawEventError, "RawRecordStatus"),
        ({"sequence": "FIRST"}, RawEventError, "SequenceObservation"),
        ({"parse_result": "ok"}, RawEventError, "pending"),
        (
            {"status": RawRecordStatus.PARSED},
            RawEventError,
            "parse_result",
        ),
        (
            {
                "status": RawRecordStatus.PARSED,
                "parse_result": "ok",
                "error_type": "CRC",
            },
            RawEventError,
            "cannot contain errors",
        ),
        (
            {
                "status": RawRecordStatus.REJECTED,
                "error_type": "CRC",
                "error_message": "bad",
                "parse_result": "ok",
            },
            RawEventError,
            "cannot contain a parse result",
        ),
    ],
)
def test_event_validation_is_strict(
    overrides: dict[str, object],
    error: type[Exception],
    match: str,
) -> None:
    with pytest.raises(error, match=match):
        make_event(**overrides)


@pytest.mark.parametrize(
    "field",
    ["parse_result", "error_type", "error_message", "sequence"],
)
def test_pending_event_rejects_every_outcome_field(field: str) -> None:
    value: object = SequenceTracker(8).observe(1) if field == "sequence" else "value"

    with pytest.raises(RawEventError, match="pending"):
        make_event(**{field: value})


def test_parsed_and_rejected_models_enforce_bounded_single_line_summaries() -> None:
    observation = SequenceTracker(16).observe(9)
    parsed = make_event(
        status=RawRecordStatus.PARSED,
        parse_result="profile=AFE_V1 fields=4",
        sequence=observation,
    )
    rejected = make_event(
        status=RawRecordStatus.REJECTED,
        error_type="CrcMismatch",
        error_message="CRC validation failed",
    )

    assert parsed.sequence is observation
    assert rejected.error_type == "CrcMismatch"
    with pytest.raises(RawEventError, match="single-line"):
        make_event(
            status=RawRecordStatus.PARSED,
            parse_result="line one\nline two",
        )
    with pytest.raises(RawEventLimitError, match="parse_result"):
        make_event(
            status=RawRecordStatus.PARSED,
            parse_result="X" * (MAX_RAW_RESULT_CHARS + 1),
        )
    with pytest.raises(RawEventError, match="error_message"):
        make_event(
            status=RawRecordStatus.REJECTED,
            error_type="CRC",
            error_message="",
        )


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("max_events", 0),
        ("max_events", True),
        ("max_events", MAX_RAW_EVENTS + 1),
        ("max_total_bytes", 0),
        ("max_total_bytes", 1.5),
        ("max_total_bytes", MAX_RAW_LOG_BYTES + 1),
    ],
)
def test_log_configuration_has_hard_resource_bounds(name: str, value: object) -> None:
    settings: dict[str, object] = {name: value}

    with pytest.raises((RawEventError, RawEventLimitError), match=name):
        BoundedRawEventLog(**cast(Any, settings))


def test_log_evicts_by_count_and_byte_budget_with_auditable_counters() -> None:
    log = BoundedRawEventLog(max_events=2, max_total_bytes=6)

    first = log.append_received(
        received_at=NOW,
        port_id="MEM",
        profile_name="AFE_V1",
        raw_bytes=b"A\n",
    )
    second = log.append_received(
        received_at=NOW,
        port_id="MEM",
        profile_name="AFE_V1",
        raw_bytes=b"BB\n",
    )
    third = log.append_received(
        received_at=NOW,
        port_id="MEM",
        profile_name="AFE_V1",
        raw_bytes=b"CCC\n",
    )
    snapshot = log.snapshot()

    assert log.max_events == 2
    assert log.max_total_bytes == 6
    assert first.event_id == 1
    assert second.event_id == 2
    assert third.event_id == 3
    assert snapshot.events == (third,)
    assert snapshot.retained_bytes == 4
    assert snapshot.dropped_events == 2
    assert snapshot.dropped_bytes == 5


def test_log_marks_pending_events_without_mutating_prior_values() -> None:
    log = BoundedRawEventLog(max_events=4, max_total_bytes=32)
    pending = log.append_received(
        received_at=NOW,
        port_id="MEM",
        profile_name="AFE_V1",
        raw_bytes=b"A\n",
    )
    rejected_pending = log.append_received(
        received_at=NOW,
        port_id="MEM",
        profile_name="AFE_V1",
        raw_bytes=b"B\n",
    )
    observation = SequenceTracker(8).observe(3)

    parsed = log.mark_parsed(
        pending.event_id,
        parse_result="profile=AFE_V1 fields=2",
        sequence=observation,
    )
    rejected = log.mark_rejected(
        rejected_pending.event_id,
        error_type="CrcMismatch",
        error_message="CRC validation failed",
    )

    assert pending.status is RawRecordStatus.PENDING_PROFILE
    assert parsed.status is RawRecordStatus.PARSED
    assert parsed.sequence is observation
    assert rejected.status is RawRecordStatus.REJECTED
    assert log.snapshot().events == (parsed, rejected)
    with pytest.raises(RawEventError, match="already"):
        log.mark_parsed(parsed.event_id, parse_result="again")


def test_missing_evicted_and_invalid_event_ids_cannot_be_updated() -> None:
    log = BoundedRawEventLog(max_events=1, max_total_bytes=16)
    evicted = log.append_received(
        received_at=NOW,
        port_id="MEM",
        profile_name="AFE_V1",
        raw_bytes=b"A\n",
    )
    log.append_received(
        received_at=NOW,
        port_id="MEM",
        profile_name="AFE_V1",
        raw_bytes=b"B\n",
    )

    with pytest.raises(RawEventNotFound, match="evicted"):
        log.mark_rejected(
            evicted.event_id,
            error_type="Old",
            error_message="already evicted",
        )
    with pytest.raises(RawEventError, match="event_id"):
        log.mark_parsed(cast(Any, True), parse_result="bad id")


def test_oversize_for_configured_log_is_rejected_without_eviction() -> None:
    log = BoundedRawEventLog(max_events=2, max_total_bytes=2)

    with pytest.raises(RawEventLimitError, match="total byte limit"):
        log.append_received(
            received_at=NOW,
            port_id="MEM",
            profile_name="AFE_V1",
            raw_bytes=b"ABC",
        )
    assert log.snapshot().events == ()


def test_clear_returns_evidence_resets_counters_and_keeps_ids_monotonic() -> None:
    log = BoundedRawEventLog(max_events=1, max_total_bytes=8)
    log.append_received(
        received_at=NOW,
        port_id="MEM",
        profile_name="AFE_V1",
        raw_bytes=b"A\n",
    )
    log.append_received(
        received_at=NOW,
        port_id="MEM",
        profile_name="AFE_V1",
        raw_bytes=b"B\n",
    )

    previous = log.clear()
    after_clear = log.snapshot()
    new = log.append_received(
        received_at=NOW,
        port_id="MEM",
        profile_name="AFE_V1",
        raw_bytes=b"C\n",
    )

    assert previous.dropped_events == 1
    assert after_clear.events == ()
    assert after_clear.dropped_events == 0
    assert after_clear.dropped_bytes == 0
    assert after_clear.retained_bytes == 0
    assert new.event_id == 3
    with pytest.raises(FrozenInstanceError):
        previous.retained_bytes = 0  # type: ignore[misc]


def test_privacy_notice_makes_storage_and_upload_boundaries_explicit() -> None:
    assert "memory-only" in RAW_EVENT_PRIVACY_NOTICE
    assert "never persisted or uploaded automatically" in RAW_EVENT_PRIVACY_NOTICE
    assert "device identifiers" in RAW_EVENT_PRIVACY_NOTICE
