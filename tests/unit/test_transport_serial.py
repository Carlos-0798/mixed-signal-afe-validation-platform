"""Tests for driver-neutral serial discovery, lifecycle, and reconnect behavior."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest

from analog_validation.transport import (
    MAX_BAUD_RATE,
    MAX_RAW_EVENT_BYTES,
    MAX_READ_CHUNK_BYTES,
    MAX_READ_TIMEOUT_SECONDS,
    MAX_RECONNECT_ATTEMPTS,
    MAX_SERIAL_TEXT_CHARS,
    BoundedRawEventLog,
    RawRecordEvent,
    RawRecordStatus,
    SerialBackendDisconnected,
    SerialBackendTimeout,
    SerialCloseError,
    SerialConnectionSettings,
    SerialDiscoveryError,
    SerialOpenError,
    SerialParity,
    SerialPollStatus,
    SerialPortInfo,
    SerialReadError,
    SerialReconnectError,
    SerialSession,
    SerialSessionState,
    SerialStateError,
    SerialStopBits,
    StreamIssueKind,
)
from tests.support import MemorySerialBackend

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def settings(**overrides: object) -> SerialConnectionSettings:
    values: dict[str, object] = {
        "port_id": "MEMORY:AFE",
        "profile_name": "AFE_V1",
    }
    values.update(overrides)
    return SerialConnectionSettings(**cast(Any, values))


def open_session(
    backend: MemorySerialBackend,
    *,
    connection: SerialConnectionSettings | None = None,
    event_log: BoundedRawEventLog | None = None,
    clock: Any = None,
) -> SerialSession:
    kwargs: dict[str, object] = {}
    if event_log is not None:
        kwargs["event_log"] = event_log
    if clock is not None:
        kwargs["clock"] = clock
    session = SerialSession(backend, connection or settings(), **cast(Any, kwargs))
    session.open()
    return session


def test_connection_settings_defaults_are_explicit_and_immutable() -> None:
    connection = settings()

    assert connection.port_id == "MEMORY:AFE"
    assert connection.profile_name == "AFE_V1"
    assert connection.baud_rate == 115_200
    assert connection.data_bits == 8
    assert connection.parity is SerialParity.NONE
    assert connection.stop_bits is SerialStopBits.ONE
    assert connection.read_chunk_bytes == 512
    assert connection.max_record_bytes == 128
    assert connection.read_timeout_seconds == 0.25
    assert connection.max_reconnect_attempts == 2
    with pytest.raises(FrozenInstanceError):
        connection.port_id = "OTHER"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"port_id": 3}, "port_id"),
        ({"port_id": ""}, "port_id"),
        ({"profile_name": " AFE"}, "profile_name"),
        ({"profile_name": "A\nFE"}, "profile_name"),
        ({"profile_name": "P" * (MAX_SERIAL_TEXT_CHARS + 1)}, "profile_name"),
        ({"baud_rate": True}, "baud_rate"),
        ({"baud_rate": 0}, "baud_rate"),
        ({"baud_rate": MAX_BAUD_RATE + 1}, "baud_rate"),
        ({"data_bits": 4}, "data_bits"),
        ({"data_bits": 9}, "data_bits"),
        ({"parity": "NONE"}, "parity"),
        ({"stop_bits": 1}, "stop_bits"),
        ({"read_chunk_bytes": 0}, "read_chunk_bytes"),
        ({"read_chunk_bytes": MAX_READ_CHUNK_BYTES + 1}, "read_chunk_bytes"),
        ({"max_record_bytes": 0}, "max_record_bytes"),
        ({"max_record_bytes": MAX_RAW_EVENT_BYTES + 1}, "max_record_bytes"),
        ({"read_timeout_seconds": True}, "read_timeout_seconds"),
        ({"read_timeout_seconds": 0.0}, "read_timeout_seconds"),
        ({"read_timeout_seconds": math.inf}, "read_timeout_seconds"),
        (
            {"read_timeout_seconds": MAX_READ_TIMEOUT_SECONDS + 0.1},
            "read_timeout_seconds",
        ),
        ({"max_reconnect_attempts": -1}, "max_reconnect_attempts"),
        ({"max_reconnect_attempts": MAX_RECONNECT_ATTEMPTS + 1}, "reconnect"),
    ],
)
def test_connection_settings_validation_is_strict(
    overrides: dict[str, object], match: str
) -> None:
    with pytest.raises(SerialStateError, match=match):
        settings(**overrides)


def test_all_supported_line_settings_are_backend_neutral() -> None:
    for parity in SerialParity:
        for stop_bits in SerialStopBits:
            connection = settings(parity=parity, stop_bits=stop_bits, data_bits=5)
            assert connection.parity is parity
            assert connection.stop_bits is stop_bits


def test_port_info_validates_identity_and_optional_description() -> None:
    port = SerialPortInfo("MEMORY:1", "Deterministic test port")

    assert port.port_id == "MEMORY:1"
    assert port.description == "Deterministic test port"
    assert SerialPortInfo("MEMORY:2").description is None
    with pytest.raises(SerialStateError, match="description"):
        SerialPortInfo("MEMORY:1", "bad\ndescription")


def test_session_constructor_rejects_incompatible_contracts() -> None:
    backend = MemorySerialBackend()

    with pytest.raises(SerialStateError, match="settings"):
        SerialSession(backend, cast(Any, "settings"))
    with pytest.raises(SerialStateError, match="event log"):
        SerialSession(
            backend,
            settings(max_record_bytes=8),
            event_log=BoundedRawEventLog(max_events=2, max_total_bytes=7),
        )
    with pytest.raises(SerialStateError, match="clock"):
        SerialSession(backend, settings(), clock=cast(Any, 7))


def test_discovery_returns_valid_unique_ports_without_opening() -> None:
    ports = (SerialPortInfo("MEMORY:1"), SerialPortInfo("MEMORY:2", "second"))
    backend = MemorySerialBackend(ports=ports)
    session = SerialSession(backend, settings())

    assert session.discover_ports() == ports
    assert backend.discover_calls == 1
    assert backend.open_calls == []
    assert session.state is SerialSessionState.CLOSED


@pytest.mark.parametrize(
    ("action", "match"),
    [
        (RuntimeError("driver failed"), "discovery failed"),
        ([SerialPortInfo("MEMORY:1")], "invalid port inventory"),
        (("MEMORY:1",), "invalid port inventory"),
        (
            (SerialPortInfo("MEMORY:1"), SerialPortInfo("MEMORY:1")),
            "duplicate port IDs",
        ),
    ],
)
def test_discovery_normalizes_backend_failures_and_contract_violations(
    action: object, match: str
) -> None:
    backend = MemorySerialBackend.scripted(discover=(action,))

    with pytest.raises(SerialDiscoveryError, match=match):
        SerialSession(backend, settings()).discover_ports()


def test_discovery_is_not_allowed_while_open() -> None:
    backend = MemorySerialBackend()
    session = open_session(backend)

    with pytest.raises(SerialStateError, match="discover"):
        session.discover_ports()


def test_open_passes_exact_settings_and_prevents_double_open() -> None:
    backend = MemorySerialBackend()
    connection = settings(baud_rate=9600)
    session = SerialSession(backend, connection)

    assert session.settings is connection
    assert session.state is SerialSessionState.CLOSED
    session.open()

    assert session.state is SerialSessionState.OPEN
    assert backend.is_open is True
    assert backend.open_calls == [connection]
    assert session.pending_bytes == 0
    assert session.event_log.snapshot().events == ()
    with pytest.raises(SerialStateError, match="open"):
        session.open()


def test_open_failure_attempts_cleanup_and_remains_closed() -> None:
    backend = MemorySerialBackend.scripted(
        opens=(RuntimeError("busy"),),
        closes=(RuntimeError("cleanup failed"),),
    )
    session = SerialSession(backend, settings())

    with pytest.raises(SerialOpenError, match="open failed"):
        session.open()

    assert session.state is SerialSessionState.CLOSED
    assert backend.close_calls == 1
    assert backend.is_open is False


def test_poll_requires_an_open_session() -> None:
    session = SerialSession(MemorySerialBackend(), settings())

    with pytest.raises(SerialStateError, match="poll"):
        session.poll()


@pytest.mark.parametrize("action", [b"", SerialBackendTimeout()])
def test_timeout_is_normal_and_preserves_partial_record(action: object) -> None:
    backend = MemorySerialBackend.scripted(reads=(b"part", action))
    session = open_session(backend)

    first = session.poll()
    timeout = session.poll()

    assert first.status is SerialPollStatus.DATA
    assert first.records == ()
    assert timeout.status is SerialPollStatus.TIMEOUT
    assert timeout.records == ()
    assert session.pending_bytes == 4
    assert session.state is SerialSessionState.OPEN
    assert backend.read_calls == [(512, 0.25), (512, 0.25)]


def test_partial_and_multiple_records_preserve_bytes_and_utc_provenance() -> None:
    eastern = timezone(timedelta(hours=-4))
    clock = lambda: datetime(2026, 8, 30, 8, 0, tzinfo=eastern)
    backend = MemorySerialBackend.scripted(
        reads=(bytearray(b"A\nB\npar"), memoryview(b"tial\n"))
    )
    session = open_session(backend, clock=clock)

    first = session.poll()
    second = session.poll()

    assert first.status is SerialPollStatus.DATA
    assert tuple(event.raw_bytes for event in first.records) == (b"A\n", b"B\n")
    assert tuple(event.raw_bytes for event in second.records) == (b"partial\n",)
    assert all(event.received_at == NOW for event in (*first.records, *second.records))
    assert all(
        event.status is RawRecordStatus.PENDING_PROFILE
        for event in (*first.records, *second.records)
    )
    assert tuple(
        event.event_id for event in session.event_log.snapshot().events
    ) == (1, 2, 3)


def test_overlong_record_is_not_logged_and_stream_recovers() -> None:
    backend = MemorySerialBackend.scripted(reads=(b"abcde\nok\n",))
    session = open_session(
        backend,
        connection=settings(max_record_bytes=4, read_chunk_bytes=16),
    )

    result = session.poll()

    assert tuple(event.raw_bytes for event in result.records) == (b"ok\n",)
    assert result.issues[0].kind is StreamIssueKind.OVERLONG_RECORD
    assert result.issues[0].discarded_bytes == 6
    assert session.event_log.snapshot().retained_bytes == 3


@pytest.mark.parametrize(
    ("action", "match"),
    [
        (RuntimeError("driver read"), "bounded read failed"),
        ("not bytes", "bytes-like"),
        (b"12345", "bounded read size"),
    ],
)
def test_read_and_backend_contract_failures_close_deterministically(
    action: object, match: str
) -> None:
    backend = MemorySerialBackend.scripted(reads=(action,))
    session = open_session(
        backend,
        connection=settings(read_chunk_bytes=4, max_record_bytes=4),
    )

    with pytest.raises(SerialReadError, match=match):
        session.poll()

    assert session.state is SerialSessionState.CLOSED
    assert backend.is_open is False
    assert backend.close_calls == 1


@pytest.mark.parametrize(
    ("clock", "match"),
    [
        (lambda: "now", "datetime"),
        (lambda: datetime(2026, 8, 30, 12, 0), "timezone-aware"),  # noqa: DTZ001
    ],
)
def test_invalid_receive_clock_aborts_session(clock: Any, match: str) -> None:
    backend = MemorySerialBackend.scripted(reads=(b"A\n",))
    session = open_session(backend, clock=clock)

    with pytest.raises(SerialReadError, match=match):
        session.poll()

    assert session.state is SerialSessionState.CLOSED


def test_unexpected_receive_processing_failure_is_normalized_and_closes() -> None:
    class FailingEventLog(BoundedRawEventLog):
        def append_received(
            self,
            *,
            received_at: datetime,
            port_id: str,
            profile_name: str,
            raw_bytes: bytes | bytearray | memoryview,
        ) -> RawRecordEvent:
            raise RuntimeError("injected event sink failure")

    backend = MemorySerialBackend.scripted(reads=(b"A\n",))
    session = open_session(backend, event_log=FailingEventLog())

    with pytest.raises(SerialReadError, match="receive processing failed"):
        session.poll()

    assert session.state is SerialSessionState.CLOSED
    assert backend.is_open is False


def test_disconnect_discards_partial_bytes_then_reconnects_without_reading() -> None:
    backend = MemorySerialBackend.scripted(
        opens=(None, None),
        reads=(b"old", SerialBackendDisconnected(), b"new\n"),
    )
    session = open_session(backend)
    session.poll()

    reconnect = session.poll()

    assert reconnect.status is SerialPollStatus.RECONNECTED
    assert reconnect.records == ()
    assert reconnect.reset is not None
    assert reconnect.reset.discarded_bytes == 3
    assert reconnect.reconnect_attempts == 1
    assert session.pending_bytes == 0
    assert session.state is SerialSessionState.OPEN
    assert len(backend.open_calls) == 2
    assert session.poll().records[0].raw_bytes == b"new\n"


def test_reconnect_uses_finite_attempts_and_can_recover_after_one_failure() -> None:
    backend = MemorySerialBackend.scripted(
        opens=(None, RuntimeError("first reconnect"), None),
        reads=(SerialBackendDisconnected(),),
    )
    session = open_session(
        backend,
        connection=settings(max_reconnect_attempts=2),
    )

    result = session.poll()

    assert result.status is SerialPollStatus.RECONNECTED
    assert result.reconnect_attempts == 2
    assert session.state is SerialSessionState.OPEN
    assert len(backend.open_calls) == 3
    assert backend.close_calls == 2


@pytest.mark.parametrize("attempts", [0, 2])
def test_reconnect_budget_exhaustion_leaves_session_closed(attempts: int) -> None:
    reconnect_failures = tuple(RuntimeError("unavailable") for _ in range(attempts))
    backend = MemorySerialBackend.scripted(
        opens=(None, *reconnect_failures),
        reads=(SerialBackendDisconnected(),),
        closes=(RuntimeError("disconnect cleanup"),),
    )
    session = open_session(
        backend,
        connection=settings(max_reconnect_attempts=attempts),
    )

    with pytest.raises(SerialReconnectError, match=f"after {attempts} attempts"):
        session.poll()

    assert session.state is SerialSessionState.CLOSED
    assert backend.is_open is False
    assert len(backend.open_calls) == attempts + 1


def test_close_resets_partial_state_is_idempotent_and_reports_close_failure() -> None:
    backend = MemorySerialBackend.scripted(reads=(b"part",))
    session = open_session(backend)
    session.poll()

    reset = session.close()
    second = session.close()

    assert reset.discarded_bytes == 4
    assert second.discarded_bytes == 0
    assert session.state is SerialSessionState.CLOSED
    assert backend.close_calls == 1

    failing = MemorySerialBackend.scripted(closes=(RuntimeError("close failed"),))
    failing_session = open_session(failing)
    with pytest.raises(SerialCloseError, match="close failed"):
        failing_session.close()
    assert failing_session.state is SerialSessionState.CLOSED
