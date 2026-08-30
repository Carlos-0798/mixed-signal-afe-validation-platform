from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

import analog_validation.analysis.hysteresis as hysteresis_module
from analog_validation.analysis import (
    HYSTERESIS_ANALYSIS_SCHEMA_VERSION,
    HYSTERESIS_CRITERIA_SCHEMA_VERSION,
    HYSTERESIS_EVALUATION_SCHEMA_VERSION,
    HYSTERESIS_TEST_TYPE,
    HysteresisAcceptanceCriteria,
    HysteresisAnalysisConfig,
    HysteresisAnalysisResult,
    HysteresisCriterionName,
    HysteresisCriterionResult,
    HysteresisCycleInput,
    HysteresisSummary,
    MeasurementBatch,
    SweepDirection,
    analyze_hysteresis,
    evaluate_hysteresis,
)
from analog_validation.domain import (
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
    QualityFlag,
)
from analog_validation.domain import TestRunMetadata as RunMetadata
from analog_validation.domain import TestRunOutcome as RunOutcome
from analog_validation.errors import ValidationError

NOW = datetime(2026, 8, 30, tzinfo=timezone.utc)


def measurement(
    record_id: str,
    channel: str,
    value: float | None,
    unit: MeasurementUnit,
    *,
    source: EvidenceSource = EvidenceSource.HOST_TEST,
    status: MeasurementStatus = MeasurementStatus.VALID,
    flags: frozenset[QualityFlag] = frozenset(),
) -> Measurement:
    return Measurement(
        record_id=record_id,
        raw_record_id=f"raw-{record_id}",
        timestamp=NOW,
        channel=channel,
        value=value,
        unit=unit,
        status=status,
        source=source,
        quality_flags=flags,
    )


def batch(
    prefix: str,
    values: list[float],
    states: list[int],
    *,
    source: EvidenceSource = EvidenceSource.HOST_TEST,
) -> MeasurementBatch:
    records: list[Measurement] = []
    for index, (value, state) in enumerate(zip(values, states, strict=True)):
        records.extend(
            (
                measurement(
                    f"{prefix}-a-{index}",
                    "vin",
                    value,
                    MeasurementUnit.MILLIVOLT,
                    source=source,
                ),
                measurement(
                    f"{prefix}-d-{index}",
                    "state",
                    state,
                    MeasurementUnit.BOOLEAN,
                    source=source,
                ),
            )
        )
    return MeasurementBatch(tuple(records))


def cycle(
    index: int = 0,
    *,
    prefix: str = "c0",
    high_shift: float = 0.0,
    low_shift: float = 0.0,
) -> HysteresisCycleInput:
    return HysteresisCycleInput(
        index,
        batch(
            f"{prefix}-r",
            [1700, 1790 + high_shift, 1810 + high_shift, 1900],
            [0, 0, 1, 1],
        ),
        batch(
            f"{prefix}-f",
            [1900, 1510 + low_shift, 1490 + low_shift, 1400],
            [1, 1, 0, 0],
        ),
    )


def config() -> HysteresisAnalysisConfig:
    return HysteresisAnalysisConfig("vin", "state")


def criteria(*, min_cycles: int = 1) -> HysteresisAcceptanceCriteria:
    return HysteresisAcceptanceCriteria(
        "schmitt-v1",
        "1",
        1750,
        1850,
        1450,
        1550,
        250,
        350,
        30,
        min_cycles,
    )


def metadata(analysis: HysteresisAnalysisResult) -> RunMetadata:
    raw_ids = tuple(
        dict.fromkeys(
            reference.raw_record_id
            for item in analysis.cycles
            for point in item.rising_points + item.falling_points
            for reference in (point.input_decision.reference, point.state_reference)
        )
    )
    return RunMetadata(
        "run-hyst",
        HYSTERESIS_TEST_TYPE,
        "cfg",
        "1",
        NOW,
        NOW,
        "0.1.0",
        "fixture",
        "reference",
        "1",
        analysis.evidence_source,
        raw_ids,
    )


