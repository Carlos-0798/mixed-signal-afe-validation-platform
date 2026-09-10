"""Offline table inspection, conversion, and package verification CLI actions."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TextIO, TypeVar, cast

from .errors import CliUsageError
from .import_packages import (
    VOLTAGE_IMPORT_HARDWARE_CLAIM,
    VoltageImportPublication,
    load_voltage_mapping,
    load_voltage_table,
    publish_voltage_import,
    verify_voltage_import,
)
from .tabular_import import preview_voltage_import

_DELIMITERS = {"comma": ",", "semicolon": ";", "tab": "\t"}
_ParserT = TypeVar("_ParserT", bound=argparse.ArgumentParser)


def add_import_csv_parser(commands: argparse._SubParsersAction[_ParserT]) -> None:
    """Add CSV import actions without device discovery or optional UI imports."""
    parser = commands.add_parser("import-csv", help="inspect and import ordinary voltage CSV tables for offline replay")
    actions = parser.add_subparsers(dest="import_action", metavar="ACTION")
    inspect = actions.add_parser("inspect", help="inspect bounded columns and the first five data rows")
    inspect.add_argument("--input", required=True, type=Path)
    inspect.add_argument("--delimiter", choices=tuple(_DELIMITERS), default="comma")
    convert = actions.add_parser("convert", help="convert an explicit source and mapping into a new package")
    convert.add_argument("--input", required=True, type=Path)
    convert.add_argument("--mapping", required=True, type=Path)
    convert.add_argument("--output", required=True, type=Path)
    verify = actions.add_parser("verify", help="verify package hashes and reproduce its conversion")
    verify.add_argument("--input", required=True, type=Path)
    for action in (inspect, convert, verify):
        action.add_argument("--json", action="store_true", dest="as_json", help="emit versioned machine-readable JSON")


def _publication_document(publication: VoltageImportPublication) -> dict[str, object]:
    return {
        "output_directory": str(publication.output_directory),
        "replay_path": str(publication.replay_path),
        "project_path": str(publication.project_path),
        "manifest_path": str(publication.manifest_path),
        "row_count": publication.configuration.sample_count,
        "job_type": publication.configuration.job_type.value,
        "evidence_source": "CSV_REPLAY",
        "hardware_claim": VOLTAGE_IMPORT_HARDWARE_CLAIM,
    }


def execute_import_csv(arguments: argparse.Namespace, *, schema_version: str) -> dict[str, object]:
    """Execute one offline action; the shared CLI owns rendering and errors."""
    action = arguments.import_action
    document: dict[str, object] = {"schema_version": schema_version, "command": f"import-csv {action}"}
    if action == "inspect":
        source = load_voltage_table(arguments.input, delimiter=_DELIMITERS[arguments.delimiter])
        document.update({
            "columns": list(source.columns),
            "row_count": len(source.rows),
            "source_sha256": source.source_sha256,
            "preview_rows": [list(row) for row in source.rows[:5]],
            "preview_row_numbers": list(source.row_numbers[:5]),
        })
    elif action == "convert":
        mapping = load_voltage_mapping(arguments.mapping)
        preview = preview_voltage_import(load_voltage_table(arguments.input, delimiter=mapping.delimiter), mapping)
        publication = publish_voltage_import(arguments.output, preview, source_name=arguments.input.name)
        document.update(_publication_document(publication))
    elif action == "verify":
        publication = verify_voltage_import(arguments.input)
        document.update(_publication_document(publication))
        document["verified"] = True
    else:
        raise CliUsageError("import-csv requires an ACTION")
    return document


def write_import_csv_document(document: dict[str, object], output: TextIO) -> None:
    """Render a concise human result with an explicit evidence boundary."""
    output.write(f"{document['command']} completed.\nRows: {document['row_count']}\n")
    if "columns" in document:
        columns = cast(list[str], document["columns"])
        output.write(f"Columns: {', '.join(columns)}\n")
        output.write(f"SHA-256: {document['source_sha256']}\n")
    else:
        output.write(f"Evidence: {document['evidence_source']}\n")
        output.write(f"Project: {document['project_path']}\n")
        output.write(f"{document['hardware_claim']}\n")


__all__ = ["add_import_csv_parser", "execute_import_csv", "write_import_csv_document"]
