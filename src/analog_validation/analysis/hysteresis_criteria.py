"""Versioned hysteresis criteria and safe TestRun conclusion mapping."""

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

from .hysteresis import HysteresisAnalysisResult

HYSTERESIS_CRITERIA_SCHEMA_VERSION = "hysteresis-criteria.v1"
HYSTERESIS_EVALUATION_SCHEMA_VERSION = "hysteresis-evaluation.v1"
HYSTERESIS_TEST_TYPE = "hysteresis"

_VOLTAGE_UNITS = frozenset({MeasurementUnit.VOLT, MeasurementUnit.MILLIVOLT})


class HysteresisCriterionName(str, Enum):
    """Stable checks evaluated only after every cycle is complete."""

    MEAN_HIGH_THRESHOLD = "MEAN_HIGH_THRESHOLD"
    MEAN_LOW_THRESHOLD = "MEAN_LOW_THRESHOLD"
    MEAN_WIDTH = "MEAN_WIDTH"
    WIDTH_SPAN = "WIDTH_SPAN"
    COMPLETE_CYCLES = "COMPLETE_CYCLES"


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


def _range(name: str, minimum: object, maximum: object) -> tuple[float, float]:
    lower = _finite(f"minimum_{name}", minimum)
    upper = _finite(f"maximum_{name}", maximum)
    if lower > upper:
        raise ValidationError(f"minimum_{name} cannot exceed maximum_{name}")
    return lower, upper


@dataclass(frozen=True, slots=True)
class HysteresisAcceptanceCriteria:
    """Inclusive threshold/width limits kept separate from observations."""

    criteria_id: str
    criteria_version: str
    minimum_high_threshold: float
    maximum_high_threshold: float
    minimum_low_threshold: float
    maximum_low_threshold: float
    minimum_width: float
    maximum_width: float
    maximum_width_span: float
    minimum_complete_cycles: int
    normalized_unit: MeasurementUnit = MeasurementUnit.MILLIVOLT
    schema_version: str = HYSTERESIS_CRITERIA_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _identifier("criteria_id", self.criteria_id)
        _identifier("criteria_version", self.criteria_version)
        for stem in ("high_threshold", "low_threshold", "width"):
            lower, upper = _range(
                stem,
                getattr(self, f"minimum_{stem}"),
                getattr(self, f"maximum_{stem}"),
            )
            object.__setattr__(self, f"minimum_{stem}", lower)
            object.__setattr__(self, f"maximum_{stem}", upper)
        if self.minimum_width < 0:
            raise ValidationError("minimum_width cannot be negative")
        width_span = _finite("maximum_width_span", self.maximum_width_span)
        if width_span < 0:
            raise ValidationError("maximum_width_span cannot be negative")
        object.__setattr__(self, "maximum_width_span", width_span)
        if (
            isinstance(self.minimum_complete_cycles, bool)
            or not isinstance(self.minimum_complete_cycles, int)
            or self.minimum_complete_cycles < 1
        ):
            raise ValidationError("minimum_complete_cycles must be a positive integer")
        if self.normalized_unit not in _VOLTAGE_UNITS:
            raise ValidationError("normalized_unit must be V or mV")
        if self.schema_version != HYSTERESIS_CRITERIA_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported hysteresis criteria schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class HysteresisCriterionResult:
    """One inclusive numeric check with explicit engineering units."""

    criterion: HysteresisCriterionName
    actual_value: float
    unit: str
    passed: bool
    lower_limit: float | None = None
    upper_limit: float | None = None
    schema_version: str = HYSTERESIS_EVALUATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.criterion, HysteresisCriterionName):
            raise ValidationError("criterion must be a HysteresisCriterionName")
        actual = _finite("actual_value", self.actual_value)
        unit = _identifier("unit", self.unit)
        if self.criterion is HysteresisCriterionName.COMPLETE_CYCLES:
            if unit != "cycles":
                raise ValidationError("complete-cycle criterion requires cycles")
        elif unit not in {"V", "mV"}:
            raise ValidationError("threshold and width criteria require V or mV")
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
        expected_pass = (lower is None or actual >= lower) and (
            upper is None or actual <= upper
        )
        if self.passed is not expected_pass:
            raise ValidationError("passed must agree with the inclusive limits")
        object.__setattr__(self, "actual_value", actual)
        object.__setattr__(self, "lower_limit", lower)
        object.__setattr__(self, "upper_limit", upper)
        if self.schema_version != HYSTERESIS_EVALUATION_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported hysteresis evaluation schema: {self.schema_version}"
            )


def _check(
    name: HysteresisCriterionName,
    actual: float,
    unit: str,
    *,
    lower: float | None = None,
    upper: float | None = None,
) -> HysteresisCriterionResult:
    passed = (lower is None or actual >= lower) and (upper is None or actual <= upper)
    return HysteresisCriterionResult(name, actual, unit, passed, lower, upper)


def _record_ids(analysis: HysteresisAnalysisResult) -> tuple[str, ...]:
    values = tuple(
        reference.record_id
        for cycle in analysis.cycles
        for point in cycle.rising_points + cycle.falling_points
        for reference in (point.input_decision.reference, point.state_reference)
    )
    if len(values) != len(set(values)):
        raise ValidationError("analysis record IDs must be unique")
    return values


def _raw_ids(analysis: HysteresisAnalysisResult) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            reference.raw_record_id
            for cycle in analysis.cycles
            for point in cycle.rising_points + cycle.falling_points
            for reference in (point.input_decision.reference, point.state_reference)
        )
    )


