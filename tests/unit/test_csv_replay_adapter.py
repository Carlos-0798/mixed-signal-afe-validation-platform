from __future__ import annotations

import math
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import pytest

from analog_validation import (
    CSV_REPLAY_ADAPTER_CONFIG_SCHEMA_VERSION,
    AdapterError,
    AdapterStateError,
    CapabilityError,
    ConfigurationError,
    CsvReplayAdapter,
    CsvReplayAdapterConfig,
    CsvReplayDataset,
    CsvReplayRecord,
    DeviceCommand,
    EvidenceSource,
    MeasurementStatus,
    MeasurementUnit,
    QualityFlag,
    ReplayChannelConfig,
    ReplayChannelKind,
    ReplayEndOfData,
    ReplayTimingMode,
    SafeRange,
    load_csv_replay,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET_FILE = ROOT / "test-data" / "golden" / "csv_replay_v1_valid.csv"
UTC_TIME = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def channel_configs() -> tuple[ReplayChannelConfig, ...]:
    return (
        ReplayChannelConfig(
            "afe.ch0.input",
            ReplayChannelKind.ANALOG,
            MeasurementUnit.MILLIVOLT,
            SafeRange(0, 3300, MeasurementUnit.MILLIVOLT),
        ),
        ReplayChannelConfig(
            "afe.ch0.output",
            ReplayChannelKind.ANALOG,
            MeasurementUnit.MILLIVOLT,
            SafeRange(0, 3300, MeasurementUnit.MILLIVOLT),
        ),
        ReplayChannelConfig(
            "afe.ch0.threshold",
            ReplayChannelKind.DIGITAL,
            MeasurementUnit.BOOLEAN,
        ),
    )


def make_config(**changes: Any) -> CsvReplayAdapterConfig:
    values: dict[str, Any] = {"channels": channel_configs()}
    values.update(changes)
    return CsvReplayAdapterConfig(**values)


def ready_adapter(
    *,
    config: CsvReplayAdapterConfig | None = None,
    dataset: CsvReplayDataset | None = None,
    sleeper: Any = None,
) -> CsvReplayAdapter:
    if config is None:
        config = make_config()
    if dataset is None:
        dataset = load_csv_replay(DATASET_FILE)
    adapter = (
        CsvReplayAdapter(dataset, config)
        if sleeper is None
        else CsvReplayAdapter(dataset, config, sleeper=sleeper)
    )
    adapter.connect()
    adapter.get_capabilities()
    return adapter


def make_record(
    record_id: str = "record-001",
    *,
    timestamp: datetime = UTC_TIME,
    channel: str = "afe.ch0.input",
    value: float | None = 1.0,
    unit: MeasurementUnit = MeasurementUnit.MILLIVOLT,
    status: MeasurementStatus = MeasurementStatus.VALID,
    source: EvidenceSource = EvidenceSource.SYNTHETIC,
    flags: frozenset[QualityFlag] = frozenset(),
) -> CsvReplayRecord:
    return CsvReplayRecord(
        record_id,
        record_id,
        timestamp,
        channel,
        value,
        unit,
        status,
        source,
        flags,
    )


def test_public_enums_and_default_adapter_config_are_explicit_and_frozen() -> None:
    config = make_config()

    assert ReplayChannelKind.ANALOG.value == "ANALOG"
    assert ReplayChannelKind.DIGITAL.value == "DIGITAL"
    assert ReplayTimingMode.IMMEDIATE.value == "IMMEDIATE"
    assert ReplayTimingMode.SCALED.value == "SCALED"
    assert config.device_id == "csv-replay-1"
    assert config.profile_name == "afe"
    assert config.profile_version == "1"
    assert config.timing_mode is ReplayTimingMode.IMMEDIATE
    assert config.speed_multiplier == 1.0
    assert config.schema_version == CSV_REPLAY_ADAPTER_CONFIG_SCHEMA_VERSION
    assert isinstance(config.channels, tuple)
    with pytest.raises(FrozenInstanceError):
        config.speed_multiplier = 2.0  # type: ignore[misc]


@pytest.mark.parametrize("name", ["", " leading", "trailing "])
def test_channel_config_rejects_invalid_name(name: str) -> None:
    with pytest.raises(ConfigurationError, match="channel name"):
        ReplayChannelConfig(
            name,
            ReplayChannelKind.ANALOG,
            MeasurementUnit.VOLT,
            SafeRange(0, 3.3, MeasurementUnit.VOLT),
        )


def test_channel_config_requires_typed_kind_unit_and_role_consistency() -> None:
    with pytest.raises(ConfigurationError, match="ReplayChannelKind"):
        ReplayChannelConfig(
            "ch",
            cast(Any, "ANALOG"),
            MeasurementUnit.VOLT,
            SafeRange(0, 3.3, MeasurementUnit.VOLT),
        )
    with pytest.raises(ConfigurationError, match="MeasurementUnit"):
        ReplayChannelConfig(
            "ch",
            ReplayChannelKind.ANALOG,
            cast(Any, "V"),
            SafeRange(0, 3.3, MeasurementUnit.VOLT),
        )
    with pytest.raises(ConfigurationError, match="require a safe_input_range"):
        ReplayChannelConfig(
            "ch", ReplayChannelKind.ANALOG, MeasurementUnit.VOLT
        )
    with pytest.raises(ConfigurationError, match="unit must match"):
        ReplayChannelConfig(
            "ch",
            ReplayChannelKind.ANALOG,
            MeasurementUnit.VOLT,
            SafeRange(0, 3300, MeasurementUnit.MILLIVOLT),
        )
    with pytest.raises(ConfigurationError, match="cannot use bool"):
        ReplayChannelConfig(
            "ch",
            ReplayChannelKind.ANALOG,
            MeasurementUnit.BOOLEAN,
            SafeRange(0, 1, MeasurementUnit.BOOLEAN),
        )
    with pytest.raises(ConfigurationError, match="must use bool"):
        ReplayChannelConfig(
            "ch", ReplayChannelKind.DIGITAL, MeasurementUnit.VOLT
        )
    with pytest.raises(ConfigurationError, match="cannot define"):
        ReplayChannelConfig(
            "ch",
            ReplayChannelKind.DIGITAL,
            MeasurementUnit.BOOLEAN,
            SafeRange(0, 1, MeasurementUnit.BOOLEAN),
        )


@pytest.mark.parametrize("field", ["device_id", "profile_name", "profile_version"])
@pytest.mark.parametrize("value", ["", " invalid"])
def test_adapter_config_rejects_invalid_identity(field: str, value: str) -> None:
    with pytest.raises(ConfigurationError, match=field):
        make_config(**{field: value})


def test_adapter_config_freezes_iterable_and_rejects_bad_channels() -> None:
    mutable = list(channel_configs())
    config = CsvReplayAdapterConfig(cast(Any, mutable))
    mutable.clear()
    assert len(config.channels) == 3

    with pytest.raises(ConfigurationError, match="iterable"):
        CsvReplayAdapterConfig(cast(Any, "channels"))
    with pytest.raises(ConfigurationError, match="ReplayChannelConfig"):
        CsvReplayAdapterConfig(cast(Any, (object(),)))
    with pytest.raises(ConfigurationError, match="unique"):
        CsvReplayAdapterConfig((channel_configs()[0], channel_configs()[0]))


@pytest.mark.parametrize("value", [True, "2", math.nan, math.inf, 0, -1])
def test_adapter_config_rejects_invalid_speed(value: object) -> None:
    with pytest.raises(ConfigurationError, match="speed_multiplier"):
        make_config(speed_multiplier=value)


def test_adapter_config_rejects_timing_type_and_schema_version() -> None:
    with pytest.raises(ConfigurationError, match="ReplayTimingMode"):
        make_config(timing_mode=cast(Any, "IMMEDIATE"))
    with pytest.raises(ConfigurationError, match="config version"):
        make_config(schema_version="csv-replay-adapter-config.v2")


def test_constructor_requires_typed_inputs_and_callable_sleeper() -> None:
    dataset = load_csv_replay(DATASET_FILE)
    config = make_config()
    with pytest.raises(ConfigurationError, match="CsvReplayDataset"):
        CsvReplayAdapter(cast(Any, object()), config)
    with pytest.raises(ConfigurationError, match="CsvReplayAdapterConfig"):
        CsvReplayAdapter(dataset, cast(Any, object()))
    with pytest.raises(ConfigurationError, match="sleeper"):
        CsvReplayAdapter(dataset, config, sleeper=cast(Any, 1))


def test_constructor_rejects_undeclared_channel_and_unit_mismatch() -> None:
    dataset = load_csv_replay(DATASET_FILE)
    input_only = make_config(channels=(channel_configs()[0],))
    with pytest.raises(ConfigurationError, match="not declared"):
        CsvReplayAdapter(dataset, input_only)

    channels = list(channel_configs())
    channels[1] = ReplayChannelConfig(
        "afe.ch0.output",
        ReplayChannelKind.ANALOG,
        MeasurementUnit.VOLT,
        SafeRange(0, 3.3, MeasurementUnit.VOLT),
    )
    with pytest.raises(ConfigurationError, match="does not match configured unit"):
        CsvReplayAdapter(dataset, make_config(channels=tuple(channels)))


def test_capabilities_are_explicit_read_only_and_controller_neutral() -> None:
    adapter = ready_adapter()
    capabilities = adapter.capabilities

    assert adapter.evidence_source is EvidenceSource.CSV_REPLAY
    assert adapter.dataset.dataset_id == "afe-demo-001"
    assert adapter.replay_config == make_config()
    assert adapter.speed_multiplier == 1.0
    assert not adapter.is_paused
    assert not adapter.at_end
    assert capabilities.device_id == "csv-replay-1"
    assert capabilities.profile_name == "afe"
    assert capabilities.profile_version == "1"
    assert capabilities.adc_channels == ("afe.ch0.input", "afe.ch0.output")
    assert capabilities.digital_input_channels == ("afe.ch0.threshold",)
    assert capabilities.supported_commands == frozenset(
        {DeviceCommand.READ_MEASUREMENT, DeviceCommand.READ_DIGITAL_STATE}
    )
    assert capabilities.get_input_range("afe.ch0.input") == SafeRange(
        0, 3300, MeasurementUnit.MILLIVOLT
    )
    assert capabilities.is_read_only
    assert not capabilities.automated_output_allowed


def test_replayed_measurement_preserves_content_and_uses_current_replay_source() -> None:
    adapter = ready_adapter()

    first = adapter.read_measurement("afe.ch0.input")
    missing = adapter.read_measurement("afe.ch0.input")
    saturated = adapter.read_measurement("afe.ch0.output")
    non_finite = adapter.read_measurement("afe.ch0.output")
    digital = adapter.read_digital_state("afe.ch0.threshold")

    assert first.record_id == "csv-replay:afe-demo-001:input-000"
    assert first.raw_record_id == "input-000"
    assert first.timestamp == UTC_TIME
    assert first.value == 800.0
    assert first.source is EvidenceSource.CSV_REPLAY
    assert first.is_derived
    assert not first.is_bench_evidence
    assert missing.value is None
    assert missing.status is MeasurementStatus.INVALID
    assert missing.quality_flags == frozenset(
        {QualityFlag.MISSING, QualityFlag.COMMUNICATION_ERROR}
    )
    assert saturated.status is MeasurementStatus.SUSPECT
    assert saturated.quality_flags == frozenset({QualityFlag.SATURATED})
    assert math.isnan(cast(float, non_finite.value))
    assert non_finite.source is EvidenceSource.CSV_REPLAY
    assert digital.value == 1.0
    assert digital.unit is MeasurementUnit.BOOLEAN
    assert digital.source is EvidenceSource.CSV_REPLAY


def test_declared_bench_source_cannot_elevate_replayed_measurement() -> None:
    source_record = make_record(source=EvidenceSource.BENCH_DMM)
    dataset = CsvReplayDataset("declared-bench", (source_record,), 1)
    config = CsvReplayAdapterConfig((channel_configs()[0],))
    adapter = ready_adapter(dataset=dataset, config=config)

    measurement = adapter.read_measurement("afe.ch0.input")

    assert adapter.dataset.records[0].declared_source is EvidenceSource.BENCH_DMM
    assert measurement.source is EvidenceSource.CSV_REPLAY
    assert not measurement.is_bench_evidence


def test_channel_cursors_are_independent_and_end_state_is_explicit() -> None:
    adapter = ready_adapter()

    adapter.read_measurement("afe.ch0.input")
    assert not adapter.channel_at_end("afe.ch0.input")
    adapter.read_measurement("afe.ch0.input")
    assert adapter.channel_at_end("afe.ch0.input")
    assert not adapter.channel_at_end("afe.ch0.output")

    first_output = adapter.read_measurement("afe.ch0.output")
    assert first_output.raw_record_id == "output-001"
    adapter.read_measurement("afe.ch0.output")
    adapter.read_digital_state("afe.ch0.threshold")

    assert adapter.at_end
    with pytest.raises(ReplayEndOfData, match="reached EOF"):
        adapter.read_measurement("afe.ch0.input")
    assert adapter.at_end


def test_configured_empty_channel_reports_eof_without_fake_measurement() -> None:
    dataset = CsvReplayDataset("empty", (), 0)
    config = CsvReplayAdapterConfig((channel_configs()[0],))
    adapter = ready_adapter(dataset=dataset, config=config)

    assert adapter.at_end
    assert adapter.channel_at_end("afe.ch0.input")
    with pytest.raises(ReplayEndOfData):
        adapter.read_measurement("afe.ch0.input")


def test_empty_config_has_no_read_commands_and_is_complete_after_connect() -> None:
    dataset = CsvReplayDataset("empty", (), 0)
    adapter = ready_adapter(
        dataset=dataset,
        config=CsvReplayAdapterConfig(()),
    )

    assert adapter.capabilities.adc_channels == ()
    assert adapter.capabilities.digital_input_channels == ()
    assert adapter.capabilities.supported_commands == frozenset()
    assert adapter.at_end


def test_pause_resume_is_idempotent_and_preserves_cursor() -> None:
    adapter = ready_adapter()

    adapter.pause()
    adapter.pause()
    assert adapter.is_paused
    with pytest.raises(AdapterStateError, match="paused"):
        adapter.read_measurement("afe.ch0.input")
    assert not adapter.channel_at_end("afe.ch0.input")

    adapter.resume()
    adapter.resume()
    assert not adapter.is_paused
    assert adapter.read_measurement("afe.ch0.input").raw_record_id == "input-000"

    adapter.pause()
    adapter.disconnect()
    assert not adapter.is_paused
    assert not adapter.at_end
    adapter.connect()
    adapter.get_capabilities()
    assert not adapter.is_paused
    assert adapter.read_measurement("afe.ch0.input").raw_record_id == "input-000"


@pytest.mark.parametrize("operation", ["pause", "resume", "speed", "end"])
def test_runtime_controls_require_connected_active_state(operation: str) -> None:
    adapter = CsvReplayAdapter(load_csv_replay(DATASET_FILE), make_config())

    with pytest.raises(AdapterStateError, match="cannot"):
        if operation == "pause":
            adapter.pause()
        elif operation == "resume":
            adapter.resume()
        elif operation == "speed":
            adapter.set_speed_multiplier(2.0)
        else:
            adapter.channel_at_end("afe.ch0.input")

    adapter.connect()
    adapter.get_capabilities()
    adapter.safe_shutdown()
    with pytest.raises(AdapterStateError, match="cannot"):
        if operation == "pause":
            adapter.pause()
        elif operation == "resume":
            adapter.resume()
        elif operation == "speed":
            adapter.set_speed_multiplier(2.0)
        else:
            adapter.channel_at_end("afe.ch0.input")


def test_channel_end_query_validates_identifier_and_capability() -> None:
    adapter = ready_adapter()

    for channel in (cast(Any, 1), "", " bad"):
        with pytest.raises(ConfigurationError, match="channel"):
            adapter.channel_at_end(channel)
    with pytest.raises(CapabilityError, match="not available"):
        adapter.channel_at_end("unknown")


@pytest.mark.parametrize("value", [True, "2", math.nan, math.inf, 0, -1])
def test_runtime_speed_change_rejects_invalid_values(value: object) -> None:
    adapter = ready_adapter()

    with pytest.raises(ConfigurationError, match="speed_multiplier"):
        adapter.set_speed_multiplier(cast(Any, value))


def test_runtime_speed_change_is_applied_and_reconnect_resets_it() -> None:
    adapter = ready_adapter(config=make_config(speed_multiplier=2))

    assert adapter.speed_multiplier == 2.0
    adapter.set_speed_multiplier(4)
    assert adapter.speed_multiplier == 4.0
    adapter.disconnect()
    assert adapter.speed_multiplier == 2.0
    adapter.connect()
    assert adapter.speed_multiplier == 2.0


def test_immediate_mode_never_calls_sleeper() -> None:
    calls: list[float] = []
    adapter = ready_adapter(sleeper=calls.append)

    adapter.read_measurement("afe.ch0.input")
    adapter.read_measurement("afe.ch0.input")

    assert calls == []


def test_scaled_mode_uses_per_channel_timestamp_delta_and_current_speed() -> None:
    calls: list[float] = []
    config = make_config(
        timing_mode=ReplayTimingMode.SCALED,
        speed_multiplier=2,
    )
    adapter = ready_adapter(config=config, sleeper=calls.append)

    adapter.read_measurement("afe.ch0.output")
    adapter.set_speed_multiplier(4)
    adapter.read_measurement("afe.ch0.output")
    adapter.read_measurement("afe.ch0.input")
    adapter.read_measurement("afe.ch0.input")

    assert calls == pytest.approx([0.05, 0.05])


def test_scaled_mode_skips_sleep_for_equal_timestamps() -> None:
    calls: list[float] = []
    first = make_record()
    second = make_record("record-002")
    dataset = CsvReplayDataset("same-time", (first, second), 2)
    config = CsvReplayAdapterConfig(
        (channel_configs()[0],), timing_mode=ReplayTimingMode.SCALED
    )
    adapter = ready_adapter(dataset=dataset, config=config, sleeper=calls.append)

    adapter.read_measurement("afe.ch0.input")
    adapter.read_measurement("afe.ch0.input")

    assert calls == []


def test_sleeper_failure_is_wrapped_and_does_not_consume_record() -> None:
    calls = 0

    def fail_sleep(delay: float) -> None:
        nonlocal calls
        calls += 1
        assert delay > 0
        raise RuntimeError("simulated timer failure")

    config = make_config(timing_mode=ReplayTimingMode.SCALED)
    adapter = ready_adapter(config=config, sleeper=fail_sleep)
    adapter.read_measurement("afe.ch0.input")

    with pytest.raises(AdapterError, match="read measurement failed") as captured:
        adapter.read_measurement("afe.ch0.input")
    assert isinstance(captured.value.__cause__, RuntimeError)
    assert calls == 1
    assert not adapter.channel_at_end("afe.ch0.input")
    with pytest.raises(AdapterError):
        adapter.read_measurement("afe.ch0.input")
    assert calls == 2


def test_protected_read_hook_rejects_missing_connection_state() -> None:
    adapter = CsvReplayAdapter(load_csv_replay(DATASET_FILE), make_config())

    with pytest.raises(AdapterStateError, match="not connected"):
        adapter._read_measurement("afe.ch0.input")
