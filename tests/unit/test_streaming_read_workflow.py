from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

import pytest

from analog_validation import (
    MAX_READ_WORKFLOW_INTERVAL_SECONDS,
    AdapterStateError,
    ChannelRange,
    ChannelReadRequest,
    DeviceAdapter,
    DeviceCapabilities,
    DeviceCommand,
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
    ReadOperation,
    ReadWorkflowRequest,
    ReadWorkflowStatus,
    ReplayEndOfData,
    SafeRange,
    SimulatorAdapter,
    ValidationError,
    run_streaming_read_workflow,
)

NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)


class FiniteStreamingAdapter(DeviceAdapter):
    def __init__(self) -> None:
        super().__init__(EvidenceSource.SYNTHETIC)
        self.analog_reads = 0
        self.digital_reads = 0

    def _connect(self) -> None:
        return None

    def _disconnect(self) -> None:
        return None

    def _get_capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities(
            "finite-stream",
            "afe",
            "1",
            adc_channels=("input",),
            digital_input_channels=("state",),
            safe_input_ranges=(
                ChannelRange(
                    "input",
                    SafeRange(0.0, 10.0, MeasurementUnit.MILLIVOLT),
                ),
            ),
            supported_commands=frozenset(
                {DeviceCommand.READ_MEASUREMENT, DeviceCommand.READ_DIGITAL_STATE}
            ),
        )

    def _read_measurement(self, channel: str) -> Measurement:
        self.analog_reads += 1
        return Measurement(
            f"analog-{self.analog_reads}",
            f"analog-{self.analog_reads}",
            NOW,
            channel,
            float(self.analog_reads),
            MeasurementUnit.MILLIVOLT,
            MeasurementStatus.VALID,
            EvidenceSource.SYNTHETIC,
        )

    def _read_digital_state(self, channel: str) -> Measurement:
        self.digital_reads += 1
        if self.digital_reads > 1:
            raise ReplayEndOfData("finite digital stream ended")
        return Measurement(
            "digital-1",
            "digital-1",
            NOW,
            channel,
            1.0,
            MeasurementUnit.BOOLEAN,
            MeasurementStatus.VALID,
            EvidenceSource.SYNTHETIC,
        )


def request(*, count: int = 3) -> ReadWorkflowRequest:
    return ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "afe.ch0.input",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                count,
            ),
            ChannelReadRequest(
                "afe.ch0.output",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                count,
            ),
        ),
        request_id="streaming-test",
    )


def test_streaming_read_interleaves_channels_observes_and_waits_between_cycles() -> None:
    adapter = SimulatorAdapter()
    observed: list[tuple[int, str]] = []
    checkpoints: list[str] = []
    waits: list[float] = []

    result = run_streaming_read_workflow(
        adapter,
        request(),
        sample_interval_seconds=0.25,
        checkpoint=lambda: checkpoints.append("checked"),
        on_measurement=lambda cycle, value: observed.append((cycle, value.channel)),
        wait_interval=waits.append,
    )

    assert result.status is ReadWorkflowStatus.COMPLETED
    assert adapter.is_connected is False
    assert [(cycle, channel) for cycle, channel in observed] == [
        (0, "afe.ch0.input"),
        (0, "afe.ch0.output"),
        (1, "afe.ch0.input"),
        (1, "afe.ch0.output"),
        (2, "afe.ch0.input"),
        (2, "afe.ch0.output"),
    ]
    assert [value.channel for value in result.measurements] == [
        channel for _cycle, channel in observed
    ]
    assert waits == [0.25, 0.25]
    assert len(checkpoints) == 9


def test_streaming_read_unsupported_preflight_performs_no_reads_or_waits() -> None:
    adapter = SimulatorAdapter()
    observed: list[Measurement] = []
    waits: list[float] = []
    unsupported = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "not.available",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                2,
            ),
        )
    )

    result = run_streaming_read_workflow(
        adapter,
        unsupported,
        sample_interval_seconds=1.0,
        on_measurement=lambda _cycle, value: observed.append(value),
        wait_interval=waits.append,
    )

    assert result.status is ReadWorkflowStatus.UNSUPPORTED
    assert result.measurements == ()
    assert result.missing_requirements == ("analog-channel:not.available",)
    assert observed == []
    assert waits == []
    assert adapter.is_connected is False


