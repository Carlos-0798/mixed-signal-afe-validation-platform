"""Product application services that compose the frozen engineering core."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import cast

from analog_validation import __version__
from analog_validation.adapters import AdapterState, DeviceAdapter
from analog_validation.analysis import (
    CALIBRATION_TEST_TYPE,
    DC_SWEEP_TEST_TYPE,
    FREQUENCY_RESPONSE_TEST_TYPE,
    HYSTERESIS_TEST_TYPE,
    CalibrationAcceptanceCriteria,
    CalibrationFitConfig,
    DCSweepAcceptanceCriteria,
    DCSweepAnalysisConfig,
    FrequencyResponseAcceptanceCriteria,
    FrequencyResponseAnalysisConfig,
    HysteresisAcceptanceCriteria,
    HysteresisAnalysisConfig,
    HysteresisCycleInput,
    LinearCalibrationCoefficients,
    MeasurementBatch,
    analyze_dc_sweep,
    analyze_frequency_response,
    analyze_hysteresis,
    evaluate_calibration,
    evaluate_dc_sweep,
    evaluate_frequency_response,
    evaluate_hysteresis,
    fit_linear_calibration,
)
from analog_validation.domain import (
    Measurement,
    MeasurementUnit,
    TestRunMetadata,
    TestRunOutcome,
)
from analog_validation.exports import (
    ResultExportBundle,
    build_calibration_export,
    build_dc_sweep_export,
    build_frequency_response_export,
    build_hysteresis_export,
)
from analog_validation.workflows import (
    ReadOperation,
    ReadWorkflowRequest,
    ReadWorkflowResult,
    ReadWorkflowStatus,
    run_read_workflow,
    run_streaming_read_workflow,
)

from .errors import ProductRequestError, ProductServiceError, ProductWorkerTimeoutError
from .factories import AdapterFactory
from .issues import UserIssue
from .live import LiveMonitorSession, LiveMonitorSnapshot
from .models import (
    MAX_PRODUCT_LIMITATION_CHARS,
    MAX_PRODUCT_LIMITATIONS,
    ProductJobEvent,
    ProductJobRequest,
    ProductJobResult,
    ProductJobType,
    ProductResultStatus,
    ProductWorkerState,
)
from .worker import (
    DEFAULT_PRODUCT_JOIN_TIMEOUT_S,
    ProductCancellationToken,
    ProductJobService,
    ProductJobServiceFactory,
    ProductJobWorker,
    ProductProgressReporter,
)

Clock = Callable[[], datetime]


def _utc_now(clock: Clock) -> datetime:
    value = clock()
    if not isinstance(value, datetime):
        raise ProductServiceError("service clock must return a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ProductServiceError("service clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _require_callable(name: str, value: object) -> None:
    if not callable(value):
        raise ProductRequestError(f"{name} must be callable")


def _require_limitations(values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ProductRequestError("limitations must be an iterable of strings")
    frozen = tuple(values)
    if not frozen or not all(isinstance(value, str) for value in frozen):
        raise ProductRequestError("limitations must contain at least one string")
    checked = cast(tuple[str, ...], frozen)
    if len(checked) > MAX_PRODUCT_LIMITATIONS:
        raise ProductRequestError(
            f"limitations exceeds {MAX_PRODUCT_LIMITATIONS} entries"
        )
    for value in checked:
        if not value or value != value.strip():
            raise ProductRequestError(
                "each limitation must be a non-empty stripped string"
            )
        if len(value) > MAX_PRODUCT_LIMITATION_CHARS:
            raise ProductRequestError(
                f"limitation exceeds {MAX_PRODUCT_LIMITATION_CHARS} characters"
            )
        if not value.isprintable():
            raise ProductRequestError(
                "limitations must contain only printable characters"
            )
    if len(checked) != len(set(checked)):
        raise ProductRequestError("limitations cannot contain duplicates")
    return checked


def _status_from_read(status: ReadWorkflowStatus) -> ProductResultStatus:
    return {
        ReadWorkflowStatus.COMPLETED: ProductResultStatus.COMPLETED,
        ReadWorkflowStatus.INCOMPLETE: ProductResultStatus.INCOMPLETE,
        ReadWorkflowStatus.UNSUPPORTED: ProductResultStatus.UNSUPPORTED,
    }[status]


def _status_from_outcome(outcome: TestRunOutcome) -> ProductResultStatus:
    return {
        TestRunOutcome.PASS: ProductResultStatus.COMPLETED,
        TestRunOutcome.FAIL: ProductResultStatus.COMPLETED,
        TestRunOutcome.INCOMPLETE: ProductResultStatus.INCOMPLETE,
        TestRunOutcome.UNSUPPORTED: ProductResultStatus.UNSUPPORTED,
        TestRunOutcome.ABORTED: ProductResultStatus.CANCELLED,
        TestRunOutcome.ERROR: ProductResultStatus.ERROR,
    }[outcome]


@dataclass(frozen=True, slots=True)
class ProductServiceOutput:
    """Rich service payload published only after a safe application checkpoint."""

    read_result: ReadWorkflowResult
    result_export: ResultExportBundle | None = None
    calibration_coefficients: LinearCalibrationCoefficients | None = None
    live_monitor: LiveMonitorSnapshot | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.read_result, ReadWorkflowResult):
            raise ProductRequestError("read_result must be a ReadWorkflowResult")
        if self.result_export is not None and not isinstance(
            self.result_export, ResultExportBundle
        ):
            raise ProductRequestError(
                "result_export must be a ResultExportBundle or None"
            )
        if self.calibration_coefficients is not None and not isinstance(
            self.calibration_coefficients, LinearCalibrationCoefficients
        ):
            raise ProductRequestError(
                "calibration_coefficients must be LinearCalibrationCoefficients or None"
            )
        if self.calibration_coefficients is not None and self.result_export is None:
            raise ProductRequestError(
                "calibration coefficients require a finalized result export"
            )
        if self.live_monitor is not None and not isinstance(
            self.live_monitor, LiveMonitorSnapshot
        ):
            raise ProductRequestError(
                "live_monitor must be a LiveMonitorSnapshot or None"
            )
        if self.live_monitor is not None and self.live_monitor.total_points != len(
            self.read_result.measurements
        ):
            raise ProductRequestError(
                "live monitor point count must match acquired measurements"
            )


class ProductServiceOutputSlot:
    """Thread-safe single-publication handoff from worker service to presenter."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._value: ProductServiceOutput | None = None

    @property
    def value(self) -> ProductServiceOutput | None:
        with self._lock:
            return self._value

    def publish(self, value: ProductServiceOutput) -> None:
        if not isinstance(value, ProductServiceOutput):
            raise ProductRequestError("service output must be ProductServiceOutput")
        with self._lock:
            if self._value is not None:
                raise ProductServiceError("service output was already published")
            self._value = value


