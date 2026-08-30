"""Strict, bounded CSV Replay v1 models and parser."""

from __future__ import annotations

import csv
import io
import math
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from itertools import pairwise
from pathlib import Path
from typing import TypeVar, cast

from analog_validation.domain import (
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
    QualityFlag,
)
from analog_validation.errors import (
    ReplayError,
    ReplayFormatError,
    ReplayLimitError,
    UnsupportedReplayVersion,
    ValidationError,
)

CSV_REPLAY_SCHEMA_VERSION = "csv-replay.v1"
CSV_REPLAY_COLUMNS = (
    "row_type",
    "schema_version",
    "dataset_id",
    "record_id",
    "raw_record_id",
    "timestamp_utc",
    "channel",
    "value",
    "unit",
    "status",
    "source",
    "quality_flags",
    "record_count",
)
MAX_REPLAY_BYTES = 10_485_760
MAX_REPLAY_RECORDS = 100_000
MAX_REPLAY_FIELD_CHARS = 1_024

_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_TIMESTAMP_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z\Z"
)
_NUMBER_PATTERN = re.compile(
    r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?(?:0|[1-9]\d*))?\Z"
)
_NON_FINITE_VALUES = {
    "NaN": math.nan,
    "Infinity": math.inf,
    "-Infinity": -math.inf,
}

E = TypeVar("E", bound=Enum)


def _require_identifier(name: str, value: object) -> str:
    if not isinstance(value, str) or _IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise ReplayFormatError(
            f"{name} must start with an alphanumeric character and contain only "
            "letters, digits, '.', '_', ':', '/', or '-'"
        )
    return value


def _require_schema_version(value: object) -> str:
    if value != CSV_REPLAY_SCHEMA_VERSION:
        raise UnsupportedReplayVersion(f"unsupported CSV replay version: {value}")
    return CSV_REPLAY_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class CsvReplayRecord:
    """One immutable record whose source is only a declaration from a file."""

    record_id: str
    raw_record_id: str
    timestamp: datetime
    channel: str
    value: float | None
    unit: MeasurementUnit
    status: MeasurementStatus
    declared_source: EvidenceSource
    quality_flags: frozenset[QualityFlag] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        _require_identifier("record_id", self.record_id)
        _require_identifier("raw_record_id", self.raw_record_id)
        _require_identifier("channel", self.channel)
        if (
            not isinstance(self.timestamp, datetime)
            or self.timestamp.tzinfo is None
            or self.timestamp.utcoffset() != timedelta(0)
        ):
            raise ReplayFormatError("timestamp must be a timezone-aware UTC datetime")
        try:
            validated = Measurement(
                self.record_id,
                self.raw_record_id,
                self.timestamp,
                self.channel,
                self.value,
                self.unit,
                self.status,
                self.declared_source,
                self.quality_flags,
            )
        except ValidationError as error:
            raise ReplayFormatError(f"invalid replay record: {error}") from error
        object.__setattr__(self, "timestamp", validated.timestamp)
        object.__setattr__(self, "value", validated.value)
        object.__setattr__(self, "quality_flags", validated.quality_flags)


@dataclass(frozen=True, slots=True)
class CsvReplayDataset:
    """Complete immutable dataset proven to contain a matching END record."""

    dataset_id: str
    records: tuple[CsvReplayRecord, ...]
    declared_record_count: int
    schema_version: str = CSV_REPLAY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_identifier("dataset_id", self.dataset_id)
        _require_schema_version(self.schema_version)
        if isinstance(self.records, (str, bytes)) or not isinstance(
            self.records, Iterable
        ):
            raise ReplayFormatError("records must be an iterable")
        frozen: tuple[object, ...] = tuple(self.records)
        if not all(isinstance(record, CsvReplayRecord) for record in frozen):
            raise ReplayFormatError("records must contain CsvReplayRecord values")
        records = cast(tuple[CsvReplayRecord, ...], frozen)
        object.__setattr__(self, "records", records)
        if len(records) > MAX_REPLAY_RECORDS:
            raise ReplayLimitError(
                f"replay exceeds the {MAX_REPLAY_RECORDS}-record limit"
            )
        if (
            isinstance(self.declared_record_count, bool)
            or not isinstance(self.declared_record_count, int)
            or self.declared_record_count < 0
        ):
            raise ReplayFormatError("declared_record_count must be a non-negative integer")
        if self.declared_record_count != len(records):
            raise ReplayFormatError(
                "END record_count does not match the number of DATA records"
            )
        record_ids = [record.record_id for record in records]
        if len(record_ids) != len(set(record_ids)):
            raise ReplayFormatError("DATA record_id values must be unique")
        for previous, current in pairwise(records):
            if current.timestamp < previous.timestamp:
                raise ReplayFormatError(
                    "DATA timestamps must be in nondecreasing UTC order"
                )

    def __len__(self) -> int:
        return len(self.records)

    @property
    def is_complete(self) -> bool:
        """Return true because construction requires a matching END count."""

        return self.declared_record_count == len(self.records)


