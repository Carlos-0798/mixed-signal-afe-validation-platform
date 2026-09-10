"""Tests for calibration criteria, TestRun mapping, and result export."""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest

from analog_validation.analysis import (
    CALIBRATION_TEST_TYPE,
    CalibrationAcceptanceCriteria,
    CalibrationCriterionName,
    CalibrationCriterionResult,
    CalibrationFitConfig,
    CalibrationFitResult,
    MeasurementBatch,
    evaluate_calibration,
    fit_linear_calibration,
)
from analog_validation.domain import (
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
)
from analog_validation.domain import (
    TestRunMetadata as RunMetadata,
)
from analog_validation.domain import (
    TestRunOutcome as RunOutcome,
)
from analog_validation.errors import ValidationError
from analog_validation.exports import (
    build_calibration_export,
    dump_result_export_csv,
    dump_result_export_json,
    parse_result_export_csv,
    parse_result_export_json,
)

NOW = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)


def _batch(prefix: str, channel: str, values: tuple[float, ...]) -> MeasurementBatch:
    return MeasurementBatch(
        tuple(
            Measurement(
                f"{prefix}-{index}",
                f"raw-{prefix}-{index}",
                NOW + timedelta(milliseconds=index),
                channel,
                value,
                MeasurementUnit.MILLIVOLT,
                MeasurementStatus.VALID,
                EvidenceSource.HOST_TEST,
            )
            for index, value in enumerate(values)
        )
    )


def _analysis(
    observed: tuple[float, ...] = (0.0, 50.0, 100.0),
    reference: tuple[float, ...] = (10.0, 110.0, 210.0),
    *,
    minimum: int = 3,
) -> CalibrationFitResult:
    return fit_linear_calibration(
        _batch("observed", "adc.raw", observed),
        _batch("reference", "dmm.reference", reference),
        CalibrationFitConfig(
            "adc.raw",
            "dmm.reference",
            "adc-linear",
            "1",
            minimum_included_points=minimum,
        ),
    )


def _raw_ids(analysis: CalibrationFitResult) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            reference.raw_record_id
            for point in analysis.points
            for reference in (
                point.observed_decision.reference,
                point.reference_decision.reference,
            )
        )
    )


def _metadata(analysis: CalibrationFitResult, **overrides: Any) -> RunMetadata:
    values: dict[str, Any] = {
        "run_id": "calibration-run",
        "test_type": CALIBRATION_TEST_TYPE,
        "configuration_id": "product-calibration",
        "configuration_version": "1",
        "started_at": NOW,
        "ended_at": NOW + timedelta(seconds=1),
        "software_version": "0.1.0b1",
        "device_id": "host-fixture",
        "profile_name": "afe",
        "profile_version": "1",
        "evidence_source": analysis.observed_source,
        "input_record_ids": _raw_ids(analysis),
    }
    values.update(overrides)
    return RunMetadata(**values)


def _criteria(**overrides: Any) -> CalibrationAcceptanceCriteria:
    values: dict[str, Any] = {
        "criteria_id": "calibration-default",
        "criteria_version": "1",
        "max_after_rmse": 1.0,
        "max_after_mean_absolute_error": 1.0,
        "max_after_max_absolute_error": 2.0,
        "minimum_rmse_reduction": 0.0,
        "minimum_included_points": 3,
    }
    values.update(overrides)
    return CalibrationAcceptanceCriteria(**values)


def test_calibration_evaluation_passes_and_preserves_exact_evidence() -> None:
    analysis = _analysis()
    result = evaluate_calibration(analysis, _criteria(), _metadata(analysis))

    assert result.is_conclusive
    assert result.passed_criteria == 5
    assert result.failed_criteria == 0
    assert result.test_run_result.outcome is RunOutcome.PASS
    assert tuple(value.criterion for value in result.criterion_results) == tuple(
        CalibrationCriterionName
    )
    assert result.test_run_result.evidence_record_ids == tuple(
        reference.record_id
        for point in analysis.points
        for reference in (
            point.observed_decision.reference,
            point.reference_decision.reference,
        )
    )


def test_calibration_evaluation_can_fail_without_changing_evidence() -> None:
    analysis = _analysis(
        (0.0, 50.0, 100.0, 150.0),
        (10.0, 111.0, 209.0, 311.0),
    )
    result = evaluate_calibration(
        analysis,
        _criteria(
            max_after_rmse=0.01,
            max_after_mean_absolute_error=0.01,
            max_after_max_absolute_error=0.01,
        ),
        _metadata(analysis),
    )

    assert result.test_run_result.outcome is RunOutcome.FAIL
    assert result.failed_criteria >= 1
    assert result.test_run_result.missing_requirements == ()


