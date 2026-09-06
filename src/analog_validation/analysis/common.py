"""Shared quality, lineage, and unit semantics for formal analyses."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import cast

from analog_validation.domain import (
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
    QualityFlag,
)
from analog_validation.errors import ValidationError

ANALYSIS_COMMON_SCHEMA_VERSION = "analysis-common.v1"

_VOLTAGE_UNITS = frozenset({MeasurementUnit.VOLT, MeasurementUnit.MILLIVOLT})


class PointDisposition(str, Enum):
    """Whether one source record may contribute to an analysis."""

    INCLUDED = "INCLUDED"
    EXCLUDED = "EXCLUDED"
    INVALID = "INVALID"


class PointExclusionReason(str, Enum):
    """Stable, explainable reason a record cannot be used by default."""

    MISSING_VALUE = "MISSING_VALUE"
    NON_FINITE_VALUE = "NON_FINITE_VALUE"
    INVALID_STATUS = "INVALID_STATUS"
    SUSPECT_STATUS = "SUSPECT_STATUS"
    SATURATED = "SATURATED"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    TIME_ANOMALY = "TIME_ANOMALY"
    COMMUNICATION_ERROR = "COMMUNICATION_ERROR"
    DEVICE_FAULT = "DEVICE_FAULT"


_EXCLUSION_REASON_BY_QUALITY_FLAG = {
    QualityFlag.MISSING: PointExclusionReason.MISSING_VALUE,
    QualityFlag.NON_FINITE: PointExclusionReason.NON_FINITE_VALUE,
    QualityFlag.SATURATED: PointExclusionReason.SATURATED,
    QualityFlag.OUT_OF_RANGE: PointExclusionReason.OUT_OF_RANGE,
    QualityFlag.TIME_ANOMALY: PointExclusionReason.TIME_ANOMALY,
    QualityFlag.COMMUNICATION_ERROR: PointExclusionReason.COMMUNICATION_ERROR,
    QualityFlag.DEVICE_FAULT: PointExclusionReason.DEVICE_FAULT,
}


def _require_identifier(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValidationError(f"{name} must be a non-empty stripped string")
    return value


def _require_voltage_unit(name: str, value: object) -> MeasurementUnit:
    if not isinstance(value, MeasurementUnit) or value not in _VOLTAGE_UNITS:
        raise ValidationError(f"{name} must be V or mV")
    return value


def _freeze_enum_set(
    name: str,
    values: object,
    enum_type: type[Enum],
) -> frozenset[Enum]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ValidationError(f"{name} must be an iterable")
    try:
        frozen = frozenset(values)
    except TypeError as error:
        raise ValidationError(f"{name} must contain hashable values") from error
    if not all(isinstance(value, enum_type) for value in frozen):
        raise ValidationError(f"{name} contains an unknown {enum_type.__name__}")
    return frozen


@dataclass(frozen=True, slots=True)
class AnalysisQualityPolicy:
    """Versioned opt-in list for finite SUSPECT measurements.

    The default allows no suspect quality flags. INVALID measurements are
    never eligible regardless of this policy.
    """

    allowed_suspect_flags: frozenset[QualityFlag] = field(default_factory=frozenset)
    schema_version: str = ANALYSIS_COMMON_SCHEMA_VERSION

    def __post_init__(self) -> None:
        flags = cast(
            frozenset[QualityFlag],
            _freeze_enum_set(
                "allowed_suspect_flags",
                self.allowed_suspect_flags,
                QualityFlag,
            ),
        )
        forbidden = flags & {QualityFlag.MISSING, QualityFlag.NON_FINITE}
        if forbidden:
            raise ValidationError(
                "missing and non-finite measurements can never be allowed"
            )
        object.__setattr__(self, "allowed_suspect_flags", flags)
        if self.schema_version != ANALYSIS_COMMON_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported analysis common schema: {self.schema_version}"
            )


DEFAULT_ANALYSIS_QUALITY_POLICY = AnalysisQualityPolicy()


@dataclass(frozen=True, slots=True)
class AnalysisRecordReference:
    """Frozen source identity needed to trace one analysis decision."""

    record_id: str
    raw_record_id: str
    timestamp: datetime
    channel: str
    source: EvidenceSource
    schema_version: str = ANALYSIS_COMMON_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("record_id", "raw_record_id", "channel"):
            _require_identifier(name, getattr(self, name))
        if not isinstance(self.timestamp, datetime):
            raise ValidationError("timestamp must be a datetime")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValidationError("timestamp must include a timezone")
        object.__setattr__(
            self,
            "timestamp",
            self.timestamp.astimezone(timezone.utc),
        )
        if not isinstance(self.source, EvidenceSource):
            raise ValidationError("source must be an EvidenceSource")
        if self.schema_version != ANALYSIS_COMMON_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported analysis common schema: {self.schema_version}"
            )

    @classmethod
    def from_measurement(
        cls,
        measurement: Measurement,
    ) -> AnalysisRecordReference:
        """Copy immutable lineage fields without relabeling the evidence."""

        if not isinstance(measurement, Measurement):
            raise ValidationError("measurement must be a Measurement")
        return cls(
            record_id=measurement.record_id,
            raw_record_id=measurement.raw_record_id,
            timestamp=measurement.timestamp,
            channel=measurement.channel,
            source=measurement.source,
        )

    @property
    def is_derived(self) -> bool:
        """Return whether this record refers to a different raw record."""

        return self.record_id != self.raw_record_id

    @property
    def is_bench_evidence(self) -> bool:
        """Preserve the source's explicit physical-evidence classification."""

        return self.source.is_bench_evidence


