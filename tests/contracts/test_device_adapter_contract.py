"""Reference execution proving the reusable adapter contract is collectible."""

from __future__ import annotations

from datetime import datetime, timezone

from analog_validation.adapters import DeviceAdapter
from analog_validation.domain import (
    ChannelRange,
    DeviceCapabilities,
    DeviceCommand,
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
    SafeRange,
)

from .adapter_contract import AdapterContractSpec, ReadOnlyAdapterContract


class ContractReferenceAdapter(DeviceAdapter):
    """Small host-only adapter used only to execute the common test suite."""

    def __init__(self) -> None:
        super().__init__(EvidenceSource.HOST_TEST)
        self._read_index = 0
        self._reference_capabilities = DeviceCapabilities(
            "contract-reference",
            "contract",
            "1",
            adc_channels=("adc0",),
            safe_input_ranges=(
                ChannelRange(
                    "adc0", SafeRange(0.0, 3.3, MeasurementUnit.VOLT)
                ),
            ),
            supported_commands=frozenset({DeviceCommand.READ_MEASUREMENT}),
        )

    def _connect(self) -> None:
        pass

    def _disconnect(self) -> None:
        pass

    def _get_capabilities(self) -> DeviceCapabilities:
        return self._reference_capabilities

    def _read_measurement(self, channel: str) -> Measurement:
        self._read_index += 1
        record_id = f"contract-reference-{self._read_index}"
        return Measurement(
            record_id,
            record_id,
            datetime(2026, 8, 29, tzinfo=timezone.utc),
            channel,
            1.25,
            MeasurementUnit.VOLT,
            MeasurementStatus.VALID,
            EvidenceSource.HOST_TEST,
        )


class TestReferenceAdapterContract(ReadOnlyAdapterContract):
    """Run every reusable contract check against a minimal valid adapter."""

    contract_spec = AdapterContractSpec(
        factory=ContractReferenceAdapter,
        evidence_source=EvidenceSource.HOST_TEST,
        analog_channel="adc0",
        analog_unit=MeasurementUnit.VOLT,
    )