def test_calibration_incomplete_paths_do_not_publish_criteria_results() -> None:
    incomplete = _analysis((0.0, 50.0), (10.0, 110.0))
    missing_data = evaluate_calibration(incomplete, _criteria(), _metadata(incomplete))
    assert missing_data.test_run_result.outcome is RunOutcome.INCOMPLETE
    assert missing_data.criterion_results == ()
    assert missing_data.test_run_result.missing_requirements == (
        "analysis:included-points:2/3",
    )

    complete = _analysis((0.0, 50.0), (10.0, 110.0), minimum=2)
    missing_criteria = evaluate_calibration(complete, None, _metadata(complete))
    assert missing_criteria.test_run_result.missing_requirements == (
        "acceptance-criteria",
    )
    too_few_for_criteria = evaluate_calibration(
        complete, _criteria(), _metadata(complete)
    )
    assert too_few_for_criteria.test_run_result.missing_requirements == (
        "criteria-included-points:2/3",
    )


def test_calibration_result_export_round_trips_json_and_csv() -> None:
    analysis = _analysis()
    evaluation = evaluate_calibration(analysis, _criteria(), _metadata(analysis))
    bundle = build_calibration_export(
        evaluation,
        ("Host-test calibration fixture only; no physical AFE was calibrated.",),
    )

    metrics = {value.name: value.value for value in bundle.metrics}
    assert metrics["coefficient_id"] == "adc-linear"
    assert metrics["scale"] == pytest.approx(2.0)
    before_rmse = metrics["before_rmse"]
    after_rmse = metrics["after_rmse"]
    assert isinstance(before_rmse, (int, float)) and not isinstance(before_rmse, bool)
    assert isinstance(after_rmse, (int, float)) and not isinstance(after_rmse, bool)
    assert before_rmse > after_rmse
    assert bundle.points[0].label == "calibration-point-0"
    assert [value.name for value in bundle.points[0].values] == [
        "observed",
        "reference",
        "calibrated",
        "before_error",
        "after_error",
    ]
    assert parse_result_export_json(dump_result_export_json(bundle)) == bundle
    assert parse_result_export_csv(dump_result_export_csv(bundle)) == bundle


def test_calibration_mapping_rejects_cross_source_and_metadata_mismatch() -> None:
    analysis = _analysis()
    reference = tuple(
        replace(measurement, source=EvidenceSource.BENCH_DMM)
        for measurement in _batch(
            "reference-other", "dmm.reference", (10.0, 110.0, 210.0)
        ).measurements
    )
    cross_source = fit_linear_calibration(
        _batch("observed-other", "adc.raw", (0.0, 50.0, 100.0)),
        MeasurementBatch(reference),
        analysis.config,
    )
    with pytest.raises(ValidationError, match="one evidence source"):
        evaluate_calibration(cross_source, _criteria(), _metadata(analysis))
    with pytest.raises(ValidationError, match="test_type"):
        evaluate_calibration(
            analysis, _criteria(), _metadata(analysis, test_type="wrong")
        )
    with pytest.raises(ValidationError, match="evidence source"):
        evaluate_calibration(
            analysis,
            _criteria(),
            _metadata(analysis, evidence_source=EvidenceSource.CSV_REPLAY),
        )
    with pytest.raises(ValidationError, match="input_record_ids"):
        evaluate_calibration(
            analysis, _criteria(), _metadata(analysis, input_record_ids=("wrong",))
        )


def test_calibration_mapping_rejects_unit_mismatch_and_duplicate_evidence() -> None:
    analysis = _analysis()
    with pytest.raises(ValidationError, match="criteria unit"):
        evaluate_calibration(
            analysis,
            replace(_criteria(), normalized_unit=MeasurementUnit.VOLT),
            _metadata(analysis),
        )

    first, second, third = analysis.points
    duplicate_second = replace(
        second,
        observed_decision=replace(
            second.observed_decision,
            reference=replace(
                second.observed_decision.reference,
                record_id=first.observed_decision.reference.record_id,
            ),
        ),
    )
    malformed = replace(analysis, points=(first, duplicate_second, third))
    with pytest.raises(ValidationError, match="record IDs must be unique"):
        evaluate_calibration(malformed, _criteria(), _metadata(malformed))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"criteria_id": ""}, "non-empty"),
        ({"max_after_rmse": True}, "numeric"),
        ({"max_after_rmse": -1}, "negative"),
        ({"minimum_rmse_reduction": float("inf")}, "finite"),
        ({"minimum_included_points": 1}, "at least two"),
        ({"normalized_unit": MeasurementUnit.HERTZ}, "V or mV"),
        ({"schema_version": "wrong"}, "unsupported"),
    ],
)
def test_calibration_criteria_validation(changes: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        _criteria(**changes)


def test_calibration_criterion_result_and_evaluation_are_self_consistent() -> None:
    with pytest.raises(ValidationError, match="agree"):
        CalibrationCriterionResult(
            CalibrationCriterionName.AFTER_RMSE,
            2.0,
            "mV",
            True,
            upper_limit=1.0,
        )
    analysis = _analysis()
    valid = evaluate_calibration(analysis, _criteria(), _metadata(analysis))
    with pytest.raises(ValidationError, match="criterion_results"):
        replace(valid, criterion_results=())
    with pytest.raises(ValidationError, match="schema"):
        replace(valid, schema_version="wrong")
    with pytest.raises(ValidationError, match="CalibrationFitResult"):
        evaluate_calibration(object(), _criteria(), _metadata(analysis))  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="CalibrationEvaluationResult"):
        build_calibration_export(object(), ("limitation",))  # type: ignore[arg-type]


