from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

import pytest

from analog_validation.adapters import (
    SimulatorAdapter,
    SimulatorConfig,
    SimulatorFaultMode,
    generate_afe_telemetry,
)
from analog_validation.domain import (
    EvidenceSource,
    MeasurementStatus,
    MeasurementUnit,
    QualityFlag,
)
from analog_validation.errors import (
    AdapterError,
    AdapterStateError,
    CrcMismatch,
    ValidationError,
)

FIXED_TIME = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def ready_adapter(config: SimulatorConfig) -> SimulatorAdapter:
    adapter = SimulatorAdapter(config, clock=lambda: FIXED_TIME)
    adapter.connect()
    adapter.get_capabilities()
    return adapter


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"gain": True}, "gain must be numeric"),
        ({"gain": "2"}, "gain must be numeric"),
        ({"gain": float("nan")}, "gain must be finite"),
        ({"gain": 0}, "gain must be greater than zero"),
        ({"offset_mv": float("inf")}, "offset_mv must be finite"),
        ({"noise_stddev_mv": -0.1}, "noise_stddev_mv must be at least 0.0"),
        ({"saturation_min_mv": -1}, "saturation_min_mv must be at least 0.0"),
        (
            {"saturation_min_mv": 100, "saturation_max_mv": 100},
            "saturation limits",
        ),
        ({"saturation_max_mv": 3301}, "saturation limits"),
        ({"hysteresis_low_mv": -1}, "hysteresis_low_mv must be at least 0.0"),
        (
            {"hysteresis_low_mv": 100, "hysteresis_high_mv": 100},
            "hysteresis thresholds",
        ),
        ({"hysteresis_high_mv": 3301}, "hysteresis thresholds"),
    ],
)
def test_config_rejects_invalid_nonideality_values(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        SimulatorConfig(**cast(Any, changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"output_channel": "afe.ch0.input"},
        {"threshold_channel": "afe.ch0.input"},
        {"threshold_channel": "afe.ch0.output"},
    ],
)
def test_config_requires_three_distinct_channels(changes: dict[str, str]) -> None:
    with pytest.raises(ValidationError, match="must be distinct"):
        SimulatorConfig(**cast(Any, changes))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"fault_mode": "CRC_ERROR"}, "SimulatorFaultMode"),
        ({"fault_every_n": 2}, "requires a non-NONE"),
        (
            {"fault_mode": SimulatorFaultMode.CRC_ERROR},
            "fault_mode requires fault_every_n",
        ),
        (
            {
                "fault_mode": SimulatorFaultMode.CRC_ERROR,
                "fault_every_n": True,
            },
            "fault_every_n must be an integer",
        ),
        (
            {"fault_mode": SimulatorFaultMode.CRC_ERROR, "fault_every_n": 0},
            "fault_every_n must be at least 1",
        ),
    ],
)
def test_config_rejects_inconsistent_fault_controls(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        SimulatorConfig(**cast(Any, changes))


def test_integer_inputs_are_normalized_to_floats() -> None:
    config = SimulatorConfig(
        gain=2,
        offset_mv=1,
        noise_stddev_mv=0,
        saturation_min_mv=1,
        saturation_max_mv=3000,
        hysteresis_low_mv=800,
        hysteresis_high_mv=900,
    )

    assert all(
        isinstance(value, float)
        for value in (
            config.gain,
            config.offset_mv,
            config.noise_stddev_mv,
            config.saturation_min_mv,
            config.saturation_max_mv,
            config.hysteresis_low_mv,
            config.hysteresis_high_mv,
        )
    )


def test_gain_offset_and_channel_streams_are_independent_and_aligned() -> None:
    config = SimulatorConfig(
        seed=430,
        interval_ms=10,
        gain=1.5,
        offset_mv=7.0,
        noise_stddev_mv=0.0,
        saturation_min_mv=0.0,
        saturation_max_mv=3300.0,
    )
    adapter = ready_adapter(config)

    inputs = [adapter.read_measurement(config.analog_channel) for _ in range(5)]
    outputs = [adapter.read_measurement(config.output_channel) for _ in range(5)]

    assert [item.timestamp for item in inputs] == [item.timestamp for item in outputs]
    assert [item.value for item in outputs] == [
        1.5 * cast(float, item.value) + 7.0 for item in inputs
    ]
    assert all(item.status is MeasurementStatus.VALID for item in outputs)
    assert all(item.quality_flags == frozenset() for item in outputs)


def test_nonzero_noise_is_seeded_and_reproducible() -> None:
    config = SimulatorConfig(
        seed=123,
        noise_stddev_mv=4.0,
        saturation_min_mv=0.0,
        saturation_max_mv=3300.0,
    )
    first = ready_adapter(config)
    second = ready_adapter(config)
    different = ready_adapter(
        SimulatorConfig(
            seed=124,
            noise_stddev_mv=4.0,
            saturation_min_mv=0.0,
            saturation_max_mv=3300.0,
        )
    )

    first_values = [
        first.read_measurement(config.output_channel).value for _ in range(10)
    ]
    second_values = [
        second.read_measurement(config.output_channel).value for _ in range(10)
    ]
    different_values = [
        different.read_measurement(config.output_channel).value for _ in range(10)
    ]

    assert first_values == second_values
    assert first_values != different_values


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        (
            SimulatorConfig(
                gain=5.0,
                offset_mv=0.0,
                saturation_min_mv=0.0,
                saturation_max_mv=1000.0,
            ),
            1000.0,
        ),
        (
            SimulatorConfig(
                gain=0.1,
                offset_mv=-100.0,
                saturation_min_mv=25.0,
                saturation_max_mv=3300.0,
            ),
            25.0,
        ),
    ],
)
def test_high_and_low_saturation_are_explicitly_flagged(
    config: SimulatorConfig, expected: float
) -> None:
    measurement = ready_adapter(config).read_measurement(config.output_channel)

    assert measurement.value == expected
    assert measurement.status is MeasurementStatus.SUSPECT
    assert measurement.quality_flags == frozenset({QualityFlag.SATURATED})
    assert measurement.source is EvidenceSource.SYNTHETIC
    assert not measurement.is_bench_evidence


