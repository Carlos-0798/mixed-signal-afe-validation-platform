from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

import pytest

from analog_validation.adapters import AdapterState, DeviceAdapter
from analog_validation.config import (
    ChannelConfig,
    ChannelRole,
    ProfileConfig,
    ValidationConfig,
)
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
    AdapterError,
    AdapterStateError,
    CapabilityError,
    ConfigurationError,
    ValidationError,
)

NOW = datetime(2026, 8, 29, tzinfo=timezone.utc)


def make_capabilities(
    *,
    digital: bool = False,
    output: bool = False,
    generic_command: bool = False,
) -> DeviceCapabilities:
    commands = {DeviceCommand.READ_MEASUREMENT}
    digital_channels: tuple[str, ...] = ()
    if digital:
        commands.add(DeviceCommand.READ_DIGITAL_STATE)
        digital_channels = ("din0",)
    dac_channels: tuple[str, ...] = ()
    output_ranges: tuple[ChannelRange, ...] = ()
    if output:
        commands.update(
            {
                DeviceCommand.SET_ANALOG_STIMULUS,
                DeviceCommand.SAFE_SHUTDOWN,
            }
        )
        dac_channels = ("dac0",)
        output_ranges = (
            ChannelRange(
                "dac0", SafeRange(0.0, 3.3, MeasurementUnit.VOLT)
            ),
        )
    if generic_command:
        commands.add(DeviceCommand.RUN_DEVICE_COMMAND)
    return DeviceCapabilities(
        "fake-1",
        "afe",
        "1",
        adc_channels=("adc0",),
        dac_channels=dac_channels,
        digital_input_channels=digital_channels,
        safe_input_ranges=(
            ChannelRange("adc0", SafeRange(0.0, 3.3, MeasurementUnit.VOLT)),
        ),
        safe_output_ranges=output_ranges,
        supported_commands=frozenset(commands),
        supports_safe_shutdown=output,
    )


def make_config(
    *,
    allow_output: bool = True,
    profile: str = "afe",
    source: EvidenceSource = EvidenceSource.HOST_TEST,
) -> ValidationConfig:
    return ValidationConfig(
        "adapter-test",
        "1",
        ProfileConfig(profile, "1"),
        source,
        (
            ChannelConfig("adc0", ChannelRole.ANALOG_INPUT, MeasurementUnit.VOLT),
            ChannelConfig(
                "dac0",
                ChannelRole.ANALOG_OUTPUT,
                MeasurementUnit.VOLT,
                safe_output_range=SafeRange(0.0, 2.5, MeasurementUnit.VOLT),
            ),
        ),
        allow_output=allow_output,
    )


def make_measurement(
    channel: str = "adc0",
    *,
    unit: MeasurementUnit = MeasurementUnit.VOLT,
    source: EvidenceSource = EvidenceSource.HOST_TEST,
) -> Measurement:
    return Measurement(
        f"record-{channel}",
        f"record-{channel}",
        NOW,
        channel,
        1.25,
        unit,
        MeasurementStatus.VALID,
        source,
    )


