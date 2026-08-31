from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from typing import Any, cast

import pytest

import analog_validation_app.services as services_module
from analog_validation import (
    AdapterState,
    ChannelReadRequest,
    CsvReplayAdapterConfig,
    MeasurementUnit,
    ReadOperation,
    ReadWorkflowRequest,
    ReplayChannelConfig,
    ReplayChannelKind,
    SafeRange,
    SimulatorAdapter,
    SimulatorConfig,
)
from analog_validation import (
    TestRunOutcome as RunOutcome,
)
from analog_validation.analysis import (
    DCSweepAcceptanceCriteria,
    DCSweepAnalysisConfig,
    HysteresisAcceptanceCriteria,
    HysteresisAnalysisConfig,
)
from analog_validation.exports import ResultExportBundle
from analog_validation.workflows import ReadWorkflowStatus
from analog_validation_app import (
    DCSweepJobService,
    HysteresisJobService,
    ProductCancellationToken,
    ProductJobExecution,
    ProductJobRequest,
    ProductJobResult,
    ProductJobType,
    ProductRequestError,
    ProductResultStatus,
    ProductServiceError,
    ProductServiceOutput,
    ProductServiceOutputSlot,
    ProductSourceMode,
    ProductWorkerState,
    ProductWorkerTimeoutError,
    ReadJobService,
    execute_product_job,
    make_csv_replay_adapter_factory,
    make_dc_sweep_service_factory,
    make_hysteresis_service_factory,
    make_read_service_factory,
    make_simulator_adapter_factory,
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_REPLAY = ROOT / "test-data" / "golden" / "csv_replay_v1_valid.csv"
NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
LIMITATIONS = ("Host-side service test; no hardware was accessed.",)


def product_request(job_type: ProductJobType) -> ProductJobRequest:
    return ProductJobRequest(
        f"service-{job_type.value.lower()}",
        ProductSourceMode.SIMULATOR,
        job_type,
        "afe",
        "1",
    )


def simulator_factory() -> Callable[[ProductJobRequest], SimulatorAdapter]:
    factory = make_simulator_adapter_factory(SimulatorConfig())
    return cast(Callable[[ProductJobRequest], SimulatorAdapter], factory)


def read_request(
    channel: str = "afe.ch0.input", sample_count: int = 3
) -> ReadWorkflowRequest:
    return ReadWorkflowRequest(
        (
            ChannelReadRequest(
                channel,
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                sample_count,
            ),
        )
    )


def dc_parts(
    points: int = 24,
) -> tuple[ReadWorkflowRequest, DCSweepAnalysisConfig, DCSweepAcceptanceCriteria]:
    workflow = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "afe.ch0.input",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                points,
            ),
            ChannelReadRequest(
                "afe.ch0.output",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                points,
            ),
        )
    )
    analysis = DCSweepAnalysisConfig("afe.ch0.input", "afe.ch0.output", 25, 3275)
    criteria = DCSweepAcceptanceCriteria("service-dc", "1", 2.0, 0.05, 25, 0.999, 1, 3)
    return workflow, analysis, criteria


def hysteresis_parts() -> tuple[
    ReadWorkflowRequest,
    HysteresisAnalysisConfig,
    HysteresisAcceptanceCriteria,
]:
    workflow = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "afe.ch0.input",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                34,
            ),
            ChannelReadRequest(
                "afe.ch0.threshold",
                ReadOperation.DIGITAL,
                MeasurementUnit.BOOLEAN,
                34,
            ),
        )
    )
    analysis = HysteresisAnalysisConfig("afe.ch0.input", "afe.ch0.threshold")
    criteria = HysteresisAcceptanceCriteria(
        "service-hysteresis", "1", 900, 1100, 800, 1000, 20, 200, 0, 1
    )
    return workflow, analysis, criteria


