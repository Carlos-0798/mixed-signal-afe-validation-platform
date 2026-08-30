"""Immutable, versioned product configuration models."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import cast

from analog_validation.domain import EvidenceSource, MeasurementUnit, SafeRange
from analog_validation.errors import ConfigurationError, ValidationError

VALIDATION_CONFIG_SCHEMA_VERSION = "validation-config.v1"


def _require_identifier(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"{name} must be a non-empty string")
    if value != value.strip():
        raise ConfigurationError(f"{name} must not have surrounding whitespace")
    return value


class ChannelRole(str, Enum):
    """Controller-neutral role assigned to a configured channel."""

    ANALOG_INPUT = "ANALOG_INPUT"
    ANALOG_OUTPUT = "ANALOG_OUTPUT"
    PWM_OUTPUT = "PWM_OUTPUT"
    DIGITAL_INPUT = "DIGITAL_INPUT"

    @property
    def is_output(self) -> bool:
        """Return whether the role can request an external stimulus."""

        return self in {self.ANALOG_OUTPUT, self.PWM_OUTPUT}


@dataclass(frozen=True, slots=True)
class ProfileConfig:
    """Profile identity expected by a validation configuration."""

    name: str
    version: str

    def __post_init__(self) -> None:
        _require_identifier("profile name", self.name)
        _require_identifier("profile version", self.version)


@dataclass(frozen=True, slots=True)
class TimeoutConfig:
    """Finite host-side time limits expressed in seconds."""

    connect_s: float = 5.0
    command_s: float = 2.0
    settle_s: float = 0.1
    test_s: float = 60.0

    def __post_init__(self) -> None:
        for name in ("connect_s", "command_s", "settle_s", "test_s"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ConfigurationError(f"{name} must be numeric")
            number = float(value)
            if not math.isfinite(number):
                raise ConfigurationError(f"{name} must be finite")
            object.__setattr__(self, name, number)

        if self.connect_s <= 0 or self.command_s <= 0 or self.test_s <= 0:
            raise ConfigurationError(
                "connect_s, command_s, and test_s must be greater than zero"
            )
        if self.settle_s < 0:
            raise ConfigurationError("settle_s must not be negative")
        if self.test_s < self.command_s + self.settle_s:
            raise ConfigurationError(
                "test_s must be at least command_s plus settle_s"
            )


@dataclass(frozen=True, slots=True)
class ChannelConfig:
    """One configured channel and its software-side output safety limit."""

    name: str
    role: ChannelRole
    unit: MeasurementUnit
    enabled: bool = True
    safe_output_range: SafeRange | None = None

    def __post_init__(self) -> None:
        _require_identifier("channel name", self.name)
        if not isinstance(self.role, ChannelRole):
            raise ConfigurationError("role must be a supported ChannelRole")
        if not isinstance(self.unit, MeasurementUnit):
            raise ConfigurationError("unit must be a supported MeasurementUnit")
        if not isinstance(self.enabled, bool):
            raise ConfigurationError("enabled must be boolean")

        if self.role.is_output and not isinstance(self.safe_output_range, SafeRange):
            raise ConfigurationError("output channels require a safe_output_range")
        if not self.role.is_output and self.safe_output_range is not None:
            raise ConfigurationError("input channels cannot define safe_output_range")
        if (
            self.safe_output_range is not None
            and self.safe_output_range.unit is not self.unit
        ):
            raise ConfigurationError(
                "safe_output_range unit must match the channel unit"
            )
        if self.role is ChannelRole.DIGITAL_INPUT and self.unit is not MeasurementUnit.BOOLEAN:
            raise ConfigurationError("DIGITAL_INPUT channels must use bool units")
        if self.role is ChannelRole.PWM_OUTPUT and self.unit is not MeasurementUnit.RATIO:
            raise ConfigurationError("PWM_OUTPUT channels must use ratio units")

    @property
    def is_output(self) -> bool:
        """Return whether this channel can request an external stimulus."""

        return self.role.is_output


@dataclass(frozen=True, slots=True)
class ValidationConfig:
    """Top-level, immutable validation configuration.

    ``allow_output`` is deliberately false by default. Setting it to true is
    only one gate: device capability validation and per-value range checks are
    still required before an adapter may perform an output operation.
    """

    config_id: str
    config_version: str
    profile: ProfileConfig
    evidence_source: EvidenceSource
    channels: tuple[ChannelConfig, ...]
    timeouts: TimeoutConfig = field(default_factory=TimeoutConfig)
    allow_output: bool = False
    schema_version: str = VALIDATION_CONFIG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_identifier("config_id", self.config_id)
        _require_identifier("config_version", self.config_version)
        if not isinstance(self.profile, ProfileConfig):
            raise ConfigurationError("profile must be a ProfileConfig")
        if not isinstance(self.evidence_source, EvidenceSource):
            raise ConfigurationError("evidence_source must be an EvidenceSource")
        if isinstance(self.channels, (str, bytes)) or not isinstance(
            self.channels, Iterable
        ):
            raise ConfigurationError("channels must be an iterable")
        frozen: tuple[object, ...] = tuple(self.channels)
        if not all(isinstance(channel, ChannelConfig) for channel in frozen):
            raise ConfigurationError("channels must contain ChannelConfig values")
        channels = cast(tuple[ChannelConfig, ...], frozen)
        names = [channel.name for channel in channels]
        if len(names) != len(set(names)):
            raise ConfigurationError("channels cannot contain duplicate names")
        if not any(channel.enabled for channel in channels):
            raise ConfigurationError("at least one channel must be enabled")
        object.__setattr__(self, "channels", channels)

        if not isinstance(self.timeouts, TimeoutConfig):
            raise ConfigurationError("timeouts must be a TimeoutConfig")
        if not isinstance(self.allow_output, bool):
            raise ConfigurationError("allow_output must be boolean")
        if self.schema_version != VALIDATION_CONFIG_SCHEMA_VERSION:
            raise ConfigurationError(
                f"unsupported configuration schema version: {self.schema_version}"
            )
        if self.allow_output and not any(
            channel.enabled and channel.is_output for channel in channels
        ):
            raise ConfigurationError(
                "allow_output requires at least one enabled output channel"
            )

    def get_channel(self, name: str) -> ChannelConfig:
        """Return a configured channel or reject the unknown name."""

        _require_identifier("channel name", name)
        for channel in self.channels:
            if channel.name == name:
                return channel
        raise ConfigurationError(f"channel {name} is not configured")

    def require_output(
        self,
        channel_name: str,
        value: float,
        unit: MeasurementUnit,
    ) -> ChannelConfig:
        """Validate one output request against configuration-only gates."""

        if not self.allow_output:
            raise ConfigurationError("output is disabled by this configuration")
        channel = self.get_channel(channel_name)
        if not channel.enabled:
            raise ConfigurationError(f"channel {channel_name} is disabled")
        if not channel.is_output:
            raise ConfigurationError(f"channel {channel_name} is not an output")
        if not isinstance(unit, MeasurementUnit):
            raise ConfigurationError("unit must be a supported MeasurementUnit")
        if unit is not channel.unit:
            raise ConfigurationError(
                f"output unit {unit.value} does not match channel unit "
                f"{channel.unit.value}"
            )
        safe_range = channel.safe_output_range
        if safe_range is None:  # pragma: no cover - guaranteed by ChannelConfig
            raise ConfigurationError("output channel has no safe_output_range")
        try:
            in_range = safe_range.contains(value)
        except ValidationError as error:
            raise ConfigurationError("output value must be finite and numeric") from error
        if not in_range:
            raise ConfigurationError(
                f"output value {value} is outside [{safe_range.minimum}, "
                f"{safe_range.maximum}] {safe_range.unit.value}"
            )
        return channel


__all__ = [
    "VALIDATION_CONFIG_SCHEMA_VERSION",
    "ChannelConfig",
    "ChannelRole",
    "ProfileConfig",
    "TimeoutConfig",
    "ValidationConfig",
]
