"""Tests for the controller-neutral, safety-gated DC sweep runner."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest

import analog_validation.runners.dc_sweep as runner_module
from analog_validation.adapters import AdapterState, DeviceAdapter
from analog_validation.analysis import (
    DCSweepAcceptanceCriteria,
    DCSweepAnalysisConfig,
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
from analog_validation.domain import (
    TestRunMetadata as RunMetadata,
)
from analog_validation.domain import (
    TestRunOutcome as RunOutcome,
)
from analog_validation.errors import (
    AdapterDataError,
    AdapterError,
    AdapterStateError,
    ReplayEndOfData,
    ValidationError,
)
from analog_validation.runners import (
    DC_SWEEP_RUNNER_SCHEMA_VERSION,
    DCSweepAcquisitionStep,
    DCSweepPlan,
    DCSweepRunnerResult,
    run_dc_sweep,
)

NOW = datetime(2026, 8, 30, 20, 0, tzinfo=timezone.utc)
STIMULUS = "afe.stimulus"
INPUT = "afe.input"
OUTPUT = "afe.output"


def capabilities(
    *,
    output: bool = True,
    safe_shutdown: bool = True,
    read: bool = True,
    unit: MeasurementUnit = MeasurementUnit.MILLIVOLT,
    device_id: str = "reference-output-1",
    profile_name: str = "reference-output",
) -> DeviceCapabilities:
    commands: set[DeviceCommand] = set()
    if read:
        commands.add(DeviceCommand.READ_MEASUREMENT)
    dac_channels: tuple[str, ...] = ()
    output_ranges: tuple[ChannelRange, ...] = ()
    if output:
        commands.add(DeviceCommand.SET_ANALOG_STIMULUS)
        dac_channels = (STIMULUS,)
        output_ranges = (
            ChannelRange(STIMULUS, SafeRange(0.0, 1200.0, unit)),
        )
    if safe_shutdown:
        commands.add(DeviceCommand.SAFE_SHUTDOWN)
    return DeviceCapabilities(
        device_id=device_id,
        profile_name=profile_name,
        profile_version="1",
        adc_channels=(INPUT, OUTPUT),
        dac_channels=dac_channels,
        safe_input_ranges=(
            ChannelRange(INPUT, SafeRange(0.0, 1200.0, unit)),
            ChannelRange(OUTPUT, SafeRange(0.0, 3300.0, unit)),
        ),
        safe_output_ranges=output_ranges,
        supported_commands=frozenset(commands),
        supports_safe_shutdown=safe_shutdown,
    )


def config(
    *,
    allow_output: bool = True,
    source: EvidenceSource = EvidenceSource.HOST_TEST,
    profile_name: str = "reference-output",
    unit: MeasurementUnit = MeasurementUnit.MILLIVOLT,
    maximum: float = 1000.0,
) -> ValidationConfig:
    return ValidationConfig(
        config_id="dc-run-config",
        config_version="1.0",
        profile=ProfileConfig(profile_name, "1"),
        evidence_source=source,
        channels=(
            ChannelConfig(INPUT, ChannelRole.ANALOG_INPUT, unit),
            ChannelConfig(OUTPUT, ChannelRole.ANALOG_INPUT, unit),
            ChannelConfig(
                STIMULUS,
                ChannelRole.ANALOG_OUTPUT,
                unit,
                safe_output_range=SafeRange(0.0, maximum, unit),
            ),
        ),
        timeouts=TimeoutConfig(settle_s=0.25),
        allow_output=allow_output,
    )


def analysis_config(
    *, unit: MeasurementUnit = MeasurementUnit.MILLIVOLT
) -> DCSweepAnalysisConfig:
    return DCSweepAnalysisConfig(
        input_channel=INPUT,
        output_channel=OUTPUT,
        low_output_limit=0.0,
        high_output_limit=3300.0,
        normalized_unit=unit,
    )


def criteria(
    *,
    target_gain: float = 2.0,
    unit: MeasurementUnit = MeasurementUnit.MILLIVOLT,
) -> DCSweepAcceptanceCriteria:
    return DCSweepAcceptanceCriteria(
        criteria_id="dc-nominal",
        criteria_version="1.0",
        target_gain=target_gain,
        gain_absolute_tolerance=0.01,
        max_abs_offset=20.0,
        min_r_squared=0.999,
        max_rmse=0.001,
        minimum_included_points=3,
        normalized_unit=unit,
    )


def plan(
    *,
    setpoints: tuple[float, ...] = (100.0, 200.0, 300.0),
    repetitions: int = 1,
    acceptance: DCSweepAcceptanceCriteria | None = None,
    unit: MeasurementUnit = MeasurementUnit.MILLIVOLT,
) -> DCSweepPlan:
    return DCSweepPlan(
        plan_id="dc-plan",
        plan_version="1.0",
        stimulus_channel=STIMULUS,
        unit=unit,
        setpoints=setpoints,
        repetitions=repetitions,
        analysis_config=analysis_config(unit=unit),
        criteria=criteria(unit=unit) if acceptance is None else acceptance,
    )


def metadata(
    *,
    source: EvidenceSource = EvidenceSource.HOST_TEST,
    device_id: str = "reference-output-1",
    profile_name: str = "reference-output",
) -> RunMetadata:
    return RunMetadata(
        run_id="dc-run-001",
        test_type="dc-sweep",
        configuration_id="dc-run-config",
        configuration_version="1.0",
        started_at=NOW,
        ended_at=NOW + timedelta(seconds=2),
        software_version="0.1.0.dev0",
        device_id=device_id,
        profile_name=profile_name,
        profile_version="1",
        evidence_source=source,
    )


class ReferenceOutputAdapter(DeviceAdapter):
    """Host-only adapter that records calls and derives exact synthetic values."""

    def __init__(
        self,
        declared_capabilities: DeviceCapabilities | None = None,
    ) -> None:
        super().__init__(EvidenceSource.HOST_TEST)
        self.declared_capabilities = declared_capabilities or capabilities()
        self.calls: list[object] = []
        self.current_setpoint = 0.0
        self.read_count = 0
        self.connect_error: Exception | None = None
        self.capability_error: Exception | None = None
        self.read_error_at: int | None = None
        self.read_error: Exception = AdapterError("injected read failure")
        self.shutdown_error: Exception | None = None
        self.disconnect_error: Exception | None = None
        self.duplicate_record_at: int | None = None

    def _connect(self) -> None:
        self.calls.append("connect")
        if self.connect_error is not None:
            raise self.connect_error

    def _disconnect(self) -> None:
        self.calls.append("disconnect")
        if self.disconnect_error is not None:
            raise self.disconnect_error

    def _get_capabilities(self) -> DeviceCapabilities:
        self.calls.append("capabilities")
        if self.capability_error is not None:
            raise self.capability_error
        return self.declared_capabilities

    def _set_stimulus(
        self,
        channel: str,
        value: float,
        unit: MeasurementUnit,
    ) -> None:
        self.calls.append(("set", channel, value, unit))
        self.current_setpoint = value

    def _read_measurement(self, channel: str) -> Measurement:
        self.calls.append(("read", channel))
        if self.read_error_at == self.read_count:
            raise self.read_error
        sequence = self.read_count
        self.read_count += 1
        record_sequence = (
            0 if self.duplicate_record_at == sequence else sequence
        )
        value = (
            self.current_setpoint
            if channel == INPUT
            else 2.0 * self.current_setpoint + 12.0
        )
        return Measurement(
            record_id=f"record-{record_sequence}",
            raw_record_id=f"raw-{record_sequence}",
            timestamp=NOW + timedelta(milliseconds=sequence),
            channel=channel,
            value=value,
            unit=MeasurementUnit.MILLIVOLT,
            status=MeasurementStatus.VALID,
            source=EvidenceSource.HOST_TEST,
        )

    def _safe_shutdown(self) -> None:
        self.calls.append("safe_shutdown")
        if self.shutdown_error is not None:
            raise self.shutdown_error


def run_reference(
    adapter: ReferenceOutputAdapter | None = None,
    *,
    selected_plan: DCSweepPlan | None = None,
    selected_config: ValidationConfig | None = None,
    selected_metadata: RunMetadata | None = None,
    settle: Any = lambda _seconds: None,
    abort_requested: Any = lambda: False,
) -> DCSweepRunnerResult:
    return run_dc_sweep(
        adapter or ReferenceOutputAdapter(),
        selected_plan or plan(),
        selected_config or config(),
        selected_metadata or metadata(),
        settle=settle,
        abort_requested=abort_requested,
    )


def test_public_runner_schema_exports_and_models_are_frozen() -> None:
    from analog_validation import runners

    selected_plan = plan(repetitions=2)
    step = DCSweepAcquisitionStep(0, 0, 0, 100.0, "input-1", "output-1")

    assert DC_SWEEP_RUNNER_SCHEMA_VERSION == "dc-sweep-runner.v1"
    assert runners.__all__ == [
        "DC_SWEEP_RUNNER_SCHEMA_VERSION",
        "DCSweepAcquisitionStep",
        "DCSweepPlan",
        "DCSweepRunnerResult",
        "run_dc_sweep",
    ]
    assert selected_plan.expected_points == 6
    assert selected_plan.expected_measurements == 12
    assert isinstance(selected_plan.setpoints, tuple)
    assert step.schema_version == DC_SWEEP_RUNNER_SCHEMA_VERSION
    with pytest.raises(FrozenInstanceError):
        selected_plan.repetitions = 3  # type: ignore[misc]


@pytest.mark.parametrize("field", ["plan_id", "plan_version", "stimulus_channel"])
@pytest.mark.parametrize("value", ["", " bad", "bad "])
def test_plan_rejects_invalid_identifiers(field: str, value: str) -> None:
    values = {
        "plan_id": "dc-plan",
        "plan_version": "1.0",
        "stimulus_channel": STIMULUS,
        "unit": MeasurementUnit.MILLIVOLT,
        "setpoints": (100.0,),
        "repetitions": 1,
        "analysis_config": analysis_config(),
        field: value,
    }
    with pytest.raises(ValidationError, match=field):
        DCSweepPlan(**cast(Any, values))


@pytest.mark.parametrize("setpoints", ["bad", (), (True,), (float("nan"),)])
def test_plan_rejects_invalid_setpoints(setpoints: object) -> None:
    with pytest.raises(ValidationError, match="setpoint"):
        DCSweepPlan(
            "dc-plan",
            "1",
            STIMULUS,
            MeasurementUnit.MILLIVOLT,
            cast(Any, setpoints),
            1,
            analysis_config(),
        )


@pytest.mark.parametrize("repetitions", [True, 0, -1, 1.5, "2"])
def test_plan_rejects_invalid_repetitions(repetitions: object) -> None:
    with pytest.raises(ValidationError, match="repetitions"):
        replace(plan(), repetitions=cast(Any, repetitions))


def test_plan_rejects_wrong_types_units_channels_and_schema() -> None:
    with pytest.raises(ValidationError, match="unit must be V or mV"):
        replace(plan(), unit=cast(Any, MeasurementUnit.AMPERE))
    with pytest.raises(ValidationError, match="DCSweepAnalysisConfig"):
        replace(plan(), analysis_config=cast(Any, object()))
    with pytest.raises(ValidationError, match="channels must be distinct"):
        replace(plan(), stimulus_channel=INPUT)
    with pytest.raises(ValidationError, match="analysis normalized unit"):
        replace(plan(), unit=MeasurementUnit.VOLT)
    with pytest.raises(ValidationError, match="DCSweepAcceptanceCriteria"):
        replace(plan(), criteria=cast(Any, object()))
    with pytest.raises(ValidationError, match="criteria normalized unit"):
        replace(plan(), criteria=criteria(unit=MeasurementUnit.VOLT))
    with pytest.raises(ValidationError, match="runner schema"):
        replace(plan(), schema_version="dc-sweep-runner.v2")


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"sequence": -1}, "sequence"),
        ({"setpoint_index": True}, "setpoint_index"),
        ({"repetition_index": 1.5}, "repetition_index"),
        ({"setpoint": float("inf")}, "finite"),
        ({"input_record_id": ""}, "input_record_id"),
        ({"output_record_id": " bad"}, "output_record_id"),
        ({"output_record_id": "input-1"}, "distinct"),
        ({"schema_version": "runner.v2"}, "runner schema"),
    ],
)
def test_acquisition_step_rejects_invalid_values(
    changes: dict[str, object], message: str
) -> None:
    values: dict[str, object] = {
        "sequence": 0,
        "setpoint_index": 0,
        "repetition_index": 0,
        "setpoint": 100.0,
        "input_record_id": "input-1",
        "output_record_id": "output-1",
    }
    values.update(changes)
    with pytest.raises(ValidationError, match=message):
        DCSweepAcquisitionStep(**cast(Any, values))


def test_complete_runner_passes_and_preserves_order_lineage_and_cleanup() -> None:
    adapter = ReferenceOutputAdapter()
    waits: list[float] = []

    result = run_dc_sweep(
        adapter,
        plan(),
        config(),
        metadata(),
        settle=waits.append,
    )

    assert result.outcome is RunOutcome.PASS
    assert result.evaluation is not None
    assert result.analysis is result.evaluation.analysis
    assert result.evaluation.passed_criteria == 5
    assert len(result.measurements) == 6
    assert len(result.completed_steps) == 3
    assert [step.setpoint for step in result.completed_steps] == [100, 200, 300]
    assert result.test_run_result.evidence_record_ids == tuple(
        f"record-{index}" for index in range(6)
    )
    assert result.test_run_result.metadata.input_record_ids == tuple(
        f"raw-{index}" for index in range(6)
    )
    assert waits == [0.25, 0.25, 0.25]
    assert adapter.calls[-2:] == ["safe_shutdown", "disconnect"]
    assert adapter.state is AdapterState.DISCONNECTED
    assert not result.test_run_result.metadata.is_bench_evidence


def test_runner_can_produce_fail_or_criteria_incomplete_only_after_full_cleanup() -> None:
    failed_plan = plan(acceptance=criteria(target_gain=3.0))
    failed = run_reference(selected_plan=failed_plan)
    no_criteria = replace(plan(), criteria=None)
    incomplete = run_reference(selected_plan=no_criteria)

    assert failed.outcome is RunOutcome.FAIL
    assert failed.evaluation is not None
    assert failed.evaluation.failed_criteria == 1
    assert incomplete.outcome is RunOutcome.INCOMPLETE
    assert incomplete.evaluation is not None
    assert incomplete.test_run_result.missing_requirements == (
        "acceptance-criteria",
    )


def test_runner_supports_repetition_order_and_incomplete_analysis() -> None:
    repeated = run_reference(
        selected_plan=plan(setpoints=(100.0, 200.0, 300.0), repetitions=2)
    )
    same_input = run_reference(
        selected_plan=plan(setpoints=(100.0, 100.0, 100.0))
    )

    assert [
        (step.setpoint_index, step.repetition_index, step.setpoint)
        for step in repeated.completed_steps
    ] == [
        (0, 0, 100.0),
        (0, 1, 100.0),
        (1, 0, 200.0),
        (1, 1, 200.0),
        (2, 0, 300.0),
        (2, 1, 300.0),
    ]
    assert repeated.outcome is RunOutcome.PASS
    assert same_input.outcome is RunOutcome.INCOMPLETE
    assert same_input.analysis is not None
    assert "analysis:distinct-input-values:1/2" in (
        same_input.test_run_result.missing_requirements
    )


@pytest.mark.parametrize(
    ("declared", "expected"),
    [
        (
            capabilities(output=False, safe_shutdown=False),
            {
                "command:SET_ANALOG_STIMULUS",
                f"output-channel:{STIMULUS}",
                "command:SAFE_SHUTDOWN",
            },
        ),
        (
            capabilities(read=False),
            {"command:READ_MEASUREMENT"},
        ),
        (
            capabilities(unit=MeasurementUnit.VOLT),
            {
                f"analog-unit:{INPUT}:mV",
                f"analog-unit:{OUTPUT}:mV",
                f"output-unit:{STIMULUS}:mV",
            },
        ),
    ],
)
def test_capability_preflight_returns_unsupported_without_output(
    declared: DeviceCapabilities,
    expected: set[str],
) -> None:
    adapter = ReferenceOutputAdapter(declared)

    result = run_reference(adapter)

    assert result.outcome is RunOutcome.UNSUPPORTED
    assert set(result.test_run_result.missing_requirements) == expected
    assert result.measurements == ()
    assert not any(isinstance(call, tuple) and call[0] == "set" for call in adapter.calls)
    assert "safe_shutdown" not in adapter.calls
    assert adapter.calls[-1] == "disconnect"
    assert adapter.state is AdapterState.DISCONNECTED


def test_capability_preflight_lists_a_missing_analysis_channel() -> None:
    declared = DeviceCapabilities(
        device_id="reference-output-1",
        profile_name="reference-output",
        profile_version="1",
        adc_channels=(INPUT,),
        dac_channels=(STIMULUS,),
        safe_input_ranges=(
            ChannelRange(
                INPUT,
                SafeRange(0.0, 1200.0, MeasurementUnit.MILLIVOLT),
            ),
        ),
        safe_output_ranges=(
            ChannelRange(
                STIMULUS,
                SafeRange(0.0, 1200.0, MeasurementUnit.MILLIVOLT),
            ),
        ),
        supported_commands=frozenset(
            {
                DeviceCommand.READ_MEASUREMENT,
                DeviceCommand.SET_ANALOG_STIMULUS,
                DeviceCommand.SAFE_SHUTDOWN,
            }
        ),
        supports_safe_shutdown=True,
    )

    result = run_reference(ReferenceOutputAdapter(declared))

    assert result.outcome is RunOutcome.UNSUPPORTED
    assert result.test_run_result.missing_requirements == (
        f"analog-channel:{OUTPUT}",
    )


def test_out_of_range_setpoint_and_disabled_output_are_rejected_before_connect() -> None:
    adapter = ReferenceOutputAdapter()
    with pytest.raises(Exception, match="outside"):
        run_reference(adapter, selected_plan=plan(setpoints=(1001.0,)))
    assert adapter.calls == []

    with pytest.raises(ValidationError, match="allow_output=true"):
        run_reference(adapter, selected_config=config(allow_output=False))
    assert adapter.calls == []


def test_abort_before_output_and_after_settle_are_incomplete_and_shutdown() -> None:
    before = ReferenceOutputAdapter()
    before_result = run_reference(before, abort_requested=lambda: True)
    calls = iter((False, True))
    after = ReferenceOutputAdapter()
    after_result = run_reference(after, abort_requested=lambda: next(calls))

    assert before_result.outcome is RunOutcome.INCOMPLETE
    assert before_result.measurements == ()
    assert not any(isinstance(call, tuple) and call[0] == "set" for call in before.calls)
    assert before.calls[-2:] == ["safe_shutdown", "disconnect"]
    assert after_result.outcome is RunOutcome.INCOMPLETE
    assert after_result.measurements == ()
    assert any(isinstance(call, tuple) and call[0] == "set" for call in after.calls)
    assert after.calls[-2:] == ["safe_shutdown", "disconnect"]


@pytest.mark.parametrize(
    ("read_error", "outcome", "gap"),
    [
        (ReplayEndOfData("early EOF"), RunOutcome.INCOMPLETE, "acquisition-end-of-data"),
        (AdapterError("read failed"), RunOutcome.ERROR, "execution-error:AdapterError"),
    ],
)
def test_read_end_or_failure_preserves_partial_evidence_and_cleans_up(
    read_error: Exception,
    outcome: RunOutcome,
    gap: str,
) -> None:
    adapter = ReferenceOutputAdapter()
    adapter.read_error_at = 3
    adapter.read_error = read_error

    result = run_reference(adapter)

    assert result.outcome is outcome
    assert len(result.measurements) == 3
    assert len(result.completed_steps) == 1
    assert gap in result.test_run_result.missing_requirements
    assert result.test_run_result.evidence_record_ids == (
        "record-0",
        "record-1",
        "record-2",
    )
    assert adapter.calls[-2:] == ["safe_shutdown", "disconnect"]


def test_wait_abort_callback_duplicate_and_keyboard_interrupt_never_pass() -> None:
    wait_failure = run_reference(
        settle=lambda _seconds: (_ for _ in ()).throw(RuntimeError("wait failed"))
    )
    abort_failure = run_reference(
        abort_requested=lambda: (_ for _ in ()).throw(RuntimeError("abort failed"))
    )
    duplicate_output_adapter = ReferenceOutputAdapter()
    duplicate_output_adapter.duplicate_record_at = 1
    duplicate_output = run_reference(duplicate_output_adapter)
    duplicate_input_adapter = ReferenceOutputAdapter()
    duplicate_input_adapter.duplicate_record_at = 2
    duplicate_input = run_reference(duplicate_input_adapter)
    interrupted = run_reference(
        settle=lambda _seconds: (_ for _ in ()).throw(KeyboardInterrupt())
    )

    assert wait_failure.outcome is RunOutcome.ERROR
    assert wait_failure.test_run_result.missing_requirements == (
        "execution-error:RuntimeError",
    )
    assert abort_failure.outcome is RunOutcome.ERROR
    assert duplicate_output.outcome is RunOutcome.ERROR
    assert duplicate_output.test_run_result.missing_requirements == (
        "execution-error:AdapterDataError",
    )
    assert len(duplicate_output.measurements) == 1
    assert duplicate_input.outcome is RunOutcome.ERROR
    assert len(duplicate_input.measurements) == 2
    assert interrupted.outcome is RunOutcome.INCOMPLETE
    assert interrupted.test_run_result.missing_requirements[0] == (
        "runner-interrupted"
    )


@pytest.mark.parametrize("cleanup_point", ["shutdown", "disconnect"])
def test_cleanup_failure_overrides_an_apparent_pass(cleanup_point: str) -> None:
    adapter = ReferenceOutputAdapter()
    if cleanup_point == "shutdown":
        adapter.shutdown_error = AdapterError("safe state failed")
    else:
        adapter.disconnect_error = RuntimeError("close failed")

    result = run_reference(adapter)

    assert result.outcome is RunOutcome.ERROR
    assert result.analysis is None
    assert result.evaluation is None
    assert result.test_run_result.missing_requirements[0].startswith(
        "cleanup-error:"
    )
    assert adapter.state is AdapterState.DISCONNECTED


def test_connection_capability_and_analysis_errors_become_explicit_error_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connect_adapter = ReferenceOutputAdapter()
    connect_adapter.connect_error = RuntimeError("port unavailable")
    connect_result = run_reference(connect_adapter)
    capability_adapter = ReferenceOutputAdapter()
    capability_adapter.capability_error = AdapterDataError("bad capabilities")
    capability_result = run_reference(capability_adapter)

    assert connect_result.outcome is RunOutcome.ERROR
    assert connect_result.capabilities is None
    assert connect_adapter.state is AdapterState.DISCONNECTED
    assert capability_result.outcome is RunOutcome.ERROR
    assert capability_adapter.calls[-1] == "disconnect"

    def fail_analysis(*_args: object, **_kwargs: object) -> Any:
        raise ValidationError("analysis failed")

    monkeypatch.setattr(runner_module, "analyze_dc_sweep", fail_analysis)
    analysis_result = run_reference()
    assert analysis_result.outcome is RunOutcome.ERROR
    assert analysis_result.test_run_result.missing_requirements == (
        "analysis-error:ValidationError",
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("adapter", object(), "DeviceAdapter"),
        ("plan", object(), "DCSweepPlan"),
        ("config", object(), "ValidationConfig"),
        ("metadata", object(), "TestRunMetadata"),
        ("settle", 1, "settle"),
        ("abort_requested", 1, "abort_requested"),
    ],
)
def test_runner_rejects_wrong_input_types(
    field: str,
    value: object,
    message: str,
) -> None:
    values: dict[str, Any] = {
        "adapter": ReferenceOutputAdapter(),
        "plan": plan(),
        "config": config(),
        "metadata": metadata(),
        "settle": lambda _seconds: None,
        "abort_requested": lambda: False,
    }
    values[field] = value
    with pytest.raises(ValidationError, match=message):
        run_dc_sweep(**values)


def test_runner_static_metadata_config_and_state_gates_prevent_io() -> None:
    adapter = ReferenceOutputAdapter()
    cases = (
        (config(source=EvidenceSource.SYNTHETIC), metadata(), "configuration evidence"),
        (config(), replace(metadata(), test_type="hysteresis"), "test_type"),
        (
            config(),
            metadata(source=EvidenceSource.SYNTHETIC),
            "metadata evidence",
        ),
        (
            config(),
            replace(metadata(), input_record_ids=("predeclared",)),
            "input_record_ids",
        ),
        (
            config(),
            replace(metadata(), configuration_id="other"),
            "configuration",
        ),
        (
            config(),
            replace(metadata(), profile_name="other"),
            "profile",
        ),
    )
    for selected_config, selected_metadata, message in cases:
        with pytest.raises(ValidationError, match=message):
            run_reference(
                adapter,
                selected_config=selected_config,
                selected_metadata=selected_metadata,
            )
        assert adapter.calls == []

    adapter.connect()
    with pytest.raises(AdapterStateError, match="disconnected"):
        run_reference(adapter)
    adapter.disconnect()


def test_runner_rejects_misconfigured_channels_before_connect() -> None:
    base = config()
    disabled_stimulus = replace(
        base,
        channels=(
            *base.channels[:2],
            replace(base.channels[2], enabled=False),
            ChannelConfig(
                "unused-output",
                ChannelRole.ANALOG_OUTPUT,
                MeasurementUnit.MILLIVOLT,
                safe_output_range=SafeRange(
                    0.0, 1000.0, MeasurementUnit.MILLIVOLT
                ),
            ),
        ),
    )
    wrong_stimulus_unit = replace(
        base,
        channels=(
            *base.channels[:2],
            ChannelConfig(
                STIMULUS,
                ChannelRole.ANALOG_OUTPUT,
                MeasurementUnit.VOLT,
                safe_output_range=SafeRange(0.0, 1.0, MeasurementUnit.VOLT),
            ),
        ),
    )
    disabled_input = replace(
        base,
        channels=(replace(base.channels[0], enabled=False), *base.channels[1:]),
    )
    wrong_input_unit = replace(
        base,
        channels=(
            ChannelConfig(INPUT, ChannelRole.ANALOG_INPUT, MeasurementUnit.VOLT),
            *base.channels[1:],
        ),
    )

    for selected, message in (
        (disabled_stimulus, "enabled output"),
        (wrong_stimulus_unit, "stimulus channel unit"),
        (disabled_input, "enabled analog input"),
        (wrong_input_unit, "analysis channel"),
    ):
        adapter = ReferenceOutputAdapter()
        with pytest.raises(ValidationError, match=message):
            run_reference(adapter, selected_config=selected)
        assert adapter.calls == []


def test_connected_metadata_or_profile_mismatch_is_error_without_output() -> None:
    wrong_device = run_reference(selected_metadata=metadata(device_id="other"))
    mismatched_profile_adapter = ReferenceOutputAdapter(
        capabilities(profile_name="other")
    )
    profile_error = run_reference(mismatched_profile_adapter)

    assert wrong_device.outcome is RunOutcome.ERROR
    assert wrong_device.test_run_result.missing_requirements == (
        "execution-error:ValidationError",
    )
    assert profile_error.outcome is RunOutcome.ERROR
    assert not any(
        isinstance(call, tuple) and call[0] == "set"
        for call in mismatched_profile_adapter.calls
    )


def test_runner_result_rejects_corrupted_fields_and_relationships() -> None:
    passing = run_reference()
    assert passing.evaluation is not None
    assert passing.analysis is not None

    with pytest.raises(ValidationError, match="plan"):
        replace(passing, plan=cast(Any, object()))
    with pytest.raises(ValidationError, match="capabilities"):
        replace(passing, capabilities=cast(Any, object()))
    with pytest.raises(ValidationError, match="measurements must be an iterable"):
        replace(passing, measurements=cast(Any, "bad"))
    with pytest.raises(ValidationError, match="Measurement"):
        replace(passing, measurements=cast(Any, (object(),)))
    with pytest.raises(ValidationError, match="completed_steps must be an iterable"):
        replace(passing, completed_steps=cast(Any, "bad"))
    with pytest.raises(ValidationError, match="DCSweepAcquisitionStep"):
        replace(passing, completed_steps=cast(Any, (object(),)))
    with pytest.raises(ValidationError, match="analysis must"):
        replace(passing, analysis=cast(Any, object()))
    with pytest.raises(ValidationError, match="evaluation must"):
        replace(passing, evaluation=cast(Any, object()))
    with pytest.raises(ValidationError, match="TestRunResult"):
        replace(passing, test_run_result=cast(Any, object()))
    with pytest.raises(ValidationError, match="runner schema"):
        replace(passing, schema_version="runner.v2")


def test_runner_result_rejects_corrupted_evidence_steps_and_conclusion() -> None:
    passing = run_reference()
    assert passing.evaluation is not None
    assert passing.analysis is not None
    duplicate = replace(passing.measurements[1], record_id="record-0")
    wrong_source = replace(
        passing.measurements[0], source=EvidenceSource.SYNTHETIC
    )

    with pytest.raises(ValidationError, match="record IDs"):
        replace(passing, measurements=(passing.measurements[0], duplicate, *passing.measurements[2:]))
    with pytest.raises(ValidationError, match="sources"):
        replace(passing, measurements=(wrong_source, *passing.measurements[1:]))
    with pytest.raises(ValidationError, match="evidence IDs"):
        replace(
            passing,
            test_run_result=replace(
                passing.test_run_result,
                evidence_record_ids=passing.test_run_result.evidence_record_ids[:-1],
            ),
        )
    with pytest.raises(ValidationError, match="raw IDs"):
        replace(
            passing,
            test_run_result=replace(
                passing.test_run_result,
                metadata=replace(
                    passing.test_run_result.metadata,
                    input_record_ids=("wrong",),
                ),
            ),
        )
    shortened_measurements = passing.measurements[:-2]
    shortened_run = replace(
        passing.test_run_result,
        metadata=replace(
            passing.test_run_result.metadata,
            input_record_ids=tuple(
                item.raw_record_id for item in shortened_measurements
            ),
        ),
        evidence_record_ids=tuple(
            item.record_id for item in shortened_measurements
        ),
    )
    with pytest.raises(ValidationError, match="complete pairs"):
        replace(
            passing,
            measurements=shortened_measurements,
            test_run_result=shortened_run,
        )
    with pytest.raises(ValidationError, match="exceed"):
        replace(
            passing,
            plan=replace(passing.plan, setpoints=(100.0, 200.0)),
        )
    with pytest.raises(ValidationError, match="contiguous"):
        replace(
            passing,
            completed_steps=(replace(passing.completed_steps[0], sequence=1), *passing.completed_steps[1:]),
        )
    with pytest.raises(ValidationError, match="plan order"):
        replace(
            passing,
            completed_steps=(replace(passing.completed_steps[0], setpoint=101), *passing.completed_steps[1:]),
        )
    with pytest.raises(ValidationError, match="record IDs"):
        replace(
            passing,
            completed_steps=(replace(passing.completed_steps[0], input_record_id="record-2"), *passing.completed_steps[1:]),
        )
    wrong_channel = replace(passing.measurements[0], channel=OUTPUT)
    with pytest.raises(ValidationError, match="order"):
        replace(passing, measurements=(wrong_channel, *passing.measurements[1:]))
    wrong_unit = replace(passing.measurements[0], unit=MeasurementUnit.VOLT)
    with pytest.raises(ValidationError, match="units"):
        replace(passing, measurements=(wrong_unit, *passing.measurements[1:]))


def test_runner_result_rejects_invalid_evaluation_relationships() -> None:
    passing = run_reference()
    failed = run_reference(selected_plan=plan(acceptance=criteria(target_gain=3.0)))
    different = run_reference(
        selected_plan=plan(setpoints=(100.0, 100.0, 100.0))
    )
    assert passing.analysis is not None
    assert passing.evaluation is not None
    assert failed.evaluation is not None

    with pytest.raises(ValidationError, match="analysis without evaluation"):
        replace(passing, evaluation=None)
    with pytest.raises(ValidationError, match="require evaluation"):
        replace(passing, analysis=None, evaluation=None)
    with pytest.raises(ValidationError, match="runner analysis"):
        replace(passing, analysis=different.analysis)
    with pytest.raises(ValidationError, match="criteria"):
        replace(passing, evaluation=failed.evaluation)
    with pytest.raises(ValidationError, match="TestRun results"):
        replace(
            passing,
            test_run_result=failed.test_run_result,
        )
    with pytest.raises(ValidationError, match="all measurements"):
        replace(
            passing,
            plan=replace(passing.plan, setpoints=(*passing.plan.setpoints, 400.0)),
        )


def test_runner_result_validates_capability_identity() -> None:
    passing = run_reference()
    wrong_device = replace(
        capabilities(), device_id="other-device"
    )
    wrong_profile = replace(
        capabilities(), profile_name="other-profile"
    )
    with pytest.raises(ValidationError, match="device ID"):
        replace(passing, capabilities=wrong_device)
    with pytest.raises(ValidationError, match="profile"):
        replace(passing, capabilities=wrong_profile)