def replay_config() -> CsvReplayAdapterConfig:
    return CsvReplayAdapterConfig(
        (
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


def run_service(
    request: ProductJobRequest,
    factory: Callable[[ProductJobRequest], object],
    slot: ProductServiceOutputSlot,
) -> ProductJobExecution:
    return execute_product_job(request, cast(Any, factory), slot)


def test_service_output_and_slot_are_typed_single_publication_contracts() -> None:
    request = product_request(ProductJobType.READ)
    slot = ProductServiceOutputSlot()
    execution = run_service(
        request,
        make_read_service_factory(
            simulator_factory(), read_request(), LIMITATIONS, slot
        ),
        slot,
    )
    assert execution.output is not None
    output = execution.output
    assert output.read_result.status is ReadWorkflowStatus.COMPLETED
    assert output.result_export is None
    assert slot.value is output

    with pytest.raises(ProductServiceError, match="already"):
        slot.publish(output)
    with pytest.raises(ProductRequestError, match="ReadWorkflowResult"):
        ProductServiceOutput(cast(Any, object()))
    with pytest.raises(ProductRequestError, match="ResultExportBundle"):
        ProductServiceOutput(output.read_result, cast(Any, object()))
    with pytest.raises(ProductRequestError, match="ProductServiceOutput"):
        ProductServiceOutputSlot().publish(cast(Any, object()))


def test_read_service_completes_through_real_worker_and_progress_chain() -> None:
    request = product_request(ProductJobType.READ)
    slot = ProductServiceOutputSlot()

    execution = run_service(
        request,
        make_read_service_factory(
            simulator_factory(), read_request(sample_count=4), LIMITATIONS, slot
        ),
        slot,
    )

    assert execution.worker_state is ProductWorkerState.SUCCEEDED
    assert execution.result is not None
    assert execution.result.status is ProductResultStatus.COMPLETED
    assert execution.result.test_run_outcome is None
    assert execution.output is not None
    assert len(execution.output.read_result.measurements) == 4
    assert [event.completed for event in execution.events] == [None, None, 0, 1, None]


def test_read_service_returns_unsupported_without_fabricating_data() -> None:
    request = product_request(ProductJobType.READ)
    slot = ProductServiceOutputSlot()

    execution = run_service(
        request,
        make_read_service_factory(
            simulator_factory(), read_request("missing.channel"), LIMITATIONS, slot
        ),
        slot,
    )

    assert execution.result is not None
    assert execution.result.status is ProductResultStatus.UNSUPPORTED
    assert execution.output is not None
    assert execution.output.read_result.measurements == ()
    assert execution.output.read_result.missing_requirements == (
        "analog-channel:missing.channel",
    )


def test_read_service_preserves_replay_incomplete_semantics() -> None:
    request = ProductJobRequest(
        "replay-read",
        ProductSourceMode.CSV_REPLAY,
        ProductJobType.READ,
        "afe",
        "1",
    )
    slot = ProductServiceOutputSlot()
    config = CsvReplayAdapterConfig((replay_config().channels[0],))

    execution = run_service(
        request,
        make_read_service_factory(
            make_csv_replay_adapter_factory(GOLDEN_REPLAY, config),
            read_request(sample_count=3),
            LIMITATIONS,
            slot,
        ),
        slot,
    )

    assert execution.result is not None
    assert execution.result.status is ProductResultStatus.INCOMPLETE
    assert execution.output is not None
    assert len(execution.output.read_result.measurements) == 2


def test_dc_service_produces_formal_pass_and_result_export() -> None:
    request = product_request(ProductJobType.DC_ANALYSIS)
    workflow, analysis, criteria = dc_parts()
    slot = ProductServiceOutputSlot()

    execution = run_service(
        request,
        make_dc_sweep_service_factory(
            simulator_factory(),
            workflow,
            analysis,
            criteria,
            LIMITATIONS,
            slot,
            clock=lambda: NOW,
        ),
        slot,
    )

    assert execution.worker_state is ProductWorkerState.SUCCEEDED
    assert execution.result is not None
    assert execution.result.test_run_outcome is RunOutcome.PASS
    assert execution.result.is_engineering_conclusion
    assert execution.output is not None
    bundle = cast(ResultExportBundle, execution.output.result_export)
    assert bundle.test_run_result.outcome is RunOutcome.PASS
    assert bundle.test_run_result.metadata.started_at == NOW
    assert len(bundle.points) == 24
    assert {metric.name: metric.value for metric in bundle.metrics}["gain"] == 2.0


def test_dc_service_preserves_formal_fail_as_successful_orchestration() -> None:
    request = product_request(ProductJobType.DC_ANALYSIS)
    workflow, analysis, _ = dc_parts(6)
    failing = DCSweepAcceptanceCriteria("failing", "1", 99, 0, 0, 1, 0, 3)
    slot = ProductServiceOutputSlot()

    execution = run_service(
        request,
        make_dc_sweep_service_factory(
            simulator_factory(),
            workflow,
            analysis,
            failing,
            LIMITATIONS,
            slot,
            clock=lambda: NOW,
        ),
        slot,
    )

    assert execution.worker_state is ProductWorkerState.SUCCEEDED
    assert execution.result is not None
    assert execution.result.status is ProductResultStatus.COMPLETED
    assert execution.result.test_run_outcome is RunOutcome.FAIL


def test_dc_service_without_criteria_is_incomplete_not_pass() -> None:
    request = product_request(ProductJobType.DC_ANALYSIS)
    workflow, analysis, _ = dc_parts(6)
    slot = ProductServiceOutputSlot()

    execution = run_service(
        request,
        make_dc_sweep_service_factory(
            simulator_factory(),
            workflow,
            analysis,
            None,
            LIMITATIONS,
            slot,
            clock=lambda: NOW,
        ),
        slot,
    )

    assert execution.result is not None
    assert execution.result.status is ProductResultStatus.INCOMPLETE
    assert execution.result.test_run_outcome is RunOutcome.INCOMPLETE
    assert execution.output is not None
    assert execution.output.result_export is not None


def test_dc_service_stops_before_analysis_when_acquisition_is_unsupported() -> None:
    request = product_request(ProductJobType.DC_ANALYSIS)
    workflow = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "missing.input",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                3,
            ),
            ChannelReadRequest(
                "missing.output",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                3,
            ),
        )
    )
    analysis = DCSweepAnalysisConfig("missing.input", "missing.output", 0, 3300)
    slot = ProductServiceOutputSlot()

    execution = run_service(
        request,
        make_dc_sweep_service_factory(
            simulator_factory(),
            workflow,
            analysis,
            None,
            LIMITATIONS,
            slot,
        ),
        slot,
    )

    assert execution.result is not None
    assert execution.result.status is ProductResultStatus.UNSUPPORTED
    assert execution.output is not None
    assert execution.output.result_export is None


