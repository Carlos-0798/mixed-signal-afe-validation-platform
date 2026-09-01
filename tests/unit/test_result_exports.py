"""Tests for stable, provenance-preserving JSON/CSV result exports."""

from __future__ import annotations

import csv
import io
import json
import math
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from os import PathLike
from pathlib import Path
from typing import Any

import pytest

import analog_validation.exports._files as file_module
from analog_validation.analysis import AnalysisRecordReference, PointDisposition
from analog_validation.domain import EvidenceSource
from analog_validation.domain import TestRunMetadata as RunMetadata
from analog_validation.domain import TestRunOutcome as RunOutcome
from analog_validation.domain import TestRunResult as RunResult
from analog_validation.errors import AnalogValidationError, ValidationError
from analog_validation.exports import (
    CSV_RESULT_EXPORT_COLUMNS,
    MAX_RESULT_EXPORT_BYTES,
    RESULT_EXPORT_SCHEMA_VERSION,
    ExportCriterion,
    ExportPoint,
    ExportSchemaReference,
    ExportValue,
    ResultExportBundle,
    ResultExportError,
    ResultExportExistsError,
    ResultExportFormatError,
    ResultExportLimitError,
    ResultExportPathError,
    UnsupportedResultExportVersion,
    dump_result_export_csv,
    dump_result_export_json,
    load_result_export_csv,
    load_result_export_json,
    parse_result_export_csv,
    parse_result_export_json,
    result_export_from_dict,
    result_export_to_dict,
    write_result_export_csv,
    write_result_export_json,
)

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def unsafe_replace(instance: Any, **changes: Any) -> Any:
    return replace(instance, **changes)


def reference(
    index: int,
    *,
    source: EvidenceSource = EvidenceSource.SYNTHETIC,
) -> AnalysisRecordReference:
    return AnalysisRecordReference(
        f"record-{index}",
        f"raw-{index}",
        NOW + timedelta(milliseconds=index),
        f"channel-{index}",
        source,
    )


def metadata(
    *,
    source: EvidenceSource = EvidenceSource.SYNTHETIC,
    input_ids: tuple[str, ...] = ("raw-0", "raw-1"),
) -> RunMetadata:
    return RunMetadata(
        "run-1",
        "dc-sweep",
        "config-1",
        "1",
        NOW,
        NOW + timedelta(seconds=1),
        "0.1.0.dev0",
        "fixture",
        "afe",
        "1",
        source,
        input_ids,
    )


def points(
    *, source: EvidenceSource = EvidenceSource.SYNTHETIC
) -> tuple[ExportPoint, ...]:
    return (
        ExportPoint(
            0,
            "dc-point",
            PointDisposition.INCLUDED,
            (reference(0, source=source),),
            (
                ExportValue("input", 100.0, "mV"),
                ExportValue("output", 200.0, "mV"),
            ),
        ),
        ExportPoint(
            1,
            "dc-point",
            PointDisposition.EXCLUDED,
            (reference(1, source=source),),
            (
                ExportValue("input", 1000.0, "mV"),
                ExportValue("output", 3290.0, "mV"),
            ),
            ("SATURATED",),
            ("HIGH_SATURATION",),
        ),
    )


def bundle(outcome: RunOutcome = RunOutcome.PASS) -> ResultExportBundle:
    item_points = points()
    passed = outcome is RunOutcome.PASS
    result = RunResult(
        metadata(),
        outcome,
        "criteria passed" if passed else "criteria failed",
        tuple(ref.record_id for point in item_points for ref in point.references),
    )
    return ResultExportBundle(
        result,
        (
            ExportSchemaReference("test-run", "test-run.v1"),
            ExportSchemaReference("dc-analysis", "dc-sweep-analysis.v1"),
        ),
        (
            ExportValue("gain", 2.0, "ratio"),
            ExportValue("included_points", 1, "points"),
        ),
        item_points,
        (
            "HOST_TEST/SYNTHETIC results do not verify physical hardware.",
            "Excluded points remain in this export.",
        ),
        "dc-criteria",
        "1",
        (
            ExportCriterion(
                "GAIN",
                2.0 if passed else 3.0,
                "ratio",
                passed,
                1.9,
                2.1,
            ),
        ),
    )


