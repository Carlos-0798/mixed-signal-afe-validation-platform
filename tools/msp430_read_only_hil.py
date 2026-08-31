"""Bounded, receive-only MSP430 Protocol v1 HIL evidence capture.

This tool never sends an application byte, flashes firmware, changes FRAM, or
infers external wiring.  It opens one explicitly selected serial port and reads
unsolicited telemetry through the product's SerialAdapter and ReadWorkflow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analog_validation.domain import EvidenceSource, Measurement, MeasurementUnit
from analog_validation.errors import ProtocolError
from analog_validation.profiles import (
    MSP430_HEALTH_V1_SERIAL_IDENTITY,
    Msp430HealthV1SerialProfile,
)
from analog_validation.protocol.envelope import decode_crc_envelope
from analog_validation.protocol.msp430_health_v1 import (
    MSP430_HEALTH_CHANNEL_BUS_VOLTAGE,
    MSP430_HEALTH_CHANNEL_CURRENT,
    MSP430_HEALTH_CHANNEL_FAN_PWM,
    MSP430_HEALTH_CHANNEL_TEMPERATURE_DS,
    MSP430_HEALTH_CHANNEL_TEMPERATURE_NTC,
    MSP430_HEALTH_INTERFACE_COMMIT,
    Msp430Telemetry,
    parse_msp430_message,
)
from analog_validation.serial_adapters import (
    SerialAdapter,
    SerialAdapterConfig,
    project_identity_read_only_capabilities,
)
from analog_validation.transport import (
    RawRecordEvent,
    RawRecordStatus,
    SerialBackend,
    SerialBackendDisconnected,
    SerialConnectionSettings,
    SerialParity,
    SerialPortInfo,
    SerialSession,
    SerialStopBits,
)
from analog_validation.workflows import (
    ChannelReadRequest,
    ReadOperation,
    ReadWorkflowRequest,
    ReadWorkflowResult,
    ReadWorkflowStatus,
    run_read_workflow,
)
from analog_validation_pyserial import PySerialBackend

HIL_EVIDENCE_SCHEMA_VERSION = "msp430-receive-only-hil.v1"
DEFAULT_FRAME_COUNT = 5
DEFAULT_READ_TIMEOUT_SECONDS = 0.25
DEFAULT_MAX_POLLS_PER_OPERATION = 20
MAX_HIL_FRAME_COUNT = 100
MAX_HIL_POLLS_PER_OPERATION = 1000

_LEGACY_HEARTBEAT = re.compile(
    rb"^HB seq=(?P<sequence>[0-9]+) uptime_ms=(?P<uptime>[0-9]+) "
    rb"s1=(?P<s1>[01]) s2=(?P<s2>[01])\r?\n$"
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class ReceiveOnlyBackendCounters:
    """Observe receive-side lifecycle without adding a write operation."""

    def __init__(self, backend: SerialBackend) -> None:
        self._backend = backend
        self.discovery_calls = 0
        self.open_calls = 0
        self.read_calls = 0
        self.empty_reads = 0
        self.received_bytes = 0
        self.disconnect_events = 0
        self.close_calls = 0

    def discover_ports(self) -> tuple[SerialPortInfo, ...]:
        self.discovery_calls += 1
        return self._backend.discover_ports()

    def open(self, settings: SerialConnectionSettings) -> None:
        self.open_calls += 1
        self._backend.open(settings)

    def read(self, max_bytes: int, timeout_seconds: float) -> bytes:
        self.read_calls += 1
        try:
            raw = self._backend.read(max_bytes, timeout_seconds)
        except SerialBackendDisconnected:
            self.disconnect_events += 1
            raise
        if not raw:
            self.empty_reads += 1
        self.received_bytes += len(raw)
        return raw

    def close(self) -> None:
        self.close_calls += 1
        self._backend.close()

    def as_dict(self) -> dict[str, int]:
        return {
            "discovery_calls": self.discovery_calls,
            "open_calls": self.open_calls,
            "read_calls": self.read_calls,
            "empty_reads": self.empty_reads,
            "received_bytes": self.received_bytes,
            "disconnect_events": self.disconnect_events,
            "reconnect_open_calls": max(self.open_calls - 1, 0),
            "close_calls": self.close_calls,
            "application_write_calls": 0,
            "application_bytes_sent": 0,
        }


def _request(frame_count: int) -> ReadWorkflowRequest:
    channels = (
        (MSP430_HEALTH_CHANNEL_TEMPERATURE_DS, MeasurementUnit.CELSIUS),
        (MSP430_HEALTH_CHANNEL_TEMPERATURE_NTC, MeasurementUnit.CELSIUS),
        (MSP430_HEALTH_CHANNEL_BUS_VOLTAGE, MeasurementUnit.MILLIVOLT),
        (MSP430_HEALTH_CHANNEL_CURRENT, MeasurementUnit.MILLIAMPERE),
        (MSP430_HEALTH_CHANNEL_FAN_PWM, MeasurementUnit.RATIO),
    )
    return ReadWorkflowRequest(
        tuple(
            ChannelReadRequest(channel, ReadOperation.ANALOG, unit, frame_count)
            for channel, unit in channels
        ),
        request_id="msp430-receive-only-hil",
    )


def _measurement_dict(measurement: Measurement) -> dict[str, object]:
    return {
        "record_id": measurement.record_id,
        "raw_record_id": measurement.raw_record_id,
        "timestamp_utc": _utc_text(measurement.timestamp),
        "channel": measurement.channel,
        "value": measurement.value,
        "unit": measurement.unit.value,
        "status": measurement.status.value,
        "source": measurement.source.value,
        "quality_flags": sorted(flag.value for flag in measurement.quality_flags),
    }


def _crc_status(raw: bytes) -> str:
    try:
        decode_crc_envelope(
            raw,
            max_record_bytes=MSP430_HEALTH_V1_SERIAL_IDENTITY.max_record_bytes,
        )
    except ProtocolError as error:
        return "INVALID" if type(error).__name__ == "CrcMismatch" else "NOT_EVALUABLE"
    return "VALID"


def _telemetry_dict(message: Msp430Telemetry) -> dict[str, Any]:
    return {
        "sequence": message.sequence,
        "uptime_ms": message.uptime_ms,
        "temperature_ds_deci_c_raw": message.temperature_ds_deci_c,
        "temperature_ntc_deci_c_raw": message.temperature_ntc_deci_c,
        "bus_mv_raw": message.bus_mv,
        "current_ma_raw": message.current_ma,
        "power_mw_raw": message.power_mw,
        "pwm_permille_raw": message.pwm_permille,
        "state": message.state.value,
        "fault_flags_hex": f"0x{message.fault_flags:04X}",
        "known_faults": [
            fault.name for fault in type(message.known_faults) if fault & message.known_faults
        ],
        "unknown_fault_bits_hex": f"0x{message.unknown_fault_bits:04X}",
        "availability": {
            "temperature_ds": message.temperature_ds_available,
            "temperature_ntc": message.temperature_ntc_available,
            "ina219": message.ina219_available,
        },
    }


def _legacy_heartbeat_dict(raw: bytes) -> dict[str, object] | None:
    """Recognize only the peer's documented temporary heartbeat syntax."""

    match = _LEGACY_HEARTBEAT.fullmatch(raw)
    if match is None:
        return None
    sequence = int(match.group("sequence"))
    uptime_ms = int(match.group("uptime"))
    if sequence > 0xFFFFFFFF or uptime_ms > 0xFFFFFFFF:
        return None
    return {
        "kind": "LEGACY_HEARTBEAT",
        "sequence": sequence,
        "uptime_ms": uptime_ms,
        "s1_pressed": match.group("s1") == b"1",
        "s2_pressed": match.group("s2") == b"1",
    }


