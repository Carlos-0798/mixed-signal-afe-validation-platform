"""Tests for immutable configuration models and local output gates."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from analog_validation import (
    VALIDATION_CONFIG_SCHEMA_VERSION,
    ChannelConfig,
    ChannelRole,
    ConfigurationError,
    EvidenceSource,
    MeasurementUnit,
    ProfileConfig,
    SafeRange,
    TimeoutConfig,
    ValidationConfig,
)


def analog_input(name: str = "adc0", *, enabled: bool = True) -> ChannelConfig:
    return ChannelConfig(
        name=name,
        role=ChannelRole.ANALOG_INPUT,
        unit=MeasurementUnit.VOLT,
        enabled=enabled,
    )


def analog_output(name: str = "dac0", *, enabled: bool = True) -> ChannelConfig:
    return ChannelConfig(
        name=name,
        role=ChannelRole.ANALOG_OUTPUT,
        unit=MeasurementUnit.VOLT,
        enabled=enabled,
        safe_output_range=SafeRange(0, 3.3, MeasurementUnit.VOLT),
    )


def make_config(**changes: Any) -> ValidationConfig:
    values: dict[str, Any] = {
        "config_id": "synthetic-readonly",
        "config_version": "1.0",
        "profile": ProfileConfig("afe", "1"),
        "evidence_source": EvidenceSource.SYNTHETIC,
        "channels": (analog_input(),),
    }
    values.update(changes)
    return ValidationConfig(**values)


def test_channel_role_values_and_output_classification_are_stable() -> None:
    assert [role.value for role in ChannelRole] == [
        "ANALOG_INPUT",
        "ANALOG_OUTPUT",
        "PWM_OUTPUT",
        "DIGITAL_INPUT",
    ]
    assert not ChannelRole.ANALOG_INPUT.is_output
    assert not ChannelRole.DIGITAL_INPUT.is_output
    assert ChannelRole.ANALOG_OUTPUT.is_output
    assert ChannelRole.PWM_OUTPUT.is_output


def test_profile_config_is_validated_and_immutable() -> None:
    profile = ProfileConfig("afe", "1")
    assert profile.name == "afe"
    with pytest.raises(FrozenInstanceError):
        profile.name = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("name", "version", "message"),
    [("", "1", "profile name"), (" afe", "1", "whitespace"), ("afe", "", "version")],
)
def test_profile_identifiers_are_nonempty_and_trimmed(
    name: str, version: str, message: str
) -> None:
    with pytest.raises(ConfigurationError, match=message):
        ProfileConfig(name, version)


def test_timeout_config_normalizes_numbers_and_allows_zero_settle() -> None:
    timeouts = TimeoutConfig(connect_s=5, command_s=2, settle_s=0, test_s=2)
    assert timeouts == TimeoutConfig(5.0, 2.0, 0.0, 2.0)


@pytest.mark.parametrize("field", ["connect_s", "command_s", "settle_s", "test_s"])
@pytest.mark.parametrize("value", [True, "1"])
def test_timeout_values_must_be_numeric(field: str, value: object) -> None:
    with pytest.raises(ConfigurationError, match=f"{field} must be numeric"):
        TimeoutConfig(**{field: cast(float, value)})


@pytest.mark.parametrize("field", ["connect_s", "command_s", "settle_s", "test_s"])
@pytest.mark.parametrize("value", [math.inf, math.nan])
def test_timeout_values_must_be_finite(field: str, value: float) -> None:
    with pytest.raises(ConfigurationError, match=f"{field} must be finite"):
        TimeoutConfig(**{field: value})


@pytest.mark.parametrize(
    "changes",
    [
        {"connect_s": 0},
        {"command_s": 0},
        {"test_s": 0},
        {"settle_s": -0.1},
        {"command_s": 2, "settle_s": 1, "test_s": 2.9},
    ],
)
def test_timeout_relationships_are_safe(changes: dict[str, float]) -> None:
    with pytest.raises(ConfigurationError):
        TimeoutConfig(**changes)


def test_all_channel_roles_accept_their_expected_units_and_ranges() -> None:
    pwm = ChannelConfig(
        "pwm0",
        ChannelRole.PWM_OUTPUT,
        MeasurementUnit.RATIO,
        safe_output_range=SafeRange(0, 1, MeasurementUnit.RATIO),
    )
    digital = ChannelConfig(
        "din0", ChannelRole.DIGITAL_INPUT, MeasurementUnit.BOOLEAN
    )
    assert analog_input().is_output is False
    assert analog_output().is_output is True
    assert pwm.is_output
    assert not digital.is_output


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"name": ""}, "channel name"),
        ({"name": " adc0"}, "whitespace"),
        ({"role": "ANALOG_INPUT"}, "ChannelRole"),
        ({"unit": "V"}, "MeasurementUnit"),
        ({"enabled": 1}, "boolean"),
    ],
)
def test_channel_identity_types_and_flag_are_validated(
    changes: dict[str, object], message: str
) -> None:
    values: dict[str, object] = {
        "name": "adc0",
        "role": ChannelRole.ANALOG_INPUT,
        "unit": MeasurementUnit.VOLT,
    }
    values.update(changes)
    with pytest.raises(ConfigurationError, match=message):
        ChannelConfig(**cast(Any, values))


def test_output_range_rules_prevent_ambiguous_or_mismatched_units() -> None:
    with pytest.raises(ConfigurationError, match="require"):
        ChannelConfig("dac0", ChannelRole.ANALOG_OUTPUT, MeasurementUnit.VOLT)
    with pytest.raises(ConfigurationError, match="input channels"):
        ChannelConfig(
            "adc0",
            ChannelRole.ANALOG_INPUT,
            MeasurementUnit.VOLT,
            safe_output_range=SafeRange(0, 1, MeasurementUnit.VOLT),
        )
    with pytest.raises(ConfigurationError, match="must match"):
        ChannelConfig(
            "dac0",
            ChannelRole.ANALOG_OUTPUT,
            MeasurementUnit.VOLT,
            safe_output_range=SafeRange(0, 1000, MeasurementUnit.MILLIVOLT),
        )


def test_digital_and_pwm_channels_use_unambiguous_units() -> None:
    with pytest.raises(ConfigurationError, match="bool"):
        ChannelConfig("din0", ChannelRole.DIGITAL_INPUT, MeasurementUnit.UNITLESS)
    with pytest.raises(ConfigurationError, match="ratio"):
        ChannelConfig(
            "pwm0",
            ChannelRole.PWM_OUTPUT,
            MeasurementUnit.VOLT,
            safe_output_range=SafeRange(0, 1, MeasurementUnit.VOLT),
        )


def test_validation_config_freezes_channels_and_exposes_schema() -> None:
    channels = [analog_input()]
    config = make_config(channels=channels)
    channels.clear()
    assert config.channels == (analog_input(),)
    assert config.schema_version == VALIDATION_CONFIG_SCHEMA_VERSION
    assert config.get_channel("adc0") == analog_input()
    with pytest.raises(FrozenInstanceError):
        config.config_id = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"config_id": ""}, "config_id"),
        ({"config_version": " 1"}, "whitespace"),
        ({"profile": None}, "ProfileConfig"),
        ({"evidence_source": "SYNTHETIC"}, "EvidenceSource"),
        ({"timeouts": None}, "TimeoutConfig"),
        ({"allow_output": 1}, "boolean"),
        ({"schema_version": "validation-config.v2"}, "schema version"),
    ],
)
def test_validation_config_rejects_invalid_top_level_values(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ConfigurationError, match=message):
        make_config(**changes)


def test_channel_collection_must_be_iterable_typed_unique_and_enabled() -> None:
    with pytest.raises(ConfigurationError, match="iterable"):
        make_config(channels=cast(Any, None))
    with pytest.raises(ConfigurationError, match="iterable"):
        make_config(channels=cast(Any, "adc0"))
    with pytest.raises(ConfigurationError, match="ChannelConfig"):
        make_config(channels=(object(),))
    with pytest.raises(ConfigurationError, match="duplicate"):
        make_config(channels=(analog_input(), analog_input()))
    with pytest.raises(ConfigurationError, match="enabled"):
        make_config(channels=(analog_input(enabled=False),))


def test_allow_output_requires_an_enabled_output_channel() -> None:
    with pytest.raises(ConfigurationError, match="enabled output"):
        make_config(allow_output=True)
    with pytest.raises(ConfigurationError, match="enabled output"):
        make_config(channels=(analog_output(enabled=False), analog_input()), allow_output=True)


def test_get_channel_rejects_bad_or_unknown_names() -> None:
    config = make_config()
    with pytest.raises(ConfigurationError, match="channel name"):
        config.get_channel("")
    with pytest.raises(ConfigurationError, match="not configured"):
        config.get_channel("adc1")


def test_output_request_accepts_inclusive_bounds() -> None:
    config = make_config(channels=(analog_output(),), allow_output=True)
    assert config.require_output("dac0", 0, MeasurementUnit.VOLT).name == "dac0"
    assert config.require_output("dac0", 3.3, MeasurementUnit.VOLT).name == "dac0"


def test_output_request_requires_every_configuration_gate() -> None:
    with pytest.raises(ConfigurationError, match="disabled by"):
        make_config(channels=(analog_output(),)).require_output(
            "dac0", 1, MeasurementUnit.VOLT
        )

    disabled = make_config(
        channels=(analog_output(enabled=False), analog_output("dac1")),
        allow_output=True,
    )
    with pytest.raises(ConfigurationError, match="is disabled"):
        disabled.require_output("dac0", 1, MeasurementUnit.VOLT)

    not_output = make_config(channels=(analog_input(), analog_output()), allow_output=True)
    with pytest.raises(ConfigurationError, match="not an output"):
        not_output.require_output("adc0", 1, MeasurementUnit.VOLT)
    with pytest.raises(ConfigurationError, match="supported MeasurementUnit"):
        not_output.require_output("dac0", 1, cast(MeasurementUnit, "V"))
    with pytest.raises(ConfigurationError, match="does not match"):
        not_output.require_output("dac0", 1, MeasurementUnit.MILLIVOLT)
    with pytest.raises(ConfigurationError, match="finite and numeric"):
        not_output.require_output("dac0", math.nan, MeasurementUnit.VOLT)
    with pytest.raises(ConfigurationError, match="outside"):
        not_output.require_output("dac0", 3.31, MeasurementUnit.VOLT)
