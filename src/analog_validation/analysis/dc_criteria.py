"""Versioned DC sweep acceptance criteria and TestRun mapping."""

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

from .dc_sweep import DCSweepAnalysisResult

DC_SWEEP_CRITERIA_SCHEMA_VERSION = "dc-sweep-criteria.v1"
DC_SWEEP_EVALUATION_SCHEMA_VERSION = "dc-sweep-evaluation.v1"
DC_SWEEP_TEST_TYPE = "dc-sweep"

_VOLTAGE_UNITS = frozenset({MeasurementUnit.VOLT, MeasurementUnit.MILLIVOLT})


class DCSweepCriterionName(str, Enum):
    """Stable criteria evaluated for one complete DC sweep."""

    GAIN = "GAIN"
    ABS_OFFSET = "ABS_OFFSET"
    R_SQUARED = "R_SQUARED"
    RMSE = "RMSE"
    INCLUDED_POINTS = "INCLUDED_POINTS"


_CRITERION_UNITS = {
    DCSweepCriterionName.GAIN: frozenset({"ratio"}),
    DCSweepCriterionName.ABS_OFFSET: frozenset({"V", "mV"}),
    DCSweepCriterionName.R_SQUARED: frozenset({"ratio"}),
    DCSweepCriterionName.RMSE: frozenset({"V", "mV"}),
    DCSweepCriterionName.INCLUDED_POINTS: frozenset({"points"}),
}


def _require_identifier(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValidationError(f"{name} must be a non-empty stripped string")
    return value


def _require_finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValidationError(f"{name} must be finite")
    return number


def _optional_finite_number(name: str, value: object) -> float | None:
    if value is None:
        return None
    return _require_finite_number(name, value)


def _require_nonnegative(name: str, value: object) -> float:
    number = _require_finite_number(name, value)
    if number < 0.0:
        raise ValidationError(f"{name} cannot be negative")
    return number


def _require_voltage_unit(name: str, value: object) -> MeasurementUnit:
    if not isinstance(value, MeasurementUnit) or value not in _VOLTAGE_UNITS:
        raise ValidationError(f"{name} must be V or mV")
    return value


@dataclass(frozen=True, slots=True)
class DCSweepAcceptanceCriteria:
    """Immutable engineering limits kept separate from measured results."""

    criteria_id: str
    criteria_version: str
    target_gain: float
    gain_absolute_tolerance: float
    max_abs_offset: float
    min_r_squared: float
    max_rmse: float
    minimum_included_points: int
    normalized_unit: MeasurementUnit = MeasurementUnit.MILLIVOLT
    schema_version: str = DC_SWEEP_CRITERIA_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_identifier("criteria_id", self.criteria_id)
        _require_identifier("criteria_version", self.criteria_version)
        object.__setattr__(
            self,
            "target_gain",
            _require_finite_number("target_gain", self.target_gain),
        )
        for name in (
            "gain_absolute_tolerance",
            "max_abs_offset",
            "max_rmse",
        ):
            object.__setattr__(
                self,
                name,
                _require_nonnegative(name, getattr(self, name)),
            )
        gain_bounds = (
            self.target_gain - self.gain_absolute_tolerance,
            self.target_gain + self.gain_absolute_tolerance,
        )
        if not all(math.isfinite(value) for value in gain_bounds):
            raise ValidationError("derived gain limits must be finite")
        minimum_r_squared = _require_finite_number(
            "min_r_squared",
            self.min_r_squared,
        )
        if not 0.0 <= minimum_r_squared <= 1.0:
            raise ValidationError("min_r_squared must be between zero and one")
        object.__setattr__(self, "min_r_squared", minimum_r_squared)
        if (
            isinstance(self.minimum_included_points, bool)
            or not isinstance(self.minimum_included_points, int)
            or self.minimum_included_points < 2
        ):
            raise ValidationError(
                "minimum_included_points must be an integer of at least two"
            )
        _require_voltage_unit("normalized_unit", self.normalized_unit)
        if self.schema_version != DC_SWEEP_CRITERIA_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported DC sweep criteria schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class DCSweepCriterionResult:
    """One inclusive numeric limit evaluation with an explicit unit."""

    criterion: DCSweepCriterionName
    actual_value: float
    unit: str
    passed: bool
    lower_limit: float | None = None
    upper_limit: float | None = None
    schema_version: str = DC_SWEEP_EVALUATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.criterion, DCSweepCriterionName):
            raise ValidationError("criterion must be a DCSweepCriterionName")
        actual = _require_finite_number("actual_value", self.actual_value)
        unit = _require_identifier("unit", self.unit)
        if unit not in _CRITERION_UNITS[self.criterion]:
            raise ValidationError(f"unit is not valid for {self.criterion.value}")
        if not isinstance(self.passed, bool):
            raise ValidationError("passed must be a bool")
        lower = _optional_finite_number("lower_limit", self.lower_limit)
        upper = _optional_finite_number("upper_limit", self.upper_limit)
        if lower is None and upper is None:
            raise ValidationError("at least one criterion limit is required")
        if lower is not None and upper is not None and lower > upper:
            raise ValidationError("lower_limit cannot exceed upper_limit")
        expected_pass = (lower is None or actual >= lower) and (
            upper is None or actual <= upper
        )
        if self.passed is not expected_pass:
            raise ValidationError("passed must agree with the inclusive limits")
        object.__setattr__(self, "actual_value", actual)
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "lower_limit", lower)
        object.__setattr__(self, "upper_limit", upper)
        if self.schema_version != DC_SWEEP_EVALUATION_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported DC sweep evaluation schema: {self.schema_version}"
            )


