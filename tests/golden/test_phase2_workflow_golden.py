"""Freeze Phase 2 Simulator/CSV workflow meaning end to end."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from analog_validation import (
    AdapterState,
    ChannelReadRequest,
    CsvReplayAdapter,
    CsvReplayAdapterConfig,
    CsvReplayDataset,
    MeasurementUnit,
    ReadOperation,
    ReadWorkflowRequest,
    ReadWorkflowResult,
    ReplayChannelConfig,
    ReplayChannelKind,
    SafeRange,
    SimulatorAdapter,
    load_csv_replay,
    run_read_workflow,
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = ROOT / "test-data" / "golden"
EXPECTED: dict[str, Any] = json.loads(
    (GOLDEN_DIR / "phase2_workflow_v1.json").read_text(encoding="utf-8")
)


def _request() -> ReadWorkflowRequest:
    operations = {operation.value: operation for operation in ReadOperation}
    units = {unit.value: unit for unit in MeasurementUnit}
    requirements = tuple(
        ChannelReadRequest(channel, operations[operation], units[unit], count)
        for channel, operation, unit, count in EXPECTED["request"]["requirements"]
    )
    return ReadWorkflowRequest(
        requirements,
        request_id=EXPECTED["request"]["request_id"],
    )


def _replay_channels() -> tuple[ReplayChannelConfig, ...]:
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


def _normalize(result: ReadWorkflowResult) -> dict[str, Any]:
    return {
        "status": result.status.value,
        "device_id": result.capabilities.device_id,
        "profile": {
            "name": result.capabilities.profile_name,
            "version": result.capabilities.profile_version,
        },
        "evidence_source": result.evidence_source.value,
        "missing_requirements": list(result.missing_requirements),
        "measurements": [
            {
                "record_id": item.record_id,
                "raw_record_id": item.raw_record_id,
                "timestamp_utc": item.timestamp.isoformat().replace("+00:00", "Z"),
                "channel": item.channel,
                "value": item.value,
                "unit": item.unit.value,
                "status": item.status.value,
                "source": item.source.value,
                "quality_flags": sorted(
                    flag.value for flag in item.quality_flags
                ),
            }
            for item in result.measurements
        ],
    }


def test_phase2_workflow_golden_manifest_is_host_only_and_versioned() -> None:
    assert set(EXPECTED) == {
        "schema_version",
        "evidence_source",
        "request",
        "simulator",
        "csv_replay",
        "unsupported",
    }
    assert EXPECTED["schema_version"] == "phase2-workflow-golden.v1"
    assert EXPECTED["evidence_source"] == "HOST_TEST"
    assert all(
        section["evidence_source"] not in {
            "BENCH_DMM",
            "BENCH_CONTROLLER",
            "BENCH_SCOPE",
        }
        for section in (
            EXPECTED["simulator"],
            EXPECTED["csv_replay"],
            EXPECTED["unsupported"],
        )
    )


@pytest.mark.parametrize("source", ["simulator", "csv_replay"])
def test_phase2_completed_workflow_matches_frozen_meaning(source: str) -> None:
    adapter = (
        SimulatorAdapter()
        if source == "simulator"
        else CsvReplayAdapter(
            load_csv_replay(GOLDEN_DIR / "csv_replay_v1_valid.csv"),
            CsvReplayAdapterConfig(_replay_channels()),
        )
    )

    result = run_read_workflow(adapter, _request())

    assert _normalize(result) == EXPECTED[source]
    assert adapter.state is AdapterState.DISCONNECTED


def test_phase2_unsupported_workflow_matches_frozen_meaning() -> None:
    adapter = CsvReplayAdapter(
        CsvReplayDataset("empty", (), 0),
        CsvReplayAdapterConfig(()),
    )

    result = run_read_workflow(adapter, _request())

    assert _normalize(result) == EXPECTED["unsupported"]
    assert adapter.state is AdapterState.DISCONNECTED
