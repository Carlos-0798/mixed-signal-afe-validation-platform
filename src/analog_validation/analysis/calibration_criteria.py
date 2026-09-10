"""Versioned calibration criteria and safe TestRun conclusion mapping."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from analog_validation.domain import (
    MeasurementUnit,
    TestRunMetadata,
    TestRunOutcome,
    TestRunResult,
)
from analog_validation.errors import ValidationError

from .calibration import CalibrationFitResult

CALIBRATION_CRITERIA_SCHEMA_VERSION = "calibration-criteria.v1"
CALIBRATION_EVALUATION_SCHEMA_VERSION = "calibration-evaluation.v1"
CALIBRATION_TEST_TYPE = "calibration"

_VOLTAGE_UNITS = frozenset({MeasurementUnit.VOLT, MeasurementUnit.MILLIVOLT})


class CalibrationCriterionName(str, Enum):
    """Stable criteria evaluated for one complete linear calibration fit."""

    AFTER_RMSE = "AFTER_RMSE"
    AFTER_MEAN_ABSOLUTE_ERROR = "AFTER_MEAN_ABSOLUTE_ERROR"
    AFTER_MAX_ABSOLUTE_ERROR = "AFTER_MAX_ABSOLUTE_ERROR"
    RMSE_REDUCTION = "RMSE_REDUCTION"
    INCLUDED_POINTS = "INCLUDED_POINTS"


_CRITERION_UNITS = {
    CalibrationCriterionName.AFTER_RMSE: frozenset({"V", "mV"}),
    CalibrationCriterionName.AFTER_MEAN_ABSOLUTE_ERROR: frozenset({"V", "mV"}),
    CalibrationCriterionName.AFTER_MAX_ABSOLUTE_ERROR: frozenset({"V", "mV"}),
    CalibrationCriterionName.RMSE_REDUCTION: frozenset({"V", "mV"}),
    CalibrationCriterionName.INCLUDED_POINTS: frozenset({"points"}),
}


def _identifier(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValidationError(f"{name} must be a non-empty stripped string")
    return value


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{name} must be numeric")
    checked = float(value)
    if not math.isfinite(checked):
        raise ValidationError(f"{name} must be finite")
    return checked


def _nonnegative(name: str, value: object) -> float:
    checked = _finite(name, value)
    if checked < 0.0:
        raise ValidationError(f"{name} cannot be negative")
    return checked


def _optional_finite(name: str, value: object) -> float | None:
    return None if value is None else _finite(name, value)


@dataclass(frozen=True, slots=True)
class CalibrationAcceptanceCriteria:
    """Explicit limits kept separate from observed and reference records."""

    criteria_id: str
    criteria_version: str
    max_after_rmse: float
    max_after_mean_absolute_error: float
    max_after_max_absolute_error: float
    minimum_rmse_reduction: float
    minimum_included_points: int
    normalized_unit: MeasurementUnit = MeasurementUnit.MILLIVOLT
    schema_version: str = CALIBRATION_CRITERIA_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _identifier("criteria_id", self.criteria_id)
        _identifier("criteria_version", self.criteria_version)
        for name in (
            "max_after_rmse",
            "max_after_mean_absolute_error",
            "max_after_max_absolute_error",
            "minimum_rmse_reduction",
        ):
            object.__setattr__(self, name, _nonnegative(name, getattr(self, name)))
        if (
            isinstance(self.minimum_included_points, bool)
            or not isinstance(self.minimum_included_points, int)
            or self.minimum_included_points < 2
        ):
            raise ValidationError(
                "minimum_included_points must be an integer of at least two"
            )
        if (
            not isinstance(self.normalized_unit, MeasurementUnit)
            or self.normalized_unit not in _VOLTAGE_UNITS
        ):
            raise ValidationError("normalized_unit must be V or mV")
        if self.schema_version != CALIBRATION_CRITERIA_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported calibration criteria schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class CalibrationCriterionResult:
    """One already-evaluated inclusive calibration limit."""

    criterion: CalibrationCriterionName
    actual_value: float
    unit: str
    passed: bool
    lower_limit: float | None = None
    upper_limit: float | None = None
    schema_version: str = CALIBRATION_EVALUATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.criterion, CalibrationCriterionName):
            raise ValidationError("criterion must be a CalibrationCriterionName")
        actual = _finite("actual_value", self.actual_value)
        unit = _identifier("unit", self.unit)
        if unit not in _CRITERION_UNITS[self.criterion]:
            raise ValidationError(f"unit is not valid for {self.criterion.value}")
        if not isinstance(self.passed, bool):
            raise ValidationError("passed must be a bool")
        lower = _optional_finite("lower_limit", self.lower_limit)
        upper = _optional_finite("upper_limit", self.upper_limit)
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
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "lower_limit", lower)
        object.__setattr__(self, "upper_limit", upper)
        if self.schema_version != CALIBRATION_EVALUATION_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported calibration evaluation schema: {self.schema_version}"
            )


def _criterion(
    name: CalibrationCriterionName,
    actual: float,
    unit: str,
    *,
    lower: float | None = None,
    upper: float | None = None,
) -> CalibrationCriterionResult:
    return CalibrationCriterionResult(
        name,
        actual,
        unit,
        (lower is None or actual >= lower) and (upper is None or actual <= upper),
        lower,
        upper,
    )


def _record_ids(analysis: CalibrationFitResult) -> tuple[str, ...]:
    values = tuple(
        reference.record_id
        for point in analysis.points
        for reference in (
            point.observed_decision.reference,
            point.reference_decision.reference,
        )
    )
    if len(values) != len(set(values)):
        raise ValidationError("calibration analysis record IDs must be unique")
    return values


def _raw_record_ids(analysis: CalibrationFitResult) -> tuple[str, ...]:
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


def _validate_metadata(
    analysis: CalibrationFitResult,
    metadata: TestRunMetadata,
) -> None:
    if analysis.observed_source is not analysis.reference_source:
        raise ValidationError(
            "calibration TestRun v1 requires observed and reference records "
            "from one evidence source"
        )
    if metadata.test_type != CALIBRATION_TEST_TYPE:
        raise ValidationError(f"metadata test_type must be {CALIBRATION_TEST_TYPE}")
    if metadata.evidence_source is not analysis.observed_source:
        raise ValidationError(
            "metadata evidence source must match calibration analysis"
        )
    if metadata.input_record_ids != _raw_record_ids(analysis):
        raise ValidationError(
            "metadata input_record_ids must match calibration raw records"
        )


def _results(
    analysis: CalibrationFitResult,
    criteria: CalibrationAcceptanceCriteria,
) -> tuple[CalibrationCriterionResult, ...]:
    metrics = analysis.metrics
    if metrics is None:  # pragma: no cover - guarded by evaluation preflight
        raise ValidationError("complete calibration evaluation requires metrics")
    unit = criteria.normalized_unit.value
    return (
        _criterion(
            CalibrationCriterionName.AFTER_RMSE,
            metrics.after_rmse,
            unit,
            upper=criteria.max_after_rmse,
        ),
        _criterion(
            CalibrationCriterionName.AFTER_MEAN_ABSOLUTE_ERROR,
            metrics.after_mean_absolute_error,
            unit,
            upper=criteria.max_after_mean_absolute_error,
        ),
        _criterion(
            CalibrationCriterionName.AFTER_MAX_ABSOLUTE_ERROR,
            metrics.after_max_absolute_error,
            unit,
            upper=criteria.max_after_max_absolute_error,
        ),
        _criterion(
            CalibrationCriterionName.RMSE_REDUCTION,
            metrics.before_rmse - metrics.after_rmse,
            unit,
            lower=criteria.minimum_rmse_reduction,
        ),
        _criterion(
            CalibrationCriterionName.INCLUDED_POINTS,
            float(metrics.included_points),
            "points",
            lower=float(criteria.minimum_included_points),
        ),
    )


def _derive(
    analysis: CalibrationFitResult,
    criteria: CalibrationAcceptanceCriteria | None,
) -> tuple[
    TestRunOutcome,
    str,
    tuple[CalibrationCriterionResult, ...],
    tuple[str, ...],
]:
    if (
        criteria is not None
        and criteria.normalized_unit is not analysis.config.normalized_unit
    ):
        raise ValidationError("criteria unit must match calibration config")
    missing: list[str] = []
    if criteria is None:
        missing.append("acceptance-criteria")
    missing.extend(
        f"analysis:{requirement}" for requirement in analysis.missing_requirements
    )
    if missing:
        return (
            TestRunOutcome.INCOMPLETE,
            "Calibration criteria not evaluated",
            (),
            tuple(missing),
        )
    if criteria is None:  # pragma: no cover - guarded above
        raise ValidationError("criteria are required for calibration evaluation")
    if analysis.included_points < criteria.minimum_included_points:
        return (
            TestRunOutcome.INCOMPLETE,
            "Calibration criteria not evaluated",
            (),
            (
                (
                    f"criteria-included-points:{analysis.included_points}/"
                    f"{criteria.minimum_included_points}"
                ),
            ),
        )
    results = _results(analysis, criteria)
    outcome = (
        TestRunOutcome.PASS
        if all(result.passed for result in results)
        else TestRunOutcome.FAIL
    )
    summary = (
        "Calibration criteria passed"
        if outcome is TestRunOutcome.PASS
        else "Calibration criteria failed"
    )
    return outcome, summary, results, ()


@dataclass(frozen=True, slots=True)
class CalibrationEvaluationResult:
    """Calibration fit, criteria checks, and one consistent TestRun result."""

    analysis: CalibrationFitResult
    criteria: CalibrationAcceptanceCriteria | None
    criterion_results: tuple[CalibrationCriterionResult, ...]
    test_run_result: TestRunResult
    schema_version: str = CALIBRATION_EVALUATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.analysis, CalibrationFitResult):
            raise ValidationError("analysis must be a CalibrationFitResult")
        if self.criteria is not None and not isinstance(
            self.criteria, CalibrationAcceptanceCriteria
        ):
            raise ValidationError(
                "criteria must be CalibrationAcceptanceCriteria or None"
            )
        if isinstance(self.criterion_results, (str, bytes)) or not isinstance(
            self.criterion_results, Iterable
        ):
            raise ValidationError("criterion_results must be an iterable")
        results = tuple(self.criterion_results)
        if not all(isinstance(value, CalibrationCriterionResult) for value in results):
            raise ValidationError(
                "criterion_results must contain CalibrationCriterionResult values"
            )
        object.__setattr__(self, "criterion_results", results)
        if not isinstance(self.test_run_result, TestRunResult):
            raise ValidationError("test_run_result must be a TestRunResult")
        _validate_metadata(self.analysis, self.test_run_result.metadata)
        outcome, summary, expected_results, missing = _derive(
            self.analysis, self.criteria
        )
        if results != expected_results:
            raise ValidationError(
                "criterion_results must match calibration analysis and criteria"
            )
        if self.test_run_result.outcome is not outcome:
            raise ValidationError("TestRun outcome must match calibration evaluation")
        if self.test_run_result.summary != summary:
            raise ValidationError("TestRun summary must match calibration evaluation")
        if self.test_run_result.missing_requirements != missing:
            raise ValidationError(
                "TestRun missing_requirements must match calibration evaluation"
            )
        if self.test_run_result.evidence_record_ids != _record_ids(self.analysis):
            raise ValidationError(
                "TestRun evidence_record_ids must match every calibration point"
            )
        if self.schema_version != CALIBRATION_EVALUATION_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported calibration evaluation schema: {self.schema_version}"
            )

    @property
    def is_conclusive(self) -> bool:
        """Return whether calibration criteria produced PASS or FAIL."""

        return self.test_run_result.is_complete

    @property
    def passed_criteria(self) -> int:
        return sum(result.passed for result in self.criterion_results)

    @property
    def failed_criteria(self) -> int:
        return sum(not result.passed for result in self.criterion_results)


def evaluate_calibration(
    analysis: CalibrationFitResult,
    criteria: CalibrationAcceptanceCriteria | None,
    metadata: TestRunMetadata,
) -> CalibrationEvaluationResult:
    """Map one calibration fit and optional criteria to a safe conclusion."""

    if not isinstance(analysis, CalibrationFitResult):
        raise ValidationError("analysis must be a CalibrationFitResult")
    if criteria is not None and not isinstance(criteria, CalibrationAcceptanceCriteria):
        raise ValidationError("criteria must be CalibrationAcceptanceCriteria or None")
    if not isinstance(metadata, TestRunMetadata):
        raise ValidationError("metadata must be a TestRunMetadata")
    _validate_metadata(analysis, metadata)
    outcome, summary, results, missing = _derive(analysis, criteria)
    return CalibrationEvaluationResult(
        analysis,
        criteria,
        results,
        TestRunResult(metadata, outcome, summary, _record_ids(analysis), missing),
    )


__all__ = [
    "CALIBRATION_CRITERIA_SCHEMA_VERSION",
    "CALIBRATION_EVALUATION_SCHEMA_VERSION",
    "CALIBRATION_TEST_TYPE",
    "CalibrationAcceptanceCriteria",
    "CalibrationCriterionName",
    "CalibrationCriterionResult",
    "CalibrationEvaluationResult",
    "evaluate_calibration",
]