class FakeAdapter(DeviceAdapter):
    def __init__(
        self,
        capabilities: DeviceCapabilities | None = None,
        *,
        source: EvidenceSource = EvidenceSource.HOST_TEST,
    ) -> None:
        super().__init__(source)
        self.fake_capabilities: object = capabilities or make_capabilities()
        self.analog_result: object = make_measurement()
        self.digital_result: object = make_measurement(
            "din0", unit=MeasurementUnit.BOOLEAN
        )
        self.failures: dict[str, Exception] = {}
        self.calls: list[object] = []

    def _record(self, action: str) -> None:
        self.calls.append(action)
        failure = self.failures.get(action)
        if failure is not None:
            raise failure

    def _connect(self) -> None:
        self._record("connect")

    def _disconnect(self) -> None:
        self._record("disconnect")

    def _get_capabilities(self) -> DeviceCapabilities:
        self._record("capabilities")
        return cast(DeviceCapabilities, self.fake_capabilities)

    def _read_measurement(self, channel: str) -> Measurement:
        self._record("read_measurement")
        return cast(Measurement, self.analog_result)

    def _read_digital_state(self, channel: str) -> Measurement:
        self._record("read_digital_state")
        return cast(Measurement, self.digital_result)

    def _set_stimulus(
        self, channel: str, value: float, unit: MeasurementUnit
    ) -> None:
        self.calls.append(("set_stimulus", channel, value, unit))
        failure = self.failures.get("set_stimulus")
        if failure is not None:
            raise failure

    def _run_command(self, command: str) -> None:
        self.calls.append(("run_command", command))
        failure = self.failures.get("run_command")
        if failure is not None:
            raise failure

    def _safe_shutdown(self) -> None:
        self._record("safe_shutdown")


class MinimalAdapter(DeviceAdapter):
    def __init__(self, capabilities: DeviceCapabilities) -> None:
        super().__init__(EvidenceSource.HOST_TEST)
        self.fake_capabilities = capabilities

    def _connect(self) -> None:
        pass

    def _disconnect(self) -> None:
        pass

    def _get_capabilities(self) -> DeviceCapabilities:
        return self.fake_capabilities

    def _read_measurement(self, channel: str) -> Measurement:
        return make_measurement(channel)


def connect_and_confirm(adapter: DeviceAdapter) -> DeviceCapabilities:
    adapter.connect()
    return adapter.get_capabilities()


def test_adapter_starts_disconnected_with_explicit_source() -> None:
    adapter = FakeAdapter(source=EvidenceSource.SYNTHETIC)

    assert adapter.state is AdapterState.DISCONNECTED
    assert not adapter.is_connected
    assert adapter.evidence_source is EvidenceSource.SYNTHETIC
    with pytest.raises(AdapterStateError, match="not been confirmed"):
        _ = adapter.capabilities


def test_adapter_rejects_untyped_evidence_source() -> None:
    with pytest.raises(ValidationError, match="EvidenceSource"):
        FakeAdapter(source=cast(EvidenceSource, "SYNTHETIC"))


def test_connect_is_read_only_and_cannot_repeat() -> None:
    adapter = FakeAdapter()

    adapter.connect()

    assert adapter.state is AdapterState.CONNECTED_READ_ONLY
    assert adapter.is_connected
    assert adapter.calls == ["connect"]
    with pytest.raises(AdapterStateError, match="cannot connect"):
        adapter.connect()


@pytest.mark.parametrize(
    ("failure", "error_type"),
    [
        (RuntimeError("port failed"), AdapterConnectionError),
        (AdapterConnectionError("known failure"), AdapterConnectionError),
    ],
)
def test_connect_failure_is_typed_and_resets_state(
    failure: Exception, error_type: type[Exception]
) -> None:
    adapter = FakeAdapter()
    adapter.failures["connect"] = failure

    with pytest.raises(error_type):
        adapter.connect()

    assert adapter.state is AdapterState.DISCONNECTED
    assert not adapter.is_connected


def test_capabilities_require_connection_then_are_cached() -> None:
    adapter = FakeAdapter()
    with pytest.raises(AdapterStateError, match="get capabilities"):
        adapter.get_capabilities()

    adapter.connect()
    first = adapter.get_capabilities()
    second = adapter.get_capabilities()

    assert first is second
    assert adapter.capabilities is first
    assert adapter.state is AdapterState.CAPABILITIES_CONFIRMED
    assert adapter.calls.count("capabilities") == 1


def test_invalid_capability_payload_is_rejected_without_advancing_state() -> None:
    adapter = FakeAdapter()
    adapter.fake_capabilities = object()
    adapter.connect()

    with pytest.raises(AdapterDataError, match="DeviceCapabilities"):
        adapter.get_capabilities()

    assert adapter.state is AdapterState.CONNECTED_READ_ONLY


