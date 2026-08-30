"""Tests for strict JSON configuration I/O and capability matching."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from analog_validation import (
    MAX_CONFIG_BYTES,
    CapabilityError,
    ChannelConfig,
    ChannelRange,
    ChannelRole,
    ConfigurationError,
    DeviceCapabilities,
    DeviceCommand,
    EvidenceSource,
    MeasurementUnit,
    ProfileConfig,
    SafeRange,
    ValidationConfig,
    dump_validation_config_json,
    load_validation_config,
    parse_validation_config_json,
    validate_config_capabilities,
    validation_config_to_dict,
)

EXAMPLE = Path("examples/config/afe-synthetic-readonly.v1.json")


def base_payload() -> dict[str, Any]:
    return {
        "schema_version": "validation-config.v1",
        "config_id": "test-config",
        "config_version": "1.0",
        "profile": {"name": "afe", "version": "1"},
        "evidence_source": "SYNTHETIC",
        "allow_output": False,
        "timeouts_s": {"connect": 5, "command": 2, "settle": 0.1, "test": 60},
        "channels": [
            {
                "name": "adc0",
                "role": "ANALOG_INPUT",
                "unit": "V",
                "enabled": True,
            }
        ],
    }


def parse_payload(payload: object) -> ValidationConfig:
    return parse_validation_config_json(json.dumps(payload))


def output_channel(
    name: str,
    role: ChannelRole,
    unit: MeasurementUnit,
    minimum: float,
    maximum: float,
) -> ChannelConfig:
    return ChannelConfig(
        name,
        role,
        unit,
        safe_output_range=SafeRange(minimum, maximum, unit),
    )


def make_config(
    channels: tuple[ChannelConfig, ...], *, allow_output: bool = False
) -> ValidationConfig:
    return ValidationConfig(
        "test-config",
        "1.0",
        ProfileConfig("afe", "1"),
        EvidenceSource.SYNTHETIC,
        channels,
        allow_output=allow_output,
    )


def make_capabilities(**changes: Any) -> DeviceCapabilities:
    values: dict[str, Any] = {
        "device_id": "sim-1",
        "profile_name": "afe",
        "profile_version": "1",
        "adc_channels": ("adc0",),
        "dac_channels": ("dac0",),
        "pwm_channels": ("pwm0",),
        "digital_input_channels": ("din0",),
        "safe_input_ranges": (
            ChannelRange("adc0", SafeRange(0, 3.3, MeasurementUnit.VOLT)),
        ),
        "safe_output_ranges": (
            ChannelRange("dac0", SafeRange(0, 3.3, MeasurementUnit.VOLT)),
            ChannelRange("pwm0", SafeRange(0, 1, MeasurementUnit.RATIO)),
        ),
        "supported_commands": frozenset(
            {
                DeviceCommand.READ_MEASUREMENT,
                DeviceCommand.READ_DIGITAL_STATE,
                DeviceCommand.SET_ANALOG_STIMULUS,
                DeviceCommand.SET_PWM_STIMULUS,
                DeviceCommand.SAFE_SHUTDOWN,
            }
        ),
        "supports_safe_shutdown": True,
    }
    values.update(changes)
    return DeviceCapabilities(**values)


def test_example_loads_and_dump_round_trip_is_deterministic() -> None:
    config = load_validation_config(EXAMPLE)
    dumped = dump_validation_config_json(config)
    assert config.config_id == "afe-synthetic-readonly"
    assert parse_validation_config_json(dumped) == config
    assert parse_validation_config_json(dumped.encode("utf-8")) == config
    assert dumped.endswith("\n")


def test_output_range_json_round_trip_preserves_explicit_units() -> None:
    payload = base_payload()
    payload["allow_output"] = True
    payload["channels"] = [
        {
            "name": "dac0",
            "role": "ANALOG_OUTPUT",
            "unit": "V",
            "enabled": True,
            "safe_output_range": {"minimum": 0, "maximum": 3.3, "unit": "V"},
        }
    ]
    config = parse_payload(payload)
    serialized = validation_config_to_dict(config)
    assert serialized["channels"] == payload["channels"]
    assert parse_payload(serialized) == config


def test_parser_requires_utf8_string_or_bytes_and_json_object() -> None:
    with pytest.raises(ConfigurationError, match="valid UTF-8"):
        parse_validation_config_json(b"\xff")
    with pytest.raises(ConfigurationError, match="valid UTF-8"):
        parse_validation_config_json("\ud800")
    with pytest.raises(ConfigurationError, match="str or bytes"):
        parse_validation_config_json(cast(Any, 1))
    with pytest.raises(ConfigurationError, match="not valid JSON"):
        parse_validation_config_json("{")
    with pytest.raises(ConfigurationError, match="JSON object"):
        parse_validation_config_json("[]")


@pytest.mark.parametrize(
    "payload",
    [b" " * (MAX_CONFIG_BYTES + 1), " " * (MAX_CONFIG_BYTES + 1)],
    ids=["bytes", "text"],
)
def test_direct_parser_enforces_the_size_limit(payload: str | bytes) -> None:
    with pytest.raises(ConfigurationError, match="size limit"):
        parse_validation_config_json(payload)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_parser_rejects_nonstandard_json_numbers(constant: str) -> None:
    with pytest.raises(ConfigurationError, match="not allowed"):
        parse_validation_config_json(constant)


def test_parser_rejects_duplicate_keys_even_when_values_match() -> None:
    with pytest.raises(ConfigurationError, match="duplicate JSON field"):
        parse_validation_config_json('{"schema_version":"a","schema_version":"a"}')


def test_top_level_missing_and_unknown_fields_are_rejected() -> None:
    payload = base_payload()
    del payload["config_id"]
    with pytest.raises(ConfigurationError, match="missing.*config_id"):
        parse_payload(payload)
    payload = base_payload()
    payload["python"] = "__import__('os')"
    with pytest.raises(ConfigurationError, match="unknown.*python"):
        parse_payload(payload)


@pytest.mark.parametrize("field", ["profile", "timeouts_s"])
def test_nested_objects_are_required(field: str) -> None:
    payload = base_payload()
    payload[field] = []
    with pytest.raises(ConfigurationError, match="JSON object"):
        parse_payload(payload)


def test_nested_missing_and_unknown_fields_are_rejected() -> None:
    payload = base_payload()
    del payload["profile"]["version"]
    with pytest.raises(ConfigurationError, match="missing.*version"):
        parse_payload(payload)
    payload = base_payload()
    payload["timeouts_s"]["minutes"] = 1
    with pytest.raises(ConfigurationError, match="unknown.*minutes"):
        parse_payload(payload)


def test_channels_must_be_array_of_exact_objects() -> None:
    payload = base_payload()
    payload["channels"] = {}
    with pytest.raises(ConfigurationError, match="JSON array"):
        parse_payload(payload)
    payload = base_payload()
    payload["channels"] = [[]]
    with pytest.raises(ConfigurationError, match="JSON object"):
        parse_payload(payload)
    payload = base_payload()
    del payload["channels"][0]["enabled"]
    with pytest.raises(ConfigurationError, match="missing.*enabled"):
        parse_payload(payload)
    payload = base_payload()
    payload["channels"][0]["gpio"] = 1
    with pytest.raises(ConfigurationError, match="unknown.*gpio"):
        parse_payload(payload)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("role", 1, "channel role must be a string"),
        ("role", "ADC", "unsupported channel role"),
        ("unit", "volts", "unsupported measurement unit"),
    ],
)
def test_channel_enums_are_strict(field: str, value: object, message: str) -> None:
    payload = base_payload()
    payload["channels"][0][field] = value
    with pytest.raises(ConfigurationError, match=message):
        parse_payload(payload)


def test_evidence_source_is_a_controlled_string() -> None:
    payload = base_payload()
    payload["evidence_source"] = 1
    with pytest.raises(ConfigurationError, match="evidence source must be a string"):
        parse_payload(payload)
    payload["evidence_source"] = "PHYSICAL"
    with pytest.raises(ConfigurationError, match="unsupported evidence source"):
        parse_payload(payload)


def test_safe_range_object_and_fields_are_strict() -> None:
    payload = base_payload()
    channel = payload["channels"][0]
    channel["role"] = "ANALOG_OUTPUT"
    channel["safe_output_range"] = []
    with pytest.raises(ConfigurationError, match="JSON object"):
        parse_payload(payload)

    channel["safe_output_range"] = {"minimum": 0, "maximum": 1}
    with pytest.raises(ConfigurationError, match="missing.*unit"):
        parse_payload(payload)
    channel["safe_output_range"] = {
        "minimum": 0,
        "maximum": 1,
        "unit": "V",
        "extra": 1,
    }
    with pytest.raises(ConfigurationError, match="unknown.*extra"):
        parse_payload(payload)
    channel["safe_output_range"] = {"minimum": 1, "maximum": 1, "unit": "V"}
    with pytest.raises(ConfigurationError, match="invalid safe_output_range"):
        parse_payload(payload)


def test_loader_checks_path_extension_access_size_and_read_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ConfigurationError, match="path-like"):
        load_validation_config(cast(Any, object()))
    with pytest.raises(ConfigurationError, match=".json"):
        load_validation_config(tmp_path / "config.txt")
    with pytest.raises(ConfigurationError, match="cannot access"):
        load_validation_config(tmp_path / "missing.json")

    large = tmp_path / "large.json"
    large.write_bytes(b" " * (MAX_CONFIG_BYTES + 1))
    with pytest.raises(ConfigurationError, match="size limit"):
        load_validation_config(large)

    path = tmp_path / "unreadable.json"
    path.write_text("{}", encoding="utf-8")

    def fail_read(self: Path) -> bytes:
        raise OSError("simulated read failure")

    monkeypatch.setattr(Path, "read_bytes", fail_read)
    with pytest.raises(ConfigurationError, match="cannot read"):
        load_validation_config(path)


def test_serializer_validates_config_and_indent_types() -> None:
    config = parse_payload(base_payload())
    with pytest.raises(ConfigurationError, match="ValidationConfig"):
        validation_config_to_dict(cast(Any, object()))
    with pytest.raises(ConfigurationError, match="non-negative integer"):
        dump_validation_config_json(config, indent=-1)
    with pytest.raises(ConfigurationError, match="non-negative integer"):
        dump_validation_config_json(config, indent=cast(int, True))
    assert dump_validation_config_json(config, indent=0).startswith("{")


def test_capability_validation_accepts_all_roles_and_narrower_output_ranges() -> None:
    config = make_config(
        (
            ChannelConfig("adc0", ChannelRole.ANALOG_INPUT, MeasurementUnit.VOLT),
            ChannelConfig("din0", ChannelRole.DIGITAL_INPUT, MeasurementUnit.BOOLEAN),
            output_channel("dac0", ChannelRole.ANALOG_OUTPUT, MeasurementUnit.VOLT, 0.1, 3.2),
            output_channel("pwm0", ChannelRole.PWM_OUTPUT, MeasurementUnit.RATIO, 0.1, 0.9),
        ),
        allow_output=True,
    )
    validate_config_capabilities(config, make_capabilities())


def test_disabled_channels_are_not_required_from_device() -> None:
    config = make_config(
        (
            ChannelConfig("adc0", ChannelRole.ANALOG_INPUT, MeasurementUnit.VOLT),
            ChannelConfig(
                "missing",
                ChannelRole.ANALOG_INPUT,
                MeasurementUnit.VOLT,
                enabled=False,
            ),
        )
    )
    validate_config_capabilities(config, make_capabilities())


def test_capability_validation_requires_typed_inputs_and_matching_profile() -> None:
    config = make_config(
        (ChannelConfig("adc0", ChannelRole.ANALOG_INPUT, MeasurementUnit.VOLT),)
    )
    with pytest.raises(ConfigurationError, match="ValidationConfig"):
        validate_config_capabilities(cast(Any, object()), make_capabilities())
    with pytest.raises(CapabilityError, match="DeviceCapabilities"):
        validate_config_capabilities(config, cast(Any, object()))
    with pytest.raises(ConfigurationError, match="profile"):
        validate_config_capabilities(
            ValidationConfig(
                "c",
                "1",
                ProfileConfig("other", "1"),
                EvidenceSource.SYNTHETIC,
                config.channels,
            ),
            make_capabilities(),
        )


@pytest.mark.parametrize(
    "channel",
    [
        ChannelConfig("missing", ChannelRole.ANALOG_INPUT, MeasurementUnit.VOLT),
        ChannelConfig("missing", ChannelRole.DIGITAL_INPUT, MeasurementUnit.BOOLEAN),
        output_channel("missing", ChannelRole.ANALOG_OUTPUT, MeasurementUnit.VOLT, 0, 1),
        output_channel("missing", ChannelRole.PWM_OUTPUT, MeasurementUnit.RATIO, 0, 1),
    ],
)
def test_missing_device_channels_are_capability_errors(channel: ChannelConfig) -> None:
    with pytest.raises(CapabilityError, match="not available"):
        validate_config_capabilities(make_config((channel,)), make_capabilities())


def test_input_and_output_units_must_match_device_declarations() -> None:
    input_config = make_config(
        (ChannelConfig("adc0", ChannelRole.ANALOG_INPUT, MeasurementUnit.MILLIVOLT),)
    )
    with pytest.raises(ConfigurationError, match="does not match"):
        validate_config_capabilities(input_config, make_capabilities())

    output_config = make_config(
        (
            output_channel(
                "dac0", ChannelRole.ANALOG_OUTPUT, MeasurementUnit.MILLIVOLT, 0, 1000
            ),
        )
    )
    with pytest.raises(ConfigurationError, match="does not match"):
        validate_config_capabilities(output_config, make_capabilities())


def test_configured_output_range_cannot_exceed_device_safe_range() -> None:
    config = make_config(
        (output_channel("dac0", ChannelRole.ANALOG_OUTPUT, MeasurementUnit.VOLT, 0, 3.4),)
    )
    with pytest.raises(ConfigurationError, match="exceeds"):
        validate_config_capabilities(config, make_capabilities())


def test_enabled_output_requires_command_and_safe_shutdown_when_allowed() -> None:
    config = make_config(
        (output_channel("dac0", ChannelRole.ANALOG_OUTPUT, MeasurementUnit.VOLT, 0, 3.3),),
        allow_output=True,
    )
    no_command = make_capabilities(
        supported_commands=frozenset(
            {
                DeviceCommand.READ_MEASUREMENT,
                DeviceCommand.READ_DIGITAL_STATE,
                DeviceCommand.SET_PWM_STIMULUS,
            }
        ),
        supports_safe_shutdown=False,
    )
    with pytest.raises(CapabilityError, match="does not support"):
        validate_config_capabilities(config, no_command)

    no_shutdown = make_capabilities(
        supported_commands=frozenset(
            {
                DeviceCommand.READ_MEASUREMENT,
                DeviceCommand.READ_DIGITAL_STATE,
                DeviceCommand.SET_ANALOG_STIMULUS,
                DeviceCommand.SET_PWM_STIMULUS,
            }
        ),
        supports_safe_shutdown=False,
    )
    with pytest.raises(CapabilityError, match="SAFE_SHUTDOWN"):
        validate_config_capabilities(config, no_shutdown)


def test_read_only_config_does_not_require_output_command_or_shutdown() -> None:
    config = make_config(
        (output_channel("dac0", ChannelRole.ANALOG_OUTPUT, MeasurementUnit.VOLT, 0, 3.3),)
    )
    capabilities = make_capabilities(
        supported_commands=frozenset(
            {DeviceCommand.READ_MEASUREMENT, DeviceCommand.READ_DIGITAL_STATE}
        ),
        supports_safe_shutdown=False,
    )
    validate_config_capabilities(config, capabilities)
