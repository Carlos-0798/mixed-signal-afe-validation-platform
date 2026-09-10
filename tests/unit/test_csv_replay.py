from __future__ import annotations

import math
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

import pytest

from analog_validation import (
    CSV_REPLAY_COLUMNS,
    CSV_REPLAY_SCHEMA_VERSION,
    MAX_REPLAY_BYTES,
    MAX_REPLAY_FIELD_CHARS,
    MAX_REPLAY_RECORDS,
    CsvReplayDataset,
    CsvReplayRecord,
    EvidenceSource,
    MeasurementStatus,
    MeasurementUnit,
    QualityFlag,
    ReplayError,
    ReplayFormatError,
    ReplayLimitError,
    UnsupportedReplayVersion,
    load_csv_replay,
    parse_csv_replay,
)

ROOT = Path(__file__).resolve().parents[2]
VALID_FILE = ROOT / "test-data" / "golden" / "csv_replay_v1_valid.csv"
UTC_TIME = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def valid_text() -> str:
    return VALID_FILE.read_text(encoding="utf-8")


def make_record(**changes: Any) -> CsvReplayRecord:
    values: dict[str, Any] = {
        "record_id": "record-001",
        "raw_record_id": "record-001",
        "timestamp": UTC_TIME,
        "channel": "afe.ch0.input",
        "value": 800,
        "unit": MeasurementUnit.MILLIVOLT,
        "status": MeasurementStatus.VALID,
        "declared_source": EvidenceSource.SYNTHETIC,
    }
    values.update(changes)
    return CsvReplayRecord(**values)


def replace_once(old: str, new: str) -> str:
    text = valid_text()
    assert text.count(old) >= 1
    return text.replace(old, new, 1)


def assert_replay_semantically_equal(
    actual: CsvReplayDataset, expected: CsvReplayDataset
) -> None:
    """Compare replay meaning without relying on ``NaN == NaN``.

    IEEE 754 deliberately makes NaN unequal to every value, including itself.
    Python 3.14 also stopped an older dataclass comparison implementation from
    accidentally hiding that rule through object identity.  Replay equivalence
    therefore compares every ordinary field directly and handles NaN explicitly.
    """

    assert actual.dataset_id == expected.dataset_id
    assert actual.declared_record_count == expected.declared_record_count
    assert actual.schema_version == expected.schema_version
    assert len(actual.records) == len(expected.records)
    for actual_record, expected_record in zip(
        actual.records, expected.records, strict=True
    ):
        assert (
            actual_record.record_id,
            actual_record.raw_record_id,
            actual_record.timestamp,
            actual_record.channel,
            actual_record.unit,
            actual_record.status,
            actual_record.declared_source,
            actual_record.quality_flags,
        ) == (
            expected_record.record_id,
            expected_record.raw_record_id,
            expected_record.timestamp,
            expected_record.channel,
            expected_record.unit,
            expected_record.status,
            expected_record.declared_source,
            expected_record.quality_flags,
        )
        actual_value = actual_record.value
        expected_value = expected_record.value
        if (
            isinstance(actual_value, float)
            and isinstance(expected_value, float)
            and math.isnan(actual_value)
            and math.isnan(expected_value)
        ):
            continue
        assert actual_value == expected_value


