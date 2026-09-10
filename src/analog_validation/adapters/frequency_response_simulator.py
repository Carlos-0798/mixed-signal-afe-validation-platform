"""Deterministic read-only frequency-response simulator adapter."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

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

from .base import DeviceAdapter
from .simulator import DEFAULT_SIMULATOR_EPOCH

FREQUENCY_RESPONSE_SIMULATOR_CONFIG_SCHEMA_VERSION = (
    "frequency-response-simulator-config.v1"
)

Clock = Callable[[], datetime]


def _identifier(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValidationError(f"{name} must be a non-empty stripped string")
    return value


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{name} must be numeric")
    checked = float(value)
    if not math.isfinite(checked):
        raise ValidationError(f"{name} must be finite")
    return checked


def _log_square_difference(high: float, low: float) -> float:
    """Return ``log(high**2 - low**2)`` without squaring either value."""

    ratio = low / high
    return (
        2.0 * math.log(high)
        + math.log1p(-ratio)
        + math.log1p(ratio)
    )


@dataclass(frozen=True, slots=True)
class FrequencyResponseSimulatorConfig:
    """One bounded logarithmic sweep and normalized single-pole response."""

    point_count: int = 21
    frequency_minimum_hz: float = 10.0
    frequency_maximum_hz: float = 100_000.0
    cutoff_frequency_hz: float = 1_000.0
    input_amplitude: float = 1_000.0
    passband_gain: float = 1.0
    amplitude_unit: MeasurementUnit = MeasurementUnit.MILLIVOLT
    device_id: str = "simulator-frequency-response-1"
    profile_name: str = "afe"
    profile_version: str = "1"
    frequency_channel: str = "afe.ch0.frequency"
    input_amplitude_channel: str = "afe.ch0.input"
    output_amplitude_channel: str = "afe.ch0.output"
    interval_ms: int = 100
    schema_version: str = FREQUENCY_RESPONSE_SIMULATOR_CONFIG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            isinstance(self.point_count, bool)
            or not isinstance(self.point_count, int)
            or self.point_count < 2
        ):
            raise ValidationError("point_count must be an integer of at least two")
        if (
            isinstance(self.interval_ms, bool)
            or not isinstance(self.interval_ms, int)
            or self.interval_ms < 0
        ):
            raise ValidationError("interval_ms must be a non-negative integer")
        for name in (
            "device_id",
            "profile_name",
            "profile_version",
            "frequency_channel",
            "input_amplitude_channel",
            "output_amplitude_channel",
        ):
            _identifier(name, getattr(self, name))
        channels = (
            self.frequency_channel,
            self.input_amplitude_channel,
            self.output_amplitude_channel,
        )
        if len(set(channels)) != 3:
            raise ValidationError("frequency-response channels must be distinct")
        if self.amplitude_unit not in {
            MeasurementUnit.VOLT,
            MeasurementUnit.MILLIVOLT,
        }:
            raise ValidationError("amplitude_unit must be V or mV")
        minimum = _finite("frequency_minimum_hz", self.frequency_minimum_hz)
        maximum = _finite("frequency_maximum_hz", self.frequency_maximum_hz)
        cutoff = _finite("cutoff_frequency_hz", self.cutoff_frequency_hz)
        if not 0.0 < minimum < cutoff < maximum:
            raise ValidationError(
                "frequency bounds must satisfy 0 < minimum < cutoff < maximum"
            )
        amplitude = _finite("input_amplitude", self.input_amplitude)
        gain = _finite("passband_gain", self.passband_gain)
        maximum_amplitude = (
            3.3 if self.amplitude_unit is MeasurementUnit.VOLT else 3300.0
        )
        if amplitude <= 0.0 or gain <= 0.0:
            raise ValidationError("input_amplitude and passband_gain must be positive")
        if amplitude > maximum_amplitude or amplitude * gain > maximum_amplitude:
            raise ValidationError(
                "simulated input and passband output must stay within 3.3 V"
            )
        for name, value in (
            ("frequency_minimum_hz", minimum),
            ("frequency_maximum_hz", maximum),
            ("cutoff_frequency_hz", cutoff),
            ("input_amplitude", amplitude),
            ("passband_gain", gain),
        ):
            object.__setattr__(self, name, value)
        if self.schema_version != FREQUENCY_RESPONSE_SIMULATOR_CONFIG_SCHEMA_VERSION:
            raise ValidationError(
                "unsupported frequency-response simulator config: "
                f"{self.schema_version}"
            )

    def frequency_at(self, index: int) -> float:
        """Return one endpoint-inclusive logarithmic frequency point."""

        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < self.point_count
        ):
            raise ValidationError("frequency index is outside the configured sweep")
        fraction = index / (self.point_count - 1)
        return 10.0 ** (
            math.log10(self.frequency_minimum_hz)
            + fraction
            * (
                math.log10(self.frequency_maximum_hz)
                - math.log10(self.frequency_minimum_hz)
            )
        )

    def output_amplitude_at(self, index: int) -> float:
        """Return a reference-normalized deterministic single-pole response."""

        frequency = self.frequency_at(index)
        if index == 0:
            return self.input_amplitude * self.passband_gain
        log_normalized_square = _log_square_difference(
            frequency, self.frequency_minimum_hz
        ) - _log_square_difference(
            self.cutoff_frequency_hz, self.frequency_minimum_hz
        )
        if log_normalized_square >= 0.0:
            log_attenuation = -0.5 * (
                log_normalized_square
                + math.log1p(math.exp(-log_normalized_square))
            )
        else:
            log_attenuation = -0.5 * math.log1p(
                math.exp(log_normalized_square)
            )
        ratio = self.passband_gain * math.exp(log_attenuation)
        return self.input_amplitude * ratio


class FrequencyResponseSimulatorAdapter(DeviceAdapter):
    """Expose a synthetic three-channel sweep through the read-only adapter API."""

    def __init__(
        self,
        config: FrequencyResponseSimulatorConfig | None = None,
        *,
        clock: Clock | None = None,
    ) -> None:
        super().__init__(EvidenceSource.SYNTHETIC)
        selected = config or FrequencyResponseSimulatorConfig()
        if not isinstance(selected, FrequencyResponseSimulatorConfig):
            raise ValidationError("config must be a FrequencyResponseSimulatorConfig")
        if clock is not None and not callable(clock):
            raise ValidationError("clock must be callable")
        self._config = selected
        self._clock = clock or (lambda: DEFAULT_SIMULATOR_EPOCH)
        self._started_at: datetime | None = None
        self._cursors: dict[str, int] = {}
        amplitude_maximum = (
            3.3 if selected.amplitude_unit is MeasurementUnit.VOLT else 3300.0
        )
        self._capability_snapshot = DeviceCapabilities(
            selected.device_id,
            selected.profile_name,
            selected.profile_version,
            adc_channels=(
                selected.frequency_channel,
                selected.input_amplitude_channel,
                selected.output_amplitude_channel,
            ),
            safe_input_ranges=(
                ChannelRange(
                    selected.frequency_channel,
                    SafeRange(
                        selected.frequency_minimum_hz,
                        selected.frequency_maximum_hz,
                        MeasurementUnit.HERTZ,
                    ),
                ),
                ChannelRange(
                    selected.input_amplitude_channel,
                    SafeRange(0.0, amplitude_maximum, selected.amplitude_unit),
                ),
                ChannelRange(
                    selected.output_amplitude_channel,
                    SafeRange(0.0, amplitude_maximum, selected.amplitude_unit),
                ),
            ),
            supported_commands=frozenset({DeviceCommand.READ_MEASUREMENT}),
        )

    @property
    def frequency_response_config(self) -> FrequencyResponseSimulatorConfig:
        """Return the immutable configuration behind this synthetic source."""

        return self._config

    def _connect(self) -> None:
        started_at = self._clock()
        if not isinstance(started_at, datetime):
            raise AdapterConnectionError("simulator clock must return a datetime")
        if started_at.tzinfo is None or started_at.utcoffset() is None:
            raise AdapterConnectionError(
                "simulator clock must return a timezone-aware datetime"
            )
        self._started_at = started_at.astimezone(timezone.utc)
        self._cursors = dict.fromkeys(
            (
                self._config.frequency_channel,
                self._config.input_amplitude_channel,
                self._config.output_amplitude_channel,
            ),
            0,
        )

    def _disconnect(self) -> None:
        self._started_at = None
        self._cursors.clear()

    def _get_capabilities(self) -> DeviceCapabilities:
        return self._capability_snapshot

    def _read_measurement(self, channel: str) -> Measurement:
        index = self._cursors.get(channel)
        if index is None or self._started_at is None:
            raise AdapterStateError("frequency-response simulator is not connected")
        if index >= self._config.point_count:
            raise AdapterStateError(
                "frequency-response simulator has no further configured points"
            )
        if channel == self._config.frequency_channel:
            value = self._config.frequency_at(index)
            unit = MeasurementUnit.HERTZ
            role = "frequency"
        elif channel == self._config.input_amplitude_channel:
            value = self._config.input_amplitude
            unit = self._config.amplitude_unit
            role = "input-amplitude"
        elif channel == self._config.output_amplitude_channel:
            value = self._config.output_amplitude_at(index)
            unit = self._config.amplitude_unit
            role = "output-amplitude"
        else:  # pragma: no cover - public adapter preflight owns this invariant
            raise AdapterStateError("unknown frequency-response simulator channel")
        self._cursors[channel] = index + 1
        record_id = f"frequency-simulator-{role}-{index:08d}"
        return Measurement(
            record_id,
            record_id,
            self._started_at + timedelta(milliseconds=index * self._config.interval_ms),
            channel,
            value,
            unit,
            MeasurementStatus.VALID,
            EvidenceSource.SYNTHETIC,
        )


__all__ = [
    "FREQUENCY_RESPONSE_SIMULATOR_CONFIG_SCHEMA_VERSION",
    "FrequencyResponseSimulatorAdapter",
    "FrequencyResponseSimulatorConfig",
]