def test_single_cycle_uses_adjacent_midpoints_and_preserves_lineage() -> None:
    result = analyze_hysteresis((cycle(),), config())
    assert result.schema_version == HYSTERESIS_ANALYSIS_SCHEMA_VERSION
    assert result.is_complete
    assert result.summary == HysteresisSummary(
        1, 1800, 1500, 300, 300, 300, MeasurementUnit.MILLIVOLT
    )
    assert result.summary.width_span == 0
    item = result.cycles[0]
    assert item.is_complete
    assert item.high_threshold == 1800
    assert item.low_threshold == 1500
    assert item.width == 300
    transition = item.rising_transition
    assert transition is not None
    assert transition.method == "adjacent-input-interval-midpoint"
    assert transition.before_input_reference.record_id == "c0-r-a-1"
    assert transition.before_state_reference.record_id == "c0-r-d-1"
    assert transition.after_input_reference.record_id == "c0-r-a-2"
    assert transition.after_state_reference.record_id == "c0-r-d-2"


def test_multiple_cycles_have_per_cycle_and_summary_statistics() -> None:
    result = analyze_hysteresis(
        (cycle(0, prefix="c0"), cycle(1, prefix="c1", high_shift=10, low_shift=-10)),
        config(),
    )
    assert [item.width for item in result.cycles] == [300, 320]
    assert result.summary is not None
    assert result.summary.cycle_count == 2
    assert result.summary.mean_high_threshold == 1805
    assert result.summary.mean_low_threshold == 1495
    assert result.summary.mean_width == 310
    assert result.summary.minimum_width == 300
    assert result.summary.maximum_width == 320
    assert result.summary.width_span == 20


def test_no_transition_and_missing_point_are_incomplete_without_partial_thresholds() -> (
    None
):
    no_transition = HysteresisCycleInput(
        0,
        batch("r", [1000, 2000], [0, 0]),
        batch("f", [2000, 1000], [1, 0]),
    )
    result = analyze_hysteresis((no_transition,), config())
    assert not result.is_complete
    assert result.missing_requirements == ("cycle-0:rising-transition",)
    assert result.cycles[0].high_threshold is None
    assert result.cycles[0].low_threshold is None

    rising = list(cycle().rising.measurements)
    rising[0] = measurement(
        "missing",
        "vin",
        None,
        MeasurementUnit.MILLIVOLT,
        status=MeasurementStatus.INVALID,
        flags=frozenset({QualityFlag.MISSING}),
    )
    incomplete = analyze_hysteresis(
        (HysteresisCycleInput(0, MeasurementBatch(tuple(rising)), cycle().falling),),
        config(),
    )
    assert incomplete.missing_requirements == ("cycle-0:rising-usable-points",)
    assert incomplete.cycles[0].rising_points[0].exclusion_reasons == (
        "input-not-included",
    )


@pytest.mark.parametrize(
    ("rising_values", "rising_states", "falling_values", "falling_states", "message"),
    [
        ([1000, 900], [0, 1], [2000, 1000], [1, 0], "rising input"),
        ([1000, 2000], [0, 1], [1000, 2000], [1, 0], "falling input"),
        ([1000, 2000], [1, 0], [2000, 1000], [1, 0], "rising transition is reversed"),
        ([1000, 1500, 2000], [0, 1, 0], [2000, 1000], [1, 0], "chatter"),
        ([1000, 1200], [0, 1], [2000, 1800], [1, 0], "high threshold is below"),
    ],
)
def test_structurally_unsafe_sequences_are_rejected(
    rising_values: list[float],
    rising_states: list[int],
    falling_values: list[float],
    falling_states: list[int],
    message: str,
) -> None:
    item = HysteresisCycleInput(
        0,
        batch("r", rising_values, rising_states),
        batch("f", falling_values, falling_states),
    )
    with pytest.raises(ValidationError, match=message):
        analyze_hysteresis((item,), config())


