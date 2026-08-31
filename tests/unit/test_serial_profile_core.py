"""Tests for the controller-neutral serial-profile contract."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

import pytest

from analog_validation import profiles
from analog_validation.domain import DeviceCapabilities
from analog_validation.profiles import (
    MAX_PROFILE_IDENTITY_CHARS,
    SERIAL_PROFILE_SCHEMA_VERSION,
    SerialProfileIdentity,
    SerialProfileRecord,
    SerialProfileResetResult,
    SerialProfileStateError,
)
from analog_validation.transport import BoundedRawEventLog, RawRecordEvent

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def test_profile_namespace_exports_are_explicit() -> None:
    assert profiles.__all__ == [
        "AFE_V1_SEQUENCE_BITS",
        "AFE_V1_SERIAL_IDENTITY",
        "MAX_PROFILE_IDENTITY_CHARS",
        "SERIAL_PROFILE_SCHEMA_VERSION",
        "AfeV1SerialProfile",
        "SerialProfile",
        "SerialProfileError",
        "SerialProfileIdentity",
        "SerialProfileRecord",
        "SerialProfileResetResult",
        "SerialProfileStateError",
    ]


def make_log_and_event(
    *, profile_name: str = "demo", raw: bytes = b"DEMO,1\n"
) -> tuple[BoundedRawEventLog, RawRecordEvent]:
    log = BoundedRawEventLog(max_events=8, max_total_bytes=4096)
    event = log.append_received(
        received_at=NOW,
        port_id="MEMORY:PROFILE",
        profile_name=profile_name,
        raw_bytes=raw,
    )
    return log, event


def test_identity_freezes_profile_selection_and_limits() -> None:
    identity = SerialProfileIdentity("demo", "1", 16, 128)

    assert identity.name == "demo"
    assert identity.version == "1"
    assert identity.sequence_bits == 16
    assert identity.max_record_bytes == 128
    assert identity.schema_version == SERIAL_PROFILE_SCHEMA_VERSION


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"name": 1}, "name must be a string"),
        ({"name": ""}, "name must be non-empty"),
        ({"name": " demo"}, "outer whitespace"),
        ({"name": "x" * (MAX_PROFILE_IDENTITY_CHARS + 1)}, "exceeds"),
        ({"name": "de\nmo"}, "single-line"),
        ({"version": cast(Any, None)}, "version must be a string"),
        ({"sequence_bits": True}, "sequence_bits must be an integer"),
        ({"sequence_bits": 1}, "sequence_bits must be between"),
        ({"max_record_bytes": False}, "max_record_bytes must be an integer"),
        ({"max_record_bytes": 4097}, "max_record_bytes must be between"),
        ({"schema_version": "serial-profile.v2"}, "unsupported"),
    ],
)
def test_identity_rejects_ambiguous_or_unbounded_values(
    changes: dict[str, Any], match: str
) -> None:
    values: dict[str, Any] = {
        "name": "demo",
        "version": "1",
        "sequence_bits": 16,
        "max_record_bytes": 128,
    }
    values.update(changes)

    with pytest.raises(SerialProfileStateError, match=match):
        SerialProfileIdentity(**values)


def test_profile_record_represents_accepted_and_rejected_outcomes() -> None:
    identity = SerialProfileIdentity("demo", "1", 16, 128)
    accepted_log, pending = make_log_and_event()
    parsed = accepted_log.mark_parsed(
        pending.event_id,
        parse_result="profile=demo version=1 message=Demo",
    )
    accepted = SerialProfileRecord(identity, parsed, "message")

    rejected_log, rejected_pending = make_log_and_event(raw=b"BAD\n")
    rejected_event = rejected_log.mark_rejected(
        rejected_pending.event_id,
        error_type="ProtocolError",
        error_message="bad demo record",
    )
    rejected: SerialProfileRecord[str] = SerialProfileRecord(
        identity, rejected_event, None
    )

    assert accepted.accepted
    assert accepted.message == "message"
    assert not rejected.accepted
    assert rejected.message is None


@pytest.mark.parametrize(
    ("case", "match"),
    [
        ("identity", "identity must"),
        ("event", "event must"),
        ("profile", "does not match"),
        ("measurements-list", "tuple of Measurement"),
        ("measurements-member", "tuple of Measurement"),
        ("capabilities", "DeviceCapabilities"),
        ("pending", "pending raw event"),
        ("parsed-no-message", "requires a message"),
        ("rejected-derived", "cannot contain derived data"),
    ],
)
def test_profile_record_rejects_incoherent_result_models(
    case: str, match: str
) -> None:
    identity = SerialProfileIdentity("demo", "1", 16, 128)
    log, pending = make_log_and_event()
    parsed = log.mark_parsed(
        pending.event_id,
        parse_result="profile=demo version=1 message=Demo",
    )
    rejected_log, rejected_pending = make_log_and_event(raw=b"BAD\n")
    rejected = rejected_log.mark_rejected(
        rejected_pending.event_id,
        error_type="ProtocolError",
        error_message="bad demo record",
    )

    with pytest.raises(SerialProfileStateError, match=match):
        if case == "identity":
            SerialProfileRecord(cast(Any, object()), parsed, "message")
        elif case == "event":
            SerialProfileRecord(identity, cast(Any, object()), "message")
        elif case == "profile":
            SerialProfileRecord(
                SerialProfileIdentity("other", "1", 16, 128),
                parsed,
                "message",
            )
        elif case == "measurements-list":
            SerialProfileRecord(identity, parsed, "message", cast(Any, []))
        elif case == "measurements-member":
            SerialProfileRecord(identity, parsed, "message", cast(Any, (object(),)))
        elif case == "capabilities":
            SerialProfileRecord(
                identity,
                parsed,
                "message",
                capabilities=cast(DeviceCapabilities, object()),
            )
        elif case == "pending":
            SerialProfileRecord(identity, pending, "message")
        elif case == "parsed-no-message":
            SerialProfileRecord[str](identity, parsed, None)
        else:
            SerialProfileRecord(identity, rejected, "message")


def test_reset_result_preserves_bounded_discard_diagnostics() -> None:
    reset = SerialProfileResetResult(previous_sequence=65535, discarded_records=3)

    assert reset.previous_sequence == 65535
    assert reset.discarded_records == 3
    assert SerialProfileResetResult(None) == SerialProfileResetResult(None, 0)


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"previous_sequence": True}, "previous_sequence"),
        ({"previous_sequence": cast(Any, "1")}, "previous_sequence"),
        ({"previous_sequence": -1}, "previous_sequence"),
        ({"previous_sequence": None, "discarded_records": False}, "integer"),
        ({"previous_sequence": None, "discarded_records": -1}, "between"),
    ],
)
def test_reset_result_rejects_invalid_counters(
    kwargs: dict[str, Any], match: str
) -> None:
    with pytest.raises(SerialProfileStateError, match=match):
        SerialProfileResetResult(**kwargs)
