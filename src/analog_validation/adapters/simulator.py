"""Deterministic read-only simulator adapter and AFE sample generator."""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import count as count_indices
from itertools import islice

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
    AdapterStateError,
    ValidationError,
)
from analog_validation.protocol import AfeTelemetry

from .base import DeviceAdapter

SIMULATOR_CONFIG_SCHEMA_VERSION = "simulator-config.v1"
DEFAULT_SIMULATOR_EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)

Clock = Callable[[], datetime]


def _require_integer(name: str, value: object, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ValidationError(f"{name} must be at least {minimum}")
    return value


def _require_identifier(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{name} must be a non-empty string")
    if value != value.strip():
        raise ValidationError(f"{name} must not have surrounding whitespace")
    return value


@dataclass(frozen=True, slots=True)
class SimulatorConfig:
    """Versioned controls for the deterministic Step 3 simulator."""

    seed: int = 430
    interval_ms: int = 100
    device_id: str = "simulator-afe-1"
    profile_name: str = "afe"
    profile_version: str = "1"
    analog_channel: str = "afe.ch0.input"
    schema_version: str = SIMULATOR_CONFIG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_integer("seed", self.seed)
        _require_integer("interval_ms", self.interval_ms, minimum=0)
        for name in (
            "device_id",
            "profile_name",
            "profile_version",
            "analog_channel",
        ):
            _require_identifier(name, getattr(self, name))
        if self.schema_version != SIMULATOR_CONFIG_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported simulator config schema version: {self.schema_version}"
            )


def _telemetry_stream(interval_ms: int, seed: int) -> Iterator[AfeTelemetry]:
    rng = random.Random(seed)
    for index in count_indices():
        input_mv = round(800 + 550 * math.sin(index / 7.0) + rng.gauss(0, 2))
        ideal_output = 2.0 * input_mv + 12
        output_mv = round(min(3275, max(25, ideal_output + rng.gauss(0, 3))))
        fault = 0x0001 if output_mv in {25, 3275} else 0
        yield AfeTelemetry(
            seq=index & 0xFFFF,
            time_ms=(index * interval_ms) & 0xFFFFFFFF,
            channel=0,
            input_mv=input_mv,
            output_mv=output_mv,
            gain_milli=2000,
            threshold=int(input_mv >= 1800),
            fault_flags=fault,
        )


def generate_afe_telemetry(
    count: int,
    interval_ms: int = 100,
    seed: int = 430,
) -> Iterator[AfeTelemetry]:
    """Return a finite deterministic sequence using the frozen AFE formula."""

    validated_count = _require_integer("count", count, minimum=0)
    validated_interval = _require_integer("interval_ms", interval_ms, minimum=0)
    validated_seed = _require_integer("seed", seed)
    return islice(
        _telemetry_stream(validated_interval, validated_seed),
        validated_count,
    )


class SimulatorAdapter(DeviceAdapter):
    """Deterministic, read-only AFE simulator with explicit SYNTHETIC data."""

    def __init__(
        self,
        config: SimulatorConfig | None = None,
        *,
        clock: Clock | None = None,
    ) -> None:
        super().__init__(EvidenceSource.SYNTHETIC)
        if config is None:
            config = SimulatorConfig()
        if not isinstance(config, SimulatorConfig):
            raise ValidationError("config must be a SimulatorConfig")
        if clock is not None and not callable(clock):
            raise ValidationError("clock must be callable")
        self._simulator_config = config
        self._clock: Clock = clock or (lambda: DEFAULT_SIMULATOR_EPOCH)
        self._stream: Iterator[AfeTelemetry] | None = None
        self._started_at: datetime | None = None
        self._read_index = 0
        self._simulator_capabilities = DeviceCapabilities(
            config.device_id,
            config.profile_name,
            config.profile_version,
            adc_channels=(config.analog_channel,),
            safe_input_ranges=(
                ChannelRange(
                    config.analog_channel,
                    SafeRange(0.0, 3300.0, MeasurementUnit.MILLIVOLT),
                ),
            ),
            supported_commands=frozenset({DeviceCommand.READ_MEASUREMENT}),
        )

    @property
    def simulator_config(self) -> SimulatorConfig:
        """Return the immutable configuration used for this adapter."""

        return self._simulator_config

    def _connect(self) -> None:
        started_at = self._clock()
        if not isinstance(started_at, datetime):
            raise AdapterConnectionError("simulator clock must return a datetime")
        if started_at.tzinfo is None or started_at.utcoffset() is None:
            raise AdapterConnectionError("simulator clock must return a timezone-aware datetime")
        self._started_at = started_at.astimezone(timezone.utc)
        self._stream = _telemetry_stream(
            self._simulator_config.interval_ms,
            self._simulator_config.seed,
        )
        self._read_index = 0

    def _disconnect(self) -> None:
        self._stream = None
        self._started_at = None
        self._read_index = 0

    def _get_capabilities(self) -> DeviceCapabilities:
        return self._simulator_capabilities

    def _read_measurement(self, channel: str) -> Measurement:
        if self._stream is None or self._started_at is None:
            raise AdapterStateError("simulator stream is not connected")
        message = next(self._stream)
        index = self._read_index
        self._read_index += 1
        record_id = f"simulator-{index:08d}"
        return Measurement(
            record_id,
            record_id,
            self._started_at
            + timedelta(milliseconds=index * self._simulator_config.interval_ms),
            channel,
            float(message.input_mv),
            MeasurementUnit.MILLIVOLT,
            MeasurementStatus.VALID,
            EvidenceSource.SYNTHETIC,
        )


__all__ = [
    "DEFAULT_SIMULATOR_EPOCH",
    "SIMULATOR_CONFIG_SCHEMA_VERSION",
    "SimulatorAdapter",
    "SimulatorConfig",
    "generate_afe_telemetry",
]