def _decode_replay_input(text: str | bytes) -> str:
    if isinstance(text, bytes):
        if len(text) > MAX_REPLAY_BYTES:
            raise ReplayLimitError(
                f"replay exceeds the {MAX_REPLAY_BYTES}-byte size limit"
            )
        try:
            decoded = text.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise ReplayFormatError("replay must be valid UTF-8") from error
    elif isinstance(text, str):
        try:
            encoded_length = len(text.encode("utf-8", errors="strict"))
        except UnicodeEncodeError as error:
            raise ReplayFormatError("replay must be valid UTF-8") from error
        if encoded_length > MAX_REPLAY_BYTES:
            raise ReplayLimitError(
                f"replay exceeds the {MAX_REPLAY_BYTES}-byte size limit"
            )
        decoded = text
    else:
        raise ReplayFormatError("replay input must be str or bytes")
    if decoded.startswith("\ufeff"):
        raise ReplayFormatError("UTF-8 BOM is not allowed")
    if "\x00" in decoded:
        raise ReplayFormatError("NUL bytes are not allowed")
    if "\r" in decoded.replace("\r\n", ""):
        raise ReplayFormatError("line endings must be LF or CRLF")
    return decoded


def _read_rows(decoded: str) -> list[list[str]]:
    rows: list[list[str]] = []
    try:
        reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
        for row_number, row in enumerate(reader, start=1):
            if len(row) != len(CSV_REPLAY_COLUMNS):
                raise ReplayFormatError(
                    f"row {row_number} must contain exactly "
                    f"{len(CSV_REPLAY_COLUMNS)} columns"
                )
            for field_value in row:
                if len(field_value) > MAX_REPLAY_FIELD_CHARS:
                    raise ReplayLimitError(
                        f"row {row_number} contains a field longer than "
                        f"{MAX_REPLAY_FIELD_CHARS} characters"
                    )
                if any(ord(character) < 32 for character in field_value):
                    raise ReplayFormatError(
                        f"row {row_number} contains an ASCII control character"
                    )
            rows.append(row)
            if len(rows) > MAX_REPLAY_RECORDS + 3:
                raise ReplayLimitError(
                    f"replay exceeds the {MAX_REPLAY_RECORDS}-record limit"
                )
    except csv.Error as error:
        raise ReplayFormatError(f"malformed CSV: {error}") from error
    return rows


def _require_empty(row: list[str], indices: range, context: str) -> None:
    if any(row[index] for index in indices):
        raise ReplayFormatError(f"{context} contains data in reserved columns")


def _parse_timestamp(value: str) -> datetime:
    if _TIMESTAMP_PATTERN.fullmatch(value) is None:
        raise ReplayFormatError("timestamp_utc must use ISO 8601 UTC with a Z suffix")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except ValueError as error:
        raise ReplayFormatError("timestamp_utc is not a valid calendar time") from error


def _parse_enum(enum_type: type[E], value: str, field_name: str) -> E:
    try:
        return enum_type(value)
    except ValueError as error:
        raise ReplayFormatError(f"unsupported {field_name}: {value}") from error


def _parse_value(value: str) -> float | None:
    if value == "":
        return None
    if value in _NON_FINITE_VALUES:
        return _NON_FINITE_VALUES[value]
    if _NUMBER_PATTERN.fullmatch(value) is None:
        raise ReplayFormatError("value must use the canonical decimal grammar")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ReplayFormatError(
            "overflowing value is not allowed; use an explicit non-finite token"
        )
    return parsed


def _parse_quality_flags(value: str) -> frozenset[QualityFlag]:
    if value == "":
        return frozenset()
    tokens = value.split("|")
    if any(not token for token in tokens):
        raise ReplayFormatError("quality_flags contains an empty token")
    if len(tokens) != len(set(tokens)):
        raise ReplayFormatError("quality_flags cannot contain duplicates")
    flags = frozenset(
        _parse_enum(QualityFlag, token, "quality flag") for token in tokens
    )
    canonical = [flag.value for flag in QualityFlag if flag in flags]
    if tokens != canonical:
        raise ReplayFormatError("quality_flags must use canonical enum order")
    return flags