def test_dc_service_stops_before_analysis_on_replay_eof() -> None:
    request = ProductJobRequest(
        "replay-dc",
        ProductSourceMode.CSV_REPLAY,
        ProductJobType.DC_ANALYSIS,
        "afe",
        "1",
    )
    workflow, analysis, criteria = dc_parts(3)
    slot = ProductServiceOutputSlot()

    execution = run_service(
        request,
        make_dc_sweep_service_factory(
            make_csv_replay_adapter_factory(GOLDEN_REPLAY, replay_config()),
            workflow,
            analysis,
            criteria,
            LIMITATIONS,
            slot,
        ),
        slot,
    )

    assert execution.result is not None
    assert execution.result.status is ProductResultStatus.INCOMPLETE
    assert execution.output is not None
    assert execution.output.read_result.status is ReadWorkflowStatus.INCOMPLETE
    assert execution.output.result_export is None


def test_hysteresis_service_produces_formal_pass_with_explicit_directions() -> None:
    request = product_request(ProductJobType.HYSTERESIS_ANALYSIS)
    workflow, analysis, criteria = hysteresis_parts()
    slot = ProductServiceOutputSlot()

    execution = run_service(
        request,
        make_hysteresis_service_factory(
            simulator_factory(),
            workflow,
            analysis,
            criteria,
            12,
            22,
            LIMITATIONS,
            slot,
            clock=lambda: NOW,
        ),
        slot,
    )

    assert execution.worker_state is ProductWorkerState.SUCCEEDED
    assert execution.result is not None
    assert execution.result.test_run_outcome is RunOutcome.PASS
    assert execution.output is not None
    bundle = cast(ResultExportBundle, execution.output.result_export)
    assert len(bundle.points) == 34
    metrics = {metric.name: metric.value for metric in bundle.metrics}
    assert metrics["complete_cycles"] == 1