def _raw_event_dict(event: RawRecordEvent) -> dict[str, Any]:
    raw_ascii = event.raw_bytes.decode("ascii", errors="replace")
    item: dict[str, Any] = {
        "event_id": event.event_id,
        "received_at_utc": _utc_text(event.received_at),
        "port_id": event.port_id,
        "profile_name": event.profile_name,
        "raw_ascii": raw_ascii,
        "raw_sha256": hashlib.sha256(event.raw_bytes).hexdigest(),
        "byte_count": len(event.raw_bytes),
        "crc_status": _crc_status(event.raw_bytes),
        "profile_status": event.status.value,
        "parse_result": event.parse_result,
        "error_type": event.error_type,
        "error_message": event.error_message,
        "sequence_observation": None,
        "telemetry": None,
        "out_of_profile_diagnostic": _legacy_heartbeat_dict(event.raw_bytes),
    }
    if event.sequence is not None:
        item["sequence_observation"] = {
            "sequence": event.sequence.sequence,
            "previous_sequence": event.sequence.previous_sequence,
            "disposition": event.sequence.disposition.value,
            "missing_count": event.sequence.missing_count,
        }
    if event.status is RawRecordStatus.PARSED:
        try:
            message = parse_msp430_message(event.raw_bytes)
        except ProtocolError:
            message = None
        if isinstance(message, Msp430Telemetry):
            item["telemetry"] = _telemetry_dict(message)
    return item


