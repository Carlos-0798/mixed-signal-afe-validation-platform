"""Tests for frequency-response criteria, TestRun mapping, and export."""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest

from analog_validation.analysis import (
    FREQUENCY_RESPONSE_TEST_TYPE,
    FrequencyResponseAcceptanceCriteria,
    FrequencyResponseAnalysisConfig,
    FrequencyResponseCriterionName,
    FrequencyResponseCriterionResult,
    MeasurementBatch,
    analyze_frequency_response,
    evaluate_frequency_response,
)
from analog_validation.domain import (
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
)
from analog_validation.domain import TestRunMetadata as RunMetadata
from analog_validation.domain import TestRunOutcome as RunOutcome
from analog_validation.errors import ValidationError
from analog_validation.exports import (
    build_frequency_response_export,
    dump_result_export_csv,
    dump_result_export_json,
    parse_result_export_csv,
    parse_result_export_json,
)

NOW = datetime(2026, 9, 5, 16, 0, tzinfo=timezone.utc)


def _batch(
    prefix: str,
    channel: str,
    values: tuple[float, ...],
    unit: MeasurementUnit,
) -> MeasurementBatch:
    return MeasurementBatch(
        tuple(
            Measurement(
                f"{prefix}-{index}",
                f"raw-{prefix}-{index}",
                NOW + timedelta(milliseconds=index),
                channel,
                value,
                unit,
                MeasurementStatus.VALID,
                EvidenceSource.SYNTHETIC,
            )
            for index, value in enumerate(values)
        )
    )


def _analysis(*, cutoff_hz: float = 1000.0, points: int = 13):
    frequencies = tuple(10.0 ** (1.0 + 4.0 * index / (points - 1)) for index in range(points))
    inputs = tuple(1000.0 for _ in frequencies)
    outputs = tuple(
        input_value / math.sqrt(1.0 + (frequency / cutoff_hz) ** 2)
        for frequency, input_value in zip(frequencies, inputs, strict=True)
    )
    return analyze_frequency_response(
        _batch("frequency", "afe.ch0.frequency", frequencies, MeasurementUnit.HERTZ),
        _batch("input", "afe.ch0.input", inputs, MeasurementUnit.MILLIVOLT),
        _batch("output", "afe.ch0.output", outputs, MeasurementUnit.MILLIVOLT),
        FrequencyResponseAnalysisConfig(
            "afe.ch0.frequency",
            "afe.ch0.input",
            "afe.ch0.output",
            minimum_included_points=2,
        ),
    )


