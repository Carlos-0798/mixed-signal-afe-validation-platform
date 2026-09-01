"""Versioned test-run metadata and conclusion semantics."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import cast

from analog_validation.errors import ValidationError

from .enums import EvidenceSource, TestRunOutcome

TEST_RUN_SCHEMA_VERSION = "test-run.v1"


def _require_identifier(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{name} must be a non-empty string")
    if value != value.strip():
        raise ValidationError(f"{name} must not have surrounding whitespace")
    return value


def _freeze_identifiers(name: str, values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ValidationError(f"{name} must be an iterable")
    frozen: tuple[object, ...] = tuple(values)
    for value in frozen:
        _require_identifier(name, value)
    if len(frozen) != len(set(frozen)):
        raise ValidationError(f"{name} cannot contain duplicates")
    return cast(tuple[str, ...], frozen)


def _utc_datetime(name: str, value: object) -> datetime:
    if not isinstance(value, datetime):
        raise ValidationError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError(f"{name} must include a timezone")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class TestRunMetadata:
    """Reproducibility information for one finalized test attempt."""

    run_id: str
    test_type: str
    configuration_id: str
    configuration_version: str
    started_at: datetime
    ended_at: datetime
    software_version: str
    device_id: str
    profile_name: str
    profile_version: str
    evidence_source: EvidenceSource
    input_record_ids: tuple[str, ...] = ()
    schema_version: str = TEST_RUN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "run_id",
            "test_type",
            "configuration_id",
            "configuration_version",
            "software_version",
            "device_id",
            "profile_name",
            "profile_version",
        ):
            _require_identifier(name, getattr(self, name))

        started_at = _utc_datetime("started_at", self.started_at)
        ended_at = _utc_datetime("ended_at", self.ended_at)
        if ended_at < started_at:
            raise ValidationError("ended_at cannot be earlier than started_at")
        object.__setattr__(self, "started_at", started_at)
        object.__setattr__(self, "ended_at", ended_at)

        if not isinstance(self.evidence_source, EvidenceSource):
            raise ValidationError("evidence_source must be a supported EvidenceSource")
        object.__setattr__(
            self,
            "input_record_ids",
            _freeze_identifiers("input_record_ids", self.input_record_ids),
        )
        if self.schema_version != TEST_RUN_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported test-run schema version: {self.schema_version}"
            )

    @property
    def duration_seconds(self) -> float:
        """Return the finalized run duration."""

        return (self.ended_at - self.started_at).total_seconds()

    @property
    def is_bench_evidence(self) -> bool:
        """Return whether the run explicitly cites physical bench evidence."""

        return self.evidence_source.is_bench_evidence


@dataclass(frozen=True, slots=True)
class TestRunResult:
    """Final result that cannot disguise missing evidence as PASS."""

    metadata: TestRunMetadata
    outcome: TestRunOutcome
    summary: str
    evidence_record_ids: tuple[str, ...] = ()
    missing_requirements: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, TestRunMetadata):
            raise ValidationError("metadata must be TestRunMetadata")
        if not isinstance(self.outcome, TestRunOutcome):
            raise ValidationError("outcome must be a supported TestRunOutcome")
        _require_identifier("summary", self.summary)
        evidence = _freeze_identifiers("evidence_record_ids", self.evidence_record_ids)
        missing = _freeze_identifiers("missing_requirements", self.missing_requirements)
        object.__setattr__(self, "evidence_record_ids", evidence)
        object.__setattr__(self, "missing_requirements", missing)

        if self.outcome in {TestRunOutcome.PASS, TestRunOutcome.FAIL}:
            if missing:
                raise ValidationError(
                    "complete PASS/FAIL results cannot have missing requirements"
                )
            if not evidence:
                raise ValidationError("complete PASS/FAIL results require evidence")
        elif self.outcome in {
            TestRunOutcome.INCOMPLETE,
            TestRunOutcome.UNSUPPORTED,
        } and not missing:
            raise ValidationError(
                f"{self.outcome.value} result must identify missing requirements"
            )

    @property
    def is_complete(self) -> bool:
        """Return whether evaluation produced a PASS or FAIL conclusion."""

        return self.outcome in {TestRunOutcome.PASS, TestRunOutcome.FAIL}

    @property
    def is_pass(self) -> bool:
        """Return true only for an evidence-backed PASS conclusion."""

        return self.outcome is TestRunOutcome.PASS


__all__ = ["TEST_RUN_SCHEMA_VERSION", "TestRunMetadata", "TestRunResult"]