def incomplete_bundle() -> ResultExportBundle:
    item_points = points()
    return ResultExportBundle(
        RunResult(
            metadata(),
            RunOutcome.INCOMPLETE,
            "criteria not evaluated",
            tuple(ref.record_id for point in item_points for ref in point.references),
            ("analysis:included-points:1/3",),
        ),
        (ExportSchemaReference("dc-analysis", "dc-sweep-analysis.v1"),),
        (ExportValue("included_points", 1, "points"),),
        item_points,
        ("Incomplete evidence cannot produce PASS/FAIL.",),
    )


def unsupported_bundle() -> ResultExportBundle:
    return ResultExportBundle(
        RunResult(
            metadata(source=EvidenceSource.HOST_TEST, input_ids=()),
            RunOutcome.UNSUPPORTED,
            "adapter lacks output capability",
            (),
            ("command:SET_ANALOG_STIMULUS",),
        ),
        (ExportSchemaReference("runner", "dc-sweep-runner.v1"),),
        (),
        (),
        ("No acquisition occurred.",),
    )


def test_models_preserve_lineage_quality_and_are_immutable() -> None:
    value = bundle()
    assert value.schema_version == RESULT_EXPORT_SCHEMA_VERSION
    assert value.points[0].evidence_source is EvidenceSource.SYNTHETIC
    assert value.points[1].quality_flags == ("SATURATED",)
    assert value.points[1].exclusion_reasons == ("HIGH_SATURATION",)
    assert value.test_run_result.metadata.input_record_ids == ("raw-0", "raw-1")
    with pytest.raises(FrozenInstanceError):
        value.limitations = ()  # type: ignore[misc]


@pytest.mark.parametrize(
    "value",
    [bundle(), bundle(RunOutcome.FAIL), incomplete_bundle(), unsupported_bundle()],
)
def test_json_is_deterministic_and_round_trips_every_outcome(
    value: ResultExportBundle,
) -> None:
    first = dump_result_export_json(value)
    second = dump_result_export_json(value)
    assert first == second
    assert first.endswith("\n")
    assert parse_result_export_json(first) == value
    document = json.loads(first)
    assert list(document) == [
        "schema_version",
        "test_run",
        "criteria",
        "source_schemas",
        "metrics",
        "points",
        "limitations",
    ]
    assert document["test_run"]["metadata"]["evidence_source"] == (
        value.test_run_result.metadata.evidence_source.value
    )
    assert result_export_from_dict(result_export_to_dict(value)) == value


@pytest.mark.parametrize(
    "value",
    [bundle(), bundle(RunOutcome.FAIL), incomplete_bundle(), unsupported_bundle()],
)
def test_csv_has_stable_rows_and_round_trips_every_outcome(
    value: ResultExportBundle,
) -> None:
    text = dump_result_export_csv(value)
    assert text == dump_result_export_csv(value)
    reader = list(csv.reader(io.StringIO(text)))
    assert tuple(reader[0]) == CSV_RESULT_EXPORT_COLUMNS
    assert reader[1][1] == "RUN"
    assert [row[2] for row in reader[1:]] == [
        str(index) for index in range(len(reader) - 1)
    ]
    assert parse_result_export_csv(text) == value