def test_unexpected_capability_hook_failure_is_adapter_error() -> None:
    adapter = FakeAdapter()
    adapter.failures["capabilities"] = RuntimeError("bad simulator")
    adapter.connect()

    with pytest.raises(AdapterError, match="get capabilities failed"):
        adapter.get_capabilities()


def test_read_measurement_requires_confirmed_capability() -> None:
    adapter = FakeAdapter()
    with pytest.raises(AdapterStateError, match="read measurement"):
        adapter.read_measurement("adc0")
    adapter.connect()
    with pytest.raises(AdapterStateError, match="read measurement"):
        adapter.read_measurement("adc0")


def test_valid_analog_measurement_passes_contract() -> None:
    adapter = FakeAdapter()
    connect_and_confirm(adapter)

    measurement = adapter.read_measurement("adc0")

    assert measurement == make_measurement()
    assert adapter.state is AdapterState.CAPABILITIES_CONFIRMED


@pytest.mark.parametrize("channel", ["", " adc0", cast(Any, 1)])
def test_read_rejects_invalid_channel_identifier(channel: str) -> None:
    adapter = FakeAdapter()
    connect_and_confirm(adapter)

    with pytest.raises(ValidationError, match="channel"):
        adapter.read_measurement(channel)


def test_read_rejects_missing_channel_or_command() -> None:
    adapter = FakeAdapter()
    connect_and_confirm(adapter)
    with pytest.raises(CapabilityError, match="ADC channel"):
        adapter.read_measurement("adc9")

    unsupported = FakeAdapter(
        DeviceCapabilities(
            "empty",
            "afe",
            "1",
            adc_channels=("adc0",),
            safe_input_ranges=(
                ChannelRange(
                    "adc0", SafeRange(0.0, 3.3, MeasurementUnit.VOLT)
                ),
            ),
        )
    )
    connect_and_confirm(unsupported)
    with pytest.raises(CapabilityError, match="READ_MEASUREMENT"):
        unsupported.read_measurement("adc0")


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (object(), "must return a Measurement"),
        (make_measurement("adc9"), "different measurement channel"),
        (
            make_measurement(unit=MeasurementUnit.MILLIVOLT),
            "incompatible measurement unit",
        ),
        (
            make_measurement(source=EvidenceSource.SYNTHETIC),
            "incompatible evidence source",
        ),
    ],
)
def test_read_rejects_adapter_contract_violations(result: object, message: str) -> None:
    adapter = FakeAdapter()
    adapter.analog_result = result
    connect_and_confirm(adapter)

    with pytest.raises(AdapterDataError, match=message):
        adapter.read_measurement("adc0")


def test_read_hook_preserves_domain_error_and_wraps_unexpected_error() -> None:
    adapter = FakeAdapter()
    connect_and_confirm(adapter)
    adapter.failures["read_measurement"] = CapabilityError("expected")
    with pytest.raises(CapabilityError, match="expected"):
        adapter.read_measurement("adc0")

    adapter.failures["read_measurement"] = RuntimeError("unexpected")
    with pytest.raises(AdapterError, match="read measurement failed"):
        adapter.read_measurement("adc0")


def test_digital_read_uses_same_measurement_contract() -> None:
    adapter = FakeAdapter(make_capabilities(digital=True))
    connect_and_confirm(adapter)

    measurement = adapter.read_digital_state("din0")

    assert measurement.channel == "din0"
    assert measurement.unit is MeasurementUnit.BOOLEAN


def test_digital_read_rejects_unavailable_channel_and_default_hook() -> None:
    adapter = FakeAdapter(make_capabilities(digital=True))
    connect_and_confirm(adapter)
    with pytest.raises(CapabilityError, match="digital input channel"):
        adapter.read_digital_state("din9")

    minimal = MinimalAdapter(make_capabilities(digital=True))
    connect_and_confirm(minimal)
    with pytest.raises(CapabilityError, match="does not implement digital"):
        minimal.read_digital_state("din0")