def test_non_binary_and_wrong_channel_or_unit_are_rejected() -> None:
    for replacement, message in (
        (measurement("bad", "state", 2, MeasurementUnit.BOOLEAN), "zero or one"),
        (measurement("bad", "wrong", 0, MeasurementUnit.BOOLEAN), "channel"),
        (measurement("bad", "state", 0, MeasurementUnit.UNITLESS), "unit"),
    ):
        records = list(cycle().rising.measurements)
        records[1] = replacement
        item = HysteresisCycleInput(
            0, MeasurementBatch(tuple(records)), cycle().falling
        )
        with pytest.raises(ValidationError, match=message):
            analyze_hysteresis((item,), config())


def test_invalid_state_is_an_explicit_incomplete_point() -> None:
    records = list(cycle().rising.measurements)
    records[1] = measurement(
        "bad-state",
        "state",
        None,
        MeasurementUnit.BOOLEAN,
        status=MeasurementStatus.INVALID,
        flags=frozenset({QualityFlag.MISSING}),
    )
    result = analyze_hysteresis(
        (HysteresisCycleInput(0, MeasurementBatch(tuple(records)), cycle().falling),),
        config(),
    )
    point = result.cycles[0].rising_points[0]
    assert not point.included
    assert point.state_value is None
    assert point.exclusion_reasons == ("state-status:INVALID",)


def test_criteria_pass_fail_missing_and_minimum_cycles() -> None:
    analysis = analyze_hysteresis((cycle(),), config())
    passed = evaluate_hysteresis(analysis, criteria(), metadata(analysis))
    assert passed.schema_version == HYSTERESIS_EVALUATION_SCHEMA_VERSION
    assert passed.is_conclusive
    assert passed.test_run_result.outcome is RunOutcome.PASS
    assert tuple(value.criterion for value in passed.criterion_results) == tuple(
        HysteresisCriterionName
    )
    assert all(value.passed for value in passed.criterion_results)
    assert passed.test_run_result.evidence_record_ids[0] == "c0-r-a-0"

    failed_criteria = replace(criteria(), maximum_width=299)
    failed = evaluate_hysteresis(analysis, failed_criteria, metadata(analysis))
    assert failed.test_run_result.outcome is RunOutcome.FAIL
    assert not failed.criterion_results[2].passed

    absent = evaluate_hysteresis(analysis, None, metadata(analysis))
    assert absent.test_run_result.outcome is RunOutcome.INCOMPLETE
    assert absent.test_run_result.missing_requirements == ("acceptance-criteria",)

    too_few = evaluate_hysteresis(analysis, criteria(min_cycles=2), metadata(analysis))
    assert too_few.test_run_result.outcome is RunOutcome.INCOMPLETE
    assert too_few.test_run_result.missing_requirements == (
        "criteria-complete-cycles:1/2",
    )


def test_incomplete_analysis_maps_to_incomplete_evaluation() -> None:
    item = HysteresisCycleInput(
        0,
        batch("r", [1000, 2000], [0, 0]),
        batch("f", [2000, 1000], [1, 0]),
    )
    analysis = analyze_hysteresis((item,), config())
    result = evaluate_hysteresis(analysis, criteria(), metadata(analysis))
    assert result.test_run_result.outcome is RunOutcome.INCOMPLETE
    assert result.criterion_results == ()
    assert result.test_run_result.missing_requirements == (
        "analysis:cycle-0:rising-transition",
    )


