"""Deterministic read-only simulator adapter and AFE sample generator."""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
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
    QualityFlag,
    SafeRange,
)
from analog_validation.errors import (
    AdapterConnectionError,
    AdapterError,
    AdapterStateError,
    CrcMismatch,
    ValidationError,
)
from analog_validation.protocol import AfeTelemetry

from .base import DeviceAdapter

SIMULATOR_CONFIG_SCHEMA_VERSION = "simulator-config.v1"
DEFAULT_SIMULATOR_EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)

Clock = Callable[[], datetime]


class SimulatorFaultMode(str, Enum):
    """Deterministic fault injected on a configured read cadence."""

    NONE = "NONE"
    MISSING_SAMPLE = "MISSING_SAMPLE"
    COMMUNICATION_ERROR = "COMMUNICATION_ERROR"
    CRC_ERROR = "CRC_ERROR"


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


def _require_number(
    name: str,
    value: object,
    *,
    minimum: float | None = None,
    strictly_positive: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValidationError(f"{name} must be finite")
    if strictly_positive and number <= 0:
        raise ValidationError(f"{name} must be greater than zero")
    if minimum is not None and number < minimum:
        raise ValidationError(f"{name} must be at least {minimum}")
    return number


@dataclass(frozen=True, slots=True)
class SimulatorConfig:
    """Versioned controls for deterministic signal and fault simulation."""

    seed: int = 430
    interval_ms: int = 100
    device_id: str = "simulator-afe-1"
    profile_name: str = "afe"
    profile_version: str = "1"
    analog_channel: str = "afe.ch0.input"
    output_channel: str = "afe.ch0.output"
    threshold_channel: str = "afe.ch0.threshold"
    gain: float = 2.0
    offset_mv: float = 12.0
    noise_stddev_mv: float = 0.0
    saturation_min_mv: float = 25.0
    saturation_max_mv: float = 3275.0
    hysteresis_low_mv: float = 900.0
    hysteresis_high_mv: float = 1000.0
    fault_mode: SimulatorFaultMode = SimulatorFaultMode.NONE
    fault_every_n: int | None = None
    schema_version: str = SIMULATOR_CONFIG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_integer("seed", self.seed)
        _require_integer("interval_ms", self.interval_ms, minimum=0)
        for name in (
            "device_id",
            "profile_name",
            "profile_version",
            "analog_channel",
            "output_channel",
            "threshold_channel",
        ):
            _require_identifier(name, getattr(self, name))
        channels = {
            self.analog_channel,
            self.output_channel,
            self.threshold_channel,
        }
        if len(channels) != 3:
            raise ValidationError("simulator channel names must be distinct")

        gain = _require_number("gain", self.gain, strictly_positive=True)
        offset = _require_number("offset_mv", self.offset_mv)
        noise = _require_number("noise_stddev_mv", self.noise_stddev_mv, minimum=0.0)
        saturation_min = _require_number(
            "saturation_min_mv", self.saturation_min_mv, minimum=0.0
        )
        saturation_max = _require_number(
            "saturation_max_mv", self.saturation_max_mv, minimum=0.0
        )
        if saturation_min >= saturation_max or saturation_max > 3300.0:
            raise ValidationError(
                "saturation limits must satisfy 0 <= minimum < maximum <= 3300 mV"
            )
        hysteresis_low = _require_number(
            "hysteresis_low_mv", self.hysteresis_low_mv, minimum=0.0
        )
        hysteresis_high = _require_number(
            "hysteresis_high_mv", self.hysteresis_high_mv, minimum=0.0
        )
        if hysteresis_low >= hysteresis_high or hysteresis_high > 3300.0:
            raise ValidationError(
                "hysteresis thresholds must satisfy 0 <= low < high <= 3300 mV"
            )
        for name, value in (
            ("gain", gain),
            ("offset_mv", offset),
            ("noise_stddev_mv", noise),
            ("saturation_min_mv", saturation_min),
            ("saturation_max_mv", saturation_max),
            ("hysteresis_low_mv", hysteresis_low),
            ("hysteresis_high_mv", hysteresis_high),
        ):
            object.__setattr__(self, name, value)

        if not isinstance(self.fault_mode, SimulatorFaultMode):
            raise ValidationError("fault_mode must be a SimulatorFaultMode")
        if self.fault_mode is SimulatorFaultMode.NONE:
            if self.fault_every_n is not None:
                raise ValidationError("fault_every_n requires a non-NONE fault_mode")
        else:
            if self.fault_every_n is None:
                raise ValidationError("fault_mode requires fault_every_n")
            _require_integer("fault_every_n", self.fault_every_n, minimum=1)
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
        self._streams: dict[str, Iterator[AfeTelemetry]] = {}
        self._noise_rngs: dict[str, random.Random] = {}
        self._started_at: datetime | None = None
        self._read_indices: dict[str, int] = {}
        self._hysteresis_states: dict[str, bool] = {}
        self._simulator_capabilities = DeviceCapabilities(
            config.device_id,
            config.profile_name,
            config.profile_version,
            adc_channels=(config.analog_channel, config.output_channel),
            digital_input_channels=(config.threshold_channel,),
            safe_input_ranges=(
                ChannelRange(
                    config.analog_channel,
                    SafeRange(0.0, 3300.0, MeasurementUnit.MILLIVOLT),
                ),
                ChannelRange(
                    config.output_channel,
                    SafeRange(0.0, 3300.0, MeasurementUnit.MILLIVOLT),
                ),
            ),
            supported_commands=frozenset(
                {
                    DeviceCommand.READ_DIGITAL_STATE,
                    DeviceCommand.READ_MEASUREMENT,
                }
            ),
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
            raise AdapterConnectionError(
                "simulator clock must return a timezone-aware datetime"
            )
        self._started_at = started_at.astimezone(timezone.utc)
        channels = (
            self._simulator_config.analog_channel,
            self._simulator_config.output_channel,
            self._simulator_config.threshold_channel,
        )
        self._streams = {
            channel: _telemetry_stream(
                self._simulator_config.interval_ms,
                self._simulator_config.seed,
            )
            for channel in channels
        }
        self._noise_rngs = {
            self._simulator_config.output_channel: random.Random(
                self._simulator_config.seed ^ 0x5EED5EED
            )
        }
        self._read_indices = dict.fromkeys(channels, 0)
        self._hysteresis_states = {self._simulator_config.threshold_channel: False}

    def _disconnect(self) -> None:
        self._streams.clear()
        self._noise_rngs.clear()
        self._started_at = None
        self._read_indices.clear()
        self._hysteresis_states.clear()

    def _get_capabilities(self) -> DeviceCapabilities:
        return self._simulator_capabilities

    def _read_measurement(self, channel: str) -> Measurement:
        message, index = self._next_sample(channel)
        fault = self._apply_fault(channel, index, MeasurementUnit.MILLIVOLT)
        if fault is not None:
            return fault

        if channel == self._simulator_config.analog_channel:
            value = float(message.input_mv)
            status = MeasurementStatus.VALID
            flags: frozenset[QualityFlag] = frozenset()
        else:
            noise_rng = self._noise_rngs.get(channel)
            if noise_rng is None:
                raise AdapterStateError(
                    "simulator output noise source is not connected"
                )
            raw_value = (
                self._simulator_config.gain * message.input_mv
                + self._simulator_config.offset_mv
                + noise_rng.gauss(0.0, self._simulator_config.noise_stddev_mv)
            )
            value = min(
                self._simulator_config.saturation_max_mv,
                max(self._simulator_config.saturation_min_mv, raw_value),
            )
            if value != raw_value:
                status = MeasurementStatus.SUSPECT
                flags = frozenset({QualityFlag.SATURATED})
            else:
                status = MeasurementStatus.VALID
                flags = frozenset()

        return self._make_measurement(
            channel,
            index,
            value,
            MeasurementUnit.MILLIVOLT,
            status,
            flags,
        )

    def _read_digital_state(self, channel: str) -> Measurement:
        message, index = self._next_sample(channel)
        fault = self._apply_fault(channel, index, MeasurementUnit.BOOLEAN)
        if fault is not None:
            return fault

        state = self._hysteresis_states.get(channel)
        if state is None:
            raise AdapterStateError("simulator hysteresis state is not connected")
        if not state and message.input_mv >= self._simulator_config.hysteresis_high_mv:
            state = True
        elif state and message.input_mv <= self._simulator_config.hysteresis_low_mv:
            state = False
        self._hysteresis_states[channel] = state
        return self._make_measurement(
            channel,
            index,
            float(state),
            MeasurementUnit.BOOLEAN,
            MeasurementStatus.VALID,
        )

    def _next_sample(self, channel: str) -> tuple[AfeTelemetry, int]:
        stream = self._streams.get(channel)
        index = self._read_indices.get(channel)
        if stream is None or index is None or self._started_at is None:
            raise AdapterStateError("simulator stream is not connected")
        message = next(stream)
        self._read_indices[channel] = index + 1
        return message, index

    def _apply_fault(
        self,
        channel: str,
        index: int,
        unit: MeasurementUnit,
    ) -> Measurement | None:
        mode = self._simulator_config.fault_mode
        cadence = self._simulator_config.fault_every_n
        if mode is SimulatorFaultMode.NONE or cadence is None:
            return None
        if (index + 1) % cadence != 0:
            return None
        if mode is SimulatorFaultMode.MISSING_SAMPLE:
            return self._make_measurement(
                channel,
                index,
                None,
                unit,
                MeasurementStatus.INVALID,
                frozenset({QualityFlag.COMMUNICATION_ERROR, QualityFlag.MISSING}),
            )
        if mode is SimulatorFaultMode.COMMUNICATION_ERROR:
            raise AdapterError("injected simulator communication error")
        raise CrcMismatch("injected simulator CRC error")

    def _make_measurement(
        self,
        channel: str,
        index: int,
        value: float | None,
        unit: MeasurementUnit,
        status: MeasurementStatus,
        flags: frozenset[QualityFlag] = frozenset(),
    ) -> Measurement:
        if self._started_at is None:
            raise AdapterStateError("simulator clock is not connected")
        record_id = (
            f"simulator-{index:08d}"
            if channel == self._simulator_config.analog_channel
            else f"simulator-{channel}-{index:08d}"
        )
        return Measurement(
            record_id,
            record_id,
            self._started_at
            + timedelta(milliseconds=index * self._simulator_config.interval_ms),
            channel,
            value,
            unit,
            status,
            EvidenceSource.SYNTHETIC,
            flags,
        )


__all__ = [
    "DEFAULT_SIMULATOR_EPOCH",
    "SIMULATOR_CONFIG_SCHEMA_VERSION",
    "SimulatorAdapter",
    "SimulatorConfig",
    "SimulatorFaultMode",
    "generate_afe_telemetry",
]
