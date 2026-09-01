"""Controller-neutral, versioned result-export document model."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TypeAlias, cast

from analog_validation.analysis import AnalysisRecordReference, PointDisposition
from analog_validation.domain import EvidenceSource, TestRunOutcome, TestRunResult
from analog_validation.errors import ValidationError

RESULT_EXPORT_SCHEMA_VERSION = "result-export.v1"

ExportScalar: TypeAlias = str | int | float | bool | None


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


def _optional_finite(name: str, value: object) -> float | None:
    return None if value is None else _finite(name, value)


def _freeze(
    name: str,
    values: object,
    expected_type: type[object],
    *,
    allow_empty: bool = True,
) -> tuple[object, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ValidationError(f"{name} must be an iterable")
    frozen = tuple(values)
    if not allow_empty and not frozen:
        raise ValidationError(f"{name} cannot be empty")
    if not all(isinstance(value, expected_type) for value in frozen):
        raise ValidationError(f"{name} contains an unsupported value")
    return frozen


def _freeze_identifiers(
    name: str,
    values: object,
    *,
    allow_empty: bool = True,
) -> tuple[str, ...]:
    frozen = _freeze(name, values, str, allow_empty=allow_empty)
    identifiers = tuple(_identifier(name, value) for value in frozen)
    if len(identifiers) != len(set(identifiers)):
        raise ValidationError(f"{name} cannot contain duplicates")
    return identifiers


def _scalar(name: str, value: object) -> ExportScalar:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValidationError(f"{name} must be a JSON scalar with finite numbers")


@dataclass(frozen=True, slots=True)
class ExportSchemaReference:
    """One source schema name/version included in an exported result."""

    name: str
    version: str
    schema_version: str = RESULT_EXPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _identifier("schema name", self.name)
        _identifier("schema version value", self.version)
        if self.schema_version != RESULT_EXPORT_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported result export schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class ExportValue:
    """One named finite scalar with an explicit display/engineering unit."""

    name: str
    value: ExportScalar
    unit: str
    schema_version: str = RESULT_EXPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _identifier("value name", self.name)
        object.__setattr__(self, "value", _scalar("value", self.value))
        _identifier("value unit", self.unit)
        if self.schema_version != RESULT_EXPORT_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported result export schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class ExportCriterion:
    """One already-evaluated inclusive criterion; exporters do no math."""

    name: str
    actual_value: float
    unit: str
    passed: bool
    lower_limit: float | None = None
    upper_limit: float | None = None
    schema_version: str = RESULT_EXPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _identifier("criterion name", self.name)
        actual = _finite("actual_value", self.actual_value)
        _identifier("criterion unit", self.unit)
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
            raise ValidationError("passed must agree with inclusive limits")
        object.__setattr__(self, "actual_value", actual)
        object.__setattr__(self, "lower_limit", lower)
        object.__setattr__(self, "upper_limit", upper)
        if self.schema_version != RESULT_EXPORT_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported result export schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class ExportPoint:
    """One traceable point with values and explicit quality decisions."""

    index: int
    label: str
    disposition: PointDisposition
    references: tuple[AnalysisRecordReference, ...]
    values: tuple[ExportValue, ...]
    quality_flags: tuple[str, ...] = ()
    exclusion_reasons: tuple[str, ...] = ()
    schema_version: str = RESULT_EXPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            isinstance(self.index, bool)
            or not isinstance(self.index, int)
            or self.index < 0
        ):
            raise ValidationError("point index must be a non-negative integer")
        _identifier("point label", self.label)
        if not isinstance(self.disposition, PointDisposition):
            raise ValidationError("disposition must be a PointDisposition")
        references = cast(
            tuple[AnalysisRecordReference, ...],
            _freeze(
                "references",
                self.references,
                AnalysisRecordReference,
                allow_empty=False,
            ),
        )
        if len({value.record_id for value in references}) != len(references):
            raise ValidationError("point reference record IDs must be unique")
        if len({value.source for value in references}) != 1:
            raise ValidationError("point references must use one evidence source")
        values = cast(
            tuple[ExportValue, ...],
            _freeze("values", self.values, ExportValue, allow_empty=False),
        )
        if len({value.name for value in values}) != len(values):
            raise ValidationError("point value names must be unique")
        quality = _freeze_identifiers("quality_flags", self.quality_flags)
        reasons = _freeze_identifiers("exclusion_reasons", self.exclusion_reasons)
        if self.disposition is PointDisposition.INCLUDED and reasons:
            raise ValidationError("included points cannot have exclusion reasons")
        if self.disposition is not PointDisposition.INCLUDED and not reasons:
            raise ValidationError("excluded or invalid points require reasons")
        object.__setattr__(self, "references", references)
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "quality_flags", quality)
        object.__setattr__(self, "exclusion_reasons", reasons)
        if self.schema_version != RESULT_EXPORT_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported result export schema: {self.schema_version}"
            )

    @property
    def evidence_source(self) -> EvidenceSource:
        return self.references[0].source


@dataclass(frozen=True, slots=True)
class ResultExportBundle:
    """Complete export payload without analysis recomputation or source promotion."""

    test_run_result: TestRunResult
    source_schemas: tuple[ExportSchemaReference, ...]
    metrics: tuple[ExportValue, ...]
    points: tuple[ExportPoint, ...]
    limitations: tuple[str, ...]
    criteria_id: str | None = None
    criteria_version: str | None = None
    criterion_results: tuple[ExportCriterion, ...] = ()
    schema_version: str = RESULT_EXPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.test_run_result, TestRunResult):
            raise ValidationError("test_run_result must be a TestRunResult")
        schemas = cast(
            tuple[ExportSchemaReference, ...],
            _freeze(
                "source_schemas",
                self.source_schemas,
                ExportSchemaReference,
                allow_empty=False,
            ),
        )
        if len({value.name for value in schemas}) != len(schemas):
            raise ValidationError("source schema names must be unique")
        metrics = cast(
            tuple[ExportValue, ...],
            _freeze("metrics", self.metrics, ExportValue),
        )
        if len({value.name for value in metrics}) != len(metrics):
            raise ValidationError("metric names must be unique")
        points = cast(
            tuple[ExportPoint, ...],
            _freeze("points", self.points, ExportPoint),
        )
        if tuple(value.index for value in points) != tuple(range(len(points))):
            raise ValidationError("point indexes must be contiguous from zero")
        limitations = _freeze_identifiers(
            "limitations", self.limitations, allow_empty=False
        )
        criteria = cast(
            tuple[ExportCriterion, ...],
            _freeze("criterion_results", self.criterion_results, ExportCriterion),
        )
        if len({value.name for value in criteria}) != len(criteria):
            raise ValidationError("criterion names must be unique")
        has_criteria_identity = (
            self.criteria_id is not None or self.criteria_version is not None
        )
        if has_criteria_identity:
            if self.criteria_id is None or self.criteria_version is None:
                raise ValidationError(
                    "criteria ID and version must be present together"
                )
            _identifier("criteria_id", self.criteria_id)
            _identifier("criteria_version", self.criteria_version)
        elif criteria:
            raise ValidationError("criterion results require criteria identity")

        source = self.test_run_result.metadata.evidence_source
        if any(point.evidence_source is not source for point in points):
            raise ValidationError("point source must match TestRun evidence source")
        point_record_ids = tuple(
            reference.record_id for point in points for reference in point.references
        )
        if len(point_record_ids) != len(set(point_record_ids)):
            raise ValidationError("point record IDs must be unique across the export")
        evidence_ids = self.test_run_result.evidence_record_ids
        if points and point_record_ids != evidence_ids:
            raise ValidationError("point record IDs must match TestRun evidence IDs")
        if evidence_ids and not points:
            raise ValidationError("TestRun evidence IDs require exported points")
        point_raw_ids = tuple(
            dict.fromkeys(
                reference.raw_record_id
                for point in points
                for reference in point.references
            )
        )
        if points and point_raw_ids != self.test_run_result.metadata.input_record_ids:
            raise ValidationError("point raw IDs must match TestRun input IDs")

        outcome = self.test_run_result.outcome
        if outcome in {TestRunOutcome.PASS, TestRunOutcome.FAIL}:
            if not has_criteria_identity or not criteria or not points:
                raise ValidationError(
                    "PASS/FAIL exports require criteria and point evidence"
                )
            all_passed = all(value.passed for value in criteria)
            if (outcome is TestRunOutcome.PASS) is not all_passed:
                raise ValidationError("criterion results must match TestRun outcome")
        object.__setattr__(self, "source_schemas", schemas)
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(self, "points", points)
        object.__setattr__(self, "limitations", limitations)
        object.__setattr__(self, "criterion_results", criteria)
        if self.schema_version != RESULT_EXPORT_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported result export schema: {self.schema_version}"
            )


__all__ = [
    "RESULT_EXPORT_SCHEMA_VERSION",
    "ExportCriterion",
    "ExportPoint",
    "ExportScalar",
    "ExportSchemaReference",
    "ExportValue",
    "ResultExportBundle",
]
