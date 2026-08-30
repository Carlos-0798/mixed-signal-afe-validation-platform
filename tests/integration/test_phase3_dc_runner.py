"""Integration checks that read-only product adapters remain output-safe."""

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
from analog_validation import (
    TestRunMetadata as RunMetadata,
)
from analog_validation import (
    TestRunOutcome as RunOutcome,
)
from analog_validation.adapters import AdapterState, DeviceAdapter
from analog_validation.analysis import DCSweepAnalysisConfig
from analog_validation.config import (
    ChannelConfig,
    ChannelRole,
    ProfileConfig,
    TimeoutConfig,
    ValidationConfig,
)
from analog_validation.runners import DCSweepPlan, run_dc_sweep

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 30, 21, 0, tzinfo=timezone.utc)
INPUT = "afe.ch0.input"
OUTPUT = "afe.ch0.output"
STIMULUS = "afe.stimulus"


def plan() -> DCSweepPlan:
    return DCSweepPlan(
        plan_id="read-only-proof",
        plan_version="1",
        stimulus_channel=STIMULUS,
        unit=MeasurementUnit.MILLIVOLT,
        setpoints=(100.0, 200.0, 300.0),
        repetitions=1,
        analysis_config=DCSweepAnalysisConfig(
            input_channel=INPUT,
            output_channel=OUTPUT,
            low_output_limit=0.0,
            high_output_limit=3300.0,
        ),
    )


def config(source: EvidenceSource) -> ValidationConfig:
    return ValidationConfig(
        config_id="read-only-proof",
        config_version="1",
        profile=ProfileConfig("afe", "1"),
        evidence_source=source,
        channels=(
            ChannelConfig(INPUT, ChannelRole.ANALOG_INPUT, MeasurementUnit.MILLIVOLT),
            ChannelConfig(OUTPUT, ChannelRole.ANALOG_INPUT, MeasurementUnit.MILLIVOLT),
            ChannelConfig(
                STIMULUS,
                ChannelRole.ANALOG_OUTPUT,
                MeasurementUnit.MILLIVOLT,
                safe_output_range=SafeRange(
                    0.0, 1000.0, MeasurementUnit.MILLIVOLT
                ),
            ),
        ),
        timeouts=TimeoutConfig(settle_s=0.0),
        allow_output=True,
    )


def metadata(source: EvidenceSource, device_id: str) -> RunMetadata:
    return RunMetadata(
        run_id=f"read-only-{source.value.lower()}",
        test_type="dc-sweep",
        configuration_id="read-only-proof",
        configuration_version="1",
        started_at=NOW,
        ended_at=NOW + timedelta(seconds=1),
        software_version="0.1.0.dev0",
        device_id=device_id,
        profile_name="afe",
        profile_version="1",
        evidence_source=source,
    )


def csv_adapter() -> CsvReplayAdapter:
    dataset = load_csv_replay(
        ROOT / "test-data" / "golden" / "csv_replay_v1_valid.csv"
    )
    adapter_config = CsvReplayAdapterConfig(
        channels=(
            ReplayChannelConfig(
                INPUT,
                ReplayChannelKind.ANALOG,
                MeasurementUnit.MILLIVOLT,
                SafeRange(0.0, 3300.0, MeasurementUnit.MILLIVOLT),
            ),
            ReplayChannelConfig(
                OUTPUT,
                ReplayChannelKind.ANALOG,
                MeasurementUnit.MILLIVOLT,
                SafeRange(0.0, 3300.0, MeasurementUnit.MILLIVOLT),
            ),
            ReplayChannelConfig(
                "afe.ch0.threshold",
                ReplayChannelKind.DIGITAL,
                MeasurementUnit.BOOLEAN,
            ),
        )
    )
    return CsvReplayAdapter(dataset, adapter_config)


@pytest.mark.parametrize(
    ("adapter", "source", "device_id"),
    [
        (SimulatorAdapter(), EvidenceSource.SYNTHETIC, "simulator-afe-1"),
        (csv_adapter(), EvidenceSource.CSV_REPLAY, "csv-replay-1"),
    ],
)
def test_read_only_product_adapters_are_unsupported_without_partial_io(
    adapter: DeviceAdapter,
    source: EvidenceSource,
    device_id: str,
) -> None:
    result = run_dc_sweep(
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
    assert result.test_run_result.metadata.evidence_source is source
    assert "command:SET_ANALOG_STIMULUS" in (
        result.test_run_result.missing_requirements
    )
    assert "command:SAFE_SHUTDOWN" in result.test_run_result.missing_requirements
    assert adapter.state is AdapterState.DISCONNECTED
