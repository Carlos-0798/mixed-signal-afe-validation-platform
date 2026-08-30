"""Run the shared adapter contract against the real SimulatorAdapter."""

from datetime import datetime, timezone

from analog_validation.adapters import SimulatorAdapter, SimulatorConfig
from analog_validation.domain import EvidenceSource, MeasurementUnit

from .adapter_contract import AdapterContractSpec, ReadOnlyAdapterContract

FIXED_TIME = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def make_simulator() -> SimulatorAdapter:
    """Create a fresh deterministic simulator for shared contract tests."""

    return SimulatorAdapter(
        SimulatorConfig(seed=430, interval_ms=10),
        clock=lambda: FIXED_TIME,
    )


class TestSimulatorAdapterContract(ReadOnlyAdapterContract):
    """Require the product simulator to satisfy every shared behavior."""

    contract_spec = AdapterContractSpec(
        factory=make_simulator,
        evidence_source=EvidenceSource.SYNTHETIC,
        analog_channel="afe.ch0.input",
        analog_unit=MeasurementUnit.MILLIVOLT,
    )
