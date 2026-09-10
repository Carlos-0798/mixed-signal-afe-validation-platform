from __future__ import annotations

import hashlib
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from analog_validation.domain import EvidenceSource, MeasurementStatus, MeasurementUnit
from analog_validation_app.errors import ProductRequestError
from analog_validation_app.tabular_import import (
    MAX_VOLTAGE_IMPORT_BYTES,
    MAX_VOLTAGE_IMPORT_CELL_CHARS,
    MAX_VOLTAGE_IMPORT_COLUMNS,
    MAX_VOLTAGE_IMPORT_ROWS,
    VOLTAGE_IMPORT_MAPPING_SCHEMA_VERSION,
    TabularImportSource,
    VoltageImportError,
    VoltageImportMapping,
    mapping_from_dict,
    mapping_to_dict,
    parse_voltage_table,
    preview_voltage_import,
)


def mapping(**changes: Any) -> VoltageImportMapping:
    values: dict[str, Any] = {
        "name": "Scope voltage",
        "time_column": "Time",
        "input_column": "Input",
        "input_unit": MeasurementUnit.VOLT,
    }
    values.update(changes)
    return VoltageImportMapping(**values)


@pytest.mark.parametrize(
    ("suffix", "utc_minutes"), [("Z", 0), ("+05:30", -330), ("-04:00", 240)]
)
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
def test_timestamp_precision_in_table_and_elapsed_origin(
    suffix: str, utc_minutes: int, fraction: str, microseconds: int
) -> None:
    timestamp = f"2026-09-09T12:00:00{fraction}{suffix}"
    expected = datetime(2026, 9, 9, 12, microsecond=microseconds, tzinfo=timezone.utc)
    expected += timedelta(minutes=utc_minutes)
    source = parse_voltage_table(f"Time,Input\n{timestamp},1".encode())

    preview = preview_voltage_import(source, mapping())

    assert preview.dataset.records[0].timestamp == expected
    assert preview.dataset.records[0].timestamp.tzinfo is timezone.utc
    assert preview.dataset.records[0].declared_source is EvidenceSource.CSV_REPLAY
    selected = mapping(time_mode="elapsed_seconds", start_time_utc=timestamp)
    assert mapping_from_dict(mapping_to_dict(selected)) == selected
    assert selected.start_time_utc == timestamp
    elapsed = parse_voltage_table(b"Time,Input\n0,1\n0.000001,2")

    elapsed_preview = preview_voltage_import(elapsed, selected)

    assert [record.timestamp for record in elapsed_preview.dataset.records] == [
        expected,
        expected + timedelta(microseconds=1),
    ]
    assert all(
        record.timestamp.tzinfo is timezone.utc
        and record.declared_source is EvidenceSource.CSV_REPLAY
        for record in elapsed_preview.dataset.records
    )


@pytest.mark.parametrize(
    ("timestamp", "message"),
    [
        ("2026-09-09T12:00:00.Z", "ISO 8601"),
        ("2026-09-09T12:00:00.1234567Z", "ISO 8601"),
        ("2026-09-09T12:00:00.1234567+05:30", "ISO 8601"),
        ("2026-09-09T12:00:00.1234567-04:00", "ISO 8601"),
        ("2026-09-09T12:00:00.1+24:00", "ISO 8601"),
        ("2026-09-09T12:00:00.1-04:60", "ISO 8601"),
        ("2026-09-09T12:00:00.1", "ISO 8601"),
        ("2026-09-09T12:00:00.1z", "ISO 8601"),
        ("2026-09-09T12:00:00.1+0530", "ISO 8601"),
        ("2026-09-09T12:00:00.1+05:30:00", "ISO 8601"),
        ("2026-09-09T12:00:00.1e1Z", "ISO 8601"),
        ("2026-09-09T12:00:00.-1Z", "ISO 8601"),
        ("2026-02-30T12:00:00.1Z", "calendar"),
        ("2026-09-09T24:00:00.1+05:30", "calendar"),
        ("2026-09-09T12:00:60.1-04:00", "calendar"),
        ("0001-01-01T00:00:00.1+01:00", "calendar"),
        ("9999-12-31T23:59:59.1-01:00", "calendar"),
    ],
)
def test_invalid_timestamp_precision_in_table_and_elapsed_origin(
    timestamp: str, message: str
) -> None:
    source = parse_voltage_table(f"Time,Input\n{timestamp},1".encode())
    with pytest.raises(VoltageImportError, match=message) as table_error:
        preview_voltage_import(source, mapping())
    assert table_error.value.row_number == 2
    assert table_error.value.column == "Time"
    with pytest.raises(VoltageImportError, match=message) as origin_error:
        mapping(time_mode="elapsed_seconds", start_time_utc=timestamp)
    assert origin_error.value.row_number is None
    assert origin_error.value.column == "start_time_utc"