def test_hysteresis_without_criteria_is_incomplete_with_formal_export() -> None:
    request = product_request(ProductJobType.HYSTERESIS_ANALYSIS)
    workflow, analysis, _ = hysteresis_parts()
    slot = ProductServiceOutputSlot()

    execution = run_service(
        request,
        make_hysteresis_service_factory(
            simulator_factory(),
            workflow,
            analysis,
            None,
            12,
            22,
            LIMITATIONS,
            slot,
            clock=lambda: NOW,
        ),
        slot,
    )

    assert execution.result is not None
    assert execution.result.test_run_outcome is RunOutcome.INCOMPLETE
    assert execution.output is not None
    assert execution.output.result_export is not None


def test_hysteresis_service_stops_on_incomplete_replay() -> None:
    request = ProductJobRequest(
        "replay-hysteresis",
        ProductSourceMode.CSV_REPLAY,
        ProductJobType.HYSTERESIS_ANALYSIS,
        "afe",
        "1",
    )
    workflow, analysis, criteria = hysteresis_parts()
    slot = ProductServiceOutputSlot()

    execution = run_service(
        request,
        make_hysteresis_service_factory(
            make_csv_replay_adapter_factory(GOLDEN_REPLAY, replay_config()),
            workflow,
            analysis,
            criteria,
            12,
            22,
            LIMITATIONS,
            slot,
        ),
        slot,
    )

    assert execution.result is not None
    assert execution.result.status is ProductResultStatus.INCOMPLETE
    assert execution.output is not None
    assert execution.output.result_export is None


def test_service_wrong_job_is_failed_and_never_publishes_output() -> None:
    slot = ProductServiceOutputSlot()
    read_service_factory = make_read_service_factory(
        simulator_factory(), read_request(), LIMITATIONS, slot
    )

    execution = run_service(
        product_request(ProductJobType.DC_ANALYSIS), read_service_factory, slot
    )

    assert execution.worker_state is ProductWorkerState.FAILED
    assert execution.output is None
    assert execution.issue is not None


def test_owned_service_cleanup_disconnects_an_adapter_left_connected() -> None:
    adapter = SimulatorAdapter()
    service = ReadJobService(
        adapter, read_request(), LIMITATIONS, ProductServiceOutputSlot()
    )
    adapter.connect()
    assert adapter.state is AdapterState.CONNECTED_READ_ONLY

    service.cleanup()

    assert adapter.state is AdapterState.DISCONNECTED
    service.cleanup()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("request", object(), "ProductJobRequest"),
        ("worker_state", ProductWorkerState.RUNNING, "terminal"),
        ("result", object(), "ProductJobResult"),
        ("issue", object(), "UserIssue"),
        ("events", [object()], "ProductJobEvent"),
        ("output", object(), "ProductServiceOutput"),
        ("dropped_event_count", -1, "non-negative"),
        ("interrupted", 1, "boolean"),
    ],
)
def test_execution_snapshot_rejects_invalid_contracts(
    field: str, value: object, message: str
) -> None:
    values: dict[str, object] = {
        "request": product_request(ProductJobType.READ),
        "worker_state": ProductWorkerState.SUCCEEDED,
        "result": None,
        "issue": None,
        "events": (),
        "output": None,
        "dropped_event_count": 0,
        "interrupted": False,
    }
    values[field] = value
    with pytest.raises(ProductRequestError, match=message):
        ProductJobExecution(**cast(Any, values))


