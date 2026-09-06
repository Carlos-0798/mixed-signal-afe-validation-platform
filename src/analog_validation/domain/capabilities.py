"""Explicit device capability and safe-range declarations."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import cast

from analog_validation.errors import (
    CapabilityError,
    ConfigurationError,
    ValidationError,
)

from .enums import DeviceCommand, MeasurementUnit

CAPABILITY_SCHEMA_VERSION = "capabilities.v1"


def _require_identifier(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{name} must be a non-empty string")
    if value != value.strip():
        raise ValidationError(f"{name} must not have surrounding whitespace")
    return value


def _freeze_identifiers(name: str, values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ValidationError(f"{name} must be an iterable")
    frozen: tuple[object, ...] = tuple(values)
    for value in frozen:
        _require_identifier(name, value)
    if len(frozen) != len(set(frozen)):
        raise ValidationError(f"{name} cannot contain duplicates")
    return cast(tuple[str, ...], frozen)


@dataclass(frozen=True, slots=True)
class SafeRange:
    """Inclusive numeric range with an explicit unit."""

    minimum: float
    maximum: float
    unit: MeasurementUnit

    def __post_init__(self) -> None:
        if not isinstance(self.unit, MeasurementUnit):
            raise ValidationError("unit must be a supported MeasurementUnit")
        minimum = self._finite_number("minimum", self.minimum)
        maximum = self._finite_number("maximum", self.maximum)
        if minimum >= maximum:
            raise ValidationError("minimum must be less than maximum")
        object.__setattr__(self, "minimum", minimum)
        object.__setattr__(self, "maximum", maximum)

    @staticmethod
    def _finite_number(name: str, value: object) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError(f"{name} must be numeric")
        number = float(value)
        if not math.isfinite(number):
            raise ValidationError(f"{name} must be finite")
        return number

    def contains(self, value: float) -> bool:
        """Return whether a finite numeric value is inside this range."""

        number = self._finite_number("value", value)
        return self.minimum <= number <= self.maximum


@dataclass(frozen=True, slots=True)
class ChannelRange:
    """Safe range associated with one declared channel."""

    channel: str
    safe_range: SafeRange

    def __post_init__(self) -> None:
        _require_identifier("channel", self.channel)
        if not isinstance(self.safe_range, SafeRange):
            raise ValidationError("safe_range must be a SafeRange")


@dataclass(frozen=True, slots=True)
class DeviceCapabilities:
    """Versioned capabilities reported by a device or simulator.

    The model never derives capabilities from a board name, USB identifier, or
    manufacturer. Adapters must populate every field from explicit profile or
    capability data.
    """

    device_id: str
    profile_name: str
    profile_version: str
    adc_channels: tuple[str, ...] = ()
    dac_channels: tuple[str, ...] = ()
    pwm_channels: tuple[str, ...] = ()
    digital_input_channels: tuple[str, ...] = ()
    safe_input_ranges: tuple[ChannelRange, ...] = ()
    safe_output_ranges: tuple[ChannelRange, ...] = ()
    supported_commands: frozenset[DeviceCommand] = field(default_factory=frozenset)
    supports_safe_shutdown: bool = False
    schema_version: str = CAPABILITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_identifier("device_id", self.device_id)
        _require_identifier("profile_name", self.profile_name)
        _require_identifier("profile_version", self.profile_version)

        for name in (
            "adc_channels",
            "dac_channels",
            "pwm_channels",
            "digital_input_channels",
        ):
            object.__setattr__(
                self, name, _freeze_identifiers(name, getattr(self, name))
            )

        input_ranges = self._freeze_ranges("safe_input_ranges", self.safe_input_ranges)
        output_ranges = self._freeze_ranges(
            "safe_output_ranges", self.safe_output_ranges
        )
        object.__setattr__(self, "safe_input_ranges", input_ranges)
        object.__setattr__(self, "safe_output_ranges", output_ranges)

        commands = self._freeze_commands(self.supported_commands)
        object.__setattr__(self, "supported_commands", commands)
        if not isinstance(self.supports_safe_shutdown, bool):
            raise ValidationError("supports_safe_shutdown must be boolean")
        if self.schema_version != CAPABILITY_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported capability schema version: {self.schema_version}"
            )

        self._validate_range_coverage(input_ranges, output_ranges)
        self._validate_command_consistency(commands)

    @staticmethod
    def _freeze_ranges(name: str, values: object) -> tuple[ChannelRange, ...]:
        if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
            raise ValidationError(f"{name} must be an iterable")
        ranges: tuple[object, ...] = tuple(values)
        if not all(isinstance(item, ChannelRange) for item in ranges):
            raise ValidationError(f"{name} must contain ChannelRange values")
        typed_ranges = cast(tuple[ChannelRange, ...], ranges)
        channels = [item.channel for item in typed_ranges]
        if len(channels) != len(set(channels)):
            raise ValidationError(f"{name} cannot contain duplicate channels")
        return typed_ranges

    @staticmethod
    def _freeze_commands(values: object) -> frozenset[DeviceCommand]:
        if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
            raise ValidationError("supported_commands must be an iterable")
        commands: frozenset[object] = frozenset(values)
        if not all(isinstance(command, DeviceCommand) for command in commands):
            raise ValidationError("supported_commands contains an unknown command")
        return cast(frozenset[DeviceCommand], commands)

    def _validate_range_coverage(
        self,
        input_ranges: tuple[ChannelRange, ...],
        output_ranges: tuple[ChannelRange, ...],
    ) -> None:
        input_channels = {item.channel for item in input_ranges}
        adc_channels = set(self.adc_channels)
        if input_channels != adc_channels:
            raise ValidationError(
                "safe_input_ranges must cover exactly the declared ADC channels"
            )

        output_channels = {item.channel for item in output_ranges}
        declared_outputs = set(self.dac_channels) | set(self.pwm_channels)
        if output_channels != declared_outputs:
            raise ValidationError(
                "safe_output_ranges must cover exactly the declared DAC/PWM channels"
            )

    def _validate_command_consistency(self, commands: frozenset[DeviceCommand]) -> None:
        required_channels = {
            DeviceCommand.READ_MEASUREMENT: self.adc_channels,
            DeviceCommand.READ_DIGITAL_STATE: self.digital_input_channels,
            DeviceCommand.SET_ANALOG_STIMULUS: self.dac_channels,
            DeviceCommand.SET_PWM_STIMULUS: self.pwm_channels,
        }
        for command, channels in required_channels.items():
            if command in commands and not channels:
                raise ValidationError(f"{command.value} requires a declared channel")
        if self.supports_safe_shutdown != (DeviceCommand.SAFE_SHUTDOWN in commands):
            raise ValidationError(
                "supports_safe_shutdown and SAFE_SHUTDOWN command must agree"
            )

    @property
    def is_read_only(self) -> bool:
        """Return whether the device advertises no stimulus command."""

        return not bool(
            self.supported_commands
            & {
                DeviceCommand.SET_ANALOG_STIMULUS,
                DeviceCommand.SET_PWM_STIMULUS,
            }
        )

    @property
    def automated_output_allowed(self) -> bool:
        """Return whether output exists and an automatic safe shutdown exists."""

        return not self.is_read_only and self.supports_safe_shutdown

    def supports(self, command: DeviceCommand) -> bool:
        """Return whether an explicitly typed command was advertised."""

        if not isinstance(command, DeviceCommand):
            raise ValidationError("command must be a supported DeviceCommand")
        return command in self.supported_commands

    def require_command(self, command: DeviceCommand) -> None:
        """Reject an operation not explicitly advertised by the device."""

        if not self.supports(command):
            raise CapabilityError(f"device does not support {command.value}")

    def get_input_range(self, channel: str) -> SafeRange:
        """Return an explicitly declared safe input range."""

        return self._get_range("input", channel, self.safe_input_ranges)

    def get_output_range(self, channel: str) -> SafeRange:
        """Return an explicitly declared safe output range."""

        return self._get_range("output", channel, self.safe_output_ranges)

    @staticmethod
    def _get_range(
        direction: str, channel: str, ranges: tuple[ChannelRange, ...]
    ) -> SafeRange:
        _require_identifier("channel", channel)
        for item in ranges:
            if item.channel == channel:
                return item.safe_range
        raise CapabilityError(f"no safe {direction} range declared for {channel}")

    def require_automated_output(
        self,
        command: DeviceCommand,
        channel: str,
        value: float,
        unit: MeasurementUnit,
    ) -> None:
        """Validate a requested automatic stimulus against declared safety data."""

        if command not in {
            DeviceCommand.SET_ANALOG_STIMULUS,
            DeviceCommand.SET_PWM_STIMULUS,
        }:
            raise CapabilityError("command is not an output stimulus command")
        self.require_command(command)
        expected_channels = (
            self.dac_channels
            if command is DeviceCommand.SET_ANALOG_STIMULUS
            else self.pwm_channels
        )
        if channel not in expected_channels:
            raise CapabilityError(f"{channel} is not declared for {command.value}")
        if not self.supports_safe_shutdown:
            raise CapabilityError("automatic output requires SAFE_SHUTDOWN capability")
        safe_range = self.get_output_range(channel)
        if not isinstance(unit, MeasurementUnit):
            raise ConfigurationError("unit must be a supported MeasurementUnit")
        if unit is not safe_range.unit:
            raise ConfigurationError(
                f"output unit {unit.value} does not match safe range {safe_range.unit.value}"
            )
        try:
            in_range = safe_range.contains(value)
        except ValidationError as error:
            raise ConfigurationError(
                "output value must be finite and numeric"
            ) from error
        if not in_range:
            raise ConfigurationError(
                f"output value {value} is outside [{safe_range.minimum}, "
                f"{safe_range.maximum}] {safe_range.unit.value}"
            )


__all__ = [
    "CAPABILITY_SCHEMA_VERSION",
    "ChannelRange",
    "DeviceCapabilities",
    "SafeRange",
]
