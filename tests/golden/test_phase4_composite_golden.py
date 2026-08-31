"""Freeze representative Phase 4 external-backend product-chain meaning."""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from analog_validation.domain import (
    DeviceCommand,
    EvidenceSource,
    Measurement,
    MeasurementUnit,
)
from analog_validation.profiles import AfeV1SerialProfile, Msp430HealthV1SerialProfile
from analog_validation.protocol import (
    AFE_PROFILE_NAME,
    AFE_PROFILE_VERSION,
    AfeCapabilityChannel,
    AfeCapabilityDevice,
    AfeCapabilityEnd,
    AfeMessage,
    AfeTelemetry,
    CapabilityChannelKind,
    encode_afe_message,
)
from analog_validation.protocol.msp430_health_v1 import (
    MSP430_HEALTH_PROFILE_NAME,
    MSP430_HEALTH_PROFILE_VERSION,
    Msp430DeviceState,
    Msp430Fault,
    Msp430Message,
    Msp430Telemetry,
    encode_msp430_message,
)
from analog_validation.serial_adapters import (
    SerialAdapter,
    SerialAdapterConfig,
    project_afe_v1_read_only_capabilities,
    project_identity_read_only_capabilities,
)
from analog_validation.transport import (
    RawRecordEvent,
    SerialBackend,
    SerialBackendTimeout,
    SerialConnectionSettings,
    SerialPortInfo,
    SerialSession,
)
from analog_validation.workflows import (
    ChannelReadRequest,
    ReadOperation,
    ReadWorkflowRequest,
    ReadWorkflowResult,
    run_read_workflow,
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = ROOT / "test-data" / "golden" / "phase4_composite_v1.json"
NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


class ExternalSerialBackend:
    """A structural backend using only the public Phase 4 port contract."""

    def __init__(self, reads: tuple[bytes, ...]) -> None:
        self._reads = deque(reads)
        self.is_open = False
        self.open_calls: list[SerialConnectionSettings] = []
        self.read_calls: list[tuple[int, float]] = []
        self.close_calls = 0

    def discover_ports(self) -> tuple[SerialPortInfo, ...]:
        return (SerialPortInfo("EXTERNAL:PORT", "external fixture"),)

    def open(self, settings: SerialConnectionSettings) -> None:
        self.open_calls.append(settings)
        self.is_open = True

    def read(self, max_bytes: int, timeout_seconds: float) -> bytes:
        self.read_calls.append((max_bytes, timeout_seconds))
        if not self._reads:
            raise SerialBackendTimeout()
        return self._reads.popleft()

    def close(self) -> None:
        self.close_calls += 1
        self.is_open = False


def _damaged_crc(raw: bytes) -> bytes:
    damaged = bytearray(raw)
    damaged[-3] = ord("0") if damaged[-3] != ord("0") else ord("1")
    return bytes(damaged)


def _afe_record(message: AfeMessage) -> bytes:
    return encode_afe_message(message).encode("ascii")


def _msp430_record(message: Msp430Message) -> bytes:
    return encode_msp430_message(message).encode("ascii")


def _measurement(value: Measurement) -> dict[str, object]:
    return {
        "record_id": value.record_id,
        "raw_record_id": value.raw_record_id,
        "timestamp_utc": value.timestamp.isoformat().replace("+00:00", "Z"),
        "channel": value.channel,
        "value": value.value,
        "unit": value.unit.value,
        "status": value.status.value,
        "source": value.source.value,
        "quality_flags": sorted(flag.value for flag in value.quality_flags),
    }


def _raw_event(value: RawRecordEvent) -> dict[str, object]:
    sequence: dict[str, object] | None = None
    if value.sequence is not None:
        sequence = {
            "value": value.sequence.sequence,
            "disposition": value.sequence.disposition.value,
            "missing_count": value.sequence.missing_count,
        }
    return {
        "event_id": value.event_id,
        "raw_ascii": value.raw_bytes.decode("ascii"),
        "status": value.status.value,
        "error_type": value.error_type,
        "sequence": sequence,
    }


def _normalize(
    result: ReadWorkflowResult,
    adapter: SerialAdapter,
    backend: ExternalSerialBackend,
) -> dict[str, Any]:
    capabilities = result.capabilities
    return {
        "workflow_status": result.status.value,
        "evidence_source": result.evidence_source.value,
        "capabilities": {
            "device_id": capabilities.device_id,
            "profile_name": capabilities.profile_name,
            "profile_version": capabilities.profile_version,
            "adc_channels": list(capabilities.adc_channels),
            "digital_input_channels": list(capabilities.digital_input_channels),
            "supported_commands": sorted(
                command.value for command in capabilities.supported_commands
            ),
            "supports_safe_shutdown": capabilities.supports_safe_shutdown,
        },
        "measurements": [_measurement(value) for value in result.measurements],
        "raw_events": [_raw_event(value) for value in adapter.raw_events.events],
        "backend": {
            "open_calls": len(backend.open_calls),
            "read_calls": len(backend.read_calls),
            "close_calls": backend.close_calls,
            "is_open": backend.is_open,
            "has_write": hasattr(backend, "write"),
        },
    }


def _run_afe() -> dict[str, Any]:
    messages: tuple[AfeMessage, ...] = (
        AfeCapabilityDevice(
            9,
            "phase4-golden-afe",
            frozenset(
                {DeviceCommand.READ_MEASUREMENT, DeviceCommand.READ_DIGITAL_STATE}
            ),
        ),
        AfeCapabilityChannel(
            9,
            CapabilityChannelKind.ADC,
            0,
            0,
            3300,
            MeasurementUnit.MILLIVOLT,
        ),
        AfeCapabilityChannel(9, CapabilityChannelKind.DIGITAL_INPUT, 0),
        AfeCapabilityEnd(9, 2),
        AfeTelemetry(65535, 1000, 0, 400, 800, 2000, 0, 0),
        AfeTelemetry(0, 2000, 0, 700, 1400, 2000, 1, 0),
    )
    records = tuple(_afe_record(message) for message in messages)
    damaged = _damaged_crc(
        _afe_record(AfeTelemetry(1, 3000, 0, 900, 1800, 2000, 1, 0))
    )
    backend = ExternalSerialBackend((b"".join((*records, damaged)),))
    backend_contract: SerialBackend = backend
    session = SerialSession(
        backend_contract,
        SerialConnectionSettings(
            "EXTERNAL:AFE",
            AFE_PROFILE_NAME,
            read_chunk_bytes=1024,
            max_record_bytes=128,
        ),
        clock=lambda: NOW,
    )
    adapter = SerialAdapter(
        session,
        AfeV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST),
        SerialAdapterConfig(
            AFE_PROFILE_NAME,
            AFE_PROFILE_VERSION,
            max_polls_per_operation=2,
        ),
        capability_projector=project_afe_v1_read_only_capabilities,
    )
    request = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "afe.ch0.input",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                2,
            ),
            ChannelReadRequest(
                "afe.ch0.threshold",
                ReadOperation.DIGITAL,
                MeasurementUnit.BOOLEAN,
                2,
            ),
        ),
        request_id="phase4-golden-afe",
    )
    return _normalize(run_read_workflow(adapter, request), adapter, backend)