def _workflow_dict(result: ReadWorkflowResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "status": result.status.value,
        "evidence_source": result.evidence_source.value,
        "requested_samples": result.request.requested_sample_count,
        "measurement_count": len(result.measurements),
        "missing_requirements": list(result.missing_requirements),
        "measurements": [_measurement_dict(item) for item in result.measurements],
    }


def _error_chain(error: Exception | None) -> list[dict[str, str]]:
    chain: list[dict[str, str]] = []
    current = error
    while current is not None and len(chain) < 8:
        chain.append({"type": type(current).__name__, "message": str(current)})
        cause = current.__cause__
        current = cause if isinstance(cause, Exception) else None
    return chain


def _validate_capture_limits(
    frame_count: int,
    read_timeout_seconds: float,
    max_polls_per_operation: int,
) -> None:
    if (
        isinstance(frame_count, bool)
        or not isinstance(frame_count, int)
        or not 1 <= frame_count <= MAX_HIL_FRAME_COUNT
    ):
        raise ValueError(f"frame_count must be between 1 and {MAX_HIL_FRAME_COUNT}")
    if isinstance(read_timeout_seconds, bool) or not isinstance(
        read_timeout_seconds, (int, float)
    ):
        raise TypeError("read_timeout_seconds must be numeric")
    timeout = float(read_timeout_seconds)
    if not 0 < timeout <= 60:
        raise ValueError("read_timeout_seconds must be greater than zero up to 60")
    if (
        isinstance(max_polls_per_operation, bool)
        or not isinstance(max_polls_per_operation, int)
        or not 1 <= max_polls_per_operation <= MAX_HIL_POLLS_PER_OPERATION
    ):
        raise ValueError(
            "max_polls_per_operation must be between 1 and "
            f"{MAX_HIL_POLLS_PER_OPERATION}"
        )


