"""Bounded, offline voltage-table conversion with explicit units and provenance.

VALID identifies finite, syntactically valid values within the configured range.
It does not assert physical accuracy or promote a file to bench evidence.
"""

from __future__ import annotations

import csv
import hashlib
import io
import math
import re
import unicodedata
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
from typing import Any

from analog_validation.domain import EvidenceSource, MeasurementStatus, MeasurementUnit
from analog_validation.errors import ReplayError
from analog_validation.replay import CsvReplayDataset, CsvReplayRecord

from .errors import ProductRequestError

VOLTAGE_IMPORT_MAPPING_SCHEMA_VERSION = "voltage-import-mapping.v1"
MAX_VOLTAGE_IMPORT_BYTES = 2 * 1024 * 1024
MAX_VOLTAGE_IMPORT_ROWS = 10_000
MAX_VOLTAGE_IMPORT_COLUMNS = 64
MAX_VOLTAGE_IMPORT_CELL_CHARS = 1024
_DELIMITERS = (",", ";", "\t")
_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")
_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])\Z"
)


class VoltageImportError(ProductRequestError):
    """An import request failed, optionally identifying the original CSV cell."""

    def __init__(
        self, message: str, *, row_number: int | None = None, column: str | None = None
    ) -> None:
        self.row_number = row_number
        self.column = column
        location = f"row {row_number}" if row_number is not None else ""
        if column is not None:
            location += f" column {column!r}"
        super().__init__(f"{location.strip()}: {message}" if location else message)


def _delimiter(value: object) -> None:
    if value not in _DELIMITERS:
        raise VoltageImportError("delimiter must be comma, semicolon, or tab")


def _text(value: object, name: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != unicodedata.normalize("NFC", value.strip())
        or len(value) > MAX_VOLTAGE_IMPORT_CELL_CHARS
        or not value.isprintable()
    ):
        raise VoltageImportError(
            f"{name} must be a non-empty printable normalized string"
        )


def _timestamp(
    value: object, *, row: int | None = None, column: str | None = None
) -> datetime:
    if not isinstance(value, str) or _TIMESTAMP.fullmatch(value.strip()) is None:
        raise VoltageImportError(
            "time must be ISO 8601 with seconds and an explicit timezone (Z or ±HH:MM)",
            row_number=row,
            column=column,
        )
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except (ValueError, OverflowError) as error:
        raise VoltageImportError(
            "invalid calendar time", row_number=row, column=column
        ) from error


def _finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VoltageImportError(f"{name} must be a finite number")
    try:
        number = float(value)
    except OverflowError as error:
        raise VoltageImportError(f"{name} must be a finite number") from error
    if not math.isfinite(number):
        raise VoltageImportError(f"{name} must be a finite number")
    return number


@dataclass(frozen=True, slots=True)
class VoltageImportMapping:
    """An explicit, reusable interpretation of selected voltage-table columns."""

    name: str
    time_column: str
    input_column: str
    input_unit: MeasurementUnit
    output_column: str | None = None
    output_unit: MeasurementUnit | None = None
    time_mode: str = "timestamp"
    start_time_utc: str | None = None
    delimiter: str = ","
    minimum_mv: float = 0.0
    maximum_mv: float = 3300.0
    schema_version: str = VOLTAGE_IMPORT_MAPPING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != VOLTAGE_IMPORT_MAPPING_SCHEMA_VERSION:
            raise VoltageImportError(
                "unsupported voltage import mapping schema_version"
            )
        _text(self.name, "name")
        if len(self.name) > 256:
            raise VoltageImportError("name must contain at most 256 characters")
        columns = [self.time_column, self.input_column]
        if (self.output_column is None) != (self.output_unit is None):
            raise VoltageImportError(
                "output_column and output_unit must be provided together"
            )
        if self.output_column is not None:
            columns.append(self.output_column)
        for column in columns:
            _text(column, "column")
        if len(set(columns)) != len(columns):
            raise VoltageImportError("time, input, and output columns must be distinct")
        units = [self.input_unit]
        if self.output_unit is not None:
            units.append(self.output_unit)
        for unit in units:
            if not isinstance(unit, MeasurementUnit) or unit not in (
                MeasurementUnit.VOLT,
                MeasurementUnit.MILLIVOLT,
            ):
                raise VoltageImportError(
                    "voltage units must be MeasurementUnit.VOLT or MILLIVOLT"
                )
        _delimiter(self.delimiter)
        minimum = _finite(self.minimum_mv, "minimum_mv")
        maximum = _finite(self.maximum_mv, "maximum_mv")
        if minimum >= maximum:
            raise VoltageImportError("minimum_mv must be less than maximum_mv")
        object.__setattr__(self, "minimum_mv", minimum)
        object.__setattr__(self, "maximum_mv", maximum)
        if self.time_mode == "elapsed_seconds":
            _timestamp(self.start_time_utc, column="start_time_utc")
        elif self.time_mode != "timestamp":
            raise VoltageImportError("time_mode must be timestamp or elapsed_seconds")
        elif self.start_time_utc is not None:
            raise VoltageImportError("timestamp mode must not specify start_time_utc")


