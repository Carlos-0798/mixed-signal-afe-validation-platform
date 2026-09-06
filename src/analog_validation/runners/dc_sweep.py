"""Controller-neutral DC sweep execution with default-deny output safety."""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from typing import cast

from analog_validation.adapters import AdapterState, DeviceAdapter
from analog_validation.analysis import (
    DC_SWEEP_TEST_TYPE,
    DCSweepAcceptanceCriteria,
    DCSweepAnalysisConfig,
    DCSweepAnalysisResult,
    DCSweepEvaluationResult,
    MeasurementBatch,
    analyze_dc_sweep,
    evaluate_dc_sweep,
)
from analog_validation.config import (
    ChannelRole,
    ValidationConfig,
    validate_config_capabilities,
)
from analog_validation.domain import (
    DeviceCapabilities,
    DeviceCommand,
    Measurement,
    MeasurementUnit,
    TestRunMetadata,
    TestRunOutcome,
    TestRunResult,
)
from analog_validation.errors import (
    AdapterDataError,
    AdapterStateError,
    AnalogValidationError,
    ReplayEndOfData,
    ValidationError,
)

DC_SWEEP_RUNNER_SCHEMA_VERSION = "dc-sweep-runner.v1"

_VOLTAGE_UNITS = frozenset({MeasurementUnit.VOLT, MeasurementUnit.MILLIVOLT})


def _require_identifier(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValidationError(f"{name} must be a non-empty stripped string")
    return value


def _require_nonnegative_integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{name} must be a non-negative integer")
    return value


def _require_finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValidationError(f"{name} must be finite")
    return number


def _freeze_setpoints(values: object) -> tuple[float, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ValidationError("setpoints must be an iterable")
    setpoints = tuple(_require_finite_number("setpoint", value) for value in values)
    if not setpoints:
        raise ValidationError("setpoints cannot be empty")
    return setpoints


@dataclass(frozen=True, slots=True)
class DCSweepPlan:
    """Immutable stimulus order and analysis contract for one DC sweep."""

    plan_id: str
    plan_version: str
    stimulus_channel: str
    unit: MeasurementUnit
    setpoints: tuple[float, ...]
    repetitions: int
    analysis_config: DCSweepAnalysisConfig
    criteria: DCSweepAcceptanceCriteria | None = None
    schema_version: str = DC_SWEEP_RUNNER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_identifier("plan_id", self.plan_id)
        _require_identifier("plan_version", self.plan_version)
        _require_identifier("stimulus_channel", self.stimulus_channel)
        if (
            not isinstance(self.unit, MeasurementUnit)
            or self.unit not in _VOLTAGE_UNITS
        ):
            raise ValidationError("unit must be V or mV")
        setpoints = _freeze_setpoints(self.setpoints)
        object.__setattr__(self, "setpoints", setpoints)
        if (
            isinstance(self.repetitions, bool)
            or not isinstance(self.repetitions, int)
            or self.repetitions < 1
        ):
            raise ValidationError("repetitions must be an integer of at least one")
        if not isinstance(self.analysis_config, DCSweepAnalysisConfig):
            raise ValidationError("analysis_config must be a DCSweepAnalysisConfig")
        if self.stimulus_channel in {
            self.analysis_config.input_channel,
            self.analysis_config.output_channel,
        }:
            raise ValidationError(
                "stimulus, input, and output channels must be distinct"
            )
        if self.analysis_config.normalized_unit is not self.unit:
            raise ValidationError("plan unit must match analysis normalized unit")
        if self.criteria is not None:
            if not isinstance(self.criteria, DCSweepAcceptanceCriteria):
                raise ValidationError(
                    "criteria must be DCSweepAcceptanceCriteria or None"
                )
            if self.criteria.normalized_unit is not self.unit:
                raise ValidationError("plan unit must match criteria normalized unit")
        if self.schema_version != DC_SWEEP_RUNNER_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported DC sweep runner schema: {self.schema_version}"
            )

    @property
    def expected_points(self) -> int:
        """Return the number of complete input/output pairs requested."""

        return len(self.setpoints) * self.repetitions

    @property
    def expected_measurements(self) -> int:
        """Return the number of analog reads required for the plan."""

        return self.expected_points * 2


@dataclass(frozen=True, slots=True)
class DCSweepAcquisitionStep:
    """One completed stimulus/read pair linked to exact record IDs."""

    sequence: int
    setpoint_index: int
    repetition_index: int
    setpoint: float
    input_record_id: str
    output_record_id: str
    schema_version: str = DC_SWEEP_RUNNER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_nonnegative_integer("sequence", self.sequence)
        _require_nonnegative_integer("setpoint_index", self.setpoint_index)
        _require_nonnegative_integer("repetition_index", self.repetition_index)
        object.__setattr__(
            self,
            "setpoint",
            _require_finite_number("setpoint", self.setpoint),
        )
        _require_identifier("input_record_id", self.input_record_id)
        _require_identifier("output_record_id", self.output_record_id)
        if self.input_record_id == self.output_record_id:
            raise ValidationError("input and output record IDs must be distinct")
        if self.schema_version != DC_SWEEP_RUNNER_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported DC sweep runner schema: {self.schema_version}"
            )


