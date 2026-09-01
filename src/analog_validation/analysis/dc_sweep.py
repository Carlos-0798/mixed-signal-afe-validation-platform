"""Provenance-aware DC sweep pairing, exclusion, and linear analysis."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import Enum

from analog_validation.domain import (
    EvidenceSource,
    Measurement,
    MeasurementUnit,
)
from analog_validation.errors import ValidationError

from .common import (
    DEFAULT_ANALYSIS_QUALITY_POLICY,
    AnalysisQualityPolicy,
    MeasurementBatch,
    MeasurementDecision,
    PointDisposition,
    assess_voltage_measurement,
)

DC_SWEEP_ANALYSIS_SCHEMA_VERSION = "dc-sweep-analysis.v1"

_VOLTAGE_UNITS = frozenset(
    {MeasurementUnit.VOLT, MeasurementUnit.MILLIVOLT}
)


class DCSweepPointExclusionReason(str, Enum):
    """DC-specific reason a paired point cannot contribute to the fit."""

    INPUT_NOT_INCLUDED = "INPUT_NOT_INCLUDED"
    OUTPUT_NOT_INCLUDED = "OUTPUT_NOT_INCLUDED"
    LOW_SATURATION = "LOW_SATURATION"
    HIGH_SATURATION = "HIGH_SATURATION"


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


def _require_voltage_unit(name: str, value: object) -> MeasurementUnit:
    if not isinstance(value, MeasurementUnit) or value not in _VOLTAGE_UNITS:
        raise ValidationError(f"{name} must be V or mV")
    return value


def _freeze_reasons(
    values: object,
) -> tuple[DCSweepPointExclusionReason, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ValidationError("exclusion_reasons must be an iterable")
    frozen = tuple(values)
    if not all(isinstance(value, DCSweepPointExclusionReason) for value in frozen):
        raise ValidationError(
            "exclusion_reasons contains an unknown DCSweepPointExclusionReason"
        )
    if len(frozen) != len(set(frozen)):
        raise ValidationError("exclusion_reasons cannot contain duplicates")
    return frozen


@dataclass(frozen=True, slots=True)
class DCSweepAnalysisConfig:
    """Versioned channels, normalized unit, saturation limits, and policy."""

    input_channel: str
    output_channel: str
    low_output_limit: float
    high_output_limit: float
    normalized_unit: MeasurementUnit = MeasurementUnit.MILLIVOLT
    minimum_included_points: int = 3
    quality_policy: AnalysisQualityPolicy = DEFAULT_ANALYSIS_QUALITY_POLICY
    schema_version: str = DC_SWEEP_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_identifier("input_channel", self.input_channel)
        _require_identifier("output_channel", self.output_channel)
        if self.input_channel == self.output_channel:
            raise ValidationError("input and output channels must be distinct")
        low = _require_finite_number("low_output_limit", self.low_output_limit)
        high = _require_finite_number("high_output_limit", self.high_output_limit)
        if low >= high:
            raise ValidationError("low_output_limit must be below high_output_limit")
        object.__setattr__(self, "low_output_limit", low)
        object.__setattr__(self, "high_output_limit", high)
        _require_voltage_unit("normalized_unit", self.normalized_unit)
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
        if self.schema_version != DC_SWEEP_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported DC sweep analysis schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class DCSweepPointPair:
    """One ordinal input/output pair before quality and saturation analysis."""

    sequence: int
    input_measurement: Measurement
    output_measurement: Measurement
    schema_version: str = DC_SWEEP_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise ValidationError("sequence must be a non-negative integer")
        if not isinstance(self.input_measurement, Measurement):
            raise ValidationError("input_measurement must be a Measurement")
        if not isinstance(self.output_measurement, Measurement):
            raise ValidationError("output_measurement must be a Measurement")
        if self.input_measurement.record_id == self.output_measurement.record_id:
            raise ValidationError("paired measurements must have distinct record IDs")
        if self.input_measurement.channel == self.output_measurement.channel:
            raise ValidationError("paired measurements must use distinct channels")
        if self.input_measurement.source is not self.output_measurement.source:
            raise ValidationError("paired measurements must use one evidence source")
        if self.schema_version != DC_SWEEP_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported DC sweep analysis schema: {self.schema_version}"
            )

    @property
    def evidence_source(self) -> EvidenceSource:
        """Return the unchanged source shared by the pair."""

        return self.input_measurement.source


@dataclass(frozen=True, slots=True)
class DCSweepPointResult:
    """Complete decision and optional fitted values for one paired point."""

    sequence: int
    input_decision: MeasurementDecision
    output_decision: MeasurementDecision
    disposition: PointDisposition
    exclusion_reasons: tuple[DCSweepPointExclusionReason, ...] = ()
    predicted_output: float | None = None
    residual: float | None = None
    schema_version: str = DC_SWEEP_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise ValidationError("sequence must be a non-negative integer")
        if not isinstance(self.input_decision, MeasurementDecision):
            raise ValidationError("input_decision must be a MeasurementDecision")
        if not isinstance(self.output_decision, MeasurementDecision):
            raise ValidationError("output_decision must be a MeasurementDecision")
        if (
            self.input_decision.reference.source
            is not self.output_decision.reference.source
        ):
            raise ValidationError("point decisions must use one evidence source")
        if (
            self.input_decision.reference.record_id
            == self.output_decision.reference.record_id
        ):
            raise ValidationError("point decisions must use distinct record IDs")
        if (
            self.input_decision.normalized_unit
            is not self.output_decision.normalized_unit
        ):
            raise ValidationError("point decisions must use one normalized unit")
        if not isinstance(self.disposition, PointDisposition):
            raise ValidationError("disposition must be a PointDisposition")
        reasons = _freeze_reasons(self.exclusion_reasons)
        object.__setattr__(self, "exclusion_reasons", reasons)
        predicted = self._optional_finite("predicted_output", self.predicted_output)
        residual = self._optional_finite("residual", self.residual)
        object.__setattr__(self, "predicted_output", predicted)
        object.__setattr__(self, "residual", residual)
        self._validate_consistency(reasons)
        if self.schema_version != DC_SWEEP_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported DC sweep analysis schema: {self.schema_version}"
            )

    @staticmethod
    def _optional_finite(name: str, value: object) -> float | None:
        if value is None:
            return None
        return _require_finite_number(name, value)

    def _validate_consistency(
        self,
        reasons: tuple[DCSweepPointExclusionReason, ...],
    ) -> None:
        input_included = (
            self.input_decision.disposition is PointDisposition.INCLUDED
        )
        output_included = (
            self.output_decision.disposition is PointDisposition.INCLUDED
        )
        if input_included == (
            DCSweepPointExclusionReason.INPUT_NOT_INCLUDED in reasons
        ):
            raise ValidationError(
                "input decision and INPUT_NOT_INCLUDED reason must agree"
            )
        if output_included == (
            DCSweepPointExclusionReason.OUTPUT_NOT_INCLUDED in reasons
        ):
            raise ValidationError(
                "output decision and OUTPUT_NOT_INCLUDED reason must agree"
            )
        any_invalid = any(
            decision.disposition is PointDisposition.INVALID
            for decision in (self.input_decision, self.output_decision)
        )
        if (self.disposition is PointDisposition.INVALID) != any_invalid:
            raise ValidationError(
                "point INVALID disposition must agree with component decisions"
            )
        if self.disposition is PointDisposition.INCLUDED:
            if reasons or not input_included or not output_included:
                raise ValidationError(
                    "INCLUDED point requires two included decisions and no reasons"
                )
        elif not reasons:
            raise ValidationError("excluded or invalid point requires reasons")
        if (
            self.predicted_output is None
        ) != (self.residual is None):
            raise ValidationError(
                "predicted_output and residual must both be present or absent"
            )
        if self.disposition is not PointDisposition.INCLUDED and (
            self.predicted_output is not None or self.residual is not None
        ):
            raise ValidationError(
                "excluded or invalid point cannot contain fitted values"
            )
        saturation_reasons = {
            DCSweepPointExclusionReason.LOW_SATURATION,
            DCSweepPointExclusionReason.HIGH_SATURATION,
        }
        if saturation_reasons.issubset(reasons):
            raise ValidationError(
                "a point cannot be both low- and high-saturated"
            )
        if saturation_reasons.intersection(reasons) and (
            self.output_decision.normalized_value is None
        ):
            raise ValidationError(
                "saturation exclusion requires a finite output value"
            )

    @property
    def evidence_source(self) -> EvidenceSource:
        """Return the unchanged source shared by the two decisions."""

        return self.input_decision.reference.source

    @property
    def normalized_unit(self) -> MeasurementUnit:
        """Return the shared V or mV unit used for fitting."""

        return self.input_decision.normalized_unit


@dataclass(frozen=True, slots=True)
class DCSweepFitResult:
    """Ordinary least-squares metrics for the included DC sweep points."""

    gain: float
    offset: float
    r_squared: float
    rmse: float
    max_abs_residual: float
    used_points: int
    normalized_unit: MeasurementUnit
    schema_version: str = DC_SWEEP_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("gain", "offset", "r_squared", "rmse", "max_abs_residual"):
            object.__setattr__(
                self,
                name,
                _require_finite_number(name, getattr(self, name)),
            )
        if not 0.0 <= self.r_squared <= 1.0:
            raise ValidationError("r_squared must be between zero and one")
        if self.rmse < 0.0 or self.max_abs_residual < 0.0:
            raise ValidationError("residual metrics cannot be negative")
        if (
            isinstance(self.used_points, bool)
            or not isinstance(self.used_points, int)
            or self.used_points < 2
        ):
            raise ValidationError("used_points must be an integer of at least two")
        _require_voltage_unit("normalized_unit", self.normalized_unit)
        if self.schema_version != DC_SWEEP_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported DC sweep analysis schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class DCSweepAnalysisResult:
    """All point decisions plus a fit or explicit missing requirements."""

    config: DCSweepAnalysisConfig
    evidence_source: EvidenceSource
    points: tuple[DCSweepPointResult, ...]
    fit: DCSweepFitResult | None = None
    missing_requirements: tuple[str, ...] = ()
    schema_version: str = DC_SWEEP_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.config, DCSweepAnalysisConfig):
            raise ValidationError("config must be a DCSweepAnalysisConfig")
        if not isinstance(self.evidence_source, EvidenceSource):
            raise ValidationError("evidence_source must be an EvidenceSource")
        values = self.points
        if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
            raise ValidationError("points must be an iterable")
        points = tuple(values)
        if not points:
            raise ValidationError("points cannot be empty")
        if not all(isinstance(point, DCSweepPointResult) for point in points):
            raise ValidationError("points must contain DCSweepPointResult values")
        if tuple(point.sequence for point in points) != tuple(range(len(points))):
            raise ValidationError("point sequence must be contiguous from zero")
        if any(point.evidence_source is not self.evidence_source for point in points):
            raise ValidationError("point sources must match evidence_source")
        if any(
            point.normalized_unit is not self.config.normalized_unit
            for point in points
        ):
            raise ValidationError("point units must match analysis config")
        object.__setattr__(self, "points", points)

        missing_input = self.missing_requirements
        if isinstance(missing_input, (str, bytes)) or not isinstance(
            missing_input, Iterable
        ):
            raise ValidationError("missing_requirements must be an iterable")
        missing = tuple(missing_input)
        for value in missing:
            _require_identifier("missing requirement", value)
        if len(missing) != len(set(missing)):
            raise ValidationError("missing_requirements cannot contain duplicates")
        object.__setattr__(self, "missing_requirements", missing)

        if self.fit is not None and not isinstance(self.fit, DCSweepFitResult):
            raise ValidationError("fit must be a DCSweepFitResult or None")
        if (self.fit is None) == (not missing):
            raise ValidationError(
                "a complete result requires a fit; an incomplete result requires gaps"
            )
        included = tuple(
            point
            for point in points
            if point.disposition is PointDisposition.INCLUDED
        )
        if self.fit is not None:
            if self.fit.used_points != len(included):
                raise ValidationError("fit used_points must match included points")
            if self.fit.used_points < self.config.minimum_included_points:
                raise ValidationError(
                    "fit used_points must satisfy the configured minimum"
                )
            if self.fit.normalized_unit is not self.config.normalized_unit:
                raise ValidationError("fit unit must match analysis config")
            if any(
                point.predicted_output is None or point.residual is None
                for point in included
            ):
                raise ValidationError("complete included points require fitted values")
        elif any(
            point.predicted_output is not None or point.residual is not None
            for point in points
        ):
            raise ValidationError("incomplete analysis cannot contain fitted values")
        if self.schema_version != DC_SWEEP_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported DC sweep analysis schema: {self.schema_version}"
            )

    @property
    def is_complete(self) -> bool:
        """Return whether sufficient data produced a fit, not a PASS/FAIL."""

        return self.fit is not None

    @property
    def included_points(self) -> int:
        """Return the number of points used by a complete fit."""

        return sum(
            point.disposition is PointDisposition.INCLUDED
            for point in self.points
        )

    @property
    def excluded_points(self) -> int:
        """Return the number of finite but excluded paired points."""

        return sum(
            point.disposition is PointDisposition.EXCLUDED
            for point in self.points
        )

    @property
    def invalid_points(self) -> int:
        """Return the number of pairs containing invalid input or output."""

        return sum(
            point.disposition is PointDisposition.INVALID
            for point in self.points
        )


def pair_dc_sweep_measurements(
    batch: MeasurementBatch,
    config: DCSweepAnalysisConfig,
) -> tuple[DCSweepPointPair, ...]:
    """Pair selected input/output channels by their within-channel order."""

    if not isinstance(batch, MeasurementBatch):
        raise ValidationError("batch must be a MeasurementBatch")
    if not isinstance(config, DCSweepAnalysisConfig):
        raise ValidationError("config must be a DCSweepAnalysisConfig")
    allowed_channels = {config.input_channel, config.output_channel}
    unexpected = sorted(
        {value.channel for value in batch.measurements} - allowed_channels
    )
    if unexpected:
        raise ValidationError(
            f"batch contains unexpected channels: {','.join(unexpected)}"
        )
    inputs = tuple(
        value
        for value in batch.measurements
        if value.channel == config.input_channel
    )
    outputs = tuple(
        value
        for value in batch.measurements
        if value.channel == config.output_channel
    )
    if not inputs or not outputs:
        raise ValidationError("batch requires at least one input and output record")
    if len(inputs) != len(outputs):
        raise ValidationError("input and output record counts must match")
    return tuple(
        DCSweepPointPair(index, input_value, output_value)
        for index, (input_value, output_value) in enumerate(zip(inputs, outputs))
    )


def _classify_point(
    pair: DCSweepPointPair,
    config: DCSweepAnalysisConfig,
) -> DCSweepPointResult:
    input_decision = assess_voltage_measurement(
        pair.input_measurement,
        config.quality_policy,
        target_unit=config.normalized_unit,
    )
    output_decision = assess_voltage_measurement(
        pair.output_measurement,
        config.quality_policy,
        target_unit=config.normalized_unit,
    )
    reasons: list[DCSweepPointExclusionReason] = []
    if input_decision.disposition is not PointDisposition.INCLUDED:
        reasons.append(DCSweepPointExclusionReason.INPUT_NOT_INCLUDED)
    if output_decision.disposition is not PointDisposition.INCLUDED:
        reasons.append(DCSweepPointExclusionReason.OUTPUT_NOT_INCLUDED)
    if output_decision.normalized_value is not None:
        if output_decision.normalized_value <= config.low_output_limit:
            reasons.append(DCSweepPointExclusionReason.LOW_SATURATION)
        elif output_decision.normalized_value >= config.high_output_limit:
            reasons.append(DCSweepPointExclusionReason.HIGH_SATURATION)

    decisions = (input_decision, output_decision)
    if any(
        decision.disposition is PointDisposition.INVALID
        for decision in decisions
    ):
        disposition = PointDisposition.INVALID
    elif reasons:
        disposition = PointDisposition.EXCLUDED
    else:
        disposition = PointDisposition.INCLUDED
    return DCSweepPointResult(
        pair.sequence,
        input_decision,
        output_decision,
        disposition,
        tuple(reasons),
    )


def _fit_included_points(
    points: tuple[DCSweepPointResult, ...],
    unit: MeasurementUnit,
) -> tuple[DCSweepFitResult, tuple[DCSweepPointResult, ...]]:
    included = tuple(
        point
        for point in points
        if point.disposition is PointDisposition.INCLUDED
    )
    x_values = tuple(
        float(point.input_decision.normalized_value)  # type: ignore[arg-type]
        for point in included
    )
    y_values = tuple(
        float(point.output_decision.normalized_value)  # type: ignore[arg-type]
        for point in included
    )
    count = len(included)
    mean_x = sum(x_values) / count
    mean_y = sum(y_values) / count
    sxx = sum((value - mean_x) ** 2 for value in x_values)
    if sxx == 0.0:  # pragma: no cover - guarded by distinct-input preflight
        raise ValidationError("included input values must not all be equal")
    sxy = sum(
        (x_value - mean_x) * (y_value - mean_y)
        for x_value, y_value in zip(x_values, y_values)
    )
    gain = sxy / sxx
    offset = mean_y - gain * mean_x
    predictions = tuple(gain * value + offset for value in x_values)
    residuals = tuple(
        actual - predicted
        for actual, predicted in zip(y_values, predictions)
    )
    residual_sum_squares = sum(value**2 for value in residuals)
    total_sum_squares = sum((value - mean_y) ** 2 for value in y_values)
    if total_sum_squares == 0.0:
        r_squared = 1.0 if residual_sum_squares == 0.0 else 0.0
    else:
        r_squared = 1.0 - residual_sum_squares / total_sum_squares
        r_squared = min(1.0, max(0.0, r_squared))
    rmse = math.sqrt(residual_sum_squares / count)
    max_abs_residual = max(abs(value) for value in residuals)
    fit = DCSweepFitResult(
        gain,
        offset,
        r_squared,
        rmse,
        max_abs_residual,
        count,
        unit,
    )
    fitted_values = {
        point.sequence: (prediction, residual)
        for point, prediction, residual in zip(
            included,
            predictions,
            residuals,
        )
    }
    fitted_points = tuple(
        replace(
            point,
            predicted_output=fitted_values[point.sequence][0],
            residual=fitted_values[point.sequence][1],
        )
        if point.sequence in fitted_values
        else point
        for point in points
    )
    return fit, fitted_points


def analyze_dc_sweep(
    batch: MeasurementBatch,
    config: DCSweepAnalysisConfig,
) -> DCSweepAnalysisResult:
    """Pair, classify, and fit one DC sweep without producing PASS/FAIL."""

    pairs = pair_dc_sweep_measurements(batch, config)
    points = tuple(_classify_point(pair, config) for pair in pairs)
    included = tuple(
        point
        for point in points
        if point.disposition is PointDisposition.INCLUDED
    )
    missing: list[str] = []
    if len(included) < config.minimum_included_points:
        missing.append(
            f"included-points:{len(included)}/{config.minimum_included_points}"
        )
    distinct_inputs = len(
        {
            point.input_decision.normalized_value
            for point in included
        }
    )
    if distinct_inputs < 2:
        missing.append(f"distinct-input-values:{distinct_inputs}/2")
    if missing:
        return DCSweepAnalysisResult(
            config,
            batch.evidence_source,
            points,
            missing_requirements=tuple(missing),
        )

    fit, fitted_points = _fit_included_points(points, config.normalized_unit)
    return DCSweepAnalysisResult(
        config,
        batch.evidence_source,
        fitted_points,
        fit=fit,
    )


__all__ = [
    "DC_SWEEP_ANALYSIS_SCHEMA_VERSION",
    "DCSweepAnalysisConfig",
    "DCSweepAnalysisResult",
    "DCSweepFitResult",
    "DCSweepPointExclusionReason",
    "DCSweepPointPair",
    "DCSweepPointResult",
    "analyze_dc_sweep",
    "pair_dc_sweep_measurements",
]