def test_public_models_reject_inconsistent_manual_construction() -> None:
    analysis = analyze_hysteresis((cycle(),), config())
    point = analysis.cycles[0].rising_points[0]
    transition = analysis.cycles[0].rising_transition
    assert transition is not None and analysis.summary is not None
    with pytest.raises(ValidationError):
        replace(point, included=False)
    with pytest.raises(ValidationError):
        replace(transition, threshold=999)
    with pytest.raises(ValidationError):
        replace(analysis.cycles[0], width=299)
    with pytest.raises(ValidationError):
        replace(analysis.summary, mean_width=999)
    with pytest.raises(ValidationError):
        replace(analysis, missing_requirements=("bad",))
    evaluation = evaluate_hysteresis(analysis, criteria(), metadata(analysis))
    with pytest.raises(ValidationError):
        replace(evaluation, criterion_results=())
    with pytest.raises(ValidationError):
        HysteresisCriterionResult(
            HysteresisCriterionName.MEAN_WIDTH,
            300,
            "mV",
            False,
            250,
            350,
        )
    assert criteria().schema_version == HYSTERESIS_CRITERIA_SCHEMA_VERSION


def test_analysis_config_and_cycle_input_validation_boundaries() -> None:
    for kwargs in (
        {"input_channel": ""},
        {"state_channel": " bad"},
        {"state_channel": "vin"},
        {"normalized_unit": MeasurementUnit.AMPERE},
        {"quality_policy": object()},
        {"schema_version": "future"},
    ):
        values = {"input_channel": "vin", "state_channel": "state", **kwargs}
        with pytest.raises(ValidationError):
            HysteresisAnalysisConfig(**values)  # type: ignore[arg-type]

    valid = cycle()
    csv_rising = batch("csv-r", [1000, 2000], [0, 1], source=EvidenceSource.CSV_REPLAY)
    for change in (
        {"cycle_index": -1},
        {"cycle_index": True},
        {"rising": object()},
        {"falling": object()},
        {"rising": csv_rising},
        {"falling": valid.rising},
        {"schema_version": "future"},
    ):
        with pytest.raises(ValidationError):
            replace(valid, **change)
    assert valid.evidence_source is EvidenceSource.HOST_TEST


def test_point_transition_cycle_and_summary_model_validation() -> None:
    analysis = analyze_hysteresis((cycle(),), config())
    item = analysis.cycles[0]
    point = item.rising_points[0]
    transition = item.rising_transition
    summary = analysis.summary
    assert transition is not None and summary is not None

    point_changes = (
        {"sequence": -1},
        {"direction": "RISING"},
        {"input_decision": object()},
        {"state_reference": object()},
        {"state_value": 2},
        {"state_status": "VALID"},
        {"state_quality_flags": frozenset({"bad"})},
        {"included": 1},
        {"exclusion_reasons": (1,)},
        {"exclusion_reasons": ("x", "x")},
        {"exclusion_reasons": ("x",)},
        {"included": False, "exclusion_reasons": ()},
        {
            "state_reference": replace(
                point.state_reference, source=EvidenceSource.CSV_REPLAY
            )
        },
        {"schema_version": "future"},
    )
    for change in point_changes:
        with pytest.raises((ValidationError, TypeError)):
            replace(point, **change)

    transition_changes = (
        {"direction": "RISING"},
        {"before_input_reference": object()},
        {
            "after_state_reference": replace(
                transition.after_state_reference, source=EvidenceSource.CSV_REPLAY
            )
        },
        {"before_state": 1},
        {"interval_start": "bad"},
        {"interval_end": float("inf")},
        {"threshold": 1},
        {"interval_start": 2000, "interval_end": 1000, "threshold": 1500},
        {
            "direction": SweepDirection.FALLING,
            "before_state": 1,
            "after_state": 0,
            "interval_start": 1000,
            "interval_end": 2000,
            "threshold": 1500,
        },
        {"unit": MeasurementUnit.AMPERE},
        {"method": "first-sample"},
        {"schema_version": "future"},
    )
    for transition_change in transition_changes:
        with pytest.raises(ValidationError):
            replace(transition, **transition_change)

    falling_as_rising = replace(item.falling_points[0], direction=SweepDirection.RISING)
    rising_as_falling = replace(item.rising_points[0], direction=SweepDirection.FALLING)
    cycle_changes = (
        {"cycle_index": -1},
        {"rising_points": ()},
        {"falling_points": (object(),)},
        {"rising_points": (rising_as_falling,)},
        {"falling_points": (falling_as_rising,)},
        {"missing_requirements": ("x", "x")},
        {"unit": MeasurementUnit.AMPERE},
        {"high_threshold": None},
        {"rising_transition": None},
        {"high_threshold": 1400, "low_threshold": 1500, "width": -100},
        {"width": 299},
        {"high_threshold": 1801, "width": 301},
        {
            "high_threshold": None,
            "low_threshold": None,
            "width": None,
            "missing_requirements": (),
            "rising_transition": None,
            "falling_transition": None,
        },
        {"missing_requirements": ("x",)},
        {
            "high_threshold": None,
            "low_threshold": None,
            "width": None,
            "missing_requirements": ("x",),
        },
        {"schema_version": "future"},
    )
    for cycle_change in cycle_changes:
        with pytest.raises((ValidationError, TypeError)):
            replace(item, **cycle_change)

    for summary_change in (
        {"cycle_count": 0},
        {"cycle_count": True},
        {"mean_high_threshold": "bad"},
        {"mean_low_threshold": float("nan")},
        {"mean_high_threshold": 1400, "mean_low_threshold": 1500},
        {"minimum_width": -1},
        {"minimum_width": 400, "maximum_width": 300},
        {"mean_width": 400},
        {"unit": MeasurementUnit.AMPERE},
        {"schema_version": "future"},
    ):
        with pytest.raises(ValidationError):
            replace(summary, **summary_change)


