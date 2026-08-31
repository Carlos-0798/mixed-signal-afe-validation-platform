"""HIL tool contract tests using only the deterministic memory backend."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from analog_validation.protocol.msp430_health_v1 import (
    Msp430DeviceState,
    Msp430Telemetry,
    encode_msp430_message,
)
from analog_validation.transport import SerialPortInfo
from tests.support import MemorySerialBackend
from tools.msp430_read_only_hil import (
    HIL_EVIDENCE_SCHEMA_VERSION,
    capture_msp430_receive_only_hil,
    default_evidence_path,
    write_evidence,
)


def encoded(sequence: int, uptime_ms: int) -> bytes:
    return encode_msp430_message(
        Msp430Telemetry(
            sequence,
            uptime_ms,
            -32768,
            -32768,
            0,
            0,
            0,
            0,
            Msp430DeviceState.FAULT,
            0x0015,
        )
    ).encode("ascii")


def heartbeat(sequence: int, uptime_ms: int) -> bytes:
    return f"HB seq={sequence} uptime_ms={uptime_ms} s1=0 s2=0\r\n".encode("ascii")


def test_capture_runs_full_receive_only_adapter_workflow() -> None:
    stream = (
        heartbeat(40, 1000)
        + encoded(40, 1000)
        + heartbeat(41, 2000)
        + encoded(41, 2000)
    )
    backend = MemorySerialBackend.scripted(
        ports=(SerialPortInfo("COM4", "MSP Application UART1"),),
        reads=(stream[:35], stream[35:]),
    )

    evidence = capture_msp430_receive_only_hil(
        backend,
        port_id="COM4",
        frame_count=2,
        max_polls_per_operation=4,
    )

    assert evidence["schema_version"] == HIL_EVIDENCE_SCHEMA_VERSION
    assert evidence["capture_outcome"] == "PROTOCOL_COMPATIBLE_RECEIVE_ONLY"
    assert evidence["claim_boundary"] == {
        "physical_uart_bytes_observed": True,
        "exact_firmware_identity": "UNCONFIRMED_PASSIVE_ONLY",
        "firmware_version_field_in_protocol": False,
        "afe_hardware_validated": False,
        "external_sensor_wiring_validated": False,
        "fan_or_external_5v_validated": False,
    }
    counters = evidence["backend_counters"]
    assert counters["application_write_calls"] == 0
    assert counters["application_bytes_sent"] == 0
    assert counters["open_calls"] == counters["close_calls"] == 1
    assert counters["disconnect_events"] == 0
    assert evidence["raw_event_summary"] == {
        "retained_events": 4,
        "retained_bytes": len(stream),
        "dropped_events": 0,
        "dropped_bytes": 0,
        "parsed_telemetry_records": 2,
        "rejected_records": 2,
        "known_legacy_heartbeat_records": 2,
        "unexpected_rejected_records": 0,
        "heartbeat_alignment_anomalies": 0,
        "sequence_anomalies": 0,
    }
    assert [item["crc_status"] for item in evidence["raw_events"]] == [
        "NOT_EVALUABLE",
        "VALID",
        "NOT_EVALUABLE",
        "VALID",
    ]
    assert evidence["raw_events"][0]["out_of_profile_diagnostic"] == {
        "kind": "LEGACY_HEARTBEAT",
        "sequence": 40,
        "uptime_ms": 1000,
        "s1_pressed": False,
        "s2_pressed": False,
    }
    assert evidence["raw_events"][3]["sequence_observation"]["disposition"] == "IN_ORDER"
    assert evidence["workflow"]["status"] == "COMPLETED"
    assert evidence["workflow"]["evidence_source"] == "BENCH_CONTROLLER"
    assert evidence["workflow"]["measurement_count"] == 10
    assert all(
        measurement["source"] == "BENCH_CONTROLLER"
        for measurement in evidence["workflow"]["measurements"]
    )
    assert not hasattr(backend, "write")


def test_capture_failure_is_bounded_and_retained_as_evidence() -> None:
    backend = MemorySerialBackend.scripted(
        ports=(SerialPortInfo("COM4", "MSP Application UART1"),),
        reads=(b"not-a-frame\n",),
    )

    evidence = capture_msp430_receive_only_hil(
        backend,
        port_id="COM4",
        frame_count=1,
        max_polls_per_operation=2,
    )

    assert evidence["capture_outcome"] == "CAPTURE_FAILED"
    assert evidence["raw_event_summary"]["rejected_records"] == 1
    assert evidence["raw_events"][0]["crc_status"] == "NOT_EVALUABLE"
    assert evidence["workflow"] is None
    assert evidence["errors"][0]["type"] == "AdapterDataError"
    assert evidence["backend_counters"]["open_calls"] == 1
    assert evidence["backend_counters"]["close_calls"] == 1


@pytest.mark.parametrize(
    ("diagnostic", "expected_unexpected", "expected_alignment"),
    [
        (b"HB seq=40 uptime_ms=1000 s1=2 s2=0\r\n", 1, 0),
        (heartbeat(99, 1000), 0, 1),
    ],
)
def test_only_well_formed_heartbeat_aligned_to_telemetry_is_expected(
    diagnostic: bytes,
    expected_unexpected: int,
    expected_alignment: int,
) -> None:
    backend = MemorySerialBackend.scripted(
        ports=(SerialPortInfo("COM4", "MSP Application UART1"),),
        reads=(diagnostic + encoded(40, 1000),),
    )

    evidence = capture_msp430_receive_only_hil(
        backend,
        port_id="COM4",
        frame_count=1,
        max_polls_per_operation=2,
    )

    assert evidence["capture_outcome"] == "ACQUIRED_WITH_ANOMALIES"
    assert (
        evidence["raw_event_summary"]["unexpected_rejected_records"]
        == expected_unexpected
    )
    assert (
        evidence["raw_event_summary"]["heartbeat_alignment_anomalies"]
        == expected_alignment
    )


def test_missing_selected_port_never_opens_backend() -> None:
    backend = MemorySerialBackend(
        ports=(SerialPortInfo("COM5", "MSP Debug Interface"),)
    )

    evidence = capture_msp430_receive_only_hil(
        backend,
        port_id="COM4",
        frame_count=1,
    )

    assert evidence["capture_outcome"] == "CAPTURE_FAILED"
    assert evidence["backend_counters"]["open_calls"] == 0
    assert evidence["backend_counters"]["application_bytes_sent"] == 0
    assert evidence["errors"][0]["type"] == "RuntimeError"


@pytest.mark.parametrize(
    ("frame_count", "timeout", "polls"),
    [(0, 0.25, 20), (1, 0.0, 20), (1, 0.25, 0)],
)
def test_capture_limits_reject_unbounded_work_before_discovery(
    frame_count: int,
    timeout: float,
    polls: int,
) -> None:
    backend = MemorySerialBackend()

    with pytest.raises(ValueError):
        capture_msp430_receive_only_hil(
            backend,
            port_id="COM4",
            frame_count=frame_count,
            read_timeout_seconds=timeout,
            max_polls_per_operation=polls,
        )

    assert backend.discover_calls == 0


def test_evidence_writer_refuses_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "capture.json"
    evidence = {"schema_version": HIL_EVIDENCE_SCHEMA_VERSION}

    write_evidence(output, evidence)

    assert json.loads(output.read_text(encoding="utf-8")) == evidence
    with pytest.raises(FileExistsError):
        write_evidence(output, evidence)


def test_default_path_is_utc_stamped_under_ignored_work_tree() -> None:
    path = default_evidence_path(datetime(2026, 8, 30, 12, 34, 56, tzinfo=timezone.utc))

    assert path.name == "msp430-read-only-hil-20260830T123456Z.json"
    assert path.parent.name == "evidence"
    assert path.parent.parent.name == "work"
