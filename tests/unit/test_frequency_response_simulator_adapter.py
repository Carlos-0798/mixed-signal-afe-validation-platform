"""Tests for the deterministic read-only frequency-response simulator."""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime, timezone
from itertools import pairwise
from typing import Any, cast

import pytest

from analog_validation import (
    EvidenceSource,
    FrequencyResponseSimulatorAdapter,
    FrequencyResponseSimulatorConfig,
    MeasurementUnit,
)
from analog_validation.errors import (
    AdapterConnectionError,
    AdapterStateError,
    ValidationError,
)


def test_frequency_simulator_exposes_bounded_read_only_log_sweep() -> None:
    config = FrequencyResponseSimulatorConfig(point_count=5)
    adapter = FrequencyResponseSimulatorAdapter(config)

    adapter.connect()
    capabilities = adapter.get_capabilities()
    frequencies = tuple(
        adapter.read_measurement(config.frequency_channel).value for _ in range(5)
    )
    inputs = tuple(
        adapter.read_measurement(config.input_amplitude_channel).value for _ in range(5)
    )
    outputs = tuple(
        adapter.read_measurement(config.output_amplitude_channel).value for _ in range(5)
    )
    adapter.disconnect()

    assert capabilities.is_read_only
    assert capabilities.adc_channels == (
        config.frequency_channel,
        config.input_amplitude_channel,
        config.output_amplitude_channel,
    )
    assert frequencies == pytest.approx((10.0, 100.0, 1000.0, 10000.0, 100000.0))
    assert inputs == (1000.0,) * 5
    numeric_outputs = tuple(cast(float, value) for value in outputs)
    assert numeric_outputs[0] == pytest.approx(1000.0)
    assert numeric_outputs[2] == pytest.approx(1000.0 / math.sqrt(2.0))
    assert all(left > right for left, right in pairwise(numeric_outputs))


def test_frequency_simulator_measurements_are_deterministic_and_synthetic() -> None:
    epoch = datetime(2026, 9, 5, 17, 0, tzinfo=timezone.utc)
    config = FrequencyResponseSimulatorConfig(point_count=3)
    snapshots = []
    for _ in range(2):
        adapter = FrequencyResponseSimulatorAdapter(config, clock=lambda: epoch)
        adapter.connect()
        adapter.get_capabilities()
        snapshots.append(
            tuple(
                adapter.read_measurement(channel)
                for channel in (
                    config.frequency_channel,
                    config.input_amplitude_channel,
                    config.output_amplitude_channel,
                )
            )
        )
        adapter.disconnect()

    assert snapshots[0] == snapshots[1]
    assert all(value.source is EvidenceSource.SYNTHETIC for value in snapshots[0])
    assert tuple(value.unit for value in snapshots[0]) == (
        MeasurementUnit.HERTZ,
        MeasurementUnit.MILLIVOLT,
        MeasurementUnit.MILLIVOLT,
    )
    assert len({value.record_id for value in snapshots[0]}) == 3


@pytest.mark.parametrize(
    "changes",
    [
        {"point_count": True},
        {"point_count": 1},
        {"frequency_channel": " frequency "},
        {"input_amplitude": True},
        {"input_amplitude": math.inf},
        {"frequency_minimum_hz": 0.0},
        {"cutoff_frequency_hz": 10.0},
        {"frequency_maximum_hz": 1000.0},
        {"input_amplitude": 0.0},
        {"passband_gain": -1.0},
        {"input_amplitude": 3301.0},
        {"amplitude_unit": MeasurementUnit.HERTZ},
        {"frequency_channel": "afe.ch0.input"},
        {"interval_ms": -1},
        {"schema_version": "future"},
    ],
)
def test_frequency_simulator_config_rejects_invalid_values(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        replace(FrequencyResponseSimulatorConfig(), **cast(Any, changes))


def test_frequency_simulator_index_and_clock_are_validated() -> None:
    config = FrequencyResponseSimulatorConfig()
    for index in (-1, True, config.point_count):
        with pytest.raises(ValidationError):
            config.frequency_at(index)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        FrequencyResponseSimulatorAdapter("bad")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        FrequencyResponseSimulatorAdapter(clock="bad")  # type: ignore[arg-type]

    naive_timestamp = datetime(2026, 1, 1)  # noqa: DTZ001 - invalid clock case
    adapter = FrequencyResponseSimulatorAdapter(clock=lambda: naive_timestamp)
    with pytest.raises(AdapterConnectionError):
        adapter.connect()

    adapter = FrequencyResponseSimulatorAdapter(clock=lambda: cast(Any, object()))
    with pytest.raises(AdapterConnectionError, match="datetime"):
        adapter.connect()


def test_frequency_simulator_avoids_overflow_for_finite_extreme_frequencies() -> None:
    config = FrequencyResponseSimulatorConfig(
        point_count=10,
        frequency_minimum_hz=1.0e-200,
        cutoff_frequency_hz=1.0,
        frequency_maximum_hz=1.0e200,
    )

    first = config.output_amplitude_at(0)
    last = config.output_amplitude_at(config.point_count - 1)

    assert first == config.input_amplitude * config.passband_gain
    assert math.isfinite(last)
    assert 0.0 < last < first


def test_frequency_simulator_exposes_config_and_rejects_invalid_cursor_state() -> None:
    config = FrequencyResponseSimulatorConfig(point_count=3)
    adapter = FrequencyResponseSimulatorAdapter(config)

    assert adapter.frequency_response_config is config
    with pytest.raises(AdapterStateError, match="not connected"):
        adapter._read_measurement(config.frequency_channel)

    adapter.connect()
    adapter.get_capabilities()
    for _ in range(config.point_count):
        adapter.read_measurement(config.frequency_channel)
    with pytest.raises(AdapterStateError, match="no further"):
        adapter.read_measurement(config.frequency_channel)
    adapter.disconnect()
