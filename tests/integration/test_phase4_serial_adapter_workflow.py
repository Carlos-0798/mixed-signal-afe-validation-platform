"""Product-chain tests from in-memory serial configuration to ReadWorkflow."""

from __future__ import annotations

from datetime import datetime, timezone

from analog_validation.config import (
    ChannelConfig,
    ChannelRole,
    ProfileConfig,
    ValidationConfig,
    validate_config_capabilities,
)
from analog_validation.domain import (
    DeviceCommand,
    EvidenceSource,
    MeasurementStatus,
    MeasurementUnit,
)
from analog_validation.profiles import (
    AfeV1SerialProfile,
    Msp430HealthV1SerialProfile,
)
from analog_validation.protocol import (
    AFE_PROFILE_NAME,
    AFE_PROFILE_VERSION,
    AfeCapabilityChannel,
    AfeCapabilityDevice,
    AfeCapabilityEnd,
    AfeTelemetry,
    CapabilityChannelKind,
    encode_afe_message,
)
from analog_validation.protocol.msp430_health_v1 import (
    MSP430_HEALTH_PROFILE_NAME,
    MSP430_HEALTH_PROFILE_VERSION,
    Msp430DeviceState,
    Msp430Fault,
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
    RawRecordStatus,
    SerialConnectionSettings,
    SerialSession,
)
from analog_validation.workflows import (
    ChannelReadRequest,
    ReadOperation,
    ReadWorkflowRequest,
    ReadWorkflowStatus,
    run_read_workflow,
)
from tests.support.serial_backend import MemorySerialBackend

NOW = datetime(2026, 8, 30, 22, 30, tzinfo=timezone.utc)


def afe_capabilities() -> bytes:
    messages = (
        AfeCapabilityDevice(
            9,
            "afe-serial-memory",
            frozenset(
                {
                    DeviceCommand.READ_MEASUREMENT,
                    DeviceCommand.READ_DIGITAL_STATE,
                }
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
    )
    return "".join(encode_afe_message(value) for value in messages).encode("ascii")


def afe_tel(sequence: int, input_mv: int, threshold: int) -> bytes:
    return encode_afe_message(
        AfeTelemetry(
            sequence,
            sequence * 100,
            0,
            input_mv,
            min(3300, input_mv * 2),
            2000,
            threshold,
            0,
        )
    ).encode("ascii")


def test_afe_config_to_serial_adapter_to_workflow_preserves_raw_lineage() -> None:
    backend = MemorySerialBackend.scripted(
        reads=(
            afe_capabilities(),
            afe_tel(1, 400, 0),
            afe_tel(2, 700, 1),
        )
    )
    session = SerialSession(
        backend,
        SerialConnectionSettings(
            "MEMORY:AFE:WORKFLOW",
            AFE_PROFILE_NAME,
            read_chunk_bytes=1024,
            max_record_bytes=128,
        ),
        clock=lambda: NOW,
    )
    adapter_config = SerialAdapterConfig(
        AFE_PROFILE_NAME,
        AFE_PROFILE_VERSION,
        max_polls_per_operation=4,
    )
    adapter = SerialAdapter(
        session,
        AfeV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST),
        adapter_config,
        capability_projector=project_afe_v1_read_only_capabilities,
    )
    product_config = ValidationConfig(
        "afe-serial-read",
        "1",
        ProfileConfig(AFE_PROFILE_NAME, AFE_PROFILE_VERSION),
        EvidenceSource.HOST_TEST,
        (
            ChannelConfig(
                "afe.ch0.input",
                ChannelRole.ANALOG_INPUT,
                MeasurementUnit.MILLIVOLT,
            ),
            ChannelConfig(
                "afe.ch0.threshold",
                ChannelRole.DIGITAL_INPUT,
                MeasurementUnit.BOOLEAN,
            ),
        ),
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
        request_id="afe-memory-composite",
    )

    result = run_read_workflow(adapter, request)
    validate_config_capabilities(product_config, result.capabilities)

    assert result.status is ReadWorkflowStatus.COMPLETED
    assert [value.value for value in result.measurements] == [400.0, 700.0, 0.0, 1.0]
    assert all(value.source is EvidenceSource.HOST_TEST for value in result.measurements)
    assert all(value.status is MeasurementStatus.VALID for value in result.measurements)
    assert len({value.raw_record_id for value in result.measurements}) == 2
    assert [event.status for event in adapter.raw_events.events] == [
        RawRecordStatus.PARSED,
        RawRecordStatus.PARSED,
        RawRecordStatus.PARSED,
        RawRecordStatus.PARSED,
        RawRecordStatus.PARSED,
        RawRecordStatus.PARSED,
    ]
    assert len(backend.open_calls) == 1
    assert len(backend.read_calls) == 3
    assert backend.close_calls == 1
    assert not backend.is_open


def test_msp430_workflow_keeps_unavailable_values_as_completed_invalid_samples() -> None:
    telemetry = Msp430Telemetry(
        42,
        4000,
        -32768,
        255,
        0,
        0,
        0,
        0,
        Msp430DeviceState.INIT,
        int(Msp430Fault.DS18B20_MISSING | Msp430Fault.INA219_COMM),
    )
    backend = MemorySerialBackend.scripted(
        reads=(encode_msp430_message(telemetry).encode("ascii"),)
    )
    session = SerialSession(
        backend,
        SerialConnectionSettings(
            "MEMORY:MSP430:WORKFLOW",
            MSP430_HEALTH_PROFILE_NAME,
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
        ),
        capability_projector=project_identity_read_only_capabilities,
    )
    request = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "msp430.health.temperature_ds",
                ReadOperation.ANALOG,
                MeasurementUnit.CELSIUS,
            ),
            ChannelReadRequest(
                "msp430.health.bus_voltage",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
            ),
            ChannelReadRequest(
                "msp430.health.current",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIAMPERE,
            ),
        ),
        request_id="msp430-memory-composite",
    )

    result = run_read_workflow(adapter, request)

    assert result.status is ReadWorkflowStatus.COMPLETED
    assert [value.value for value in result.measurements] == [None, None, None]
    assert all(
        value.status is MeasurementStatus.INVALID for value in result.measurements
    )
    assert all(value.source is EvidenceSource.HOST_TEST for value in result.measurements)
    assert result.evidence_source is EvidenceSource.HOST_TEST
    assert not result.evidence_source.is_bench_evidence
    assert len(backend.read_calls) == 1
    assert backend.close_calls == 1