@dataclass(frozen=True, slots=True)
class MeasurementBatch:
    """Non-empty, one-source record collection with unique record IDs."""

    measurements: tuple[Measurement, ...]
    schema_version: str = ANALYSIS_COMMON_SCHEMA_VERSION

    def __post_init__(self) -> None:
        values = self.measurements
        if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
            raise ValidationError("measurements must be an iterable")
        frozen = tuple(values)
        if not frozen:
            raise ValidationError("measurements cannot be empty")
        if not all(isinstance(value, Measurement) for value in frozen):
            raise ValidationError("measurements must contain Measurement values")
        record_ids = tuple(value.record_id for value in frozen)
        if len(record_ids) != len(set(record_ids)):
            raise ValidationError("measurement record IDs must be unique")
        if len({value.source for value in frozen}) != 1:
            raise ValidationError("measurements must use one evidence source")
        object.__setattr__(self, "measurements", frozen)
        if self.schema_version != ANALYSIS_COMMON_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported analysis common schema: {self.schema_version}"
            )

    @property
    def evidence_source(self) -> EvidenceSource:
        """Return the explicit source shared by the batch."""

        return self.measurements[0].source

    @property
    def record_ids(self) -> tuple[str, ...]:
        """Return record IDs in original order."""

        return tuple(value.record_id for value in self.measurements)

    @property
    def raw_record_ids(self) -> tuple[str, ...]:
        """Return raw record IDs in original order without deduplication."""

        return tuple(value.raw_record_id for value in self.measurements)

    @property
    def references(self) -> tuple[AnalysisRecordReference, ...]:
        """Return immutable record references in original order."""

        return tuple(
            AnalysisRecordReference.from_measurement(value)
            for value in self.measurements
        )

    @property
    def is_bench_evidence(self) -> bool:
        """Return whether the unchanged batch source is physical evidence."""

        return self.evidence_source.is_bench_evidence


