"""Stable row-oriented CSV v1 wrapper for result-export documents."""

from __future__ import annotations

import csv
import io
import json
from os import PathLike
from pathlib import Path
from typing import cast

from analog_validation.errors import ValidationError

from ._files import read_bounded_utf8, write_utf8_atomic
from .errors import (
    ResultExportFormatError,
    ResultExportLimitError,
    UnsupportedResultExportVersion,
)
from .json_v1 import (
    MAX_RESULT_EXPORT_BYTES,
    parse_json_object,
    result_export_from_dict,
    result_export_to_dict,
)
from .models import RESULT_EXPORT_SCHEMA_VERSION, ResultExportBundle

CSV_RESULT_EXPORT_COLUMNS = (
    "format_version",
    "row_type",
    "row_index",
    "payload",
)
MAX_RESULT_EXPORT_ROWS = 100_000

_ROW_ORDER = {
    "RUN": 0,
    "SCHEMA": 1,
    "CRITERION": 2,
    "METRIC": 3,
    "POINT": 4,
    "LIMITATION": 5,
}


def _payload(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def _rows(bundle: ResultExportBundle) -> list[tuple[str, object]]:
    document = result_export_to_dict(bundle)
    criteria = cast(dict[str, object] | None, document["criteria"])
    criteria_identity = (
        None
        if criteria is None
        else {"id": criteria["id"], "version": criteria["version"]}
    )
    rows: list[tuple[str, object]] = [
        (
            "RUN",
            {
                "test_run": document["test_run"],
                "criteria": criteria_identity,
            },
        )
    ]
    rows.extend(
        ("SCHEMA", value) for value in cast(list[object], document["source_schemas"])
    )
    if criteria is not None:
        rows.extend(
            ("CRITERION", value) for value in cast(list[object], criteria["results"])
        )
    rows.extend(("METRIC", value) for value in cast(list[object], document["metrics"]))
    rows.extend(("POINT", value) for value in cast(list[object], document["points"]))
    rows.extend(
        ("LIMITATION", {"text": value})
        for value in cast(list[object], document["limitations"])
    )
    return rows


def dump_result_export_csv(bundle: ResultExportBundle) -> str:
    """Serialize deterministic rows with one strict JSON payload per row."""

    if not isinstance(bundle, ResultExportBundle):
        raise ValidationError("bundle must be a ResultExportBundle")
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CSV_RESULT_EXPORT_COLUMNS)
    for index, (row_type, payload) in enumerate(_rows(bundle)):
        writer.writerow(
            (RESULT_EXPORT_SCHEMA_VERSION, row_type, str(index), _payload(payload))
        )
    return output.getvalue()


def _payload_object(row_type: str, text: str) -> dict[str, object]:
    value = parse_json_object(text)
    if not isinstance(value, dict):
        raise ResultExportFormatError(f"{row_type} payload must be an object")
    return cast(dict[str, object], value)


def parse_result_export_csv(text: str) -> ResultExportBundle:
    """Parse stable rows, reject reordering/duplicates, and rebuild v1 domain data."""

    if not isinstance(text, str):
        raise ResultExportFormatError("CSV content must be a string")
    try:
        size = len(text.encode("utf-8"))
    except UnicodeEncodeError as error:
        raise ResultExportFormatError("CSV content must be valid UTF-8 text") from error
    if size > MAX_RESULT_EXPORT_BYTES:
        raise ResultExportLimitError("CSV result exceeds the byte limit")
    if "\x00" in text:
        raise ResultExportFormatError("CSV result cannot contain NUL")
    try:
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        header = next(reader, None)
        if header != list(CSV_RESULT_EXPORT_COLUMNS):
            raise ResultExportFormatError("CSV header does not match result-export v1")
        rows = list(reader)
    except ResultExportFormatError:
        raise
    except (csv.Error, UnicodeError) as error:
        raise ResultExportFormatError("CSV result is malformed") from error
    if not rows:
        raise ResultExportFormatError("CSV result must contain a RUN row")
    if len(rows) > MAX_RESULT_EXPORT_ROWS:
        raise ResultExportLimitError("CSV result exceeds the row limit")

    run_payload: dict[str, object] | None = None
    schemas: list[object] = []
    criteria_results: list[object] = []
    metrics: list[object] = []
    points: list[object] = []
    limitations: list[object] = []
    last_order = -1
    for expected_index, row in enumerate(rows):
        if len(row) != len(CSV_RESULT_EXPORT_COLUMNS):
            raise ResultExportFormatError("CSV row has the wrong column count")
        version, row_type, row_index, payload_text = row
        if version != RESULT_EXPORT_SCHEMA_VERSION:
            raise UnsupportedResultExportVersion(
                f"unsupported result export schema: {version}"
            )
        if row_type not in _ROW_ORDER:
            raise ResultExportFormatError(f"unknown CSV row type: {row_type}")
        if row_index != str(expected_index):
            raise ResultExportFormatError(
                "CSV row indexes must be contiguous from zero"
            )
        order = _ROW_ORDER[row_type]
        if order < last_order:
            raise ResultExportFormatError("CSV row sections are out of order")
        last_order = order
        payload = _payload_object(row_type, payload_text)
        if row_type == "RUN":
            if expected_index != 0 or run_payload is not None:
                raise ResultExportFormatError(
                    "CSV must contain exactly one first RUN row"
                )
            if set(payload) != {"test_run", "criteria"}:
                raise ResultExportFormatError(
                    "RUN payload fields do not match the schema"
                )
            run_payload = payload
        elif row_type == "SCHEMA":
            schemas.append(payload)
        elif row_type == "CRITERION":
            criteria_results.append(payload)
        elif row_type == "METRIC":
            metrics.append(payload)
        elif row_type == "POINT":
            points.append(payload)
        else:
            if set(payload) != {"text"}:
                format_error = ResultExportFormatError(
                    "LIMITATION payload fields do not match the schema"
                )
                raise format_error
            limitations.append(payload["text"])
    if run_payload is None:
        raise ResultExportFormatError("CSV result must contain one RUN row")
    criteria = run_payload["criteria"]
    if criteria is not None:
        if not isinstance(criteria, dict) or set(criteria) != {"id", "version"}:
            criteria_error = ResultExportFormatError(
                "RUN criteria fields do not match the schema"
            )
            raise criteria_error
        criteria = {**criteria, "results": criteria_results}
    elif criteria_results:
        raise ResultExportFormatError("criterion rows require criteria identity")
    document = {
        "schema_version": RESULT_EXPORT_SCHEMA_VERSION,
        "test_run": run_payload["test_run"],
        "criteria": criteria,
        "source_schemas": schemas,
        "metrics": metrics,
        "points": points,
        "limitations": limitations,
    }
    return result_export_from_dict(document)


def load_result_export_csv(path: str | PathLike[str]) -> ResultExportBundle:
    """Read and parse one bounded UTF-8 CSV result file."""

    return parse_result_export_csv(
        read_bounded_utf8(path, maximum_bytes=MAX_RESULT_EXPORT_BYTES)
    )


def write_result_export_csv(
    path: str | PathLike[str],
    bundle: ResultExportBundle,
    *,
    overwrite: bool = False,
) -> Path:
    """Atomically write CSV, rejecting an existing destination by default."""

    return write_utf8_atomic(path, dump_result_export_csv(bundle), overwrite=overwrite)


__all__ = [
    "CSV_RESULT_EXPORT_COLUMNS",
    "MAX_RESULT_EXPORT_ROWS",
    "dump_result_export_csv",
    "load_result_export_csv",
    "parse_result_export_csv",
    "write_result_export_csv",
]
