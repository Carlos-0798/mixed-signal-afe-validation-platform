"""Shared pytest contract inherited by every read-capable adapter."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

import pytest

from analog_validation.adapters import AdapterState, DeviceAdapter
from analog_validation.domain import (
    DeviceCommand,
    EvidenceSource,
    Measurement,
    MeasurementUnit,
)
from analog_validation.errors import AdapterStateError, CapabilityError


@dataclass(frozen=True, slots=True)
class AdapterContractSpec:
    """Facts needed to run the common read-only adapter contract."""

    factory: Callable[[], DeviceAdapter]
    evidence_source: EvidenceSource
    analog_channel: str
    analog_unit: MeasurementUnit


class ReadOnlyAdapterContract:
    """Reusable behavior suite for every adapter with an analog input.

    The class name deliberately does not start with ``Test`` so pytest will
    collect only concrete subclasses that provide ``contract_spec``.
    """

    contract_spec: ClassVar[AdapterContractSpec]

    def make_adapter(self) -> DeviceAdapter:
        """Create a fresh adapter through the concrete test specification."""

        adapter = self.contract_spec.factory()
        assert isinstance(adapter, DeviceAdapter)
        return adapter

    def connect_and_confirm(self, adapter: DeviceAdapter) -> None:
        """Reach the common read-capable state without adapter-specific calls."""

        adapter.connect()
        adapter.get_capabilities()

    def test_contract_initial_state_and_provenance(self) -> None:
        adapter = self.make_adapter()

        assert adapter.state is AdapterState.DISCONNECTED
        assert not adapter.is_connected
        assert adapter.evidence_source is self.contract_spec.evidence_source
        with pytest.raises(AdapterStateError, match="not been confirmed"):
            _ = adapter.capabilities

    def test_contract_connect_is_read_only(self) -> None:
        adapter = self.make_adapter()

        adapter.connect()

        assert adapter.state is AdapterState.CONNECTED_READ_ONLY
        assert adapter.is_connected
        with pytest.raises(AdapterStateError, match="cannot connect"):
            adapter.connect()

    def test_contract_capabilities_are_explicit_and_cached(self) -> None:
        adapter = self.make_adapter()
        adapter.connect()

        capabilities = adapter.get_capabilities()

        assert adapter.state is AdapterState.CAPABILITIES_CONFIRMED
        assert adapter.get_capabilities() is capabilities
        assert self.contract_spec.analog_channel in capabilities.adc_channels
        assert capabilities.supports(DeviceCommand.READ_MEASUREMENT)
        assert (
            capabilities.get_input_range(self.contract_spec.analog_channel).unit
            is self.contract_spec.analog_unit
        )

    def test_contract_read_requires_capability_confirmation(self) -> None:
        adapter = self.make_adapter()
        with pytest.raises(AdapterStateError, match="read measurement"):
            adapter.read_measurement(self.contract_spec.analog_channel)

        adapter.connect()
        with pytest.raises(AdapterStateError, match="read measurement"):
            adapter.read_measurement(self.contract_spec.analog_channel)

    def test_contract_read_returns_typed_provenance_aware_measurement(self) -> None:
        adapter = self.make_adapter()
        self.connect_and_confirm(adapter)

        measurement = adapter.read_measurement(self.contract_spec.analog_channel)

        assert isinstance(measurement, Measurement)
        assert measurement.channel == self.contract_spec.analog_channel
        assert measurement.unit is self.contract_spec.analog_unit
        assert measurement.source is self.contract_spec.evidence_source
        assert measurement.is_bench_evidence is (
            self.contract_spec.evidence_source.is_bench_evidence
        )
        assert adapter.state is AdapterState.CAPABILITIES_CONFIRMED

    def test_contract_unknown_channel_is_capability_error(self) -> None:
        adapter = self.make_adapter()
        self.connect_and_confirm(adapter)

        with pytest.raises(CapabilityError, match="ADC channel"):
            adapter.read_measurement("contract-unknown-channel")

    def test_contract_shutdown_is_idempotent_and_blocks_reads(self) -> None:
        adapter = self.make_adapter()
        self.connect_and_confirm(adapter)

        adapter.safe_shutdown()
        adapter.safe_shutdown()

        assert adapter.state is AdapterState.SAFE_SHUTDOWN
        assert adapter.is_connected
        with pytest.raises(AdapterStateError, match="read measurement"):
            adapter.read_measurement(self.contract_spec.analog_channel)

    def test_contract_disconnect_is_idempotent_and_reconnectable(self) -> None:
        adapter = self.make_adapter()
        adapter.disconnect()
        self.connect_and_confirm(adapter)

        adapter.disconnect()
        adapter.disconnect()

        assert adapter.state is AdapterState.DISCONNECTED
        assert not adapter.is_connected
        with pytest.raises(AdapterStateError, match="not been confirmed"):
            _ = adapter.capabilities

        self.connect_and_confirm(adapter)
        measurement = adapter.read_measurement(self.contract_spec.analog_channel)
        assert measurement.source is self.contract_spec.evidence_source


__all__ = ["AdapterContractSpec", "ReadOnlyAdapterContract"]