def _raw_ids(analysis: Any) -> tuple[str, ...]:
    return tuple(
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


def _metadata(analysis: Any, **overrides: Any) -> RunMetadata:
    values: dict[str, Any] = {
        "run_id": "frequency-run",
        "test_type": FREQUENCY_RESPONSE_TEST_TYPE,
        "configuration_id": "product-frequency-response",
        "configuration_version": "1",
        "started_at": NOW,
        "ended_at": NOW + timedelta(seconds=1),
        "software_version": "0.1.0b1",
        "device_id": "synthetic-frequency-source",
        "profile_name": "afe",
        "profile_version": "1",
        "evidence_source": analysis.evidence_source,
        "input_record_ids": _raw_ids(analysis),
    }
    values.update(overrides)
    return RunMetadata(**values)


def _criteria(**overrides: Any) -> FrequencyResponseAcceptanceCriteria:
    values: dict[str, Any] = {
        "criteria_id": "frequency-default",
        "criteria_version": "1",
        "target_cutoff_frequency_hz": 1000.0,
        "cutoff_relative_tolerance": 0.15,
        "minimum_included_points": 10,
    }
    values.update(overrides)
    return FrequencyResponseAcceptanceCriteria(**values)


def test_frequency_response_evaluation_passes_with_traceable_cutoff() -> None:
    analysis = _analysis()
    result = evaluate_frequency_response(analysis, _criteria(), _metadata(analysis))

    assert result.is_conclusive
    assert result.passed_criteria == 2
    assert result.failed_criteria == 0
    assert result.test_run_result.outcome is RunOutcome.PASS
    assert tuple(value.criterion for value in result.criterion_results) == tuple(
        FrequencyResponseCriterionName
    )
    assert result.criterion_results[0].actual_value == pytest.approx(1000.0, rel=0.01)
    assert result.criterion_results[0].lower_limit == 850.0
    assert result.criterion_results[0].upper_limit == 1150.0


def test_frequency_response_can_fail_without_changing_evidence() -> None:
    analysis = _analysis()
    result = evaluate_frequency_response(
        analysis,
        _criteria(target_cutoff_frequency_hz=2000.0, cutoff_relative_tolerance=0.01),
        _metadata(analysis),
    )

    assert result.test_run_result.outcome is RunOutcome.FAIL
    assert result.failed_criteria == 1
    assert result.test_run_result.missing_requirements == ()


def test_frequency_response_incomplete_paths_never_publish_criteria_results() -> None:
    analysis = _analysis(points=5)
    too_few = evaluate_frequency_response(analysis, _criteria(), _metadata(analysis))
    assert too_few.test_run_result.outcome is RunOutcome.INCOMPLETE
    assert too_few.criterion_results == ()
    assert too_few.test_run_result.missing_requirements == (
        "criteria-included-points:5/10",
    )

    missing_criteria = evaluate_frequency_response(analysis, None, _metadata(analysis))
    assert missing_criteria.test_run_result.outcome is RunOutcome.INCOMPLETE
    assert missing_criteria.test_run_result.missing_requirements == (
        "acceptance-criteria",
    )

    frequencies = (10.0, 100.0, 1000.0)
    no_crossing = analyze_frequency_response(
        _batch("f", "frequency", frequencies, MeasurementUnit.HERTZ),
        _batch("i", "input", (1000.0,) * 3, MeasurementUnit.MILLIVOLT),
        _batch("o", "output", (1000.0, 950.0, 900.0), MeasurementUnit.MILLIVOLT),
        FrequencyResponseAnalysisConfig("frequency", "input", "output"),
    )
    incomplete = evaluate_frequency_response(
        no_crossing,
        _criteria(minimum_included_points=2),
        _metadata(no_crossing),
    )
    assert incomplete.test_run_result.missing_requirements == (
        "analysis:cutoff-crossing",
    )


def test_frequency_response_export_round_trips_json_and_csv() -> None:
    analysis = _analysis()
    evaluation = evaluate_frequency_response(analysis, _criteria(), _metadata(analysis))
    bundle = build_frequency_response_export(
        evaluation,
        ("Synthetic response only; no physical bandwidth was measured.",),
    )

    metrics = {value.name: value.value for value in bundle.metrics}
    assert metrics["cutoff_frequency"] == pytest.approx(1000.0, rel=0.01)
    assert metrics["target_cutoff_frequency"] == 1000.0
    relative_error = metrics["cutoff_relative_error"]
    assert isinstance(relative_error, float)
    assert relative_error < 0.01
    assert bundle.points[0].label == "frequency-point-0"
    assert [value.name for value in bundle.points[0].values] == [
        "frequency",
        "input_amplitude",
        "output_amplitude",
        "amplitude_ratio",
        "gain",
    ]
    assert parse_result_export_json(dump_result_export_json(bundle)) == bundle
    assert parse_result_export_csv(dump_result_export_csv(bundle)) == bundle


@pytest.mark.parametrize(
    "overrides",
    [
        {"criteria_id": ""},
        {"target_cutoff_frequency_hz": True},
        {"target_cutoff_frequency_hz": 0.0},
        {"cutoff_relative_tolerance": -0.1},
        {"cutoff_relative_tolerance": 1.0},
        {"minimum_included_points": True},
        {"minimum_included_points": 1},
        {"schema_version": "future"},
    ],
)
def test_frequency_response_criteria_validation(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _criteria(**overrides)


def test_frequency_response_evaluation_models_reject_inconsistent_state() -> None:
    analysis = _analysis()
    criteria = _criteria()
    result = evaluate_frequency_response(analysis, criteria, _metadata(analysis))
    criterion = result.criterion_results[0]

    with pytest.raises(ValidationError):
        replace(criterion, passed=not criterion.passed)
    with pytest.raises(ValidationError):
        FrequencyResponseCriterionResult(
            FrequencyResponseCriterionName.CUTOFF_FREQUENCY,
            1000.0,
            "points",
            True,
            900.0,
            1100.0,
        )
    with pytest.raises(ValidationError):
        evaluate_frequency_response(
            analysis,
            criteria,
            _metadata(analysis, test_type="dc-sweep"),
        )
    with pytest.raises(ValidationError):
        replace(result, criterion_results=())
    with pytest.raises(ValidationError):
        replace(result, schema_version="future")


def test_frequency_response_criterion_result_rejects_malformed_contracts() -> None:
    valid = FrequencyResponseCriterionResult(
        FrequencyResponseCriterionName.CUTOFF_FREQUENCY,
        1000.0,
        "Hz",
        True,
        900.0,
        1100.0,
    )

    invalid_constructors = (
        lambda: FrequencyResponseCriterionResult(
            cast(Any, "CUTOFF_FREQUENCY"), 1000.0, "Hz", True, 900.0, 1100.0
        ),
        lambda: FrequencyResponseCriterionResult(
            FrequencyResponseCriterionName.CUTOFF_FREQUENCY,
            math.inf,
            "Hz",
            True,
            900.0,
            1100.0,
        ),
        lambda: FrequencyResponseCriterionResult(
            FrequencyResponseCriterionName.CUTOFF_FREQUENCY,
            1000.0,
            "Hz",
            cast(Any, 1),
            900.0,
            1100.0,
        ),
        lambda: FrequencyResponseCriterionResult(
            FrequencyResponseCriterionName.CUTOFF_FREQUENCY,
            1000.0,
            "Hz",
            True,
        ),
        lambda: FrequencyResponseCriterionResult(
            FrequencyResponseCriterionName.CUTOFF_FREQUENCY,
            1000.0,
            "Hz",
            False,
            1100.0,
            900.0,
        ),
        lambda: replace(valid, schema_version="future"),
    )
    for construct in invalid_constructors:
        with pytest.raises(ValidationError):
            construct()


def test_frequency_response_evaluation_rejects_invalid_types_and_lineage() -> None:
    analysis = _analysis()
    criteria = _criteria()
    result = evaluate_frequency_response(analysis, criteria, _metadata(analysis))

    for invalid_analysis, invalid_criteria, invalid_metadata in (
        (object(), criteria, _metadata(analysis)),
        (analysis, object(), _metadata(analysis)),
        (analysis, criteria, object()),
    ):
        with pytest.raises(ValidationError):
            evaluate_frequency_response(
                cast(Any, invalid_analysis),
                cast(Any, invalid_criteria),
                cast(Any, invalid_metadata),
            )

    with pytest.raises(ValidationError, match="evidence source"):
        evaluate_frequency_response(
            analysis,
            criteria,
            _metadata(analysis, evidence_source=EvidenceSource.HOST_TEST),
        )
    with pytest.raises(ValidationError, match="input_record_ids"):
        evaluate_frequency_response(
            analysis,
            criteria,
            _metadata(analysis, input_record_ids=("different-raw-record",)),
        )

    invalid_results = (
        lambda: replace(result, analysis=cast(Any, object())),
        lambda: replace(result, criteria=cast(Any, object())),
        lambda: replace(
            result, criterion_results=cast(Any, "not-an-iterable-contract")
        ),
        lambda: replace(result, criterion_results=cast(Any, (object(),))),
        lambda: replace(result, test_run_result=cast(Any, object())),
    )
    for construct in invalid_results:
        with pytest.raises(ValidationError):
            construct()


def test_frequency_response_evaluation_rejects_tampered_conclusion_and_ids() -> None:
    analysis = _analysis()
    criteria = _criteria()
    result = evaluate_frequency_response(analysis, criteria, _metadata(analysis))

    with pytest.raises(ValidationError, match="conclusion"):
        replace(
            result,
            test_run_result=replace(
                result.test_run_result,
                summary="Tampered frequency-response conclusion",
            ),
        )
    with pytest.raises(ValidationError, match="evidence IDs"):
        replace(
            result,
            test_run_result=replace(
                result.test_run_result,
                evidence_record_ids=result.test_run_result.evidence_record_ids[:-1],
            ),
        )

    first, second, *remaining = analysis.points
    duplicate_frequency = replace(
        first.frequency_decision,
        reference=second.frequency_decision.reference,
    )
    duplicate_analysis = replace(
        analysis,
        points=(
            replace(first, frequency_decision=duplicate_frequency),
            second,
            *remaining,
        ),
    )
    with pytest.raises(ValidationError, match="record IDs must be unique"):
        evaluate_frequency_response(
            duplicate_analysis,
            criteria,
            _metadata(duplicate_analysis),
        )


def test_frequency_response_export_rejects_non_evaluation() -> None:
    with pytest.raises(ValidationError, match="FrequencyResponseEvaluationResult"):
        build_frequency_response_export(cast(Any, object()), ())