def test_json_and_csv_local_file_round_trip_and_safe_overwrite(tmp_path: Path) -> None:
    value = bundle()
    json_path = tmp_path / "result.json"
    csv_path = tmp_path / "result.csv"
    assert write_result_export_json(json_path, value) == json_path
    assert write_result_export_csv(csv_path, value) == csv_path
    assert load_result_export_json(json_path) == value
    assert load_result_export_csv(csv_path) == value
    with pytest.raises(ResultExportExistsError):
        write_result_export_json(json_path, incomplete_bundle())
    with pytest.raises(ResultExportExistsError):
        write_result_export_csv(csv_path, incomplete_bundle())
    write_result_export_json(json_path, incomplete_bundle(), overwrite=True)
    write_result_export_csv(csv_path, incomplete_bundle(), overwrite=True)
    assert load_result_export_json(json_path) == incomplete_bundle()
    assert load_result_export_csv(csv_path) == incomplete_bundle()
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize(
    "error_type",
    [
        ResultExportError,
        ResultExportFormatError,
        ResultExportLimitError,
        ResultExportPathError,
        ResultExportExistsError,
        UnsupportedResultExportVersion,
    ],
)
def test_export_errors_share_product_root(error_type: type[ResultExportError]) -> None:
    assert issubclass(error_type, AnalogValidationError)


def test_model_validation_rejects_inconsistent_values() -> None:
    schema = ExportSchemaReference("analysis", "v1")
    metric = ExportValue("gain", 2.0, "ratio")
    criterion = ExportCriterion("gain", 2.0, "ratio", True, 1.0, 3.0)
    point = points()[0]
    complete = bundle()
    assert ExportValue("note", "kept", "text").value == "kept"

    for schema_changes in (
        {"name": ""},
        {"version": " v1"},
        {"schema_version": "bad"},
    ):
        with pytest.raises(ValidationError):
            unsafe_replace(schema, **schema_changes)
    for metric_changes in (
        {"name": ""},
        {"value": math.inf},
        {"value": object()},
        {"unit": " mV"},
        {"schema_version": "bad"},
    ):
        with pytest.raises(ValidationError):
            unsafe_replace(metric, **metric_changes)
    for criterion_changes in (
        {"name": ""},
        {"actual_value": True},
        {"actual_value": math.inf},
        {"unit": ""},
        {"passed": 1},
        {"lower_limit": None, "upper_limit": None},
        {"lower_limit": 4, "upper_limit": 3},
        {"passed": False},
        {"schema_version": "bad"},
    ):
        with pytest.raises(ValidationError):
            unsafe_replace(criterion, **criterion_changes)
    for point_changes in (
        {"index": True},
        {"index": -1},
        {"label": ""},
        {"disposition": "bad"},
        {"references": "bad"},
        {"references": ()},
        {"references": ("bad",)},
        {"references": (reference(0), reference(0))},
        {"references": (reference(0), reference(1, source=EvidenceSource.HOST_TEST))},
        {"values": "bad"},
        {"values": ()},
        {"values": ("bad",)},
        {"values": (metric, metric)},
        {"quality_flags": ("x", "x")},
        {"exclusion_reasons": ("reason",)},
        {"disposition": PointDisposition.EXCLUDED},
        {"schema_version": "bad"},
    ):
        with pytest.raises(ValidationError):
            unsafe_replace(point, **point_changes)

    for bundle_changes in (
        {"test_run_result": "bad"},
        {"source_schemas": ()},
        {"source_schemas": "bad"},
        {"source_schemas": (schema, schema)},
        {"metrics": (metric, metric)},
        {"points": (unsafe_replace(point, index=1),)},
        {"limitations": ()},
        {"criteria_id": "only-id", "criteria_version": None},
        {"criteria_id": None, "criteria_version": None},
        {"criterion_results": (criterion, criterion)},
        {"schema_version": "bad"},
    ):
        with pytest.raises(ValidationError):
            unsafe_replace(complete, **bundle_changes)
    with pytest.raises(ValidationError, match="PASS/FAIL"):
        unsafe_replace(
            complete,
            criteria_id=None,
            criteria_version=None,
            criterion_results=(),
        )