def test_calibration_criterion_result_rejects_invalid_contract_values() -> None:
    with pytest.raises(ValidationError, match="CalibrationCriterionName"):
        CalibrationCriterionResult(
            cast(CalibrationCriterionName, "AFTER_RMSE"),
            0.0,
            "mV",
            True,
            upper_limit=1.0,
        )
    with pytest.raises(ValidationError, match="actual_value must be numeric"):
        CalibrationCriterionResult(
            CalibrationCriterionName.AFTER_RMSE,
            True,
            "mV",
            True,
            upper_limit=1.0,
        )
    with pytest.raises(ValidationError, match="actual_value must be finite"):
        CalibrationCriterionResult(
            CalibrationCriterionName.AFTER_RMSE,
            math.inf,
            "mV",
            True,
            upper_limit=1.0,
        )
    with pytest.raises(ValidationError, match="unit"):
        CalibrationCriterionResult(
            CalibrationCriterionName.AFTER_RMSE,
            0.0,
            " mV",
            True,
            upper_limit=1.0,
        )
    with pytest.raises(ValidationError, match="not valid"):
        CalibrationCriterionResult(
            CalibrationCriterionName.AFTER_RMSE,
            0.0,
            "points",
            True,
            upper_limit=1.0,
        )
    with pytest.raises(ValidationError, match="passed must be a bool"):
        CalibrationCriterionResult(
            CalibrationCriterionName.AFTER_RMSE,
            0.0,
            "mV",
            cast(bool, 1),
            upper_limit=1.0,
        )
    with pytest.raises(ValidationError, match="at least one"):
        CalibrationCriterionResult(
            CalibrationCriterionName.AFTER_RMSE,
            0.0,
            "mV",
            True,
        )
    with pytest.raises(ValidationError, match="cannot exceed"):
        CalibrationCriterionResult(
            CalibrationCriterionName.RMSE_REDUCTION,
            2.0,
            "mV",
            True,
            lower_limit=3.0,
            upper_limit=1.0,
        )
    with pytest.raises(ValidationError, match="unsupported calibration evaluation"):
        CalibrationCriterionResult(
            CalibrationCriterionName.AFTER_RMSE,
            0.0,
            "mV",
            True,
            upper_limit=1.0,
            schema_version="calibration-evaluation.v2",
        )


def test_calibration_evaluation_result_rejects_mismatched_contracts() -> None:
    analysis = _analysis()
    valid = evaluate_calibration(analysis, _criteria(), _metadata(analysis))
    run = valid.test_run_result

    with pytest.raises(ValidationError, match="analysis must"):
        replace(valid, analysis=object())  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="criteria must"):
        replace(valid, criteria=object())  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="criterion_results must be an iterable"):
        replace(valid, criterion_results=None)  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="must contain"):
        replace(valid, criterion_results=(object(),))  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="test_run_result must"):
        replace(valid, test_run_result=object())  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="outcome must match"):
        replace(valid, test_run_result=replace(run, outcome=RunOutcome.FAIL))
    with pytest.raises(ValidationError, match="summary must match"):
        replace(valid, test_run_result=replace(run, summary="wrong summary"))
    incomplete = evaluate_calibration(analysis, None, _metadata(analysis))
    with pytest.raises(ValidationError, match="missing_requirements must match"):
        replace(
            incomplete,
            test_run_result=replace(
                incomplete.test_run_result,
                missing_requirements=("wrong-gap",),
            ),
        )
    with pytest.raises(ValidationError, match="evidence_record_ids must match"):
        replace(
            valid,
            test_run_result=replace(
                run,
                evidence_record_ids=run.evidence_record_ids[:-1],
            ),
        )


def test_evaluate_calibration_rejects_wrong_criteria_and_metadata_types() -> None:
    analysis = _analysis()
    with pytest.raises(ValidationError, match="criteria must"):
        evaluate_calibration(
            analysis,
            object(),  # type: ignore[arg-type]
            _metadata(analysis),
        )
    with pytest.raises(ValidationError, match="TestRunMetadata"):
        evaluate_calibration(analysis, _criteria(), object())  # type: ignore[arg-type]