@dataclass(frozen=True, slots=True)
class ProductJobExecution:
    """One joined worker snapshot suitable for CLI or Dashboard presentation."""

    request: ProductJobRequest
    worker_state: ProductWorkerState
    result: ProductJobResult | None
    issue: UserIssue | None
    events: tuple[ProductJobEvent, ...]
    output: ProductServiceOutput | None
    dropped_event_count: int
    interrupted: bool = False
    developer_error: BaseException | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request, ProductJobRequest):
            raise ProductRequestError("request must be a ProductJobRequest")
        if not isinstance(self.worker_state, ProductWorkerState):
            raise ProductRequestError("worker_state must be a ProductWorkerState")
        if not self.worker_state.is_terminal:
            raise ProductRequestError("worker_state must be terminal")
        if self.result is not None and not isinstance(self.result, ProductJobResult):
            raise ProductRequestError("result must be a ProductJobResult or None")
        if self.issue is not None and not isinstance(self.issue, UserIssue):
            raise ProductRequestError("issue must be a UserIssue or None")
        if not isinstance(self.events, tuple) or not all(
            isinstance(event, ProductJobEvent) for event in self.events
        ):
            raise ProductRequestError("events must be ProductJobEvent values")
        if self.output is not None and not isinstance(
            self.output, ProductServiceOutput
        ):
            raise ProductRequestError("output must be ProductServiceOutput or None")
        if (
            isinstance(self.dropped_event_count, bool)
            or not isinstance(self.dropped_event_count, int)
            or self.dropped_event_count < 0
        ):
            raise ProductRequestError(
                "dropped_event_count must be a non-negative integer"
            )
        if not isinstance(self.interrupted, bool):
            raise ProductRequestError("interrupted must be boolean")


class _OwnedAdapterService:
    """Shared fail-closed adapter ownership; engineering behavior stays in core."""

    def __init__(self, adapter: DeviceAdapter) -> None:
        if not isinstance(adapter, DeviceAdapter):
            raise ProductRequestError("adapter must be a DeviceAdapter")
        self._adapter = adapter

    def cleanup(self) -> None:
        if self._adapter.state is not AdapterState.DISCONNECTED:
            self._adapter.disconnect()


class ReadJobService(_OwnedAdapterService):
    """Run one controller-neutral, bounded, read-only acquisition workflow."""

    def __init__(
        self,
        adapter: DeviceAdapter,
        workflow_request: ReadWorkflowRequest,
        limitations: tuple[str, ...],
        output_slot: ProductServiceOutputSlot,
    ) -> None:
        super().__init__(adapter)
        if not isinstance(workflow_request, ReadWorkflowRequest):
            raise ProductRequestError("workflow_request must be a ReadWorkflowRequest")
        if not isinstance(output_slot, ProductServiceOutputSlot):
            raise ProductRequestError("output_slot must be a ProductServiceOutputSlot")
        self._workflow_request = workflow_request
        self._limitations = _require_limitations(limitations)
        self._output_slot = output_slot

    def run(
        self,
        request: ProductJobRequest,
        cancellation: ProductCancellationToken,
        report_progress: ProductProgressReporter,
    ) -> ProductJobResult:
        if request.job_type is not ProductJobType.READ:
            raise ProductRequestError("read service requires a READ job")
        cancellation.raise_if_cancelled()
        report_progress("Starting bounded read-only acquisition.", 0, 1)
        read_result = run_read_workflow(
            self._adapter,
            self._workflow_request,
            checkpoint=cancellation.raise_if_cancelled,
        )
        cancellation.raise_if_cancelled()
        self._output_slot.publish(ProductServiceOutput(read_result))
        report_progress("Read-only acquisition finished.", 1, 1)
        return ProductJobResult(
            request,
            _status_from_read(read_result.status),
            read_result.evidence_source,
            self._limitations,
        )


