"""Freeze the additive offline import API and portable SYNTHETIC examples."""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
from dataclasses import MISSING, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import pytest

from analog_validation import EvidenceSource, MeasurementStatus, load_csv_replay
from analog_validation_app.import_packages import (
    load_voltage_mapping,
    load_voltage_table,
    publish_voltage_import,
    verify_voltage_import,
)
from analog_validation_app.tabular_import import (
    VoltageImportMapping,
    mapping_from_dict,
    mapping_to_dict,
    preview_voltage_import,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples" / "voltage-import"
GOLDEN = ROOT / "test-data" / "golden" / "voltage_import_v1.json"
CASE_NAMES = (
    "synthetic-comma-utc-v",
    "synthetic-semicolon-elapsed-mv",
    "synthetic-tab-reordered-mixed",
)
MODULE_NAMES = (
    "analog_validation_app.tabular_import",
    "analog_validation_app.import_packages",
    "analog_validation_app.import_cli",
)


def _default(value: object) -> object:
    return value.value if isinstance(value, Enum) else value


def public_api_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for module_name in MODULE_NAMES:
        module = importlib.import_module(module_name)
        exports = module.__all__
        signatures: dict[str, object] = {}
        models: dict[str, object] = {}
        constants: dict[str, object] = {}
        for name in exports:
            value = getattr(module, name)
            if inspect.isfunction(value) or inspect.isclass(value):
                signatures[name] = [
                    [
                        parameter.name,
                        parameter.kind.name,
                        parameter.default is inspect.Parameter.empty,
                        None
                        if parameter.default is inspect.Parameter.empty
                        else _default(parameter.default),
                    ]
                    for parameter in inspect.signature(value).parameters.values()
                ]
                if is_dataclass(value):
                    models[name] = {
                        "frozen": vars(value)["__dataclass_params__"].frozen,
                        "fields": [
                            [
                                field.name,
                                str(field.type),
                                field.default is MISSING
                                and field.default_factory is MISSING,
                                None
                                if field.default is MISSING
                                else _default(field.default),
                            ]
                            for field in fields(value)
                        ],
                    }
            else:
                constants[name] = value
        snapshot[module_name] = {
            "exports": exports,
            "signatures": signatures,
            "dataclasses": models,
            "constants": constants,
        }
    return snapshot


def example_snapshot(name: str, output: Path) -> dict[str, Any]:
    source_path = EXAMPLES / f"{name}.csv"
    mapping_path = EXAMPLES / f"{name}.mapping.json"
    mapping = load_voltage_mapping(mapping_path)
    source = load_voltage_table(source_path, delimiter=mapping.delimiter)
    preview = preview_voltage_import(
        source, mapping, dataset_id="synthetic-voltage-import-v1"
    )
    publication = publish_voltage_import(output, preview, source_name=source_path.name)
    assert verify_voltage_import(output) == publication
    assert load_csv_replay(publication.replay_path) == preview.dataset
    manifest = json.loads(publication.manifest_path.read_text(encoding="utf-8"))
    artifacts = {
        path.name: {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(output.iterdir())
    }
    return {
        "source_file": source_path.name,
        "mapping_file": mapping_path.name,
        "mapping": mapping_to_dict(mapping),
        "columns": list(source.columns),
        "row_numbers": list(source.row_numbers),
        "source_sha256": source.source_sha256,
        "manifest": manifest,
        "artifacts": artifacts,
    }


def test_voltage_import_public_api_matches_frozen_contract() -> None:
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert expected["schema_version"] == "voltage-import-golden.v1"
    assert public_api_snapshot() == expected["public_api"]
    mapping = mapping_from_dict(expected["minimal_mapping"])
    assert isinstance(mapping, VoltageImportMapping)
    assert mapping_to_dict(mapping) == expected["default_mapping"]


@pytest.mark.parametrize("name", CASE_NAMES)
def test_synthetic_examples_freeze_portable_package_bytes(
    tmp_path: Path, name: str
) -> None:
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert example_snapshot(name, tmp_path / "first") == expected["examples"][name]
    assert example_snapshot(name, tmp_path / "elsewhere") == expected["examples"][name]
    source_path = EXAMPLES / f"{name}.csv"
    assert (tmp_path / "first" / "source.csv").read_bytes() == source_path.read_bytes()
    project = json.loads(
        (tmp_path / "first" / "project.json").read_text(encoding="utf-8")
    )
    assert project["presets"][0]["configuration"]["replay_path"] == "replay.csv"


def test_all_three_layouts_have_the_same_five_synthetic_dc_points() -> None:
    datasets = []
    for name in CASE_NAMES:
        mapping = load_voltage_mapping(EXAMPLES / f"{name}.mapping.json")
        source = load_voltage_table(
            EXAMPLES / f"{name}.csv", delimiter=mapping.delimiter
        )
        evidence_index = source.columns.index("FixtureEvidence")
        assert all(row[evidence_index] == "SYNTHETIC" for row in source.rows)
        preview = preview_voltage_import(source, mapping)
        datasets.append(preview.dataset)
        assert preview.row_count == 5
        assert [record.value for record in preview.dataset.records[::2]] == [
            100,
            300,
            500,
            700,
            900,
        ]
        assert [record.value for record in preview.dataset.records[1::2]] == [
            200,
            600,
            1000,
            1400,
            1800,
        ]
        assert [
            record.timestamp.isoformat() for record in preview.dataset.records[::2]
        ] == [f"2026-09-09T12:00:0{index}+00:00" for index in range(5)]
        assert all(
            record.status is MeasurementStatus.VALID
            for record in preview.dataset.records
        )
        assert all(
            record.declared_source is EvidenceSource.CSV_REPLAY
            for record in preview.dataset.records
        )
    assert datasets[0] == datasets[1] == datasets[2]
