"""CSV import CLI remains offline and keeps machine output parseable."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from analog_validation import MeasurementUnit
from analog_validation_app.cli import CliDependencies, main
from analog_validation_app.import_packages import write_voltage_mapping
from analog_validation_app.tabular_import import VoltageImportMapping


def run(args: list[str]) -> tuple[int, str, str]:
    def forbidden():
        raise AssertionError("CSV import must not access serial")
    output, errors = io.StringIO(), io.StringIO()
    code = main(args, stdout=output, stderr=errors,
                dependencies=CliDependencies(serial_backend_factory=forbidden))
    return code, output.getvalue(), errors.getvalue()


@pytest.mark.parametrize("delimiter,flag", [(",", "comma"), (";", "semicolon"), ("\t", "tab")])
def test_inspect_is_bounded_and_read_only(tmp_path: Path, delimiter: str, flag: str) -> None:
    source = tmp_path / "capture.csv"
    source.write_text(f"time{delimiter}voltage\n" + "".join(f"{n}{delimiter}1.2\n" for n in range(7)))
    code, output, errors = run(["import-csv", "inspect", "--input", str(source), "--delimiter", flag, "--json"])
    assert code == 0 and errors == ""
    document = json.loads(output)
    assert document["command"] == "import-csv inspect"
    assert document["columns"] == ["time", "voltage"]
    assert document["row_count"] == 7
    assert len(document["preview_rows"]) == 5
    assert len(document["source_sha256"]) == 64
    assert len(list(tmp_path.iterdir())) == 1


def test_convert_and_verify_machine_and_human(tmp_path: Path) -> None:
    source = tmp_path / "scope.csv"
    source.write_text("time,voltage\n0,1.2\n1,1.3\n")
    mapping_path = write_voltage_mapping(tmp_path / "mapping.json", VoltageImportMapping(
        "Scope", "time", "voltage", MeasurementUnit.VOLT,
        time_mode="elapsed_seconds", start_time_utc="2026-09-09T00:00:00Z",
    ))
    destination = tmp_path / "imported"
    args = ["import-csv", "convert", "--input", str(source), "--mapping", str(mapping_path), "--output", str(destination)]
    code, output, errors = run([*args, "--json"])
    assert code == 0 and errors == ""
    document = json.loads(output)
    assert document["command"] == "import-csv convert"
    assert document["evidence_source"] == "CSV_REPLAY"
    assert document["project_path"] == str(destination / "project.json")
    for extra in ([], ["--json"]):
        code, output, errors = run(["import-csv", "verify", "--input", str(destination), *extra])
        assert code == 0 and errors == ""
        assert "CSV_REPLAY" in output
        if extra:
            assert json.loads(output)["verified"] is True
    code, output, errors = run([*args, "--json"])
    assert code != 0 and output == ""
    assert json.loads(errors)["issue"]


def test_human_inspection_and_invalid_action(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    source.write_text("time,voltage\n0,1\n")
    code, output, errors = run(["import-csv", "inspect", "--input", str(source)])
    assert code == 0 and "voltage" in output and errors == ""
    code, output, errors = run(["import-csv"])
    assert code == 2 and output == "" and "ACTION" in errors
    code, output, errors = run(["import-csv", "verify", "--input", str(tmp_path / "missing"), "--json"])
    assert code != 0 and output == "" and json.loads(errors)["issue"]


def test_two_paired_rows_create_read_setup_below_dc_minimum(tmp_path: Path) -> None:
    source = tmp_path / "two-points.csv"
    source.write_text("time,input,output\n2026-09-09T00:00:00Z,0.1,0.2\n2026-09-09T00:00:01Z,0.2,0.4\n")
    mapping = write_voltage_mapping(tmp_path / "mapping.json", VoltageImportMapping(
        "Two points", "time", "input", MeasurementUnit.VOLT, "output", MeasurementUnit.VOLT,
    ))
    code, output, errors = run(["import-csv", "convert", "--input", str(source), "--mapping", str(mapping), "--output", str(tmp_path / "result"), "--json"])
    assert code == 0 and errors == ""
    assert json.loads(output)["job_type"] == "READ"
