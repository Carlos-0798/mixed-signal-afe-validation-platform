"""Run the shared read-only contract against CsvReplayAdapter."""

from pathlib import Path

from analog_validation import (
    CsvReplayAdapter,
    CsvReplayAdapterConfig,
    EvidenceSource,
    MeasurementUnit,
    ReplayChannelConfig,
    ReplayChannelKind,
    SafeRange,
    load_csv_replay,
)

from .adapter_contract import AdapterContractSpec, ReadOnlyAdapterContract

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "test-data" / "golden" / "csv_replay_v1_valid.csv"


def make_csv_replay() -> CsvReplayAdapter:
    """Create a fresh immediate-mode adapter for the shared contract."""

    config = CsvReplayAdapterConfig(
        channels=(
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
    )
    return CsvReplayAdapter(load_csv_replay(DATASET), config)


class TestCsvReplayAdapterContract(ReadOnlyAdapterContract):
    """Require CSV Replay to satisfy the same common adapter behavior."""

    contract_spec = AdapterContractSpec(
        factory=make_csv_replay,
        evidence_source=EvidenceSource.CSV_REPLAY,
        analog_channel="afe.ch0.input",
        analog_unit=MeasurementUnit.MILLIVOLT,
    )
