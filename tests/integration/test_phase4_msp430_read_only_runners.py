"""Prove output runners cannot write through the MSP430 read-only adapter."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from analog_validation.analysis import DCSweepAnalysisConfig, HysteresisAnalysisConfig
from analog_validation.config import (
    ChannelConfig,
    ChannelRole,
    ProfileConfig,
    ValidationConfig,
)
from analog_validation.domain import (
    EvidenceSource,
    MeasurementUnit,
    SafeRange,
)
from analog_validation.domain import TestRunMetadata as RunMetadata
from analog_validation.domain import TestRunOutcome as RunOutcome
from analog_validation.profiles import Msp430HealthV1SerialProfile
from analog_validation.protocol.msp430_health_v1 import (
    MSP430_HEALTH_PROFILE_NAME,
    MSP430_HEALTH_PROFILE_VERSION,
)
from analog_validation.runners import (
    DCSweepPlan,
    HysteresisPlan,
    run_dc_sweep,
    run_hysteresis,
)
from analog_validation.serial_adapters import (
    SerialAdapter,
    SerialAdapterConfig,
    project_identity_read_only_capabilities,
)
from analog_validation.transport import SerialConnectionSettings, SerialSession
from tests.support.serial_backend import MemorySerialBackend

NOW = datetime(2026, 8, 30, 23, 0, tzinfo=timezone.utc)
STIMULUS = "requested.stimulus"
INPUT = "requested.input"
OUTPUT = "requested.output"
STATE = "requested.state"
DEVICE_ID = "msp430-equipment-health-v1-contract"


class WriteTrapBackend(MemorySerialBackend):
    """Expose a write method solely to prove no runner/adapter code calls it."""

    def __init__(self) -> None:
        super().__init__()
        self.write_calls: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.write_calls.append(data)
        raise AssertionError("read-only MSP430 integration attempted a write")


def adapter_and_backend() -> tuple[SerialAdapter, WriteTrapBackend]:
    backend = WriteTrapBackend()
    session = SerialSession(
        backend,
        SerialConnectionSettings(
            "MEMORY:MSP430:RUNNER",
            MSP430_HEALTH_PROFILE_NAME,
            max_record_bytes=128,
        ),
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
    return adapter, backend


def output_config(*, hysteresis: bool) -> ValidationConfig:
    inputs = [
        ChannelConfig(INPUT, ChannelRole.ANALOG_INPUT, MeasurementUnit.MILLIVOLT)
    ]
    if hysteresis:
        inputs.append(
            ChannelConfig(STATE, ChannelRole.DIGITAL_INPUT, MeasurementUnit.BOOLEAN)
        )
    else:
        inputs.append(
            ChannelConfig(OUTPUT, ChannelRole.ANALOG_INPUT, MeasurementUnit.MILLIVOLT)
        )
    return ValidationConfig(
        "serial-output-request",
        "1",
        ProfileConfig(MSP430_HEALTH_PROFILE_NAME, MSP430_HEALTH_PROFILE_VERSION),
        EvidenceSource.HOST_TEST,
        (
            *inputs,
            ChannelConfig(
                STIMULUS,
                ChannelRole.ANALOG_OUTPUT,
                MeasurementUnit.MILLIVOLT,
                safe_output_range=SafeRange(
                    0,
                    2000,
                    MeasurementUnit.MILLIVOLT,
                ),
            ),
        ),
        allow_output=True,
    )


def metadata(test_type: str) -> RunMetadata:
    return RunMetadata(
        f"{test_type}-msp430-read-only",
        test_type,
        "serial-output-request",
        "1",
        NOW,
        NOW + timedelta(seconds=1),
        "0.1.0.dev0",
        DEVICE_ID,
        MSP430_HEALTH_PROFILE_NAME,
        MSP430_HEALTH_PROFILE_VERSION,
        EvidenceSource.HOST_TEST,
    )


def test_dc_runner_returns_unsupported_before_any_read_or_write() -> None:
    adapter, backend = adapter_and_backend()
    plan = DCSweepPlan(
        "msp430-dc-request",
        "1",
        STIMULUS,
        MeasurementUnit.MILLIVOLT,
        (100.0, 200.0),
        1,
        DCSweepAnalysisConfig(INPUT, OUTPUT, 0, 3300),
    )

    result = run_dc_sweep(
        adapter,
        plan,
        output_config(hysteresis=False),
        metadata("dc-sweep"),
        settle=lambda _seconds: None,
    )

    assert result.outcome is RunOutcome.UNSUPPORTED
    assert result.measurements == ()
    assert (
        "command:SET_ANALOG_STIMULUS"
        in result.test_run_result.missing_requirements
    )
    assert "command:SAFE_SHUTDOWN" in result.test_run_result.missing_requirements
    assert backend.write_calls == []
    assert backend.read_calls == []
    assert len(backend.open_calls) == 1
    assert backend.close_calls == 1


def test_hysteresis_runner_returns_unsupported_before_any_read_or_write() -> None:
    adapter, backend = adapter_and_backend()
    plan = HysteresisPlan(
        "msp430-hysteresis-request",
        "1",
        STIMULUS,
        MeasurementUnit.MILLIVOLT,
        (1000.0, 1500.0),
        (1500.0, 1000.0),
        1,
        HysteresisAnalysisConfig(INPUT, STATE),
    )

    result = run_hysteresis(
        adapter,
        plan,
        output_config(hysteresis=True),
        metadata("hysteresis"),
        settle=lambda _seconds: None,
    )

    assert result.outcome is RunOutcome.UNSUPPORTED
    assert result.measurements == ()
    assert (
        "command:SET_ANALOG_STIMULUS"
        in result.test_run_result.missing_requirements
    )
    assert "command:SAFE_SHUTDOWN" in result.test_run_result.missing_requirements
    assert backend.write_calls == []
    assert backend.read_calls == []
    assert len(backend.open_calls) == 1
    assert backend.close_calls == 1
