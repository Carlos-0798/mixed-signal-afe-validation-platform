"""Immutable, provenance-aware measurement model."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from analog_validation.errors import ValidationError

from .enums import EvidenceSource, MeasurementStatus, MeasurementUnit, QualityFlag

MEASUREMENT_SCHEMA_VERSION = "measurement.v1"


@dataclass(frozen=True, slots=True)
class Measurement:
    """One versioned measurement without hardware-specific dependencies."""

    record_id: str
    raw_record_id: str
    timestamp: datetime
    channel: str
    value: float | None
    unit: MeasurementUnit
    status: MeasurementStatus
    source: EvidenceSource
    quality_flags: frozenset[QualityFlag] = field(default_factory=frozenset)
    schema_version: str = MEASUREMENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        self._validate_text_identifier("record_id", self.record_id)
        self._validate_text_identifier("raw_record_id", self.raw_record_id)
        self._validate_text_identifier("channel", self.channel)

        if not isinstance(self.timestamp, datetime):
            raise ValidationError("timestamp must be a datetime")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValidationError("timestamp must include a timezone")
        object.__setattr__(self, "timestamp", self.timestamp.astimezone(timezone.utc))

        self._require_enum("unit", self.unit, MeasurementUnit)
        self._require_enum("status", self.status, MeasurementStatus)
        self._require_enum("source", self.source, EvidenceSource)

        try:
            flags = frozenset(self.quality_flags)
        except TypeError as error:
            raise ValidationError("quality_flags must be an iterable") from error
        if not all(isinstance(flag, QualityFlag) for flag in flags):
            raise ValidationError("quality_flags contains an unknown flag")
        object.__setattr__(self, "quality_flags", flags)

        if self.schema_version != MEASUREMENT_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported measurement schema version: {self.schema_version}"
            )

        numeric_value = self._validate_value(self.value)
        object.__setattr__(self, "value", numeric_value)
        self._validate_quality_consistency(numeric_value, flags)

    @staticmethod
    def _validate_text_identifier(name: str, value: object) -> None:
        if not isinstance(value, str) or not value:
            raise ValidationError(f"{name} must be a non-empty string")
        if value != value.strip():
            raise ValidationError(f"{name} must not have surrounding whitespace")

    @staticmethod
    def _require_enum(name: str, value: object, enum_type: type[Enum]) -> None:
        if not isinstance(value, enum_type):
            raise ValidationError(f"{name} must be a supported {enum_type.__name__}")

    @staticmethod
    def _validate_value(value: object) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError("value must be numeric or explicitly missing")
        return float(value)

    def _validate_quality_consistency(
        self,
        value: float | None,
        flags: frozenset[QualityFlag],
    ) -> None:
        is_missing = value is None
        is_non_finite = value is not None and not math.isfinite(value)

        if is_missing != (QualityFlag.MISSING in flags):
            raise ValidationError("missing value and MISSING quality flag must agree")
        if is_non_finite != (QualityFlag.NON_FINITE in flags):
            raise ValidationError(
                "non-finite value and NON_FINITE quality flag must agree"
            )
        if (is_missing or is_non_finite) and self.status is not MeasurementStatus.INVALID:
            raise ValidationError("missing or non-finite values must be INVALID")

        if self.status is MeasurementStatus.VALID and flags:
            raise ValidationError("VALID measurement cannot have quality flags")
        if self.status is MeasurementStatus.SUSPECT and not flags:
            raise ValidationError("SUSPECT measurement requires a quality flag")
        if self.status is MeasurementStatus.INVALID and not flags:
            raise ValidationError("INVALID measurement requires a quality flag")

    @property
    def is_derived(self) -> bool:
        """Return whether this record refers to a different raw record."""

        return self.record_id != self.raw_record_id

    @property
    def is_bench_evidence(self) -> bool:
        """Return whether the explicit source is a physical bench source."""

        return self.source.is_bench_evidence


__all__ = ["MEASUREMENT_SCHEMA_VERSION", "Measurement"]