def test_analysis_result_and_function_input_validation() -> None:
    analysis = analyze_hysteresis((cycle(),), config())
    assert analysis.summary is not None
    for result_change in (
        {"config": object()},
        {"evidence_source": "HOST_TEST"},
        {"cycles": ()},
        {"cycles": (object(),)},
        {"cycles": (replace(analysis.cycles[0], cycle_index=1),)},
        {"evidence_source": EvidenceSource.CSV_REPLAY},
        {"missing_requirements": ("x", "x")},
        {"summary": None, "missing_requirements": ()},
        {"summary": object()},
        {"missing_requirements": ("x",)},
        {"summary": replace(analysis.summary, cycle_count=2)},
        {"schema_version": "future"},
    ):
        with pytest.raises((ValidationError, TypeError)):
            replace(analysis, **result_change)

    with pytest.raises(ValidationError):
        hysteresis_module._state_value("bad", config())
    with pytest.raises(ValidationError, match="pairs"):
        analyze_hysteresis(
            (
                HysteresisCycleInput(
                    0,
                    MeasurementBatch(cycle().rising.measurements[:-1]),
                    cycle().falling,
                ),
            ),
            config(),
        )
    with pytest.raises(ValidationError, match="input record channel"):
        records = list(cycle().rising.measurements)
        records[0] = measurement(
            "wrong-input", "wrong", 1400, MeasurementUnit.MILLIVOLT
        )
        analyze_hysteresis(
            (
                HysteresisCycleInput(
                    0, MeasurementBatch(tuple(records)), cycle().falling
                ),
            ),
            config(),
        )
    with pytest.raises(ValidationError, match="at least two"):
        analyze_hysteresis(
            (
                HysteresisCycleInput(
                    0,
                    MeasurementBatch(cycle().rising.measurements[:2]),
                    cycle().falling,
                ),
            ),
            config(),
        )

    for cycles_value, selected_config in (
        ("bad", config()),
        ((), config()),
        ((cycle(),), object()),
        ((replace(cycle(), cycle_index=1),), config()),
    ):
        with pytest.raises(ValidationError):
            analyze_hysteresis(cycles_value, selected_config)  # type: ignore[arg-type]

    second_source = HysteresisCycleInput(
        1,
        batch("csv-r", [1000, 2000], [0, 1], source=EvidenceSource.CSV_REPLAY),
        batch("csv-f", [2000, 1000], [1, 0], source=EvidenceSource.CSV_REPLAY),
    )
    with pytest.raises(ValidationError, match="one evidence source"):
        analyze_hysteresis((cycle(), second_source), config())
    duplicate = replace(cycle(1, prefix="c1"), rising=cycle().rising)
    with pytest.raises(ValidationError, match="unique across cycles"):
        analyze_hysteresis((cycle(), duplicate), config())


