"""Presentation-only models copied from finalized result-export bundles."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TypeAlias, cast

from analog_validation import EvidenceSource, TestRunOutcome, __version__
from analog_validation.exports import (
    ResultExportBundle,
    dump_result_export_json,
)

from .errors import (
    ProductReportFormatError,
    ProductReportLimitError,
    ProductRequestError,
)

HUMAN_REPORT_SCHEMA_VERSION = "human-report.v1"
MAX_REPORT_POINTS = 10_000
REPORT_HARDWARE_CLAIM = "NO_NEW_HARDWARE_VALIDATION"

ReportScalar: TypeAlias = str | int | float | bool | None


class ReportChartKind(str, Enum):
    """Supported presentation plots; values do not select analysis code."""

    DC_SWEEP = "DC_SWEEP"
    HYSTERESIS = "HYSTERESIS"
    NONE = "NONE"


def _display_text(value: object, *, fallback: str = "[not printable]") -> str:
    if not isinstance(value, str):
        raise ProductReportFormatError("report text must be a string")
    printable = "".join(
        character if character.isprintable() else " " for character in value
    )
    cleaned = " ".join(printable.split())
    return cleaned or fallback


def _identifier(name: str, value: object) -> str:
    checked = _display_text(value)
    if len(checked) > 1024:
        raise ProductReportLimitError(f"{name} exceeds 1024 display characters")
    return checked


def _sha256(value: object) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ProductReportFormatError(
            "canonical_result_sha256 must have 64 hex digits"
        )
    lowered = value.lower()
    if any(character not in "0123456789abcdef" for character in lowered):
        raise ProductReportFormatError("canonical_result_sha256 must be hexadecimal")
    return lowered


def _scalar(name: str, value: object) -> ReportScalar:
    if value is None or isinstance(value, (str, bool, int)):
        return cast(ReportScalar, value)
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ProductReportFormatError(f"{name} must be a finite report scalar")


def _timestamp(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _freeze(
    name: str,
    values: object,
    expected_type: type[object],
    *,
    allow_empty: bool = True,
) -> tuple[object, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ProductReportFormatError(f"{name} must be an iterable")
    frozen = tuple(values)
    if not allow_empty and not frozen:
        raise ProductReportFormatError(f"{name} cannot be empty")
    if not all(isinstance(value, expected_type) for value in frozen):
        raise ProductReportFormatError(f"{name} contains an invalid value")
    return frozen


def _text_values(
    name: str,
    values: object,
    *,
    allow_empty: bool = True,
) -> tuple[str, ...]:
    frozen = _freeze(name, values, str, allow_empty=allow_empty)
    return tuple(_identifier(name, value) for value in frozen)


@dataclass(frozen=True, slots=True)
class ReportSchemaView:
    """One source schema identity shown in every human report."""

    name: str
    version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _identifier("schema name", self.name))
        object.__setattr__(self, "version", _identifier("schema version", self.version))


@dataclass(frozen=True, slots=True)
class ReportValueView:
    """One already-finalized metric or point value."""

    name: str
    value: ReportScalar
    unit: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _identifier("value name", self.name))
        object.__setattr__(self, "value", _scalar("value", self.value))
        object.__setattr__(self, "unit", _identifier("value unit", self.unit))


@dataclass(frozen=True, slots=True)
class ReportCriterionView:
    """One copied criterion result; this model does not grade it again."""

    name: str
    actual_value: float
    unit: str
    passed: bool
    lower_limit: float | None
    upper_limit: float | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _identifier("criterion name", self.name))
        actual = _scalar("criterion actual_value", self.actual_value)
        if not isinstance(actual, float):
            actual = float(cast(int, actual))
        object.__setattr__(self, "actual_value", actual)
        object.__setattr__(self, "unit", _identifier("criterion unit", self.unit))
        if not isinstance(self.passed, bool):
            raise ProductReportFormatError("criterion passed must be boolean")
        for name in ("lower_limit", "upper_limit"):
            value = getattr(self, name)
            if value is not None:
                checked = _scalar(name, value)
                if isinstance(checked, bool) or not isinstance(checked, (int, float)):
                    raise ProductReportFormatError(f"{name} must be numeric or None")
                object.__setattr__(self, name, float(checked))


@dataclass(frozen=True, slots=True)
class ReportReferenceView:
    """Privacy-bounded record identity copied from one exported point."""

    record_id: str
    raw_record_id: str
    timestamp: str
    channel: str
    source: str

    def __post_init__(self) -> None:
        for name in (
            "record_id",
            "raw_record_id",
            "timestamp",
            "channel",
            "source",
        ):
            object.__setattr__(self, name, _identifier(name, getattr(self, name)))


@dataclass(frozen=True, slots=True)
class ReportPointView:
    """One point copied for tables and display-only plotting."""

    index: int
    label: str
    disposition: str
    references: tuple[ReportReferenceView, ...]
    values: tuple[ReportValueView, ...]
    quality_flags: tuple[str, ...]
    exclusion_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            isinstance(self.index, bool)
            or not isinstance(self.index, int)
            or self.index < 0
        ):
            raise ProductReportFormatError("point index must be a non-negative integer")
        object.__setattr__(self, "label", _identifier("point label", self.label))
        object.__setattr__(
            self, "disposition", _identifier("point disposition", self.disposition)
        )
        references = cast(
            tuple[ReportReferenceView, ...],
            _freeze("point references", self.references, ReportReferenceView),
        )
        values = cast(
            tuple[ReportValueView, ...],
            _freeze("point values", self.values, ReportValueView),
        )
        if len({value.name for value in values}) != len(values):
            raise ProductReportFormatError("point value names cannot repeat")
        object.__setattr__(self, "references", references)
        object.__setattr__(self, "values", values)
        object.__setattr__(
            self, "quality_flags", _text_values("quality_flags", self.quality_flags)
        )
        object.__setattr__(
            self,
            "exclusion_reasons",
            _text_values("exclusion_reasons", self.exclusion_reasons),
        )

    def get_value(self, name: str) -> ReportValueView | None:
        """Return a named copied value without deriving a replacement."""

        if not isinstance(name, str):
            raise ProductRequestError("point value name must be a string")
        return next((value for value in self.values if value.name == name), None)


@dataclass(frozen=True, slots=True)
class HumanReportView:
    """Complete immutable presentation input with no analysis methods."""

    title: str
    canonical_result_sha256: str
    generator_version: str
    input_schema_version: str
    run_id: str
    test_type: str
    configuration_id: str
    configuration_version: str
    started_at: str
    ended_at: str
    input_software_version: str
    device_id: str
    profile_name: str
    profile_version: str
    evidence_source: EvidenceSource
    outcome: TestRunOutcome
    summary: str
    source_schemas: tuple[ReportSchemaView, ...]
    metrics: tuple[ReportValueView, ...]
    points: tuple[ReportPointView, ...]
    limitations: tuple[str, ...]
    missing_requirements: tuple[str, ...]
    not_verified: tuple[str, ...]
    chart_kind: ReportChartKind
    criteria_id: str | None = None
    criteria_version: str | None = None
    criterion_results: tuple[ReportCriterionView, ...] = ()
    schema_version: str = HUMAN_REPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "title",
            "generator_version",
            "input_schema_version",
            "run_id",
            "test_type",
            "configuration_id",
            "configuration_version",
            "started_at",
            "ended_at",
            "input_software_version",
            "device_id",
            "profile_name",
            "profile_version",
            "summary",
        ):
            object.__setattr__(self, name, _identifier(name, getattr(self, name)))
        object.__setattr__(
            self,
            "canonical_result_sha256",
            _sha256(self.canonical_result_sha256),
        )
        if not isinstance(self.evidence_source, EvidenceSource):
            raise ProductReportFormatError("evidence_source must be an EvidenceSource")
        if not isinstance(self.outcome, TestRunOutcome):
            raise ProductReportFormatError("outcome must be a TestRunOutcome")
        if not isinstance(self.chart_kind, ReportChartKind):
            raise ProductReportFormatError("chart_kind must be a ReportChartKind")
        source_schemas = cast(
            tuple[ReportSchemaView, ...],
            _freeze(
                "source_schemas",
                self.source_schemas,
                ReportSchemaView,
                allow_empty=False,
            ),
        )
        metrics = cast(
            tuple[ReportValueView, ...],
            _freeze("metrics", self.metrics, ReportValueView),
        )
        points = cast(
            tuple[ReportPointView, ...],
            _freeze("points", self.points, ReportPointView),
        )
        if len(points) > MAX_REPORT_POINTS:
            raise ProductReportLimitError(
                f"report points exceed the {MAX_REPORT_POINTS} point limit"
            )
        if tuple(point.index for point in points) != tuple(range(len(points))):
            raise ProductReportFormatError("report point indexes must be contiguous")
        criteria = cast(
            tuple[ReportCriterionView, ...],
            _freeze("criterion_results", self.criterion_results, ReportCriterionView),
        )
        object.__setattr__(self, "source_schemas", source_schemas)
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(self, "points", points)
        object.__setattr__(self, "criterion_results", criteria)
        object.__setattr__(
            self,
            "limitations",
            _text_values("limitations", self.limitations, allow_empty=False),
        )
        object.__setattr__(
            self,
            "missing_requirements",
            _text_values("missing_requirements", self.missing_requirements),
        )
        object.__setattr__(
            self,
            "not_verified",
            _text_values("not_verified", self.not_verified, allow_empty=False),
        )
        if (self.criteria_id is None) != (self.criteria_version is None):
            raise ProductReportFormatError(
                "criteria ID and version must be present together"
            )
        if self.criteria_id is not None:
            object.__setattr__(
                self, "criteria_id", _identifier("criteria_id", self.criteria_id)
            )
            object.__setattr__(
                self,
                "criteria_version",
                _identifier("criteria_version", self.criteria_version),
            )
        if criteria and self.criteria_id is None:
            raise ProductReportFormatError("criteria results require criteria identity")
        if self.schema_version != HUMAN_REPORT_SCHEMA_VERSION:
            raise ProductReportFormatError(
                f"unsupported human report schema: {self.schema_version}"
            )

    @property
    def is_bench_evidence(self) -> bool:
        """Mirror only the declared input evidence class."""

        return self.evidence_source.is_bench_evidence


def _chart_kind(bundle: ResultExportBundle) -> ReportChartKind:
    schemas = {schema.name for schema in bundle.source_schemas}
    has_dc = "dc-sweep-analysis" in schemas
    has_hysteresis = "hysteresis-analysis" in schemas
    if has_dc and has_hysteresis:
        raise ProductReportFormatError(
            "one report cannot contain both DC and hysteresis analysis schemas"
        )
    if has_dc:
        return ReportChartKind.DC_SWEEP
    if has_hysteresis:
        return ReportChartKind.HYSTERESIS
    return ReportChartKind.NONE


def _not_verified(source: EvidenceSource) -> tuple[str, ...]:
    values = [
        "Report generation did not acquire new data, drive an output, or validate hardware.",
        "Device identity, wiring, electrical protection, instrument calibration, and long-duration reliability were not independently verified by this report.",
    ]
    if not source.is_bench_evidence:
        values.append("The input result contains no declared physical bench evidence.")
    elif source is EvidenceSource.BENCH_CONTROLLER:
        values.append(
            "Controller telemetry is preserved as controller evidence and is not promoted to direct analog-front-end performance evidence."
        )
    else:
        values.append(
            "Bench-labeled evidence is preserved as declared and was not independently repeated during report generation."
        )
    return tuple(values)


def build_human_report_view(bundle: ResultExportBundle) -> HumanReportView:
    """Copy one finalized result bundle into a presentation-only view."""

    if not isinstance(bundle, ResultExportBundle):
        raise ProductReportFormatError("bundle must be a ResultExportBundle")
    if len(bundle.points) > MAX_REPORT_POINTS:
        raise ProductReportLimitError(
            f"report points exceed the {MAX_REPORT_POINTS} point limit"
        )
    kind = _chart_kind(bundle)
    titles = {
        ReportChartKind.DC_SWEEP: "DC Sweep Validation Report",
        ReportChartKind.HYSTERESIS: "Hysteresis Validation Report",
        ReportChartKind.NONE: "Analog Validation Report",
    }
    result = bundle.test_run_result
    metadata = result.metadata
    canonical = dump_result_export_json(bundle).encode("utf-8")
    return HumanReportView(
        title=titles[kind],
        canonical_result_sha256=hashlib.sha256(canonical).hexdigest(),
        generator_version=__version__,
        input_schema_version=bundle.schema_version,
        run_id=_display_text(metadata.run_id),
        test_type=_display_text(metadata.test_type),
        configuration_id=_display_text(metadata.configuration_id),
        configuration_version=_display_text(metadata.configuration_version),
        started_at=_timestamp(metadata.started_at),
        ended_at=_timestamp(metadata.ended_at),
        input_software_version=_display_text(metadata.software_version),
        device_id=_display_text(metadata.device_id),
        profile_name=_display_text(metadata.profile_name),
        profile_version=_display_text(metadata.profile_version),
        evidence_source=metadata.evidence_source,
        outcome=result.outcome,
        summary=_display_text(result.summary),
        source_schemas=tuple(
            ReportSchemaView(schema.name, schema.version)
            for schema in bundle.source_schemas
        ),
        metrics=tuple(
            ReportValueView(value.name, value.value, value.unit)
            for value in bundle.metrics
        ),
        points=tuple(
            ReportPointView(
                point.index,
                point.label,
                point.disposition.value,
                tuple(
                    ReportReferenceView(
                        reference.record_id,
                        reference.raw_record_id,
                        _timestamp(reference.timestamp),
                        reference.channel,
                        reference.source.value,
                    )
                    for reference in point.references
                ),
                tuple(
                    ReportValueView(value.name, value.value, value.unit)
                    for value in point.values
                ),
                point.quality_flags,
                point.exclusion_reasons,
            )
            for point in bundle.points
        ),
        limitations=tuple(_display_text(value) for value in bundle.limitations),
        missing_requirements=tuple(
            _display_text(value) for value in result.missing_requirements
        ),
        not_verified=_not_verified(metadata.evidence_source),
        chart_kind=kind,
        criteria_id=bundle.criteria_id,
        criteria_version=bundle.criteria_version,
        criterion_results=tuple(
            ReportCriterionView(
                criterion.name,
                criterion.actual_value,
                criterion.unit,
                criterion.passed,
                criterion.lower_limit,
                criterion.upper_limit,
            )
            for criterion in bundle.criterion_results
        ),
    )


__all__ = [
    "HUMAN_REPORT_SCHEMA_VERSION",
    "MAX_REPORT_POINTS",
    "REPORT_HARDWARE_CLAIM",
    "HumanReportView",
    "ReportChartKind",
    "ReportCriterionView",
    "ReportPointView",
    "ReportReferenceView",
    "ReportScalar",
    "ReportSchemaView",
    "ReportValueView",
    "build_human_report_view",
]