def test_bundle_rejects_source_evidence_and_outcome_mismatches() -> None:
    complete = bundle()
    wrong_source_points = points(source=EvidenceSource.HOST_TEST)
    duplicate_reference = replace(
        complete.points[1],
        references=(replace(complete.points[1].references[0], record_id="record-0"),),
    )
    for mismatch_changes in (
        {"points": wrong_source_points},
        {"points": (complete.points[0], duplicate_reference)},
        {"points": complete.points[:1]},
        {"points": ()},
        {"test_run_result": replace(complete.test_run_result, outcome=RunOutcome.FAIL)},
    ):
        with pytest.raises(ValidationError):
            unsafe_replace(complete, **mismatch_changes)
    wrong_raw_metadata = replace(
        complete.test_run_result.metadata, input_record_ids=("other",)
    )
    with pytest.raises(ValidationError, match="raw IDs"):
        unsafe_replace(
            complete,
            test_run_result=replace(
                complete.test_run_result, metadata=wrong_raw_metadata
            ),
        )


def test_public_dump_argument_validation() -> None:
    with pytest.raises(ValidationError):
        result_export_to_dict("bad")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        dump_result_export_csv("bad")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "null",
        '{"schema_version":"result-export.v1"}',
        '{"a":1,"a":2}',
        '{"value":NaN}',
        "\x00",
    ],
)
def test_json_rejects_malformed_or_noncanonical_documents(text: str) -> None:
    with pytest.raises(ResultExportFormatError):
        parse_result_export_json(text)


def test_json_rejects_wrong_version_and_size() -> None:
    document = result_export_to_dict(bundle())
    document["schema_version"] = "result-export.v2"
    with pytest.raises(UnsupportedResultExportVersion):
        parse_result_export_json(json.dumps(document))
    with pytest.raises(ResultExportLimitError):
        parse_result_export_json(" " * (MAX_RESULT_EXPORT_BYTES + 1))
    with pytest.raises(ResultExportFormatError):
        parse_result_export_json(1)  # type: ignore[arg-type]


def test_json_field_type_and_enum_errors_are_stable() -> None:
    base = result_export_to_dict(bundle())
    mutations = []
    for path, value in (
        (("test_run",), []),
        (("test_run", "metadata", "started_at"), "not-time"),
        (("test_run", "metadata", "started_at"), "not-timeZ"),
        (("test_run", "metadata", "started_at"), "2026-01-01T00:00:00+00:00"),
        (("test_run", "metadata", "run_id"), 1),
        (("test_run", "metadata", "input_record_ids"), [1]),
        (("test_run", "metadata", "schema_version"), "bad"),
        (("test_run", "metadata", "evidence_source"), "FAKE"),
        (("test_run", "outcome"), "MAYBE"),
        (("points", 0, "index"), True),
        (("points", 0, "disposition"), "MAYBE"),
        (("points", 0, "references"), {}),
        (("metrics", 0, "value"), []),
        (("criteria", "results", 0, "passed"), 1),
        (("criteria", "results", 0, "actual_value"), "bad"),
        (("limitations",), []),
    ):
        mutated = json.loads(json.dumps(base))
        target: Any = mutated
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = value
        mutations.append(mutated)
    for document in mutations:
        with pytest.raises(ResultExportFormatError):
            parse_result_export_json(json.dumps(document))


def test_json_rejects_unpaired_unicode_surrogate() -> None:
    with pytest.raises(ResultExportFormatError, match="UTF-8"):
        parse_result_export_json("\ud800")


def csv_rows(value: ResultExportBundle | None = None) -> list[list[str]]:
    return list(csv.reader(io.StringIO(dump_result_export_csv(value or bundle()))))


def csv_text(rows: list[list[str]]) -> str:
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows(rows)
    return output.getvalue()


