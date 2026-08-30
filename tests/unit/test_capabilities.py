"""Tests for explicit controller-neutral capability declarations."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from analog_validation import (
    CAPABILITY_SCHEMA_VERSION,
    CapabilityError,
    ChannelRange,
    ConfigurationError,
    DeviceCapabilities,
    DeviceCommand,
    MeasurementUnit,
    SafeRange,
    ValidationError,
)


def make_read_only_capabilities(**changes: Any) -> DeviceCapabilities:
    values: dict[str, Any] = {
        "device_id": "simulator-001",
        "profile_name": "afe-simulator",
        "profile_version": "1.0",
        "adc_channels": ("adc0",),
        "safe_input_ranges": (
            ChannelRange("adc0", SafeRange(0, 3.3, MeasurementUnit.VOLT)),
        ),
        "supported_commands": frozenset({DeviceCommand.READ_MEASUREMENT}),
    }
    values.update(changes)
    return DeviceCapabilities(**values)


def make_output_capabilities(**changes: Any) -> DeviceCapabilities:
    values: dict[str, Any] = {
        "device_id": "simulator-001",
        "profile_name": "afe-simulator",
        "profile_version": "1.0",
        "dac_channels": ("dac0",),
        "pwm_channels": ("pwm0",),
        "safe_output_ranges": (
            ChannelRange("dac0", SafeRange(0, 3.3, MeasurementUnit.VOLT)),
            ChannelRange("pwm0", SafeRange(0, 1, MeasurementUnit.RATIO)),
        ),
        "supported_commands": frozenset(
            {
                DeviceCommand.SET_ANALOG_STIMULUS,
                DeviceCommand.SET_PWM_STIMULUS,
                DeviceCommand.SAFE_SHUTDOWN,
            }
        ),
        "supports_safe_shutdown": True,
    }
    values.update(changes)
    return DeviceCapabilities(**values)


def test_device_command_values_are_stable() -> None:
    assert [command.value for command in DeviceCommand] == [
        "READ_MEASUREMENT",
        "READ_DIGITAL_STATE",
        "SET_ANALOG_STIMULUS",
        "SET_PWM_STIMULUS",
        "RUN_DEVICE_COMMAND",
        "SAFE_SHUTDOWN",
    ]


def test_safe_range_is_inclusive_finite_and_immutable() -> None:
    safe_range = SafeRange(0, 3.3, MeasurementUnit.VOLT)

    assert safe_range.minimum == 0.0
    assert safe_range.maximum == 3.3
    assert safe_range.contains(0)
    assert safe_range.contains(3.3)
    assert not safe_range.contains(3.31)
    with pytest.raises(FrozenInstanceError):
        safe_range.maximum = 5.0  # type: ignore[misc]


@pytest.mark.parametrize("value", [True, "0", object()])
def test_safe_range_limits_must_be_numeric(value: object) -> None:
    with pytest.raises(ValidationError, match="minimum must be numeric"):
        SafeRange(cast(float, value), 3.3, MeasurementUnit.VOLT)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_safe_range_limits_must_be_finite(value: float) -> None:
    with pytest.raises(ValidationError, match="maximum must be finite"):
        SafeRange(0, value, MeasurementUnit.VOLT)


@pytest.mark.parametrize(("minimum", "maximum"), [(1, 1), (2, 1)])
def test_safe_range_must_have_increasing_limits(
    minimum: float, maximum: float
) -> None:
    with pytest.raises(ValidationError, match="less than"):
        SafeRange(minimum, maximum, MeasurementUnit.VOLT)


def test_safe_range_rejects_unknown_unit_and_invalid_probe() -> None:
    with pytest.raises(ValidationError, match="MeasurementUnit"):
        SafeRange(0, 1, cast(MeasurementUnit, "VOLT"))

    with pytest.raises(ValidationError, match="value must be numeric"):
        SafeRange(0, 1, MeasurementUnit.VOLT).contains(cast(float, True))


def test_channel_range_requires_identifier_and_safe_range() -> None:
    with pytest.raises(ValidationError, match="channel"):
        ChannelRange(" adc0", SafeRange(0, 1, MeasurementUnit.VOLT))
    with pytest.raises(ValidationError, match="SafeRange"):
        ChannelRange("adc0", cast(SafeRange, None))


def test_read_only_capability_is_explicit_and_immutable() -> None:
    channels = ["adc0"]
    commands = {DeviceCommand.READ_MEASUREMENT}
    capabilities = make_read_only_capabilities(
        adc_channels=channels,
        supported_commands=commands,
    )
    channels.clear()
    commands.clear()

    assert capabilities.adc_channels == ("adc0",)
    assert capabilities.supported_commands == frozenset(
        {DeviceCommand.READ_MEASUREMENT}
    )
    assert capabilities.schema_version == CAPABILITY_SCHEMA_VERSION
    assert capabilities.is_read_only
    assert not capabilities.automated_output_allowed
    assert capabilities.supports(DeviceCommand.READ_MEASUREMENT)
    capabilities.require_command(DeviceCommand.READ_MEASUREMENT)
    assert capabilities.get_input_range("adc0").maximum == 3.3
    with pytest.raises(FrozenInstanceError):
        capabilities.device_id = "changed"  # type: ignore[misc]


def test_output_capability_allows_checked_automatic_stimulus() -> None:
    capabilities = make_output_capabilities()

    assert not capabilities.is_read_only
    assert capabilities.automated_output_allowed
    assert capabilities.get_output_range("dac0").unit is MeasurementUnit.VOLT
    capabilities.require_automated_output(
        DeviceCommand.SET_ANALOG_STIMULUS,
        "dac0",
        1.65,
        MeasurementUnit.VOLT,
    )
    capabilities.require_automated_output(
        DeviceCommand.SET_PWM_STIMULUS,
        "pwm0",
        0.5,
        MeasurementUnit.RATIO,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("device_id", ""),
        ("profile_name", " profile"),
        ("profile_version", "1.0 "),
    ],
)
def test_capability_identifiers_must_be_nonempty_and_trimmed(
    field: str, value: str
) -> None:
    with pytest.raises(ValidationError, match=field):
        make_read_only_capabilities(**{field: value})


def test_channel_collections_must_be_iterable_unique_identifiers() -> None:
    with pytest.raises(ValidationError, match="iterable"):
        DeviceCapabilities("d", "p", "1", adc_channels=cast(Any, None))
    with pytest.raises(ValidationError, match="iterable"):
        DeviceCapabilities("d", "p", "1", adc_channels=cast(Any, "adc0"))
    with pytest.raises(ValidationError, match="adc_channels"):
        DeviceCapabilities("d", "p", "1", adc_channels=("",))
    with pytest.raises(ValidationError, match="duplicates"):
        DeviceCapabilities("d", "p", "1", adc_channels=("adc0", "adc0"))


def test_range_collections_must_be_typed_unique_and_match_channels() -> None:
    safe_range = SafeRange(0, 3.3, MeasurementUnit.VOLT)
    channel_range = ChannelRange("adc0", safe_range)
    with pytest.raises(ValidationError, match="iterable"):
        DeviceCapabilities("d", "p", "1", safe_input_ranges=cast(Any, None))
    with pytest.raises(ValidationError, match="ChannelRange"):
        DeviceCapabilities(
            "d",
            "p",
            "1",
            safe_input_ranges=cast(tuple[ChannelRange, ...], (safe_range,)),
        )
    with pytest.raises(ValidationError, match="duplicate channels"):
        DeviceCapabilities(
            "d", "p", "1", safe_input_ranges=(channel_range, channel_range)
        )
    with pytest.raises(ValidationError, match="ADC channels"):
        DeviceCapabilities("d", "p", "1", safe_input_ranges=(channel_range,))
    with pytest.raises(ValidationError, match="DAC/PWM channels"):
        DeviceCapabilities("d", "p", "1", dac_channels=("dac0",))


def test_commands_must_be_typed_iterable_and_consistent() -> None:
    with pytest.raises(ValidationError, match="iterable"):
        DeviceCapabilities("d", "p", "1", supported_commands=cast(Any, None))
    with pytest.raises(ValidationError, match="iterable"):
        DeviceCapabilities("d", "p", "1", supported_commands=cast(Any, "READ"))
    with pytest.raises(ValidationError, match="unknown command"):
        DeviceCapabilities(
            "d", "p", "1", supported_commands=cast(Any, {"READ_MEASUREMENT"})
        )


@pytest.mark.parametrize(
    "command",
    [
        DeviceCommand.READ_MEASUREMENT,
        DeviceCommand.READ_DIGITAL_STATE,
        DeviceCommand.SET_ANALOG_STIMULUS,
        DeviceCommand.SET_PWM_STIMULUS,
    ],
)
def test_commands_requiring_channels_cannot_claim_missing_hardware(
    command: DeviceCommand,
) -> None:
    with pytest.raises(ValidationError, match="requires a declared channel"):
        DeviceCapabilities("d", "p", "1", supported_commands=frozenset({command}))


@pytest.mark.parametrize(
    ("supports_safe_shutdown", "commands"),
    [
        (True, frozenset()),
        (False, frozenset({DeviceCommand.SAFE_SHUTDOWN})),
    ],
)
def test_safe_shutdown_flag_and_command_must_agree(
    supports_safe_shutdown: bool,
    commands: frozenset[DeviceCommand],
) -> None:
    with pytest.raises(ValidationError, match="must agree"):
        DeviceCapabilities(
            "d",
            "p",
            "1",
            supported_commands=commands,
            supports_safe_shutdown=supports_safe_shutdown,
        )


def test_capability_rejects_non_boolean_flag_and_unknown_schema() -> None:
    with pytest.raises(ValidationError, match="boolean"):
        DeviceCapabilities("d", "p", "1", supports_safe_shutdown=cast(bool, 1))
    with pytest.raises(ValidationError, match="schema version"):
        DeviceCapabilities("d", "p", "1", schema_version="capabilities.v2")


def test_unsupported_commands_and_ranges_raise_capability_errors() -> None:
    capabilities = make_read_only_capabilities()
    with pytest.raises(ValidationError, match="DeviceCommand"):
        capabilities.supports(cast(DeviceCommand, "READ_MEASUREMENT"))
    with pytest.raises(CapabilityError, match="does not support"):
        capabilities.require_command(DeviceCommand.SET_ANALOG_STIMULUS)
    with pytest.raises(CapabilityError, match="no safe input"):
        capabilities.get_input_range("adc1")
    with pytest.raises(CapabilityError, match="no safe output"):
        capabilities.get_output_range("dac0")
    with pytest.raises(ValidationError, match="channel"):
        capabilities.get_input_range("")


def test_automatic_output_requires_correct_command_channel_and_shutdown() -> None:
    capabilities = make_output_capabilities()
    with pytest.raises(CapabilityError, match="not an output"):
        capabilities.require_automated_output(
            DeviceCommand.READ_MEASUREMENT, "dac0", 1, MeasurementUnit.VOLT
        )
    with pytest.raises(CapabilityError, match="does not support"):
        make_read_only_capabilities().require_automated_output(
            DeviceCommand.SET_ANALOG_STIMULUS,
            "dac0",
            1,
            MeasurementUnit.VOLT,
        )
    with pytest.raises(CapabilityError, match="not declared"):
        capabilities.require_automated_output(
            DeviceCommand.SET_ANALOG_STIMULUS,
            "dac1",
            1,
            MeasurementUnit.VOLT,
        )

    no_shutdown = make_output_capabilities(
        supported_commands=frozenset({DeviceCommand.SET_ANALOG_STIMULUS}),
        supports_safe_shutdown=False,
    )
    with pytest.raises(CapabilityError, match="SAFE_SHUTDOWN"):
        no_shutdown.require_automated_output(
            DeviceCommand.SET_ANALOG_STIMULUS,
            "dac0",
            1,
            MeasurementUnit.VOLT,
        )


def test_automatic_output_rejects_bad_unit_value_and_range() -> None:
    capabilities = make_output_capabilities()
    with pytest.raises(ConfigurationError, match="supported MeasurementUnit"):
        capabilities.require_automated_output(
            DeviceCommand.SET_ANALOG_STIMULUS,
            "dac0",
            1,
            cast(MeasurementUnit, "V"),
        )
    with pytest.raises(ConfigurationError, match="does not match"):
        capabilities.require_automated_output(
            DeviceCommand.SET_ANALOG_STIMULUS,
            "dac0",
            1,
            MeasurementUnit.MILLIVOLT,
        )
    with pytest.raises(ConfigurationError, match="finite and numeric"):
        capabilities.require_automated_output(
            DeviceCommand.SET_ANALOG_STIMULUS,
            "dac0",
            math.nan,
            MeasurementUnit.VOLT,
        )
    with pytest.raises(ConfigurationError, match="outside"):
        capabilities.require_automated_output(
            DeviceCommand.SET_ANALOG_STIMULUS,
            "dac0",
            3.31,
            MeasurementUnit.VOLT,
        )
