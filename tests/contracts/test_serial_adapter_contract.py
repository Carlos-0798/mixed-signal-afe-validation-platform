"""Run the frozen read-only DeviceAdapter contract against SerialAdapter."""

from __future__ import annotations

from analog_validation.domain import (
    DeviceCommand,
    EvidenceSource,
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
    MSP430_HEALTH_CHANNEL_TEMPERATURE_DS,
    MSP430_HEALTH_PROFILE_NAME,
    MSP430_HEALTH_PROFILE_VERSION,
    Msp430DeviceState,
    Msp430Telemetry,
    encode_msp430_message,
)
from analog_validation.serial_adapters import (
    SerialAdapter,
    SerialAdapterConfig,
    project_afe_v1_read_only_capabilities,
    project_identity_read_only_capabilities,
)
from analog_validation.transport import SerialConnectionSettings, SerialSession
from tests.contracts.adapter_contract import (
    AdapterContractSpec,
    ReadOnlyAdapterContract,
)
from tests.support.serial_backend import MemorySerialBackend


def make_serial_adapter() -> SerialAdapter:
    telemetry = Msp430Telemetry(
        1,
        100,
        250,
        260,
        5000,
        100,
        500,
        250,
        Msp430DeviceState.NORMAL,
        0,
    )
    backend = MemorySerialBackend.scripted(
        reads=(encode_msp430_message(telemetry).encode("ascii"),)
    )
    session = SerialSession(
        backend,
        SerialConnectionSettings(
            "MEMORY:CONTRACT",
            MSP430_HEALTH_PROFILE_NAME,
            max_record_bytes=128,
        ),
    )
    return SerialAdapter(
        session,
        Msp430HealthV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST),
        SerialAdapterConfig(
            MSP430_HEALTH_PROFILE_NAME,
            MSP430_HEALTH_PROFILE_VERSION,
        ),
        capability_projector=project_identity_read_only_capabilities,
    )


class TestSerialAdapterContract(ReadOnlyAdapterContract):
    contract_spec = AdapterContractSpec(
        factory=make_serial_adapter,
        evidence_source=EvidenceSource.HOST_TEST,
        analog_channel=MSP430_HEALTH_CHANNEL_TEMPERATURE_DS,
        analog_unit=MeasurementUnit.CELSIUS,
    )


def make_afe_serial_adapter() -> SerialAdapter:
    messages = (
        AfeCapabilityDevice(
            3,
            "afe-contract",
            frozenset({DeviceCommand.READ_MEASUREMENT}),
        ),
        AfeCapabilityChannel(
            3,
            CapabilityChannelKind.ADC,
            0,
            0,
            3300,
            MeasurementUnit.MILLIVOLT,
        ),
        AfeCapabilityEnd(3, 1),
        AfeTelemetry(1, 100, 0, 500, 1000, 2000, 0, 0),
    )
    chunk = "".join(encode_afe_message(message) for message in messages).encode(
        "ascii"
    )
    backend = MemorySerialBackend.scripted(reads=(chunk, chunk))
    session = SerialSession(
        backend,
        SerialConnectionSettings(
            "MEMORY:AFE:CONTRACT",
            AFE_PROFILE_NAME,
            read_chunk_bytes=1024,
            max_record_bytes=128,
        ),
    )
    return SerialAdapter(
        session,
        AfeV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST),
        SerialAdapterConfig(AFE_PROFILE_NAME, AFE_PROFILE_VERSION),
        capability_projector=project_afe_v1_read_only_capabilities,
    )


class TestAfeSerialAdapterContract(ReadOnlyAdapterContract):
    contract_spec = AdapterContractSpec(
        factory=make_afe_serial_adapter,
        evidence_source=EvidenceSource.HOST_TEST,
        analog_channel="afe.ch0.input",
        analog_unit=MeasurementUnit.MILLIVOLT,
    )
