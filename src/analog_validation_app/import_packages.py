"""Bounded offline voltage import storage and reproducible package verification.

Hashes detect changed bytes. Consistency checks reproduce the conversion, but
neither a hash nor a byte-for-byte copy proves who acquired the measurements.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import cast

from analog_validation import (
    CSV_REPLAY_COLUMNS,
    MAX_REPLAY_BYTES,
    CsvReplayDataset,
    parse_csv_replay,
)

from .atomic_directory import publish_directory_no_replace
from .models import ProductJobType, ProductSourceMode
from .product_workflows import ProductWorkflowConfiguration
from .projects import (
    MAX_VALIDATION_PROJECT_BYTES,
    ValidationPreset,
    ValidationProject,
    dump_validation_project,
)
from .tabular_import import (
    TabularImportSource,
    VoltageImportError,
    VoltageImportMapping,
    VoltageImportPreview,
    mapping_from_dict,
    mapping_to_dict,
    parse_voltage_table,
    preview_voltage_import,
)

VOLTAGE_IMPORT_MANIFEST_SCHEMA_VERSION = "voltage-import-manifest.v1"
VOLTAGE_IMPORT_MANIFEST_FILENAME = "import-manifest.json"
VOLTAGE_IMPORT_HARDWARE_CLAIM = (
    "No physical hardware validation is established by importing or replaying this file."
)
MAX_VOLTAGE_MAPPING_BYTES = 65_536
MAX_VOLTAGE_IMPORT_MANIFEST_BYTES = 65_536
_SOURCE_BYTE_LIMIT = 2_097_152
_ARTIFACT_LIMITS = {
    "source.csv": _SOURCE_BYTE_LIMIT,
    "mapping.json": MAX_VOLTAGE_MAPPING_BYTES,
    "replay.csv": MAX_REPLAY_BYTES,
    "project.json": MAX_VALIDATION_PROJECT_BYTES,
}


@dataclass(frozen=True, slots=True)
class VoltageImportPublication:
    """Published offline project with absolute paths ready for the Dashboard."""

    output_directory: Path
    replay_path: Path
    project_path: Path
    manifest_path: Path
    configuration: ProductWorkflowConfiguration


def _path(value: str | os.PathLike[str]) -> Path:
    try:
        path = Path(value).absolute()
        # Reject links in the complete path, including Windows junctions. Keep
        # the lexical path until after this check so resolve cannot hide a link.
        for item in (path, *path.parents):
            if item.is_symlink():
                raise VoltageImportError("import paths must not contain symbolic links")
            if item.exists() and getattr(item.lstat(), "st_file_attributes", 0) & 0x400:
                raise VoltageImportError("import paths must not contain reparse points")
        return path
    except (TypeError, ValueError, OSError) as error:
        raise VoltageImportError("import path is invalid or inaccessible") from error


def _read_bytes(path: Path, limit: int) -> bytes:
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise VoltageImportError("import input must be a regular file")
        if before.st_size > limit:
            raise VoltageImportError(f"import input exceeds the {limit}-byte limit")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        flags |= getattr(os, "O_NONBLOCK", 0)
        with os.fdopen(os.open(path, flags), "rb") as handle:
            opened = os.fstat(handle.fileno())
            if not stat.S_ISREG(opened.st_mode) or (
                before.st_dev, before.st_ino
            ) != (opened.st_dev, opened.st_ino):
                raise VoltageImportError("import input changed while being opened")
            data = handle.read(limit + 1)
        if len(data) > limit:
            raise VoltageImportError(f"import input exceeds the {limit}-byte limit")
        return data
    except OSError as error:
        raise VoltageImportError("import input could not be read") from error


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise VoltageImportError(f"JSON contains duplicate field: {key}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> object:
    raise VoltageImportError(f"JSON must not contain {value}")


def _json(data: bytes) -> object:
    try:
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant,
        )
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise VoltageImportError("import JSON must be valid UTF-8 JSON") from error


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def load_voltage_table(
    path: str | os.PathLike[str], *, delimiter: str = ","
) -> TabularImportSource:
    """Read at most 2 MiB from a regular file and validate its CSV structure."""
    return parse_voltage_table(_read_bytes(_path(path), _SOURCE_BYTE_LIMIT), delimiter=delimiter)


def load_voltage_mapping(path: str | os.PathLike[str]) -> VoltageImportMapping:
    """Load strict versioned JSON without opening the measurement source."""
    return mapping_from_dict(_json(_read_bytes(_path(path), MAX_VOLTAGE_MAPPING_BYTES)))


def write_voltage_mapping(
    path: str | os.PathLike[str], mapping: VoltageImportMapping
) -> Path:
    """Atomically create one mapping file; never replace an existing path."""
    destination = _path(path)
    payload = _json_bytes(mapping_to_dict(mapping))
    if len(payload) > MAX_VOLTAGE_MAPPING_BYTES:
        raise VoltageImportError("mapping JSON exceeds its byte limit")
    temporary: Path | None = None
    try:
        if destination.exists():
            raise VoltageImportError("mapping destination already exists")
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{destination.name}.", suffix=".tmp",
            dir=destination.parent, delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, destination)
    except FileExistsError as error:
        raise VoltageImportError("mapping destination already exists") from error
    except OSError as error:
        raise VoltageImportError("mapping destination could not be written") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination


def _source_name(value: object) -> str:
    if (
        not isinstance(value, str) or not value or len(value) > 256
        or value != value.strip() or not value.isprintable()
        or value in {".", ".."} or any(char in value for char in "/\\:")
    ):
        raise VoltageImportError("source_name must be a printable filename basename")
    return value


def _replay_bytes(dataset: CsvReplayDataset) -> bytes:
    """Render the existing replay grammar and check exact dataset round-trip."""
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CSV_REPLAY_COLUMNS)
    prefix = [dataset.schema_version, dataset.dataset_id]
    writer.writerow(["META", *prefix, *([""] * 10)])
    for record in dataset.records:
        writer.writerow([
            "DATA", *prefix, record.record_id, record.raw_record_id,
            record.timestamp.isoformat().replace("+00:00", "Z"), record.channel,
            "" if record.value is None else format(Decimal(str(record.value)), "f"),
            record.unit.value, record.status.value, record.declared_source.value,
            "|".join(sorted(flag.value for flag in record.quality_flags)), "",
        ])
    writer.writerow(["END", *prefix, *([""] * 9), dataset.declared_record_count])
    payload = stream.getvalue().encode("utf-8")
    if parse_csv_replay(payload) != dataset:
        raise VoltageImportError("serialized replay does not match the preview dataset")
    return payload


def _configuration(directory: Path, preview: VoltageImportPreview) -> ProductWorkflowConfiguration:
    return ProductWorkflowConfiguration(
        source_mode=ProductSourceMode.CSV_REPLAY,
        job_type=(ProductJobType.DC_ANALYSIS if preview.mapping.output_column is not None
                  and preview.row_count >= 3 else ProductJobType.READ),
        replay_path=directory / "replay.csv",
        replay_minimum=preview.mapping.minimum_mv,
        replay_maximum=preview.mapping.maximum_mv,
        sample_count=preview.row_count,
    )


def _payloads(directory: Path, preview: VoltageImportPreview) -> dict[str, bytes]:
    config = _configuration(directory, preview)
    project = ValidationProject(
        "imported-voltage", preview.mapping.name,
        "Imported voltage measurements for offline CSV replay. " + VOLTAGE_IMPORT_HARDWARE_CLAIM,
        (ValidationPreset("imported-voltage", preview.mapping.name, config),),
    )
    return {
        "source.csv": preview.source.raw_bytes,
        "mapping.json": _json_bytes(mapping_to_dict(preview.mapping)),
        "replay.csv": _replay_bytes(preview.dataset),
        "project.json": dump_validation_project(project, path=directory / "project.json").encode("utf-8"),
    }


def _manifest(preview: VoltageImportPreview, source_name: str, payloads: dict[str, bytes]) -> dict[str, object]:
    return {
        "schema_version": VOLTAGE_IMPORT_MANIFEST_SCHEMA_VERSION,
        "source_name": source_name,
        "dataset_id": preview.dataset.dataset_id,
        "row_count": preview.row_count,
        "record_count": len(preview.dataset.records),
        "evidence_source": "CSV_REPLAY",
        "hardware_claim": VOLTAGE_IMPORT_HARDWARE_CLAIM,
        "time_conversion": {
            "mode": preview.mapping.time_mode,
            "start_time_utc": preview.mapping.start_time_utc,
        },
        "artifacts": [
            {"path": name, "sha256": hashlib.sha256(payload).hexdigest(), "size_bytes": len(payload)}
            for name, payload in payloads.items()
        ],
    }


def _publication(directory: Path, preview: VoltageImportPreview) -> VoltageImportPublication:
    return VoltageImportPublication(
        directory, directory / "replay.csv", directory / "project.json",
        directory / VOLTAGE_IMPORT_MANIFEST_FILENAME, _configuration(directory, preview),
    )


def publish_voltage_import(
    output_directory: str | os.PathLike[str], preview: VoltageImportPreview,
    *, source_name: str = "source.csv",
) -> VoltageImportPublication:
    """Publish a complete new package, preserving the exact source bytes."""
    destination = _path(output_directory)
    name = _source_name(source_name)
    if not isinstance(preview, VoltageImportPreview):
        raise VoltageImportError("preview must be VoltageImportPreview")
    regenerated = preview_voltage_import(
        parse_voltage_table(preview.source.raw_bytes, delimiter=preview.mapping.delimiter),
        preview.mapping, dataset_id=preview.dataset.dataset_id,
    )
    if regenerated != preview:
        raise VoltageImportError("preview does not match its source and mapping")
    payloads = _payloads(destination, preview)
    manifest = _json_bytes(_manifest(preview, name, payloads))
    staging: Path | None = None
    try:
        if destination.exists():
            raise VoltageImportError("import output already exists")
        if not destination.parent.is_dir():
            raise VoltageImportError("import output parent must be an existing directory")
        staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent))
        for filename, payload in {**payloads, VOLTAGE_IMPORT_MANIFEST_FILENAME: manifest}.items():
            with (staging / filename).open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        publish_directory_no_replace(staging, destination)
        staging = None
    except FileExistsError as error:
        raise VoltageImportError("import output already exists") from error
    except OSError as error:
        raise VoltageImportError("import output could not be published") from error
    finally:
        if staging is not None:
            shutil.rmtree(staging)
    return _publication(destination, preview)


def verify_voltage_import(output_directory: str | os.PathLike[str]) -> VoltageImportPublication:
    """Check hashes and reproduce all derived bytes without accessing a device."""
    directory = _path(output_directory)
    if not directory.is_dir():
        raise VoltageImportError("import package must be an existing directory")
    document = _json(_read_bytes(_path(directory / VOLTAGE_IMPORT_MANIFEST_FILENAME), MAX_VOLTAGE_IMPORT_MANIFEST_BYTES))
    fields = {"schema_version", "source_name", "dataset_id", "row_count", "record_count",
              "evidence_source", "hardware_claim", "time_conversion", "artifacts"}
    if not isinstance(document, dict) or set(document) != fields:
        raise VoltageImportError("import manifest fields are invalid")
    if document["schema_version"] != VOLTAGE_IMPORT_MANIFEST_SCHEMA_VERSION:
        raise VoltageImportError("unsupported import manifest schema version")
    for field in ("row_count", "record_count"):
        if type(document[field]) is not int or not 1 <= document[field] <= 20_000:
            raise VoltageImportError(f"import manifest {field} is invalid")
    artifacts = document["artifacts"]
    if not isinstance(artifacts, list) or len(artifacts) != len(_ARTIFACT_LIMITS):
        raise VoltageImportError("import manifest must name exactly four artifacts")
    payloads: dict[str, bytes] = {}
    for item, name in zip(artifacts, _ARTIFACT_LIMITS):
        if (not isinstance(item, dict) or set(item) != {"path", "sha256", "size_bytes"}
            or item["path"] != name or type(item["size_bytes"]) is not int):
            raise VoltageImportError("import artifact fields or paths are invalid")
        data = _read_bytes(_path(directory / name), _ARTIFACT_LIMITS[name])
        if len(data) != item["size_bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise VoltageImportError(f"import artifact hash or size mismatch: {name}")
        payloads[name] = data
    mapping = mapping_from_dict(_json(payloads["mapping.json"]))
    preview = preview_voltage_import(
        parse_voltage_table(payloads["source.csv"], delimiter=mapping.delimiter), mapping,
        dataset_id=cast(str, document["dataset_id"]),
    )
    expected = _payloads(directory, preview)
    if payloads != expected:
        raise VoltageImportError("import artifacts are not consistent with source and mapping")
    if document != _manifest(preview, _source_name(document["source_name"]), expected):
        raise VoltageImportError("import manifest does not match the reproduced conversion")
    return _publication(directory, preview)


__all__ = [
    "MAX_VOLTAGE_IMPORT_MANIFEST_BYTES",
    "MAX_VOLTAGE_MAPPING_BYTES",
    "VOLTAGE_IMPORT_HARDWARE_CLAIM",
    "VOLTAGE_IMPORT_MANIFEST_FILENAME",
    "VOLTAGE_IMPORT_MANIFEST_SCHEMA_VERSION",
    "VoltageImportPublication",
    "load_voltage_mapping",
    "load_voltage_table",
    "publish_voltage_import",
    "verify_voltage_import",
    "write_voltage_mapping",
]