def test_timestamp_pair_conversion_provenance_and_immutability() -> None:
    payload = (
        b"\xef\xbb\xbf Time ,Input,Output,Note\r\n"
        b'2026-09-09T10:00:00-04:00,1.25,2500,"captured, locally"\r\n'
        b"2026-09-09T14:00:01Z,3.3,0,end\r\n"
    )
    source = parse_voltage_table(payload)
    selected = mapping(output_column="Output", output_unit=MeasurementUnit.MILLIVOLT)
    result = preview_voltage_import(source, selected, dataset_id="scope-import")
    assert source.raw_bytes is payload
    assert source.columns == ("Time", "Input", "Output", "Note")
    assert source.row_numbers == (2, 3)
    assert source.source_sha256 == hashlib.sha256(payload).hexdigest()
    assert result.row_count == 2
    assert result.mapping is selected
    assert result.source is source
    assert result.dataset.dataset_id == "scope-import"
    assert result.dataset.is_complete
    records = result.dataset.records
    assert [record.value for record in records] == [1250, 2500, 3300, 0]
    assert [record.channel for record in records] == [
        "afe.ch0.input",
        "afe.ch0.output",
        "afe.ch0.input",
        "afe.ch0.output",
    ]
    assert records[0].timestamp == datetime(2026, 9, 9, 14, tzinfo=timezone.utc)
    assert records[0].timestamp == records[1].timestamp
    for record in records:
        assert record.declared_source is EvidenceSource.CSV_REPLAY
        assert not record.declared_source.is_bench_evidence
        assert record.status is MeasurementStatus.VALID
        assert record.unit is MeasurementUnit.MILLIVOLT
        assert not record.quality_flags
        assert record.raw_record_id in record.record_id
    assert "row-2" in records[0].raw_record_id
    assert "input" in records[0].raw_record_id
    assert "output" in records[1].raw_record_id
    for instance in (source, selected, result):
        with pytest.raises(FrozenInstanceError):
            instance.__setattr__(next(iter(instance.__dataclass_fields__)), None)


@pytest.mark.parametrize("delimiter", [",", ";", "\t"])
def test_delimiters_elapsed_origin_and_equal_times(delimiter: str) -> None:
    source = parse_voltage_table(
        f"Time{delimiter}Input\n0{delimiter}.25\n0{delimiter}+1e0\n1.5{delimiter}1.\n".encode(),
        delimiter=delimiter,
    )
    result = preview_voltage_import(
        source,
        mapping(
            delimiter=delimiter,
            time_mode="elapsed_seconds",
            start_time_utc="2026-09-09T10:00:00-04:00",
        ),
    )
    assert result.dataset.records[0].timestamp == result.dataset.records[1].timestamp
    assert result.dataset.records[2].timestamp.microsecond == 500_000
    assert result.dataset.records[0].value == 250