def test_hysteresis_switches_at_thresholds_and_holds_inside_band() -> None:
    config = SimulatorConfig(
        hysteresis_low_mv=850.0,
        hysteresis_high_mv=950.0,
    )
    adapter = ready_adapter(config)
    input_values = [item.input_mv for item in generate_afe_telemetry(25)]

    measurements = [
        adapter.read_digital_state(config.threshold_channel) for _ in input_values
    ]

    expected: list[float] = []
    state = False
    for value in input_values:
        if not state and value >= 950:
            state = True
        elif state and value <= 850:
            state = False
        expected.append(float(state))
    assert [item.value for item in measurements] == expected
    assert expected[:4] == [0.0, 0.0, 1.0, 1.0]
    assert expected[21:24] == [1.0, 0.0, 0.0]
    assert all(item.unit is MeasurementUnit.BOOLEAN for item in measurements)
    assert all(item.source is EvidenceSource.SYNTHETIC for item in measurements)


def test_missing_sample_fault_returns_invalid_measurement_and_consumes_sample() -> None:
    config = SimulatorConfig(
        fault_mode=SimulatorFaultMode.MISSING_SAMPLE,
        fault_every_n=2,
    )
    adapter = ready_adapter(config)

    first = adapter.read_measurement(config.analog_channel)
    missing = adapter.read_measurement(config.analog_channel)
    third = adapter.read_measurement(config.analog_channel)

    assert first.value == 800.0
    assert missing.value is None
    assert missing.status is MeasurementStatus.INVALID
    assert missing.quality_flags == frozenset(
        {QualityFlag.COMMUNICATION_ERROR, QualityFlag.MISSING}
    )
    assert missing.source is EvidenceSource.SYNTHETIC
    assert third.value == 953.0