def _table_parts(
    payload: bytes, delimiter: str
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...], tuple[int, ...]]:
    _delimiter(delimiter)
    if not isinstance(payload, bytes):
        raise VoltageImportError("voltage table input must be immutable bytes")
    if len(payload) > MAX_VOLTAGE_IMPORT_BYTES:
        raise VoltageImportError(
            f"table exceeds the {MAX_VOLTAGE_IMPORT_BYTES}-byte limit"
        )
    try:
        decoded = payload.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as error:
        raise VoltageImportError("table must be valid UTF-8") from error
    if "\x00" in decoded:
        raise VoltageImportError("NUL characters are not allowed")
    reader = csv.reader(
        io.StringIO(decoded, newline=""), delimiter=delimiter, strict=True
    )
    columns: tuple[str, ...] = ()
    rows: list[tuple[str, ...]] = []
    numbers: list[int] = []
    row_number = 1
    try:
        for row in reader:
            if not columns:
                if not row or len(row) > MAX_VOLTAGE_IMPORT_COLUMNS:
                    raise VoltageImportError(
                        "header must contain 1 to 64 columns", row_number=1
                    )
                columns = tuple(
                    unicodedata.normalize("NFC", cell.strip()) for cell in row
                )
                if any(not column for column in columns):
                    raise VoltageImportError(
                        "header names must be non-empty", row_number=1
                    )
                if len(set(columns)) != len(columns):
                    raise VoltageImportError(
                        "header names must be unique after normalization", row_number=1
                    )
            else:
                if len(row) != len(columns):
                    raise VoltageImportError(
                        f"expected exactly {len(columns)} columns",
                        row_number=row_number,
                    )
                rows.append(tuple(row))
                numbers.append(row_number)
                if len(rows) > MAX_VOLTAGE_IMPORT_ROWS:
                    raise VoltageImportError(
                        f"table exceeds the {MAX_VOLTAGE_IMPORT_ROWS}-row limit",
                        row_number=row_number,
                    )
            for index, cell in enumerate(row):
                if len(cell) > MAX_VOLTAGE_IMPORT_CELL_CHARS:
                    raise VoltageImportError(
                        f"cell exceeds {MAX_VOLTAGE_IMPORT_CELL_CHARS} characters",
                        row_number=row_number,
                        column=columns[index],
                    )
            row_number = reader.line_num + 1
    except csv.Error as error:
        raise VoltageImportError(
            f"malformed CSV: {error}", row_number=row_number
        ) from error
    if not columns:
        raise VoltageImportError("table requires a header")
    if not rows:
        raise VoltageImportError("table requires at least one data row")
    return columns, tuple(rows), tuple(numbers)


@dataclass(frozen=True, slots=True)
class TabularImportSource:
    """Immutable preview cells tied to the exact source bytes and row positions."""

    raw_bytes: bytes
    delimiter: str
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    row_numbers: tuple[int, ...]

    def __post_init__(self) -> None:
        expected = _table_parts(self.raw_bytes, self.delimiter)
        if (self.columns, self.rows, self.row_numbers) != expected:
            raise VoltageImportError(
                "source fields must match the parsed immutable source bytes"
            )

    @property
    def source_sha256(self) -> str:
        return hashlib.sha256(self.raw_bytes).hexdigest()


@dataclass(frozen=True, slots=True)
class VoltageImportPreview:
    """A validated conversion ready for explicit local publication."""

    source: TabularImportSource
    mapping: VoltageImportMapping
    dataset: CsvReplayDataset

    @property
    def row_count(self) -> int:
        return len(self.source.rows)


def parse_voltage_table(payload: bytes, *, delimiter: str = ",") -> TabularImportSource:
    """Parse a bounded UTF-8 CSV table without guessing units or accessing files."""
    return TabularImportSource(payload, delimiter, *_table_parts(payload, delimiter))


def _number(value: str, *, row: int, column: str) -> float:
    if _NUMBER.fullmatch(value.strip()) is None:
        raise VoltageImportError(
            "value must be a finite dot-decimal number", row_number=row, column=column
        )
    parsed = float(value.strip())
    if not math.isfinite(parsed):
        raise VoltageImportError("value must be finite", row_number=row, column=column)
    return parsed


