from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import Any, cast

import pytest

from analog_validation import (
    READ_WORKFLOW_SCHEMA_VERSION,
    AdapterStateError,
    ChannelRange,
    ChannelReadRequest,
    DeviceCapabilities,
    DeviceCommand,
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
    ReadOperation,
    ReadWorkflowRequest,
    ReadWorkflowResult,
    ReadWorkflowStatus,
    SafeRange,
    SimulatorAdapter,
    ValidationError,
    run_read_workflow,
)

UTC_TIME = datetime(2026, 8, 30, 18, 0, tzinfo=timezone.utc)


def analog_request(
    channel: str = "input",
    *,
    unit: MeasurementUnit = MeasurementUnit.MILLIVOLT,
    count: int = 1,
) -> ChannelReadRequest:
    return ChannelReadRequest(channel, ReadOperation.ANALOG, unit, count)


def digital_request(channel: str = "state", *, count: int = 1) -> ChannelReadRequest:
    return ChannelReadRequest(
        channel,
        ReadOperation.DIGITAL,
        MeasurementUnit.BOOLEAN,
        count,
    )


def workflow_request() -> ReadWorkflowRequest:
    return ReadWorkflowRequest((analog_request(count=2), digital_request()))


def capabilities() -> DeviceCapabilities:
    return DeviceCapabilities(
        "device-1",
        "afe",
        "1",
        adc_channels=("input",),
        digital_input_channels=("state",),
        safe_input_ranges=(
            ChannelRange(
                "input", SafeRange(0, 3300, MeasurementUnit.MILLIVOLT)
            ),
        ),
        supported_commands=frozenset(
            {DeviceCommand.READ_MEASUREMENT, DeviceCommand.READ_DIGITAL_STATE}
        ),
    )


def analog_only_capabilities() -> DeviceCapabilities:
    return DeviceCapabilities(
        "device-1",
        "afe",
        "1",
        adc_channels=("input",),
        safe_input_ranges=(
            ChannelRange(
                "input", SafeRange(0, 3300, MeasurementUnit.MILLIVOLT)
            ),
        ),
        supported_commands=frozenset({DeviceCommand.READ_MEASUREMENT}),
    )


def measurement(
    record_id: str,
    channel: str,
    unit: MeasurementUnit,
    *,
    source: EvidenceSource = EvidenceSource.SYNTHETIC,
) -> Measurement:
    return Measurement(
        record_id,
        record_id,
        UTC_TIME,
        channel,
        1.0,
        unit,
        MeasurementStatus.VALID,
        source,
    )


def completed_measurements() -> tuple[Measurement, ...]:
    return (
        measurement("m-1", "input", MeasurementUnit.MILLIVOLT),
        measurement("m-2", "input", MeasurementUnit.MILLIVOLT),
        measurement("m-3", "state", MeasurementUnit.BOOLEAN),
    )


def make_result(**changes: Any) -> ReadWorkflowResult:
    values: dict[str, Any] = {
        "request": workflow_request(),
        "capabilities": capabilities(),
        "evidence_source": EvidenceSource.SYNTHETIC,
        "status": ReadWorkflowStatus.COMPLETED,
        "measurements": completed_measurements(),
    }
    values.update(changes)
    return ReadWorkflowResult(**values)


def test_public_workflow_enums_schema_and_models_are_frozen() -> None:
    requirement = analog_request(count=2)
    request = ReadWorkflowRequest([requirement])  # type: ignore[arg-type]
    result = ReadWorkflowResult(
        request,
        capabilities(),
        EvidenceSource.SYNTHETIC,
        ReadWorkflowStatus.COMPLETED,
        (
            measurement("m-1", "input", MeasurementUnit.MILLIVOLT),
            measurement("m-2", "input", MeasurementUnit.MILLIVOLT),
        ),
    )

    assert READ_WORKFLOW_SCHEMA_VERSION == "read-workflow.v1"
    assert ReadOperation.ANALOG.value == "ANALOG"
    assert ReadOperation.DIGITAL.value == "DIGITAL"
    assert ReadWorkflowStatus.COMPLETED.value == "COMPLETED"
    assert ReadWorkflowStatus.UNSUPPORTED.value == "UNSUPPORTED"
    assert ReadWorkflowStatus.INCOMPLETE.value == "INCOMPLETE"
    assert request.request_id == "read-workflow"
    assert request.requested_sample_count == 2
    assert isinstance(request.requirements, tuple)
    assert result.is_completed
    assert not result.is_unsupported
    assert not result.is_incomplete
    with pytest.raises(FrozenInstanceError):
        requirement.sample_count = 3  # type: ignore[misc]


