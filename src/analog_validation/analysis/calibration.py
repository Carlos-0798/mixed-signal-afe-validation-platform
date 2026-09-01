"""Versioned linear calibration fitting and immutable record derivation."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from statistics import fmean
from typing import cast

from analog_validation.domain import EvidenceSource, Measurement, MeasurementUnit
from analog_validation.errors import ValidationError

from .common import (
    DEFAULT_ANALYSIS_QUALITY_POLICY,
    AnalysisQualityPolicy,
    MeasurementBatch,
    MeasurementDecision,
    PointDisposition,
    assess_voltage_measurement,
)

CALIBRATION_ANALYSIS_SCHEMA_VERSION = "calibration-analysis.v1"
CALIBRATION_METHOD = "linear-reference-fit"

_VOLTAGE_UNITS = frozenset({MeasurementUnit.VOLT, MeasurementUnit.MILLIVOLT})


class CalibrationPointExclusionReason(str, Enum):
    """Stable reason a paired calibration point cannot enter the fit."""

    OBSERVED_NOT_INCLUDED = "OBSERVED_NOT_INCLUDED"
    REFERENCE_NOT_INCLUDED = "REFERENCE_NOT_INCLUDED"


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


def _voltage_unit(name: str, value: object) -> MeasurementUnit:
    if not isinstance(value, MeasurementUnit) or value not in _VOLTAGE_UNITS:
        raise ValidationError(f"{name} must be V or mV")
    return value


@dataclass(frozen=True, slots=True)
class CalibrationFitConfig:
    """Channels, coefficient identity, unit, and quality policy for a fit."""

    observed_channel: str
    reference_channel: str
    coefficient_id: str
    coefficient_version: str
    normalized_unit: MeasurementUnit = MeasurementUnit.MILLIVOLT
    minimum_included_points: int = 3
    quality_policy: AnalysisQualityPolicy = DEFAULT_ANALYSIS_QUALITY_POLICY
    schema_version: str = CALIBRATION_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "observed_channel",
            "reference_channel",
            "coefficient_id",
            "coefficient_version",
        ):
            _identifier(name, getattr(self, name))
        if self.observed_channel == self.reference_channel:
            raise ValidationError("observed and reference channels must be distinct")
        _voltage_unit("normalized_unit", self.normalized_unit)
        if (
            isinstance(self.minimum_included_points, bool)
            or not isinstance(self.minimum_included_points, int)
            or self.minimum_included_points < 2
        ):
            raise ValidationError(
                "minimum_included_points must be an integer of at least two"
            )
        if not isinstance(self.quality_policy, AnalysisQualityPolicy):
            raise ValidationError("quality_policy must be an AnalysisQualityPolicy")
        if self.schema_version != CALIBRATION_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported calibration analysis schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class CalibrationPointResult:
    """One observed/reference pair and its quality decision."""

    sequence: int
    observed_decision: MeasurementDecision
    reference_decision: MeasurementDecision
    disposition: PointDisposition
    exclusion_reasons: tuple[CalibrationPointExclusionReason, ...] = ()
    calibrated_value: float | None = None
    before_error: float | None = None
    after_error: float | None = None
    schema_version: str = CALIBRATION_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise ValidationError("sequence must be a non-negative integer")
        if not isinstance(self.observed_decision, MeasurementDecision):
            raise ValidationError("observed_decision must be a MeasurementDecision")
        if not isinstance(self.reference_decision, MeasurementDecision):
            raise ValidationError("reference_decision must be a MeasurementDecision")
        if (
            self.observed_decision.normalized_unit
            is not self.reference_decision.normalized_unit
        ):
            raise ValidationError("calibration decisions must use one normalized unit")
        if not isinstance(self.disposition, PointDisposition):
            raise ValidationError("disposition must be a PointDisposition")
        if isinstance(self.exclusion_reasons, (str, bytes)) or not isinstance(
            self.exclusion_reasons, Iterable
        ):
            raise ValidationError("exclusion_reasons must be an iterable")
        reasons = tuple(self.exclusion_reasons)
        if not all(
            isinstance(value, CalibrationPointExclusionReason) for value in reasons
        ):
            raise ValidationError("exclusion_reasons contains an unknown reason")
        if len(reasons) != len(set(reasons)):
            raise ValidationError("exclusion_reasons cannot contain duplicates")
        object.__setattr__(self, "exclusion_reasons", reasons)
        observed_included = (
            self.observed_decision.disposition is PointDisposition.INCLUDED
        )
        reference_included = (
            self.reference_decision.disposition is PointDisposition.INCLUDED
        )
        expected_reasons = tuple(
            reason
            for condition, reason in (
                (
                    not observed_included,
                    CalibrationPointExclusionReason.OBSERVED_NOT_INCLUDED,
                ),
                (
                    not reference_included,
                    CalibrationPointExclusionReason.REFERENCE_NOT_INCLUDED,
                ),
            )
            if condition
        )
        if reasons != expected_reasons:
            raise ValidationError("exclusion reasons must match component decisions")
        any_invalid = any(
            value.disposition is PointDisposition.INVALID
            for value in (self.observed_decision, self.reference_decision)
        )
        expected_disposition = (
            PointDisposition.INVALID
            if any_invalid
            else PointDisposition.INCLUDED
            if observed_included and reference_included
            else PointDisposition.EXCLUDED
        )
        if self.disposition is not expected_disposition:
            raise ValidationError("point disposition must match component decisions")
        values = (self.calibrated_value, self.before_error, self.after_error)
        if self.disposition is PointDisposition.INCLUDED:
            if any((value is None) != (values[0] is None) for value in values):
                raise ValidationError("fitted values must be all present or all absent")
            for name, value in zip(
                ("calibrated_value", "before_error", "after_error"),
                values,
                strict=True,
            ):
                if value is not None:
                    object.__setattr__(self, name, _finite(name, value))
        elif any(value is not None for value in values):
            raise ValidationError(
                "excluded calibration points cannot have fitted values"
            )
        if self.schema_version != CALIBRATION_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported calibration analysis schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class CalibrationErrorMetrics:
    """Before/after errors for the exact included fit records."""

    included_points: int
    before_rmse: float
    after_rmse: float
    before_mean_absolute_error: float
    after_mean_absolute_error: float
    before_max_absolute_error: float
    after_max_absolute_error: float
    unit: MeasurementUnit
    schema_version: str = CALIBRATION_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            isinstance(self.included_points, bool)
            or not isinstance(self.included_points, int)
            or self.included_points < 2
        ):
            raise ValidationError("included_points must be an integer of at least two")
        for name in (
            "before_rmse",
            "after_rmse",
            "before_mean_absolute_error",
            "after_mean_absolute_error",
            "before_max_absolute_error",
            "after_max_absolute_error",
        ):
            value = _finite(name, getattr(self, name))
            if value < 0:
                raise ValidationError(f"{name} cannot be negative")
            object.__setattr__(self, name, value)
        _voltage_unit("unit", self.unit)
        if self.schema_version != CALIBRATION_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported calibration analysis schema: {self.schema_version}"
            )


def _freeze_ids(name: str, values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ValidationError(f"{name} must be an iterable")
    frozen = tuple(values)
    for value in frozen:
        _identifier(name, value)
    if not frozen or len(frozen) != len(set(frozen)):
        raise ValidationError(f"{name} must be non-empty and unique")
    return frozen


@dataclass(frozen=True, slots=True)
class LinearCalibrationCoefficients:
    """Self-contained linear coefficients with fit-source lineage."""

    coefficient_id: str
    coefficient_version: str
    scale: float
    offset: float
    unit: MeasurementUnit
    observed_source: EvidenceSource
    reference_source: EvidenceSource
    observed_record_ids: tuple[str, ...]
    reference_record_ids: tuple[str, ...]
    observed_raw_record_ids: tuple[str, ...]
    reference_raw_record_ids: tuple[str, ...]
    method: str = CALIBRATION_METHOD
    schema_version: str = CALIBRATION_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _identifier("coefficient_id", self.coefficient_id)
        _identifier("coefficient_version", self.coefficient_version)
        scale = _finite("scale", self.scale)
        if scale == 0:
            raise ValidationError("scale cannot be zero")
        object.__setattr__(self, "scale", scale)
        object.__setattr__(self, "offset", _finite("offset", self.offset))
        _voltage_unit("unit", self.unit)
        if not isinstance(self.observed_source, EvidenceSource) or not isinstance(
            self.reference_source, EvidenceSource
        ):
            raise ValidationError("coefficient sources must be EvidenceSource values")
        for name in (
            "observed_record_ids",
            "reference_record_ids",
            "observed_raw_record_ids",
            "reference_raw_record_ids",
        ):
            object.__setattr__(self, name, _freeze_ids(name, getattr(self, name)))
        lengths = {
            len(self.observed_record_ids),
            len(self.reference_record_ids),
            len(self.observed_raw_record_ids),
            len(self.reference_raw_record_ids),
        }
        if len(lengths) != 1:
            raise ValidationError(
                "coefficient lineage collections must have equal lengths"
            )
        if self.method != CALIBRATION_METHOD:
            raise ValidationError("unsupported calibration method")
        if self.schema_version != CALIBRATION_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported calibration analysis schema: {self.schema_version}"
            )

    def apply(self, value: float) -> float:
        """Apply the finite linear mapping without altering source evidence."""

        result = self.scale * _finite("value", value) + self.offset
        return _finite("calibrated value", result)


@dataclass(frozen=True, slots=True)
class CalibrationFitResult:
    """All pair decisions plus optional coefficients and error metrics."""

    config: CalibrationFitConfig
    observed_source: EvidenceSource
    reference_source: EvidenceSource
    points: tuple[CalibrationPointResult, ...]
    coefficients: LinearCalibrationCoefficients | None = None
    metrics: CalibrationErrorMetrics | None = None
    missing_requirements: tuple[str, ...] = ()
    schema_version: str = CALIBRATION_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.config, CalibrationFitConfig):
            raise ValidationError("config must be a CalibrationFitConfig")
        if not isinstance(self.observed_source, EvidenceSource) or not isinstance(
            self.reference_source, EvidenceSource
        ):
            raise ValidationError("result sources must be EvidenceSource values")
        points = tuple(self.points)
        if not points or not all(
            isinstance(value, CalibrationPointResult) for value in points
        ):
            raise ValidationError("points must contain CalibrationPointResult values")
        if tuple(value.sequence for value in points) != tuple(range(len(points))):
            raise ValidationError("point sequences must be contiguous from zero")
        object.__setattr__(self, "points", points)
        missing = tuple(self.missing_requirements)
        if not all(isinstance(value, str) and value for value in missing) or len(
            missing
        ) != len(set(missing)):
            raise ValidationError("missing_requirements must contain unique strings")
        object.__setattr__(self, "missing_requirements", missing)
        complete = self.coefficients is not None and self.metrics is not None
        if complete != (not missing):
            raise ValidationError("fit outputs and missing requirements must agree")
        if complete:
            if not isinstance(
                self.coefficients, LinearCalibrationCoefficients
            ) or not isinstance(self.metrics, CalibrationErrorMetrics):
                raise ValidationError("complete fit requires coefficients and metrics")
            if (
                self.coefficients.unit is not self.config.normalized_unit
                or self.metrics.unit is not self.config.normalized_unit
            ):
                raise ValidationError("fit outputs must match the configured unit")
            if (
                self.coefficients.observed_source,
                self.coefficients.reference_source,
            ) != (self.observed_source, self.reference_source):
                raise ValidationError("coefficient sources must match the fit result")
            if self.metrics.included_points != self.included_points:
                raise ValidationError("metrics point count must match included points")
        elif self.coefficients is not None or self.metrics is not None:
            raise ValidationError("incomplete fit cannot publish partial outputs")
        if self.schema_version != CALIBRATION_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported calibration analysis schema: {self.schema_version}"
            )

    @property
    def included_points(self) -> int:
        return sum(
            value.disposition is PointDisposition.INCLUDED for value in self.points
        )

    @property
    def is_complete(self) -> bool:
        return self.coefficients is not None


def _paired_points(
    observed: MeasurementBatch,
    reference: MeasurementBatch,
    config: CalibrationFitConfig,
) -> tuple[CalibrationPointResult, ...]:
    if len(observed.measurements) != len(reference.measurements):
        raise ValidationError("observed and reference batches must have equal lengths")
    all_ids = observed.record_ids + reference.record_ids
    if len(all_ids) != len(set(all_ids)):
        raise ValidationError("calibration record IDs must be unique")
    points: list[CalibrationPointResult] = []
    for sequence, (observed_measurement, reference_measurement) in enumerate(
        zip(observed.measurements, reference.measurements, strict=True)
    ):
        if observed_measurement.channel != config.observed_channel:
            raise ValidationError("observed channel does not match calibration config")
        if reference_measurement.channel != config.reference_channel:
            raise ValidationError("reference channel does not match calibration config")
        observed_decision = assess_voltage_measurement(
            observed_measurement,
            config.quality_policy,
            target_unit=config.normalized_unit,
        )
        reference_decision = assess_voltage_measurement(
            reference_measurement,
            config.quality_policy,
            target_unit=config.normalized_unit,
        )
        reasons = tuple(
            reason
            for condition, reason in (
                (
                    observed_decision.disposition is not PointDisposition.INCLUDED,
                    CalibrationPointExclusionReason.OBSERVED_NOT_INCLUDED,
                ),
                (
                    reference_decision.disposition is not PointDisposition.INCLUDED,
                    CalibrationPointExclusionReason.REFERENCE_NOT_INCLUDED,
                ),
            )
            if condition
        )
        disposition = (
            PointDisposition.INVALID
            if any(
                value.disposition is PointDisposition.INVALID
                for value in (observed_decision, reference_decision)
            )
            else PointDisposition.EXCLUDED
            if reasons
            else PointDisposition.INCLUDED
        )
        points.append(
            CalibrationPointResult(
                sequence,
                observed_decision,
                reference_decision,
                disposition,
                reasons,
            )
        )
    return tuple(points)


def _errors(values: tuple[float, ...]) -> tuple[float, float, float]:
    return (
        math.sqrt(fmean(value * value for value in values)),
        fmean(abs(value) for value in values),
        max(abs(value) for value in values),
    )


def fit_linear_calibration(
    observed: MeasurementBatch,
    reference: MeasurementBatch,
    config: CalibrationFitConfig,
) -> CalibrationFitResult:
    """Fit reference = scale * observed + offset with full lineage."""

    if not isinstance(observed, MeasurementBatch):
        raise ValidationError("observed must be a MeasurementBatch")
    if not isinstance(reference, MeasurementBatch):
        raise ValidationError("reference must be a MeasurementBatch")
    if not isinstance(config, CalibrationFitConfig):
        raise ValidationError("config must be a CalibrationFitConfig")
    points = _paired_points(observed, reference, config)
    included = tuple(
        value for value in points if value.disposition is PointDisposition.INCLUDED
    )
    missing: list[str] = []
    if len(included) < config.minimum_included_points:
        missing.append(
            f"included-points:{len(included)}/{config.minimum_included_points}"
        )
    observed_values = tuple(
        value.observed_decision.normalized_value for value in included
    )
    distinct = len(set(observed_values))
    if distinct < 2:
        missing.append(f"distinct-observed-values:{distinct}/2")
    if missing:
        return CalibrationFitResult(
            config,
            observed.evidence_source,
            reference.evidence_source,
            points,
            missing_requirements=tuple(missing),
        )
    x_values = tuple(cast(float, value) for value in observed_values)
    y_values = tuple(
        cast(float, value.reference_decision.normalized_value) for value in included
    )
    mean_x = fmean(x_values)
    mean_y = fmean(y_values)
    denominator = sum((value - mean_x) ** 2 for value in x_values)
    scale = (
        sum(
            (x_value - mean_x) * (y_value - mean_y)
            for x_value, y_value in zip(x_values, y_values, strict=True)
        )
        / denominator
    )
    offset = mean_y - scale * mean_x
    if scale == 0:
        raise ValidationError("derived calibration scale cannot be zero")
    calibrated = tuple(scale * value + offset for value in x_values)
    before_errors = tuple(
        observed_value - reference_value
        for observed_value, reference_value in zip(x_values, y_values, strict=True)
    )
    after_errors = tuple(
        calibrated_value - reference_value
        for calibrated_value, reference_value in zip(calibrated, y_values, strict=True)
    )
    before_rmse, before_mae, before_max = _errors(before_errors)
    after_rmse, after_mae, after_max = _errors(after_errors)
    included_ids = {value.sequence: index for index, value in enumerate(included)}
    fitted_points = tuple(
        CalibrationPointResult(
            point.sequence,
            point.observed_decision,
            point.reference_decision,
            point.disposition,
            point.exclusion_reasons,
            calibrated_value=calibrated[included_ids[point.sequence]],
            before_error=before_errors[included_ids[point.sequence]],
            after_error=after_errors[included_ids[point.sequence]],
        )
        if point.sequence in included_ids
        else point
        for point in points
    )
    coefficients = LinearCalibrationCoefficients(
        config.coefficient_id,
        config.coefficient_version,
        scale,
        offset,
        config.normalized_unit,
        observed.evidence_source,
        reference.evidence_source,
        tuple(value.observed_decision.reference.record_id for value in included),
        tuple(value.reference_decision.reference.record_id for value in included),
        tuple(value.observed_decision.reference.raw_record_id for value in included),
        tuple(value.reference_decision.reference.raw_record_id for value in included),
    )
    metrics = CalibrationErrorMetrics(
        len(included),
        before_rmse,
        after_rmse,
        before_mae,
        after_mae,
        before_max,
        after_max,
        config.normalized_unit,
    )
    return CalibrationFitResult(
        config,
        observed.evidence_source,
        reference.evidence_source,
        fitted_points,
        coefficients,
        metrics,
    )


@dataclass(frozen=True, slots=True)
class CalibrationApplicationConfig:
    """Explicit channels and deterministic derived-record namespace."""

    input_channel: str
    output_channel: str
    output_record_prefix: str
    quality_policy: AnalysisQualityPolicy = DEFAULT_ANALYSIS_QUALITY_POLICY
    schema_version: str = CALIBRATION_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("input_channel", "output_channel", "output_record_prefix"):
            _identifier(name, getattr(self, name))
        if self.input_channel == self.output_channel:
            raise ValidationError("input and output channels must be distinct")
        if not isinstance(self.quality_policy, AnalysisQualityPolicy):
            raise ValidationError("quality_policy must be an AnalysisQualityPolicy")
        if self.schema_version != CALIBRATION_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported calibration analysis schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class CalibrationAppliedPoint:
    """One original decision and optional immutable calibrated Measurement."""

    sequence: int
    original_decision: MeasurementDecision
    calibrated_measurement: Measurement | None
    coefficient_id: str
    coefficient_version: str
    correction: float | None
    schema_version: str = CALIBRATION_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise ValidationError("sequence must be a non-negative integer")
        if not isinstance(self.original_decision, MeasurementDecision):
            raise ValidationError("original_decision must be a MeasurementDecision")
        _identifier("coefficient_id", self.coefficient_id)
        _identifier("coefficient_version", self.coefficient_version)
        included = self.original_decision.disposition is PointDisposition.INCLUDED
        if included != (self.calibrated_measurement is not None):
            raise ValidationError(
                "included decisions require one calibrated Measurement"
            )
        if included != (self.correction is not None):
            raise ValidationError("included decisions require one correction")
        if self.calibrated_measurement is not None:
            calibrated = self.calibrated_measurement
            if (
                calibrated.raw_record_id
                != self.original_decision.reference.raw_record_id
            ):
                raise ValidationError(
                    "calibrated Measurement must preserve raw_record_id"
                )
            if calibrated.source is not self.original_decision.reference.source:
                raise ValidationError(
                    "calibrated Measurement must preserve evidence source"
                )
            object.__setattr__(
                self, "correction", _finite("correction", self.correction)
            )
        if self.schema_version != CALIBRATION_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported calibration analysis schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class CalibrationApplicationResult:
    """Original decisions and derived records without overwriting evidence."""

    config: CalibrationApplicationConfig
    coefficients: LinearCalibrationCoefficients
    evidence_source: EvidenceSource
    points: tuple[CalibrationAppliedPoint, ...]
    missing_requirements: tuple[str, ...] = ()
    schema_version: str = CALIBRATION_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.config, CalibrationApplicationConfig):
            raise ValidationError("config must be a CalibrationApplicationConfig")
        if not isinstance(self.coefficients, LinearCalibrationCoefficients):
            raise ValidationError("coefficients must be LinearCalibrationCoefficients")
        if not isinstance(self.evidence_source, EvidenceSource):
            raise ValidationError("evidence_source must be an EvidenceSource")
        points = tuple(self.points)
        if not points or not all(
            isinstance(value, CalibrationAppliedPoint) for value in points
        ):
            raise ValidationError("points must contain CalibrationAppliedPoint values")
        if tuple(value.sequence for value in points) != tuple(range(len(points))):
            raise ValidationError("point sequences must be contiguous from zero")
        if any(
            value.original_decision.reference.source is not self.evidence_source
            for value in points
        ):
            raise ValidationError("all application points must match evidence_source")
        object.__setattr__(self, "points", points)
        missing = tuple(self.missing_requirements)
        if not all(isinstance(value, str) and value for value in missing) or len(
            missing
        ) != len(set(missing)):
            raise ValidationError("missing_requirements must contain unique strings")
        expected_missing = (
            ()
            if all(value.calibrated_measurement is not None for value in points)
            else (f"calibrated-points:{self.calibrated_points}/{len(points)}",)
        )
        if missing != expected_missing:
            raise ValidationError("missing requirements must match derived records")
        object.__setattr__(self, "missing_requirements", missing)
        if self.schema_version != CALIBRATION_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported calibration analysis schema: {self.schema_version}"
            )

    @property
    def calibrated_points(self) -> int:
        return sum(value.calibrated_measurement is not None for value in self.points)

    @property
    def is_complete(self) -> bool:
        return not self.missing_requirements


def apply_linear_calibration(
    batch: MeasurementBatch,
    coefficients: LinearCalibrationCoefficients,
    config: CalibrationApplicationConfig,
) -> CalibrationApplicationResult:
    """Create derived records while preserving raw IDs, source, and originals."""

    if not isinstance(batch, MeasurementBatch):
        raise ValidationError("batch must be a MeasurementBatch")
    if not isinstance(coefficients, LinearCalibrationCoefficients):
        raise ValidationError("coefficients must be LinearCalibrationCoefficients")
    if not isinstance(config, CalibrationApplicationConfig):
        raise ValidationError("config must be a CalibrationApplicationConfig")
    points: list[CalibrationAppliedPoint] = []
    for sequence, measurement in enumerate(batch.measurements):
        if measurement.channel != config.input_channel:
            raise ValidationError(
                "measurement channel does not match application config"
            )
        decision = assess_voltage_measurement(
            measurement,
            config.quality_policy,
            target_unit=coefficients.unit,
        )
        derived: Measurement | None = None
        correction: float | None = None
        if decision.disposition is PointDisposition.INCLUDED:
            original_value = cast(float, decision.normalized_value)
            calibrated_value = coefficients.apply(original_value)
            correction = calibrated_value - original_value
            derived = Measurement(
                record_id=f"{config.output_record_prefix}:{sequence}:{measurement.record_id}",
                raw_record_id=measurement.raw_record_id,
                timestamp=measurement.timestamp,
                channel=config.output_channel,
                value=calibrated_value,
                unit=coefficients.unit,
                status=measurement.status,
                source=measurement.source,
                quality_flags=measurement.quality_flags,
            )
        points.append(
            CalibrationAppliedPoint(
                sequence,
                decision,
                derived,
                coefficients.coefficient_id,
                coefficients.coefficient_version,
                correction,
            )
        )
    calibrated_count = sum(value.calibrated_measurement is not None for value in points)
    missing = (
        ()
        if calibrated_count == len(points)
        else (f"calibrated-points:{calibrated_count}/{len(points)}",)
    )
    return CalibrationApplicationResult(
        config,
        coefficients,
        batch.evidence_source,
        tuple(points),
        missing,
    )


__all__ = [
    "CALIBRATION_ANALYSIS_SCHEMA_VERSION",
    "CALIBRATION_METHOD",
    "CalibrationApplicationConfig",
    "CalibrationApplicationResult",
    "CalibrationAppliedPoint",
    "CalibrationErrorMetrics",
    "CalibrationFitConfig",
    "CalibrationFitResult",
    "CalibrationPointExclusionReason",
    "CalibrationPointResult",
    "LinearCalibrationCoefficients",
    "apply_linear_calibration",
    "fit_linear_calibration",
]