def _parse_count(value: str) -> int:
    if re.fullmatch(r"0|[1-9]\d*", value) is None:
        raise ReplayFormatError("END record_count must be a canonical integer")
    count = int(value)
    if count > MAX_REPLAY_RECORDS:
        raise ReplayLimitError(
            f"replay exceeds the {MAX_REPLAY_RECORDS}-record limit"
        )
    return count


def _parse_data_row(row: list[str], row_number: int, dataset_id: str) -> CsvReplayRecord:
    if row[0] != "DATA":
        raise ReplayFormatError(f"row {row_number} must be a DATA row")
    _require_schema_version(row[1])
    if row[2] != dataset_id:
        raise ReplayFormatError(f"row {row_number} dataset_id does not match META")
    if row[12] != "":
        raise ReplayFormatError(f"row {row_number} DATA record_count must be empty")
    try:
        return CsvReplayRecord(
            record_id=row[3],
            raw_record_id=row[4],
            timestamp=_parse_timestamp(row[5]),
            channel=row[6],
            value=_parse_value(row[7]),
            unit=_parse_enum(MeasurementUnit, row[8], "measurement unit"),
            status=_parse_enum(MeasurementStatus, row[9], "measurement status"),
            declared_source=_parse_enum(EvidenceSource, row[10], "evidence source"),
            quality_flags=_parse_quality_flags(row[11]),
        )
    except ReplayFormatError as error:
        raise ReplayFormatError(f"row {row_number}: {error}") from error


def parse_csv_replay(text: str | bytes) -> CsvReplayDataset:
    """Parse one complete, bounded CSV Replay v1 document without executing it."""

    rows = _read_rows(_decode_replay_input(text))
    if not rows:
        raise ReplayFormatError("replay is empty")
    if tuple(rows[0]) != CSV_REPLAY_COLUMNS:
        raise ReplayFormatError("CSV replay header or column order is invalid")
    if len(rows) < 3:
        raise ReplayFormatError("replay requires META and END rows")

    meta = rows[1]
    if meta[0] != "META":
        raise ReplayFormatError("row 2 must be a META row")
    _require_schema_version(meta[1])
    dataset_id = _require_identifier("dataset_id", meta[2])
    _require_empty(meta, range(3, len(CSV_REPLAY_COLUMNS)), "META row")

    end = rows[-1]
    if end[0] != "END":
        raise ReplayFormatError("last row must be an END row")
    _require_schema_version(end[1])
    if end[2] != dataset_id:
        raise ReplayFormatError("END dataset_id does not match META")
    _require_empty(end, range(3, 12), "END row")
    declared_count = _parse_count(end[12])

    records = tuple(
        _parse_data_row(row, row_number, dataset_id)
        for row_number, row in enumerate(rows[2:-1], start=3)
    )
    return CsvReplayDataset(dataset_id, records, declared_count)


def load_csv_replay(path: str | os.PathLike[str]) -> CsvReplayDataset:
    """Read one bounded local .csv file without modifying its bytes or metadata."""

    try:
        replay_path = Path(path)
    except TypeError as error:
        raise ReplayError("replay path must be path-like") from error
    if replay_path.suffix.lower() != ".csv":
        raise ReplayFormatError("replay file must use a .csv extension")
    try:
        size = replay_path.stat().st_size
    except OSError as error:
        raise ReplayError(f"cannot access replay file: {error}") from error
    if size > MAX_REPLAY_BYTES:
        raise ReplayLimitError(
            f"replay exceeds the {MAX_REPLAY_BYTES}-byte size limit"
        )
    try:
        data = replay_path.read_bytes()
    except OSError as error:
        raise ReplayError(f"cannot read replay file: {error}") from error
    return parse_csv_replay(data)


__all__ = [
    "CSV_REPLAY_COLUMNS",
    "CSV_REPLAY_SCHEMA_VERSION",
    "MAX_REPLAY_BYTES",
    "MAX_REPLAY_FIELD_CHARS",
    "MAX_REPLAY_RECORDS",
    "CsvReplayDataset",
    "CsvReplayRecord",
    "load_csv_replay",
    "parse_csv_replay",
]
