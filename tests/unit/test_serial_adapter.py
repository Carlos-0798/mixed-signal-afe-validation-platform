"""Focused tests for the receive-only Phase 4 SerialAdapter."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, cast

import pytest

from analog_validation import serial_adapters
from analog_validation.adapters import AdapterState
from analog_validation.domain import (
    ChannelRange,
    DeviceCapabilities,
    DeviceCommand,
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
    SafeRange,
)
from analog_validation.errors import (
    AdapterConnectionError,
    AdapterDataError,
    CapabilityError,
    ConfigurationError,
)
from analog_validation.profiles import (
    MSP430_HEALTH_V1_SERIAL_IDENTITY,
    AfeV1SerialProfile,
    Msp430HealthV1SerialProfile,
    SerialProfileResetResult,
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
    MSP430_HEALTH_MAX_RECORD_BYTES,
    MSP430_HEALTH_PROFILE_NAME,
    MSP430_HEALTH_PROFILE_VERSION,
    Msp430DeviceState,
    Msp430Telemetry,
    encode_msp430_message,
)
from analog_validation.serial_adapters import (
    MAX_BUFFERED_MEASUREMENTS,
    MAX_POLLS_PER_OPERATION,
    SERIAL_ADAPTER_CONFIG_SCHEMA_VERSION,
    SerialAdapter,
    SerialAdapterConfig,
    project_afe_v1_read_only_capabilities,
    project_identity_read_only_capabilities,
)
from analog_validation.transport import (
    SerialBackendDisconnected,
    SerialConnectionSettings,
    SerialSession,
    SerialSessionState,
)
from tests.support.serial_backend import MemorySerialBackend

NOW = datetime(2026, 8, 30, 22, 0, tzinfo=timezone.utc)


class StaticProfile:
    """Runtime-compatible profile stub for constructor and capability defenses."""

    def __init__(self, source: EvidenceSource, initial: object) -> None:
        self._source = source
        self._initial = initial

    @property
    def identity(self):  # type: ignore[no-untyped-def]
        return MSP430_HEALTH_V1_SERIAL_IDENTITY

    @property
    def evidence_source(self) -> EvidenceSource:
        return self._source

    @property
    def initial_capabilities(self) -> DeviceCapabilities | None:
        return cast(DeviceCapabilities | None, self._initial)

    def process_record(self, event: object, event_log: object) -> object:
        raise AssertionError("StaticProfile does not consume records")

    def reset(self) -> SerialProfileResetResult:
        return SerialProfileResetResult(None)


def msp_telemetry(**changes: Any) -> Msp430Telemetry:
    values: dict[str, Any] = {
        "sequence": 10,
        "uptime_ms": 1_000,
        "temperature_ds_deci_c": 250,
        "temperature_ntc_deci_c": 260,
        "bus_mv": 5_000,
        "current_ma": 120,
        "power_mw": 600,
        "pwm_permille": 300,
        "state": Msp430DeviceState.NORMAL,
        "fault_flags": 0,
    }
    values.update(changes)
    return Msp430Telemetry(**values)


def msp_record(**changes: Any) -> bytes:
    return encode_msp430_message(msp_telemetry(**changes)).encode("ascii")


def damaged_crc(record: bytes) -> bytes:
    replacement = b"0000" if record[-5:-1] != b"0000" else b"FFFF"
    return record[:-5] + replacement + b"\n"


def make_msp_adapter(
    *,
    reads: tuple[object, ...] = (),
    backend: MemorySerialBackend | None = None,
    config: SerialAdapterConfig | None = None,
    projector: object = project_identity_read_only_capabilities,
    settings: SerialConnectionSettings | None = None,
) -> tuple[SerialAdapter, MemorySerialBackend, Msp430HealthV1SerialProfile]:
    selected_backend = backend or MemorySerialBackend.scripted(reads=reads)
    selected_settings = settings or SerialConnectionSettings(
        port_id="MEMORY:MSP430",
        profile_name=MSP430_HEALTH_PROFILE_NAME,
        max_record_bytes=MSP430_HEALTH_MAX_RECORD_BYTES,
        read_chunk_bytes=512,
        max_reconnect_attempts=1,
    )
    session = SerialSession(selected_backend, selected_settings, clock=lambda: NOW)
    profile = Msp430HealthV1SerialProfile(
        evidence_source=EvidenceSource.HOST_TEST
    )
    selected_config = config or SerialAdapterConfig(
        MSP430_HEALTH_PROFILE_NAME,
        MSP430_HEALTH_PROFILE_VERSION,
    )
    adapter = SerialAdapter(
        session,
        profile,
        selected_config,
        capability_projector=cast(Any, projector),
    )
    return adapter, selected_backend, profile


def afe_capability_records(*, device_id: str = "afe-memory-1") -> bytes:
    messages = (
        AfeCapabilityDevice(
            77,
            device_id,
            frozenset(
                {
                    DeviceCommand.READ_MEASUREMENT,
                    DeviceCommand.READ_DIGITAL_STATE,
                }
            ),
        ),
        AfeCapabilityChannel(
            77,
            CapabilityChannelKind.ADC,
            0,
            0,
            3300,
            MeasurementUnit.MILLIVOLT,
        ),
        AfeCapabilityChannel(77, CapabilityChannelKind.DIGITAL_INPUT, 0),
        AfeCapabilityEnd(77, 2),
    )
    return "".join(encode_afe_message(message) for message in messages).encode(
        "ascii"
    )


def afe_telemetry(*, sequence: int = 1) -> bytes:
    return encode_afe_message(
        AfeTelemetry(sequence, 100, 0, 500, 1500, 3000, 1, 0)
    ).encode("ascii")


def make_afe_adapter(
    *,
    reads: tuple[object, ...],
    max_polls: int = 4,
) -> tuple[SerialAdapter, MemorySerialBackend]:
    backend = MemorySerialBackend.scripted(reads=reads)
    session = SerialSession(
        backend,
        SerialConnectionSettings(
            port_id="MEMORY:AFE",
            profile_name=AFE_PROFILE_NAME,
            read_chunk_bytes=1024,
            max_record_bytes=128,
        ),
        clock=lambda: NOW,
    )
    profile = AfeV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    adapter = SerialAdapter(
        session,
        profile,
        SerialAdapterConfig(
            AFE_PROFILE_NAME,
            AFE_PROFILE_VERSION,
            max_polls_per_operation=max_polls,
        ),
        capability_projector=project_afe_v1_read_only_capabilities,
    )
    return adapter, backend


def test_config_defaults_and_schema_are_explicit() -> None:
    config = SerialAdapterConfig("profile", "1")

    assert config.profile_name == "profile"
    assert config.profile_version == "1"
    assert config.max_polls_per_operation == 32
    assert config.max_buffered_measurements == 1024
    assert config.schema_version == SERIAL_ADAPTER_CONFIG_SCHEMA_VERSION


def test_public_serial_adapter_exports_are_explicit() -> None:
    assert serial_adapters.__all__ == [
        "DEFAULT_MAX_BUFFERED_MEASUREMENTS",
        "DEFAULT_MAX_POLLS_PER_OPERATION",
        "MAX_BUFFERED_MEASUREMENTS",
        "MAX_POLLS_PER_OPERATION",
        "SERIAL_ADAPTER_CONFIG_SCHEMA_VERSION",
        "CapabilityProjector",
        "SerialAdapter",
        "SerialAdapterConfig",
        "project_afe_v1_read_only_capabilities",
        "project_identity_read_only_capabilities",
    ]
    assert all(hasattr(serial_adapters, name) for name in serial_adapters.__all__)


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"profile_name": ""}, "profile_name"),
        ({"profile_name": " profile"}, "profile_name"),
        ({"profile_name": "bad\x00"}, "printable"),
        ({"profile_version": "\n"}, "profile_version"),
        ({"max_polls_per_operation": True}, "integer"),
        ({"max_polls_per_operation": 0}, "between"),
        ({"max_polls_per_operation": MAX_POLLS_PER_OPERATION + 1}, "between"),
        ({"max_buffered_measurements": 0}, "between"),
        (
            {"max_buffered_measurements": MAX_BUFFERED_MEASUREMENTS + 1},
            "between",
        ),
        ({"schema_version": "serial-adapter-config.v2"}, "unsupported"),
    ],
)
def test_config_rejects_invalid_values(
    changes: dict[str, object], match: str
) -> None:
    values: dict[str, object] = {"profile_name": "profile", "profile_version": "1"}
    values.update(changes)

    with pytest.raises(ConfigurationError, match=match):
        SerialAdapterConfig(**values)  # type: ignore[arg-type]


def test_constructor_freezes_profile_session_and_evidence_identity() -> None:
    adapter, backend, profile = make_msp_adapter()

    assert adapter.state is AdapterState.DISCONNECTED
    assert adapter.evidence_source is EvidenceSource.HOST_TEST
    assert adapter.profile_identity is profile.identity
    assert adapter.serial_config.profile_name == MSP430_HEALTH_PROFILE_NAME
    assert adapter.raw_events.events == ()
    assert adapter.native_capabilities is None
    assert not backend.is_open


@pytest.mark.parametrize(
    ("kind", "match"),
    [
        ("session", "SerialSession"),
        ("profile", "SerialProfile"),
        ("config", "SerialAdapterConfig"),
        ("projector", "callable"),
    ],
)
def test_constructor_rejects_wrong_boundary_types(kind: str, match: str) -> None:
    backend = MemorySerialBackend()
    session = SerialSession(
        backend,
        SerialConnectionSettings(
            "MEMORY:MSP430",
            MSP430_HEALTH_PROFILE_NAME,
            max_record_bytes=128,
        ),
    )
    profile = Msp430HealthV1SerialProfile(
        evidence_source=EvidenceSource.HOST_TEST
    )
    config = SerialAdapterConfig(
        MSP430_HEALTH_PROFILE_NAME,
        MSP430_HEALTH_PROFILE_VERSION,
    )
    values: dict[str, object] = {
        "session": session,
        "profile": profile,
        "config": config,
        "capability_projector": project_identity_read_only_capabilities,
    }
    values[kind if kind != "projector" else "capability_projector"] = object()

    with pytest.raises(ConfigurationError, match=match):
        SerialAdapter(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("change", "match"),
    [
        ("config-name", "config"),
        ("config-version", "config"),
        ("session-profile", "profile_name"),
        ("record-size", "max_record_bytes"),
        ("open-session", "closed"),
    ],
)
def test_constructor_rejects_identity_or_state_mismatch(
    change: str, match: str
) -> None:
    settings = SerialConnectionSettings(
        "MEMORY:MSP430",
        "wrong" if change == "session-profile" else MSP430_HEALTH_PROFILE_NAME,
        max_record_bytes=127 if change == "record-size" else 128,
    )
    backend = MemorySerialBackend()
    session = SerialSession(backend, settings)
    if change == "open-session":
        session.open()
    profile = Msp430HealthV1SerialProfile(
        evidence_source=EvidenceSource.HOST_TEST
    )
    config = SerialAdapterConfig(
        "wrong" if change == "config-name" else MSP430_HEALTH_PROFILE_NAME,
        "2" if change == "config-version" else MSP430_HEALTH_PROFILE_VERSION,
    )

    with pytest.raises(ConfigurationError, match=match):
        SerialAdapter(
            session,
            profile,
            config,
            capability_projector=project_identity_read_only_capabilities,
        )
    session.close()


def test_constructor_rejects_profile_that_attempts_non_serial_evidence() -> None:
    backend = MemorySerialBackend()
    session = SerialSession(
        backend,
        SerialConnectionSettings(
            "MEMORY:STATIC",
            MSP430_HEALTH_PROFILE_NAME,
            max_record_bytes=128,
        ),
    )
    profile = StaticProfile(EvidenceSource.SYNTHETIC, None)

    with pytest.raises(ConfigurationError, match="HOST_TEST or BENCH_CONTROLLER"):
        SerialAdapter(
            session,
            cast(Any, profile),
            SerialAdapterConfig(
                MSP430_HEALTH_PROFILE_NAME,
                MSP430_HEALTH_PROFILE_VERSION,
            ),
            capability_projector=project_identity_read_only_capabilities,
        )


def test_msp_static_capabilities_require_no_poll_and_remain_read_only() -> None:
    adapter, backend, _ = make_msp_adapter()

    adapter.connect()
    capabilities = adapter.get_capabilities()

    assert capabilities is adapter.capabilities
    assert adapter.native_capabilities is not None
    assert capabilities.is_read_only
    assert not capabilities.supports_safe_shutdown
    assert backend.read_calls == []
    adapter.disconnect()


def test_one_msp_record_buffers_independent_channel_measurements() -> None:
    adapter, backend, _ = make_msp_adapter(reads=(msp_record(),))
    adapter.connect()
    adapter.get_capabilities()

    ds = adapter.read_measurement("msp430.health.temperature_ds")
    ntc = adapter.read_measurement("msp430.health.temperature_ntc")
    bus = adapter.read_measurement("msp430.health.bus_voltage")
    current = adapter.read_measurement("msp430.health.current")
    pwm = adapter.read_measurement("msp430.health.fan_pwm")

    assert [value.value for value in (ds, ntc, bus, current, pwm)] == [
        25.0,
        26.0,
        5000.0,
        120.0,
        0.3,
    ]
    assert len(backend.read_calls) == 1
    assert adapter.buffered_measurement_count == 0
    assert adapter.raw_events.events[0].raw_bytes == msp_record()
    adapter.disconnect()


def test_unknown_channel_fails_before_any_serial_poll() -> None:
    adapter, backend, _ = make_msp_adapter(reads=(msp_record(),))
    adapter.connect()
    adapter.get_capabilities()

    with pytest.raises(CapabilityError, match="ADC channel"):
        adapter.read_measurement("unknown")

    assert backend.read_calls == []
    adapter.disconnect()


def test_bounded_poll_budget_turns_repeated_timeouts_into_data_error() -> None:
    config = SerialAdapterConfig(
        MSP430_HEALTH_PROFILE_NAME,
        MSP430_HEALTH_PROFILE_VERSION,
        max_polls_per_operation=2,
    )
    adapter, backend, _ = make_msp_adapter(config=config)
    adapter.connect()
    adapter.get_capabilities()

    with pytest.raises(AdapterDataError, match="bounded poll budget"):
        adapter.read_measurement(MSP430_HEALTH_CHANNEL_TEMPERATURE_DS)

    assert len(backend.read_calls) == 2
    adapter.disconnect()


def test_rejected_record_is_retained_and_later_valid_record_recovers() -> None:
    invalid = damaged_crc(msp_record(sequence=9))
    valid = msp_record(sequence=10)
    adapter, _, _ = make_msp_adapter(reads=(invalid + valid,))
    adapter.connect()
    adapter.get_capabilities()

    measurement = adapter.read_measurement(MSP430_HEALTH_CHANNEL_TEMPERATURE_DS)

    assert measurement.value == 25.0
    assert adapter.rejected_record_count == 1
    assert [event.status.value for event in adapter.raw_events.events] == [
        "REJECTED",
        "PARSED",
    ]
    adapter.disconnect()


def test_stream_issue_is_counted_and_following_record_is_usable() -> None:
    chunk = b"X" * 129 + b"\n" + msp_record()
    adapter, _, _ = make_msp_adapter(reads=(chunk,))
    adapter.connect()
    adapter.get_capabilities()

    measurement = adapter.read_measurement(MSP430_HEALTH_CHANNEL_TEMPERATURE_DS)

    assert measurement.value == 25.0
    assert adapter.stream_issue_count == 1
    assert len(adapter.raw_events.events) == 1
    adapter.disconnect()


def test_measurement_buffer_overflow_fails_closed() -> None:
    config = SerialAdapterConfig(
        MSP430_HEALTH_PROFILE_NAME,
        MSP430_HEALTH_PROFILE_VERSION,
        max_buffered_measurements=4,
    )
    adapter, _, _ = make_msp_adapter(reads=(msp_record(),), config=config)
    adapter.connect()
    adapter.get_capabilities()

    with pytest.raises(AdapterDataError, match="buffer limit"):
        adapter.read_measurement(MSP430_HEALTH_CHANNEL_TEMPERATURE_DS)

    assert adapter.buffered_measurement_count == 0
    adapter.disconnect()


def test_reconnect_invalidates_capabilities_and_requires_visible_reconfirmation() -> None:
    backend = MemorySerialBackend.scripted(reads=(SerialBackendDisconnected(),))
    adapter, _, _ = make_msp_adapter(backend=backend)
    adapter.connect()
    adapter.get_capabilities()

    with pytest.raises(AdapterConnectionError, match="reconnected"):
        adapter.read_measurement(MSP430_HEALTH_CHANNEL_TEMPERATURE_DS)

    assert adapter.state is AdapterState.CONNECTED_READ_ONLY
    assert adapter.reconnect_count == 1
    assert adapter.native_capabilities is None
    capabilities = adapter.get_capabilities()
    assert capabilities.profile_name == MSP430_HEALTH_PROFILE_NAME
    adapter.disconnect()


def test_fatal_poll_failure_marks_adapter_disconnected() -> None:
    adapter, backend, _ = make_msp_adapter(reads=(RuntimeError("read failed"),))
    adapter.connect()
    adapter.get_capabilities()

    with pytest.raises(AdapterConnectionError, match="poll failed"):
        adapter.read_measurement(MSP430_HEALTH_CHANNEL_TEMPERATURE_DS)

    assert adapter.state is AdapterState.DISCONNECTED
    assert not backend.is_open


def test_open_and_close_failures_are_mapped_to_adapter_connection_errors() -> None:
    open_backend = MemorySerialBackend.scripted(
        opens=(RuntimeError("open failed"),)
    )
    open_adapter, _, _ = make_msp_adapter(backend=open_backend)
    with pytest.raises(AdapterConnectionError, match="open failed"):
        open_adapter.connect()
    assert open_adapter.state is AdapterState.DISCONNECTED

    close_backend = MemorySerialBackend.scripted(
        closes=(RuntimeError("close failed"),)
    )
    close_adapter, _, _ = make_msp_adapter(backend=close_backend)
    close_adapter.connect()
    with pytest.raises(AdapterConnectionError, match="close failed"):
        close_adapter.disconnect()
    assert close_adapter.state is AdapterState.DISCONNECTED


def test_disconnect_resets_profile_and_buffer_but_preserves_raw_provenance() -> None:
    adapter, backend, profile = make_msp_adapter(
        reads=(msp_record(sequence=99), msp_record(sequence=1))
    )
    adapter.connect()
    adapter.get_capabilities()
    adapter.read_measurement(MSP430_HEALTH_CHANNEL_TEMPERATURE_DS)
    assert profile.last_telemetry_sequence == 99
    assert adapter.buffered_measurement_count == 4

    adapter.disconnect()
    adapter.connect()
    adapter.get_capabilities()
    adapter.read_measurement(MSP430_HEALTH_CHANNEL_TEMPERATURE_DS)

    assert profile.last_telemetry_sequence == 1
    assert len(adapter.raw_events.events) == 2
    assert len(backend.open_calls) == 2
    adapter.disconnect()


def test_afe_capability_projection_is_explicit_and_receive_only() -> None:
    native = DeviceCapabilities(
        "afe-device",
        AFE_PROFILE_NAME,
        AFE_PROFILE_VERSION,
        adc_channels=("adc0",),
        dac_channels=("dac1",),
        pwm_channels=("pwm2",),
        digital_input_channels=("din3",),
        safe_input_ranges=(
            ChannelRange("adc0", SafeRange(0, 3300, MeasurementUnit.MILLIVOLT)),
        ),
        safe_output_ranges=(
            ChannelRange("dac1", SafeRange(0, 3300, MeasurementUnit.MILLIVOLT)),
            ChannelRange("pwm2", SafeRange(0, 1, MeasurementUnit.RATIO)),
        ),
        supported_commands=frozenset(DeviceCommand),
        supports_safe_shutdown=True,
    )

    projected = project_afe_v1_read_only_capabilities(native)

    assert projected.adc_channels == ("afe.ch0.input",)
    assert projected.dac_channels == ("afe.ch1.dac",)
    assert projected.pwm_channels == ("afe.ch2.pwm",)
    assert projected.digital_input_channels == ("afe.ch3.threshold",)
    assert projected.supported_commands == frozenset(
        {
            DeviceCommand.READ_MEASUREMENT,
            DeviceCommand.READ_DIGITAL_STATE,
        }
    )
    assert projected.is_read_only
    assert not projected.supports_safe_shutdown
    assert projected.get_output_range("afe.ch2.pwm").unit is MeasurementUnit.RATIO


@pytest.mark.parametrize("name", ["adc", "adc-1", "adc256", "wrong0"])
def test_afe_projection_rejects_noncanonical_wire_names(name: str) -> None:
    native = DeviceCapabilities(
        "afe-device",
        AFE_PROFILE_NAME,
        AFE_PROFILE_VERSION,
        adc_channels=(name,),
        safe_input_ranges=(
            ChannelRange(name, SafeRange(0, 1, MeasurementUnit.MILLIVOLT)),
        ),
        supported_commands=frozenset({DeviceCommand.READ_MEASUREMENT}),
    )

    with pytest.raises(ConfigurationError, match="0..255"):
        project_afe_v1_read_only_capabilities(native)


def test_capability_projectors_reject_wrong_types_and_profiles() -> None:
    with pytest.raises(ConfigurationError, match="DeviceCapabilities"):
        project_identity_read_only_capabilities(cast(Any, object()))
    with pytest.raises(ConfigurationError, match="DeviceCapabilities"):
        project_afe_v1_read_only_capabilities(cast(Any, object()))

    msp_capabilities = make_msp_adapter()[2].capabilities
    with pytest.raises(ConfigurationError, match="not AFE v1"):
        project_afe_v1_read_only_capabilities(msp_capabilities)


def test_afe_passive_capabilities_and_buffered_telemetry_share_one_poll() -> None:
    adapter, backend = make_afe_adapter(
        reads=(afe_capability_records() + afe_telemetry(),)
    )
    adapter.connect()

    capabilities = adapter.get_capabilities()
    input_measurement = adapter.read_measurement("afe.ch0.input")
    threshold = adapter.read_digital_state("afe.ch0.threshold")

    assert capabilities.adc_channels == ("afe.ch0.input",)
    assert capabilities.digital_input_channels == ("afe.ch0.threshold",)
    assert capabilities.is_read_only
    assert adapter.native_capabilities is not None
    assert adapter.native_capabilities.adc_channels == ("adc0",)
    assert input_measurement.value == 500.0
    assert threshold.value == 1.0
    assert len(backend.read_calls) == 1
    adapter.disconnect()


def test_afe_capability_timeout_is_bounded_and_disconnectable() -> None:
    adapter, backend = make_afe_adapter(reads=(), max_polls=2)
    adapter.connect()

    with pytest.raises(AdapterDataError, match="capability negotiation"):
        adapter.get_capabilities()

    assert len(backend.read_calls) == 2
    adapter.disconnect()
    assert adapter.state is AdapterState.DISCONNECTED


def test_changed_native_capabilities_fail_closed_during_read() -> None:
    adapter, _ = make_afe_adapter(
        reads=(
            afe_capability_records(device_id="first"),
            afe_capability_records(device_id="second") + afe_telemetry(),
        )
    )
    adapter.connect()
    adapter.get_capabilities()

    with pytest.raises(AdapterDataError, match="changed in-session"):
        adapter.read_measurement("afe.ch0.input")

    adapter.disconnect()


def test_changed_projected_capabilities_fail_closed_during_read() -> None:
    calls = 0

    def changing_projector(native: DeviceCapabilities) -> DeviceCapabilities:
        nonlocal calls
        calls += 1
        projected = project_afe_v1_read_only_capabilities(native)
        if calls == 1:
            return projected
        return replace(
            projected,
            adc_channels=("afe.ch0.alternate",),
            safe_input_ranges=(
                ChannelRange(
                    "afe.ch0.alternate",
                    projected.safe_input_ranges[0].safe_range,
                ),
            ),
        )

    backend = MemorySerialBackend.scripted(
        reads=(
            afe_capability_records(),
            afe_capability_records() + afe_telemetry(),
        )
    )
    session = SerialSession(
        backend,
        SerialConnectionSettings(
            "MEMORY:AFE:CHANGED",
            AFE_PROFILE_NAME,
            read_chunk_bytes=1024,
            max_record_bytes=128,
        ),
        clock=lambda: NOW,
    )
    adapter = SerialAdapter(
        session,
        AfeV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST),
        SerialAdapterConfig(AFE_PROFILE_NAME, AFE_PROFILE_VERSION),
        capability_projector=changing_projector,
    )
    adapter.connect()
    adapter.get_capabilities()

    with pytest.raises(AdapterDataError, match="projected capabilities changed"):
        adapter.read_measurement("afe.ch0.input")

    adapter.disconnect()


@pytest.mark.parametrize(
    ("projector", "match"),
    [
        (lambda _value: cast(Any, object()), "must return"),
        (
            lambda value: replace(value, device_id="changed"),
            "identity",
        ),
        (
            lambda value: DeviceCapabilities(
                value.device_id,
                value.profile_name,
                value.profile_version,
            ),
            "every declared channel",
        ),
        (
            lambda value: replace(
                value,
                supported_commands=value.supported_commands
                | {DeviceCommand.RUN_DEVICE_COMMAND},
            ),
            "added a command",
        ),
    ],
)
def test_projection_contract_rejects_invalid_or_escalated_results(
    projector: object,
    match: str,
) -> None:
    adapter, _, _ = make_msp_adapter(projector=projector)
    adapter.connect()

    with pytest.raises(AdapterDataError, match=match):
        adapter.get_capabilities()

    adapter.disconnect()


def test_projection_contract_rejects_range_changes_and_native_write_commands() -> None:
    def change_range(value: DeviceCapabilities) -> DeviceCapabilities:
        first, *remaining = value.safe_input_ranges
        changed = ChannelRange(
            first.channel,
            SafeRange(
                first.safe_range.minimum + 1,
                first.safe_range.maximum,
                first.safe_range.unit,
            ),
        )
        return replace(value, safe_input_ranges=(changed, *remaining))

    range_adapter, _, _ = make_msp_adapter(projector=change_range)
    range_adapter.connect()
    with pytest.raises(AdapterDataError, match="numeric range"):
        range_adapter.get_capabilities()
    range_adapter.disconnect()

    profile = StaticProfile(
        EvidenceSource.HOST_TEST,
        replace(
            make_msp_adapter()[2].capabilities,
            supported_commands=frozenset(
                {
                    DeviceCommand.READ_MEASUREMENT,
                    DeviceCommand.RUN_DEVICE_COMMAND,
                }
            ),
        ),
    )
    backend = MemorySerialBackend()
    session = SerialSession(
        backend,
        SerialConnectionSettings(
            "MEMORY:STATIC:WRITE",
            MSP430_HEALTH_PROFILE_NAME,
            max_record_bytes=128,
        ),
    )
    write_adapter = SerialAdapter(
        session,
        cast(Any, profile),
        SerialAdapterConfig(
            MSP430_HEALTH_PROFILE_NAME,
            MSP430_HEALTH_PROFILE_VERSION,
        ),
        capability_projector=lambda value: value,
    )
    write_adapter.connect()
    with pytest.raises(AdapterDataError, match="receive-only"):
        write_adapter.get_capabilities()
    write_adapter.disconnect()


def test_invalid_static_capabilities_are_rejected() -> None:
    backend = MemorySerialBackend()
    session = SerialSession(
        backend,
        SerialConnectionSettings(
            "MEMORY:STATIC:INVALID",
            MSP430_HEALTH_PROFILE_NAME,
            max_record_bytes=128,
        ),
    )
    adapter = SerialAdapter(
        session,
        cast(Any, StaticProfile(EvidenceSource.HOST_TEST, object())),
        SerialAdapterConfig(
            MSP430_HEALTH_PROFILE_NAME,
            MSP430_HEALTH_PROFILE_VERSION,
        ),
        capability_projector=project_identity_read_only_capabilities,
    )
    adapter.connect()
    with pytest.raises(AdapterDataError, match="invalid capabilities"):
        adapter.get_capabilities()
    adapter.disconnect()


def test_profile_processing_and_measurement_contract_failures_are_wrapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, _, profile = make_msp_adapter(reads=(msp_record(),))
    adapter.connect()
    adapter.get_capabilities()
    monkeypatch.setattr(
        profile,
        "process_record",
        lambda _event, _log: (_ for _ in ()).throw(RuntimeError("profile failed")),
    )
    with pytest.raises(AdapterDataError, match="profile processing"):
        adapter.read_measurement(MSP430_HEALTH_CHANNEL_TEMPERATURE_DS)
    adapter.disconnect()

    bad_type_adapter, _, bad_type_profile = make_msp_adapter(reads=(msp_record(),))
    bad_type_adapter.connect()
    bad_type_adapter.get_capabilities()
    monkeypatch.setattr(
        bad_type_profile,
        "process_record",
        lambda _event, _log: SimpleNamespace(
            accepted=True,
            capabilities=None,
            measurements=("not-a-measurement",),
        ),
    )
    with pytest.raises(AdapterDataError, match="invalid measurements"):
        bad_type_adapter.read_measurement(MSP430_HEALTH_CHANNEL_TEMPERATURE_DS)
    bad_type_adapter.disconnect()

    wrong_source = Measurement(
        "wrong-source",
        "wrong-source-raw",
        NOW,
        MSP430_HEALTH_CHANNEL_TEMPERATURE_DS,
        25,
        MeasurementUnit.CELSIUS,
        MeasurementStatus.VALID,
        EvidenceSource.SYNTHETIC,
    )
    source_adapter, _, source_profile = make_msp_adapter(reads=(msp_record(),))
    source_adapter.connect()
    source_adapter.get_capabilities()
    monkeypatch.setattr(
        source_profile,
        "process_record",
        lambda _event, _log: SimpleNamespace(
            accepted=True,
            capabilities=None,
            measurements=(wrong_source,),
        ),
    )
    with pytest.raises(AdapterDataError, match="changed measurement evidence"):
        source_adapter.read_measurement(MSP430_HEALTH_CHANNEL_TEMPERATURE_DS)
    source_adapter.disconnect()


def test_projector_exception_is_wrapped_as_adapter_data_error() -> None:
    def fail(_capabilities: DeviceCapabilities) -> DeviceCapabilities:
        raise RuntimeError("projection failed")

    adapter, _, _ = make_msp_adapter(projector=fail)
    adapter.connect()

    with pytest.raises(AdapterDataError, match="projection failed"):
        adapter.get_capabilities()

    adapter.disconnect()


def test_session_is_closed_after_adapter_disconnect() -> None:
    backend = MemorySerialBackend()
    settings = SerialConnectionSettings(
        "MEMORY:MSP430",
        MSP430_HEALTH_PROFILE_NAME,
        max_record_bytes=128,
    )
    session = SerialSession(backend, settings)
    profile = Msp430HealthV1SerialProfile(
        evidence_source=EvidenceSource.HOST_TEST
    )
    adapter = SerialAdapter(
        session,
        profile,
        SerialAdapterConfig(
            MSP430_HEALTH_PROFILE_NAME,
            MSP430_HEALTH_PROFILE_VERSION,
        ),
        capability_projector=project_identity_read_only_capabilities,
    )

    adapter.connect()
    adapter.disconnect()

    assert session.state is SerialSessionState.CLOSED