@dataclass(frozen=True, slots=True)
class MeasurementDecision:
    """One explainable decision about a voltage measurement's usability."""

    reference: AnalysisRecordReference
    original_unit: MeasurementUnit
    normalized_value: float | None
    normalized_unit: MeasurementUnit
    status: MeasurementStatus
    observed_quality_flags: frozenset[QualityFlag]
    disposition: PointDisposition
    quality_policy: AnalysisQualityPolicy = DEFAULT_ANALYSIS_QUALITY_POLICY
    exclusion_reasons: tuple[PointExclusionReason, ...] = ()
    schema_version: str = ANALYSIS_COMMON_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.reference, AnalysisRecordReference):
            raise ValidationError("reference must be an AnalysisRecordReference")
        _require_voltage_unit("original_unit", self.original_unit)
        _require_voltage_unit("normalized_unit", self.normalized_unit)
        if self.normalized_value is not None:
            value = self.normalized_value
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValidationError("normalized_value must be numeric or missing")
            value = float(value)
            if not math.isfinite(value):
                raise ValidationError("normalized_value must be finite")
            object.__setattr__(self, "normalized_value", value)
        if not isinstance(self.status, MeasurementStatus):
            raise ValidationError("status must be a MeasurementStatus")
        flags = cast(
            frozenset[QualityFlag],
            _freeze_enum_set(
                "observed_quality_flags",
                self.observed_quality_flags,
                QualityFlag,
            ),
        )
        object.__setattr__(self, "observed_quality_flags", flags)
        if not isinstance(self.disposition, PointDisposition):
            raise ValidationError("disposition must be a PointDisposition")
        if not isinstance(self.quality_policy, AnalysisQualityPolicy):
            raise ValidationError("quality_policy must be an AnalysisQualityPolicy")
        reasons_input = self.exclusion_reasons
        if isinstance(reasons_input, (str, bytes)) or not isinstance(
            reasons_input, Iterable
        ):
            raise ValidationError("exclusion_reasons must be an iterable")
        reasons = tuple(reasons_input)
        if not all(isinstance(reason, PointExclusionReason) for reason in reasons):
            raise ValidationError(
                "exclusion_reasons contains an unknown PointExclusionReason"
            )
        if len(reasons) != len(set(reasons)):
            raise ValidationError("exclusion_reasons cannot contain duplicates")
        object.__setattr__(self, "exclusion_reasons", reasons)
        self._validate_decision_consistency(reasons)
        if self.schema_version != ANALYSIS_COMMON_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported analysis common schema: {self.schema_version}"
            )

    def _validate_decision_consistency(
        self,
        reasons: tuple[PointExclusionReason, ...],
    ) -> None:
        if self.status is MeasurementStatus.VALID and self.observed_quality_flags:
            raise ValidationError("VALID decision cannot have quality flags")
        if (
            self.status is not MeasurementStatus.VALID
            and not self.observed_quality_flags
        ):
            raise ValidationError("SUSPECT/INVALID decision requires quality flags")
        if self.disposition is not PointDisposition.INCLUDED and not reasons:
            raise ValidationError("excluded or invalid decision requires reasons")
        quality_reasons = _quality_reasons(self.observed_quality_flags)
        if self.disposition is PointDisposition.INVALID:
            if self.status is not MeasurementStatus.INVALID:
                raise ValidationError("INVALID disposition requires INVALID status")
            if reasons != (PointExclusionReason.INVALID_STATUS, *quality_reasons):
                raise ValidationError(
                    "INVALID decision reasons must match every quality flag"
                )
        elif self.status is MeasurementStatus.INVALID:
            raise ValidationError("INVALID status requires INVALID disposition")
        if (
            self.disposition is PointDisposition.EXCLUDED
            and self.status is not MeasurementStatus.SUSPECT
        ):
            raise ValidationError("EXCLUDED disposition requires SUSPECT status")
        if self.disposition is PointDisposition.EXCLUDED:
            disallowed_flags = (
                self.observed_quality_flags - self.quality_policy.allowed_suspect_flags
            )
            disallowed_reasons = _quality_reasons(disallowed_flags)
            expected = (
                PointExclusionReason.SUSPECT_STATUS,
                *disallowed_reasons,
            )
            if not disallowed_reasons or reasons != expected:
                raise ValidationError(
                    "EXCLUDED decision reasons must match disallowed quality flags"
                )
        if self.disposition is PointDisposition.INCLUDED:
            if reasons:
                raise ValidationError("INCLUDED decision cannot have exclusion reasons")
            if self.normalized_value is None:
                raise ValidationError("INCLUDED decision requires a finite value")
            if (
                self.status is MeasurementStatus.SUSPECT
                and not self.observed_quality_flags.issubset(
                    self.quality_policy.allowed_suspect_flags
                )
            ):
                raise ValidationError(
                    "INCLUDED suspect decision requires an explicit quality policy"
                )

        unavailable = {
            PointExclusionReason.MISSING_VALUE,
            PointExclusionReason.NON_FINITE_VALUE,
        }
        has_unavailable_reason = bool(unavailable.intersection(reasons))
        if (self.normalized_value is None) != has_unavailable_reason:
            raise ValidationError(
                "missing normalized value and unavailable-value reason must agree"
            )