def _criterion_result(
    criterion: DCSweepCriterionName,
    actual_value: float,
    unit: str,
    *,
    lower_limit: float | None = None,
    upper_limit: float | None = None,
) -> DCSweepCriterionResult:
    passed = (lower_limit is None or actual_value >= lower_limit) and (
        upper_limit is None or actual_value <= upper_limit
    )
    return DCSweepCriterionResult(
        criterion=criterion,
        actual_value=actual_value,
        unit=unit,
        passed=passed,
        lower_limit=lower_limit,
        upper_limit=upper_limit,
    )


def _evaluate_complete_fit(
    analysis: DCSweepAnalysisResult,
    criteria: DCSweepAcceptanceCriteria,
) -> tuple[DCSweepCriterionResult, ...]:
    fit = analysis.fit
    if fit is None:  # pragma: no cover - protected by evaluation preflight
        raise ValidationError("complete criteria evaluation requires a fit")
    gain_lower = criteria.target_gain - criteria.gain_absolute_tolerance
    gain_upper = criteria.target_gain + criteria.gain_absolute_tolerance
    return (
        _criterion_result(
            DCSweepCriterionName.GAIN,
            fit.gain,
            "ratio",
            lower_limit=gain_lower,
            upper_limit=gain_upper,
        ),
        _criterion_result(
            DCSweepCriterionName.ABS_OFFSET,
            abs(fit.offset),
            criteria.normalized_unit.value,
            upper_limit=criteria.max_abs_offset,
        ),
        _criterion_result(
            DCSweepCriterionName.R_SQUARED,
            fit.r_squared,
            "ratio",
            lower_limit=criteria.min_r_squared,
        ),
        _criterion_result(
            DCSweepCriterionName.RMSE,
            fit.rmse,
            criteria.normalized_unit.value,
            upper_limit=criteria.max_rmse,
        ),
        _criterion_result(
            DCSweepCriterionName.INCLUDED_POINTS,
            float(analysis.included_points),
            "points",
            lower_limit=float(criteria.minimum_included_points),
        ),
    )


def _analysis_record_ids(analysis: DCSweepAnalysisResult) -> tuple[str, ...]:
    values = tuple(
        reference.record_id
        for point in analysis.points
        for reference in (
            point.input_decision.reference,
            point.output_decision.reference,
        )
    )
    if len(values) != len(set(values)):
        raise ValidationError("analysis point record IDs must be unique")
    return values


def _analysis_raw_record_ids(analysis: DCSweepAnalysisResult) -> tuple[str, ...]:
    values = (
        reference.raw_record_id
        for point in analysis.points
        for reference in (
            point.input_decision.reference,
            point.output_decision.reference,
        )
    )
    return tuple(dict.fromkeys(values))


def _validate_metadata(
    analysis: DCSweepAnalysisResult,
    metadata: TestRunMetadata,
) -> None:
    if metadata.test_type != DC_SWEEP_TEST_TYPE:
        raise ValidationError(f"metadata test_type must be {DC_SWEEP_TEST_TYPE}")
    if metadata.evidence_source is not analysis.evidence_source:
        raise ValidationError("metadata evidence source must match analysis")
    expected_raw_ids = _analysis_raw_record_ids(analysis)
    if metadata.input_record_ids != expected_raw_ids:
        raise ValidationError(
            "metadata input_record_ids must match analysis raw records"
        )


def _derive_evaluation(
    analysis: DCSweepAnalysisResult,
    criteria: DCSweepAcceptanceCriteria | None,
) -> tuple[
    TestRunOutcome,
    str,
    tuple[DCSweepCriterionResult, ...],
    tuple[str, ...],
]:
    if criteria is not None and (
        criteria.normalized_unit is not analysis.config.normalized_unit
    ):
        raise ValidationError("criteria unit must match analysis config")

    missing: list[str] = []
    if criteria is None:
        missing.append("acceptance-criteria")
    missing.extend(
        f"analysis:{requirement}" for requirement in analysis.missing_requirements
    )
    if missing:
        return (
            TestRunOutcome.INCOMPLETE,
            "DC sweep criteria not evaluated",
            (),
            tuple(missing),
        )

    if criteria is None:  # pragma: no cover - protected by missing preflight
        raise ValidationError("criteria are required for complete evaluation")
    if analysis.included_points < criteria.minimum_included_points:
        return (
            TestRunOutcome.INCOMPLETE,
            "DC sweep criteria not evaluated",
            (),
            (
                (
                    f"criteria-included-points:{analysis.included_points}/"
                    f"{criteria.minimum_included_points}"
                ),
            ),
        )

    criterion_results = _evaluate_complete_fit(analysis, criteria)
    outcome = (
        TestRunOutcome.PASS
        if all(result.passed for result in criterion_results)
        else TestRunOutcome.FAIL
    )
    summary = (
        "DC sweep criteria passed"
        if outcome is TestRunOutcome.PASS
        else "DC sweep criteria failed"
    )
    return outcome, summary, criterion_results, ()