def test_public_constants_and_valid_fixture_parse_from_text_and_bytes() -> None:
    assert CSV_REPLAY_SCHEMA_VERSION == "csv-replay.v1"
    assert CSV_REPLAY_COLUMNS == (
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
    text = valid_text()
    dataset = parse_csv_replay(text)

    assert_replay_semantically_equal(parse_csv_replay(text.encode("utf-8")), dataset)
    assert dataset.dataset_id == "afe-demo-001"
    assert dataset.schema_version == CSV_REPLAY_SCHEMA_VERSION
    assert dataset.declared_record_count == 5
    assert len(dataset) == 5
    assert dataset.is_complete
    assert dataset.records[0].value == 800.0
    assert dataset.records[1].quality_flags == frozenset({QualityFlag.SATURATED})
    assert dataset.records[2].value is None
    assert dataset.records[2].quality_flags == frozenset(
        {QualityFlag.MISSING, QualityFlag.COMMUNICATION_ERROR}
    )
    assert math.isnan(cast(float, dataset.records[3].value))
    assert dataset.records[3].declared_source is EvidenceSource.SPICE_MODEL
    assert dataset.records[4].unit is MeasurementUnit.BOOLEAN
    assert dataset.records[4].declared_source is EvidenceSource.HOST_TEST


def test_record_and_dataset_are_frozen_and_normalize_immutable_values() -> None:
    mutable_flags = {QualityFlag.SATURATED}
    record = make_record(
        status=MeasurementStatus.SUSPECT,
        quality_flags=cast(frozenset[QualityFlag], mutable_flags),
    )
    records = [record]
    dataset = CsvReplayDataset(
        "dataset-001",
        cast(tuple[CsvReplayRecord, ...], records),
        1,
    )

    mutable_flags.add(QualityFlag.OUT_OF_RANGE)
    records.clear()
    assert record.value == 800.0
    assert record.quality_flags == frozenset({QualityFlag.SATURATED})
    assert dataset.records == (record,)
    with pytest.raises(FrozenInstanceError):
        record.value = 1.0  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        dataset.dataset_id = "other"  # type: ignore[misc]


@pytest.mark.parametrize("field", ["record_id", "raw_record_id", "channel"])
@pytest.mark.parametrize(
    "value",
    ["", " leading", "trailing ", "=formula", "comma,value", "name with space"],
)
def test_record_identifiers_use_a_safe_bounded_grammar(
    field: str, value: str
) -> None:
    with pytest.raises(ReplayFormatError, match=field):
        make_record(**{field: value})


@pytest.mark.parametrize(
    "timestamp",
    [
        cast(Any, "2026-08-30T12:00:00Z"),
        UTC_TIME.replace(tzinfo=None),
        UTC_TIME.astimezone(timezone(timedelta(hours=-4))),
    ],
)
def test_record_requires_a_typed_utc_timestamp(timestamp: datetime) -> None:
    with pytest.raises(ReplayFormatError, match="UTC datetime"):
        make_record(timestamp=timestamp)


def test_record_wraps_measurement_consistency_errors() -> None:
    with pytest.raises(ReplayFormatError, match="invalid replay record"):
        make_record(value=None)
    with pytest.raises(ReplayFormatError, match="invalid replay record"):
        make_record(
            value=None,
            status=MeasurementStatus.VALID,
            quality_flags=frozenset({QualityFlag.MISSING}),
        )


def test_empty_dataset_is_a_complete_explicit_end_condition() -> None:
    dataset = CsvReplayDataset("empty-dataset", (), 0)

    assert len(dataset) == 0
    assert dataset.is_complete


@pytest.mark.parametrize("dataset_id", ["", " bad", "=formula"])
def test_dataset_identifier_is_strict(dataset_id: str) -> None:
    with pytest.raises(ReplayFormatError, match="dataset_id"):
        CsvReplayDataset(dataset_id, (), 0)


def test_dataset_rejects_unknown_version_and_invalid_record_container() -> None:
    with pytest.raises(UnsupportedReplayVersion):
        CsvReplayDataset("dataset", (), 0, schema_version="csv-replay.v2")
    with pytest.raises(ReplayFormatError, match="iterable"):
        CsvReplayDataset("dataset", cast(Any, "records"), 0)
    with pytest.raises(ReplayFormatError, match="CsvReplayRecord"):
        CsvReplayDataset("dataset", cast(Any, (object(),)), 1)


@pytest.mark.parametrize("count", [True, "1", -1])
def test_dataset_declared_count_must_be_nonnegative_integer(count: object) -> None:
    with pytest.raises(ReplayFormatError, match="non-negative integer"):
        CsvReplayDataset("dataset", (), cast(Any, count))


def test_dataset_rejects_count_duplicate_time_and_record_limits() -> None:
    first = make_record()
    second = make_record(
        record_id="record-002",
        raw_record_id="record-002",
        timestamp=UTC_TIME + timedelta(milliseconds=1),
    )
    with pytest.raises(ReplayFormatError, match="record_count"):
        CsvReplayDataset("dataset", (first,), 0)
    with pytest.raises(ReplayFormatError, match="unique"):
        CsvReplayDataset("dataset", (first, first), 2)
    with pytest.raises(ReplayFormatError, match="nondecreasing"):
        CsvReplayDataset("dataset", (second, first), 2)
    with pytest.raises(ReplayLimitError, match="record limit"):
        CsvReplayDataset(
            "dataset",
            (first,) * (MAX_REPLAY_RECORDS + 1),
            MAX_REPLAY_RECORDS + 1,
        )


@pytest.mark.parametrize(
    ("payload", "error_type", "message"),
    [
        (b"\xff", ReplayFormatError, "valid UTF-8"),
        ("\ud800", ReplayFormatError, "valid UTF-8"),
        (cast(Any, 1), ReplayFormatError, "str or bytes"),
        ("\ufeff" + valid_text(), ReplayFormatError, "BOM"),
        (valid_text().replace("META", "ME\x00TA", 1), ReplayFormatError, "NUL"),
        (valid_text().replace("\n", "\r", 1), ReplayFormatError, "LF or CRLF"),
    ],
)
def test_parser_rejects_invalid_encoding_and_transport_text(
    payload: str | bytes,
    error_type: type[ReplayError],
    message: str,
) -> None:
    with pytest.raises(error_type, match=message):
        parse_csv_replay(payload)


@pytest.mark.parametrize(
    "payload",
    [b" " * (MAX_REPLAY_BYTES + 1), " " * (MAX_REPLAY_BYTES + 1)],
    ids=["bytes", "text"],
)
def test_direct_parser_enforces_byte_limit(payload: str | bytes) -> None:
    with pytest.raises(ReplayLimitError, match="size limit"):
        parse_csv_replay(payload)


def test_parser_accepts_crlf_without_changing_meaning() -> None:
    lf = parse_csv_replay(valid_text())
    crlf = parse_csv_replay(valid_text().replace("\n", "\r\n"))

    assert_replay_semantically_equal(crlf, lf)


@pytest.mark.parametrize(
    ("fraction", "microseconds"),
    [
        ("", 0),
        (".1", 100_000),
        (".12", 120_000),
        (".123", 123_000),
        (".1234", 123_400),
        (".12345", 123_450),
        (".123456", 123_456),
        (".000000", 0),
        (".000001", 1),
        (".999999", 999_999),
    ],
)
def test_parser_preserves_fractional_second_precision(
    fraction: str, microseconds: int
) -> None:
    timestamp = f"2026-08-30T12:00:01{fraction}Z"
    payload = valid_text().replace("2026-08-30T12:00:00.300000Z", timestamp)

    dataset = parse_csv_replay(payload)

    expected = datetime(2026, 8, 30, 12, 0, 1, microseconds, tzinfo=timezone.utc)
    assert dataset.records[3].timestamp == expected
    assert dataset.records[4].timestamp == expected
    assert dataset.records[3].timestamp.tzinfo is timezone.utc
    assert dataset.records[3].declared_source is EvidenceSource.SPICE_MODEL
    assert dataset.records[4].declared_source is EvidenceSource.HOST_TEST


@pytest.mark.parametrize(
    ("timestamp", "message"),
    [
        ("2026-08-30T12:00:01.Z", "ISO 8601"),
        ("2026-08-30T12:00:01.1234567Z", "ISO 8601"),
        ("2026-08-30T12:00:01.0000000Z", "ISO 8601"),
        ("2026-08-30T12:00:01.-1Z", "ISO 8601"),
        ("2026-08-30T12:00:01.1e1Z", "ISO 8601"),
        ("2026-08-30T12:00:01.1", "ISO 8601"),
        ("2026-08-30T12:00:01.1z", "ISO 8601"),
        ("2026-08-30T12:00:01.1+00:00", "ISO 8601"),
        ("2026-08-30T12:00:01.1Z ", "ISO 8601"),
        ("2026-02-30T12:00:01.1Z", "calendar"),
        ("2026-08-30T24:00:00.1Z", "calendar"),
        ("2026-08-30T12:00:60.1Z", "calendar"),
    ],
)
def test_parser_rejects_invalid_fractional_timestamps(
    timestamp: str, message: str
) -> None:
    payload = replace_once("2026-08-30T12:00:00Z", timestamp)

    with pytest.raises(ReplayFormatError, match=message):
        parse_csv_replay(payload)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("", "empty"),
        ("a,b,c\n", "exactly 13 columns"),
        ('"unterminated,,,,,,,,,,,,\n', "malformed CSV"),
        (
            valid_text().replace("row_type", "row_order", 1),
            "header or column order",
        ),
        (
            ",".join(CSV_REPLAY_COLUMNS) + "\n",
            "requires META and END",
        ),
    ],
)
def test_parser_rejects_missing_or_malformed_structure(
    payload: str, message: str
) -> None:
    with pytest.raises(ReplayFormatError, match=message):
        parse_csv_replay(payload)