def capture_msp430_receive_only_hil(
    backend: SerialBackend,
    *,
    port_id: str,
    frame_count: int = DEFAULT_FRAME_COUNT,
    read_timeout_seconds: float = DEFAULT_READ_TIMEOUT_SECONDS,
    max_polls_per_operation: int = DEFAULT_MAX_POLLS_PER_OPERATION,
) -> dict[str, Any]:
    """Run one finite capture and return evidence even when acquisition fails."""

    _validate_capture_limits(
        frame_count,
        read_timeout_seconds,
        max_polls_per_operation,
    )
    started_at = _utc_now()
    counted = ReceiveOnlyBackendCounters(backend)
    settings = SerialConnectionSettings(
        port_id=port_id,
        profile_name=MSP430_HEALTH_V1_SERIAL_IDENTITY.name,
        baud_rate=115_200,
        data_bits=8,
        parity=SerialParity.NONE,
        stop_bits=SerialStopBits.ONE,
        read_chunk_bytes=512,
        max_record_bytes=MSP430_HEALTH_V1_SERIAL_IDENTITY.max_record_bytes,
        read_timeout_seconds=read_timeout_seconds,
        max_reconnect_attempts=0,
    )
    session = SerialSession(counted, settings)
    profile = Msp430HealthV1SerialProfile(
        evidence_source=EvidenceSource.BENCH_CONTROLLER
    )
    adapter = SerialAdapter(
        session,
        profile,
        SerialAdapterConfig(
            profile_name=profile.identity.name,
            profile_version=profile.identity.version,
            max_polls_per_operation=max_polls_per_operation,
            max_buffered_measurements=max(frame_count * 5, 32),
        ),
        capability_projector=project_identity_read_only_capabilities,
    )

    inventory: tuple[SerialPortInfo, ...] = ()
    workflow: ReadWorkflowResult | None = None
    capture_error: Exception | None = None
    try:
        inventory = counted.discover_ports()
        if port_id not in {port.port_id for port in inventory}:
            raise RuntimeError("selected port is not present in the current inventory")
        workflow = run_read_workflow(adapter, _request(frame_count))
    except Exception as error:  # noqa: BLE001 - evidence must retain expected failures
        capture_error = error

    raw_snapshot = adapter.raw_events
    raw_events = [_raw_event_dict(event) for event in raw_snapshot.events]
    parsed_telemetry = [item for item in raw_events if item["telemetry"] is not None]
    rejected_count = sum(
        item["profile_status"] == RawRecordStatus.REJECTED.value for item in raw_events
    )
    legacy_heartbeats = [
        item for item in raw_events if item["out_of_profile_diagnostic"] is not None
    ]
    unexpected_rejected_count = sum(
        item["profile_status"] == RawRecordStatus.REJECTED.value
        and item["out_of_profile_diagnostic"] is None
        for item in raw_events
    )
    telemetry_uptime_by_sequence = {
        item["telemetry"]["sequence"]: item["telemetry"]["uptime_ms"]
        for item in parsed_telemetry
    }
    heartbeat_alignment_anomalies = sum(
        telemetry_uptime_by_sequence.get(item["out_of_profile_diagnostic"]["sequence"])
        != item["out_of_profile_diagnostic"]["uptime_ms"]
        for item in legacy_heartbeats
    )
    sequence_anomalies = sum(
        observation is not None
        and observation["disposition"] not in {"FIRST", "IN_ORDER"}
        for observation in (
            item["sequence_observation"] for item in raw_events
        )
    )
    protocol_compatible = (
        capture_error is None
        and workflow is not None
        and workflow.status is ReadWorkflowStatus.COMPLETED
        and len(parsed_telemetry) >= frame_count
        and unexpected_rejected_count == 0
        and heartbeat_alignment_anomalies == 0
        and sequence_anomalies == 0
        and counted.disconnect_events == 0
    )
    if protocol_compatible:
        outcome = "PROTOCOL_COMPATIBLE_RECEIVE_ONLY"
    elif workflow is not None and workflow.status is ReadWorkflowStatus.COMPLETED:
        outcome = "ACQUIRED_WITH_ANOMALIES"
    else:
        outcome = "CAPTURE_FAILED"

    ended_at = _utc_now()
    return {
        "schema_version": HIL_EVIDENCE_SCHEMA_VERSION,
        "capture_outcome": outcome,
        "started_at_utc": _utc_text(started_at),
        "ended_at_utc": _utc_text(ended_at),
        "safety_boundary": {
            "receive_only": True,
            "application_commands_sent": False,
            "firmware_flashing_performed": False,
            "fram_modified": False,
            "external_wiring_required": False,
            "dtr_rts_requested_inactive_before_open": True,
            "driver_control_line_glitch_excluded": False,
        },
        "claim_boundary": {
            "physical_uart_bytes_observed": bool(raw_events),
            "exact_firmware_identity": "UNCONFIRMED_PASSIVE_ONLY",
            "firmware_version_field_in_protocol": False,
            "afe_hardware_validated": False,
            "external_sensor_wiring_validated": False,
            "fan_or_external_5v_validated": False,
        },
        "expected_interface": {
            "peer_commit": MSP430_HEALTH_INTERFACE_COMMIT,
            "profile_name": MSP430_HEALTH_V1_SERIAL_IDENTITY.name,
            "profile_version": MSP430_HEALTH_V1_SERIAL_IDENTITY.version,
        },
        "serial_configuration": {
            "selected_port": port_id,
            "baud_rate": settings.baud_rate,
            "data_bits": settings.data_bits,
            "parity": settings.parity.value,
            "stop_bits": settings.stop_bits.value,
            "read_chunk_bytes": settings.read_chunk_bytes,
            "max_record_bytes": settings.max_record_bytes,
            "read_timeout_seconds": settings.read_timeout_seconds,
            "max_reconnect_attempts": settings.max_reconnect_attempts,
            "max_polls_per_operation": max_polls_per_operation,
            "requested_telemetry_frames": frame_count,
        },
        "port_inventory": [
            {"port_id": port.port_id, "description": port.description}
            for port in inventory
        ],
        "backend_counters": counted.as_dict(),
        "raw_event_summary": {
            "retained_events": len(raw_events),
            "retained_bytes": raw_snapshot.retained_bytes,
            "dropped_events": raw_snapshot.dropped_events,
            "dropped_bytes": raw_snapshot.dropped_bytes,
            "parsed_telemetry_records": len(parsed_telemetry),
            "rejected_records": rejected_count,
            "known_legacy_heartbeat_records": len(legacy_heartbeats),
            "unexpected_rejected_records": unexpected_rejected_count,
            "heartbeat_alignment_anomalies": heartbeat_alignment_anomalies,
            "sequence_anomalies": sequence_anomalies,
        },
        "raw_events": raw_events,
        "workflow": _workflow_dict(workflow),
        "errors": _error_chain(capture_error),
        "limitations": [
            "Passive Protocol v1 telemetry contains no firmware-version field.",
            "Protocol compatibility does not prove the exact flashed image.",
            "Documented legacy HB lines remain out-of-profile parser rejections and are assessed separately.",
            "Controller telemetry does not validate AFE gain, filtering, hysteresis, or ADC accuracy.",
            "Reported sensor values do not prove external sensor wiring without separate bench evidence.",
            "No disconnect was intentionally induced; zero reconnects means not exercised, not proven recovery.",
        ],
    }