def normalize_voltage(
    value: float,
    unit: MeasurementUnit,
    target_unit: MeasurementUnit = MeasurementUnit.MILLIVOLT,
) -> float:
    """Convert one finite voltage between V and mV without guessing units."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("value must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValidationError("value must be finite")
    source = _require_voltage_unit("unit", unit)
    target = _require_voltage_unit("target_unit", target_unit)
    if source is target:
        return number
    if source is MeasurementUnit.VOLT:
        return number * 1000.0
    return number / 1000.0


def _quality_reasons(
    flags: frozenset[QualityFlag],
) -> tuple[PointExclusionReason, ...]:
    return tuple(
        _EXCLUSION_REASON_BY_QUALITY_FLAG[flag] for flag in QualityFlag if flag in flags
    )


def assess_voltage_measurement(
    measurement: Measurement,
    policy: AnalysisQualityPolicy = DEFAULT_ANALYSIS_QUALITY_POLICY,
    *,
    target_unit: MeasurementUnit = MeasurementUnit.MILLIVOLT,
) -> MeasurementDecision:
    """Classify one voltage record without changing its value or provenance."""

    if not isinstance(measurement, Measurement):
        raise ValidationError("measurement must be a Measurement")
    if not isinstance(policy, AnalysisQualityPolicy):
        raise ValidationError("policy must be an AnalysisQualityPolicy")
    _require_voltage_unit("measurement unit", measurement.unit)
    target = _require_voltage_unit("target_unit", target_unit)

    normalized: float | None = None
    if measurement.value is not None and math.isfinite(measurement.value):
        normalized = normalize_voltage(
            measurement.value,
            measurement.unit,
            target,
        )

    reasons: tuple[PointExclusionReason, ...]
    if measurement.status is MeasurementStatus.VALID:
        disposition = PointDisposition.INCLUDED
        reasons = ()
    elif measurement.status is MeasurementStatus.INVALID:
        disposition = PointDisposition.INVALID
        reasons = (
            PointExclusionReason.INVALID_STATUS,
            *_quality_reasons(measurement.quality_flags),
        )
    else:
        disallowed = measurement.quality_flags - policy.allowed_suspect_flags
        if disallowed:
            disposition = PointDisposition.EXCLUDED
            reasons = (
                PointExclusionReason.SUSPECT_STATUS,
                *_quality_reasons(disallowed),
            )
        else:
            disposition = PointDisposition.INCLUDED
            reasons = ()

    return MeasurementDecision(
        reference=AnalysisRecordReference.from_measurement(measurement),
        original_unit=measurement.unit,
        normalized_value=normalized,
        normalized_unit=target,
        status=measurement.status,
        observed_quality_flags=measurement.quality_flags,
        disposition=disposition,
        quality_policy=policy,
        exclusion_reasons=reasons,
    )


__all__ = [
    "ANALYSIS_COMMON_SCHEMA_VERSION",
    "DEFAULT_ANALYSIS_QUALITY_POLICY",
    "AnalysisQualityPolicy",
    "AnalysisRecordReference",
    "MeasurementBatch",
    "MeasurementDecision",
    "PointDisposition",
    "PointExclusionReason",
    "assess_voltage_measurement",
    "normalize_voltage",
]