def _run_msp430() -> dict[str, Any]:
    messages: tuple[Msp430Message, ...] = (
        Msp430Telemetry(
            0xFFFFFFFF,
            1000,
            421,
            418,
            5012,
            186,
            932,
            650,
            Msp430DeviceState.COOLING_HIGH,
            0,
        ),
        Msp430Telemetry(
            0,
            2000,
            -32768,
            -32768,
            0,
            0,
            0,
            0,
            Msp430DeviceState.FAULT,
            int(
                Msp430Fault.DS18B20_MISSING
                | Msp430Fault.NTC_RANGE
                | Msp430Fault.INA219_COMM
            ),
        ),
    )
    records = tuple(_msp430_record(message) for message in messages)
    damaged = _damaged_crc(_msp430_record(messages[0]))
    backend = ExternalSerialBackend((b"".join((*records, damaged)),))
    backend_contract: SerialBackend = backend
    session = SerialSession(
        backend_contract,
        SerialConnectionSettings(
            "EXTERNAL:MSP430",
            MSP430_HEALTH_PROFILE_NAME,
            read_chunk_bytes=1024,
            max_record_bytes=128,
        ),
        clock=lambda: NOW,
    )
    adapter = SerialAdapter(
        session,
        Msp430HealthV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST),
        SerialAdapterConfig(
            MSP430_HEALTH_PROFILE_NAME,
            MSP430_HEALTH_PROFILE_VERSION,
            max_polls_per_operation=2,
        ),
        capability_projector=project_identity_read_only_capabilities,
    )
    request = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "msp430.health.temperature_ds",
                ReadOperation.ANALOG,
                MeasurementUnit.CELSIUS,
                2,
            ),
            ChannelReadRequest(
                "msp430.health.bus_voltage",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                2,
            ),
        ),
        request_id="phase4-golden-msp430",
    )
    return _normalize(run_read_workflow(adapter, request), adapter, backend)


def _actual() -> dict[str, Any]:
    return {
        "schema_version": "phase4-composite-golden.v1",
        "evidence_source": "HOST_TEST",
        "limitations": [
            "In-memory external backend only; no COM port or physical AFE was used.",
            (
                "MSP430 unavailable sentinels are frozen as invalid missing data, "
                "not physical zero readings."
            ),
        ],
        "afe": _run_afe(),
        "msp430": _run_msp430(),
    }


def _expected() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(GOLDEN_PATH.read_text(encoding="utf-8")))


def test_phase4_composite_fixture_is_versioned_and_host_only() -> None:
    expected = _expected()
    assert set(expected) == {
        "schema_version",
        "evidence_source",
        "limitations",
        "afe",
        "msp430",
    }
    assert expected["schema_version"] == "phase4-composite-golden.v1"
    assert expected["evidence_source"] == "HOST_TEST"
    assert all("BENCH_" not in value for value in expected["limitations"])


def test_phase4_external_backend_composites_match_frozen_meaning() -> None:
    assert _actual() == _expected()


def test_phase4_composites_retain_crc_rejection_and_wrap_semantics() -> None:
    actual = _actual()
    afe_events = actual["afe"]["raw_events"]
    msp430_events = actual["msp430"]["raw_events"]
    assert afe_events[-1]["status"] == "REJECTED"
    assert afe_events[-1]["error_type"] == "CrcMismatch"
    assert afe_events[5]["sequence"]["disposition"] == "IN_ORDER"
    assert msp430_events[-1]["status"] == "REJECTED"
    assert msp430_events[-1]["error_type"] == "CrcMismatch"
    assert msp430_events[1]["sequence"] == {
        "disposition": "IN_ORDER",
        "missing_count": 0,
        "value": 0,
    }


def test_phase4_composites_never_upgrade_host_or_missing_evidence() -> None:
    actual = _actual()
    assert actual["evidence_source"] == "HOST_TEST"
    for product in (actual["afe"], actual["msp430"]):
        assert product["evidence_source"] == "HOST_TEST"
        assert product["backend"]["has_write"] is False
    missing = actual["msp430"]["measurements"]
    assert missing[1]["value"] is None
    assert missing[1]["status"] == "INVALID"
    assert missing[3]["value"] is None
    assert missing[3]["status"] == "INVALID"