@pytest.mark.parametrize(
    ("request_value", "factory", "slot", "message"),
    [
        (object(), lambda _request: object(), ProductServiceOutputSlot(), "request"),
        (
            product_request(ProductJobType.READ),
            object(),
            ProductServiceOutputSlot(),
            "service_factory",
        ),
        (
            product_request(ProductJobType.READ),
            lambda _request: object(),
            object(),
            "output_slot",
        ),
    ],
)
def test_execute_product_job_validates_inputs(
    request_value: object, factory: object, slot: object, message: str
) -> None:
    with pytest.raises(ProductRequestError, match=message):
        execute_product_job(
            cast(Any, request_value), cast(Any, factory), cast(Any, slot)
        )


def test_execute_product_job_timeout_cancels_and_leaves_no_service_running() -> None:
    request = product_request(ProductJobType.READ)
    stopped = Event()

    class SlowService:
        def run(
            self,
            request: ProductJobRequest,
            cancellation: ProductCancellationToken,
            report_progress: Callable[[str, int | None, int | None], None],
        ) -> ProductJobResult:
            while not cancellation.wait(0.001):
                pass
            cancellation.raise_if_cancelled()
            raise AssertionError("unreachable")

        def cleanup(self) -> None:
            stopped.set()

    with pytest.raises(ProductWorkerTimeoutError, match="bounded join"):
        execute_product_job(
            request,
            lambda _request: SlowService(),
            ProductServiceOutputSlot(),
            join_timeout_s=0.02,
        )
    assert stopped.wait(1.0)


def test_execute_product_job_turns_keyboard_interrupt_into_cancelled_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed: list[bool] = []

    class InterruptWorker:
        state = ProductWorkerState.CANCELLED
        result = None
        issue = None
        events: tuple[object, ...] = ()
        dropped_event_count = 0
        last_error = None
        cleanup_error = None

        def __init__(self, factory: object, *, join_timeout_s: float) -> None:
            pass

        def start(self, request: ProductJobRequest) -> None:
            pass

        def join(self, timeout_s: float) -> bool:
            raise KeyboardInterrupt

        def cancel_and_join(self, timeout_s: float) -> None:
            pass

        def close(self, timeout_s: float) -> None:
            closed.append(True)

    monkeypatch.setattr(services_module, "ProductJobWorker", InterruptWorker)
    request = product_request(ProductJobType.READ)

    execution = execute_product_job(
        request, cast(Any, lambda _request: object()), ProductServiceOutputSlot()
    )

    assert execution.worker_state is ProductWorkerState.CANCELLED
    assert execution.interrupted
    assert execution.output is None
    assert closed == [True]


def test_service_clock_fails_closed_for_wrong_or_naive_values() -> None:
    request = product_request(ProductJobType.DC_ANALYSIS)
    workflow, analysis, criteria = dc_parts(3)
    for clock in (
        cast(Callable[[], datetime], lambda: cast(Any, "not-time")),
        lambda: NOW.replace(tzinfo=None),
    ):
        slot = ProductServiceOutputSlot()
        execution = run_service(
            request,
            make_dc_sweep_service_factory(
                simulator_factory(),
                workflow,
                analysis,
                criteria,
                LIMITATIONS,
                slot,
                clock=clock,
            ),
            slot,
        )
        assert execution.worker_state is ProductWorkerState.FAILED
        assert isinstance(execution.developer_error, ProductServiceError)