def test_criteria_and_evaluation_validation_boundaries() -> None:
    base = criteria()
    for criteria_change in (
        {"criteria_id": ""},
        {"criteria_version": " bad"},
        {"minimum_high_threshold": "bad"},
        {"maximum_high_threshold": float("inf")},
        {"minimum_high_threshold": 1900, "maximum_high_threshold": 1800},
        {"minimum_width": -1},
        {"maximum_width_span": -1},
        {"minimum_complete_cycles": 0},
        {"minimum_complete_cycles": True},
        {"normalized_unit": MeasurementUnit.AMPERE},
        {"schema_version": "future"},
    ):
        with pytest.raises(ValidationError):
            replace(base, **criteria_change)

    valid_check = HysteresisCriterionResult(
        HysteresisCriterionName.MEAN_WIDTH, 300, "mV", True, 250, 350
    )
    for check_change in (
        {"criterion": "MEAN_WIDTH"},
        {"actual_value": "bad"},
        {"unit": "ratio"},
        {"passed": 1},
        {"lower_limit": None, "upper_limit": None},
        {"lower_limit": 400, "upper_limit": 300},
        {"passed": False},
        {"schema_version": "future"},
    ):
        with pytest.raises(ValidationError):
            replace(valid_check, **check_change)
    with pytest.raises(ValidationError, match="cycles"):
        HysteresisCriterionResult(
            HysteresisCriterionName.COMPLETE_CYCLES, 1, "mV", True, 1, None
        )

    analysis = analyze_hysteresis((cycle(),), config())
    run_metadata = metadata(analysis)
    for changed, message in (
        (replace(run_metadata, test_type="wrong"), "test_type"),
        (replace(run_metadata, evidence_source=EvidenceSource.CSV_REPLAY), "source"),
        (replace(run_metadata, input_record_ids=()), "raw records"),
    ):
        with pytest.raises(ValidationError, match=message):
            evaluate_hysteresis(analysis, base, changed)
    with pytest.raises(ValidationError, match="criteria unit"):
        evaluate_hysteresis(
            analysis, replace(base, normalized_unit=MeasurementUnit.VOLT), run_metadata
        )
    for value, selected_criteria, selected_metadata in (
        (object(), base, run_metadata),
        (analysis, object(), run_metadata),
        (analysis, base, object()),
    ):
        with pytest.raises(ValidationError):
            evaluate_hysteresis(value, selected_criteria, selected_metadata)  # type: ignore[arg-type]

    evaluation = evaluate_hysteresis(analysis, base, run_metadata)
    for evaluation_change in (
        {"analysis": object()},
        {"criteria": object()},
        {"criterion_results": "bad"},
        {"criterion_results": (object(),)},
        {"test_run_result": object()},
        {"test_run_result": replace(evaluation.test_run_result, summary="wrong")},
        {
            "test_run_result": replace(
                evaluation.test_run_result, evidence_record_ids=("wrong",)
            )
        },
        {"schema_version": "future"},
    ):
        with pytest.raises((ValidationError, TypeError)):
            replace(evaluation, **evaluation_change)

    duplicate_point = replace(
        analysis.cycles[0].rising_points[0],
        state_reference=analysis.cycles[0].rising_points[0].input_decision.reference,
    )
    duplicate_cycle = replace(
        analysis.cycles[0],
        rising_points=(duplicate_point, *analysis.cycles[0].rising_points[1:]),
    )
    duplicate_analysis = replace(analysis, cycles=(duplicate_cycle,))
    with pytest.raises(ValidationError, match="record IDs"):
        evaluate_hysteresis(
            duplicate_analysis,
            base,
            metadata(duplicate_analysis),
        )
