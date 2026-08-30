"""Integration proof that product adapters remain read-only for hysteresis."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from analog_validation import (
    CsvReplayAdapter,
    CsvReplayAdapterConfig,
    EvidenceSource,
    MeasurementUnit,
    ReplayChannelConfig,
    ReplayChannelKind,
    SafeRange,
    SimulatorAdapter,
    load_csv_replay,
)
from analog_validation import TestRunMetadata as RunMetadata
from analog_validation import TestRunOutcome as RunOutcome
from analog_validation.adapters import AdapterState, DeviceAdapter
from analog_validation.analysis import HysteresisAnalysisConfig
from analog_validation.config import (
    ChannelConfig,
    ChannelRole,
    ProfileConfig,
    TimeoutConfig,
    ValidationConfig,
)
from analog_validation.runners import HysteresisPlan, run_hysteresis

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 30, 22, 0, tzinfo=timezone.utc)
INPUT = "afe.ch0.input"
STATE = "afe.ch0.threshold"
STIMULUS = "afe.stimulus"


def plan() -> HysteresisPlan:
    return HysteresisPlan(
        "read-only-hysteresis",
        "1",
        STIMULUS,
        MeasurementUnit.MILLIVOLT,
        (1000, 1800, 2000),
        (2000, 1500, 1000),
        1,
        HysteresisAnalysisConfig(INPUT, STATE),
    )


def config(source: EvidenceSource) -> ValidationConfig:
    return ValidationConfig(
        "read-only-hysteresis",
        "1",
        ProfileConfig("afe", "1"),
        source,
        (
            ChannelConfig(INPUT, ChannelRole.ANALOG_INPUT, MeasurementUnit.MILLIVOLT),
            ChannelConfig(STATE, ChannelRole.DIGITAL_INPUT, MeasurementUnit.BOOLEAN),
            ChannelConfig(
                STIMULUS,
                ChannelRole.ANALOG_OUTPUT,
                MeasurementUnit.MILLIVOLT,
                safe_output_range=SafeRange(0, 3300, MeasurementUnit.MILLIVOLT),
            ),
        ),
        TimeoutConfig(settle_s=0),
        True,
    )


def metadata(source: EvidenceSource, device_id: str) -> RunMetadata:
    return RunMetadata(
        f"read-only-hysteresis-{source.value.lower()}",
        "hysteresis",
        "read-only-hysteresis",
        "1",
        NOW,
        NOW + timedelta(seconds=1),
        "0.1.0.dev0",
        device_id,
        "afe",
        "1",
        source,
    )


def csv_adapter() -> CsvReplayAdapter:
    dataset = load_csv_replay(ROOT / "test-data" / "golden" / "csv_replay_v1_valid.csv")
    return CsvReplayAdapter(
        dataset,
        CsvReplayAdapterConfig(
            channels=(
                ReplayChannelConfig(
                    INPUT,
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
                    STATE, ReplayChannelKind.DIGITAL, MeasurementUnit.BOOLEAN
                ),
            )
        ),
    )


@pytest.mark.parametrize(
    ("adapter", "source", "device_id"),
    [
        (SimulatorAdapter(), EvidenceSource.SYNTHETIC, "simulator-afe-1"),
        (csv_adapter(), EvidenceSource.CSV_REPLAY, "csv-replay-1"),
    ],
)
def test_read_only_product_adapters_are_unsupported_without_hysteresis_io(
    adapter: DeviceAdapter,
    source: EvidenceSource,
    device_id: str,
) -> None:
    result = run_hysteresis(
        adapter,
        plan(),
        config(source),
        metadata(source, device_id),
        settle=lambda _seconds: None,
    )
    assert result.outcome is RunOutcome.UNSUPPORTED
    assert result.measurements == ()
    assert result.completed_steps == ()
    assert result.test_run_result.evidence_record_ids == ()
    assert "command:SET_ANALOG_STIMULUS" in result.test_run_result.missing_requirements
    assert "command:SAFE_SHUTDOWN" in result.test_run_result.missing_requirements
    assert adapter.state is AdapterState.DISCONNECTED
