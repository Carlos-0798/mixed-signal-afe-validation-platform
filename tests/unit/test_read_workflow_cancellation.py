"""Cooperative read checkpoints stop acquisition without exporting partial results."""

from __future__ import annotations

from typing import Any, cast

import pytest

from analog_validation import (
    AdapterState,
    ChannelReadRequest,
    DeviceAdapter,
    Measurement,
    MeasurementUnit,
    ReadOperation,
    ReadWorkflowRequest,
    SimulatorAdapter,
    ValidationError,
    run_read_workflow,
)
from analog_validation_app import (
    ProductCancellationToken,
    ProductJobCancelled,
    ProductJobType,
    ProductSourceMode,
    ProductWorkflowConfiguration,
    prepare_product_job,
)


def _request(operation: ReadOperation = ReadOperation.ANALOG) -> ReadWorkflowRequest:
    return ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "afe.ch0.input"
                if operation is ReadOperation.ANALOG
                else "afe.ch0.threshold",
                operation,
                MeasurementUnit.MILLIVOLT
                if operation is ReadOperation.ANALOG
                else MeasurementUnit.BOOLEAN,
                5,
            ),
        )
    )


def test_read_checkpoint_is_validated_before_connecting() -> None:
    adapter = SimulatorAdapter()
    with pytest.raises(ValidationError, match="checkpoint must be callable"):
        run_read_workflow(adapter, _request(), checkpoint=cast(Any, object()))
    assert adapter.state is AdapterState.DISCONNECTED


def test_cancelled_read_checkpoint_does_not_connect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = SimulatorAdapter()
    cancellation = ProductCancellationToken()
    cancellation._request()

    def unexpected_connect(self: DeviceAdapter) -> None:
        pytest.fail("cancelled acquisition must not connect")

    monkeypatch.setattr(DeviceAdapter, "connect", unexpected_connect)
    with pytest.raises(ProductJobCancelled):
        run_read_workflow(
            adapter, _request(), checkpoint=cancellation.raise_if_cancelled
        )


@pytest.mark.parametrize("operation", tuple(ReadOperation))
def test_read_cancellation_stops_before_the_next_sample_and_disconnects(
    operation: ReadOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = SimulatorAdapter()
    cancellation = ProductCancellationToken()
    method = (
        "read_measurement"
        if operation is ReadOperation.ANALOG
        else "read_digital_state"
    )
    original = getattr(DeviceAdapter, method)
    acquired: list[Measurement] = []

    def cancel_after_read(self: DeviceAdapter, channel: str) -> Measurement:
        measurement = cast(Measurement, original(self, channel))
        acquired.append(measurement)
        cancellation._request()
        return measurement

    monkeypatch.setattr(DeviceAdapter, method, cancel_after_read)
    with pytest.raises(ProductJobCancelled):
        run_read_workflow(
            adapter,
            _request(operation),
            checkpoint=cancellation.raise_if_cancelled,
        )
    assert len(acquired) == 1
    assert adapter.state is AdapterState.DISCONNECTED


@pytest.mark.parametrize(
    "job_type",
    (
        ProductJobType.READ,
        ProductJobType.DC_ANALYSIS,
        ProductJobType.HYSTERESIS_ANALYSIS,
        ProductJobType.CALIBRATION_ANALYSIS,
        ProductJobType.FREQUENCY_RESPONSE_ANALYSIS,
    ),
)
def test_product_services_stop_acquisition_at_read_checkpoints_without_output(
    job_type: ProductJobType, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = prepare_product_job(
        ProductWorkflowConfiguration(ProductSourceMode.SIMULATOR, job_type),
        "cancel-at-first-sample",
    )
    cancellation = ProductCancellationToken()
    original = DeviceAdapter.read_measurement
    acquired: list[Measurement] = []
    adapters: list[DeviceAdapter] = []

    def cancel_after_read(self: DeviceAdapter, channel: str) -> Measurement:
        measurement = original(self, channel)
        acquired.append(measurement)
        adapters.append(self)
        cancellation._request()
        return measurement

    monkeypatch.setattr(DeviceAdapter, "read_measurement", cancel_after_read)
    service = prepared.service_factory(prepared.request)
    try:
        with pytest.raises(ProductJobCancelled):
            service.run(prepared.request, cancellation, lambda *args: None)
        assert len(acquired) == 1
        assert adapters[0].state is AdapterState.DISCONNECTED
        assert prepared.output_slot.value is None
    finally:
        service.cleanup()