@pytest.mark.parametrize("channel", ["", " leading", "trailing ", cast(Any, 1)])
def test_channel_read_request_rejects_invalid_channel(channel: str) -> None:
    with pytest.raises(ValidationError, match="channel"):
        analog_request(channel)


def test_channel_read_request_requires_typed_operation_unit_and_matching_role() -> None:
    with pytest.raises(ValidationError, match="ReadOperation"):
        ChannelReadRequest(
            "input",
            cast(Any, "ANALOG"),
            MeasurementUnit.MILLIVOLT,
        )
    with pytest.raises(ValidationError, match="MeasurementUnit"):
        ChannelReadRequest("input", ReadOperation.ANALOG, cast(Any, "mV"))
    with pytest.raises(ValidationError, match="analog reads"):
        ChannelReadRequest(
            "input", ReadOperation.ANALOG, MeasurementUnit.BOOLEAN
        )
    with pytest.raises(ValidationError, match="digital reads"):
        ChannelReadRequest(
            "state", ReadOperation.DIGITAL, MeasurementUnit.MILLIVOLT
        )


@pytest.mark.parametrize("count", [True, 0, -1, 1.5, "2"])
def test_channel_read_request_rejects_invalid_sample_count(count: object) -> None:
    with pytest.raises(ValidationError, match="sample_count"):
        analog_request(count=cast(Any, count))


def test_workflow_request_freezes_iterable_and_rejects_bad_collections() -> None:
    mutable = [analog_request()]
    request = ReadWorkflowRequest(cast(Any, mutable))
    mutable.clear()
    assert len(request.requirements) == 1

    with pytest.raises(ValidationError, match="iterable"):
        ReadWorkflowRequest(cast(Any, "requirements"))
    with pytest.raises(ValidationError, match="ChannelReadRequest"):
        ReadWorkflowRequest(cast(Any, (object(),)))
    with pytest.raises(ValidationError, match="cannot be empty"):
        ReadWorkflowRequest(())
    with pytest.raises(ValidationError, match="unique"):
        ReadWorkflowRequest((analog_request(), analog_request()))


def test_workflow_request_rejects_invalid_identity_and_schema() -> None:
    for request_id in ("", " bad", "bad "):
        with pytest.raises(ValidationError, match="request_id"):
            ReadWorkflowRequest((analog_request(),), request_id=request_id)
    with pytest.raises(ValidationError, match="workflow version"):
        ReadWorkflowRequest(
            (analog_request(),), schema_version="read-workflow.v2"
        )


