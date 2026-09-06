"""Strict, bounded persistence for versioned linear calibration coefficients."""

from __future__ import annotations

import json
from enum import Enum
from os import PathLike
from pathlib import Path
from typing import TypeVar, cast

from analog_validation.analysis import (
    CALIBRATION_ANALYSIS_SCHEMA_VERSION,
    CALIBRATION_METHOD,
    LinearCalibrationCoefficients,
)
from analog_validation.domain import EvidenceSource, MeasurementUnit
from analog_validation.errors import ValidationError

from ._files import read_bounded_utf8, write_utf8_atomic
from .errors import (
    ResultExportFormatError,
    ResultExportLimitError,
    UnsupportedResultExportVersion,
)
from .json_v1 import parse_json_object

CALIBRATION_COEFFICIENTS_SCHEMA_VERSION = "calibration-coefficients.v1"
MAX_CALIBRATION_COEFFICIENT_BYTES = 262_144

_EnumT = TypeVar("_EnumT", bound=Enum)


def calibration_coefficients_to_dict(
    coefficients: LinearCalibrationCoefficients,
) -> dict[str, object]:
    """Map validated coefficients to the exact v1 JSON document shape."""

    if not isinstance(coefficients, LinearCalibrationCoefficients):
        raise ValidationError("coefficients must be LinearCalibrationCoefficients")
    return {
        "schema_version": CALIBRATION_COEFFICIENTS_SCHEMA_VERSION,
        "analysis_schema_version": coefficients.schema_version,
        "coefficient_id": coefficients.coefficient_id,
        "coefficient_version": coefficients.coefficient_version,
        "method": coefficients.method,
        "scale": coefficients.scale,
        "offset": coefficients.offset,
        "unit": coefficients.unit.value,
        "observed_source": coefficients.observed_source.value,
        "reference_source": coefficients.reference_source.value,
        "lineage": {
            "observed_record_ids": list(coefficients.observed_record_ids),
            "reference_record_ids": list(coefficients.reference_record_ids),
            "observed_raw_record_ids": list(coefficients.observed_raw_record_ids),
            "reference_raw_record_ids": list(coefficients.reference_raw_record_ids),
        },
    }


def dump_calibration_coefficients_json(
    coefficients: LinearCalibrationCoefficients,
) -> str:
    """Serialize one coefficient set deterministically without non-finite values."""

    return (
        json.dumps(
            calibration_coefficients_to_dict(coefficients),
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            separators=(",", ": "),
        )
        + "\n"
    )


def _object(name: str, value: object, keys: tuple[str, ...]) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ResultExportFormatError(f"{name} must be an object")
    if set(value) != set(keys):
        raise ResultExportFormatError(f"{name} fields do not match the schema")
    return cast(dict[str, object], value)


def _text(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise ResultExportFormatError(f"{name} must be a string")
    return value


def _number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ResultExportFormatError(f"{name} must be numeric")
    return float(value)


def _string_array(name: str, value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ResultExportFormatError(f"{name} must be an array of strings")
    return tuple(value)


def _enum(name: str, enum_type: type[_EnumT], value: object) -> _EnumT:
    text = _text(name, value)
    try:
        return enum_type(text)
    except ValueError as error:
        raise ResultExportFormatError(f"{name} has an unsupported value") from error


def calibration_coefficients_from_dict(
    document: object,
) -> LinearCalibrationCoefficients:
    """Validate and rebuild a coefficient set without changing its provenance."""

    root = _object(
        "coefficient document",
        document,
        (
            "schema_version",
            "analysis_schema_version",
            "coefficient_id",
            "coefficient_version",
            "method",
            "scale",
            "offset",
            "unit",
            "observed_source",
            "reference_source",
            "lineage",
        ),
    )
    version = _text("schema_version", root["schema_version"])
    if version != CALIBRATION_COEFFICIENTS_SCHEMA_VERSION:
        raise UnsupportedResultExportVersion(
            f"unsupported calibration coefficient schema: {version}"
        )
    analysis_version = _text("analysis_schema_version", root["analysis_schema_version"])
    if analysis_version != CALIBRATION_ANALYSIS_SCHEMA_VERSION:
        raise ResultExportFormatError(
            f"unsupported calibration analysis schema: {analysis_version}"
        )
    method = _text("method", root["method"])
    if method != CALIBRATION_METHOD:
        raise ResultExportFormatError(f"unsupported calibration method: {method}")
    lineage = _object(
        "lineage",
        root["lineage"],
        (
            "observed_record_ids",
            "reference_record_ids",
            "observed_raw_record_ids",
            "reference_raw_record_ids",
        ),
    )
    try:
        return LinearCalibrationCoefficients(
            _text("coefficient_id", root["coefficient_id"]),
            _text("coefficient_version", root["coefficient_version"]),
            _number("scale", root["scale"]),
            _number("offset", root["offset"]),
            _enum("unit", MeasurementUnit, root["unit"]),
            _enum("observed_source", EvidenceSource, root["observed_source"]),
            _enum("reference_source", EvidenceSource, root["reference_source"]),
            _string_array("observed_record_ids", lineage["observed_record_ids"]),
            _string_array("reference_record_ids", lineage["reference_record_ids"]),
            _string_array(
                "observed_raw_record_ids", lineage["observed_raw_record_ids"]
            ),
            _string_array(
                "reference_raw_record_ids", lineage["reference_raw_record_ids"]
            ),
            method,
            analysis_version,
        )
    except ValidationError as error:
        raise ResultExportFormatError(
            "coefficient document violates calibration domain rules"
        ) from error


def parse_calibration_coefficients_json(
    text: str,
) -> LinearCalibrationCoefficients:
    """Parse one bounded strict coefficient JSON document."""

    if not isinstance(text, str):
        raise ResultExportFormatError("coefficient JSON content must be a string")
    try:
        size = len(text.encode("utf-8"))
    except UnicodeEncodeError as error:
        raise ResultExportFormatError(
            "coefficient JSON content must be valid UTF-8 text"
        ) from error
    if size > MAX_CALIBRATION_COEFFICIENT_BYTES:
        raise ResultExportLimitError("coefficient JSON exceeds the byte limit")
    if "\x00" in text:
        raise ResultExportFormatError("coefficient JSON cannot contain NUL")
    return calibration_coefficients_from_dict(parse_json_object(text))


def load_calibration_coefficients_json(
    path: str | PathLike[str],
) -> LinearCalibrationCoefficients:
    """Read and validate one bounded local coefficient file."""

    return parse_calibration_coefficients_json(
        read_bounded_utf8(path, maximum_bytes=MAX_CALIBRATION_COEFFICIENT_BYTES)
    )


def write_calibration_coefficients_json(
    path: str | PathLike[str],
    coefficients: LinearCalibrationCoefficients,
    *,
    overwrite: bool = False,
) -> Path:
    """Atomically publish coefficients; reject an existing path by default."""

    return write_utf8_atomic(
        path,
        dump_calibration_coefficients_json(coefficients),
        overwrite=overwrite,
    )


__all__ = [
    "CALIBRATION_COEFFICIENTS_SCHEMA_VERSION",
    "MAX_CALIBRATION_COEFFICIENT_BYTES",
    "calibration_coefficients_from_dict",
    "calibration_coefficients_to_dict",
    "dump_calibration_coefficients_json",
    "load_calibration_coefficients_json",
    "parse_calibration_coefficients_json",
    "write_calibration_coefficients_json",
]