def test_arm_requires_confirmed_capabilities_and_output_permission() -> None:
    adapter = FakeAdapter(make_capabilities(output=True))
    with pytest.raises(AdapterStateError, match="cannot arm"):
        adapter.arm(make_config())
    connect_and_confirm(adapter)

    with pytest.raises(ConfigurationError, match="ValidationConfig"):
        adapter.arm(cast(ValidationConfig, object()))
    with pytest.raises(ConfigurationError, match="allow_output=true"):
        adapter.arm(make_config(allow_output=False))
    with pytest.raises(ConfigurationError, match="profile"):
        adapter.arm(make_config(profile="other"))

    synthetic = FakeAdapter(
        make_capabilities(output=True), source=EvidenceSource.SYNTHETIC
    )
    connect_and_confirm(synthetic)
    with pytest.raises(ConfigurationError, match="evidence source"):
        synthetic.arm(make_config())


def test_arm_and_set_stimulus_follow_safe_state_sequence() -> None:
    adapter = FakeAdapter(make_capabilities(output=True))
    connect_and_confirm(adapter)
    adapter.arm(make_config())

    assert adapter.state is AdapterState.ARMED
    adapter.set_stimulus("dac0", 1.5, MeasurementUnit.VOLT)

    assert adapter.state is AdapterState.RUNNING
    assert (
        "set_stimulus",
        "dac0",
        1.5,
        MeasurementUnit.VOLT,
    ) in adapter.calls
    adapter.set_stimulus("dac0", 2.0, MeasurementUnit.VOLT)


def test_stimulus_is_rejected_before_arm_and_outside_configured_range() -> None:
    adapter = FakeAdapter(make_capabilities(output=True))
    connect_and_confirm(adapter)
    with pytest.raises(AdapterStateError, match="set stimulus"):
        adapter.set_stimulus("dac0", 1.0, MeasurementUnit.VOLT)

    adapter.arm(make_config())
    with pytest.raises(ConfigurationError, match="outside"):
        adapter.set_stimulus("dac0", 3.0, MeasurementUnit.VOLT)
    with pytest.raises(ConfigurationError, match="unit"):
        adapter.set_stimulus("dac0", 1.0, MeasurementUnit.MILLIVOLT)


def test_advertised_output_with_missing_hook_is_rejected() -> None:
    adapter = MinimalAdapter(make_capabilities(output=True))
    connect_and_confirm(adapter)
    adapter.arm(make_config())

    with pytest.raises(CapabilityError, match="does not implement stimulus"):
        adapter.set_stimulus("dac0", 1.0, MeasurementUnit.VOLT)

    assert adapter.state is AdapterState.ARMED


def test_run_command_requires_capability_and_valid_identifier() -> None:
    adapter = FakeAdapter(make_capabilities(generic_command=True))
    connect_and_confirm(adapter)
    adapter.run_command("SELF_TEST")
    assert ("run_command", "SELF_TEST") in adapter.calls

    with pytest.raises(ValidationError, match="command"):
        adapter.run_command(" SELF_TEST")

    unsupported = FakeAdapter()
    connect_and_confirm(unsupported)
    with pytest.raises(CapabilityError, match="RUN_DEVICE_COMMAND"):
        unsupported.run_command("SELF_TEST")


def test_default_run_command_hook_rejects_false_capability_claim() -> None:
    adapter = MinimalAdapter(make_capabilities(generic_command=True))
    connect_and_confirm(adapter)

    with pytest.raises(CapabilityError, match="does not implement device commands"):
        adapter.run_command("SELF_TEST")