def test_unicode_normalization_multiline_row_positions_and_custom_range() -> None:
    source = parse_voltage_table(
        'Time,Input,e\u0301\n"bad\ntime",-1,note\n2026-09-09T00:00:00Z,0,ok'.encode()
    )
    assert source.columns[-1] == "é"
    assert source.row_numbers == (2, 4)
    with pytest.raises(VoltageImportError) as caught:
        preview_voltage_import(source, mapping(minimum_mv=-1000))
    assert caught.value.row_number == 2
    assert caught.value.column == "Time"
    valid = parse_voltage_table(b"Time,Input\n2026-09-09T00:00:00Z,-1")
    assert (
        preview_voltage_import(valid, mapping(minimum_mv=-1000))
        .dataset.records[0]
        .value
        == -1000
    )


@pytest.mark.parametrize(
    "payload,match",
    [
        (b"", "header"),
        (b"Time,Input\n", "data row"),
        (b"\xff", "UTF-8"),
        (b"Time,Input\n0,\x00", "NUL"),
        (b"Time,Input\n0", "columns"),
        (b"Time,Input\n0,1,2", "columns"),
        (b"Time,Input\n\n", "columns"),
        (b"Time, Time\n0,1", "unique"),
        (b"Time, \n0,1", "non-empty"),
        (b'Time,Input\n0,"unfinished', "malformed"),
        (b"x" * (MAX_VOLTAGE_IMPORT_BYTES + 1), "byte"),
        (
            (
                ",".join(f"c{i}" for i in range(MAX_VOLTAGE_IMPORT_COLUMNS + 1)) + "\n"
            ).encode(),
            "column",
        ),
        (
            ("Time,Input\n0," + "1" * (MAX_VOLTAGE_IMPORT_CELL_CHARS + 1)).encode(),
            "character",
        ),
        (("Time,Input\n" + "0,1\n" * (MAX_VOLTAGE_IMPORT_ROWS + 1)).encode(), "row"),
    ],
    ids=[
        "empty",
        "header-only",
        "encoding",
        "nul",
        "short-row",
        "wide-row",
        "blank-row",
        "duplicate",
        "empty-header",
        "quote",
        "bytes",
        "columns",
        "cell",
        "rows",
    ],
)
def test_source_rejects_invalid_and_over_limit_tables(
    payload: bytes, match: str
) -> None:
    with pytest.raises(VoltageImportError, match=match):
        parse_voltage_table(payload)


@pytest.mark.parametrize(
    "payload", [None, "Time,Input\n0,1", bytearray(b"Time,Input\n0,1")]
)
def test_payload_type_is_immutable_bytes(payload: Any) -> None:
    with pytest.raises(VoltageImportError, match="bytes"):
        parse_voltage_table(payload)


@pytest.mark.parametrize("delimiter", ["|", "", None, 3])
def test_invalid_delimiters(delimiter: Any) -> None:
    with pytest.raises(VoltageImportError, match="delimiter"):
        parse_voltage_table(b"Time,Input\n0,1", delimiter=delimiter)


def test_source_rejects_forged_rows_and_mutable_containers() -> None:
    source = parse_voltage_table(b"Time,Input\n0,1")
    with pytest.raises(VoltageImportError):
        replace(source, rows=(("0", "2"),))
    with pytest.raises(VoltageImportError):
        replace(source, columns=list(source.columns))  # type: ignore[arg-type]
    with pytest.raises(VoltageImportError):
        replace(source, rows=(["0", "1"],))  # type: ignore[arg-type]
    with pytest.raises(VoltageImportError):
        replace(source, row_numbers=[2])  # type: ignore[arg-type]
    assert (
        TabularImportSource(
            source.raw_bytes, ",", source.columns, source.rows, source.row_numbers
        )
        == source
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"name": ""},
        {"name": " name "},
        {"name": 2},
        {"time_column": ""},
        {"time_column": 1},
        {"input_column": "Time"},
        {"input_unit": "V"},
        {"input_unit": MeasurementUnit.AMPERE},
        {"output_column": "Output"},
        {"output_unit": MeasurementUnit.VOLT},
        {"output_column": "Time", "output_unit": MeasurementUnit.VOLT},
        {"output_column": "Output", "output_unit": MeasurementUnit.OHM},
        {"time_mode": "auto"},
        {"time_mode": "elapsed_seconds"},
        {"start_time_utc": "2026-09-09T00:00:00Z"},
        {"time_mode": "elapsed_seconds", "start_time_utc": "2026-09-09T00:00:00"},
        {"time_mode": "elapsed_seconds", "start_time_utc": 3},
        {"minimum_mv": True},
        {"minimum_mv": "0"},
        {"minimum_mv": float("nan")},
        {"maximum_mv": float("inf")},
        {"minimum_mv": 4, "maximum_mv": 3},
        {"minimum_mv": 3, "maximum_mv": 3},
        {"schema_version": "v2"},
        {"delimiter": "|"},
    ],
)
def test_mapping_invariants(changes: dict[str, Any]) -> None:
    with pytest.raises(VoltageImportError):
        mapping(**changes)


