"""Tests for versioned DC sweep criteria and TestRun mapping."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest

from analog_validation import (
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
    ValidationError,
)
from analog_validation import TestRunMetadata as RunMetadata
from analog_validation import TestRunOutcome as RunOutcome
from analog_validation import TestRunResult as RunResult
from analog_validation.analysis import (
    DC_SWEEP_CRITERIA_SCHEMA_VERSION,
    DC_SWEEP_EVALUATION_SCHEMA_VERSION,
    DC_SWEEP_TEST_TYPE,
    DCSweepAcceptanceCriteria,
    DCSweepAnalysisConfig,
    DCSweepAnalysisResult,
    DCSweepCriterionName,
    DCSweepCriterionResult,
    DCSweepEvaluationResult,
    MeasurementBatch,
    analyze_dc_sweep,
    evaluate_dc_sweep,
)

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
INPUT_CHANNEL = "afe.ch0.input"
OUTPUT_CHANNEL = "afe.ch0.output"


def make_measurement(
    record_id: str,
    channel: str,
    value: float,
    *,
    sequence: int,
    unit: MeasurementUnit = MeasurementUnit.MILLIVOLT,
    source: EvidenceSource = EvidenceSource.SYNTHETIC,
    raw_record_id: str | None = None,
) -> Measurement:
    return Measurement(
        record_id=record_id,
        raw_record_id=raw_record_id or f"raw-{record_id}",
        timestamp=NOW + timedelta(milliseconds=sequence),
        channel=channel,
        value=value,
        unit=unit,
        status=MeasurementStatus.VALID,
        source=source,
    )


def make_analysis(
    inputs: list[float],
    outputs: list[float],
    *,
    unit: MeasurementUnit = MeasurementUnit.MILLIVOLT,
    source: EvidenceSource = EvidenceSource.SYNTHETIC,
    minimum: int = 3,
    shared_raw_id: str | None = None,
) -> DCSweepAnalysisResult:
    records: list[Measurement] = []
    for index, (input_value, output_value) in enumerate(zip(inputs, outputs)):
        records.extend(
            (
                make_measurement(
                    f"input-{index}",
                    INPUT_CHANNEL,
                    input_value,
                    sequence=index * 2,
                    unit=unit,
                    source=source,
                    raw_record_id=shared_raw_id,
                ),
                make_measurement(
                    f"output-{index}",
                    OUTPUT_CHANNEL,
                    output_value,
                    sequence=index * 2 + 1,
                    unit=unit,
                    source=source,
                    raw_record_id=shared_raw_id,
                ),
            )
        )
    return analyze_dc_sweep(
        MeasurementBatch(tuple(records)),
        DCSweepAnalysisConfig(
            input_channel=INPUT_CHANNEL,
            output_channel=OUTPUT_CHANNEL,
            low_output_limit=-10_000.0,
            high_output_limit=10_000.0,
            normalized_unit=unit,
            minimum_included_points=minimum,
        ),
    )


def exact_analysis(
    *,
    unit: MeasurementUnit = MeasurementUnit.MILLIVOLT,
    source: EvidenceSource = EvidenceSource.SYNTHETIC,
) -> DCSweepAnalysisResult:
    scale = 1.0 if unit is MeasurementUnit.MILLIVOLT else 0.001
    return make_analysis(
        [100.0 * scale, 200.0 * scale, 300.0 * scale, 400.0 * scale],
        [212.0 * scale, 412.0 * scale, 612.0 * scale, 812.0 * scale],
        unit=unit,
        source=source,
    )


def raw_ids(analysis: DCSweepAnalysisResult) -> tuple[str, ...]:
    values = (
        reference.raw_record_id
        for point in analysis.points
        for reference in (
            point.input_decision.reference,
            point.output_decision.reference,
        )
    )
    return tuple(dict.fromkeys(values))


def evidence_ids(analysis: DCSweepAnalysisResult) -> tuple[str, ...]:
    return tuple(
        reference.record_id
        for point in analysis.points
        for reference in (
            point.input_decision.reference,
            point.output_decision.reference,
        )
    )


def make_metadata(
    analysis: DCSweepAnalysisResult,
    **overrides: Any,
) -> RunMetadata:
    values: dict[str, Any] = {
        "run_id": "dc-run-001",
        "test_type": DC_SWEEP_TEST_TYPE,
        "configuration_id": "dc-plan-default",
        "configuration_version": "1.0",
        "started_at": NOW,
        "ended_at": NOW + timedelta(seconds=2),
        "software_version": "0.1.0.dev0",
        "device_id": "simulator-001",
        "profile_name": "afe-simulator",
        "profile_version": "1.0",
        "evidence_source": analysis.evidence_source,
        "input_record_ids": raw_ids(analysis),
    }
    values.update(overrides)
    return RunMetadata(**values)


def make_criteria(**overrides: Any) -> DCSweepAcceptanceCriteria:
    values: dict[str, Any] = {
        "criteria_id": "afe-dc-nominal",
        "criteria_version": "1.0",
        "target_gain": 2.0,
        "gain_absolute_tolerance": 0.05,
        "max_abs_offset": 20.0,
        "min_r_squared": 0.99,
        "max_rmse": 5.0,
        "minimum_included_points": 3,
        "normalized_unit": MeasurementUnit.MILLIVOLT,
    }
    values.update(overrides)
    return DCSweepAcceptanceCriteria(**values)


def passing_evaluation() -> DCSweepEvaluationResult:
    analysis = exact_analysis()
    return evaluate_dc_sweep(analysis, make_criteria(), make_metadata(analysis))


def test_public_criteria_schema_enum_and_exports_are_stable() -> None:
    import analog_validation.analysis.dc_criteria as module
    from analog_validation import analysis

    expected = {
        "DC_SWEEP_CRITERIA_SCHEMA_VERSION",
        "DC_SWEEP_EVALUATION_SCHEMA_VERSION",
        "DC_SWEEP_TEST_TYPE",
        "DCSweepAcceptanceCriteria",
        "DCSweepCriterionName",
        "DCSweepCriterionResult",
        "DCSweepEvaluationResult",
        "evaluate_dc_sweep",
    }

    assert DC_SWEEP_CRITERIA_SCHEMA_VERSION == "dc-sweep-criteria.v1"
    assert DC_SWEEP_EVALUATION_SCHEMA_VERSION == "dc-sweep-evaluation.v1"
    assert DC_SWEEP_TEST_TYPE == "dc-sweep"
    assert set(module.__all__) == expected
    assert expected.issubset(set(analysis.__all__))
    assert tuple(value.value for value in DCSweepCriterionName) == (
        "GAIN",
        "ABS_OFFSET",
        "R_SQUARED",
        "RMSE",
        "INCLUDED_POINTS",
    )


def test_acceptance_criteria_normalizes_numbers_and_is_frozen() -> None:
    criteria = make_criteria(
        target_gain=2,
        gain_absolute_tolerance=0,
        max_abs_offset=20,
        min_r_squared=1,
        max_rmse=0,
    )

    assert criteria.target_gain == 2.0
    assert criteria.gain_absolute_tolerance == 0.0
    assert criteria.max_abs_offset == 20.0
    assert criteria.min_r_squared == 1.0
    assert criteria.max_rmse == 0.0
    assert criteria.normalized_unit is MeasurementUnit.MILLIVOLT
    with pytest.raises(FrozenInstanceError):
        criteria.target_gain = 3.0  # type: ignore[misc]


@pytest.mark.parametrize("field", ["criteria_id", "criteria_version"])
@pytest.mark.parametrize("value", [None, "", " bad", "bad "])
def test_acceptance_criteria_rejects_bad_identifiers(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError, match=field):
        make_criteria(**{field: value})


@pytest.mark.parametrize(
    "field",
    [
        "target_gain",
        "gain_absolute_tolerance",
        "max_abs_offset",
        "min_r_squared",
        "max_rmse",
    ],
)
@pytest.mark.parametrize("value", [True, "1", None])
def test_acceptance_criteria_rejects_non_numeric_values(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError, match="numeric"):
        make_criteria(**{field: value})


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_acceptance_criteria_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(ValidationError, match="finite"):
        make_criteria(target_gain=value)


def test_acceptance_criteria_rejects_overflowing_derived_gain_limits() -> None:
    with pytest.raises(ValidationError, match="derived gain limits must be finite"):
        make_criteria(
            target_gain=1e308,
            gain_absolute_tolerance=1e308,
        )


@pytest.mark.parametrize(
    "field",
    ["gain_absolute_tolerance", "max_abs_offset", "max_rmse"],
)
def test_acceptance_criteria_rejects_negative_limits(field: str) -> None:
    with pytest.raises(ValidationError, match="cannot be negative"):
        make_criteria(**{field: -0.1})


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_acceptance_criteria_rejects_r_squared_outside_unit_interval(
    value: float,
) -> None:
    with pytest.raises(ValidationError, match="between zero and one"):
        make_criteria(min_r_squared=value)


@pytest.mark.parametrize("value", [True, 1, 2.5, "3"])
def test_acceptance_criteria_rejects_bad_minimum_points(value: object) -> None:
    with pytest.raises(ValidationError, match="integer of at least two"):
        make_criteria(minimum_included_points=value)


def test_acceptance_criteria_rejects_bad_unit_and_schema() -> None:
    with pytest.raises(ValidationError, match="normalized_unit must be V or mV"):
        make_criteria(normalized_unit=MeasurementUnit.AMPERE)
    with pytest.raises(ValidationError, match="normalized_unit must be V or mV"):
        make_criteria(normalized_unit="mV")
    with pytest.raises(ValidationError, match="unsupported DC sweep criteria"):
        make_criteria(schema_version="dc-sweep-criteria.v2")


@pytest.mark.parametrize(
    ("lower", "upper", "actual", "passed"),
    [
        (1.0, None, 1.0, True),
        (1.0, None, 0.9, False),
        (None, 1.0, 1.0, True),
        (None, 1.0, 1.1, False),
        (1.0, 2.0, 1.5, True),
        (1.0, 2.0, 2.1, False),
    ],
)
def test_criterion_result_uses_inclusive_limits(
    lower: float | None,
    upper: float | None,
    actual: float,
    passed: bool,
) -> None:
    result = DCSweepCriterionResult(
        DCSweepCriterionName.GAIN,
        actual,
        "ratio",
        passed,
        lower_limit=lower,
        upper_limit=upper,
    )

    assert result.actual_value == actual
    assert result.passed is passed
    with pytest.raises(FrozenInstanceError):
        result.passed = not passed  # type: ignore[misc]


def test_criterion_result_rejects_wrong_name_actual_unit_or_pass_type() -> None:
    with pytest.raises(ValidationError, match="DCSweepCriterionName"):
        DCSweepCriterionResult(
            cast(DCSweepCriterionName, "GAIN"),
            2.0,
            "ratio",
            True,
            lower_limit=1.0,
        )
    with pytest.raises(ValidationError, match="actual_value must be numeric"):
        DCSweepCriterionResult(
            DCSweepCriterionName.GAIN,
            True,
            "ratio",
            True,
            lower_limit=1.0,
        )
    with pytest.raises(ValidationError, match="actual_value must be finite"):
        DCSweepCriterionResult(
            DCSweepCriterionName.GAIN,
            math.inf,
            "ratio",
            True,
            lower_limit=1.0,
        )
    with pytest.raises(ValidationError, match="unit"):
        DCSweepCriterionResult(
            DCSweepCriterionName.GAIN,
            2.0,
            " ratio",
            True,
            lower_limit=1.0,
        )
    with pytest.raises(ValidationError, match="not valid for GAIN"):
        DCSweepCriterionResult(
            DCSweepCriterionName.GAIN,
            2.0,
            "mV",
            True,
            lower_limit=1.0,
        )
    with pytest.raises(ValidationError, match="passed must be a bool"):
        DCSweepCriterionResult(
            DCSweepCriterionName.GAIN,
            2.0,
            "ratio",
            cast(bool, 1),
            lower_limit=1.0,
        )


def test_criterion_result_rejects_bad_limits_and_inconsistent_pass() -> None:
    with pytest.raises(ValidationError, match="lower_limit must be numeric"):
        DCSweepCriterionResult(
            DCSweepCriterionName.GAIN,
            2.0,
            "ratio",
            True,
            lower_limit=True,
        )
    with pytest.raises(ValidationError, match="upper_limit must be finite"):
        DCSweepCriterionResult(
            DCSweepCriterionName.GAIN,
            2.0,
            "ratio",
            True,
            upper_limit=math.nan,
        )
    with pytest.raises(ValidationError, match="at least one"):
        DCSweepCriterionResult(
            DCSweepCriterionName.GAIN,
            2.0,
            "ratio",
            True,
        )
    with pytest.raises(ValidationError, match="cannot exceed"):
        DCSweepCriterionResult(
            DCSweepCriterionName.GAIN,
            2.0,
            "ratio",
            True,
            lower_limit=3.0,
            upper_limit=1.0,
        )
    with pytest.raises(ValidationError, match="must agree"):
        DCSweepCriterionResult(
            DCSweepCriterionName.GAIN,
            2.0,
            "ratio",
            False,
            lower_limit=1.0,
        )
    with pytest.raises(ValidationError, match="unsupported DC sweep evaluation"):
        DCSweepCriterionResult(
            DCSweepCriterionName.GAIN,
            2.0,
            "ratio",
            True,
            lower_limit=1.0,
            schema_version="dc-sweep-evaluation.v2",
        )


def test_exact_fit_maps_to_evidence_backed_pass_with_five_checks() -> None:
    evaluation = passing_evaluation()
    test_run = evaluation.test_run_result

    assert evaluation.is_conclusive
    assert evaluation.passed_criteria == 5
    assert evaluation.failed_criteria == 0
    assert test_run.outcome is RunOutcome.PASS
    assert test_run.is_pass
    assert test_run.summary == "DC sweep criteria passed"
    assert test_run.evidence_record_ids == evidence_ids(evaluation.analysis)
    assert test_run.missing_requirements == ()
    assert tuple(result.criterion for result in evaluation.criterion_results) == (
        DCSweepCriterionName.GAIN,
        DCSweepCriterionName.ABS_OFFSET,
        DCSweepCriterionName.R_SQUARED,
        DCSweepCriterionName.RMSE,
        DCSweepCriterionName.INCLUDED_POINTS,
    )

    gain, offset, r_squared, rmse, points = evaluation.criterion_results
    assert (gain.actual_value, gain.lower_limit, gain.upper_limit, gain.unit) == (
        2.0,
        1.95,
        2.05,
        "ratio",
    )
    assert (offset.actual_value, offset.upper_limit, offset.unit) == (
        12.0,
        20.0,
        "mV",
    )
    assert (r_squared.actual_value, r_squared.lower_limit, r_squared.unit) == (
        1.0,
        0.99,
        "ratio",
    )
    assert (rmse.actual_value, rmse.upper_limit, rmse.unit) == (0.0, 5.0, "mV")
    assert (points.actual_value, points.lower_limit, points.unit) == (
        4.0,
        3.0,
        "points",
    )


def test_exact_inclusive_criteria_boundaries_pass() -> None:
    analysis = exact_analysis()
    criteria = make_criteria(
        gain_absolute_tolerance=0.0,
        max_abs_offset=12.0,
        min_r_squared=1.0,
        max_rmse=0.0,
        minimum_included_points=4,
    )

    evaluation = evaluate_dc_sweep(analysis, criteria, make_metadata(analysis))

    assert evaluation.test_run_result.outcome is RunOutcome.PASS
    assert all(result.passed for result in evaluation.criterion_results)


def test_out_of_tolerance_complete_data_maps_to_fail_with_exact_checks() -> None:
    analysis = make_analysis(
        [100.0, 200.0, 300.0, 400.0, 500.0],
        [211.0, 415.0, 608.0, 818.0, 1005.0],
    )
    criteria = make_criteria(
        target_gain=2.1,
        gain_absolute_tolerance=0.01,
        max_abs_offset=10.0,
        min_r_squared=1.0,
        max_rmse=0.0,
        minimum_included_points=5,
    )

    evaluation = evaluate_dc_sweep(analysis, criteria, make_metadata(analysis))
    failed = {
        result.criterion
        for result in evaluation.criterion_results
        if not result.passed
    }

    assert evaluation.is_conclusive
    assert evaluation.test_run_result.outcome is RunOutcome.FAIL
    assert not evaluation.test_run_result.is_pass
    assert evaluation.test_run_result.summary == "DC sweep criteria failed"
    assert evaluation.passed_criteria == 1
    assert evaluation.failed_criteria == 4
    assert failed == {
        DCSweepCriterionName.GAIN,
        DCSweepCriterionName.ABS_OFFSET,
        DCSweepCriterionName.R_SQUARED,
        DCSweepCriterionName.RMSE,
    }


def test_offset_criterion_uses_absolute_value() -> None:
    analysis = make_analysis(
        [100.0, 200.0, 300.0],
        [188.0, 388.0, 588.0],
    )
    evaluation = evaluate_dc_sweep(
        analysis,
        make_criteria(max_abs_offset=10.0),
        make_metadata(analysis),
    )
    offset = evaluation.criterion_results[1]

    assert analysis.fit is not None
    assert analysis.fit.offset == pytest.approx(-12.0)
    assert offset.actual_value == pytest.approx(12.0)
    assert not offset.passed


def test_incomplete_analysis_never_evaluates_performance_criteria() -> None:
    analysis = make_analysis(
        [100.0, 100.0],
        [200.0, 200.0],
    )

    evaluation = evaluate_dc_sweep(
        analysis,
        make_criteria(),
        make_metadata(analysis),
    )

    assert not evaluation.is_conclusive
    assert evaluation.passed_criteria == 0
    assert evaluation.failed_criteria == 0
    assert evaluation.criterion_results == ()
    assert evaluation.test_run_result.outcome is RunOutcome.INCOMPLETE
    assert evaluation.test_run_result.missing_requirements == (
        "analysis:included-points:2/3",
        "analysis:distinct-input-values:1/2",
    )


def test_missing_criteria_never_becomes_pass() -> None:
    analysis = exact_analysis()

    evaluation = evaluate_dc_sweep(analysis, None, make_metadata(analysis))

    assert not evaluation.is_conclusive
    assert evaluation.criteria is None
    assert evaluation.criterion_results == ()
    assert evaluation.test_run_result.outcome is RunOutcome.INCOMPLETE
    assert evaluation.test_run_result.missing_requirements == (
        "acceptance-criteria",
    )


def test_missing_criteria_and_analysis_gaps_are_both_reported() -> None:
    analysis = make_analysis([100.0], [200.0])

    evaluation = evaluate_dc_sweep(analysis, None, make_metadata(analysis))

    assert evaluation.test_run_result.missing_requirements == (
        "acceptance-criteria",
        "analysis:included-points:1/3",
        "analysis:distinct-input-values:1/2",
    )


def test_criteria_point_shortage_is_incomplete_not_fail() -> None:
    analysis = exact_analysis()
    criteria = make_criteria(minimum_included_points=5)

    evaluation = evaluate_dc_sweep(analysis, criteria, make_metadata(analysis))

    assert not evaluation.is_conclusive
    assert evaluation.criterion_results == ()
    assert evaluation.test_run_result.outcome is RunOutcome.INCOMPLETE
    assert evaluation.test_run_result.missing_requirements == (
        "criteria-included-points:4/5",
    )


def test_volt_criteria_and_analysis_preserve_explicit_unit() -> None:
    analysis = exact_analysis(unit=MeasurementUnit.VOLT)
    criteria = make_criteria(
        max_abs_offset=0.02,
        max_rmse=0.005,
        normalized_unit=MeasurementUnit.VOLT,
    )

    evaluation = evaluate_dc_sweep(analysis, criteria, make_metadata(analysis))

    assert evaluation.test_run_result.outcome is RunOutcome.PASS
    assert evaluation.criterion_results[1].unit == "V"
    assert evaluation.criterion_results[3].unit == "V"


def test_criteria_unit_must_match_analysis_config() -> None:
    analysis = exact_analysis()
    criteria = make_criteria(normalized_unit=MeasurementUnit.VOLT)
    with pytest.raises(ValidationError, match="criteria unit must match"):
        evaluate_dc_sweep(analysis, criteria, make_metadata(analysis))


def test_metadata_must_match_test_type_source_and_raw_records() -> None:
    analysis = exact_analysis()
    criteria = make_criteria()
    with pytest.raises(ValidationError, match="test_type must be dc-sweep"):
        evaluate_dc_sweep(
            analysis,
            criteria,
            make_metadata(analysis, test_type="hysteresis"),
        )
    with pytest.raises(ValidationError, match="evidence source must match"):
        evaluate_dc_sweep(
            analysis,
            criteria,
            make_metadata(analysis, evidence_source=EvidenceSource.CSV_REPLAY),
        )
    with pytest.raises(ValidationError, match="input_record_ids must match"):
        evaluate_dc_sweep(
            analysis,
            criteria,
            make_metadata(analysis, input_record_ids=("wrong",)),
        )


def test_repeated_raw_reference_is_deduplicated_in_metadata_only() -> None:
    analysis = make_analysis(
        [100.0, 200.0, 300.0],
        [212.0, 412.0, 612.0],
        shared_raw_id="raw-capture-1",
    )
    metadata = make_metadata(analysis)

    evaluation = evaluate_dc_sweep(analysis, make_criteria(), metadata)

    assert metadata.input_record_ids == ("raw-capture-1",)
    assert evaluation.test_run_result.evidence_record_ids == evidence_ids(analysis)
    assert len(evaluation.test_run_result.evidence_record_ids) == 6


def test_evaluator_rejects_wrong_argument_types() -> None:
    analysis = exact_analysis()
    metadata = make_metadata(analysis)
    with pytest.raises(ValidationError, match="analysis must"):
        evaluate_dc_sweep(cast(DCSweepAnalysisResult, object()), make_criteria(), metadata)
    with pytest.raises(ValidationError, match="criteria must"):
        evaluate_dc_sweep(analysis, cast(DCSweepAcceptanceCriteria, object()), metadata)
    with pytest.raises(ValidationError, match="metadata must"):
        evaluate_dc_sweep(analysis, make_criteria(), cast(RunMetadata, object()))


def test_evaluator_rejects_duplicate_analysis_record_ids() -> None:
    analysis = exact_analysis()
    first = analysis.points[0]
    second = analysis.points[1]
    duplicate_second = replace(
        second,
        input_decision=replace(
            second.input_decision,
            reference=replace(
                second.input_decision.reference,
                record_id=first.input_decision.reference.record_id,
            ),
        ),
    )
    malformed = replace(
        analysis,
        points=(first, duplicate_second, *analysis.points[2:]),
    )
    metadata = make_metadata(malformed)

    with pytest.raises(ValidationError, match="record IDs must be unique"):
        evaluate_dc_sweep(malformed, make_criteria(), metadata)


def test_evaluation_result_freezes_a_mutable_result_collection() -> None:
    evaluation = passing_evaluation()
    mutable = list(evaluation.criterion_results)
    rebuilt = DCSweepEvaluationResult(
        evaluation.analysis,
        evaluation.criteria,
        cast(tuple[DCSweepCriterionResult, ...], mutable),
        evaluation.test_run_result,
    )
    mutable.clear()

    assert len(rebuilt.criterion_results) == 5
    with pytest.raises(FrozenInstanceError):
        rebuilt.criteria = None  # type: ignore[misc]


def test_evaluation_result_rejects_wrong_model_types_and_collections() -> None:
    evaluation = passing_evaluation()
    with pytest.raises(ValidationError, match="analysis must"):
        replace(evaluation, analysis=object())  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="criteria must"):
        replace(evaluation, criteria=object())  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="criterion_results must be an iterable"):
        replace(evaluation, criterion_results=None)  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="must contain"):
        replace(evaluation, criterion_results=(object(),))  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="test_run_result must"):
        replace(evaluation, test_run_result=object())  # type: ignore[arg-type]


def test_evaluation_result_rejects_mismatched_criteria_results() -> None:
    evaluation = passing_evaluation()
    with pytest.raises(ValidationError, match="must match analysis and criteria"):
        replace(evaluation, criterion_results=evaluation.criterion_results[:-1])


def test_evaluation_result_rejects_mismatched_outcome_summary_and_evidence() -> None:
    evaluation = passing_evaluation()
    run = evaluation.test_run_result
    with pytest.raises(ValidationError, match="outcome must match"):
        replace(
            evaluation,
            test_run_result=RunResult(
                run.metadata,
                RunOutcome.FAIL,
                "DC sweep criteria passed",
                evidence_record_ids=run.evidence_record_ids,
            ),
        )
    with pytest.raises(ValidationError, match="summary must match"):
        replace(
            evaluation,
            test_run_result=replace(run, summary="wrong summary"),
        )
    with pytest.raises(ValidationError, match="evidence_record_ids must match"):
        replace(
            evaluation,
            test_run_result=replace(
                run,
                evidence_record_ids=run.evidence_record_ids[:-1],
            ),
        )


def test_evaluation_result_rejects_mismatched_missing_requirements() -> None:
    analysis = exact_analysis()
    evaluation = evaluate_dc_sweep(analysis, None, make_metadata(analysis))
    run = evaluation.test_run_result

    with pytest.raises(ValidationError, match="missing_requirements must match"):
        replace(
            evaluation,
            test_run_result=replace(
                run,
                missing_requirements=("different-gap",),
            ),
        )


def test_evaluation_result_revalidates_metadata_and_schema() -> None:
    evaluation = passing_evaluation()
    wrong_metadata = replace(evaluation.test_run_result.metadata, test_type="other")
    with pytest.raises(ValidationError, match="test_type must be dc-sweep"):
        replace(
            evaluation,
            test_run_result=replace(
                evaluation.test_run_result,
                metadata=wrong_metadata,
            ),
        )
    with pytest.raises(ValidationError, match="unsupported DC sweep evaluation"):
        replace(evaluation, schema_version="dc-sweep-evaluation.v2")
