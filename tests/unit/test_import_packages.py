"""Create-new import packages preserve bytes and verify conversion consistency."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import analog_validation_app.import_packages as packages
from analog_validation import MeasurementUnit, load_csv_replay
from analog_validation_app.errors import ProductRequestError
from analog_validation_app.models import ProductJobType, ProductSourceMode
from analog_validation_app.projects import load_validation_project
from analog_validation_app.tabular_import import (
    VoltageImportMapping,
    parse_voltage_table,
    preview_voltage_import,
)

RAW = b"time,input,output\r\n2026-09-09T12:00:00Z,0.1,210\r\n2026-09-09T12:00:01Z,0.2,410\r\n"


def mapping() -> VoltageImportMapping:
    return VoltageImportMapping(
        "Scope capture", "time", "input", MeasurementUnit.VOLT,
        "output", MeasurementUnit.MILLIVOLT,
    )


def preview():
    return preview_voltage_import(parse_voltage_table(RAW), mapping())


def publish(tmp_path: Path):
    return packages.publish_voltage_import(tmp_path / "package", preview(), source_name="capture.csv")


def test_source_and_mapping_load_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    source.write_bytes(RAW)
    assert packages.load_voltage_table(source).raw_bytes == RAW
    path = packages.write_voltage_mapping(tmp_path / "mapping.json", mapping())
    assert packages.load_voltage_mapping(path) == mapping()
    with pytest.raises(ProductRequestError, match="exists"):
        packages.write_voltage_mapping(path, mapping())
    assert packages.load_voltage_mapping(path) == mapping()
    assert sorted(item.name for item in tmp_path.iterdir()) == ["mapping.json", "source.csv"]


@pytest.mark.parametrize("payload", [b"[]", b'{"schema_version":1}', b'{"name":1,"name":2}', b"\xff", b"{", b'{"x":NaN}'])
def test_mapping_rejects_invalid_json(tmp_path: Path, payload: bytes) -> None:
    path = tmp_path / "mapping.json"
    path.write_bytes(payload)
    with pytest.raises(ProductRequestError):
        packages.load_voltage_mapping(path)


def test_loader_rejects_missing_directory_and_size(tmp_path: Path) -> None:
    for path in (tmp_path, tmp_path / "missing.csv"):
        with pytest.raises(ProductRequestError):
            packages.load_voltage_table(path)
    path = tmp_path / "large.csv"
    path.write_bytes(b"x" * (2_097_152 + 1))
    with pytest.raises(ProductRequestError, match="limit"):
        packages.load_voltage_table(path)


def test_publication_round_trip_and_portability(tmp_path: Path) -> None:
    publication = publish(tmp_path)
    assert publication.output_directory == (tmp_path / "package").resolve()
    assert publication.configuration.source_mode is ProductSourceMode.CSV_REPLAY
    assert publication.configuration.job_type is ProductJobType.READ
    assert publication.configuration.sample_count == 2
    assert publication.configuration.replay_path == publication.replay_path
    assert publication.replay_path.is_absolute()
    assert (publication.output_directory / "source.csv").read_bytes() == RAW
    assert load_csv_replay(publication.replay_path) == preview().dataset
    project = load_validation_project(publication.project_path)
    assert project.presets[0].configuration == publication.configuration
    document = json.loads(publication.project_path.read_text())
    assert document["presets"][0]["configuration"]["replay_path"] == "replay.csv"
    manifest = json.loads(publication.manifest_path.read_text())
    assert manifest["schema_version"] == "voltage-import-manifest.v1"
    assert manifest["source_name"] == "capture.csv"
    assert manifest["evidence_source"] == "CSV_REPLAY"
    assert manifest["row_count"] == 2
    assert "physical hardware" in manifest["hardware_claim"]
    for artifact in manifest["artifacts"]:
        payload = (publication.output_directory / artifact["path"]).read_bytes()
        assert artifact["size_bytes"] == len(payload)
        assert artifact["sha256"] == hashlib.sha256(payload).hexdigest()
    assert packages.verify_voltage_import(publication.output_directory) == publication
    relocated = tmp_path / "moved"
    publication.output_directory.rename(relocated)
    verified = packages.verify_voltage_import(relocated)
    assert verified.configuration.replay_path == relocated / "replay.csv"


@pytest.mark.parametrize("one_row,output", [(True, True), (False, True), (False, False)])
def test_small_or_single_channel_import_uses_read(tmp_path: Path, one_row: bool, output: bool) -> None:
    chosen = mapping() if output else replace(mapping(), output_column=None, output_unit=None)
    raw = RAW.splitlines(keepends=True)
    selected = b"".join(raw[:2]) if one_row else RAW
    converted = preview_voltage_import(parse_voltage_table(selected), chosen)
    result = packages.publish_voltage_import(tmp_path / "result", converted)
    assert result.configuration.job_type is ProductJobType.READ
    assert packages.verify_voltage_import(result.output_directory) == result


def test_three_paired_rows_prepare_dc_and_two_rows_preserve_both_channels(tmp_path: Path) -> None:
    raw = RAW + b"2026-09-09T12:00:02Z,0.3,610\r\n"
    converted = preview_voltage_import(parse_voltage_table(raw), mapping())
    publication = packages.publish_voltage_import(tmp_path / "three-rows", converted)
    assert publication.configuration.job_type is ProductJobType.DC_ANALYSIS
    assert publication.configuration.sample_count == 3
    assert packages.verify_voltage_import(publication.output_directory) == publication
    two_row = publish(tmp_path)
    assert two_row.configuration.job_type is ProductJobType.READ
    records = load_csv_replay(two_row.replay_path).records
    assert len(records) == 4
    assert {record.channel for record in records} == {"afe.ch0.input", "afe.ch0.output"}


@pytest.mark.parametrize("name", ["../capture.csv", "a/b.csv", "a\\b.csv", "", ".", "..", " C.csv", "C:foo", "x\x00.csv"])
def test_source_name_must_be_only_a_basename(tmp_path: Path, name: str) -> None:
    with pytest.raises(ProductRequestError):
        packages.publish_voltage_import(tmp_path / "new", preview(), source_name=name)
    assert list(tmp_path.iterdir()) == []


def test_existing_output_and_failed_publish_leave_no_partial_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "package"
    target.mkdir()
    marker = target / "keep.txt"
    marker.write_text("keep")
    with pytest.raises(ProductRequestError, match="exists"):
        publish(tmp_path)
    assert marker.read_text() == "keep"
    def fail_publish(staging: Path, destination: Path) -> None:
        assert (staging / "replay.csv").is_file()
        assert destination == tmp_path / "failed"
        raise OSError("injected publication error")
    monkeypatch.setattr(packages, "publish_directory_no_replace", fail_publish)
    with pytest.raises(ProductRequestError, match="publish"):
        packages.publish_voltage_import(tmp_path / "failed", preview())
    assert sorted(p.name for p in tmp_path.iterdir()) == ["package"]


@pytest.mark.parametrize("filename", ["source.csv", "mapping.json", "replay.csv", "project.json"])
def test_tamper_without_manifest_update_fails(tmp_path: Path, filename: str) -> None:
    publication = publish(tmp_path)
    path = publication.output_directory / filename
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ProductRequestError, match="hash|size"):
        packages.verify_voltage_import(publication.output_directory)


def test_rehashed_inconsistent_project_still_fails(tmp_path: Path) -> None:
    publication = publish(tmp_path)
    document = json.loads(publication.project_path.read_text())
    document["presets"][0]["configuration"]["replay_path"] = "../../outside.csv"
    publication.project_path.write_text(json.dumps(document))
    manifest = json.loads(publication.manifest_path.read_text())
    for item in manifest["artifacts"]:
        payload = (publication.output_directory / item["path"]).read_bytes()
        item["sha256"] = hashlib.sha256(payload).hexdigest()
        item["size_bytes"] = len(payload)
    publication.manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ProductRequestError, match="consistent|match"):
        packages.verify_voltage_import(publication.output_directory)


@pytest.mark.parametrize("change", ["version", "extra", "missing", "traversal", "bool_size", "claim", "rows", "time"])
def test_manifest_contract_is_strict(tmp_path: Path, change: str) -> None:
    publication = publish(tmp_path)
    document = json.loads(publication.manifest_path.read_text())
    if change == "version":
        document["schema_version"] = "future"
    elif change == "extra":
        document["extra"] = True
    elif change == "missing":
        del document["source_name"]
    elif change == "traversal":
        document["artifacts"][0]["path"] = "../source.csv"
    elif change == "bool_size":
        document["artifacts"][0]["size_bytes"] = True
    elif change == "claim":
        document["evidence_source"] = "HARDWARE"
    elif change == "rows":
        document["row_count"] = True
    else:
        document["time_conversion"]["start_time_utc"] = "1970-01-01T00:00:00Z"
    publication.manifest_path.write_text(json.dumps(document))
    with pytest.raises(ProductRequestError):
        packages.verify_voltage_import(publication.output_directory)


def test_path_guards_reject_links_reparse_points_and_invalid_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ProductRequestError, match="invalid"):
        packages.load_voltage_table(cast(Any, None))
    source = tmp_path / "source.csv"
    source.write_bytes(RAW)
    original_link = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == source or original_link(path))
    with pytest.raises(ProductRequestError, match="symbolic links"):
        packages.load_voltage_table(source)
    monkeypatch.setattr(Path, "is_symlink", original_link)
    original_stat = Path.lstat
    def reparse_stat(path: Path):
        if path == source:
            return SimpleNamespace(st_file_attributes=0x400)
        return original_stat(path)
    monkeypatch.setattr(Path, "is_symlink", lambda path: False)
    monkeypatch.setattr(Path, "lstat", reparse_stat)
    with pytest.raises(ProductRequestError, match="reparse"):
        packages.load_voltage_table(source)


def test_input_changed_on_open_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.csv"
    source.write_bytes(RAW)
    original = packages.os.fstat
    def replaced_descriptor(fd: int):
        result = original(fd)
        return SimpleNamespace(st_mode=result.st_mode, st_dev=result.st_dev, st_ino=result.st_ino + 1)
    monkeypatch.setattr(packages.os, "fstat", replaced_descriptor)
    with pytest.raises(ProductRequestError, match="changed"):
        packages.load_voltage_table(source)


def test_read_stays_bounded_when_size_grows_after_stat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.csv"
    source.write_bytes(RAW)
    monkeypatch.setattr(packages, "_SOURCE_BYTE_LIMIT", 10)
    original = Path.lstat
    def stale_stat(path: Path):
        result = original(path)
        if path == source:
            return SimpleNamespace(st_mode=result.st_mode, st_size=1, st_dev=result.st_dev, st_ino=result.st_ino)
        return result
    monkeypatch.setattr(Path, "lstat", stale_stat)
    with pytest.raises(ProductRequestError, match="limit"):
        packages.load_voltage_table(source)


def test_mapping_write_failures_clean_staging_and_keep_raced_destination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    destination = tmp_path / "map.json"
    def rival_link(source: Path, target: Path) -> None:
        target.write_bytes(b"rival data")
        raise FileExistsError("raced")
    monkeypatch.setattr(packages.os, "link", rival_link)
    with pytest.raises(ProductRequestError, match="exists"):
        packages.write_voltage_mapping(destination, mapping())
    assert destination.read_bytes() == b"rival data"
    assert list(tmp_path.iterdir()) == [destination]
    with pytest.raises(ProductRequestError, match="written"):
        packages.write_voltage_mapping(tmp_path / "absent" / "map.json", mapping())
    monkeypatch.setattr(packages, "MAX_VOLTAGE_MAPPING_BYTES", 1)
    with pytest.raises(ProductRequestError, match="limit"):
        packages.write_voltage_mapping(tmp_path / "oversized.json", mapping())


def test_publication_guards_preview_origin_and_parent(tmp_path: Path) -> None:
    with pytest.raises(ProductRequestError, match="VoltageImportPreview"):
        packages.publish_voltage_import(tmp_path / "result", cast(Any, None))
    original = preview()
    records = original.dataset.records
    forged = replace(original, dataset=replace(original.dataset, records=(replace(records[0], value=123.0), *records[1:])))
    with pytest.raises(ProductRequestError, match="match"):
        packages.publish_voltage_import(tmp_path / "result", forged)
    with pytest.raises(ProductRequestError, match="parent"):
        packages.publish_voltage_import(tmp_path / "missing" / "result", preview())
    assert list(tmp_path.iterdir()) == []


def test_concurrent_destination_creation_cannot_replace_existing_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    destination = tmp_path / "package"
    def concurrent_publication(staging: Path, output: Path) -> None:
        output.mkdir()
        raise FileExistsError("raced destination")
    monkeypatch.setattr(packages, "publish_directory_no_replace", concurrent_publication)
    with pytest.raises(ProductRequestError, match="exists"):
        publish(tmp_path)
    assert list(tmp_path.iterdir()) == [destination]
    assert list(destination.iterdir()) == []


def test_serializer_fails_closed_if_round_trip_changes_dataset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(packages, "parse_csv_replay", lambda payload: None)
    with pytest.raises(ProductRequestError, match="serialized replay"):
        publish(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_manifest_rejects_incomplete_artifact_set(tmp_path: Path) -> None:
    publication = publish(tmp_path)
    document = json.loads(publication.manifest_path.read_text())
    document["artifacts"].pop()
    publication.manifest_path.write_text(json.dumps(document))
    with pytest.raises(ProductRequestError, match="exactly four"):
        packages.verify_voltage_import(publication.output_directory)