@pytest.mark.parametrize(
    "limitations",
    [
        "text",
        (),
        (object(),),
        ("",),
        (" padded ",),
        ("line\nbreak",),
        ("duplicate", "duplicate"),
        tuple(f"limit-{index}" for index in range(65)),
        ("x" * 1025,),
    ],
)
def test_services_reject_invalid_limitations(limitations: object) -> None:
    with pytest.raises(ProductRequestError, match="limitation"):
        ReadJobService(
            SimulatorAdapter(),
            read_request(),
            cast(Any, limitations),
            ProductServiceOutputSlot(),
        )


def test_service_factories_require_callable_adapter_factories() -> None:
    workflow, dc_analysis, dc_criteria = dc_parts()
    hyst_workflow, hyst_analysis, hyst_criteria = hysteresis_parts()
    slot = ProductServiceOutputSlot()
    for call in (
        lambda: make_read_service_factory(
            cast(Any, object()), read_request(), LIMITATIONS, slot
        ),
        lambda: make_dc_sweep_service_factory(
            cast(Any, object()),
            workflow,
            dc_analysis,
            dc_criteria,
            LIMITATIONS,
            slot,
        ),
        lambda: make_hysteresis_service_factory(
            cast(Any, object()),
            hyst_workflow,
            hyst_analysis,
            hyst_criteria,
            12,
            22,
            LIMITATIONS,
            slot,
        ),
    ):
        with pytest.raises(ProductRequestError, match="adapter_factory"):
            call()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("adapter", object(), "adapter"),
        ("workflow", object(), "workflow_request"),
        ("slot", object(), "output_slot"),
    ],
)
def test_read_service_constructor_validates_owned_inputs(
    field: str, value: object, message: str
) -> None:
    values: dict[str, object] = {
        "adapter": SimulatorAdapter(),
        "workflow": read_request(),
        "limitations": LIMITATIONS,
        "slot": ProductServiceOutputSlot(),
    }
    values[field] = value
    with pytest.raises(ProductRequestError, match=message):
        ReadJobService(
            cast(Any, values["adapter"]),
            cast(Any, values["workflow"]),
            cast(Any, values["limitations"]),
            cast(Any, values["slot"]),
        )


def test_dc_service_constructor_and_workflow_shape_fail_closed() -> None:
    workflow, analysis, criteria = dc_parts(3)
    slot = ProductServiceOutputSlot()
    base = (
        SimulatorAdapter(),
        workflow,
        analysis,
        criteria,
        LIMITATIONS,
        slot,
    )
    invalid_cases = (
        ((base[0], object(), *base[2:]), "workflow_request"),
        ((base[0], base[1], object(), *base[3:]), "analysis_config"),
        ((base[0], base[1], base[2], object(), *base[4:]), "criteria"),
        ((*base[:-1], object()), "output_slot"),
    )
    for values, message in invalid_cases:
        with pytest.raises(ProductRequestError, match=message):
            DCSweepJobService(*cast(Any, values))
    with pytest.raises(ProductRequestError, match="clock"):
        DCSweepJobService(*base, clock=cast(Any, object()))

    one_channel = read_request()
    wrong_channels = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "other.input",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                3,
            ),
            ChannelReadRequest(
                "other.output",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                3,
            ),
        )
    )
    wrong_operation = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "afe.ch0.input",
                ReadOperation.DIGITAL,
                MeasurementUnit.BOOLEAN,
                3,
            ),
            ChannelReadRequest(
                "afe.ch0.output",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                3,
            ),
        )
    )
    unequal = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "afe.ch0.input",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                2,
            ),
            ChannelReadRequest(
                "afe.ch0.output",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                3,
            ),
        )
    )
    for invalid, message in (
        (one_channel, "two channel"),
        (wrong_channels, "match"),
        (wrong_operation, "analog"),
        (unequal, "counts"),
    ):
        with pytest.raises(ProductRequestError, match=message):
            DCSweepJobService(
                SimulatorAdapter(),
                invalid,
                analysis,
                criteria,
                LIMITATIONS,
                ProductServiceOutputSlot(),
            )