def test_csv_rejects_header_rows_order_indexes_types_and_payloads() -> None:
    cases: list[list[list[str]]] = []
    rows = csv_rows()
    wrong_header = [row[:] for row in rows]
    wrong_header[0][0] = "wrong"
    cases.append(wrong_header)
    wrong_columns = [row[:] for row in rows]
    wrong_columns[1].pop()
    cases.append(wrong_columns)
    wrong_index = [row[:] for row in rows]
    wrong_index[2][2] = "9"
    cases.append(wrong_index)
    wrong_type = [row[:] for row in rows]
    wrong_type[1][1] = "UNKNOWN"
    cases.append(wrong_type)
    wrong_payload = [row[:] for row in rows]
    wrong_payload[1][3] = "[]"
    cases.append(wrong_payload)
    bad_json = [row[:] for row in rows]
    bad_json[1][3] = "not-json"
    cases.append(bad_json)
    wrong_version = [row[:] for row in rows]
    wrong_version[1][0] = "result-export.v2"
    cases.append(wrong_version)
    out_of_order = [row[:] for row in rows]
    out_of_order[2], out_of_order[-1] = out_of_order[-1], out_of_order[2]
    for index, row in enumerate(out_of_order[1:]):
        row[2] = str(index)
    cases.append(out_of_order)
    for value in cases:
        with pytest.raises(ResultExportError):
            parse_result_export_csv(csv_text(value))


def test_csv_rejects_missing_duplicate_or_invalid_run_and_criteria() -> None:
    with pytest.raises(ResultExportFormatError):
        parse_result_export_csv(",".join(CSV_RESULT_EXPORT_COLUMNS) + "\n")
    rows = csv_rows()
    duplicate_run = [rows[0], rows[1], rows[1][:], *rows[2:]]
    for index, row in enumerate(duplicate_run[1:]):
        row[2] = str(index)
    with pytest.raises(ResultExportFormatError):
        parse_result_export_csv(csv_text(duplicate_run))
    rows = csv_rows()
    invalid_run = [row[:] for row in rows]
    invalid_run[1][3] = '{"test_run":{}}'
    with pytest.raises(ResultExportFormatError):
        parse_result_export_csv(csv_text(invalid_run))
    invalid_identity = [row[:] for row in rows]
    run_payload = json.loads(invalid_identity[1][3])
    run_payload["criteria"] = []
    invalid_identity[1][3] = json.dumps(run_payload, separators=(",", ":"))
    with pytest.raises(ResultExportFormatError, match="RUN criteria"):
        parse_result_export_csv(csv_text(invalid_identity))
    no_identity = csv_rows(incomplete_bundle())
    insert_at = next(
        index for index, row in enumerate(no_identity) if row[1] == "METRIC"
    )
    no_identity.insert(
        insert_at,
        [RESULT_EXPORT_SCHEMA_VERSION, "CRITERION", "0", '{"name":"x"}'],
    )
    for index, row in enumerate(no_identity[1:]):
        row[2] = str(index)
    with pytest.raises(ResultExportFormatError):
        parse_result_export_csv(csv_text(no_identity))
    bad_limit = [row[:] for row in rows]
    bad_limit[-1][3] = '{"wrong":"value"}'
    with pytest.raises(ResultExportFormatError, match="LIMITATION payload"):
        parse_result_export_csv(csv_text(bad_limit))
    no_run = csv_rows()
    no_run[1][1] = "SCHEMA"
    no_run[1][3] = '{"name":"test","version":"v1"}'
    with pytest.raises(ResultExportFormatError, match="RUN"):
        parse_result_export_csv(csv_text(no_run))


def test_csv_rejects_non_string_nul_size_and_row_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ResultExportFormatError):
        parse_result_export_csv(1)  # type: ignore[arg-type]
    with pytest.raises(ResultExportFormatError):
        parse_result_export_csv("\x00")
    with pytest.raises(ResultExportLimitError):
        parse_result_export_csv(" " * (MAX_RESULT_EXPORT_BYTES + 1))
    monkeypatch.setattr("analog_validation.exports.csv_v1.MAX_RESULT_EXPORT_ROWS", 0)
    with pytest.raises(ResultExportLimitError):
        parse_result_export_csv(dump_result_export_csv(bundle()))