def test_streaming_read_reports_exact_remaining_samples_at_end_of_data() -> None:
    adapter = FiniteStreamingAdapter()
    observed: list[tuple[int, str]] = []
    waits: list[float] = []
    streaming_request = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "input",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                2,
            ),
            ChannelReadRequest(
                "state",
                ReadOperation.DIGITAL,
                MeasurementUnit.BOOLEAN,
                2,
            ),
        )
    )

    result = run_streaming_read_workflow(
        adapter,
        streaming_request,
        sample_interval_seconds=0.1,
        on_measurement=lambda cycle, value: observed.append((cycle, value.channel)),
        wait_interval=waits.append,
    )

    assert result.status is ReadWorkflowStatus.INCOMPLETE
    assert tuple(value.channel for value in result.measurements) == (
        "input",
        "state",
        "input",
    )
    assert result.missing_requirements == ("samples:DIGITAL:state:1",)
    assert observed == [(0, "input"), (0, "state"), (1, "input")]
    assert waits == [0.1]
    assert adapter.is_connected is False


@pytest.mark.parametrize(
    "value",
    [
        True,
        "0",
        -0.1,
        float("nan"),
        float("inf"),
        MAX_READ_WORKFLOW_INTERVAL_SECONDS + 0.1,
    ],
)
def test_streaming_read_rejects_invalid_interval(value: object) -> None:
    with pytest.raises(ValidationError, match="sample_interval_seconds"):
        run_streaming_read_workflow(
            SimulatorAdapter(), request(), sample_interval_seconds=cast(Any, value)
        )


def test_streaming_read_rejects_invalid_inputs_before_opening_adapter() -> None:
    adapter = SimulatorAdapter()
    with pytest.raises(ValidationError, match="DeviceAdapter"):
        run_streaming_read_workflow(cast(Any, object()), request())
    with pytest.raises(ValidationError, match="ReadWorkflowRequest"):
        run_streaming_read_workflow(adapter, cast(Any, object()))
    unequal = ReadWorkflowRequest(
        (
            request().requirements[0],
            ChannelReadRequest(
                "afe.ch0.output",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                2,
            ),
        )
    )
    with pytest.raises(ValidationError, match="equal sample counts"):
        run_streaming_read_workflow(adapter, unequal)
    for name, values in (
        ("checkpoint", {"checkpoint": object()}),
        ("on_measurement", {"on_measurement": object()}),
        ("wait_interval", {"wait_interval": object()}),
    ):
        with pytest.raises(ValidationError, match=name):
            run_streaming_read_workflow(adapter, request(), **cast(Any, values))
    assert adapter.is_connected is False

    adapter.connect()
    with pytest.raises(AdapterStateError, match="requires a disconnected adapter"):
        run_streaming_read_workflow(adapter, request())
    assert adapter.is_connected is True
    adapter.disconnect()


def test_streaming_read_callback_and_wait_failures_still_disconnect() -> None:
    observer_adapter = SimulatorAdapter()

    def fail_observer(_cycle: int, _measurement: Measurement) -> None:
        raise RuntimeError("observer failed")

    with pytest.raises(RuntimeError, match="observer failed"):
        run_streaming_read_workflow(
            observer_adapter,
            request(count=1),
            on_measurement=fail_observer,
        )
    assert observer_adapter.is_connected is False

    waiter_adapter = SimulatorAdapter()

    def fail_waiter(_seconds: float) -> None:
        raise RuntimeError("wait failed")

    with pytest.raises(RuntimeError, match="wait failed"):
        run_streaming_read_workflow(
            waiter_adapter,
            request(count=2),
            sample_interval_seconds=0.1,
            wait_interval=fail_waiter,
        )
    assert waiter_adapter.is_connected is False


def test_streaming_read_checkpoint_can_stop_before_resource_open() -> None:
    adapter = SimulatorAdapter()

    def stop() -> None:
        raise RuntimeError("stop before open")

    with pytest.raises(RuntimeError, match="stop before open"):
        run_streaming_read_workflow(adapter, request(), checkpoint=stop)
    assert adapter.is_connected is False