def test_dc_service_rejects_wrong_runtime_job_type() -> None:
    workflow, analysis, criteria = dc_parts(3)
    slot = ProductServiceOutputSlot()
    service = DCSweepJobService(
        SimulatorAdapter(), workflow, analysis, criteria, LIMITATIONS, slot
    )
    with pytest.raises(ProductRequestError, match="DC_ANALYSIS"):
        service.run(
            product_request(ProductJobType.READ),
            ProductCancellationToken(),
            lambda *_args: None,
        )


def test_hysteresis_service_constructor_and_workflow_shape_fail_closed() -> None:
    workflow, analysis, criteria = hysteresis_parts()
    slot = ProductServiceOutputSlot()
    base = (
        SimulatorAdapter(),
        workflow,
        analysis,
        criteria,
        12,
        22,
        LIMITATIONS,
        slot,
    )
    invalid_cases = (
        ((base[0], object(), *base[2:]), "workflow_request"),
        ((base[0], base[1], object(), *base[3:]), "analysis_config"),
        ((base[0], base[1], base[2], object(), *base[4:]), "criteria"),
        ((*base[:4], 1, *base[5:]), "rising_count"),
        ((*base[:5], True, *base[6:]), "falling_count"),
        ((*base[:-1], object()), "output_slot"),
    )
    for values, message in invalid_cases:
        with pytest.raises(ProductRequestError, match=message):
            HysteresisJobService(*cast(Any, values))
    with pytest.raises(ProductRequestError, match="clock"):
        HysteresisJobService(*base, clock=cast(Any, object()))

    one_channel = read_request()
    wrong_channels = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "other.input",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                34,
            ),
            ChannelReadRequest(
                "other.state",
                ReadOperation.DIGITAL,
                MeasurementUnit.BOOLEAN,
                34,
            ),
        )
    )
    wrong_operation = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "afe.ch0.input",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                34,
            ),
            ChannelReadRequest(
                "afe.ch0.threshold",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                34,
            ),
        )
    )
    wrong_counts = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                "afe.ch0.input",
                ReadOperation.ANALOG,
                MeasurementUnit.MILLIVOLT,
                33,
            ),
            ChannelReadRequest(
                "afe.ch0.threshold",
                ReadOperation.DIGITAL,
                MeasurementUnit.BOOLEAN,
                34,
            ),
        )
    )
    for invalid, message in (
        (one_channel, "two channel"),
        (wrong_channels, "match"),
        (wrong_operation, "analog input"),
        (wrong_counts, "counts"),
    ):
        with pytest.raises(ProductRequestError, match=message):
            HysteresisJobService(
                SimulatorAdapter(),
                invalid,
                analysis,
                criteria,
                12,
                22,
                LIMITATIONS,
                ProductServiceOutputSlot(),
            )


def test_hysteresis_service_rejects_wrong_runtime_job_type() -> None:
    workflow, analysis, criteria = hysteresis_parts()
    service = HysteresisJobService(
        SimulatorAdapter(),
        workflow,
        analysis,
        criteria,
        12,
        22,
        LIMITATIONS,
        ProductServiceOutputSlot(),
    )
    with pytest.raises(ProductRequestError, match="HYSTERESIS_ANALYSIS"):
        service.run(
            product_request(ProductJobType.READ),
            ProductCancellationToken(),
            lambda *_args: None,
        )


def test_execution_snapshot_rejects_non_enum_worker_state() -> None:
    with pytest.raises(ProductRequestError, match="ProductWorkerState"):
        ProductJobExecution(
            product_request(ProductJobType.READ),
            cast(Any, "SUCCEEDED"),
            None,
            None,
            (),
            None,
            0,
        )