def test_csv_rejects_invalid_unicode_and_malformed_quoting() -> None:
    with pytest.raises(ResultExportFormatError, match="UTF-8"):
        parse_result_export_csv("\ud800")
    malformed = (
        ",".join(CSV_RESULT_EXPORT_COLUMNS) + '\nresult-export.v1,RUN,0,"unterminated'
    )
    with pytest.raises(ResultExportFormatError, match="malformed"):
        parse_result_export_csv(malformed)


def test_file_access_rejects_bad_paths_encoding_size_and_argument_types(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(ResultExportPathError):
        load_result_export_json(missing)
    with pytest.raises(ResultExportPathError):
        load_result_export_json(tmp_path)
    bad_utf8 = tmp_path / "bad.json"
    bad_utf8.write_bytes(b"\xff")
    with pytest.raises(ResultExportPathError):
        load_result_export_json(bad_utf8)
    too_large = tmp_path / "large.json"
    too_large.write_bytes(b" " * (MAX_RESULT_EXPORT_BYTES + 1))
    with pytest.raises(ResultExportLimitError):
        load_result_export_json(too_large)
    with pytest.raises(ResultExportPathError):
        write_result_export_json(tmp_path / "missing" / "value.json", bundle())
    with pytest.raises(ResultExportPathError):
        file_module.read_bounded_utf8(1, maximum_bytes=10)  # type: ignore[arg-type]
    with pytest.raises(ResultExportPathError):
        file_module.write_utf8_atomic(tmp_path / "x", 1, overwrite=False)  # type: ignore[arg-type]
    with pytest.raises(ResultExportPathError):
        file_module.write_utf8_atomic(tmp_path / "x", "x", overwrite=1)  # type: ignore[arg-type]


def test_file_access_wraps_path_and_read_races(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BadPath(PathLike[str]):
        def __fspath__(self) -> str:
            raise ValueError("bad path")

    with pytest.raises(ResultExportPathError, match="invalid"):
        file_module.read_bounded_utf8(BadPath(), maximum_bytes=10)
    with pytest.raises(ResultExportPathError, match="identify a file"):
        file_module.read_bounded_utf8(".", maximum_bytes=10)

    path = tmp_path / "read.txt"
    path.write_text("", encoding="utf-8")

    def fail_read(self: Path) -> bytes:
        raise OSError("read failed")

    monkeypatch.setattr(Path, "read_bytes", fail_read)
    with pytest.raises(ResultExportPathError, match="could not be read"):
        file_module.read_bounded_utf8(path, maximum_bytes=10)
    monkeypatch.setattr(Path, "read_bytes", lambda self: b"xx")
    with pytest.raises(ResultExportLimitError):
        file_module.read_bounded_utf8(path, maximum_bytes=1)


def test_file_write_wraps_prepare_publish_and_cleanup_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "result.txt"
    original_exists = Path.exists

    def fail_parent_exists(self: Path) -> bool:
        if self == tmp_path:
            raise OSError("stat failed")
        return original_exists(self)

    monkeypatch.setattr(Path, "exists", fail_parent_exists)
    with pytest.raises(ResultExportPathError, match="prepared"):
        file_module.write_utf8_atomic(destination, "value", overwrite=False)
    monkeypatch.setattr(Path, "exists", original_exists)

    def fail_link_exists(source: Path, target: Path) -> None:
        raise FileExistsError

    monkeypatch.setattr(file_module.os, "link", fail_link_exists)
    with pytest.raises(ResultExportExistsError):
        file_module.write_utf8_atomic(destination, "value", overwrite=False)

    def fail_link(source: Path, target: Path) -> None:
        raise OSError("link failed")

    monkeypatch.setattr(file_module.os, "link", fail_link)
    with pytest.raises(ResultExportPathError, match="could not be written"):
        file_module.write_utf8_atomic(destination, "value", overwrite=False)

    def fail_unlink(self: Path, missing_ok: bool = False) -> None:
        raise OSError("cleanup failed")

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    with pytest.raises(ResultExportPathError, match="could not be written"):
        file_module.write_utf8_atomic(destination, "value", overwrite=False)