@dataclass(frozen=True, slots=True)
class DCSweepEvaluationResult:
    """Analysis, optional criteria, checks, and one consistent TestRunResult."""

    analysis: DCSweepAnalysisResult
    criteria: DCSweepAcceptanceCriteria | None
    criterion_results: tuple[DCSweepCriterionResult, ...]
    test_run_result: TestRunResult
    schema_version: str = DC_SWEEP_EVALUATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.analysis, DCSweepAnalysisResult):
            raise ValidationError("analysis must be a DCSweepAnalysisResult")
        if self.criteria is not None and not isinstance(
            self.criteria,
            DCSweepAcceptanceCriteria,
        ):
            raise ValidationError("criteria must be DCSweepAcceptanceCriteria or None")
        values = self.criterion_results
        if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
            raise ValidationError("criterion_results must be an iterable")
        results = tuple(values)
        if not all(isinstance(value, DCSweepCriterionResult) for value in results):
            raise ValidationError(
                "criterion_results must contain DCSweepCriterionResult values"
            )
        object.__setattr__(self, "criterion_results", results)
        if not isinstance(self.test_run_result, TestRunResult):
            raise ValidationError("test_run_result must be a TestRunResult")
        _validate_metadata(self.analysis, self.test_run_result.metadata)

        expected_outcome, expected_summary, expected_results, expected_missing = (
            _derive_evaluation(self.analysis, self.criteria)
        )
        if results != expected_results:
            raise ValidationError("criterion_results must match analysis and criteria")
        if self.test_run_result.outcome is not expected_outcome:
            raise ValidationError("TestRun outcome must match criteria evaluation")
        if self.test_run_result.summary != expected_summary:
            raise ValidationError("TestRun summary must match criteria evaluation")
        if self.test_run_result.missing_requirements != expected_missing:
            raise ValidationError(
                "TestRun missing_requirements must match criteria evaluation"
            )
        if self.test_run_result.evidence_record_ids != _analysis_record_ids(
            self.analysis
        ):
            raise ValidationError(
                "TestRun evidence_record_ids must match every analysis point"
            )
        if self.schema_version != DC_SWEEP_EVALUATION_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported DC sweep evaluation schema: {self.schema_version}"
            )

    @property
    def is_conclusive(self) -> bool:
        """Return whether all criteria were evaluated as PASS or FAIL."""

        return self.test_run_result.is_complete

    @property
    def passed_criteria(self) -> int:
        """Return the number of satisfied criteria, zero if not evaluated."""

        return sum(result.passed for result in self.criterion_results)

    @property
    def failed_criteria(self) -> int:
        """Return the number of failed criteria, zero if not evaluated."""

        return sum(not result.passed for result in self.criterion_results)


def evaluate_dc_sweep(
    analysis: DCSweepAnalysisResult,
    criteria: DCSweepAcceptanceCriteria | None,
    metadata: TestRunMetadata,
) -> DCSweepEvaluationResult:
    """Map one analysis and optional criteria to a safe TestRun conclusion."""

    if not isinstance(analysis, DCSweepAnalysisResult):
        raise ValidationError("analysis must be a DCSweepAnalysisResult")
    if criteria is not None and not isinstance(criteria, DCSweepAcceptanceCriteria):
        raise ValidationError("criteria must be DCSweepAcceptanceCriteria or None")
    if not isinstance(metadata, TestRunMetadata):
        raise ValidationError("metadata must be a TestRunMetadata")
    _validate_metadata(analysis, metadata)
    outcome, summary, criterion_results, missing = _derive_evaluation(
        analysis,
        criteria,
    )
    test_run_result = TestRunResult(
        metadata=metadata,
        outcome=outcome,
        summary=summary,
        evidence_record_ids=_analysis_record_ids(analysis),
        missing_requirements=missing,
    )
    return DCSweepEvaluationResult(
        analysis=analysis,
        criteria=criteria,
        criterion_results=criterion_results,
        test_run_result=test_run_result,
    )


__all__ = [
    "DC_SWEEP_CRITERIA_SCHEMA_VERSION",
    "DC_SWEEP_EVALUATION_SCHEMA_VERSION",
    "DC_SWEEP_TEST_TYPE",
    "DCSweepAcceptanceCriteria",
    "DCSweepCriterionName",
    "DCSweepCriterionResult",
    "DCSweepEvaluationResult",
    "evaluate_dc_sweep",
]