def _validate_metadata(
    analysis: HysteresisAnalysisResult, metadata: TestRunMetadata
) -> None:
    if metadata.test_type != HYSTERESIS_TEST_TYPE:
        raise ValidationError(f"metadata test_type must be {HYSTERESIS_TEST_TYPE}")
    if metadata.evidence_source is not analysis.evidence_source:
        raise ValidationError("metadata evidence source must match analysis")
    if metadata.input_record_ids != _raw_ids(analysis):
        raise ValidationError(
            "metadata input_record_ids must match analysis raw records"
        )


def _derive(
    analysis: HysteresisAnalysisResult,
    criteria: HysteresisAcceptanceCriteria | None,
) -> tuple[TestRunOutcome, str, tuple[HysteresisCriterionResult, ...], tuple[str, ...]]:
    if (
        criteria is not None
        and criteria.normalized_unit is not analysis.config.normalized_unit
    ):
        raise ValidationError("criteria unit must match analysis config")
    missing = ([] if criteria is not None else ["acceptance-criteria"]) + [
        f"analysis:{value}" for value in analysis.missing_requirements
    ]
    if missing:
        return (
            TestRunOutcome.INCOMPLETE,
            "Hysteresis criteria not evaluated",
            (),
            tuple(missing),
        )
    if (
        criteria is None or analysis.summary is None
    ):  # pragma: no cover - preflight invariant
        raise ValidationError(
            "complete hysteresis evaluation requires summary and criteria"
        )
    if analysis.summary.cycle_count < criteria.minimum_complete_cycles:
        return (
            TestRunOutcome.INCOMPLETE,
            "Hysteresis criteria not evaluated",
            (),
            (
                f"criteria-complete-cycles:{analysis.summary.cycle_count}/{criteria.minimum_complete_cycles}",
            ),
        )
    summary = analysis.summary
    unit = criteria.normalized_unit.value
    results = (
        _check(
            HysteresisCriterionName.MEAN_HIGH_THRESHOLD,
            summary.mean_high_threshold,
            unit,
            lower=criteria.minimum_high_threshold,
            upper=criteria.maximum_high_threshold,
        ),
        _check(
            HysteresisCriterionName.MEAN_LOW_THRESHOLD,
            summary.mean_low_threshold,
            unit,
            lower=criteria.minimum_low_threshold,
            upper=criteria.maximum_low_threshold,
        ),
        _check(
            HysteresisCriterionName.MEAN_WIDTH,
            summary.mean_width,
            unit,
            lower=criteria.minimum_width,
            upper=criteria.maximum_width,
        ),
        _check(
            HysteresisCriterionName.WIDTH_SPAN,
            summary.width_span,
            unit,
            upper=criteria.maximum_width_span,
        ),
        _check(
            HysteresisCriterionName.COMPLETE_CYCLES,
            float(summary.cycle_count),
            "cycles",
            lower=float(criteria.minimum_complete_cycles),
        ),
    )
    outcome = (
        TestRunOutcome.PASS
        if all(value.passed for value in results)
        else TestRunOutcome.FAIL
    )
    summary_text = (
        "Hysteresis criteria passed"
        if outcome is TestRunOutcome.PASS
        else "Hysteresis criteria failed"
    )
    return outcome, summary_text, results, ()


@dataclass(frozen=True, slots=True)
class HysteresisEvaluationResult:
    """Analysis, optional criteria, checks, and one consistent TestRunResult."""

    analysis: HysteresisAnalysisResult
    criteria: HysteresisAcceptanceCriteria | None
    criterion_results: tuple[HysteresisCriterionResult, ...]
    test_run_result: TestRunResult
    schema_version: str = HYSTERESIS_EVALUATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.analysis, HysteresisAnalysisResult):
            raise ValidationError("analysis must be a HysteresisAnalysisResult")
        if self.criteria is not None and not isinstance(
            self.criteria, HysteresisAcceptanceCriteria
        ):
            raise ValidationError(
                "criteria must be HysteresisAcceptanceCriteria or None"
            )
        if isinstance(self.criterion_results, (str, bytes)) or not isinstance(
            self.criterion_results, Iterable
        ):
            raise ValidationError("criterion_results must be an iterable")
        results = tuple(self.criterion_results)
        if not all(isinstance(value, HysteresisCriterionResult) for value in results):
            raise ValidationError(
                "criterion_results must contain HysteresisCriterionResult values"
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
            raise ValidationError("TestRun conclusion must match hysteresis evaluation")
        if self.test_run_result.evidence_record_ids != _record_ids(self.analysis):
            raise ValidationError("TestRun evidence IDs must match all analysis points")
        if self.schema_version != HYSTERESIS_EVALUATION_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported hysteresis evaluation schema: {self.schema_version}"
            )

    @property
    def is_conclusive(self) -> bool:
        return self.test_run_result.is_complete


def evaluate_hysteresis(
    analysis: HysteresisAnalysisResult,
    criteria: HysteresisAcceptanceCriteria | None,
    metadata: TestRunMetadata,
) -> HysteresisEvaluationResult:
    """Evaluate complete cycles only; incomplete evidence can never PASS."""

    if not isinstance(analysis, HysteresisAnalysisResult):
        raise ValidationError("analysis must be a HysteresisAnalysisResult")
    if criteria is not None and not isinstance(criteria, HysteresisAcceptanceCriteria):
        raise ValidationError("criteria must be HysteresisAcceptanceCriteria or None")
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
    return HysteresisEvaluationResult(analysis, criteria, results, test_run)


__all__ = [
    "HYSTERESIS_CRITERIA_SCHEMA_VERSION",
    "HYSTERESIS_EVALUATION_SCHEMA_VERSION",
    "HYSTERESIS_TEST_TYPE",
    "HysteresisAcceptanceCriteria",
    "HysteresisCriterionName",
    "HysteresisCriterionResult",
    "HysteresisEvaluationResult",
    "evaluate_hysteresis",
]
