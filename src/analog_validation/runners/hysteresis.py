"""Safety-gated rising/falling hysteresis acquisition runner."""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from itertools import pairwise

from analog_validation.adapters import AdapterState, DeviceAdapter
from analog_validation.analysis import (
    HYSTERESIS_TEST_TYPE,
    HysteresisAcceptanceCriteria,
    HysteresisAnalysisConfig,
    HysteresisAnalysisResult,
    HysteresisCycleInput,
    HysteresisEvaluationResult,
    MeasurementBatch,
    SweepDirection,
    analyze_hysteresis,
    evaluate_hysteresis,
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

HYSTERESIS_RUNNER_SCHEMA_VERSION = "hysteresis-runner.v1"

_VOLTAGE_UNITS = frozenset({MeasurementUnit.VOLT, MeasurementUnit.MILLIVOLT})


def _identifier(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValidationError(f"{name} must be a non-empty stripped string")
    return value


def _index(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{name} must be a non-negative integer")
    return value


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValidationError(f"{name} must be finite")
    return number


def _setpoints(name: str, values: object) -> tuple[float, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ValidationError(f"{name} must be an iterable")
    frozen = tuple(_finite("setpoint", value) for value in values)
    if len(frozen) < 2:
        raise ValidationError(f"{name} requires at least two values")
    return frozen


@dataclass(frozen=True, slots=True)
class HysteresisPlan:
    """Immutable repeated directional stimulus and analysis contract."""

    plan_id: str
    plan_version: str
    stimulus_channel: str
    unit: MeasurementUnit
    rising_setpoints: tuple[float, ...]
    falling_setpoints: tuple[float, ...]
    cycles: int
    analysis_config: HysteresisAnalysisConfig
    criteria: HysteresisAcceptanceCriteria | None = None
    schema_version: str = HYSTERESIS_RUNNER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _identifier("plan_id", self.plan_id)
        _identifier("plan_version", self.plan_version)
        _identifier("stimulus_channel", self.stimulus_channel)
        if self.unit not in _VOLTAGE_UNITS:
            raise ValidationError("unit must be V or mV")
        rising = _setpoints("rising_setpoints", self.rising_setpoints)
        falling = _setpoints("falling_setpoints", self.falling_setpoints)
        if any(left > right for left, right in pairwise(rising)):
            raise ValidationError(
                "rising_setpoints must be monotonically nondecreasing"
            )
        if any(left < right for left, right in pairwise(falling)):
            raise ValidationError(
                "falling_setpoints must be monotonically nonincreasing"
            )
        object.__setattr__(self, "rising_setpoints", rising)
        object.__setattr__(self, "falling_setpoints", falling)
        if (
            isinstance(self.cycles, bool)
            or not isinstance(self.cycles, int)
            or self.cycles < 1
        ):
            raise ValidationError("cycles must be a positive integer")
        if not isinstance(self.analysis_config, HysteresisAnalysisConfig):
            raise ValidationError("analysis_config must be a HysteresisAnalysisConfig")
        if self.stimulus_channel in {
            self.analysis_config.input_channel,
            self.analysis_config.state_channel,
        }:
            raise ValidationError(
                "stimulus, input, and state channels must be distinct"
            )
        if self.analysis_config.normalized_unit is not self.unit:
            raise ValidationError("plan unit must match analysis normalized unit")
        if self.criteria is not None:
            if not isinstance(self.criteria, HysteresisAcceptanceCriteria):
                raise ValidationError(
                    "criteria must be HysteresisAcceptanceCriteria or None"
                )
            if self.criteria.normalized_unit is not self.unit:
                raise ValidationError("plan unit must match criteria normalized unit")
        if self.schema_version != HYSTERESIS_RUNNER_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported hysteresis runner schema: {self.schema_version}"
            )

    @property
    def points_per_cycle(self) -> int:
        return len(self.rising_setpoints) + len(self.falling_setpoints)

    @property
    def expected_steps(self) -> int:
        return self.cycles * self.points_per_cycle

    @property
    def expected_measurements(self) -> int:
        return self.expected_steps * 2


@dataclass(frozen=True, slots=True)
class HysteresisAcquisitionStep:
    """One stimulus, analog read, and digital-state read with exact IDs."""

    sequence: int
    cycle_index: int
    direction: SweepDirection
    setpoint_index: int
    setpoint: float
    input_record_id: str
    state_record_id: str
    schema_version: str = HYSTERESIS_RUNNER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _index("sequence", self.sequence)
        _index("cycle_index", self.cycle_index)
        _index("setpoint_index", self.setpoint_index)
        if not isinstance(self.direction, SweepDirection):
            raise ValidationError("direction must be a SweepDirection")
        object.__setattr__(self, "setpoint", _finite("setpoint", self.setpoint))
        _identifier("input_record_id", self.input_record_id)
        _identifier("state_record_id", self.state_record_id)
        if self.input_record_id == self.state_record_id:
            raise ValidationError("input and state record IDs must be distinct")
        if self.schema_version != HYSTERESIS_RUNNER_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported hysteresis runner schema: {self.schema_version}"
            )


def _planned_steps(
    plan: HysteresisPlan,
) -> tuple[tuple[int, SweepDirection, int, float], ...]:
    return tuple(
        (cycle, direction, index, setpoint)
        for cycle in range(plan.cycles)
        for direction, setpoints in (
            (SweepDirection.RISING, plan.rising_setpoints),
            (SweepDirection.FALLING, plan.falling_setpoints),
        )
        for index, setpoint in enumerate(setpoints)
    )


@dataclass(frozen=True, slots=True)
class HysteresisRunnerResult:
    """One runner attempt that cannot promote partial acquisition to PASS."""

    plan: HysteresisPlan
    capabilities: DeviceCapabilities | None
    measurements: tuple[Measurement, ...]
    completed_steps: tuple[HysteresisAcquisitionStep, ...]
    analysis: HysteresisAnalysisResult | None
    evaluation: HysteresisEvaluationResult | None
    test_run_result: TestRunResult
    schema_version: str = HYSTERESIS_RUNNER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.plan, HysteresisPlan):
            raise ValidationError("plan must be a HysteresisPlan")
        if self.capabilities is not None and not isinstance(
            self.capabilities, DeviceCapabilities
        ):
            raise ValidationError("capabilities must be DeviceCapabilities or None")
        measurements = tuple(self.measurements)
        steps = tuple(self.completed_steps)
        if not all(isinstance(value, Measurement) for value in measurements):
            raise ValidationError("measurements must contain Measurement values")
        if not all(isinstance(value, HysteresisAcquisitionStep) for value in steps):
            raise ValidationError("completed_steps must contain acquisition steps")
        object.__setattr__(self, "measurements", measurements)
        object.__setattr__(self, "completed_steps", steps)
        if self.analysis is not None and not isinstance(
            self.analysis, HysteresisAnalysisResult
        ):
            raise ValidationError("analysis must be HysteresisAnalysisResult or None")
        if self.evaluation is not None and not isinstance(
            self.evaluation, HysteresisEvaluationResult
        ):
            raise ValidationError(
                "evaluation must be HysteresisEvaluationResult or None"
            )
        if not isinstance(self.test_run_result, TestRunResult):
            raise ValidationError("test_run_result must be a TestRunResult")
        ids = tuple(value.record_id for value in measurements)
        if len(ids) != len(set(ids)):
            raise ValidationError("runner measurement record IDs must be unique")
        if self.test_run_result.evidence_record_ids != ids:
            raise ValidationError("TestRun evidence IDs must match runner measurements")
        if any(
            value.source is not self.test_run_result.metadata.evidence_source
            for value in measurements
        ):
            raise ValidationError("runner measurement sources must match metadata")
        raw_ids = tuple(dict.fromkeys(value.raw_record_id for value in measurements))
        if self.test_run_result.metadata.input_record_ids != raw_ids:
            raise ValidationError("TestRun raw IDs must match runner measurements")
        if len(measurements) not in {len(steps) * 2, len(steps) * 2 + 1}:
            raise ValidationError(
                "measurements must contain pairs plus at most one analog read"
            )
        expected = _planned_steps(self.plan)
        if len(steps) > len(expected):
            raise ValidationError("completed_steps exceed the hysteresis plan")
        for sequence, step in enumerate(steps):
            if (
                step.sequence,
                step.cycle_index,
                step.direction,
                step.setpoint_index,
                step.setpoint,
            ) != (sequence, *expected[sequence]):
                raise ValidationError("completed steps must follow the plan order")
            analog, state = measurements[sequence * 2 : sequence * 2 + 2]
            if (
                analog.channel != self.plan.analysis_config.input_channel
                or analog.unit is not self.plan.unit
            ):
                raise ValidationError("analog measurement does not match the plan")
            if (
                state.channel != self.plan.analysis_config.state_channel
                or state.unit is not MeasurementUnit.BOOLEAN
            ):
                raise ValidationError("digital measurement does not match the plan")
            if (step.input_record_id, step.state_record_id) != (
                analog.record_id,
                state.record_id,
            ):
                raise ValidationError("step record IDs must match runner measurements")
        if len(measurements) % 2:
            analog = measurements[-1]
            if (
                analog.channel != self.plan.analysis_config.input_channel
                or analog.unit is not self.plan.unit
            ):
                raise ValidationError(
                    "partial analog measurement does not match the plan"
                )
        outcome = self.test_run_result.outcome
        if self.capabilities is not None and outcome is not TestRunOutcome.ERROR:
            metadata = self.test_run_result.metadata
            if metadata.device_id != self.capabilities.device_id:
                raise ValidationError("TestRun device ID must match capabilities")
            if (metadata.profile_name, metadata.profile_version) != (
                self.capabilities.profile_name,
                self.capabilities.profile_version,
            ):
                raise ValidationError("TestRun profile must match capabilities")
        if self.evaluation is None:
            if self.analysis is not None:
                raise ValidationError("analysis without evaluation is not allowed")
            if outcome in {TestRunOutcome.PASS, TestRunOutcome.FAIL}:
                raise ValidationError("PASS/FAIL runner results require evaluation")
        else:
            if self.analysis is None or self.evaluation.analysis != self.analysis:
                raise ValidationError("evaluation must reference runner analysis")
            if (
                self.evaluation.criteria != self.plan.criteria
                or self.evaluation.test_run_result != self.test_run_result
            ):
                raise ValidationError("evaluation must match plan criteria and TestRun")
        if self.schema_version != HYSTERESIS_RUNNER_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported hysteresis runner schema: {self.schema_version}"
            )

    @property
    def outcome(self) -> TestRunOutcome:
        return self.test_run_result.outcome