class LiveMonitorJobService(_OwnedAdapterService):
    """Run one finite live-view acquisition with bounded presentation state."""

    def __init__(
        self,
        adapter: DeviceAdapter,
        workflow_request: ReadWorkflowRequest,
        limitations: tuple[str, ...],
        output_slot: ProductServiceOutputSlot,
        live_session: LiveMonitorSession,
        *,
        sample_interval_seconds: float,
    ) -> None:
        super().__init__(adapter)
        if not isinstance(workflow_request, ReadWorkflowRequest):
            raise ProductRequestError("workflow_request must be a ReadWorkflowRequest")
        if not isinstance(output_slot, ProductServiceOutputSlot):
            raise ProductRequestError("output_slot must be a ProductServiceOutputSlot")
        if not isinstance(live_session, LiveMonitorSession):
            raise ProductRequestError("live_session must be a LiveMonitorSession")
        counts = {
            requirement.sample_count for requirement in workflow_request.requirements
        }
        if len(counts) != 1:
            raise ProductRequestError(
                "live monitor workflow requires equal channel sample counts"
            )
        self._workflow_request = workflow_request
        self._limitations = _require_limitations(limitations)
        self._output_slot = output_slot
        self._live_session = live_session
        self._sample_interval_seconds = sample_interval_seconds
        self._cycle_count = next(iter(counts))
        self._channel_count = len(workflow_request.requirements)

    def run(
        self,
        request: ProductJobRequest,
        cancellation: ProductCancellationToken,
        report_progress: ProductProgressReporter,
    ) -> ProductJobResult:
        if request.job_type is not ProductJobType.LIVE_MONITOR:
            raise ProductRequestError(
                "live monitor service requires a LIVE_MONITOR job"
            )
        cancellation.raise_if_cancelled()
        report_progress(
            "Starting finite live monitor acquisition.", 0, self._cycle_count
        )
        progress_stride = max(1, self._cycle_count // 100)

        def publish(cycle_index: int, measurement: object) -> None:
            if not isinstance(measurement, Measurement):
                raise ProductServiceError(
                    "streaming observer received an invalid measurement"
                )
            point = self._live_session.publish(cycle_index, measurement)
            cycle_complete = point.index % self._channel_count == 0
            completed_cycles = cycle_index + 1
            if cycle_complete and (
                completed_cycles == self._cycle_count
                or completed_cycles % progress_stride == 0
            ):
                report_progress(
                    "Live monitor acquisition is running.",
                    completed_cycles,
                    self._cycle_count,
                )

        read_result = run_streaming_read_workflow(
            self._adapter,
            self._workflow_request,
            sample_interval_seconds=self._sample_interval_seconds,
            checkpoint=lambda: self._live_session.checkpoint(cancellation),
            on_measurement=publish,
            wait_interval=lambda seconds: self._live_session.wait_interval(
                seconds, cancellation
            ),
        )
        cancellation.raise_if_cancelled()
        final_snapshot = self._live_session.snapshot()
        self._output_slot.publish(
            ProductServiceOutput(read_result, live_monitor=final_snapshot)
        )
        report_progress(
            "Finite live monitor acquisition finished.",
            self._cycle_count,
            self._cycle_count,
        )
        return ProductJobResult(
            request,
            _status_from_read(read_result.status),
            read_result.evidence_source,
            self._limitations,
        )

    def cleanup(self) -> None:
        self._live_session.resume()
        super().cleanup()


class DCSweepJobService(_OwnedAdapterService):
    """Acquire observations, then call the formal DC analysis/evaluation path."""

    def __init__(
        self,
        adapter: DeviceAdapter,
        workflow_request: ReadWorkflowRequest,
        analysis_config: DCSweepAnalysisConfig,
        criteria: DCSweepAcceptanceCriteria | None,
        limitations: tuple[str, ...],
        output_slot: ProductServiceOutputSlot,
        *,
        configuration_id: str = "product-dc-sweep",
        configuration_version: str = "1",
        clock: Clock = lambda: datetime.now(timezone.utc),
    ) -> None:
        super().__init__(adapter)
        if not isinstance(workflow_request, ReadWorkflowRequest):
            raise ProductRequestError("workflow_request must be a ReadWorkflowRequest")
        if not isinstance(analysis_config, DCSweepAnalysisConfig):
            raise ProductRequestError("analysis_config must be a DCSweepAnalysisConfig")
        if criteria is not None and not isinstance(criteria, DCSweepAcceptanceCriteria):
            raise ProductRequestError(
                "criteria must be DCSweepAcceptanceCriteria or None"
            )
        if not isinstance(output_slot, ProductServiceOutputSlot):
            raise ProductRequestError("output_slot must be a ProductServiceOutputSlot")
        _require_callable("clock", clock)
        self._validate_workflow(workflow_request, analysis_config)
        self._workflow_request = workflow_request
        self._analysis_config = analysis_config
        self._criteria = criteria
        self._limitations = _require_limitations(limitations)
        self._output_slot = output_slot
        self._configuration_id = configuration_id
        self._configuration_version = configuration_version
        self._clock = clock

    @staticmethod
    def _validate_workflow(
        workflow_request: ReadWorkflowRequest,
        config: DCSweepAnalysisConfig,
    ) -> None:
        requirements = workflow_request.requirements
        if len(requirements) != 2:
            raise ProductRequestError("DC workflow requires two channel reads")
        if tuple(requirement.channel for requirement in requirements) != (
            config.input_channel,
            config.output_channel,
        ):
            raise ProductRequestError(
                "DC workflow channels must match the analysis config"
            )
        if any(
            requirement.operation is not ReadOperation.ANALOG
            for requirement in requirements
        ):
            raise ProductRequestError("DC workflow channels must be analog")
        if requirements[0].sample_count != requirements[1].sample_count:
            raise ProductRequestError("DC workflow sample counts must match")

    def run(
        self,
        request: ProductJobRequest,
        cancellation: ProductCancellationToken,
        report_progress: ProductProgressReporter,
    ) -> ProductJobResult:
        if request.job_type is not ProductJobType.DC_ANALYSIS:
            raise ProductRequestError("DC service requires a DC_ANALYSIS job")
        started_at = _utc_now(self._clock)
        cancellation.raise_if_cancelled()
        report_progress("Acquiring paired DC observations.", 0, 3)
        read_result = run_read_workflow(
            self._adapter,
            self._workflow_request,
            checkpoint=cancellation.raise_if_cancelled,
        )
        cancellation.raise_if_cancelled()
        if read_result.status is not ReadWorkflowStatus.COMPLETED:
            self._output_slot.publish(ProductServiceOutput(read_result))
            report_progress("DC acquisition ended without complete evidence.", 3, 3)
            return ProductJobResult(
                request,
                _status_from_read(read_result.status),
                read_result.evidence_source,
                self._limitations,
            )

        report_progress("Running the formal DC fit and saturation policy.", 1, 3)
        batch = MeasurementBatch(read_result.measurements)
        analysis = analyze_dc_sweep(batch, self._analysis_config)
        cancellation.raise_if_cancelled()
        metadata = TestRunMetadata(
            request.job_id,
            DC_SWEEP_TEST_TYPE,
            self._configuration_id,
            self._configuration_version,
            started_at,
            _utc_now(self._clock),
            __version__,
            read_result.capabilities.device_id,
            request.profile_name,
            request.profile_version,
            read_result.evidence_source,
            tuple(
                dict.fromkeys(
                    reference.raw_record_id
                    for point in analysis.points
                    for reference in (
                        point.input_decision.reference,
                        point.output_decision.reference,
                    )
                )
            ),
        )
        evaluation = evaluate_dc_sweep(analysis, self._criteria, metadata)
        result_export = build_dc_sweep_export(evaluation, self._limitations)
        cancellation.raise_if_cancelled()
        self._output_slot.publish(ProductServiceOutput(read_result, result_export))
        report_progress("DC evaluation and result export are complete.", 3, 3)
        outcome = evaluation.test_run_result.outcome
        return ProductJobResult(
            request,
            _status_from_outcome(outcome),
            read_result.evidence_source,
            self._limitations,
            outcome,
        )


class FrequencyResponseJobService(_OwnedAdapterService):
    """Acquire explicit sweep triples, then evaluate one cutoff response."""

    def __init__(
        self,
        adapter: DeviceAdapter,
        workflow_request: ReadWorkflowRequest,
        analysis_config: FrequencyResponseAnalysisConfig,
        criteria: FrequencyResponseAcceptanceCriteria | None,
        limitations: tuple[str, ...],
        output_slot: ProductServiceOutputSlot,
        *,
        configuration_id: str = "product-frequency-response",
        configuration_version: str = "1",
        clock: Clock = lambda: datetime.now(timezone.utc),
    ) -> None:
        super().__init__(adapter)
        if not isinstance(workflow_request, ReadWorkflowRequest):
            raise ProductRequestError("workflow_request must be a ReadWorkflowRequest")
        if not isinstance(analysis_config, FrequencyResponseAnalysisConfig):
            raise ProductRequestError(
                "analysis_config must be a FrequencyResponseAnalysisConfig"
            )
        if criteria is not None and not isinstance(
            criteria, FrequencyResponseAcceptanceCriteria
        ):
            raise ProductRequestError(
                "criteria must be FrequencyResponseAcceptanceCriteria or None"
            )
        if not isinstance(output_slot, ProductServiceOutputSlot):
            raise ProductRequestError("output_slot must be a ProductServiceOutputSlot")
        _require_callable("clock", clock)
        self._validate_workflow(workflow_request, analysis_config)
        self._workflow_request = workflow_request
        self._analysis_config = analysis_config
        self._criteria = criteria
        self._limitations = _require_limitations(limitations)
        self._output_slot = output_slot
        self._configuration_id = configuration_id
        self._configuration_version = configuration_version
        self._clock = clock

    @staticmethod
    def _validate_workflow(
        workflow_request: ReadWorkflowRequest,
        config: FrequencyResponseAnalysisConfig,
    ) -> None:
        requirements = workflow_request.requirements
        if len(requirements) != 3:
            raise ProductRequestError(
                "frequency-response workflow requires three channel reads"
            )
        if tuple(requirement.channel for requirement in requirements) != (
            config.frequency_channel,
            config.input_amplitude_channel,
            config.output_amplitude_channel,
        ):
            raise ProductRequestError(
                "frequency-response workflow channels must match the analysis config"
            )
        if any(
            requirement.operation is not ReadOperation.ANALOG
            for requirement in requirements
        ):
            raise ProductRequestError(
                "frequency-response workflow channels must use analog reads"
            )
        if requirements[0].unit is not MeasurementUnit.HERTZ:
            raise ProductRequestError("frequency-response frequency unit must be Hz")
        if any(
            requirement.unit is not config.normalized_amplitude_unit
            for requirement in requirements[1:]
        ):
            raise ProductRequestError(
                "frequency-response amplitude units must match the analysis config"
            )
        if len({requirement.sample_count for requirement in requirements}) != 1:
            raise ProductRequestError(
                "frequency-response workflow sample counts must match"
            )

    def run(
        self,
        request: ProductJobRequest,
        cancellation: ProductCancellationToken,
        report_progress: ProductProgressReporter,
    ) -> ProductJobResult:
        if request.job_type is not ProductJobType.FREQUENCY_RESPONSE_ANALYSIS:
            raise ProductRequestError(
                "frequency-response service requires a FREQUENCY_RESPONSE_ANALYSIS job"
            )
        started_at = _utc_now(self._clock)
        cancellation.raise_if_cancelled()
        report_progress("Acquiring explicit frequency-response observations.", 0, 3)
        read_result = run_read_workflow(
            self._adapter,
            self._workflow_request,
            checkpoint=cancellation.raise_if_cancelled,
        )
        cancellation.raise_if_cancelled()
        if read_result.status is not ReadWorkflowStatus.COMPLETED:
            self._output_slot.publish(ProductServiceOutput(read_result))
            report_progress(
                "Frequency-response acquisition ended without complete evidence.",
                3,
                3,
            )
            return ProductJobResult(
                request,
                _status_from_read(read_result.status),
                read_result.evidence_source,
                self._limitations,
            )

        report_progress("Calculating amplitude ratio and the -3 dB crossing.", 1, 3)
        frequencies = MeasurementBatch(
            tuple(
                measurement
                for measurement in read_result.measurements
                if measurement.channel == self._analysis_config.frequency_channel
            )
        )
        inputs = MeasurementBatch(
            tuple(
                measurement
                for measurement in read_result.measurements
                if measurement.channel == self._analysis_config.input_amplitude_channel
            )
        )
        outputs = MeasurementBatch(
            tuple(
                measurement
                for measurement in read_result.measurements
                if measurement.channel == self._analysis_config.output_amplitude_channel
            )
        )
        analysis = analyze_frequency_response(
            frequencies,
            inputs,
            outputs,
            self._analysis_config,
        )
        cancellation.raise_if_cancelled()
        raw_ids = tuple(
            dict.fromkeys(
                reference.raw_record_id
                for point in analysis.points
                for reference in (
                    point.frequency_decision.reference,
                    point.input_decision.reference,
                    point.output_decision.reference,
                )
            )
        )
        metadata = TestRunMetadata(
            request.job_id,
            FREQUENCY_RESPONSE_TEST_TYPE,
            self._configuration_id,
            self._configuration_version,
            started_at,
            _utc_now(self._clock),
            __version__,
            read_result.capabilities.device_id,
            request.profile_name,
            request.profile_version,
            read_result.evidence_source,
            raw_ids,
        )
        evaluation = evaluate_frequency_response(analysis, self._criteria, metadata)
        result_export = build_frequency_response_export(
            evaluation,
            self._limitations,
        )
        cancellation.raise_if_cancelled()
        self._output_slot.publish(ProductServiceOutput(read_result, result_export))
        report_progress(
            "Frequency-response evaluation and result export are complete.",
            3,
            3,
        )
        outcome = evaluation.test_run_result.outcome
        return ProductJobResult(
            request,
            _status_from_outcome(outcome),
            read_result.evidence_source,
            self._limitations,
            outcome,
        )


class CalibrationJobService(_OwnedAdapterService):
    """Acquire observed/reference pairs, fit coefficients, and evaluate errors."""

    def __init__(
        self,
        adapter: DeviceAdapter,
        workflow_request: ReadWorkflowRequest,
        analysis_config: CalibrationFitConfig,
        criteria: CalibrationAcceptanceCriteria | None,
        limitations: tuple[str, ...],
        output_slot: ProductServiceOutputSlot,
        *,
        configuration_id: str = "product-calibration",
        configuration_version: str = "1",
        clock: Clock = lambda: datetime.now(timezone.utc),
    ) -> None:
        super().__init__(adapter)
        if not isinstance(workflow_request, ReadWorkflowRequest):
            raise ProductRequestError("workflow_request must be a ReadWorkflowRequest")
        if not isinstance(analysis_config, CalibrationFitConfig):
            raise ProductRequestError("analysis_config must be a CalibrationFitConfig")
        if criteria is not None and not isinstance(
            criteria, CalibrationAcceptanceCriteria
        ):
            raise ProductRequestError(
                "criteria must be CalibrationAcceptanceCriteria or None"
            )
        if not isinstance(output_slot, ProductServiceOutputSlot):
            raise ProductRequestError("output_slot must be a ProductServiceOutputSlot")
        _require_callable("clock", clock)
        self._validate_workflow(workflow_request, analysis_config)
        self._workflow_request = workflow_request
        self._analysis_config = analysis_config
        self._criteria = criteria
        self._limitations = _require_limitations(limitations)
        self._output_slot = output_slot
        self._configuration_id = configuration_id
        self._configuration_version = configuration_version
        self._clock = clock

    @staticmethod
    def _validate_workflow(
        workflow_request: ReadWorkflowRequest,
        config: CalibrationFitConfig,
    ) -> None:
        requirements = workflow_request.requirements
        if len(requirements) != 2:
            raise ProductRequestError("calibration workflow requires two channel reads")
        if tuple(requirement.channel for requirement in requirements) != (
            config.observed_channel,
            config.reference_channel,
        ):
            raise ProductRequestError(
                "calibration workflow channels must match the fit config"
            )
        if any(
            requirement.operation is not ReadOperation.ANALOG
            for requirement in requirements
        ):
            raise ProductRequestError("calibration workflow channels must be analog")
        if requirements[0].sample_count != requirements[1].sample_count:
            raise ProductRequestError("calibration workflow sample counts must match")

    def run(
        self,
        request: ProductJobRequest,
        cancellation: ProductCancellationToken,
        report_progress: ProductProgressReporter,
    ) -> ProductJobResult:
        if request.job_type is not ProductJobType.CALIBRATION_ANALYSIS:
            raise ProductRequestError(
                "calibration service requires a CALIBRATION_ANALYSIS job"
            )
        started_at = _utc_now(self._clock)
        cancellation.raise_if_cancelled()
        report_progress("Acquiring observed/reference calibration pairs.", 0, 3)
        read_result = run_read_workflow(
            self._adapter,
            self._workflow_request,
            checkpoint=cancellation.raise_if_cancelled,
        )
        cancellation.raise_if_cancelled()
        if read_result.status is not ReadWorkflowStatus.COMPLETED:
            self._output_slot.publish(ProductServiceOutput(read_result))
            report_progress(
                "Calibration acquisition ended without complete evidence.", 3, 3
            )
            return ProductJobResult(
                request,
                _status_from_read(read_result.status),
                read_result.evidence_source,
                self._limitations,
            )

        report_progress("Fitting versioned linear calibration coefficients.", 1, 3)
        observed = MeasurementBatch(
            tuple(
                measurement
                for measurement in read_result.measurements
                if measurement.channel == self._analysis_config.observed_channel
            )
        )
        reference = MeasurementBatch(
            tuple(
                measurement
                for measurement in read_result.measurements
                if measurement.channel == self._analysis_config.reference_channel
            )
        )
        analysis = fit_linear_calibration(observed, reference, self._analysis_config)
        cancellation.raise_if_cancelled()
        raw_ids = tuple(
            dict.fromkeys(
                reference.raw_record_id
                for point in analysis.points
                for reference in (
                    point.observed_decision.reference,
                    point.reference_decision.reference,
                )
            )
        )
        metadata = TestRunMetadata(
            request.job_id,
            CALIBRATION_TEST_TYPE,
            self._configuration_id,
            self._configuration_version,
            started_at,
            _utc_now(self._clock),
            __version__,
            read_result.capabilities.device_id,
            request.profile_name,
            request.profile_version,
            read_result.evidence_source,
            raw_ids,
        )
        evaluation = evaluate_calibration(analysis, self._criteria, metadata)
        result_export = build_calibration_export(evaluation, self._limitations)
        cancellation.raise_if_cancelled()
        self._output_slot.publish(
            ProductServiceOutput(read_result, result_export, analysis.coefficients)
        )
        report_progress("Calibration evaluation and result export are complete.", 3, 3)
        outcome = evaluation.test_run_result.outcome
        return ProductJobResult(
            request,
            _status_from_outcome(outcome),
            read_result.evidence_source,
            self._limitations,
            outcome,
        )


class HysteresisJobService(_OwnedAdapterService):
    """Acquire ordered observations, then call formal hysteresis evaluation."""

    def __init__(
        self,
        adapter: DeviceAdapter,
        workflow_request: ReadWorkflowRequest,
        analysis_config: HysteresisAnalysisConfig,
        criteria: HysteresisAcceptanceCriteria | None,
        rising_count: int,
        falling_count: int,
        limitations: tuple[str, ...],
        output_slot: ProductServiceOutputSlot,
        *,
        configuration_id: str = "product-hysteresis",
        configuration_version: str = "1",
        clock: Clock = lambda: datetime.now(timezone.utc),
    ) -> None:
        super().__init__(adapter)
        if not isinstance(workflow_request, ReadWorkflowRequest):
            raise ProductRequestError("workflow_request must be a ReadWorkflowRequest")
        if not isinstance(analysis_config, HysteresisAnalysisConfig):
            raise ProductRequestError(
                "analysis_config must be a HysteresisAnalysisConfig"
            )
        if criteria is not None and not isinstance(
            criteria, HysteresisAcceptanceCriteria
        ):
            raise ProductRequestError(
                "criteria must be HysteresisAcceptanceCriteria or None"
            )
        for name, count in (
            ("rising_count", rising_count),
            ("falling_count", falling_count),
        ):
            if isinstance(count, bool) or not isinstance(count, int) or count < 2:
                raise ProductRequestError(f"{name} must be an integer of at least two")
        if not isinstance(output_slot, ProductServiceOutputSlot):
            raise ProductRequestError("output_slot must be a ProductServiceOutputSlot")
        _require_callable("clock", clock)
        self._validate_workflow(
            workflow_request,
            analysis_config,
            rising_count + falling_count,
        )
        self._workflow_request = workflow_request
        self._analysis_config = analysis_config
        self._criteria = criteria
        self._rising_count = rising_count
        self._falling_count = falling_count
        self._limitations = _require_limitations(limitations)
        self._output_slot = output_slot
        self._configuration_id = configuration_id
        self._configuration_version = configuration_version
        self._clock = clock

    @staticmethod
    def _validate_workflow(
        workflow_request: ReadWorkflowRequest,
        config: HysteresisAnalysisConfig,
        total_count: int,
    ) -> None:
        requirements = workflow_request.requirements
        if len(requirements) != 2:
            raise ProductRequestError("hysteresis workflow requires two channel reads")
        if tuple(requirement.channel for requirement in requirements) != (
            config.input_channel,
            config.state_channel,
        ):
            raise ProductRequestError(
                "hysteresis workflow channels must match the analysis config"
            )
        if (
            requirements[0].operation is not ReadOperation.ANALOG
            or requirements[1].operation is not ReadOperation.DIGITAL
        ):
            raise ProductRequestError(
                "hysteresis workflow requires analog input and digital state"
            )
        if any(requirement.sample_count != total_count for requirement in requirements):
            raise ProductRequestError(
                "hysteresis workflow counts must equal rising plus falling counts"
            )

    def run(
        self,
        request: ProductJobRequest,
        cancellation: ProductCancellationToken,
        report_progress: ProductProgressReporter,
    ) -> ProductJobResult:
        if request.job_type is not ProductJobType.HYSTERESIS_ANALYSIS:
            raise ProductRequestError(
                "hysteresis service requires a HYSTERESIS_ANALYSIS job"
            )
        started_at = _utc_now(self._clock)
        cancellation.raise_if_cancelled()
        report_progress("Acquiring ordered hysteresis observations.", 0, 3)
        read_result = run_read_workflow(
            self._adapter,
            self._workflow_request,
            checkpoint=cancellation.raise_if_cancelled,
        )
        cancellation.raise_if_cancelled()
        if read_result.status is not ReadWorkflowStatus.COMPLETED:
            self._output_slot.publish(ProductServiceOutput(read_result))
            report_progress(
                "Hysteresis acquisition ended without complete evidence.", 3, 3
            )
            return ProductJobResult(
                request,
                _status_from_read(read_result.status),
                read_result.evidence_source,
                self._limitations,
            )

        report_progress("Building explicit rising and falling observation pairs.", 1, 3)
        inputs = tuple(
            measurement
            for measurement in read_result.measurements
            if measurement.channel == self._analysis_config.input_channel
        )
        states = tuple(
            measurement
            for measurement in read_result.measurements
            if measurement.channel == self._analysis_config.state_channel
        )
        paired = tuple(
            measurement for pair in zip(inputs, states) for measurement in pair
        )
        split_index = self._rising_count * 2
        cycle = HysteresisCycleInput(
            0,
            MeasurementBatch(paired[:split_index]),
            MeasurementBatch(paired[split_index:]),
        )
        analysis = analyze_hysteresis((cycle,), self._analysis_config)
        cancellation.raise_if_cancelled()
        raw_ids = tuple(
            dict.fromkeys(
                reference.raw_record_id
                for analyzed_cycle in analysis.cycles
                for point in analyzed_cycle.rising_points
                + analyzed_cycle.falling_points
                for reference in (
                    point.input_decision.reference,
                    point.state_reference,
                )
            )
        )
        metadata = TestRunMetadata(
            request.job_id,
            HYSTERESIS_TEST_TYPE,
            self._configuration_id,
            self._configuration_version,
            started_at,
            _utc_now(self._clock),
            __version__,
            read_result.capabilities.device_id,
            request.profile_name,
            request.profile_version,
            read_result.evidence_source,
            raw_ids,
        )
        evaluation = evaluate_hysteresis(analysis, self._criteria, metadata)
        result_export = build_hysteresis_export(evaluation, self._limitations)
        cancellation.raise_if_cancelled()
        self._output_slot.publish(ProductServiceOutput(read_result, result_export))
        report_progress("Hysteresis evaluation and result export are complete.", 3, 3)
        outcome = evaluation.test_run_result.outcome
        return ProductJobResult(
            request,
            _status_from_outcome(outcome),
            read_result.evidence_source,
            self._limitations,
            outcome,
        )


def make_read_service_factory(
    adapter_factory: AdapterFactory,
    workflow_request: ReadWorkflowRequest,
    limitations: tuple[str, ...],
    output_slot: ProductServiceOutputSlot,
) -> ProductJobServiceFactory:
    """Bind immutable read inputs while constructing resources in the worker."""

    _require_callable("adapter_factory", adapter_factory)

    def create(request: ProductJobRequest) -> ProductJobService:
        return ReadJobService(
            adapter_factory(request), workflow_request, limitations, output_slot
        )

    return create


def make_live_monitor_service_factory(
    adapter_factory: AdapterFactory,
    workflow_request: ReadWorkflowRequest,
    limitations: tuple[str, ...],
    output_slot: ProductServiceOutputSlot,
    live_session: LiveMonitorSession,
    *,
    sample_interval_seconds: float,
) -> ProductJobServiceFactory:
    """Bind one finite monitor while constructing resources in the worker."""

    _require_callable("adapter_factory", adapter_factory)

    def create(request: ProductJobRequest) -> ProductJobService:
        return LiveMonitorJobService(
            adapter_factory(request),
            workflow_request,
            limitations,
            output_slot,
            live_session,
            sample_interval_seconds=sample_interval_seconds,
        )

    return create


def make_calibration_service_factory(
    adapter_factory: AdapterFactory,
    workflow_request: ReadWorkflowRequest,
    analysis_config: CalibrationFitConfig,
    criteria: CalibrationAcceptanceCriteria | None,
    limitations: tuple[str, ...],
    output_slot: ProductServiceOutputSlot,
    *,
    clock: Clock = lambda: datetime.now(timezone.utc),
) -> ProductJobServiceFactory:
    """Bind a calibration fit while constructing resources in the worker."""

    _require_callable("adapter_factory", adapter_factory)

    def create(request: ProductJobRequest) -> ProductJobService:
        return CalibrationJobService(
            adapter_factory(request),
            workflow_request,
            analysis_config,
            criteria,
            limitations,
            output_slot,
            clock=clock,
        )

    return create


def make_dc_sweep_service_factory(
    adapter_factory: AdapterFactory,
    workflow_request: ReadWorkflowRequest,
    analysis_config: DCSweepAnalysisConfig,
    criteria: DCSweepAcceptanceCriteria | None,
    limitations: tuple[str, ...],
    output_slot: ProductServiceOutputSlot,
    *,
    clock: Clock = lambda: datetime.now(timezone.utc),
) -> ProductJobServiceFactory:
    """Bind one formal DC path while constructing resources in the worker."""

    _require_callable("adapter_factory", adapter_factory)

    def create(request: ProductJobRequest) -> ProductJobService:
        return DCSweepJobService(
            adapter_factory(request),
            workflow_request,
            analysis_config,
            criteria,
            limitations,
            output_slot,
            clock=clock,
        )

    return create


def make_frequency_response_service_factory(
    adapter_factory: AdapterFactory,
    workflow_request: ReadWorkflowRequest,
    analysis_config: FrequencyResponseAnalysisConfig,
    criteria: FrequencyResponseAcceptanceCriteria | None,
    limitations: tuple[str, ...],
    output_slot: ProductServiceOutputSlot,
    *,
    clock: Clock = lambda: datetime.now(timezone.utc),
) -> ProductJobServiceFactory:
    """Bind one formal frequency-response path for worker execution."""

    _require_callable("adapter_factory", adapter_factory)

    def create(request: ProductJobRequest) -> ProductJobService:
        return FrequencyResponseJobService(
            adapter_factory(request),
            workflow_request,
            analysis_config,
            criteria,
            limitations,
            output_slot,
            clock=clock,
        )

    return create


def make_hysteresis_service_factory(
    adapter_factory: AdapterFactory,
    workflow_request: ReadWorkflowRequest,
    analysis_config: HysteresisAnalysisConfig,
    criteria: HysteresisAcceptanceCriteria | None,
    rising_count: int,
    falling_count: int,
    limitations: tuple[str, ...],
    output_slot: ProductServiceOutputSlot,
    *,
    clock: Clock = lambda: datetime.now(timezone.utc),
) -> ProductJobServiceFactory:
    """Bind one formal hysteresis path while constructing resources in worker."""

    _require_callable("adapter_factory", adapter_factory)

    def create(request: ProductJobRequest) -> ProductJobService:
        return HysteresisJobService(
            adapter_factory(request),
            workflow_request,
            analysis_config,
            criteria,
            rising_count,
            falling_count,
            limitations,
            output_slot,
            clock=clock,
        )

    return create


def execute_product_job(
    request: ProductJobRequest,
    service_factory: ProductJobServiceFactory,
    output_slot: ProductServiceOutputSlot,
    *,
    join_timeout_s: float = DEFAULT_PRODUCT_JOIN_TIMEOUT_S,
    cancellation_requested: Callable[[], bool] | None = None,
    report_event: Callable[[ProductJobEvent], None] | None = None,
) -> ProductJobExecution:
    """Run, join, and close one worker; Ctrl+C becomes cooperative cancellation."""

    if not isinstance(request, ProductJobRequest):
        raise ProductRequestError("request must be a ProductJobRequest")
    if not callable(service_factory):
        raise ProductRequestError("service_factory must be callable")
    if not isinstance(output_slot, ProductServiceOutputSlot):
        raise ProductRequestError("output_slot must be a ProductServiceOutputSlot")
    if cancellation_requested is not None and not callable(cancellation_requested):
        raise ProductRequestError("cancellation_requested must be callable or None")
    if report_event is not None and not callable(report_event):
        raise ProductRequestError("report_event must be callable or None")
    worker = ProductJobWorker(service_factory, join_timeout_s=join_timeout_s)
    interrupted = False
    last_reported_event_index = 0

    def forward_events() -> None:
        nonlocal last_reported_event_index
        if report_event is None:
            return
        for event in worker.events:
            if event.index > last_reported_event_index:
                report_event(event)
                last_reported_event_index = event.index

    try:
        worker.start(request)
        try:
            deadline = monotonic() + join_timeout_s
            while True:
                if (
                    cancellation_requested is not None
                    and cancellation_requested()
                    and worker.request_cancel()
                ):
                    interrupted = True
                remaining = deadline - monotonic()
                if remaining <= 0:
                    joined = False
                    break
                joined = worker.join(max(0.001, min(0.05, remaining)))
                forward_events()
                if joined:
                    break
        except KeyboardInterrupt:
            interrupted = True
            worker.cancel_and_join(join_timeout_s)
            forward_events()
        else:
            if not joined:
                worker.cancel_and_join(join_timeout_s)
                forward_events()
                raise ProductWorkerTimeoutError(
                    "the product job exceeded its bounded join timeout"
                )
        forward_events()
        output = (
            output_slot.value
            if worker.state is ProductWorkerState.SUCCEEDED and not interrupted
            else None
        )
        return ProductJobExecution(
            request,
            worker.state,
            worker.result,
            worker.issue,
            worker.events,
            output,
            worker.dropped_event_count,
            interrupted,
            worker.last_error or worker.cleanup_error,
        )
    finally:
        worker.close(join_timeout_s)


__all__ = [
    "CalibrationJobService",
    "Clock",
    "DCSweepJobService",
    "FrequencyResponseJobService",
    "HysteresisJobService",
    "LiveMonitorJobService",
    "ProductJobExecution",
    "ProductServiceOutput",
    "ProductServiceOutputSlot",
    "ReadJobService",
    "execute_product_job",
    "make_calibration_service_factory",
    "make_dc_sweep_service_factory",
    "make_frequency_response_service_factory",
    "make_hysteresis_service_factory",
    "make_live_monitor_service_factory",
    "make_read_service_factory",
]