def default_evidence_path(started_at: datetime | None = None) -> Path:
    timestamp = (started_at or _utc_now()).strftime("%Y%m%dT%H%M%SZ")
    repository_root = Path(__file__).resolve().parents[1]
    return repository_root / "work" / "evidence" / f"msp430-read-only-hil-{timestamp}.json"


def write_evidence(path: Path, evidence: Mapping[str, object]) -> None:
    """Write a new evidence file and refuse to replace an existing capture."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(evidence, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Receive unsolicited MSP430 telemetry without sending commands."
    )
    parser.add_argument("--port", required=True, help="Explicit serial port, e.g. COM4")
    parser.add_argument("--frames", type=int, default=DEFAULT_FRAME_COUNT)
    parser.add_argument(
        "--read-timeout-seconds",
        type=float,
        default=DEFAULT_READ_TIMEOUT_SECONDS,
    )
    parser.add_argument(
        "--max-polls-per-operation",
        type=int,
        default=DEFAULT_MAX_POLLS_PER_OPERATION,
    )
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_argument_parser().parse_args(argv)
    output = arguments.output or default_evidence_path()
    evidence = capture_msp430_receive_only_hil(
        PySerialBackend(),
        port_id=arguments.port,
        frame_count=arguments.frames,
        read_timeout_seconds=arguments.read_timeout_seconds,
        max_polls_per_operation=arguments.max_polls_per_operation,
    )
    write_evidence(output, evidence)
    print(f"evidence={output}")
    print(f"capture_outcome={evidence['capture_outcome']}")
    return 0 if evidence["capture_outcome"] == "PROTOCOL_COMPATIBLE_RECEIVE_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_FRAME_COUNT",
    "DEFAULT_MAX_POLLS_PER_OPERATION",
    "DEFAULT_READ_TIMEOUT_SECONDS",
    "HIL_EVIDENCE_SCHEMA_VERSION",
    "ReceiveOnlyBackendCounters",
    "build_argument_parser",
    "capture_msp430_receive_only_hil",
    "default_evidence_path",
    "main",
    "write_evidence",
]
