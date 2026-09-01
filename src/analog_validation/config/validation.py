"""Strict JSON I/O and device-capability checks for product configuration."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, NoReturn, cast

from analog_validation.domain import (
    DeviceCapabilities,
    DeviceCommand,
    EvidenceSource,
    MeasurementUnit,
    SafeRange,
)
from analog_validation.errors import (
    CapabilityError,
    ConfigurationError,
    ValidationError,
)

from .models import (
    ChannelConfig,
    ChannelRole,
    ProfileConfig,
    TimeoutConfig,
    ValidationConfig,
)

MAX_CONFIG_BYTES = 1_048_576


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ConfigurationError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> NoReturn:
    raise ConfigurationError(f"non-standard JSON number is not allowed: {value}")


def _object(value: object, context: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{context} must be a JSON object")
    return cast(Mapping[str, Any], value)


def _exact_fields(
    value: Mapping[str, Any],
    *,
    context: str,
    required: set[str],
    optional: set[str] | None = None,
) -> None:
    optional = optional or set()
    actual = set(value)
    missing = required - actual
    unknown = actual - required - optional
    if missing:
        raise ConfigurationError(
            f"{context} is missing field(s): {', '.join(sorted(missing))}"
        )
    if unknown:
        raise ConfigurationError(
            f"{context} has unknown field(s): {', '.join(sorted(unknown))}"
        )


def _enum_value(enum_type: type[Any], value: object, context: str) -> Any:
    if not isinstance(value, str):
        raise ConfigurationError(f"{context} must be a string")
    try:
        return enum_type(value)
    except ValueError as error:
        raise ConfigurationError(f"unsupported {context}: {value}") from error


def _parse_safe_range(value: object) -> SafeRange:
    fields = _object(value, "safe_output_range")
    _exact_fields(
        fields,
        context="safe_output_range",
        required={"minimum", "maximum", "unit"},
    )
    unit = cast(
        MeasurementUnit,
        _enum_value(MeasurementUnit, fields["unit"], "measurement unit"),
    )
    try:
        return SafeRange(fields["minimum"], fields["maximum"], unit)
    except ValidationError as error:
        raise ConfigurationError(f"invalid safe_output_range: {error}") from error


def _parse_channel(value: object) -> ChannelConfig:
    fields = _object(value, "channel")
    _exact_fields(
        fields,
        context="channel",
        required={"name", "role", "unit", "enabled"},
        optional={"safe_output_range"},
    )
    role = cast(ChannelRole, _enum_value(ChannelRole, fields["role"], "channel role"))
    unit = cast(
        MeasurementUnit,
        _enum_value(MeasurementUnit, fields["unit"], "measurement unit"),
    )
    safe_range = (
        _parse_safe_range(fields["safe_output_range"])
        if "safe_output_range" in fields
        else None
    )
    return ChannelConfig(
        name=fields["name"],
        role=role,
        unit=unit,
        enabled=fields["enabled"],
        safe_output_range=safe_range,
    )


def _parse_validation_config(value: object) -> ValidationConfig:
    fields = _object(value, "configuration")
    _exact_fields(
        fields,
        context="configuration",
        required={
            "schema_version",
            "config_id",
            "config_version",
            "profile",
            "evidence_source",
            "allow_output",
            "timeouts_s",
            "channels",
        },
    )

    profile_fields = _object(fields["profile"], "profile")
    _exact_fields(
        profile_fields,
        context="profile",
        required={"name", "version"},
    )
    profile = ProfileConfig(
        name=profile_fields["name"],
        version=profile_fields["version"],
    )

    timeout_fields = _object(fields["timeouts_s"], "timeouts_s")
    _exact_fields(
        timeout_fields,
        context="timeouts_s",
        required={"connect", "command", "settle", "test"},
    )
    timeouts = TimeoutConfig(
        connect_s=timeout_fields["connect"],
        command_s=timeout_fields["command"],
        settle_s=timeout_fields["settle"],
        test_s=timeout_fields["test"],
    )

    raw_channels = fields["channels"]
    if not isinstance(raw_channels, list):
        raise ConfigurationError("channels must be a JSON array")
    channels = tuple(_parse_channel(channel) for channel in raw_channels)
    source = cast(
        EvidenceSource,
        _enum_value(EvidenceSource, fields["evidence_source"], "evidence source"),
    )
    return ValidationConfig(
        config_id=fields["config_id"],
        config_version=fields["config_version"],
        profile=profile,
        evidence_source=source,
        channels=channels,
        timeouts=timeouts,
        allow_output=fields["allow_output"],
        schema_version=fields["schema_version"],
    )


def parse_validation_config_json(text: str | bytes) -> ValidationConfig:
    """Parse strict UTF-8 JSON without evaluating code or expressions."""

    if isinstance(text, bytes):
        if len(text) > MAX_CONFIG_BYTES:
            raise ConfigurationError(
                f"configuration exceeds the {MAX_CONFIG_BYTES}-byte size limit"
            )
        try:
            decoded = text.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise ConfigurationError("configuration must be valid UTF-8") from error
    elif isinstance(text, str):
        try:
            encoded_length = len(text.encode("utf-8", errors="strict"))
        except UnicodeEncodeError as error:
            raise ConfigurationError("configuration must be valid UTF-8") from error
        if encoded_length > MAX_CONFIG_BYTES:
            raise ConfigurationError(
                f"configuration exceeds the {MAX_CONFIG_BYTES}-byte size limit"
            )
        decoded = text
    else:
        raise ConfigurationError("configuration input must be str or bytes")

    try:
        value = json.loads(
            decoded,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except json.JSONDecodeError as error:
        raise ConfigurationError(
            f"configuration is not valid JSON at line {error.lineno}, "
            f"column {error.colno}"
        ) from error
    return _parse_validation_config(value)


def load_validation_config(path: str | os.PathLike[str]) -> ValidationConfig:
    """Load one bounded local JSON configuration file."""

    try:
        config_path = Path(path)
    except TypeError as error:
        raise ConfigurationError("configuration path must be path-like") from error
    if config_path.suffix.lower() != ".json":
        raise ConfigurationError("configuration file must use a .json extension")
    try:
        size = config_path.stat().st_size
    except OSError as error:
        raise ConfigurationError(f"cannot access configuration file: {error}") from error
    if size > MAX_CONFIG_BYTES:
        raise ConfigurationError(
            f"configuration exceeds the {MAX_CONFIG_BYTES}-byte size limit"
        )
    try:
        data = config_path.read_bytes()
    except OSError as error:
        raise ConfigurationError(f"cannot read configuration file: {error}") from error
    return parse_validation_config_json(data)


def validation_config_to_dict(config: ValidationConfig) -> dict[str, object]:
    """Return the stable public JSON representation of a configuration."""

    if not isinstance(config, ValidationConfig):
        raise ConfigurationError("config must be a ValidationConfig")
    channel_values: list[dict[str, object]] = []
    for channel in config.channels:
        value: dict[str, object] = {
            "name": channel.name,
            "role": channel.role.value,
            "unit": channel.unit.value,
            "enabled": channel.enabled,
        }
        if channel.safe_output_range is not None:
            value["safe_output_range"] = {
                "minimum": channel.safe_output_range.minimum,
                "maximum": channel.safe_output_range.maximum,
                "unit": channel.safe_output_range.unit.value,
            }
        channel_values.append(value)
    return {
        "schema_version": config.schema_version,
        "config_id": config.config_id,
        "config_version": config.config_version,
        "profile": {
            "name": config.profile.name,
            "version": config.profile.version,
        },
        "evidence_source": config.evidence_source.value,
        "allow_output": config.allow_output,
        "timeouts_s": {
            "connect": config.timeouts.connect_s,
            "command": config.timeouts.command_s,
            "settle": config.timeouts.settle_s,
            "test": config.timeouts.test_s,
        },
        "channels": channel_values,
    }


def dump_validation_config_json(config: ValidationConfig, *, indent: int = 2) -> str:
    """Serialize a configuration as deterministic, standards-compliant JSON."""

    if isinstance(indent, bool) or not isinstance(indent, int) or indent < 0:
        raise ConfigurationError("indent must be a non-negative integer")
    return json.dumps(
        validation_config_to_dict(config),
        indent=indent,
        ensure_ascii=True,
        allow_nan=False,
    ) + "\n"


def _require_configured_range_within_device(
    channel: ChannelConfig,
    device_range: SafeRange,
) -> None:
    config_range = channel.safe_output_range
    assert config_range is not None  # Guaranteed by ChannelConfig.
    if config_range.unit is not device_range.unit:
        raise ConfigurationError(
            f"channel {channel.name} unit {config_range.unit.value} does not match "
            f"device unit {device_range.unit.value}"
        )
    if (
        config_range.minimum < device_range.minimum
        or config_range.maximum > device_range.maximum
    ):
        raise ConfigurationError(
            f"configured safe range for {channel.name} exceeds the device safe range"
        )


def validate_config_capabilities(
    config: ValidationConfig,
    capabilities: DeviceCapabilities,
) -> None:
    """Check configuration/device compatibility without performing I/O."""

    if not isinstance(config, ValidationConfig):
        raise ConfigurationError("config must be a ValidationConfig")
    if not isinstance(capabilities, DeviceCapabilities):
        raise CapabilityError("capabilities must be DeviceCapabilities")
    if (
        config.profile.name != capabilities.profile_name
        or config.profile.version != capabilities.profile_version
    ):
        raise ConfigurationError(
            "configuration profile does not match the selected device profile"
        )

    output_commands: set[DeviceCommand] = set()
    for channel in config.channels:
        if not channel.enabled:
            continue
        if channel.role is ChannelRole.ANALOG_INPUT:
            if channel.name not in capabilities.adc_channels:
                raise CapabilityError(f"ADC channel {channel.name} is not available")
            device_range = capabilities.get_input_range(channel.name)
            if channel.unit is not device_range.unit:
                raise ConfigurationError(
                    f"channel {channel.name} unit {channel.unit.value} does not match "
                    f"device unit {device_range.unit.value}"
                )
        elif channel.role is ChannelRole.DIGITAL_INPUT:
            if channel.name not in capabilities.digital_input_channels:
                raise CapabilityError(
                    f"digital input channel {channel.name} is not available"
                )
        elif channel.role is ChannelRole.ANALOG_OUTPUT:
            if channel.name not in capabilities.dac_channels:
                raise CapabilityError(f"DAC channel {channel.name} is not available")
            _require_configured_range_within_device(
                channel, capabilities.get_output_range(channel.name)
            )
            output_commands.add(DeviceCommand.SET_ANALOG_STIMULUS)
        else:
            if channel.name not in capabilities.pwm_channels:
                raise CapabilityError(f"PWM channel {channel.name} is not available")
            _require_configured_range_within_device(
                channel, capabilities.get_output_range(channel.name)
            )
            output_commands.add(DeviceCommand.SET_PWM_STIMULUS)

    if config.allow_output:
        for command in output_commands:
            capabilities.require_command(command)
        if not capabilities.supports_safe_shutdown:
            raise CapabilityError("automatic output requires SAFE_SHUTDOWN capability")


__all__ = [
    "MAX_CONFIG_BYTES",
    "dump_validation_config_json",
    "load_validation_config",
    "parse_validation_config_json",
    "validate_config_capabilities",
    "validation_config_to_dict",
]