def test_missing_digital_sample_retains_boolean_unit() -> None:
    config = SimulatorConfig(
        fault_mode=SimulatorFaultMode.MISSING_SAMPLE,
        fault_every_n=1,
    )
    measurement = ready_adapter(config).read_digital_state(config.threshold_channel)

    assert measurement.value is None
    assert measurement.unit is MeasurementUnit.BOOLEAN
    assert measurement.status is MeasurementStatus.INVALID


def test_fault_cadence_is_counted_independently_per_channel() -> None:
    config = SimulatorConfig(
        fault_mode=SimulatorFaultMode.MISSING_SAMPLE,
        fault_every_n=2,
    )
    adapter = ready_adapter(config)

    first_input = adapter.read_measurement(config.analog_channel)
    first_output = adapter.read_measurement(config.output_channel)
    second_input = adapter.read_measurement(config.analog_channel)
    second_output = adapter.read_measurement(config.output_channel)

    assert first_input.status is MeasurementStatus.VALID
    assert first_output.value is not None
    assert second_input.value is None
    assert second_output.value is None


def test_communication_fault_raises_stable_error_and_consumes_sample() -> None:
    config = SimulatorConfig(
        fault_mode=SimulatorFaultMode.COMMUNICATION_ERROR,
        fault_every_n=2,
    )
    adapter = ready_adapter(config)

    assert adapter.read_measurement(config.analog_channel).value == 800.0
    with pytest.raises(AdapterError, match="injected simulator communication error"):
        adapter.read_measurement(config.analog_channel)
    assert adapter.read_measurement(config.analog_channel).value == 953.0


def test_crc_fault_raises_crc_mismatch() -> None:
    config = SimulatorConfig(
        fault_mode=SimulatorFaultMode.CRC_ERROR,
        fault_every_n=1,
    )
    adapter = ready_adapter(config)

    with pytest.raises(CrcMismatch, match="injected simulator CRC error"):
        adapter.read_measurement(config.output_channel)


def test_reconnect_resets_noise_hysteresis_and_all_channel_indices() -> None:
    config = SimulatorConfig(
        noise_stddev_mv=4.0,
        hysteresis_low_mv=850.0,
        hysteresis_high_mv=950.0,
    )
    adapter = ready_adapter(config)

    first_outputs = [
        adapter.read_measurement(config.output_channel) for _ in range(5)
    ]
    first_states = [
        adapter.read_digital_state(config.threshold_channel) for _ in range(25)
    ]
    adapter.disconnect()
    adapter.connect()
    adapter.get_capabilities()
    restarted_outputs = [
        adapter.read_measurement(config.output_channel) for _ in range(5)
    ]
    restarted_states = [
        adapter.read_digital_state(config.threshold_channel) for _ in range(25)
    ]

    assert restarted_outputs == first_outputs
    assert restarted_states == first_states


def test_protected_hooks_reject_uninitialized_internal_resources() -> None:
    config = SimulatorConfig()
    adapter = SimulatorAdapter(config, clock=lambda: FIXED_TIME)

    with pytest.raises(AdapterStateError, match="stream is not connected"):
        adapter._read_digital_state(config.threshold_channel)

    adapter.connect()
    with pytest.raises(AdapterStateError, match="noise source is not connected"):
        adapter._read_measurement(config.threshold_channel)
    with pytest.raises(AdapterStateError, match="hysteresis state is not connected"):
        adapter._read_digital_state(config.output_channel)

    adapter._started_at = None
    with pytest.raises(AdapterStateError, match="clock is not connected"):
        adapter._make_measurement(
            config.analog_channel,
            0,
            1.0,
            MeasurementUnit.MILLIVOLT,
            MeasurementStatus.VALID,
        )