def test_parser_rejects_long_fields_controls_and_excessive_row_count() -> None:
    long_field = "a" * (MAX_REPLAY_FIELD_CHARS + 1)
    with pytest.raises(ReplayLimitError, match="field longer"):
        parse_csv_replay(replace_once("afe-demo-001", long_field))
    with pytest.raises(ReplayFormatError, match="control character"):
        parse_csv_replay(replace_once("afe-demo-001", "afe\tdemo"))

    rows = ",".join(CSV_REPLAY_COLUMNS) + "\n" + (
        ",,,,,,,,,,,,\n" * (MAX_REPLAY_RECORDS + 3)
    )
    with pytest.raises(ReplayLimitError, match="record limit"):
        parse_csv_replay(rows)


@pytest.mark.parametrize(
    ("old", "new", "error_type", "message"),
    [
        ("META,csv-replay.v1", "DATA,csv-replay.v1", ReplayFormatError, "META"),
        (
            "META,csv-replay.v1",
            "META,csv-replay.v2",
            UnsupportedReplayVersion,
            "unsupported",
        ),
        ("afe-demo-001,,,,,,,,,,", "bad id,,,,,,,,,,", ReplayFormatError, "dataset_id"),
        (
            "META,csv-replay.v1,afe-demo-001,,,,,,,,,,",
            "META,csv-replay.v1,afe-demo-001,reserved,,,,,,,,,",
            ReplayFormatError,
            "reserved",
        ),
        ("END,csv-replay.v1", "DATA,csv-replay.v1", ReplayFormatError, "END"),
        (
            "END,csv-replay.v1",
            "END,csv-replay.v2",
            UnsupportedReplayVersion,
            "unsupported",
        ),
        (
            "END,csv-replay.v1,afe-demo-001",
            "END,csv-replay.v1,other-dataset",
            ReplayFormatError,
            "does not match META",
        ),
        (
            "END,csv-replay.v1,afe-demo-001,,,,,,,,,,5",
            "END,csv-replay.v1,afe-demo-001,reserved,,,,,,,,,5",
            ReplayFormatError,
            "reserved",
        ),
    ],
)
def test_meta_and_end_rows_are_exact(
    old: str,
    new: str,
    error_type: type[ReplayError],
    message: str,
) -> None:
    with pytest.raises(error_type, match=message):
        parse_csv_replay(replace_once(old, new))


