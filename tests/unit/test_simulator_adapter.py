from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest

from analog_validation.adapters import (
    DEFAULT_SIMULATOR_EPOCH,
    SIMULATOR_CONFIG_SCHEMA_VERSION,
    SimulatorAdapter,
    SimulatorConfig,
    SimulatorFaultMode,
    generate_afe_telemetry,
)
from analog_validation.domain import (
    DeviceCommand,
    EvidenceSource,
    MeasurementUnit,
)
from analog_validation.errors import (
    AdapterConnectionError,
    AdapterStateError,
    ValidationError,
)

FIXED_TIME = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def read_values(adapter: SimulatorAdapter, count: int) -> tuple[float | None, ...]:
    adapter.connect()
    adapter.get_capabilities()
    return tuple(
        adapter.read_measurement(adapter.simulator_config.analog_channel).value
        for _ in range(count)
    )


def test_simulator_config_defaults_are_versioned_and_immutable() -> None:
    config = SimulatorConfig()

    assert config.seed == 430
    assert config.interval_ms == 100
    assert config.device_id == "simulator-afe-1"
    assert config.profile_name == "afe"
    assert config.profile_version == "1"
    assert config.analog_channel == "afe.ch0.input"
    assert config.output_channel == "afe.ch0.output"
    assert config.threshold_channel == "afe.ch0.threshold"
    assert config.gain == 2.0
    assert config.offset_mv == 12.0
    assert config.noise_stddev_mv == 0.0
    assert config.saturation_min_mv == 25.0
    assert config.saturation_max_mv == 3275.0
    assert config.hysteresis_low_mv == 900.0
    assert config.hysteresis_high_mv == 1000.0
    assert config.fault_mode is SimulatorFaultMode.NONE
    assert config.fault_every_n is None
    assert config.schema_version == SIMULATOR_CONFIG_SCHEMA_VERSION
    with pytest.raises(FrozenInstanceError):
        config.seed = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"seed": True}, "seed must be an integer"),
        ({"seed": 4.3}, "seed must be an integer"),
        ({"interval_ms": True}, "interval_ms must be an integer"),
        ({"interval_ms": 1.5}, "interval_ms must be an integer"),
        ({"interval_ms": -1}, "at least 0"),
    ],
)
def test_simulator_config_rejects_invalid_numbers(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        SimulatorConfig(**cast(Any, changes))


@pytest.mark.parametrize(
    "field",
    [
        "device_id",
        "profile_name",
        "profile_version",
        "analog_channel",
        "output_channel",
        "threshold_channel",
    ],
)
@pytest.mark.parametrize("value", ["", " invalid"])
def test_simulator_config_rejects_invalid_identifiers(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        SimulatorConfig(**cast(Any, {field: value}))


def test_simulator_config_rejects_unknown_schema() -> None:
    with pytest.raises(ValidationError, match="schema version"):
        SimulatorConfig(schema_version="simulator-config.v2")


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ((-1, 100, 430), "count must be at least 0"),
        ((cast(Any, True), 100, 430), "count must be an integer"),
        ((1, -1, 430), "interval_ms must be at least 0"),
        ((1, cast(Any, 1.2), 430), "interval_ms must be an integer"),
        ((1, 100, cast(Any, "430")), "seed must be an integer"),
    ],
)
def test_generator_rejects_invalid_controls(
    args: tuple[int, int, int], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        generate_afe_telemetry(*args)


def test_generator_is_finite_deterministic_and_interval_aware() -> None:
    assert list(generate_afe_telemetry(0)) == []
    first = list(generate_afe_telemetry(5, interval_ms=10, seed=430))
    second = list(generate_afe_telemetry(5, interval_ms=10, seed=430))
    slower = list(generate_afe_telemetry(5, interval_ms=20, seed=430))
    different = list(generate_afe_telemetry(5, interval_ms=10, seed=431))

    assert first == second
    assert first != different
    assert [item.time_ms for item in first] == [0, 10, 20, 30, 40]
    assert [item.time_ms for item in slower] == [0, 20, 40, 60, 80]
    assert [item.input_mv for item in first] == [item.input_mv for item in slower]


def test_default_simulator_capabilities_are_explicit_and_read_only() -> None:
    adapter = SimulatorAdapter()

    adapter.connect()
    capabilities = adapter.get_capabilities()

    assert adapter.evidence_source is EvidenceSource.SYNTHETIC
    assert adapter.simulator_config == SimulatorConfig()
    assert capabilities.device_id == "simulator-afe-1"
    assert capabilities.profile_name == "afe"
    assert capabilities.profile_version == "1"
    assert capabilities.adc_channels == ("afe.ch0.input", "afe.ch0.output")
    assert capabilities.digital_input_channels == ("afe.ch0.threshold",)
    assert capabilities.supported_commands == frozenset(
        {DeviceCommand.READ_DIGITAL_STATE, DeviceCommand.READ_MEASUREMENT}
    )
    assert capabilities.is_read_only
    assert not capabilities.automated_output_allowed
    assert (
        capabilities.get_input_range("afe.ch0.input").unit
        is MeasurementUnit.MILLIVOLT
    )
    assert (
        capabilities.get_input_range("afe.ch0.output").unit
        is MeasurementUnit.MILLIVOLT
    )


def test_custom_identity_and_channel_are_reflected_in_capabilities() -> None:
    config = SimulatorConfig(
        seed=7,
        interval_ms=25,
        device_id="demo-sim",
        profile_name="demo",
        profile_version="2",
        analog_channel="demo.input",
    )
    adapter = SimulatorAdapter(config, clock=lambda: FIXED_TIME)

    adapter.connect()
    capabilities = adapter.get_capabilities()
    measurement = adapter.read_measurement("demo.input")

    assert capabilities.device_id == "demo-sim"
    assert capabilities.profile_name == "demo"
    assert capabilities.profile_version == "2"
    assert capabilities.adc_channels == ("demo.input", "afe.ch0.output")
    assert measurement.channel == "demo.input"


def test_constructor_rejects_invalid_config_or_clock() -> None:
    with pytest.raises(ValidationError, match="SimulatorConfig"):
        SimulatorAdapter(cast(SimulatorConfig, object()))
    with pytest.raises(ValidationError, match="clock must be callable"):
        SimulatorAdapter(clock=cast(Any, 5))


@pytest.mark.parametrize(
    "clock_value",
    [object(), FIXED_TIME.replace(tzinfo=None)],
)
def test_connect_rejects_invalid_clock_result_and_resets_state(
    clock_value: object,
) -> None:
    adapter = SimulatorAdapter(clock=lambda: cast(Any, clock_value))

    with pytest.raises(AdapterConnectionError, match="clock"):
        adapter.connect()

    assert not adapter.is_connected


def test_clock_is_normalized_to_utc_and_interval_advances_timestamp() -> None:
    eastern = timezone(timedelta(hours=-4))
    started = datetime(2026, 8, 30, 8, 0, tzinfo=eastern)
    adapter = SimulatorAdapter(
        SimulatorConfig(interval_ms=25),
        clock=lambda: started,
    )
    adapter.connect()
    adapter.get_capabilities()

    measurements = [adapter.read_measurement("afe.ch0.input") for _ in range(3)]

    assert [item.timestamp for item in measurements] == [
        FIXED_TIME,
        FIXED_TIME + timedelta(milliseconds=25),
        FIXED_TIME + timedelta(milliseconds=50),
    ]
    assert [item.record_id for item in measurements] == [
        "simulator-00000000",
        "simulator-00000001",
        "simulator-00000002",
    ]
    assert all(item.record_id == item.raw_record_id for item in measurements)
    assert all(item.source is EvidenceSource.SYNTHETIC for item in measurements)
    assert not any(item.is_bench_evidence for item in measurements)


def test_same_seed_and_clock_produce_identical_measurements() -> None:
    config = SimulatorConfig(seed=430, interval_ms=10)
    first = SimulatorAdapter(config, clock=lambda: FIXED_TIME)
    second = SimulatorAdapter(config, clock=lambda: FIXED_TIME)

    first_values = read_values(first, 20)
    second_values = read_values(second, 20)

    assert first_values == second_values


def test_different_seed_changes_values_without_changing_schedule() -> None:
    first = SimulatorAdapter(SimulatorConfig(seed=430), clock=lambda: FIXED_TIME)
    second = SimulatorAdapter(SimulatorConfig(seed=431), clock=lambda: FIXED_TIME)

    first_values = read_values(first, 10)
    second_values = read_values(second, 10)

    assert first_values != second_values


def test_disconnect_and_reconnect_restart_the_deterministic_sequence() -> None:
    adapter = SimulatorAdapter(clock=lambda: FIXED_TIME)
    first_value = read_values(adapter, 1)
    adapter.disconnect()

    restarted_value = read_values(adapter, 1)

    assert restarted_value == first_value


def test_protected_read_hook_still_rejects_missing_stream() -> None:
    adapter = SimulatorAdapter()

    with pytest.raises(AdapterStateError, match="not connected"):
        adapter._read_measurement("afe.ch0.input")


def test_default_clock_is_a_fixed_reproducible_epoch() -> None:
    adapter = SimulatorAdapter()
    adapter.connect()
    adapter.get_capabilities()

    measurement = adapter.read_measurement("afe.ch0.input")

    assert measurement.timestamp == DEFAULT_SIMULATOR_EPOCH