def _freeze_typed_tuple(
    name: str,
    values: object,
    expected_type: type[object],
) -> tuple[object, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ValidationError(f"{name} must be an iterable")
    frozen = tuple(values)
    if not all(isinstance(value, expected_type) for value in frozen):
        raise ValidationError(f"{name} must contain {expected_type.__name__} values")
    return frozen


@dataclass(frozen=True, slots=True)
class DCSweepRunnerResult:
    """One runner attempt without promoting incomplete evidence to PASS."""

    plan: DCSweepPlan
    capabilities: DeviceCapabilities | None
    measurements: tuple[Measurement, ...]
    completed_steps: tuple[DCSweepAcquisitionStep, ...]
    analysis: DCSweepAnalysisResult | None
    evaluation: DCSweepEvaluationResult | None
    test_run_result: TestRunResult
    schema_version: str = DC_SWEEP_RUNNER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.plan, DCSweepPlan):
            raise ValidationError("plan must be a DCSweepPlan")
        if self.capabilities is not None and not isinstance(
            self.capabilities, DeviceCapabilities
        ):
            raise ValidationError("capabilities must be DeviceCapabilities or None")
        measurements_input = _freeze_typed_tuple(
            "measurements", self.measurements, Measurement
        )
        measurements = cast(tuple[Measurement, ...], measurements_input)
        steps_input = _freeze_typed_tuple(
            "completed_steps", self.completed_steps, DCSweepAcquisitionStep
        )
        steps = cast(tuple[DCSweepAcquisitionStep, ...], steps_input)
        object.__setattr__(self, "measurements", measurements)
        object.__setattr__(self, "completed_steps", steps)
        if self.analysis is not None and not isinstance(
            self.analysis, DCSweepAnalysisResult
        ):
            raise ValidationError("analysis must be DCSweepAnalysisResult or None")
        if self.evaluation is not None and not isinstance(
            self.evaluation, DCSweepEvaluationResult
        ):
            raise ValidationError("evaluation must be DCSweepEvaluationResult or None")
        if not isinstance(self.test_run_result, TestRunResult):
            raise ValidationError("test_run_result must be a TestRunResult")
        self._validate_records(measurements, steps)
        self._validate_conclusion(measurements, steps)
        if self.schema_version != DC_SWEEP_RUNNER_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported DC sweep runner schema: {self.schema_version}"
            )

    def _validate_records(
        self,
        measurements: tuple[Measurement, ...],
        steps: tuple[DCSweepAcquisitionStep, ...],
    ) -> None:
        record_ids = tuple(value.record_id for value in measurements)
        if len(record_ids) != len(set(record_ids)):
            raise ValidationError("runner measurement record IDs must be unique")
        source = self.test_run_result.metadata.evidence_source
        if any(value.source is not source for value in measurements):
            raise ValidationError("runner measurement sources must match metadata")
        if self.test_run_result.evidence_record_ids != record_ids:
            raise ValidationError("TestRun evidence IDs must match runner measurements")
        raw_ids = tuple(dict.fromkeys(value.raw_record_id for value in measurements))
        if self.test_run_result.metadata.input_record_ids != raw_ids:
            raise ValidationError("TestRun raw IDs must match runner measurements")
        for index, measurement in enumerate(measurements):
            expected_channel = (
                self.plan.analysis_config.input_channel
                if index % 2 == 0
                else self.plan.analysis_config.output_channel
            )
            if measurement.channel != expected_channel:
                raise ValidationError("runner measurement order must match the plan")
            if measurement.unit is not self.plan.unit:
                raise ValidationError("runner measurement units must match the plan")
        if len(measurements) not in {len(steps) * 2, len(steps) * 2 + 1}:
            raise ValidationError(
                "runner measurements must contain complete pairs plus at most one input"
            )
        expected_order = tuple(
            (setpoint_index, repetition_index, setpoint)
            for setpoint_index, setpoint in enumerate(self.plan.setpoints)
            for repetition_index in range(self.plan.repetitions)
        )
        if len(steps) > len(expected_order):
            raise ValidationError("completed_steps exceed the DC sweep plan")
        for sequence, step in enumerate(steps):
            expected_setpoint_index, expected_repetition, expected_setpoint = (
                expected_order[sequence]
            )
            if step.sequence != sequence:
                raise ValidationError("completed step sequence must be contiguous")
            if (
                step.setpoint_index != expected_setpoint_index
                or step.repetition_index != expected_repetition
                or step.setpoint != expected_setpoint
            ):
                raise ValidationError("completed steps must follow the plan order")
            input_measurement = measurements[sequence * 2]
            output_measurement = measurements[sequence * 2 + 1]
            if (
                step.input_record_id != input_measurement.record_id
                or step.output_record_id != output_measurement.record_id
            ):
                raise ValidationError(
                    "completed step record IDs must match measurements"
                )

    def _validate_conclusion(
        self,
        measurements: tuple[Measurement, ...],
        steps: tuple[DCSweepAcquisitionStep, ...],
    ) -> None:
        outcome = self.test_run_result.outcome
        if self.capabilities is not None and outcome is not TestRunOutcome.ERROR:
            metadata = self.test_run_result.metadata
            if metadata.device_id != self.capabilities.device_id:
                raise ValidationError("TestRun device ID must match capabilities")
            if (
                metadata.profile_name != self.capabilities.profile_name
                or metadata.profile_version != self.capabilities.profile_version
            ):
                raise ValidationError("TestRun profile must match capabilities")
        if self.evaluation is None:
            if self.analysis is not None:
                raise ValidationError("analysis without evaluation is not allowed")
            if outcome in {TestRunOutcome.PASS, TestRunOutcome.FAIL}:
                raise ValidationError("PASS/FAIL runner results require evaluation")
            return
        if self.analysis is None or self.evaluation.analysis != self.analysis:
            raise ValidationError("evaluation must reference the runner analysis")
        if self.evaluation.criteria != self.plan.criteria:
            raise ValidationError("evaluation criteria must match the runner plan")
        if self.evaluation.test_run_result != self.test_run_result:
            raise ValidationError("evaluation and runner TestRun results must match")
        if len(measurements) != self.plan.expected_measurements:
            raise ValidationError("evaluated runner results require all measurements")

    @property
    def outcome(self) -> TestRunOutcome:
        """Return the attempt's explicit TestRun outcome."""

        return self.test_run_result.outcome