@pytest.mark.parametrize(
    "value",
    ["", "NaN", "Infinity", "-inf", "1e309", "1_000", "no", "1,2", "3.301", "-0.001"],
)
def test_selected_voltage_rejects_row_without_dropping(value: str) -> None:
    source = parse_voltage_table(f'Time,Input\n2026-09-09T00:00:00Z,"{value}"'.encode())
    with pytest.raises(VoltageImportError) as caught:
        preview_voltage_import(source, mapping())
    assert isinstance(caught.value, ProductRequestError)
    assert caught.value.row_number == 2
    assert caught.value.column == "Input"
    assert "row 2" in str(caught.value)
    assert "Input" in str(caught.value)


@pytest.mark.parametrize(
    "timestamp",
    [
        "",
        "2026-09-09",
        "2026-09-09T00:00:00",
        "2026-02-30T00:00:00Z",
        "20260909T000000Z",
        "2026-09-09Q00:00:00Z",
        "2026-09-09T00:00:00.1234567Z",
        "0001-01-01T00:00:00+01:00",
    ],
)
def test_invalid_timestamps(timestamp: str) -> None:
    source = parse_voltage_table(f"Time,Input\n{timestamp},1".encode())
    with pytest.raises(VoltageImportError) as caught:
        preview_voltage_import(source, mapping())
    assert caught.value.row_number == 2
    assert caught.value.column == "Time"


@pytest.mark.parametrize("seconds", ["", "-1", "NaN", "1e309", "1e300"])
def test_invalid_elapsed_times(seconds: str) -> None:
    source = parse_voltage_table(f"Time,Input\n{seconds},1".encode())
    with pytest.raises(VoltageImportError) as caught:
        preview_voltage_import(
            source,
            mapping(time_mode="elapsed_seconds", start_time_utc="2026-09-09T00:00:00Z"),
        )
    assert caught.value.row_number == 2
    assert caught.value.column == "Time"


def test_time_order_is_evaluated_after_utc_conversion() -> None:
    source = parse_voltage_table(
        b"Time,Input\n2026-09-09T01:00:00Z,1\n2026-09-09T01:30:00+01:00,2"
    )
    with pytest.raises(VoltageImportError, match="nondecreasing") as caught:
        preview_voltage_import(source, mapping())
    assert caught.value.row_number == 3


def test_preview_missing_column_delimiter_mismatch_and_invalid_dataset_id() -> None:
    source = parse_voltage_table(b"Time,Input\n2026-09-09T00:00:00Z,1")
    with pytest.raises(VoltageImportError, match="missing"):
        preview_voltage_import(source, mapping(input_column="Missing"))
    with pytest.raises(VoltageImportError, match="delimiter"):
        preview_voltage_import(source, mapping(delimiter=";"))
    with pytest.raises(VoltageImportError, match="dataset_id"):
        preview_voltage_import(source, mapping(), dataset_id="bad id")
    with pytest.raises(VoltageImportError):
        preview_voltage_import(None, mapping())  # type: ignore[arg-type]
    with pytest.raises(VoltageImportError):
        preview_voltage_import(source, None)  # type: ignore[arg-type]


