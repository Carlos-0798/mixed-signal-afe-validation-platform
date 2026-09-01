"""Explicit AFE v1 wire-capability projection for the read-only adapter."""

from __future__ import annotations

from analog_validation.domain import (
    ChannelRange,
    DeviceCapabilities,
    DeviceCommand,
)
from analog_validation.errors import ConfigurationError
from analog_validation.protocol import AFE_PROFILE_NAME, AFE_PROFILE_VERSION

_READ_ONLY_COMMANDS = frozenset(
    {
        DeviceCommand.READ_MEASUREMENT,
        DeviceCommand.READ_DIGITAL_STATE,
    }
)


def _index(channel: str, prefix: str) -> int:
    if not isinstance(channel, str) or not channel.startswith(prefix):
        raise ConfigurationError(
            f"AFE {prefix} channel must use {prefix}<0..255> naming"
        )
    suffix = channel[len(prefix) :]
    if not suffix.isdigit():
        raise ConfigurationError(
            f"AFE {prefix} channel must use {prefix}<0..255> naming"
        )
    value = int(suffix)
    if not 0 <= value <= 0xFF:
        raise ConfigurationError(f"AFE channel index is outside 0..255: {channel}")
    return value


def _adapter_name(channel: str, prefix: str, role: str) -> str:
    return f"afe.ch{_index(channel, prefix)}.{role}"


def project_afe_v1_read_only_capabilities(
    capabilities: DeviceCapabilities,
) -> DeviceCapabilities:
    """Alias every frozen AFE wire channel without enabling device writes."""

    if not isinstance(capabilities, DeviceCapabilities):
        raise ConfigurationError("capabilities must be DeviceCapabilities")
    if (
        capabilities.profile_name != AFE_PROFILE_NAME
        or capabilities.profile_version != AFE_PROFILE_VERSION
    ):
        raise ConfigurationError("capabilities are not AFE v1")

    adc_names = {
        name: _adapter_name(name, "adc", "input")
        for name in capabilities.adc_channels
    }
    dac_names = {
        name: _adapter_name(name, "dac", "dac")
        for name in capabilities.dac_channels
    }
    pwm_names = {
        name: _adapter_name(name, "pwm", "pwm")
        for name in capabilities.pwm_channels
    }
    digital_names = {
        name: _adapter_name(name, "din", "threshold")
        for name in capabilities.digital_input_channels
    }
    all_names = {**adc_names, **dac_names, **pwm_names}

    return DeviceCapabilities(
        device_id=capabilities.device_id,
        profile_name=capabilities.profile_name,
        profile_version=capabilities.profile_version,
        adc_channels=tuple(adc_names[name] for name in capabilities.adc_channels),
        dac_channels=tuple(dac_names[name] for name in capabilities.dac_channels),
        pwm_channels=tuple(pwm_names[name] for name in capabilities.pwm_channels),
        digital_input_channels=tuple(
            digital_names[name] for name in capabilities.digital_input_channels
        ),
        safe_input_ranges=tuple(
            ChannelRange(adc_names[item.channel], item.safe_range)
            for item in capabilities.safe_input_ranges
        ),
        safe_output_ranges=tuple(
            ChannelRange(all_names[item.channel], item.safe_range)
            for item in capabilities.safe_output_ranges
        ),
        supported_commands=capabilities.supported_commands & _READ_ONLY_COMMANDS,
        supports_safe_shutdown=False,
    )


__all__ = ["project_afe_v1_read_only_capabilities"]
