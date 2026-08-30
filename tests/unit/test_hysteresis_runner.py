"""Tests for the safety-gated directional hysteresis runner."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from analog_validation.adapters import DeviceAdapter
from analog_validation.analysis import (
    HysteresisAcceptanceCriteria,
    HysteresisAnalysisConfig,
    SweepDirection,
)
from analog_validation.config import (
    ChannelConfig,
    ChannelRole,
    ProfileConfig,
    TimeoutConfig,
    ValidationConfig,
)
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
from analog_validation.domain import TestRunMetadata as RunMetadata
from analog_validation.domain import TestRunOutcome as RunOutcome
from analog_validation.domain import TestRunResult as RunResult
from analog_validation.errors import (
    AdapterError,
    AdapterStateError,
    ConfigurationError,
    ReplayEndOfData,
    ValidationError,
)
from analog_validation.runners import (
    HYSTERESIS_RUNNER_SCHEMA_VERSION,
    HysteresisAcquisitionStep,
    HysteresisPlan,
    HysteresisRunnerResult,
    run_hysteresis,
)

NOW = datetime(2026, 8, 30, 21, 0, tzinfo=timezone.utc)
STIMULUS = "afe.stimulus"
INPUT = "afe.input"
STATE = "afe.state"


def capabilities(
    *,
    output: bool = True,
    digital: bool = True,
    read: bool = True,
    safe_shutdown: bool = True,
    unit: MeasurementUnit = MeasurementUnit.MILLIVOLT,
) -> DeviceCapabilities:
    commands: set[DeviceCommand] = set()
    if read:
        commands.add(DeviceCommand.READ_MEASUREMENT)
    if digital:
        commands.add(DeviceCommand.READ_DIGITAL_STATE)
    dac_channels: tuple[str, ...] = ()
    outputs: tuple[ChannelRange, ...] = ()
    if output:
        commands.add(DeviceCommand.SET_ANALOG_STIMULUS)
        dac_channels = (STIMULUS,)
        outputs = (ChannelRange(STIMULUS, SafeRange(1000, 2000, unit)),)
    if safe_shutdown:
        commands.add(DeviceCommand.SAFE_SHUTDOWN)
    return DeviceCapabilities(
        device_id="hysteresis-fixture",
        profile_name="reference-output",
        profile_version="1",
        adc_channels=(INPUT,),
        dac_channels=dac_channels,
        digital_input_channels=(STATE,) if digital else (),
        safe_input_ranges=(ChannelRange(INPUT, SafeRange(1000, 2000, unit)),),
        safe_output_ranges=outputs,
        supported_commands=frozenset(commands),
        supports_safe_shutdown=safe_shutdown,
    )


def validation_config(
    *, allow_output: bool = True, maximum: float = 2000
) -> ValidationConfig:
    return ValidationConfig(
        "hysteresis-config",
        "1",
        ProfileConfig("reference-output", "1"),
        EvidenceSource.HOST_TEST,
        (
            ChannelConfig(INPUT, ChannelRole.ANALOG_INPUT, MeasurementUnit.MILLIVOLT),
            ChannelConfig(STATE, ChannelRole.DIGITAL_INPUT, MeasurementUnit.BOOLEAN),
            ChannelConfig(
                STIMULUS,
                ChannelRole.ANALOG_OUTPUT,
                MeasurementUnit.MILLIVOLT,
                safe_output_range=SafeRange(1000, maximum, MeasurementUnit.MILLIVOLT),
            ),
        ),
        TimeoutConfig(settle_s=0.1),
        allow_output,
    )


def acceptance() -> HysteresisAcceptanceCriteria:
    return HysteresisAcceptanceCriteria(
        "hysteresis-nominal", "1", 1750, 1850, 1450, 1550, 250, 350, 10, 1
    )


def plan(
    *, cycles: int = 1, selected_criteria: HysteresisAcceptanceCriteria | None = None
) -> HysteresisPlan:
    return HysteresisPlan(
        "hysteresis-plan",
        "1",
        STIMULUS,
        MeasurementUnit.MILLIVOLT,
        (1400, 1700, 1900),
        (1900, 1600, 1400),
        cycles,
        HysteresisAnalysisConfig(INPUT, STATE),
        acceptance() if selected_criteria is None else selected_criteria,
    )


def metadata() -> RunMetadata:
    return RunMetadata(
        "hysteresis-run-1",
        "hysteresis",
        "hysteresis-config",
        "1",
        NOW,
        NOW + timedelta(seconds=2),
        "0.1.0.dev0",
        "hysteresis-fixture",
        "reference-output",
        "1",
        EvidenceSource.HOST_TEST,
    )


class ReferenceHysteresisAdapter(DeviceAdapter):
    """Host-only fixture; thresholds are software behavior, not hardware proof."""

    def __init__(
        self,
        declared_capabilities: DeviceCapabilities | None = None,
        *,
        high: float = 1800,
        low: float = 1500,
    ) -> None:
        super().__init__(EvidenceSource.HOST_TEST)
        self.declared_capabilities = declared_capabilities or capabilities()
        self.high = high
        self.low = low
        self.current = 0.0
        self.digital_state = 0
        self.counter = 0
        self.calls: list[object] = []
        self.read_error_at: int | None = None
        self.end_at: int | None = None
        self.shutdown_error: Exception | None = None
        self.duplicate_at: int | None = None
        self.state_script: list[int] | None = None

    def _connect(self) -> None:
        self.calls.append("connect")

    def _disconnect(self) -> None:
        self.calls.append("disconnect")

    def _get_capabilities(self) -> DeviceCapabilities:
        self.calls.append("capabilities")
        return self.declared_capabilities

    def _set_stimulus(self, channel: str, value: float, unit: MeasurementUnit) -> None:
        self.calls.append(("set", value))
        self.current = value
        if value >= self.high:
            self.digital_state = 1
        elif value <= self.low:
            self.digital_state = 0

    def _next_measurement(
        self, channel: str, value: float, unit: MeasurementUnit
    ) -> Measurement:
        if self.end_at == self.counter:
            raise ReplayEndOfData("injected end")
        if self.read_error_at == self.counter:
            raise AdapterError("injected read failure")
        sequence = self.counter
        self.counter += 1
        record_sequence = 0 if self.duplicate_at == sequence else sequence
        return Measurement(
            f"record-{record_sequence}",
            f"raw-{record_sequence}",
            NOW + timedelta(milliseconds=sequence),
            channel,
            value,
            unit,
            MeasurementStatus.VALID,
            EvidenceSource.HOST_TEST,
        )

    def _read_measurement(self, channel: str) -> Measurement:
        self.calls.append(("read", channel))
        return self._next_measurement(channel, self.current, MeasurementUnit.MILLIVOLT)

    def _read_digital_state(self, channel: str) -> Measurement:
        self.calls.append(("digital", channel))
        value = self.digital_state
        if self.state_script is not None:
            value = self.state_script[(self.counter - 1) // 2]
        return self._next_measurement(channel, value, MeasurementUnit.BOOLEAN)

    def _safe_shutdown(self) -> None:
        self.calls.append("safe_shutdown")
        if self.shutdown_error is not None:
            raise self.shutdown_error


def run_reference(
    adapter: ReferenceHysteresisAdapter | None = None,
    *,
    selected_plan: HysteresisPlan | None = None,
    selected_config: ValidationConfig | None = None,
    selected_metadata: RunMetadata | None = None,
    settle: Any = lambda _seconds: None,
    abort_requested: Any = lambda: False,
) -> HysteresisRunnerResult:
    return run_hysteresis(
        adapter or ReferenceHysteresisAdapter(),
        selected_plan or plan(),
        selected_config or validation_config(),
        selected_metadata or metadata(),
        settle=settle,
        abort_requested=abort_requested,
    )


def test_happy_path_runs_repeated_directional_cycles_and_cleans_up() -> None:
    adapter = ReferenceHysteresisAdapter()
    result = run_reference(adapter, selected_plan=plan(cycles=2))
    assert result.schema_version == HYSTERESIS_RUNNER_SCHEMA_VERSION
    assert result.outcome is RunOutcome.PASS
    assert result.analysis is not None and result.analysis.summary is not None
    assert result.analysis.summary.cycle_count == 2
    assert result.analysis.summary.mean_high_threshold == 1800
    assert result.analysis.summary.mean_low_threshold == 1500
    assert result.analysis.summary.mean_width == 300
    assert len(result.completed_steps) == result.plan.expected_steps == 12
    assert len(result.measurements) == result.plan.expected_measurements == 24
    assert result.completed_steps[0].direction is SweepDirection.RISING
    assert result.completed_steps[3].direction is SweepDirection.FALLING
    assert adapter.calls[-2:] == ["safe_shutdown", "disconnect"]


@pytest.mark.parametrize(
    "declared",
    [
        capabilities(output=False),
        capabilities(digital=False),
        capabilities(read=False),
        capabilities(safe_shutdown=False),
    ],
)
def test_missing_capability_is_unsupported_with_zero_output(
    declared: DeviceCapabilities,
) -> None:
    adapter = ReferenceHysteresisAdapter(declared)
    result = run_reference(adapter)
    assert result.outcome is RunOutcome.UNSUPPORTED
    assert result.measurements == ()
    assert not any(
        isinstance(value, tuple) and value[0] == "set" for value in adapter.calls
    )
    assert adapter.calls[-1] == "disconnect"


def test_abort_before_and_after_settle_preserves_only_real_partial_evidence() -> None:
    first = run_reference(abort_requested=lambda: True)
    assert first.outcome is RunOutcome.INCOMPLETE
    assert first.measurements == ()

    calls = iter((False, True))
    second = run_reference(abort_requested=lambda: next(calls))
    assert second.outcome is RunOutcome.INCOMPLETE
    assert second.measurements == ()
    assert second.completed_steps == ()


@pytest.mark.parametrize(
    ("field", "expected"),
    [("read_error_at", RunOutcome.ERROR), ("end_at", RunOutcome.INCOMPLETE)],
)
def test_read_error_and_end_of_data_have_stable_outcomes(
    field: str, expected: RunOutcome
) -> None:
    adapter = ReferenceHysteresisAdapter()
    setattr(adapter, field, 1)
    result = run_reference(adapter)
    assert result.outcome is expected
    assert len(result.measurements) == 1
    assert result.completed_steps == ()
    assert adapter.calls[-2:] == ["safe_shutdown", "disconnect"]


def test_cleanup_failure_overrides_a_pending_pass() -> None:
    adapter = ReferenceHysteresisAdapter()
    adapter.shutdown_error = AdapterError("injected shutdown failure")
    result = run_reference(adapter)
    assert result.outcome is RunOutcome.ERROR
    assert result.analysis is None
    assert result.test_run_result.summary == "Hysteresis runner cleanup error"
    assert result.test_run_result.missing_requirements == (
        "cleanup-error:AdapterError",
    )


def test_analysis_rejects_chatter_and_inverted_thresholds_as_runner_errors() -> None:
    chatter = ReferenceHysteresisAdapter()
    chatter.state_script = [0, 1, 0, 1, 1, 0]
    result = run_reference(chatter)
    assert result.outcome is RunOutcome.ERROR
    assert result.test_run_result.missing_requirements == (
        "analysis-error:ValidationError",
    )

    inverted_adapter = ReferenceHysteresisAdapter()
    inverted_adapter.state_script = [0, 1, 1, 1, 0, 0]
    inverted = run_reference(inverted_adapter)
    assert inverted.outcome is RunOutcome.ERROR
    assert inverted.analysis is None


def test_absent_transition_and_absent_criteria_cannot_pass() -> None:
    no_transition = run_reference(ReferenceHysteresisAdapter(high=2500))
    assert no_transition.outcome is RunOutcome.INCOMPLETE
    assert no_transition.analysis is not None
    assert no_transition.evaluation is not None
    assert (
        "analysis:cycle-0:rising-transition"
        in no_transition.test_run_result.missing_requirements
    )

    no_criteria_plan = replace(plan(), criteria=None)
    no_criteria = run_reference(selected_plan=no_criteria_plan)
    assert no_criteria.outcome is RunOutcome.INCOMPLETE
    assert no_criteria.test_run_result.missing_requirements == ("acceptance-criteria",)


def test_duplicate_record_is_an_execution_error() -> None:
    adapter = ReferenceHysteresisAdapter()
    adapter.duplicate_at = 1
    result = run_reference(adapter)
    assert result.outcome is RunOutcome.ERROR
    assert result.test_run_result.missing_requirements == (
        "execution-error:AdapterDataError",
    )


def test_static_preflight_rejects_disabled_output_and_out_of_range_before_connect() -> (
    None
):
    adapter = ReferenceHysteresisAdapter()
    with pytest.raises(ValidationError, match="allow_output"):
        run_reference(adapter, selected_config=validation_config(allow_output=False))
    assert adapter.calls == []

    with pytest.raises(ConfigurationError, match="outside"):
        run_reference(adapter, selected_config=validation_config(maximum=1800))
    assert adapter.calls == []


def test_plan_direction_and_public_step_validation() -> None:
    assert plan().points_per_cycle == 6
    assert (
        HysteresisAcquisitionStep(
            0, 0, SweepDirection.RISING, 0, 1400, "a", "d"
        ).schema_version
        == HYSTERESIS_RUNNER_SCHEMA_VERSION
    )
    with pytest.raises(ValidationError, match="rising_setpoints"):
        replace(plan(), rising_setpoints=(1500, 1400))
    with pytest.raises(ValidationError, match="falling_setpoints"):
        replace(plan(), falling_setpoints=(1400, 1500))
    with pytest.raises(ValidationError, match="distinct"):
        replace(plan(), stimulus_channel=INPUT)


def test_plan_and_step_model_validation_boundaries() -> None:
    selected = plan()
    for change in (
        {"plan_id": ""},
        {"plan_version": " bad"},
        {"stimulus_channel": "bad "},
        {"unit": MeasurementUnit.AMPERE},
        {"rising_setpoints": "bad"},
        {"rising_setpoints": (1400,)},
        {"rising_setpoints": (1400, float("nan"))},
        {"cycles": 0},
        {"cycles": True},
        {"analysis_config": object()},
        {
            "analysis_config": replace(
                selected.analysis_config, normalized_unit=MeasurementUnit.VOLT
            )
        },
        {"criteria": object()},
        {"criteria": replace(acceptance(), normalized_unit=MeasurementUnit.VOLT)},
        {"schema_version": "future"},
    ):
        with pytest.raises(ValidationError):
            replace(selected, **change)

    step = HysteresisAcquisitionStep(0, 0, SweepDirection.RISING, 0, 1400, "a", "d")
    for change in (
        {"sequence": -1},
        {"cycle_index": True},
        {"setpoint_index": -1},
        {"direction": "RISING"},
        {"setpoint": "bad"},
        {"input_record_id": ""},
        {"state_record_id": " bad"},
        {"state_record_id": "a"},
        {"schema_version": "future"},
    ):
        with pytest.raises(ValidationError):
            replace(step, **change)


def _attempt_result(
    base: HysteresisRunnerResult,
    measurements: tuple[Measurement, ...],
    steps: tuple[HysteresisAcquisitionStep, ...],
    *,
    outcome: RunOutcome = RunOutcome.INCOMPLETE,
) -> RunResult:
    return RunResult(
        replace(
            base.test_run_result.metadata,
            input_record_ids=tuple(
                dict.fromkeys(value.raw_record_id for value in measurements)
            ),
        ),
        outcome,
        "manual runner result",
        tuple(value.record_id for value in measurements),
        () if outcome in {RunOutcome.PASS, RunOutcome.FAIL} else ("manual-gap",),
    )


def test_runner_result_model_rejects_inconsistent_manual_states() -> None:
    good = run_reference()
    assert good.analysis is not None and good.evaluation is not None
    for change in (
        {"plan": object()},
        {"capabilities": object()},
        {"measurements": (object(),)},
        {"completed_steps": (object(),)},
        {"analysis": object()},
        {"evaluation": object()},
        {"test_run_result": object()},
        {"schema_version": "future"},
    ):
        with pytest.raises((ValidationError, TypeError)):
            replace(good, **change)

    duplicate = list(good.measurements)
    duplicate[1] = replace(duplicate[1], record_id=duplicate[0].record_id)
    with pytest.raises(ValidationError, match="unique"):
        replace(good, measurements=tuple(duplicate))
    with pytest.raises(ValidationError, match="evidence IDs"):
        replace(
            good,
            test_run_result=replace(
                good.test_run_result, evidence_record_ids=("wrong",)
            ),
        )
    wrong_source = (
        replace(good.measurements[0], source=EvidenceSource.CSV_REPLAY),
        *good.measurements[1:],
    )
    with pytest.raises(ValidationError, match="sources"):
        replace(good, measurements=wrong_source)
    with pytest.raises(ValidationError, match="raw IDs"):
        replace(
            good,
            test_run_result=replace(
                good.test_run_result,
                metadata=replace(
                    good.test_run_result.metadata, input_record_ids=("wrong",)
                ),
            ),
        )

    short = good.measurements[:-1]
    with pytest.raises(ValidationError, match="pairs"):
        replace(
            good,
            measurements=short,
            test_run_result=_attempt_result(good, short, good.completed_steps),
        )
    extra_steps = (*good.completed_steps, replace(good.completed_steps[-1], sequence=6))
    extra_measurements = (
        *good.measurements,
        replace(
            good.measurements[-2], record_id="extra-a", raw_record_id="extra-raw-a"
        ),
        replace(
            good.measurements[-1], record_id="extra-d", raw_record_id="extra-raw-d"
        ),
    )
    with pytest.raises(ValidationError, match="exceed"):
        replace(
            good,
            measurements=extra_measurements,
            completed_steps=extra_steps,
            test_run_result=_attempt_result(good, extra_measurements, extra_steps),
        )
    with pytest.raises(ValidationError, match="plan order"):
        replace(
            good,
            completed_steps=(
                replace(good.completed_steps[0], setpoint=1401),
                *good.completed_steps[1:],
            ),
        )
    bad_analog = (
        replace(good.measurements[0], channel="wrong"),
        *good.measurements[1:],
    )
    with pytest.raises(ValidationError, match="analog measurement"):
        replace(good, measurements=bad_analog)
    bad_state = (
        *good.measurements[:1],
        replace(good.measurements[1], unit=MeasurementUnit.UNITLESS),
        *good.measurements[2:],
    )
    with pytest.raises(ValidationError, match="digital measurement"):
        replace(good, measurements=bad_state)
    with pytest.raises(ValidationError, match="record IDs"):
        replace(
            good,
            completed_steps=(
                replace(good.completed_steps[0], input_record_id="wrong"),
                *good.completed_steps[1:],
            ),
        )

    partial = (good.measurements[0],)
    partial_run = _attempt_result(good, partial, ())
    with pytest.raises(ValidationError, match="partial analog"):
        replace(
            good,
            measurements=(replace(partial[0], channel="wrong"),),
            completed_steps=(),
            analysis=None,
            evaluation=None,
            test_run_result=partial_run,
        )
    with pytest.raises(ValidationError, match="device ID"):
        replace(
            good,
            test_run_result=replace(
                good.test_run_result,
                metadata=replace(good.test_run_result.metadata, device_id="wrong"),
            ),
        )
    with pytest.raises(ValidationError, match="profile"):
        replace(
            good,
            test_run_result=replace(
                good.test_run_result,
                metadata=replace(good.test_run_result.metadata, profile_name="wrong"),
            ),
        )
    with pytest.raises(ValidationError, match="analysis without"):
        replace(good, evaluation=None)
    with pytest.raises(ValidationError, match="require evaluation"):
        replace(good, analysis=None, evaluation=None)
    with pytest.raises(ValidationError, match="reference runner analysis"):
        replace(good, analysis=None)
    different_criteria = replace(acceptance(), maximum_width=360)
    with pytest.raises(ValidationError, match="plan criteria"):
        replace(good, plan=replace(good.plan, criteria=different_criteria))


def test_static_preflight_identity_channel_and_state_boundaries() -> None:
    adapter = ReferenceHysteresisAdapter()
    adapter.connect()
    with pytest.raises(AdapterStateError):
        run_reference(adapter)
    adapter.disconnect()

    config_base = validation_config()
    metadata_base = metadata()
    cases = (
        (
            replace(config_base, evidence_source=EvidenceSource.CSV_REPLAY),
            metadata_base,
        ),
        (
            config_base,
            replace(metadata_base, evidence_source=EvidenceSource.CSV_REPLAY),
        ),
        (config_base, replace(metadata_base, test_type="wrong")),
        (config_base, replace(metadata_base, input_record_ids=("raw",))),
        (config_base, replace(metadata_base, configuration_id="wrong")),
        (config_base, replace(metadata_base, profile_name="wrong")),
    )
    for selected_config, selected_metadata in cases:
        with pytest.raises(ValidationError):
            run_reference(
                selected_config=selected_config, selected_metadata=selected_metadata
            )

    channels = list(config_base.channels)
    channels[2] = replace(channels[2], enabled=False)
    channels.append(
        ChannelConfig(
            "dummy-output",
            ChannelRole.ANALOG_OUTPUT,
            MeasurementUnit.MILLIVOLT,
            safe_output_range=SafeRange(1000, 2000, MeasurementUnit.MILLIVOLT),
        )
    )
    with pytest.raises(ValidationError, match="stimulus"):
        run_reference(selected_config=replace(config_base, channels=tuple(channels)))

    voltage_output = ChannelConfig(
        STIMULUS,
        ChannelRole.ANALOG_OUTPUT,
        MeasurementUnit.VOLT,
        safe_output_range=SafeRange(1, 2, MeasurementUnit.VOLT),
    )
    with pytest.raises(ValidationError, match="stimulus channel unit"):
        run_reference(
            selected_config=replace(
                config_base, channels=(*config_base.channels[:2], voltage_output)
            )
        )

    channels = list(config_base.channels)
    channels[0] = replace(channels[0], enabled=False)
    with pytest.raises(ValidationError, match="analysis input"):
        run_reference(selected_config=replace(config_base, channels=tuple(channels)))
    channels = list(config_base.channels)
    channels[1] = replace(channels[1], enabled=False)
    with pytest.raises(ValidationError, match="state channel"):
        run_reference(selected_config=replace(config_base, channels=tuple(channels)))


def test_capability_unit_and_channel_gaps_are_reported_before_output() -> None:
    variants = (
        DeviceCapabilities(
            "hysteresis-fixture",
            "reference-output",
            "1",
            digital_input_channels=(STATE,),
            supported_commands=frozenset({DeviceCommand.READ_DIGITAL_STATE}),
        ),
        capabilities(unit=MeasurementUnit.VOLT),
    )
    for declared in variants:
        adapter = ReferenceHysteresisAdapter(declared)
        result = run_reference(adapter)
        assert result.outcome is RunOutcome.UNSUPPORTED
        assert not any(
            isinstance(value, tuple) and value[0] == "set" for value in adapter.calls
        )


def test_runner_call_boundary_and_interrupt_paths() -> None:
    for adapter, selected_plan, selected_config, selected_metadata in (
        (object(), plan(), validation_config(), metadata()),
        (ReferenceHysteresisAdapter(), object(), validation_config(), metadata()),
        (ReferenceHysteresisAdapter(), plan(), object(), metadata()),
        (ReferenceHysteresisAdapter(), plan(), validation_config(), object()),
    ):
        with pytest.raises(ValidationError):
            run_hysteresis(adapter, selected_plan, selected_config, selected_metadata)  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="callable"):
        run_hysteresis(
            ReferenceHysteresisAdapter(),
            plan(),
            validation_config(),
            metadata(),
            settle=None,  # type: ignore[arg-type]
        )

    default_abort = run_hysteresis(
        ReferenceHysteresisAdapter(),
        plan(),
        validation_config(),
        metadata(),
        settle=lambda _seconds: None,
    )
    assert default_abort.outcome is RunOutcome.PASS
    device_mismatch = run_reference(
        selected_metadata=replace(metadata(), device_id="wrong-device")
    )
    assert device_mismatch.outcome is RunOutcome.ERROR
    assert device_mismatch.test_run_result.missing_requirements == (
        "execution-error:ValidationError",
    )

    interrupted = run_reference(
        settle=lambda _seconds: (_ for _ in ()).throw(KeyboardInterrupt())
    )
    assert interrupted.outcome is RunOutcome.INCOMPLETE
    assert interrupted.test_run_result.missing_requirements[0] == "runner-interrupted"
    callback_error = run_reference(
        settle=lambda _seconds: (_ for _ in ()).throw(ValueError("bad callback"))
    )
    assert callback_error.outcome is RunOutcome.ERROR

    duplicate_analog = ReferenceHysteresisAdapter()
    duplicate_analog.duplicate_at = 2
    assert run_reference(duplicate_analog).outcome is RunOutcome.ERROR