@pytest.mark.parametrize(
    ("value", "error_type", "message"),
    [
        ("", ReplayFormatError, "canonical integer"),
        ("05", ReplayFormatError, "canonical integer"),
        ("-1", ReplayFormatError, "canonical integer"),
        (str(MAX_REPLAY_RECORDS + 1), ReplayLimitError, "record limit"),
    ],
)
def test_end_count_is_bounded_canonical_integer(
    value: str, error_type: type[ReplayError], message: str
) -> None:
    old = "END,csv-replay.v1,afe-demo-001,,,,,,,,,,5"
    new = f"END,csv-replay.v1,afe-demo-001,,,,,,,,,,{value}"
    with pytest.raises(error_type, match=message):
        parse_csv_replay(replace_once(old, new))


@pytest.mark.parametrize(
    ("old", "new", "error_type", "message"),
    [
        ("DATA,csv-replay.v1", "META,csv-replay.v1", ReplayFormatError, "DATA row"),
        (
            "DATA,csv-replay.v1",
            "DATA,csv-replay.v2",
            UnsupportedReplayVersion,
            "unsupported",
        ),
        (
            "DATA,csv-replay.v1,afe-demo-001,input-000",
            "DATA,csv-replay.v1,other-dataset,input-000",
            ReplayFormatError,
            "does not match META",
        ),
        (
            "VALID,SYNTHETIC,,\n",
            "VALID,SYNTHETIC,,1\n",
            ReplayFormatError,
            "record_count must be empty",
        ),
    ],
)
def test_data_row_envelope_is_exact(
    old: str,
    new: str,
    error_type: type[ReplayError],
    message: str,
) -> None:
    with pytest.raises(error_type, match=message):
        parse_csv_replay(replace_once(old, new))


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("2026-08-30T12:00:00Z", "2026-08-30 12:00:00Z", "ISO 8601"),
        ("2026-08-30T12:00:00Z", "2026-02-30T12:00:00Z", "calendar"),
        (",800,mV,VALID", ",800,volts,VALID", "measurement unit"),
        (",800,mV,VALID", ",800,mV,GOOD", "measurement status"),
        (",800,mV,VALID,SYNTHETIC", ",800,mV,VALID,PHYSICAL", "evidence source"),
        ("input-000,input-000", "=bad,input-000", "record_id"),
    ],
)
def test_data_fields_reject_invalid_semantics(old: str, new: str, message: str) -> None:
    with pytest.raises(ReplayFormatError, match=message):
        parse_csv_replay(replace_once(old, new))