def _append_once(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _static_preflight(
    adapter: DeviceAdapter,
    plan: DCSweepPlan,
    config: ValidationConfig,
    metadata: TestRunMetadata,
) -> DeviceCommand:
    if adapter.state is not AdapterState.DISCONNECTED:
        raise AdapterStateError("DC sweep runner requires a disconnected adapter")
    if not config.allow_output:
        raise ValidationError("DC sweep runner requires allow_output=true")
    if config.evidence_source is not adapter.evidence_source:
        raise ValidationError("configuration evidence source must match adapter")
    if metadata.test_type != DC_SWEEP_TEST_TYPE:
        raise ValidationError(f"metadata test_type must be {DC_SWEEP_TEST_TYPE}")
    if metadata.evidence_source is not adapter.evidence_source:
        raise ValidationError("metadata evidence source must match adapter")
    if metadata.input_record_ids:
        raise ValidationError("runner metadata template input_record_ids must be empty")
    if (
        metadata.configuration_id != config.config_id
        or metadata.configuration_version != config.config_version
    ):
        raise ValidationError("metadata configuration must match ValidationConfig")
    if (
        metadata.profile_name != config.profile.name
        or metadata.profile_version != config.profile.version
    ):
        raise ValidationError("metadata profile must match ValidationConfig")

    stimulus = config.get_channel(plan.stimulus_channel)
    if not stimulus.enabled or not stimulus.role.is_output:
        raise ValidationError("stimulus channel must be an enabled output")
    if stimulus.unit is not plan.unit:
        raise ValidationError("stimulus channel unit must match the plan")
    output_command = (
        DeviceCommand.SET_ANALOG_STIMULUS
        if stimulus.role is ChannelRole.ANALOG_OUTPUT
        else DeviceCommand.SET_PWM_STIMULUS
    )
    for channel_name in (
        plan.analysis_config.input_channel,
        plan.analysis_config.output_channel,
    ):
        channel = config.get_channel(channel_name)
        if not channel.enabled or channel.role is not ChannelRole.ANALOG_INPUT:
            raise ValidationError(
                f"analysis channel {channel_name} must be an enabled analog input"
            )
        if channel.unit is not plan.unit:
            raise ValidationError(
                f"analysis channel {channel_name} unit must match the plan"
            )
    for setpoint in plan.setpoints:
        config.require_output(plan.stimulus_channel, setpoint, plan.unit)
    return output_command


def _missing_capabilities(
    plan: DCSweepPlan,
    capabilities: DeviceCapabilities,
    output_command: DeviceCommand,
) -> tuple[str, ...]:
    missing: list[str] = []
    if not capabilities.supports(DeviceCommand.READ_MEASUREMENT):
        _append_once(missing, f"command:{DeviceCommand.READ_MEASUREMENT.value}")
    for channel in (
        plan.analysis_config.input_channel,
        plan.analysis_config.output_channel,
    ):
        if channel not in capabilities.adc_channels:
            _append_once(missing, f"analog-channel:{channel}")
        elif capabilities.get_input_range(channel).unit is not plan.unit:
            _append_once(missing, f"analog-unit:{channel}:{plan.unit.value}")
    if not capabilities.supports(output_command):
        _append_once(missing, f"command:{output_command.value}")
    output_channels = (
        capabilities.dac_channels
        if output_command is DeviceCommand.SET_ANALOG_STIMULUS
        else capabilities.pwm_channels
    )
    if plan.stimulus_channel not in output_channels:
        _append_once(missing, f"output-channel:{plan.stimulus_channel}")
    elif capabilities.get_output_range(plan.stimulus_channel).unit is not plan.unit:
        _append_once(
            missing,
            f"output-unit:{plan.stimulus_channel}:{plan.unit.value}",
        )
    if not capabilities.supports_safe_shutdown:
        _append_once(missing, f"command:{DeviceCommand.SAFE_SHUTDOWN.value}")
    return tuple(missing)


def _metadata_with_measurements(
    template: TestRunMetadata,
    measurements: tuple[Measurement, ...],
) -> TestRunMetadata:
    raw_ids = tuple(dict.fromkeys(item.raw_record_id for item in measurements))
    return replace(template, input_record_ids=raw_ids)


def _attempt_result(
    plan: DCSweepPlan,
    capabilities: DeviceCapabilities | None,
    metadata_template: TestRunMetadata,
    measurements: tuple[Measurement, ...],
    steps: tuple[DCSweepAcquisitionStep, ...],
    outcome: TestRunOutcome,
    summary: str,
    missing: tuple[str, ...],
) -> DCSweepRunnerResult:
    metadata = _metadata_with_measurements(metadata_template, measurements)
    test_run = TestRunResult(
        metadata=metadata,
        outcome=outcome,
        summary=summary,
        evidence_record_ids=tuple(item.record_id for item in measurements),
        missing_requirements=missing,
    )
    return DCSweepRunnerResult(
        plan=plan,
        capabilities=capabilities,
        measurements=measurements,
        completed_steps=steps,
        analysis=None,
        evaluation=None,
        test_run_result=test_run,
    )


def _execution_gap(prefix: str, error: BaseException) -> str:
    return f"{prefix}:{type(error).__name__}"


def _never_abort() -> bool:
    return False


def run_dc_sweep(
    adapter: DeviceAdapter,
    plan: DCSweepPlan,
    config: ValidationConfig,
    metadata: TestRunMetadata,
    *,
    settle: Callable[[float], None] = time.sleep,
    abort_requested: Callable[[], bool] = _never_abort,
) -> DCSweepRunnerResult:
    """Execute one fully preflighted sweep and always release the adapter.

    This function verifies host-side lifecycle behavior only. A successful
    cleanup call is not proof that a physical output reached a safe voltage.
    """

    if not isinstance(adapter, DeviceAdapter):
        raise ValidationError("adapter must be a DeviceAdapter")
    if not isinstance(plan, DCSweepPlan):
        raise ValidationError("plan must be a DCSweepPlan")
    if not isinstance(config, ValidationConfig):
        raise ValidationError("config must be a ValidationConfig")
    if not isinstance(metadata, TestRunMetadata):
        raise ValidationError("metadata must be a TestRunMetadata")
    if not callable(settle):
        raise ValidationError("settle must be callable")
    if not callable(abort_requested):
        raise ValidationError("abort_requested must be callable")
    output_command = _static_preflight(adapter, plan, config, metadata)

    capabilities: DeviceCapabilities | None = None
    measurements: list[Measurement] = []
    steps: list[DCSweepAcquisitionStep] = []
    pending_outcome: TestRunOutcome | None = None
    pending_summary = ""
    pending_missing: tuple[str, ...] = ()
    cleanup_error: BaseException | None = None

    try:
        adapter.connect()
        capabilities = adapter.get_capabilities()
        if metadata.device_id != capabilities.device_id:
            raise ValidationError("metadata device_id must match capabilities")
        missing = _missing_capabilities(plan, capabilities, output_command)
        if missing:
            pending_outcome = TestRunOutcome.UNSUPPORTED
            pending_summary = "DC sweep runner unsupported"
            pending_missing = missing
        else:
            validate_config_capabilities(config, capabilities)
            adapter.arm(config)
            stop = False
            for setpoint_index, setpoint in enumerate(plan.setpoints):
                for repetition_index in range(plan.repetitions):
                    if abort_requested():
                        pending_outcome = TestRunOutcome.INCOMPLETE
                        pending_summary = "DC sweep runner aborted"
                        pending_missing = (
                            "runner-aborted",
                            f"measurements:{len(measurements)}/{plan.expected_measurements}",
                        )
                        stop = True
                        break
                    adapter.set_stimulus(
                        plan.stimulus_channel,
                        setpoint,
                        plan.unit,
                    )
                    settle(config.timeouts.settle_s)
                    if abort_requested():
                        pending_outcome = TestRunOutcome.INCOMPLETE
                        pending_summary = "DC sweep runner aborted"
                        pending_missing = (
                            "runner-aborted",
                            f"measurements:{len(measurements)}/{plan.expected_measurements}",
                        )
                        stop = True
                        break
                    input_measurement = adapter.read_measurement(
                        plan.analysis_config.input_channel
                    )
                    if any(
                        item.record_id == input_measurement.record_id
                        for item in measurements
                    ):
                        raise AdapterDataError(
                            "adapter returned a duplicate measurement record ID"
                        )
                    measurements.append(input_measurement)
                    output_measurement = adapter.read_measurement(
                        plan.analysis_config.output_channel
                    )
                    if any(
                        item.record_id == output_measurement.record_id
                        for item in measurements
                    ):
                        raise AdapterDataError(
                            "adapter returned a duplicate measurement record ID"
                        )
                    measurements.append(output_measurement)
                    steps.append(
                        DCSweepAcquisitionStep(
                            sequence=len(steps),
                            setpoint_index=setpoint_index,
                            repetition_index=repetition_index,
                            setpoint=setpoint,
                            input_record_id=input_measurement.record_id,
                            output_record_id=output_measurement.record_id,
                        )
                    )
                if stop:
                    break
    except ReplayEndOfData:
        pending_outcome = TestRunOutcome.INCOMPLETE
        pending_summary = "DC sweep acquisition incomplete"
        pending_missing = (
            "acquisition-end-of-data",
            f"measurements:{len(measurements)}/{plan.expected_measurements}",
        )
    except KeyboardInterrupt:
        pending_outcome = TestRunOutcome.INCOMPLETE
        pending_summary = "DC sweep runner interrupted"
        pending_missing = (
            "runner-interrupted",
            f"measurements:{len(measurements)}/{plan.expected_measurements}",
        )
    except Exception as error:  # noqa: BLE001 - injected callback boundary
        pending_outcome = TestRunOutcome.ERROR
        pending_summary = "DC sweep runner error"
        pending_missing = (_execution_gap("execution-error", error),)
    finally:
        if adapter.is_connected:
            try:
                adapter.disconnect()
            except AnalogValidationError as error:
                cleanup_error = error

    measurements_tuple = tuple(measurements)
    steps_tuple = tuple(steps)
    if cleanup_error is not None:
        return _attempt_result(
            plan,
            capabilities,
            metadata,
            measurements_tuple,
            steps_tuple,
            TestRunOutcome.ERROR,
            "DC sweep runner cleanup error",
            (_execution_gap("cleanup-error", cleanup_error),),
        )
    if pending_outcome is not None:
        return _attempt_result(
            plan,
            capabilities,
            metadata,
            measurements_tuple,
            steps_tuple,
            pending_outcome,
            pending_summary,
            pending_missing,
        )

    final_metadata = _metadata_with_measurements(metadata, measurements_tuple)
    try:
        analysis = analyze_dc_sweep(
            MeasurementBatch(measurements_tuple), plan.analysis_config
        )
        evaluation = evaluate_dc_sweep(analysis, plan.criteria, final_metadata)
    except AnalogValidationError as error:
        return _attempt_result(
            plan,
            capabilities,
            metadata,
            measurements_tuple,
            steps_tuple,
            TestRunOutcome.ERROR,
            "DC sweep analysis error",
            (_execution_gap("analysis-error", error),),
        )
    return DCSweepRunnerResult(
        plan=plan,
        capabilities=capabilities,
        measurements=measurements_tuple,
        completed_steps=steps_tuple,
        analysis=analysis,
        evaluation=evaluation,
        test_run_result=evaluation.test_run_result,
    )


__all__ = [
    "DC_SWEEP_RUNNER_SCHEMA_VERSION",
    "DCSweepAcquisitionStep",
    "DCSweepPlan",
    "DCSweepRunnerResult",
    "run_dc_sweep",
]