def _append_once(values: list[str], item: str) -> None:
    if item not in values:
        values.append(item)


def _static_preflight(
    adapter: DeviceAdapter,
    plan: HysteresisPlan,
    config: ValidationConfig,
    metadata: TestRunMetadata,
) -> DeviceCommand:
    if adapter.state is not AdapterState.DISCONNECTED:
        raise AdapterStateError("hysteresis runner requires a disconnected adapter")
    if not config.allow_output:
        raise ValidationError("hysteresis runner requires allow_output=true")
    if (
        config.evidence_source is not adapter.evidence_source
        or metadata.evidence_source is not adapter.evidence_source
    ):
        raise ValidationError("configuration and metadata source must match adapter")
    if metadata.test_type != HYSTERESIS_TEST_TYPE:
        raise ValidationError(f"metadata test_type must be {HYSTERESIS_TEST_TYPE}")
    if metadata.input_record_ids:
        raise ValidationError("runner metadata template input_record_ids must be empty")
    if (metadata.configuration_id, metadata.configuration_version) != (
        config.config_id,
        config.config_version,
    ):
        raise ValidationError("metadata configuration must match ValidationConfig")
    if (metadata.profile_name, metadata.profile_version) != (
        config.profile.name,
        config.profile.version,
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
    analog = config.get_channel(plan.analysis_config.input_channel)
    if (
        not analog.enabled
        or analog.role is not ChannelRole.ANALOG_INPUT
        or analog.unit is not plan.unit
    ):
        raise ValidationError(
            "analysis input must be an enabled same-unit analog input"
        )
    state = config.get_channel(plan.analysis_config.state_channel)
    if (
        not state.enabled
        or state.role is not ChannelRole.DIGITAL_INPUT
        or state.unit is not MeasurementUnit.BOOLEAN
    ):
        raise ValidationError("state channel must be an enabled boolean digital input")
    for setpoint in plan.rising_setpoints + plan.falling_setpoints:
        config.require_output(plan.stimulus_channel, setpoint, plan.unit)
    return output_command


def _missing_capabilities(
    plan: HysteresisPlan,
    capabilities: DeviceCapabilities,
    output_command: DeviceCommand,
) -> tuple[str, ...]:
    missing: list[str] = []
    if not capabilities.supports(DeviceCommand.READ_MEASUREMENT):
        _append_once(missing, f"command:{DeviceCommand.READ_MEASUREMENT.value}")
    if not capabilities.supports(DeviceCommand.READ_DIGITAL_STATE):
        _append_once(missing, f"command:{DeviceCommand.READ_DIGITAL_STATE.value}")
    analog = plan.analysis_config.input_channel
    if analog not in capabilities.adc_channels:
        _append_once(missing, f"analog-channel:{analog}")
    elif capabilities.get_input_range(analog).unit is not plan.unit:
        _append_once(missing, f"analog-unit:{analog}:{plan.unit.value}")
    state = plan.analysis_config.state_channel
    if state not in capabilities.digital_input_channels:
        _append_once(missing, f"digital-channel:{state}")
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
        _append_once(missing, f"output-unit:{plan.stimulus_channel}:{plan.unit.value}")
    if not capabilities.supports_safe_shutdown:
        _append_once(missing, f"command:{DeviceCommand.SAFE_SHUTDOWN.value}")
    return tuple(missing)


def _metadata(
    template: TestRunMetadata, measurements: tuple[Measurement, ...]
) -> TestRunMetadata:
    return replace(
        template,
        input_record_ids=tuple(
            dict.fromkeys(value.raw_record_id for value in measurements)
        ),
    )


def _attempt(
    plan: HysteresisPlan,
    capabilities: DeviceCapabilities | None,
    template: TestRunMetadata,
    measurements: tuple[Measurement, ...],
    steps: tuple[HysteresisAcquisitionStep, ...],
    outcome: TestRunOutcome,
    summary: str,
    missing: tuple[str, ...],
) -> HysteresisRunnerResult:
    test_run = TestRunResult(
        _metadata(template, measurements),
        outcome,
        summary,
        tuple(value.record_id for value in measurements),
        missing,
    )
    return HysteresisRunnerResult(
        plan, capabilities, measurements, steps, None, None, test_run
    )


def _gap(prefix: str, error: BaseException) -> str:
    return f"{prefix}:{type(error).__name__}"


def _never_abort() -> bool:
    return False


def _cycle_inputs(
    plan: HysteresisPlan, measurements: tuple[Measurement, ...]
) -> tuple[HysteresisCycleInput, ...]:
    offset = 0
    cycles: list[HysteresisCycleInput] = []
    for cycle_index in range(plan.cycles):
        rising_count = len(plan.rising_setpoints) * 2
        falling_count = len(plan.falling_setpoints) * 2
        rising = MeasurementBatch(measurements[offset : offset + rising_count])
        offset += rising_count
        falling = MeasurementBatch(measurements[offset : offset + falling_count])
        offset += falling_count
        cycles.append(HysteresisCycleInput(cycle_index, rising, falling))
    return tuple(cycles)


def run_hysteresis(
    adapter: DeviceAdapter,
    plan: HysteresisPlan,
    config: ValidationConfig,
    metadata: TestRunMetadata,
    *,
    settle: Callable[[float], None] = time.sleep,
    abort_requested: Callable[[], bool] = _never_abort,
) -> HysteresisRunnerResult:
    """Execute all directional points and clean up before any PASS/FAIL."""

    if not isinstance(adapter, DeviceAdapter):
        raise ValidationError("adapter must be a DeviceAdapter")
    if not isinstance(plan, HysteresisPlan):
        raise ValidationError("plan must be a HysteresisPlan")
    if not isinstance(config, ValidationConfig):
        raise ValidationError("config must be a ValidationConfig")
    if not isinstance(metadata, TestRunMetadata):
        raise ValidationError("metadata must be a TestRunMetadata")
    if not callable(settle) or not callable(abort_requested):
        raise ValidationError("settle and abort_requested must be callable")
    output_command = _static_preflight(adapter, plan, config, metadata)
    capabilities: DeviceCapabilities | None = None
    measurements: list[Measurement] = []
    steps: list[HysteresisAcquisitionStep] = []
    pending: tuple[TestRunOutcome, str, tuple[str, ...]] | None = None
    cleanup_error: BaseException | None = None
    try:
        adapter.connect()
        capabilities = adapter.get_capabilities()
        if metadata.device_id != capabilities.device_id:
            raise ValidationError("metadata device_id must match capabilities")
        missing = _missing_capabilities(plan, capabilities, output_command)
        if missing:
            pending = (
                TestRunOutcome.UNSUPPORTED,
                "Hysteresis runner unsupported",
                missing,
            )
        else:
            validate_config_capabilities(config, capabilities)
            adapter.arm(config)
            for cycle_index, direction, setpoint_index, setpoint in _planned_steps(
                plan
            ):
                if abort_requested():
                    pending = (
                        TestRunOutcome.INCOMPLETE,
                        "Hysteresis runner aborted",
                        (
                            "runner-aborted",
                            f"measurements:{len(measurements)}/{plan.expected_measurements}",
                        ),
                    )
                    break
                adapter.set_stimulus(plan.stimulus_channel, setpoint, plan.unit)
                settle(config.timeouts.settle_s)
                if abort_requested():
                    pending = (
                        TestRunOutcome.INCOMPLETE,
                        "Hysteresis runner aborted",
                        (
                            "runner-aborted",
                            f"measurements:{len(measurements)}/{plan.expected_measurements}",
                        ),
                    )
                    break
                analog = adapter.read_measurement(plan.analysis_config.input_channel)
                if any(value.record_id == analog.record_id for value in measurements):
                    raise AdapterDataError(
                        "adapter returned a duplicate measurement record ID"
                    )
                measurements.append(analog)
                state = adapter.read_digital_state(plan.analysis_config.state_channel)
                if any(value.record_id == state.record_id for value in measurements):
                    raise AdapterDataError(
                        "adapter returned a duplicate measurement record ID"
                    )
                measurements.append(state)
                steps.append(
                    HysteresisAcquisitionStep(
                        len(steps),
                        cycle_index,
                        direction,
                        setpoint_index,
                        setpoint,
                        analog.record_id,
                        state.record_id,
                    )
                )
    except ReplayEndOfData:
        pending = (
            TestRunOutcome.INCOMPLETE,
            "Hysteresis acquisition incomplete",
            (
                "acquisition-end-of-data",
                f"measurements:{len(measurements)}/{plan.expected_measurements}",
            ),
        )
    except KeyboardInterrupt:
        pending = (
            TestRunOutcome.INCOMPLETE,
            "Hysteresis runner interrupted",
            (
                "runner-interrupted",
                f"measurements:{len(measurements)}/{plan.expected_measurements}",
            ),
        )
    except Exception as error:  # noqa: BLE001 - callback and adapter boundary
        pending = (
            TestRunOutcome.ERROR,
            "Hysteresis runner error",
            (_gap("execution-error", error),),
        )
    finally:
        if adapter.is_connected:
            try:
                adapter.disconnect()
            except AnalogValidationError as error:
                cleanup_error = error
    measurements_tuple = tuple(measurements)
    steps_tuple = tuple(steps)
    if cleanup_error is not None:
        return _attempt(
            plan,
            capabilities,
            metadata,
            measurements_tuple,
            steps_tuple,
            TestRunOutcome.ERROR,
            "Hysteresis runner cleanup error",
            (_gap("cleanup-error", cleanup_error),),
        )
    if pending is not None:
        return _attempt(
            plan, capabilities, metadata, measurements_tuple, steps_tuple, *pending
        )
    final_metadata = _metadata(metadata, measurements_tuple)
    try:
        analysis = analyze_hysteresis(
            _cycle_inputs(plan, measurements_tuple), plan.analysis_config
        )
        evaluation = evaluate_hysteresis(analysis, plan.criteria, final_metadata)
    except AnalogValidationError as error:
        return _attempt(
            plan,
            capabilities,
            metadata,
            measurements_tuple,
            steps_tuple,
            TestRunOutcome.ERROR,
            "Hysteresis analysis error",
            (_gap("analysis-error", error),),
        )
    return HysteresisRunnerResult(
        plan,
        capabilities,
        measurements_tuple,
        steps_tuple,
        analysis,
        evaluation,
        evaluation.test_run_result,
    )


__all__ = [
    "HYSTERESIS_RUNNER_SCHEMA_VERSION",
    "HysteresisAcquisitionStep",
    "HysteresisPlan",
    "HysteresisRunnerResult",
    "run_hysteresis",
]