@pytest.mark.parametrize("value", ["+1", "01", "1_000", ".5", "1."])
def test_numeric_value_uses_canonical_decimal_grammar(value: str) -> None:
    with pytest.raises(ReplayFormatError, match="canonical decimal"):
        parse_csv_replay(replace_once(",800,mV,VALID", f",{value},mV,VALID"))


def test_numeric_overflow_requires_explicit_nonfinite_token() -> None:
    with pytest.raises(ReplayFormatError, match="overflowing"):
        parse_csv_replay(replace_once(",800,mV,VALID", ",1e999,mV,VALID"))


@pytest.mark.parametrize("value", ["Infinity", "-Infinity"])
def test_explicit_infinity_tokens_are_supported_with_consistent_quality(
    value: str,
) -> None:
    text = replace_once(",NaN,mV,INVALID,SPICE_MODEL,NON_FINITE", f",{value},mV,INVALID,SPICE_MODEL,NON_FINITE")
    parsed = parse_csv_replay(text).records[3]

    assert math.isinf(cast(float, parsed.value))


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("SATURATED,", "SATURATED||MISSING,", "empty token"),
        ("SATURATED,", "SATURATED|SATURATED,", "duplicates"),
        ("SATURATED,", "UNKNOWN,", "quality flag"),
        ("MISSING|COMMUNICATION_ERROR", "COMMUNICATION_ERROR|MISSING", "canonical"),
        (",800,mV,VALID,SYNTHETIC,,", ",800,mV,VALID,SYNTHETIC,SATURATED,", "VALID"),
    ],
)
def test_quality_flags_are_strict_and_consistent(
    old: str, new: str, message: str
) -> None:
    with pytest.raises(ReplayFormatError, match=message):
        parse_csv_replay(replace_once(old, new))


def test_loader_is_read_only_and_checks_extension_access_size_and_read_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "dataset.CSV"
    source.write_bytes(VALID_FILE.read_bytes())
    before_bytes = source.read_bytes()
    before_stat = source.stat()

    dataset = load_csv_replay(source)

    after_stat = source.stat()
    assert len(dataset) == 5
    assert source.read_bytes() == before_bytes
    assert after_stat.st_size == before_stat.st_size
    assert after_stat.st_mtime_ns == before_stat.st_mtime_ns

    with pytest.raises(ReplayError, match="path-like"):
        load_csv_replay(cast(Any, object()))
    with pytest.raises(ReplayFormatError, match=".csv"):
        load_csv_replay(tmp_path / "dataset.txt")
    with pytest.raises(ReplayError, match="cannot access"):
        load_csv_replay(tmp_path / "missing.csv")

    large = tmp_path / "large.csv"
    large.write_bytes(b" " * (MAX_REPLAY_BYTES + 1))
    with pytest.raises(ReplayLimitError, match="size limit"):
        load_csv_replay(large)

    def fail_read(self: Path) -> bytes:
        raise OSError("simulated read failure")

    monkeypatch.setattr(Path, "read_bytes", fail_read)
    with pytest.raises(ReplayError, match="cannot read"):
        load_csv_replay(source)
