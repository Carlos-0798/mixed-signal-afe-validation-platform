"""Deterministic JSON v1 result serialization and bounded local file access."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from os import PathLike
from pathlib import Path
from typing import Any, cast

from analog_validation.analysis import AnalysisRecordReference, PointDisposition
from analog_validation.domain import (
    EvidenceSource,
    TestRunMetadata,
    TestRunOutcome,
    TestRunResult,
)
from analog_validation.errors import ValidationError

from ._files import read_bounded_utf8, write_utf8_atomic
from .errors import (
    ResultExportFormatError,
    ResultExportLimitError,
    UnsupportedResultExportVersion,
)
from .models import (
    RESULT_EXPORT_SCHEMA_VERSION,
    ExportCriterion,
    ExportPoint,
    ExportScalar,
    ExportSchemaReference,
    ExportValue,
    ResultExportBundle,
)

MAX_RESULT_EXPORT_BYTES = 2_000_000


def _timestamp(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _value_to_dict(value: ExportValue) -> dict[str, object]:
    return {"name": value.name, "value": value.value, "unit": value.unit}


def _criterion_to_dict(value: ExportCriterion) -> dict[str, object]:
    return {
        "name": value.name,
        "actual_value": value.actual_value,
        "unit": value.unit,
        "passed": value.passed,
        "lower_limit": value.lower_limit,
        "upper_limit": value.upper_limit,
    }


def _reference_to_dict(value: AnalysisRecordReference) -> dict[str, object]:
    return {
        "record_id": value.record_id,
        "raw_record_id": value.raw_record_id,
        "timestamp": _timestamp(value.timestamp),
        "channel": value.channel,
        "source": value.source.value,
    }


def _point_to_dict(value: ExportPoint) -> dict[str, object]:
    return {
        "index": value.index,
        "label": value.label,
        "disposition": value.disposition.value,
        "references": [_reference_to_dict(item) for item in value.references],
        "values": [_value_to_dict(item) for item in value.values],
        "quality_flags": list(value.quality_flags),
        "exclusion_reasons": list(value.exclusion_reasons),
    }


def result_export_to_dict(bundle: ResultExportBundle) -> dict[str, object]:
    """Map one validated bundle to the exact ordered JSON document shape."""

    if not isinstance(bundle, ResultExportBundle):
        raise ValidationError("bundle must be a ResultExportBundle")
    result = bundle.test_run_result
    metadata = result.metadata
    criteria: dict[str, object] | None = None
    if bundle.criteria_id is not None and bundle.criteria_version is not None:
        criteria = {
            "id": bundle.criteria_id,
            "version": bundle.criteria_version,
            "results": [
                _criterion_to_dict(value) for value in bundle.criterion_results
            ],
        }
    return {
        "schema_version": bundle.schema_version,
        "test_run": {
            "metadata": {
                "run_id": metadata.run_id,
                "test_type": metadata.test_type,
                "configuration_id": metadata.configuration_id,
                "configuration_version": metadata.configuration_version,
                "started_at": _timestamp(metadata.started_at),
                "ended_at": _timestamp(metadata.ended_at),
                "software_version": metadata.software_version,
                "device_id": metadata.device_id,
                "profile_name": metadata.profile_name,
                "profile_version": metadata.profile_version,
                "evidence_source": metadata.evidence_source.value,
                "input_record_ids": list(metadata.input_record_ids),
                "schema_version": metadata.schema_version,
            },
            "outcome": result.outcome.value,
            "summary": result.summary,
            "evidence_record_ids": list(result.evidence_record_ids),
            "missing_requirements": list(result.missing_requirements),
        },
        "criteria": criteria,
        "source_schemas": [
            {"name": value.name, "version": value.version}
            for value in bundle.source_schemas
        ],
        "metrics": [_value_to_dict(value) for value in bundle.metrics],
        "points": [_point_to_dict(value) for value in bundle.points],
        "limitations": list(bundle.limitations),
    }


def dump_result_export_json(bundle: ResultExportBundle) -> str:
    """Serialize deterministically with strict finite-number behavior."""

    return (
        json.dumps(
            result_export_to_dict(bundle),
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            separators=(",", ": "),
        )
        + "\n"
    )


def _object(
    name: str,
    value: object,
    keys: tuple[str, ...],
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ResultExportFormatError(f"{name} must be an object")
    if set(value) != set(keys):
        raise ResultExportFormatError(f"{name} fields do not match the schema")
    return cast(dict[str, object], value)


def _array(name: str, value: object) -> list[object]:
    if not isinstance(value, list):
        raise ResultExportFormatError(f"{name} must be an array")
    return value


def _text(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise ResultExportFormatError(f"{name} must be a string")
    return value


def _string_array(name: str, value: object) -> tuple[str, ...]:
    values = _array(name, value)
    if not all(isinstance(item, str) for item in values):
        raise ResultExportFormatError(f"{name} must contain strings")
    return tuple(cast(list[str], values))


def _number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ResultExportFormatError(f"{name} must be numeric")
    return float(value)


def _optional_number(name: str, value: object) -> float | None:
    return None if value is None else _number(name, value)


def _datetime(name: str, value: object) -> datetime:
    text = _text(name, value)
    if not text.endswith("Z"):
        raise ResultExportFormatError(f"{name} must be UTC with Z suffix")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as error:
        raise ResultExportFormatError(f"{name} is not a valid timestamp") from error
    return parsed


def _enum(name: str, enum_type: type[Any], value: object) -> Any:
    text = _text(name, value)
    try:
        return enum_type(text)
    except ValueError as error:
        raise ResultExportFormatError(f"{name} has an unsupported value") from error


def _scalar(name: str, value: object) -> ExportScalar:
    if value is None or isinstance(value, (str, bool, int, float)):
        return cast(ExportScalar, value)
    raise ResultExportFormatError(f"{name} must be a JSON scalar")


def _parse_value(value: object) -> ExportValue:
    item = _object("value", value, ("name", "value", "unit"))
    return ExportValue(
        _text("value.name", item["name"]),
        _scalar("value.value", item["value"]),
        _text("value.unit", item["unit"]),
    )


def _parse_criterion(value: object) -> ExportCriterion:
    item = _object(
        "criterion",
        value,
        ("name", "actual_value", "unit", "passed", "lower_limit", "upper_limit"),
    )
    if not isinstance(item["passed"], bool):
        raise ResultExportFormatError("criterion.passed must be a bool")
    return ExportCriterion(
        _text("criterion.name", item["name"]),
        _number("criterion.actual_value", item["actual_value"]),
        _text("criterion.unit", item["unit"]),
        item["passed"],
        _optional_number("criterion.lower_limit", item["lower_limit"]),
        _optional_number("criterion.upper_limit", item["upper_limit"]),
    )


def _parse_reference(value: object) -> AnalysisRecordReference:
    item = _object(
        "reference",
        value,
        ("record_id", "raw_record_id", "timestamp", "channel", "source"),
    )
    return AnalysisRecordReference(
        _text("reference.record_id", item["record_id"]),
        _text("reference.raw_record_id", item["raw_record_id"]),
        _datetime("reference.timestamp", item["timestamp"]),
        _text("reference.channel", item["channel"]),
        _enum("reference.source", EvidenceSource, item["source"]),
    )


def _parse_point(value: object) -> ExportPoint:
    item = _object(
        "point",
        value,
        (
            "index",
            "label",
            "disposition",
            "references",
            "values",
            "quality_flags",
            "exclusion_reasons",
        ),
    )
    index = item["index"]
    if isinstance(index, bool) or not isinstance(index, int):
        raise ResultExportFormatError("point.index must be an integer")
    return ExportPoint(
        index,
        _text("point.label", item["label"]),
        _enum("point.disposition", PointDisposition, item["disposition"]),
        tuple(
            _parse_reference(value)
            for value in _array("references", item["references"])
        ),
        tuple(_parse_value(value) for value in _array("values", item["values"])),
        _string_array("quality_flags", item["quality_flags"]),
        _string_array("exclusion_reasons", item["exclusion_reasons"]),
    )


def _result_export_from_dict(document: object) -> ResultExportBundle:
    root = _object(
        "document",
        document,
        (
            "schema_version",
            "test_run",
            "criteria",
            "source_schemas",
            "metrics",
            "points",
            "limitations",
        ),
    )
    version = _text("schema_version", root["schema_version"])
    if version != RESULT_EXPORT_SCHEMA_VERSION:
        raise UnsupportedResultExportVersion(
            f"unsupported result export schema: {version}"
        )
    test_run = _object(
        "test_run",
        root["test_run"],
        (
            "metadata",
            "outcome",
            "summary",
            "evidence_record_ids",
            "missing_requirements",
        ),
    )
    metadata = _object(
        "metadata",
        test_run["metadata"],
        (
            "run_id",
            "test_type",
            "configuration_id",
            "configuration_version",
            "started_at",
            "ended_at",
            "software_version",
            "device_id",
            "profile_name",
            "profile_version",
            "evidence_source",
            "input_record_ids",
            "schema_version",
        ),
    )
    metadata_model = TestRunMetadata(
        _text("metadata.run_id", metadata["run_id"]),
        _text("metadata.test_type", metadata["test_type"]),
        _text("metadata.configuration_id", metadata["configuration_id"]),
        _text("metadata.configuration_version", metadata["configuration_version"]),
        _datetime("metadata.started_at", metadata["started_at"]),
        _datetime("metadata.ended_at", metadata["ended_at"]),
        _text("metadata.software_version", metadata["software_version"]),
        _text("metadata.device_id", metadata["device_id"]),
        _text("metadata.profile_name", metadata["profile_name"]),
        _text("metadata.profile_version", metadata["profile_version"]),
        _enum("metadata.evidence_source", EvidenceSource, metadata["evidence_source"]),
        _string_array("metadata.input_record_ids", metadata["input_record_ids"]),
        _text("metadata.schema_version", metadata["schema_version"]),
    )
    result = TestRunResult(
        metadata_model,
        _enum("test_run.outcome", TestRunOutcome, test_run["outcome"]),
        _text("test_run.summary", test_run["summary"]),
        _string_array("test_run.evidence_record_ids", test_run["evidence_record_ids"]),
        _string_array(
            "test_run.missing_requirements", test_run["missing_requirements"]
        ),
    )
    criteria_id: str | None = None
    criteria_version: str | None = None
    criterion_results: tuple[ExportCriterion, ...] = ()
    if root["criteria"] is not None:
        criteria = _object("criteria", root["criteria"], ("id", "version", "results"))
        criteria_id = _text("criteria.id", criteria["id"])
        criteria_version = _text("criteria.version", criteria["version"])
        criterion_results = tuple(
            _parse_criterion(value)
            for value in _array("criteria.results", criteria["results"])
        )
    schemas = tuple(
        ExportSchemaReference(
            _text("source schema name", item["name"]),
            _text("source schema version", item["version"]),
        )
        for raw in _array("source_schemas", root["source_schemas"])
        for item in [_object("source schema", raw, ("name", "version"))]
    )
    return ResultExportBundle(
        result,
        schemas,
        tuple(_parse_value(value) for value in _array("metrics", root["metrics"])),
        tuple(_parse_point(value) for value in _array("points", root["points"])),
        _string_array("limitations", root["limitations"]),
        criteria_id,
        criteria_version,
        criterion_results,
    )


def result_export_from_dict(document: object) -> ResultExportBundle:
    """Validate and reconstruct the exact v1 document without source promotion."""

    try:
        return _result_export_from_dict(document)
    except (ResultExportFormatError, UnsupportedResultExportVersion):
        raise
    except ValidationError as error:
        raise ResultExportFormatError(
            "result document violates domain rules"
        ) from error


def _reject_constant(value: str) -> None:
    raise ResultExportFormatError(f"non-finite JSON constant is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ResultExportFormatError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def parse_json_object(text: str) -> object:
    """Parse strict JSON for JSON and CSV payload reuse."""

    try:
        return json.loads(
            text,
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except ResultExportFormatError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        raise ResultExportFormatError("result content is not valid JSON") from error


def parse_result_export_json(text: str) -> ResultExportBundle:
    """Parse one bounded strict v1 JSON result document."""

    if not isinstance(text, str):
        raise ResultExportFormatError("JSON content must be a string")
    try:
        size = len(text.encode("utf-8"))
    except UnicodeEncodeError as error:
        raise ResultExportFormatError(
            "JSON content must be valid UTF-8 text"
        ) from error
    if size > MAX_RESULT_EXPORT_BYTES:
        raise ResultExportLimitError("JSON result exceeds the byte limit")
    if "\x00" in text:
        raise ResultExportFormatError("JSON result cannot contain NUL")
    return result_export_from_dict(parse_json_object(text))


def load_result_export_json(path: str | PathLike[str]) -> ResultExportBundle:
    """Read and parse one bounded UTF-8 JSON result file."""

    return parse_result_export_json(
        read_bounded_utf8(path, maximum_bytes=MAX_RESULT_EXPORT_BYTES)
    )


def write_result_export_json(
    path: str | PathLike[str],
    bundle: ResultExportBundle,
    *,
    overwrite: bool = False,
) -> Path:
    """Atomically write JSON, rejecting an existing destination by default."""

    return write_utf8_atomic(path, dump_result_export_json(bundle), overwrite=overwrite)


__all__ = [
    "MAX_RESULT_EXPORT_BYTES",
    "dump_result_export_json",
    "load_result_export_json",
    "parse_result_export_json",
    "result_export_from_dict",
    "result_export_to_dict",
    "write_result_export_json",
]
