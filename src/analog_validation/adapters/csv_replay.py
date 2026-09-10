"""Read-only DeviceAdapter for immutable CSV Replay v1 datasets."""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum
from typing import cast

from analog_validation.domain import (
    ChannelRange,
    DeviceCapabilities,
    DeviceCommand,
    EvidenceSource,
    Measurement,
    MeasurementUnit,
    SafeRange,
)
from analog_validation.errors import (
    AdapterStateError,
    CapabilityError,
    ConfigurationError,
    ReplayEndOfData,
)
from analog_validation.replay import CsvReplayDataset, CsvReplayRecord

from .base import AdapterState, DeviceAdapter

CSV_REPLAY_ADAPTER_CONFIG_SCHEMA_VERSION = "csv-replay-adapter-config.v1"

Sleeper = Callable[[float], None]


class ReplayChannelKind(str, Enum):
    """Input role explicitly assigned to one replay channel."""

    ANALOG = "ANALOG"
    DIGITAL = "DIGITAL"


class ReplayTimingMode(str, Enum):
    """Whether reads are immediate or delayed by scaled source timestamps."""

    IMMEDIATE = "IMMEDIATE"
    SCALED = "SCALED"


def _require_identifier(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ConfigurationError(f"{name} must be a non-empty stripped string")
    return value


def _require_speed(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError("speed_multiplier must be numeric")
    speed = float(value)
    if not math.isfinite(speed) or speed <= 0:
        raise ConfigurationError(
            "speed_multiplier must be finite and greater than zero"
        )
    return speed


@dataclass(frozen=True, slots=True)
class ReplayChannelConfig:
    """Explicit read role, unit, and range for one replay channel."""

    name: str
    kind: ReplayChannelKind
    unit: MeasurementUnit
    safe_input_range: SafeRange | None = None

    def __post_init__(self) -> None:
        _require_identifier("replay channel name", self.name)
        if not isinstance(self.kind, ReplayChannelKind):
            raise ConfigurationError("kind must be a ReplayChannelKind")
        if not isinstance(self.unit, MeasurementUnit):
            raise ConfigurationError("unit must be a MeasurementUnit")
        if self.kind is ReplayChannelKind.ANALOG:
            if not isinstance(self.safe_input_range, SafeRange):
                raise ConfigurationError(
                    "analog replay channels require a safe_input_range"
                )
            if self.safe_input_range.unit is not self.unit:
                raise ConfigurationError(
                    "safe_input_range unit must match the replay channel unit"
                )
            if self.unit is MeasurementUnit.BOOLEAN:
                raise ConfigurationError("analog replay channels cannot use bool units")
        else:
            if self.unit is not MeasurementUnit.BOOLEAN:
                raise ConfigurationError("digital replay channels must use bool units")
            if self.safe_input_range is not None:
                raise ConfigurationError(
                    "digital replay channels cannot define a safe_input_range"
                )


@dataclass(frozen=True, slots=True)
class CsvReplayAdapterConfig:
    """Immutable playback identity, channel map, and timing policy."""

    channels: tuple[ReplayChannelConfig, ...]
    device_id: str = "csv-replay-1"
    profile_name: str = "afe"
    profile_version: str = "1"
    timing_mode: ReplayTimingMode = ReplayTimingMode.IMMEDIATE
    speed_multiplier: float = 1.0
    schema_version: str = CSV_REPLAY_ADAPTER_CONFIG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("device_id", "profile_name", "profile_version"):
            _require_identifier(name, getattr(self, name))
        if isinstance(self.channels, (str, bytes)) or not isinstance(
            self.channels, Iterable
        ):
            raise ConfigurationError("channels must be an iterable")
        frozen: tuple[object, ...] = tuple(self.channels)
        if not all(isinstance(channel, ReplayChannelConfig) for channel in frozen):
            raise ConfigurationError("channels must contain ReplayChannelConfig values")
        channels = cast(tuple[ReplayChannelConfig, ...], frozen)
        names = [channel.name for channel in channels]
        if len(names) != len(set(names)):
            raise ConfigurationError("replay channel names must be unique")
        object.__setattr__(self, "channels", channels)
        if not isinstance(self.timing_mode, ReplayTimingMode):
            raise ConfigurationError("timing_mode must be a ReplayTimingMode")
        object.__setattr__(
            self,
            "speed_multiplier",
            _require_speed(self.speed_multiplier),
        )
        if self.schema_version != CSV_REPLAY_ADAPTER_CONFIG_SCHEMA_VERSION:
            raise ConfigurationError(
                f"unsupported CSV replay adapter config version: {self.schema_version}"
            )


class CsvReplayAdapter(DeviceAdapter):
    """Replay immutable records through the controller-neutral read-only port."""

    def __init__(
        self,
        dataset: CsvReplayDataset,
        config: CsvReplayAdapterConfig,
        *,
        sleeper: Sleeper = time.sleep,
    ) -> None:
        super().__init__(EvidenceSource.CSV_REPLAY)
        if not isinstance(dataset, CsvReplayDataset):
            raise ConfigurationError("dataset must be a CsvReplayDataset")
        if not isinstance(config, CsvReplayAdapterConfig):
            raise ConfigurationError("config must be a CsvReplayAdapterConfig")
        if not callable(sleeper):
            raise ConfigurationError("sleeper must be callable")
        self._dataset = dataset
        self._replay_config = config
        self._sleeper = sleeper
        self._speed_multiplier = config.speed_multiplier
        self._paused = False
        self._cursors: dict[str, int] = {}
        self._previous_records: dict[str, CsvReplayRecord] = {}
        self._records_by_channel = {
            channel.name: tuple(
                record for record in dataset.records if record.channel == channel.name
            )
            for channel in config.channels
        }
        configured_channels = {channel.name: channel for channel in config.channels}
        for record in dataset.records:
            channel = configured_channels.get(record.channel)
            if channel is None:
                raise ConfigurationError(
                    f"dataset channel {record.channel} is not declared by replay config"
                )
            if record.unit is not channel.unit:
                raise ConfigurationError(
                    f"dataset channel {record.channel} unit {record.unit.value} does "
                    f"not match configured unit {channel.unit.value}"
                )

        analog_channels = tuple(
            channel.name
            for channel in config.channels
            if channel.kind is ReplayChannelKind.ANALOG
        )
        digital_channels = tuple(
            channel.name
            for channel in config.channels
            if channel.kind is ReplayChannelKind.DIGITAL
        )
        commands: set[DeviceCommand] = set()
        if analog_channels:
            commands.add(DeviceCommand.READ_MEASUREMENT)
        if digital_channels:
            commands.add(DeviceCommand.READ_DIGITAL_STATE)
        self._replay_capabilities = DeviceCapabilities(
            config.device_id,
            config.profile_name,
            config.profile_version,
            adc_channels=analog_channels,
            digital_input_channels=digital_channels,
            safe_input_ranges=tuple(
                ChannelRange(channel.name, cast(SafeRange, channel.safe_input_range))
                for channel in config.channels
                if channel.kind is ReplayChannelKind.ANALOG
            ),
            supported_commands=frozenset(commands),
        )

    @property
    def dataset(self) -> CsvReplayDataset:
        """Return the immutable source dataset for audit lookup."""

        return self._dataset

    @property
    def replay_config(self) -> CsvReplayAdapterConfig:
        """Return the immutable adapter configuration."""

        return self._replay_config

    @property
    def speed_multiplier(self) -> float:
        """Return the current scaled-timing speed multiplier."""

        return self._speed_multiplier

    @property
    def is_paused(self) -> bool:
        """Return whether reads are currently paused."""

        return self._paused

    @property
    def at_end(self) -> bool:
        """Return whether every configured channel is exhausted."""

        if not self.is_connected:
            return False
        return all(
            self._cursors.get(channel.name, 0)
            >= len(self._records_by_channel[channel.name])
            for channel in self._replay_config.channels
        )

    def channel_at_end(self, channel: str) -> bool:
        """Return whether one configured channel has no remaining records."""

        self._require_connected_control("inspect replay end state")
        if not isinstance(channel, str) or not channel or channel != channel.strip():
            raise ConfigurationError("channel must be a non-empty stripped string")
        if channel not in self._records_by_channel:
            raise CapabilityError(f"replay channel {channel} is not available")
        return self._cursors[channel] >= len(self._records_by_channel[channel])

    def pause(self) -> None:
        """Pause future reads without changing cursors or source data."""

        self._require_connected_control("pause replay")
        self._paused = True

    def resume(self) -> None:
        """Resume future reads from the same per-channel cursors."""

        self._require_connected_control("resume replay")
        self._paused = False

    def set_speed_multiplier(self, value: float) -> None:
        """Change the delay scale applied to future SCALED reads."""

        self._require_connected_control("change replay speed")
        self._speed_multiplier = _require_speed(value)

    def _require_connected_control(self, operation: str) -> None:
        if self.state not in {
            AdapterState.CONNECTED_READ_ONLY,
            AdapterState.CAPABILITIES_CONFIRMED,
        }:
            raise AdapterStateError(
                f"cannot {operation} while adapter state is {self.state.value}"
            )

    def _connect(self) -> None:
        self._cursors = {channel.name: 0 for channel in self._replay_config.channels}
        self._previous_records.clear()
        self._speed_multiplier = self._replay_config.speed_multiplier
        self._paused = False

    def _disconnect(self) -> None:
        self._cursors.clear()
        self._previous_records.clear()
        self._speed_multiplier = self._replay_config.speed_multiplier
        self._paused = False

    def _get_capabilities(self) -> DeviceCapabilities:
        return self._replay_capabilities

    def _read_measurement(self, channel: str) -> Measurement:
        return self._next_measurement(channel)

    def _read_digital_state(self, channel: str) -> Measurement:
        return self._next_measurement(channel)

    def _next_measurement(self, channel: str) -> Measurement:
        if self._paused:
            raise AdapterStateError("CSV replay is paused")
        cursor = self._cursors.get(channel)
        if cursor is None:
            raise AdapterStateError("CSV replay is not connected")
        records = self._records_by_channel[channel]
        if cursor >= len(records):
            raise ReplayEndOfData(f"CSV replay channel {channel} reached EOF")
        record = records[cursor]
        previous = self._previous_records.get(channel)
        if (
            self._replay_config.timing_mode is ReplayTimingMode.SCALED
            and previous is not None
        ):
            delay = (
                record.timestamp - previous.timestamp
            ).total_seconds() / self._speed_multiplier
            if delay > 0:
                self._sleeper(delay)

        record_id = f"csv-replay:{self._dataset.dataset_id}:{record.record_id}"
        measurement = Measurement(
            record_id,
            record.record_id,
            record.timestamp,
            record.channel,
            record.value,
            record.unit,
            record.status,
            EvidenceSource.CSV_REPLAY,
            record.quality_flags,
        )
        self._cursors[channel] = cursor + 1
        self._previous_records[channel] = record
        return measurement


__all__ = [
    "CSV_REPLAY_ADAPTER_CONFIG_SCHEMA_VERSION",
    "CsvReplayAdapter",
    "CsvReplayAdapterConfig",
    "ReplayChannelConfig",
    "ReplayChannelKind",
    "ReplayTimingMode",
]
