"""Offline amplitude-ratio and cutoff analysis for explicit frequency points."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from itertools import pairwise
from typing import cast

from analog_validation.domain import (
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
    QualityFlag,
)
from analog_validation.errors import ValidationError

from .common import (
    DEFAULT_ANALYSIS_QUALITY_POLICY,
    AnalysisQualityPolicy,
    AnalysisRecordReference,
    MeasurementBatch,
    MeasurementDecision,
    PointDisposition,
    PointExclusionReason,
    assess_voltage_measurement,
)

FREQUENCY_RESPONSE_ANALYSIS_SCHEMA_VERSION = "frequency-response-analysis.v1"
CUTOFF_INTERPOLATION_METHOD = "linear-db-versus-log10-hz"

_VOLTAGE_UNITS = frozenset({MeasurementUnit.VOLT, MeasurementUnit.MILLIVOLT})
_REASON_BY_FLAG = {
    QualityFlag.MISSING: PointExclusionReason.MISSING_VALUE,
    QualityFlag.NON_FINITE: PointExclusionReason.NON_FINITE_VALUE,
    QualityFlag.SATURATED: PointExclusionReason.SATURATED,
    QualityFlag.OUT_OF_RANGE: PointExclusionReason.OUT_OF_RANGE,
    QualityFlag.TIME_ANOMALY: PointExclusionReason.TIME_ANOMALY,
    QualityFlag.COMMUNICATION_ERROR: PointExclusionReason.COMMUNICATION_ERROR,
    QualityFlag.DEVICE_FAULT: PointExclusionReason.DEVICE_FAULT,
}


class FrequencyPointExclusionReason(str, Enum):
    """Stable reason a frequency-response point cannot enter the result."""

    FREQUENCY_NOT_INCLUDED = "FREQUENCY_NOT_INCLUDED"
    INPUT_NOT_INCLUDED = "INPUT_NOT_INCLUDED"
    OUTPUT_NOT_INCLUDED = "OUTPUT_NOT_INCLUDED"


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


def _quality_reasons(flags: frozenset[QualityFlag]) -> tuple[PointExclusionReason, ...]:
    return tuple(_REASON_BY_FLAG[flag] for flag in QualityFlag if flag in flags)


@dataclass(frozen=True, slots=True)
class FrequencyResponseAnalysisConfig:
    """Explicit channels, unit, quality policy, and cutoff definition."""

    frequency_channel: str
    input_amplitude_channel: str
    output_amplitude_channel: str
    normalized_amplitude_unit: MeasurementUnit = MeasurementUnit.MILLIVOLT
    cutoff_drop_db: float = 3.010299956639812
    minimum_included_points: int = 2
    quality_policy: AnalysisQualityPolicy = DEFAULT_ANALYSIS_QUALITY_POLICY
    schema_version: str = FREQUENCY_RESPONSE_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        channels = (
            self.frequency_channel,
            self.input_amplitude_channel,
            self.output_amplitude_channel,
        )
        for name, value in zip(
            (
                "frequency_channel",
                "input_amplitude_channel",
                "output_amplitude_channel",
            ),
            channels,
            strict=True,
        ):
            _identifier(name, value)
        if len(set(channels)) != 3:
            raise ValidationError("frequency-response channels must be distinct")
        if self.normalized_amplitude_unit not in _VOLTAGE_UNITS:
            raise ValidationError("normalized_amplitude_unit must be V or mV")
        drop = _finite("cutoff_drop_db", self.cutoff_drop_db)
        if drop <= 0:
            raise ValidationError("cutoff_drop_db must be positive")
        object.__setattr__(self, "cutoff_drop_db", drop)
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
        if self.schema_version != FREQUENCY_RESPONSE_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported frequency-response schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class FrequencyMeasurementDecision:
    """Explainable quality decision for one measurement expressed in hertz."""

    reference: AnalysisRecordReference
    frequency_hz: float | None
    status: MeasurementStatus
    observed_quality_flags: frozenset[QualityFlag]
    disposition: PointDisposition
    quality_policy: AnalysisQualityPolicy
    exclusion_reasons: tuple[PointExclusionReason, ...] = ()
    schema_version: str = FREQUENCY_RESPONSE_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.reference, AnalysisRecordReference):
            raise ValidationError("reference must be an AnalysisRecordReference")
        if self.frequency_hz is not None:
            value = _finite("frequency_hz", self.frequency_hz)
            if value <= 0:
                raise ValidationError("frequency_hz must be positive")
            object.__setattr__(self, "frequency_hz", value)
        if not isinstance(self.status, MeasurementStatus):
            raise ValidationError("status must be a MeasurementStatus")
        try:
            flags = frozenset(self.observed_quality_flags)
        except TypeError as error:
            raise ValidationError(
                "observed_quality_flags must be an iterable"
            ) from error
        if not all(isinstance(flag, QualityFlag) for flag in flags):
            raise ValidationError("observed_quality_flags contains an unknown flag")
        object.__setattr__(self, "observed_quality_flags", flags)
        if not isinstance(self.disposition, PointDisposition):
            raise ValidationError("disposition must be a PointDisposition")
        if not isinstance(self.quality_policy, AnalysisQualityPolicy):
            raise ValidationError("quality_policy must be an AnalysisQualityPolicy")
        reasons = tuple(self.exclusion_reasons)
        if not all(isinstance(reason, PointExclusionReason) for reason in reasons):
            raise ValidationError("exclusion_reasons contains an unknown reason")
        if len(reasons) != len(set(reasons)):
            raise ValidationError("exclusion_reasons cannot contain duplicates")
        object.__setattr__(self, "exclusion_reasons", reasons)
        expected_disposition, expected_reasons = _frequency_quality_outcome(
            self.status,
            flags,
            self.quality_policy,
        )
        if self.disposition is not expected_disposition or reasons != expected_reasons:
            raise ValidationError(
                "frequency decision does not match status and quality"
            )
        unavailable = bool(
            {PointExclusionReason.MISSING_VALUE, PointExclusionReason.NON_FINITE_VALUE}
            & set(reasons)
        )
        if (self.frequency_hz is None) != unavailable:
            raise ValidationError("frequency availability must match exclusion reasons")
        if self.schema_version != FREQUENCY_RESPONSE_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported frequency-response schema: {self.schema_version}"
            )


def _frequency_quality_outcome(
    status: MeasurementStatus,
    flags: frozenset[QualityFlag],
    policy: AnalysisQualityPolicy,
) -> tuple[PointDisposition, tuple[PointExclusionReason, ...]]:
    if status is MeasurementStatus.VALID:
        return PointDisposition.INCLUDED, ()
    if status is MeasurementStatus.INVALID:
        return (
            PointDisposition.INVALID,
            (PointExclusionReason.INVALID_STATUS, *_quality_reasons(flags)),
        )
    disallowed = flags - policy.allowed_suspect_flags
    if disallowed:
        return (
            PointDisposition.EXCLUDED,
            (PointExclusionReason.SUSPECT_STATUS, *_quality_reasons(disallowed)),
        )
    return PointDisposition.INCLUDED, ()


def assess_frequency_measurement(
    measurement: Measurement,
    policy: AnalysisQualityPolicy = DEFAULT_ANALYSIS_QUALITY_POLICY,
) -> FrequencyMeasurementDecision:
    """Classify one explicit Hz record without estimating frequency from time."""

    if not isinstance(measurement, Measurement):
        raise ValidationError("measurement must be a Measurement")
    if not isinstance(policy, AnalysisQualityPolicy):
        raise ValidationError("policy must be an AnalysisQualityPolicy")
    if measurement.unit is not MeasurementUnit.HERTZ:
        raise ValidationError("frequency measurement unit must be Hz")
    value: float | None = None
    if measurement.value is not None and math.isfinite(measurement.value):
        value = _finite("frequency", measurement.value)
        if value <= 0:
            raise ValidationError("frequency must be positive")
    disposition, reasons = _frequency_quality_outcome(
        measurement.status,
        measurement.quality_flags,
        policy,
    )
    return FrequencyMeasurementDecision(
        AnalysisRecordReference.from_measurement(measurement),
        value,
        measurement.status,
        measurement.quality_flags,
        disposition,
        policy,
        reasons,
    )


@dataclass(frozen=True, slots=True)
class FrequencyResponsePointResult:
    """One frequency/input/output triple with optional ratio and gain."""

    sequence: int
    frequency_decision: FrequencyMeasurementDecision
    input_decision: MeasurementDecision
    output_decision: MeasurementDecision
    disposition: PointDisposition
    exclusion_reasons: tuple[FrequencyPointExclusionReason, ...] = ()
    amplitude_ratio: float | None = None
    gain_db: float | None = None
    schema_version: str = FREQUENCY_RESPONSE_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise ValidationError("sequence must be a non-negative integer")
        if not isinstance(self.frequency_decision, FrequencyMeasurementDecision):
            raise ValidationError(
                "frequency_decision must be a FrequencyMeasurementDecision"
            )
        if not isinstance(self.input_decision, MeasurementDecision) or not isinstance(
            self.output_decision, MeasurementDecision
        ):
            raise ValidationError(
                "amplitude decisions must be MeasurementDecision values"
            )
        if (
            self.input_decision.normalized_unit
            is not self.output_decision.normalized_unit
        ):
            raise ValidationError("amplitude decisions must use one normalized unit")
        if not isinstance(self.disposition, PointDisposition):
            raise ValidationError("disposition must be a PointDisposition")
        reasons = tuple(self.exclusion_reasons)
        if not all(
            isinstance(reason, FrequencyPointExclusionReason) for reason in reasons
        ):
            raise ValidationError("exclusion_reasons contains an unknown reason")
        if len(reasons) != len(set(reasons)):
            raise ValidationError("exclusion_reasons cannot contain duplicates")
        expected_reasons = _point_reasons(
            self.frequency_decision,
            self.input_decision,
            self.output_decision,
        )
        if reasons != expected_reasons:
            raise ValidationError("point reasons must match component decisions")
        decisions = (
            self.frequency_decision,
            self.input_decision,
            self.output_decision,
        )
        expected_disposition = (
            PointDisposition.INVALID
            if any(value.disposition is PointDisposition.INVALID for value in decisions)
            else PointDisposition.EXCLUDED
            if reasons
            else PointDisposition.INCLUDED
        )
        if self.disposition is not expected_disposition:
            raise ValidationError("point disposition must match component decisions")
        if (self.amplitude_ratio is None) != (self.gain_db is None):
            raise ValidationError(
                "amplitude_ratio and gain_db must be present together"
            )
        if (
            self.disposition is not PointDisposition.INCLUDED
            and self.amplitude_ratio is not None
        ):
            raise ValidationError(
                "excluded points cannot contain response calculations"
            )
        if self.amplitude_ratio is not None:
            ratio = _finite("amplitude_ratio", self.amplitude_ratio)
            if ratio <= 0:
                raise ValidationError("amplitude_ratio must be positive")
            gain = _finite("gain_db", self.gain_db)
            if not math.isclose(gain, 20.0 * math.log10(ratio), abs_tol=1e-12):
                raise ValidationError("gain_db must equal 20*log10(amplitude_ratio)")
            object.__setattr__(self, "amplitude_ratio", ratio)
            object.__setattr__(self, "gain_db", gain)
        if self.schema_version != FREQUENCY_RESPONSE_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported frequency-response schema: {self.schema_version}"
            )

    @property
    def frequency_hz(self) -> float | None:
        return self.frequency_decision.frequency_hz


def _point_reasons(
    frequency: FrequencyMeasurementDecision,
    input_amplitude: MeasurementDecision,
    output_amplitude: MeasurementDecision,
) -> tuple[FrequencyPointExclusionReason, ...]:
    return tuple(
        reason
        for decision, reason in (
            (frequency, FrequencyPointExclusionReason.FREQUENCY_NOT_INCLUDED),
            (input_amplitude, FrequencyPointExclusionReason.INPUT_NOT_INCLUDED),
            (output_amplitude, FrequencyPointExclusionReason.OUTPUT_NOT_INCLUDED),
        )
        if decision.disposition is not PointDisposition.INCLUDED
    )


@dataclass(frozen=True, slots=True)
class FrequencyResponseSummary:
    """Reference gain and one explainably interpolated cutoff frequency."""

    reference_gain_db: float
    cutoff_target_db: float
    cutoff_frequency_hz: float
    included_points: int
    interpolation_method: str = CUTOFF_INTERPOLATION_METHOD
    schema_version: str = FREQUENCY_RESPONSE_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("reference_gain_db", "cutoff_target_db", "cutoff_frequency_hz"):
            object.__setattr__(self, name, _finite(name, getattr(self, name)))
        if self.cutoff_frequency_hz <= 0:
            raise ValidationError("cutoff_frequency_hz must be positive")
        if (
            isinstance(self.included_points, bool)
            or not isinstance(self.included_points, int)
            or self.included_points < 2
        ):
            raise ValidationError("included_points must be an integer of at least two")
        if self.interpolation_method != CUTOFF_INTERPOLATION_METHOD:
            raise ValidationError("unsupported cutoff interpolation method")
        if self.schema_version != FREQUENCY_RESPONSE_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported frequency-response schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class FrequencyResponseAnalysisResult:
    """Point calculations and optional single-crossing cutoff summary."""

    config: FrequencyResponseAnalysisConfig
    evidence_source: EvidenceSource
    points: tuple[FrequencyResponsePointResult, ...]
    summary: FrequencyResponseSummary | None = None
    missing_requirements: tuple[str, ...] = ()
    schema_version: str = FREQUENCY_RESPONSE_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.config, FrequencyResponseAnalysisConfig):
            raise ValidationError("config must be a FrequencyResponseAnalysisConfig")
        if not isinstance(self.evidence_source, EvidenceSource):
            raise ValidationError("evidence_source must be an EvidenceSource")
        points = tuple(self.points)
        if not points or not all(
            isinstance(value, FrequencyResponsePointResult) for value in points
        ):
            raise ValidationError(
                "points must contain FrequencyResponsePointResult values"
            )
        if tuple(value.sequence for value in points) != tuple(range(len(points))):
            raise ValidationError("point sequences must be contiguous from zero")
        references = (
            reference
            for point in points
            for reference in (
                point.frequency_decision.reference,
                point.input_decision.reference,
                point.output_decision.reference,
            )
        )
        if any(value.source is not self.evidence_source for value in references):
            raise ValidationError("all response points must match evidence_source")
        object.__setattr__(self, "points", points)
        missing = tuple(self.missing_requirements)
        if not all(isinstance(value, str) and value for value in missing) or len(
            missing
        ) != len(set(missing)):
            raise ValidationError("missing_requirements must contain unique strings")
        object.__setattr__(self, "missing_requirements", missing)
        if (self.summary is not None) != (not missing):
            raise ValidationError("summary and missing requirements must agree")
        if self.summary is not None:
            if not isinstance(self.summary, FrequencyResponseSummary):
                raise ValidationError("summary must be a FrequencyResponseSummary")
            if self.summary.included_points != self.included_points:
                raise ValidationError("summary point count must match included points")
        if self.schema_version != FREQUENCY_RESPONSE_ANALYSIS_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported frequency-response schema: {self.schema_version}"
            )

    @property
    def included_points(self) -> int:
        return sum(
            value.disposition is PointDisposition.INCLUDED for value in self.points
        )

    @property
    def is_complete(self) -> bool:
        return self.summary is not None


def _validate_batches(
    frequencies: MeasurementBatch,
    inputs: MeasurementBatch,
    outputs: MeasurementBatch,
) -> None:
    batches = (frequencies, inputs, outputs)
    if not all(isinstance(value, MeasurementBatch) for value in batches):
        raise ValidationError(
            "frequency-response inputs must be MeasurementBatch values"
        )
    if len({value.evidence_source for value in batches}) != 1:
        raise ValidationError("frequency-response batches must use one evidence source")
    lengths = {len(value.measurements) for value in batches}
    if len(lengths) != 1:
        raise ValidationError("frequency-response batches must have equal lengths")
    record_ids = tuple(record_id for batch in batches for record_id in batch.record_ids)
    if len(record_ids) != len(set(record_ids)):
        raise ValidationError("frequency-response record IDs must be unique")


def _interpolate_crossings(
    points: tuple[FrequencyResponsePointResult, ...],
    target_db: float,
) -> tuple[float, ...]:
    crossings: list[float] = []
    for left, right in pairwise(points):
        left_gain = cast(float, left.gain_db)
        right_gain = cast(float, right.gain_db)
        left_frequency = cast(float, left.frequency_hz)
        right_frequency = cast(float, right.frequency_hz)
        if math.isclose(left_gain, target_db, abs_tol=1e-12):
            crossing = left_frequency
        elif math.isclose(right_gain, target_db, abs_tol=1e-12):
            crossing = right_frequency
        elif (left_gain - target_db) * (right_gain - target_db) < 0:
            log_left = math.log10(left_frequency)
            crossing = 10.0 ** (
                log_left
                + (target_db - left_gain)
                * (math.log10(right_frequency) - log_left)
                / (right_gain - left_gain)
            )
        else:
            continue
        if not crossings or not math.isclose(crossing, crossings[-1], rel_tol=1e-12):
            crossings.append(crossing)
    return tuple(crossings)


def analyze_frequency_response(
    frequencies: MeasurementBatch,
    input_amplitudes: MeasurementBatch,
    output_amplitudes: MeasurementBatch,
    config: FrequencyResponseAnalysisConfig,
) -> FrequencyResponseAnalysisResult:
    """Analyze provided amplitude points; never sample, FFT, or control hardware."""

    if not isinstance(config, FrequencyResponseAnalysisConfig):
        raise ValidationError("config must be a FrequencyResponseAnalysisConfig")
    _validate_batches(frequencies, input_amplitudes, output_amplitudes)
    points: list[FrequencyResponsePointResult] = []
    for sequence, (frequency, input_amplitude, output_amplitude) in enumerate(
        zip(
            frequencies.measurements,
            input_amplitudes.measurements,
            output_amplitudes.measurements,
            strict=True,
        )
    ):
        if frequency.channel != config.frequency_channel:
            raise ValidationError("frequency channel does not match config")
        if input_amplitude.channel != config.input_amplitude_channel:
            raise ValidationError("input amplitude channel does not match config")
        if output_amplitude.channel != config.output_amplitude_channel:
            raise ValidationError("output amplitude channel does not match config")
        frequency_decision = assess_frequency_measurement(
            frequency,
            config.quality_policy,
        )
        input_decision = assess_voltage_measurement(
            input_amplitude,
            config.quality_policy,
            target_unit=config.normalized_amplitude_unit,
        )
        output_decision = assess_voltage_measurement(
            output_amplitude,
            config.quality_policy,
            target_unit=config.normalized_amplitude_unit,
        )
        reasons = _point_reasons(frequency_decision, input_decision, output_decision)
        decisions = (frequency_decision, input_decision, output_decision)
        disposition = (
            PointDisposition.INVALID
            if any(value.disposition is PointDisposition.INVALID for value in decisions)
            else PointDisposition.EXCLUDED
            if reasons
            else PointDisposition.INCLUDED
        )
        ratio: float | None = None
        gain_db: float | None = None
        if disposition is PointDisposition.INCLUDED:
            input_value = cast(float, input_decision.normalized_value)
            output_value = cast(float, output_decision.normalized_value)
            if input_value <= 0:
                raise ValidationError("input amplitude must be positive")
            ratio = output_value / input_value
            if ratio <= 0 or not math.isfinite(ratio):
                raise ValidationError("amplitude ratio must be finite and positive")
            gain_db = 20.0 * math.log10(ratio)
        points.append(
            FrequencyResponsePointResult(
                sequence,
                frequency_decision,
                input_decision,
                output_decision,
                disposition,
                reasons,
                ratio,
                gain_db,
            )
        )
    included = tuple(
        value for value in points if value.disposition is PointDisposition.INCLUDED
    )
    included_frequencies = tuple(cast(float, value.frequency_hz) for value in included)
    if any(right <= left for left, right in pairwise(included_frequencies)):
        raise ValidationError("included frequencies must be strictly increasing")
    missing: list[str] = []
    if len(included) < config.minimum_included_points:
        missing.append(
            f"included-points:{len(included)}/{config.minimum_included_points}"
        )
    if len(included) != len(points):
        missing.append(f"usable-points:{len(included)}/{len(points)}")
    if missing:
        return FrequencyResponseAnalysisResult(
            config,
            frequencies.evidence_source,
            tuple(points),
            missing_requirements=tuple(missing),
        )
    reference_gain = cast(float, included[0].gain_db)
    cutoff_target = reference_gain - config.cutoff_drop_db
    crossings = _interpolate_crossings(included, cutoff_target)
    if not crossings:
        return FrequencyResponseAnalysisResult(
            config,
            frequencies.evidence_source,
            tuple(points),
            missing_requirements=("cutoff-crossing",),
        )
    if len(crossings) > 1:
        raise ValidationError("multiple cutoff crossings are ambiguous")
    summary = FrequencyResponseSummary(
        reference_gain,
        cutoff_target,
        crossings[0],
        len(included),
    )
    return FrequencyResponseAnalysisResult(
        config,
        frequencies.evidence_source,
        tuple(points),
        summary,
    )


__all__ = [
    "CUTOFF_INTERPOLATION_METHOD",
    "FREQUENCY_RESPONSE_ANALYSIS_SCHEMA_VERSION",
    "FrequencyMeasurementDecision",
    "FrequencyPointExclusionReason",
    "FrequencyResponseAnalysisConfig",
    "FrequencyResponseAnalysisResult",
    "FrequencyResponsePointResult",
    "FrequencyResponseSummary",
    "analyze_frequency_response",
    "assess_frequency_measurement",
]
