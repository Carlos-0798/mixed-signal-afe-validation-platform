"""Drive Simulator and CSV Replay through one upper-layer read workflow."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from analog_validation import (
    AdapterError,
    AdapterState,
    ChannelReadRequest,
    CsvReplayAdapter,
    CsvReplayAdapterConfig,
    CsvReplayDataset,
    EvidenceSource,
    MeasurementUnit,
    ReadOperation,
    ReadWorkflowRequest,
    ReadWorkflowStatus,
    ReplayChannelConfig,
    ReplayChannelKind,
    SafeRange,
    SimulatorAdapter,
    SimulatorConfig,
    SimulatorFaultMode,
    load_csv_replay,
    run_read_workflow,
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_REPLAY = ROOT / "test-data" / "golden" / "csv_replay_v1_valid.csv"
AdapterFactory = Callable[[], SimulatorAdapter | CsvReplayAdapter]


def shared_request() -> ReadWorkflowRequest:
    return ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "afe.ch0.input",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                2,
            ),
            ChannelReadRequest(
                "afe.ch0.output",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                2,
            ),
            ChannelReadRequest(
                "afe.ch0.threshold",
                ReadOperation.DIGITAL,
                MeasurementUnit.BOOLEAN,
            ),
        ),
        request_id="phase2-shared-read",
    )


def replay_channels() -> tuple[ReplayChannelConfig, ...]:
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


def make_replay() -> CsvReplayAdapter:
    return CsvReplayAdapter(
        load_csv_replay(GOLDEN_REPLAY),
        CsvReplayAdapterConfig(replay_channels()),
    )


@pytest.mark.parametrize(
    ("factory", "expected_source"),
    [
        (SimulatorAdapter, EvidenceSource.SYNTHETIC),
        (make_replay, EvidenceSource.CSV_REPLAY),
    ],
)
def test_same_workflow_completes_for_simulator_and_csv_replay(
    factory: AdapterFactory,
    expected_source: EvidenceSource,
) -> None:
    adapter = factory()

    result = run_read_workflow(adapter, shared_request())

    assert result.status is ReadWorkflowStatus.COMPLETED
    assert result.is_completed
    assert len(result.measurements) == 5
    assert [item.channel for item in result.measurements] == [
        "afe.ch0.input",
        "afe.ch0.input",
        "afe.ch0.output",
        "afe.ch0.output",
        "afe.ch0.threshold",
    ]
    assert all(item.source is expected_source for item in result.measurements)
    assert result.evidence_source is expected_source
    assert result.capabilities.profile_name == "afe"
    assert result.missing_requirements == ()
    assert adapter.state is AdapterState.DISCONNECTED


def test_preflight_returns_atomic_unsupported_without_consuming_available_data() -> None:
    dataset = CsvReplayDataset(
        "one-input",
        (load_csv_replay(GOLDEN_REPLAY).records[0],),
        1,
    )
    adapter = CsvReplayAdapter(
        dataset,
        CsvReplayAdapterConfig((replay_channels()[0],)),
    )
    request = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "afe.ch0.input",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
            ),
            ChannelReadRequest(
                "missing.state",
                ReadOperation.DIGITAL,
                MeasurementUnit.BOOLEAN,
            ),
        )
    )

    result = run_read_workflow(adapter, request)

    assert result.status is ReadWorkflowStatus.UNSUPPORTED
    assert result.measurements == ()
    assert result.missing_requirements == (
        "command:READ_DIGITAL_STATE",
        "digital-channel:missing.state",
    )
    assert adapter.state is AdapterState.DISCONNECTED

    adapter.connect()
    adapter.get_capabilities()
    assert adapter.read_measurement("afe.ch0.input").raw_record_id == "input-000"
    adapter.disconnect()


def test_preflight_reports_each_missing_channel_and_deduplicates_commands() -> None:
    adapter = CsvReplayAdapter(
        CsvReplayDataset("empty", (), 0),
        CsvReplayAdapterConfig(()),
    )
    request = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "input-a", ReadOperation.ANALOG, MeasurementUnit.MILLIVOLT
            ),
            ChannelReadRequest(
                "input-b", ReadOperation.ANALOG, MeasurementUnit.VOLT
            ),
            ChannelReadRequest(
                "state", ReadOperation.DIGITAL, MeasurementUnit.BOOLEAN
            ),
        )
    )

    result = run_read_workflow(adapter, request)

    assert result.missing_requirements == (
        "command:READ_MEASUREMENT",
        "analog-channel:input-a",
        "analog-channel:input-b",
        "command:READ_DIGITAL_STATE",
        "digital-channel:state",
    )
    assert result.is_unsupported
    assert adapter.state is AdapterState.DISCONNECTED


def test_preflight_reports_requested_analog_unit_mismatch() -> None:
    dataset = CsvReplayDataset(
        "one-input",
        (load_csv_replay(GOLDEN_REPLAY).records[0],),
        1,
    )
    adapter = CsvReplayAdapter(
        dataset,
        CsvReplayAdapterConfig((replay_channels()[0],)),
    )
    request = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "afe.ch0.input", ReadOperation.ANALOG, MeasurementUnit.VOLT
            ),
        )
    )

    result = run_read_workflow(adapter, request)

    assert result.status is ReadWorkflowStatus.UNSUPPORTED
    assert result.missing_requirements == ("analog-unit:afe.ch0.input:V",)
    assert adapter.state is AdapterState.DISCONNECTED


def test_replay_eof_returns_incomplete_with_partial_data_and_all_remaining_counts() -> None:
    request = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "afe.ch0.input",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                3,
            ),
            ChannelReadRequest(
                "afe.ch0.output",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                2,
            ),
            ChannelReadRequest(
                "afe.ch0.threshold",
                ReadOperation.DIGITAL,
                MeasurementUnit.BOOLEAN,
            ),
        )
    )
    adapter = make_replay()

    result = run_read_workflow(adapter, request)

    assert result.status is ReadWorkflowStatus.INCOMPLETE
    assert len(result.measurements) == 2
    assert result.missing_requirements == (
        "samples:ANALOG:afe.ch0.input:1",
        "samples:ANALOG:afe.ch0.output:2",
        "samples:DIGITAL:afe.ch0.threshold:1",
    )
    assert adapter.state is AdapterState.DISCONNECTED


def test_empty_replay_returns_incomplete_without_fabricating_measurements() -> None:
    adapter = CsvReplayAdapter(
        CsvReplayDataset("empty", (), 0),
        CsvReplayAdapterConfig((replay_channels()[0],)),
    )
    request = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "afe.ch0.input",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                2,
            ),
        )
    )

    result = run_read_workflow(adapter, request)

    assert result.status is ReadWorkflowStatus.INCOMPLETE
    assert result.measurements == ()
    assert result.missing_requirements == (
        "samples:ANALOG:afe.ch0.input:2",
    )
    assert adapter.state is AdapterState.DISCONNECTED


def test_execution_error_is_not_mislabeled_unsupported_and_adapter_is_cleaned_up() -> None:
    config = SimulatorConfig(
        fault_mode=SimulatorFaultMode.COMMUNICATION_ERROR,
        fault_every_n=1,
    )
    adapter = SimulatorAdapter(config)
    request = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                config.analog_channel,
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
            ),
        )
    )

    with pytest.raises(AdapterError, match="communication error"):
        run_read_workflow(adapter, request)

    assert adapter.state is AdapterState.DISCONNECTED