def test_mapping_json_roundtrip_and_minimal_document() -> None:
    selected = mapping(output_column="Output", output_unit=MeasurementUnit.MILLIVOLT)
    document = mapping_to_dict(selected)
    assert document["schema_version"] == VOLTAGE_IMPORT_MAPPING_SCHEMA_VERSION
    assert document["input_unit"] == "V"
    assert document["output_unit"] == "mV"
    assert mapping_from_dict(document) == selected
    single = mapping_to_dict(mapping())
    assert single["output_unit"] is None
    assert mapping_from_dict(single) == mapping()
    required = {
        key: single[key]
        for key in (
            "schema_version",
            "name",
            "time_column",
            "input_column",
            "input_unit",
        )
    }
    assert mapping_from_dict(required) == mapping()


@pytest.mark.parametrize("document", [None, [], {"extra": 1}, {}])
def test_mapping_json_invalid_document(document: Any) -> None:
    with pytest.raises(VoltageImportError):
        mapping_from_dict(document)


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", "v2"),
        ("input_unit", "A"),
        ("input_unit", 1),
        ("input_unit", None),
        ("output_unit", {}),
        ("name", None),
        ("maximum_mv", True),
        ("input_column", ["Input"]),
        ("unknown", "bad"),
    ],
)
def test_mapping_json_strict_values(key: str, value: Any) -> None:
    document = mapping_to_dict(mapping())
    document[key] = value
    with pytest.raises(VoltageImportError):
        mapping_from_dict(document)


def test_mapping_rejects_huge_integer_and_invalid_serializer_input() -> None:
    with pytest.raises(VoltageImportError, match="finite"):
        mapping(maximum_mv=10**1000)
    with pytest.raises(VoltageImportError):
        mapping_to_dict(None)  # type: ignore[arg-type]


def test_mapping_name_matches_publishable_project_name_limit() -> None:
    assert mapping(name="n" * 256).name == "n" * 256
    with pytest.raises(VoltageImportError, match="256"):
        mapping(name="n" * 257)


@pytest.mark.parametrize("name", ["bad\x7f", "bad\ud800"])
def test_mapping_names_reject_nonprintable_and_non_utf8_text(name: str) -> None:
    with pytest.raises(VoltageImportError, match="printable"):
        mapping(name=name)


def test_inclusive_source_size_and_shape_limits() -> None:
    header = b"Time,Input,Note\n"
    full_row = b"0,1," + b"x" * MAX_VOLTAGE_IMPORT_CELL_CHARS + b"\n"
    count, remaining = divmod(MAX_VOLTAGE_IMPORT_BYTES - len(header) - 5, len(full_row))
    payload = header + full_row * count + b"0,1," + b"x" * remaining + b"\n"
    assert len(payload) == MAX_VOLTAGE_IMPORT_BYTES
    assert parse_voltage_table(payload).raw_bytes == payload
    rows = parse_voltage_table(b"Time,Input\n" + b"0,1\n" * MAX_VOLTAGE_IMPORT_ROWS)
    assert len(rows.rows) == MAX_VOLTAGE_IMPORT_ROWS
    columns = parse_voltage_table(
        (
            ",".join(f"c{i}" for i in range(MAX_VOLTAGE_IMPORT_COLUMNS))
            + "\n"
            + ",".join("1" for _ in range(MAX_VOLTAGE_IMPORT_COLUMNS))
        ).encode()
    )
    assert len(columns.columns) == MAX_VOLTAGE_IMPORT_COLUMNS


def test_converted_voltage_overflow_and_output_error_are_reported() -> None:
    source = parse_voltage_table(b"Time,Input,Output\n2026-09-09T00:00:00Z,1,1e308")
    with pytest.raises(VoltageImportError) as caught:
        preview_voltage_import(
            source, mapping(output_column="Output", output_unit=MeasurementUnit.VOLT)
        )
    assert caught.value.column == "Output"
    assert caught.value.row_number == 2