def test_safe_shutdown_is_idempotent_and_has_no_hardware_claim() -> None:
    adapter = FakeAdapter(make_capabilities(output=True))
    adapter.safe_shutdown()
    assert adapter.calls == []

    connect_and_confirm(adapter)
    adapter.safe_shutdown()
    adapter.safe_shutdown()

    assert adapter.state is AdapterState.SAFE_SHUTDOWN
    assert adapter.calls.count("safe_shutdown") == 1
    assert adapter.get_capabilities().supports_safe_shutdown


def test_read_only_shutdown_needs_no_output_hook() -> None:
    adapter = MinimalAdapter(make_capabilities())
    adapter.connect()
    adapter.safe_shutdown()
    assert adapter.state is AdapterState.SAFE_SHUTDOWN

    adapter.disconnect()
    connect_and_confirm(adapter)
    adapter.safe_shutdown()
    assert adapter.state is AdapterState.SAFE_SHUTDOWN


def test_safe_shutdown_failure_does_not_claim_safe_state() -> None:
    adapter = FakeAdapter(make_capabilities(output=True))
    connect_and_confirm(adapter)
    adapter.failures["safe_shutdown"] = RuntimeError("relay stuck")

    with pytest.raises(AdapterError, match="safe shutdown failed"):
        adapter.safe_shutdown()

    assert adapter.state is AdapterState.CAPABILITIES_CONFIRMED


def test_default_shutdown_hook_rejects_false_capability_claim() -> None:
    adapter = MinimalAdapter(make_capabilities(output=True))
    connect_and_confirm(adapter)

    with pytest.raises(CapabilityError, match="does not implement safe shutdown"):
        adapter.safe_shutdown()


def test_disconnect_is_idempotent_and_resets_cached_state() -> None:
    adapter = FakeAdapter()
    adapter.disconnect()
    assert adapter.calls == []

    connect_and_confirm(adapter)
    adapter.disconnect()

    assert adapter.state is AdapterState.DISCONNECTED
    assert not adapter.is_connected
    assert adapter.calls[-1] == "disconnect"
    with pytest.raises(AdapterStateError, match="not been confirmed"):
        _ = adapter.capabilities


def test_disconnect_from_running_attempts_shutdown_first() -> None:
    adapter = FakeAdapter(make_capabilities(output=True))
    connect_and_confirm(adapter)
    adapter.arm(make_config())
    adapter.set_stimulus("dac0", 1.0, MeasurementUnit.VOLT)

    adapter.disconnect()

    assert adapter.calls[-2:] == ["safe_shutdown", "disconnect"]
    assert adapter.state is AdapterState.DISCONNECTED


def test_disconnect_still_releases_after_shutdown_failure() -> None:
    adapter = FakeAdapter(make_capabilities(output=True))
    connect_and_confirm(adapter)
    adapter.arm(make_config())
    adapter.failures["safe_shutdown"] = AdapterError("shutdown failed")

    with pytest.raises(AdapterError, match="shutdown failed"):
        adapter.disconnect()

    assert adapter.calls[-1] == "disconnect"
    assert adapter.state is AdapterState.DISCONNECTED


def test_disconnect_failure_is_typed_and_state_is_reset() -> None:
    adapter = FakeAdapter()
    adapter.connect()
    adapter.failures["disconnect"] = RuntimeError("close failed")

    with pytest.raises(AdapterConnectionError, match="disconnect failed"):
        adapter.disconnect()

    assert adapter.state is AdapterState.DISCONNECTED


def test_disconnect_error_takes_priority_when_shutdown_also_fails() -> None:
    adapter = FakeAdapter(make_capabilities(output=True))
    connect_and_confirm(adapter)
    adapter.arm(make_config())
    adapter.failures["safe_shutdown"] = AdapterError("shutdown failed")
    adapter.failures["disconnect"] = AdapterConnectionError("disconnect failed")

    with pytest.raises(AdapterConnectionError, match="disconnect failed"):
        adapter.disconnect()

    assert adapter.state is AdapterState.DISCONNECTED