def test_completed_result_freezes_collections_and_exposes_counts() -> None:
    mutable = list(completed_measurements())
    result = make_result(measurements=mutable)
    mutable.clear()

    assert len(result.measurements) == 3
    assert result.request.requested_sample_count == 3
    assert result.missing_requirements == ()
    assert result.schema_version == READ_WORKFLOW_SCHEMA_VERSION


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("request", object(), "ReadWorkflowRequest"),
        ("capabilities", object(), "DeviceCapabilities"),
        ("evidence_source", "SYNTHETIC", "EvidenceSource"),
        ("status", "COMPLETED", "ReadWorkflowStatus"),
    ],
)
def test_result_requires_typed_core_fields(
    field: str, value: object, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        make_result(**{field: value})


def test_result_rejects_invalid_measurement_and_missing_collections() -> None:
    with pytest.raises(ValidationError, match="iterable"):
        make_result(measurements=cast(Any, "measurements"))
    with pytest.raises(ValidationError, match="Measurement"):
        make_result(measurements=(object(),))

    unsupported = {
        "capabilities": analog_only_capabilities(),
        "status": ReadWorkflowStatus.UNSUPPORTED,
        "measurements": (),
    }
    with pytest.raises(ValidationError, match="iterable"):
        make_result(**unsupported, missing_requirements=cast(Any, 1))
    with pytest.raises(ValidationError, match="str values"):
        make_result(**unsupported, missing_requirements=(object(),))
    for missing in (("",), (" bad",), ("bad ",)):
        with pytest.raises(ValidationError, match="missing requirement"):
            make_result(**unsupported, missing_requirements=missing)
    with pytest.raises(ValidationError, match="duplicates"):
        make_result(
            **unsupported,
            missing_requirements=("command:READ", "command:READ"),
        )


def test_result_rejects_incompatible_measurements() -> None:
    with pytest.raises(ValidationError, match="not requested"):
        make_result(
            measurements=(
                *completed_measurements(),
                measurement("m-4", "other", MeasurementUnit.MILLIVOLT),
            )
        )
    wrong_unit = measurement("m-1", "input", MeasurementUnit.VOLT)
    with pytest.raises(ValidationError, match="unit"):
        make_result(measurements=(wrong_unit, *completed_measurements()[1:]))
    wrong_source = measurement(
        "m-1",
        "input",
        MeasurementUnit.MILLIVOLT,
        source=EvidenceSource.CSV_REPLAY,
    )
    with pytest.raises(ValidationError, match="source"):
        make_result(measurements=(wrong_source, *completed_measurements()[1:]))
    with pytest.raises(ValidationError, match="more samples"):
        make_result(
            measurements=(
                *completed_measurements(),
                measurement("m-4", "input", MeasurementUnit.MILLIVOLT),
            )
        )


def test_completed_result_requires_all_samples_and_no_missing_requirements() -> None:
    with pytest.raises(ValidationError, match="requested capabilities"):
        make_result(capabilities=analog_only_capabilities())
    with pytest.raises(ValidationError, match="cannot have missing"):
        make_result(missing_requirements=("samples:ANALOG:input:1",))
    with pytest.raises(ValidationError, match="every requested sample"):
        make_result(measurements=completed_measurements()[:-1])


def test_unsupported_result_requires_missing_and_forbids_partial_data() -> None:
    with pytest.raises(ValidationError, match="must identify"):
        make_result(
            capabilities=analog_only_capabilities(),
            status=ReadWorkflowStatus.UNSUPPORTED,
            measurements=(),
        )
    with pytest.raises(ValidationError, match="exact capability gaps"):
        make_result(
            capabilities=analog_only_capabilities(),
            status=ReadWorkflowStatus.UNSUPPORTED,
            measurements=(),
            missing_requirements=("digital-channel:state",),
        )
    with pytest.raises(ValidationError, match="partial"):
        make_result(
            capabilities=analog_only_capabilities(),
            status=ReadWorkflowStatus.UNSUPPORTED,
            missing_requirements=(
                "command:READ_DIGITAL_STATE",
                "digital-channel:state",
            ),
        )

    result = make_result(
        capabilities=analog_only_capabilities(),
        status=ReadWorkflowStatus.UNSUPPORTED,
        measurements=(),
        missing_requirements=(
            "command:READ_DIGITAL_STATE",
            "digital-channel:state",
        ),
    )
    assert result.is_unsupported
    assert not result.is_completed
    assert not result.is_incomplete


def test_incomplete_result_requires_missing_and_less_than_requested_data() -> None:
    with pytest.raises(ValidationError, match="requested capabilities"):
        make_result(
            capabilities=analog_only_capabilities(),
            status=ReadWorkflowStatus.INCOMPLETE,
            measurements=completed_measurements()[:1],
            missing_requirements=("samples:ANALOG:input:1",),
        )
    with pytest.raises(ValidationError, match="must identify"):
        make_result(
            status=ReadWorkflowStatus.INCOMPLETE,
            measurements=completed_measurements()[:1],
        )
    with pytest.raises(ValidationError, match="missing requested samples"):
        make_result(
            status=ReadWorkflowStatus.INCOMPLETE,
            missing_requirements=("samples:DIGITAL:state:1",),
        )

    result = make_result(
        status=ReadWorkflowStatus.INCOMPLETE,
        measurements=completed_measurements()[:1],
        missing_requirements=("samples:ANALOG:input:1", "samples:DIGITAL:state:1"),
    )
    assert result.is_incomplete
    assert not result.is_completed
    assert not result.is_unsupported


def test_result_rejects_unknown_schema_version() -> None:
    with pytest.raises(ValidationError, match="workflow version"):
        make_result(schema_version="read-workflow.v2")


def test_run_read_workflow_requires_typed_disconnected_inputs() -> None:
    request = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "afe.ch0.input",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
            ),
        )
    )
    adapter = SimulatorAdapter()

    with pytest.raises(ValidationError, match="DeviceAdapter"):
        run_read_workflow(cast(Any, object()), request)
    with pytest.raises(ValidationError, match="ReadWorkflowRequest"):
        run_read_workflow(adapter, cast(Any, object()))

    adapter.connect()
    with pytest.raises(AdapterStateError, match="requires a disconnected adapter"):
        run_read_workflow(adapter, request)
    assert adapter.is_connected
    adapter.disconnect()
