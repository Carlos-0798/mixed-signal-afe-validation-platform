"""Versioned frequency-response criteria and safe TestRun mapping."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from analog_validation.domain import TestRunMetadata, TestRunOutcome, TestRunResult
from analog_validation.errors import ValidationError

from .frequency_response import FrequencyResponseAnalysisResult

FREQUENCY_RESPONSE_CRITERIA_SCHEMA_VERSION = "frequency-response-criteria.v1"
FREQUENCY_RESPONSE_EVALUATION_SCHEMA_VERSION = "frequency-response-evaluation.v1"
FREQUENCY_RESPONSE_TEST_TYPE = "frequency-response"


class FrequencyResponseCriterionName(str, Enum):
    """Stable checks evaluated only after cutoff analysis is complete."""

    CUTOFF_FREQUENCY = "CUTOFF_FREQUENCY"
    INCLUDED_POINTS = "INCLUDED_POINTS"


def _identifier(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValidationError(f"{name} must be a non-empty stripped string")
    return value


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValidationError(f"{name} must be finite")
    return number


@dataclass(frozen=True, slots=True)
class FrequencyResponseAcceptanceCriteria:
    """Inclusive cutoff-frequency tolerance and minimum evidence size."""

    criteria_id: str
    criteria_version: str
    target_cutoff_frequency_hz: float
    cutoff_relative_tolerance: float
    minimum_included_points: int = 10
    schema_version: str = FREQUENCY_RESPONSE_CRITERIA_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _identifier("criteria_id", self.criteria_id)
        _identifier("criteria_version", self.criteria_version)
        target = _finite("target_cutoff_frequency_hz", self.target_cutoff_frequency_hz)
        if target <= 0:
            raise ValidationError("target_cutoff_frequency_hz must be positive")
        tolerance = _finite("cutoff_relative_tolerance", self.cutoff_relative_tolerance)
        if not 0.0 <= tolerance < 1.0:
            raise ValidationError(
                "cutoff_relative_tolerance must be at least zero and below one"
            )
        if (
            isinstance(self.minimum_included_points, bool)
            or not isinstance(self.minimum_included_points, int)
            or self.minimum_included_points < 2
        ):
            raise ValidationError(
                "minimum_included_points must be an integer of at least two"
            )
        object.__setattr__(self, "target_cutoff_frequency_hz", target)
        object.__setattr__(self, "cutoff_relative_tolerance", tolerance)
        if self.schema_version != FREQUENCY_RESPONSE_CRITERIA_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported frequency-response criteria schema: {self.schema_version}"
            )

    @property
    def minimum_cutoff_frequency_hz(self) -> float:
        """Return the inclusive lower cutoff limit."""

        return self.target_cutoff_frequency_hz * (1.0 - self.cutoff_relative_tolerance)

    @property
    def maximum_cutoff_frequency_hz(self) -> float:
        """Return the inclusive upper cutoff limit."""

        return self.target_cutoff_frequency_hz * (1.0 + self.cutoff_relative_tolerance)


@dataclass(frozen=True, slots=True)
class FrequencyResponseCriterionResult:
    """One inclusive numeric frequency-response check."""

    criterion: FrequencyResponseCriterionName
    actual_value: float
    unit: str
    passed: bool
    lower_limit: float | None = None
    upper_limit: float | None = None
    schema_version: str = FREQUENCY_RESPONSE_EVALUATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.criterion, FrequencyResponseCriterionName):
            raise ValidationError("criterion must be a FrequencyResponseCriterionName")
        actual = _finite("actual_value", self.actual_value)
        expected_unit = (
            "Hz"
            if self.criterion is FrequencyResponseCriterionName.CUTOFF_FREQUENCY
            else "points"
        )
        if self.unit != expected_unit:
            raise ValidationError(
                f"{self.criterion.value} criterion requires {expected_unit}"
            )
        if not isinstance(self.passed, bool):
            raise ValidationError("passed must be a bool")
        lower = (
            None
            if self.lower_limit is None
            else _finite("lower_limit", self.lower_limit)
        )
        upper = (
            None
            if self.upper_limit is None
            else _finite("upper_limit", self.upper_limit)
        )
        if lower is None and upper is None:
            raise ValidationError("at least one criterion limit is required")
        if lower is not None and upper is not None and lower > upper:
            raise ValidationError("lower_limit cannot exceed upper_limit")
        expected = (lower is None or actual >= lower) and (
            upper is None or actual <= upper
        )
        if self.passed is not expected:
            raise ValidationError("passed must agree with the inclusive limits")
        object.__setattr__(self, "actual_value", actual)
        object.__setattr__(self, "lower_limit", lower)
        object.__setattr__(self, "upper_limit", upper)
        if self.schema_version != FREQUENCY_RESPONSE_EVALUATION_SCHEMA_VERSION:
            raise ValidationError(
                "unsupported frequency-response evaluation schema: "
                f"{self.schema_version}"
            )


def _check(
    criterion: FrequencyResponseCriterionName,
    actual: float,
    unit: str,
    *,
    lower: float | None = None,
    upper: float | None = None,
) -> FrequencyResponseCriterionResult:
    passed = (lower is None or actual >= lower) and (upper is None or actual <= upper)
    return FrequencyResponseCriterionResult(
        criterion,
        actual,
        unit,
        passed,
        lower,
        upper,
    )


def _record_ids(analysis: FrequencyResponseAnalysisResult) -> tuple[str, ...]:
    values = tuple(
        reference.record_id
        for point in analysis.points
        for reference in (
            point.frequency_decision.reference,
            point.input_decision.reference,
            point.output_decision.reference,
        )
    )
    if len(values) != len(set(values)):
        raise ValidationError("analysis record IDs must be unique")
    return values


def _raw_ids(analysis: FrequencyResponseAnalysisResult) -> tuple[str, ...]:
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


def _validate_metadata(
    analysis: FrequencyResponseAnalysisResult,
    metadata: TestRunMetadata,
) -> None:
    if metadata.test_type != FREQUENCY_RESPONSE_TEST_TYPE:
        raise ValidationError(
            f"metadata test_type must be {FREQUENCY_RESPONSE_TEST_TYPE}"
        )
    if metadata.evidence_source is not analysis.evidence_source:
        raise ValidationError("metadata evidence source must match analysis")
    if metadata.input_record_ids != _raw_ids(analysis):
        raise ValidationError(
            "metadata input_record_ids must match analysis raw records"
        )


def _derive(
    analysis: FrequencyResponseAnalysisResult,
    criteria: FrequencyResponseAcceptanceCriteria | None,
) -> tuple[
    TestRunOutcome,
    str,
    tuple[FrequencyResponseCriterionResult, ...],
    tuple[str, ...],
]:
    missing = ([] if criteria is not None else ["acceptance-criteria"]) + [
        f"analysis:{value}" for value in analysis.missing_requirements
    ]
    if missing:
        return (
            TestRunOutcome.INCOMPLETE,
            "Frequency-response criteria not evaluated",
            (),
            tuple(missing),
        )
    if criteria is None or analysis.summary is None:  # pragma: no cover
        raise ValidationError(
            "complete frequency-response evaluation requires summary and criteria"
        )
    if analysis.included_points < criteria.minimum_included_points:
        return (
            TestRunOutcome.INCOMPLETE,
            "Frequency-response criteria not evaluated",
            (),
            (
                (
                    f"criteria-included-points:{analysis.included_points}/"
                    f"{criteria.minimum_included_points}"
                ),
            ),
        )
    results = (
        _check(
            FrequencyResponseCriterionName.CUTOFF_FREQUENCY,
            analysis.summary.cutoff_frequency_hz,
            "Hz",
            lower=criteria.minimum_cutoff_frequency_hz,
            upper=criteria.maximum_cutoff_frequency_hz,
        ),
        _check(
            FrequencyResponseCriterionName.INCLUDED_POINTS,
            float(analysis.included_points),
            "points",
            lower=float(criteria.minimum_included_points),
        ),
    )
    outcome = (
        TestRunOutcome.PASS
        if all(result.passed for result in results)
        else TestRunOutcome.FAIL
    )
    summary = (
        "Frequency-response criteria passed"
        if outcome is TestRunOutcome.PASS
        else "Frequency-response criteria failed"
    )
    return outcome, summary, results, ()


@dataclass(frozen=True, slots=True)
class FrequencyResponseEvaluationResult:
    """Analysis, criteria, checks, and one consistent TestRun result."""

    analysis: FrequencyResponseAnalysisResult
    criteria: FrequencyResponseAcceptanceCriteria | None
    criterion_results: tuple[FrequencyResponseCriterionResult, ...]
    test_run_result: TestRunResult
    schema_version: str = FREQUENCY_RESPONSE_EVALUATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.analysis, FrequencyResponseAnalysisResult):
            raise ValidationError("analysis must be a FrequencyResponseAnalysisResult")
        if self.criteria is not None and not isinstance(
            self.criteria, FrequencyResponseAcceptanceCriteria
        ):
            raise ValidationError(
                "criteria must be FrequencyResponseAcceptanceCriteria or None"
            )
        if isinstance(self.criterion_results, (str, bytes)) or not isinstance(
            self.criterion_results, Iterable
        ):
            raise ValidationError("criterion_results must be an iterable")
        results = tuple(self.criterion_results)
        if not all(
            isinstance(value, FrequencyResponseCriterionResult) for value in results
        ):
            raise ValidationError(
                "criterion_results must contain FrequencyResponseCriterionResult values"
            )
        object.__setattr__(self, "criterion_results", results)
        if not isinstance(self.test_run_result, TestRunResult):
            raise ValidationError("test_run_result must be a TestRunResult")
        _validate_metadata(self.analysis, self.test_run_result.metadata)
        expected = _derive(self.analysis, self.criteria)
        if results != expected[2]:
            raise ValidationError("criterion_results must match analysis and criteria")
        if (
            self.test_run_result.outcome,
            self.test_run_result.summary,
            self.test_run_result.missing_requirements,
        ) != (expected[0], expected[1], expected[3]):
            raise ValidationError(
                "TestRun conclusion must match frequency-response evaluation"
            )
        if self.test_run_result.evidence_record_ids != _record_ids(self.analysis):
            raise ValidationError(
                "TestRun evidence IDs must match all frequency-response points"
            )
        if self.schema_version != FREQUENCY_RESPONSE_EVALUATION_SCHEMA_VERSION:
            raise ValidationError(
                "unsupported frequency-response evaluation schema: "
                f"{self.schema_version}"
            )

    @property
    def is_conclusive(self) -> bool:
        """Return whether complete criteria produced PASS or FAIL."""

        return self.test_run_result.is_complete

    @property
    def passed_criteria(self) -> int:
        return sum(result.passed for result in self.criterion_results)

    @property
    def failed_criteria(self) -> int:
        return sum(not result.passed for result in self.criterion_results)


def evaluate_frequency_response(
    analysis: FrequencyResponseAnalysisResult,
    criteria: FrequencyResponseAcceptanceCriteria | None,
    metadata: TestRunMetadata,
) -> FrequencyResponseEvaluationResult:
    """Map one explicit response analysis to a safe TestRun conclusion."""

    if not isinstance(analysis, FrequencyResponseAnalysisResult):
        raise ValidationError("analysis must be a FrequencyResponseAnalysisResult")
    if criteria is not None and not isinstance(
        criteria, FrequencyResponseAcceptanceCriteria
    ):
        raise ValidationError(
            "criteria must be FrequencyResponseAcceptanceCriteria or None"
        )
    if not isinstance(metadata, TestRunMetadata):
        raise ValidationError("metadata must be a TestRunMetadata")
    _validate_metadata(analysis, metadata)
    outcome, summary, results, missing = _derive(analysis, criteria)
    test_run = TestRunResult(
        metadata=metadata,
        outcome=outcome,
        summary=summary,
        evidence_record_ids=_record_ids(analysis),
        missing_requirements=missing,
    )
    return FrequencyResponseEvaluationResult(
        analysis,
        criteria,
        results,
        test_run,
    )


__all__ = [
    "FREQUENCY_RESPONSE_CRITERIA_SCHEMA_VERSION",
    "FREQUENCY_RESPONSE_EVALUATION_SCHEMA_VERSION",
    "FREQUENCY_RESPONSE_TEST_TYPE",
    "FrequencyResponseAcceptanceCriteria",
    "FrequencyResponseCriterionName",
    "FrequencyResponseCriterionResult",
    "FrequencyResponseEvaluationResult",
    "evaluate_frequency_response",
]