def preview_voltage_import(
    source: TabularImportSource,
    mapping: VoltageImportMapping,
    *,
    dataset_id: str = "imported-voltage",
) -> VoltageImportPreview:
    """Convert selected cells to replay records; reject the entire invalid import."""
    if not isinstance(source, TabularImportSource) or not isinstance(
        mapping, VoltageImportMapping
    ):
        raise VoltageImportError("source and mapping must be validated import models")
    if source.delimiter != mapping.delimiter:
        raise VoltageImportError(
            "mapping delimiter must match the parsed table delimiter"
        )
    channels = [("input", mapping.input_column, mapping.input_unit)]
    if mapping.output_column is not None and mapping.output_unit is not None:
        channels.append(("output", mapping.output_column, mapping.output_unit))
    for column in [mapping.time_column] + [item[1] for item in channels]:
        if column not in source.columns:
            raise VoltageImportError(
                "selected column is missing from the source", column=column
            )
    origin = (
        _timestamp(mapping.start_time_utc)
        if mapping.time_mode == "elapsed_seconds"
        else None
    )
    time_index = source.columns.index(mapping.time_column)
    records: list[CsvReplayRecord] = []
    previous: datetime | None = None
    for row, row_number in zip(source.rows, source.row_numbers, strict=True):
        if origin is None:
            timestamp = _timestamp(
                row[time_index], row=row_number, column=mapping.time_column
            )
        else:
            seconds = _number(
                row[time_index], row=row_number, column=mapping.time_column
            )
            if seconds < 0:
                raise VoltageImportError(
                    "elapsed seconds must be nonnegative",
                    row_number=row_number,
                    column=mapping.time_column,
                )
            try:
                timestamp = origin + timedelta(seconds=seconds)
            except OverflowError as error:
                raise VoltageImportError(
                    "elapsed seconds exceed the supported calendar range",
                    row_number=row_number,
                    column=mapping.time_column,
                ) from error
        if previous is not None and timestamp < previous:
            raise VoltageImportError(
                "times must be nondecreasing in UTC",
                row_number=row_number,
                column=mapping.time_column,
            )
        previous = timestamp
        for role, column, unit in channels:
            value = _number(
                row[source.columns.index(column)], row=row_number, column=column
            )
            millivolts = value * (1000.0 if unit is MeasurementUnit.VOLT else 1.0)
            if (
                not math.isfinite(millivolts)
                or not mapping.minimum_mv <= millivolts <= mapping.maximum_mv
            ):
                raise VoltageImportError(
                    f"voltage must be within [{mapping.minimum_mv:g}, {mapping.maximum_mv:g}] mV",
                    row_number=row_number,
                    column=column,
                )
            raw_id = f"row-{row_number}.{role}"
            records.append(
                CsvReplayRecord(
                    record_id=f"import.{raw_id}",
                    raw_record_id=raw_id,
                    timestamp=timestamp,
                    channel=f"afe.ch0.{role}",
                    value=millivolts,
                    unit=MeasurementUnit.MILLIVOLT,
                    status=MeasurementStatus.VALID,
                    declared_source=EvidenceSource.CSV_REPLAY,
                )
            )
    try:
        dataset = CsvReplayDataset(dataset_id, tuple(records), len(records))
    except ReplayError as error:
        raise VoltageImportError(str(error)) from error
    return VoltageImportPreview(source, mapping, dataset)


def mapping_to_dict(mapping: VoltageImportMapping) -> dict[str, Any]:
    """Return a JSON-compatible mapping document with explicit enum strings."""
    if not isinstance(mapping, VoltageImportMapping):
        raise VoltageImportError("mapping must be a VoltageImportMapping")
    document = {field.name: getattr(mapping, field.name) for field in fields(mapping)}
    document["input_unit"] = mapping.input_unit.value
    document["output_unit"] = mapping.output_unit.value if mapping.output_unit else None
    return document


def mapping_from_dict(document: object) -> VoltageImportMapping:
    """Validate a mapping document, rejecting unknown keys and missing identity."""
    if not isinstance(document, dict):
        raise VoltageImportError("mapping document must be an object")
    allowed = {field.name for field in fields(VoltageImportMapping)}
    required = {"schema_version", "name", "time_column", "input_column", "input_unit"}
    if set(document) - allowed:
        raise VoltageImportError("mapping document contains unknown fields")
    if required - set(document):
        raise VoltageImportError("mapping document is missing required fields")
    values = dict(document)
    for key in ("input_unit", "output_unit"):
        value = values.get(key)
        if key == "output_unit" and value is None:
            continue
        if type(value) is not str or value not in ("V", "mV"):
            raise VoltageImportError(f"{key} must be V or mV")
        values[key] = MeasurementUnit(value)
    return VoltageImportMapping(**values)


__all__ = [
    "MAX_VOLTAGE_IMPORT_BYTES",
    "MAX_VOLTAGE_IMPORT_CELL_CHARS",
    "MAX_VOLTAGE_IMPORT_COLUMNS",
    "MAX_VOLTAGE_IMPORT_ROWS",
    "VOLTAGE_IMPORT_MAPPING_SCHEMA_VERSION",
    "TabularImportSource",
    "VoltageImportError",
    "VoltageImportMapping",
    "VoltageImportPreview",
    "mapping_from_dict",
    "mapping_to_dict",
    "parse_voltage_table",
    "preview_voltage_import",
]
