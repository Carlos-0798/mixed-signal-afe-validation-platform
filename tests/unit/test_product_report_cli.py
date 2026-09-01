from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

import analog_validation_app.cli as cli_module
from analog_validation import TestRunOutcome as RunOutcome
from analog_validation.exports import (
    load_result_export_json,
    write_result_export_csv,
)
from analog_validation_app.cli import (
    CLI_CANCELLED_EXIT_CODE,
    CLI_ENGINEERING_FAIL_EXIT_CODE,
    CLI_INCOMPLETE_EXIT_CODE,
    CLI_OPERATION_ERROR_EXIT_CODE,
    CLI_UNSUPPORTED_EXIT_CODE,
    CLI_USAGE_EXIT_CODE,
    main,
)

ROOT = Path(__file__).resolve().parents[2]
DC_RESULT = ROOT / "test-data" / "golden" / "phase3_dc_sweep_result_v1.json"


def test_report_json_command_publishes_five_hardware_honest_artifacts(
    tmp_path: Path,
) -> None:
    output = io.StringIO()
    destination = tmp_path / "report"

    assert (
        main(
            [
                "report",
                "--input",
                str(DC_RESULT),
                "--output",
                str(destination),
                "--json",
            ],
            stdout=output,
        )
        == 0
    )
    document = json.loads(output.getvalue())
    assert document["command"] == "report"
    assert document["report_schema_version"] == "human-report.v1"
    assert document["outcome"] == "PASS"
    assert document["evidence_source"] == "SYNTHETIC"
    assert document["hardware_claim"] == "NO_NEW_HARDWARE_VALIDATION"
    assert document["canonical_result_sha256"] == (
        "a137b527303a7a8938b4bba7f74d28f35e9a9ca013474cd5946f4d6da9591547"
    )
    assert [value["name"] for value in document["artifacts"]] == [
        "report.txt",
        "report.md",
        "report.html",
        "chart.svg",
        "manifest.json",
    ]


def test_report_human_output_lists_identity_and_artifact_hashes(tmp_path: Path) -> None:
    output = io.StringIO()
    destination = tmp_path / "human"

    assert (
        main(
            [
                "report",
                "--input",
                str(DC_RESULT),
                "--output",
                str(destination),
            ],
            stdout=output,
        )
        == 0
    )
    text = output.getvalue()
    assert "Report outcome: PASS" in text
    assert "Evidence source: SYNTHETIC" in text
    assert "Canonical result SHA-256:" in text
    assert "Artifact: report.html" in text
    assert "New hardware performance validation: NOT CLAIMED" in text


def test_report_accepts_explicit_csv_result_export(tmp_path: Path) -> None:
    csv_path = tmp_path / "result.data"
    write_result_export_csv(csv_path, load_result_export_json(DC_RESULT))
    output = io.StringIO()

    assert (
        main(
            [
                "report",
                "--input",
                str(csv_path),
                "--input-format",
                "csv",
                "--output",
                str(tmp_path / "csv-report"),
                "--json",
            ],
            stdout=output,
        )
        == 0
    )
    assert json.loads(output.getvalue())["canonical_result_sha256"] == (
        "a137b527303a7a8938b4bba7f74d28f35e9a9ca013474cd5946f4d6da9591547"
    )


def test_report_auto_detects_csv_result_export(tmp_path: Path) -> None:
    csv_path = tmp_path / "result.csv"
    write_result_export_csv(csv_path, load_result_export_json(DC_RESULT))
    output = io.StringIO()

    assert (
        main(
            [
                "report",
                "--input",
                str(csv_path),
                "--output",
                str(tmp_path / "auto-csv-report"),
                "--json",
            ],
            stdout=output,
        )
        == 0
    )
    assert json.loads(output.getvalue())["outcome"] == "PASS"


def test_report_rejects_unknown_auto_suffix_as_usage_error(tmp_path: Path) -> None:
    source = tmp_path / "result.data"
    source.write_text(DC_RESULT.read_text(encoding="utf-8"), encoding="utf-8")
    errors = io.StringIO()

    assert (
        main(
            [
                "report",
                "--input",
                str(source),
                "--output",
                str(tmp_path / "unused"),
                "--json",
            ],
            stderr=errors,
        )
        == CLI_USAGE_EXIT_CODE
    )
    assert json.loads(errors.getvalue())["issue"]["code"] == "INVALID_REQUEST"


def test_report_maps_input_output_and_existing_path_errors(tmp_path: Path) -> None:
    missing_errors = io.StringIO()
    assert (
        main(
            [
                "report",
                "--input",
                str(tmp_path / "missing.json"),
                "--output",
                str(tmp_path / "unused"),
                "--json",
            ],
            stderr=missing_errors,
        )
        == CLI_OPERATION_ERROR_EXIT_CODE
    )
    assert json.loads(missing_errors.getvalue())["issue"]["code"] == "INPUT_DATA"

    parent_errors = io.StringIO()
    assert (
        main(
            [
                "report",
                "--input",
                str(DC_RESULT),
                "--output",
                str(tmp_path / "missing-parent" / "report"),
                "--json",
            ],
            stderr=parent_errors,
        )
        == CLI_OPERATION_ERROR_EXIT_CODE
    )
    assert json.loads(parent_errors.getvalue())["issue"]["code"] == "OUTPUT_PATH"

    existing = tmp_path / "existing"
    existing.mkdir()
    existing_errors = io.StringIO()
    assert (
        main(
            [
                "report",
                "--input",
                str(DC_RESULT),
                "--output",
                str(existing),
                "--json",
            ],
            stderr=existing_errors,
        )
        == CLI_OPERATION_ERROR_EXIT_CODE
    )
    assert json.loads(existing_errors.getvalue())["issue"]["code"] == "OUTPUT_EXISTS"


def test_report_preserves_engineering_fail_exit_after_successful_publication(
    tmp_path: Path,
) -> None:
    failed_result = tmp_path / "failed-result.json"
    assert (
        main(
            [
                "simulate",
                "dc",
                "--points",
                "6",
                "--target-gain",
                "99",
                "--output",
                str(failed_result),
                "--json",
            ],
            stdout=io.StringIO(),
        )
        == CLI_ENGINEERING_FAIL_EXIT_CODE
    )
    report_output = io.StringIO()
    assert (
        main(
            [
                "report",
                "--input",
                str(failed_result),
                "--output",
                str(tmp_path / "failed-report"),
                "--json",
            ],
            stdout=report_output,
        )
        == CLI_ENGINEERING_FAIL_EXIT_CODE
    )
    assert json.loads(report_output.getvalue())["outcome"] == "FAIL"


@pytest.mark.parametrize(
    ("outcome", "exit_code"),
    [
        (RunOutcome.PASS, 0),
        (RunOutcome.FAIL, CLI_ENGINEERING_FAIL_EXIT_CODE),
        (RunOutcome.INCOMPLETE, CLI_INCOMPLETE_EXIT_CODE),
        (RunOutcome.UNSUPPORTED, CLI_UNSUPPORTED_EXIT_CODE),
        (RunOutcome.ABORTED, CLI_CANCELLED_EXIT_CODE),
        (RunOutcome.ERROR, CLI_OPERATION_ERROR_EXIT_CODE),
    ],
)
def test_report_exit_codes_preserve_finalized_engineering_semantics(
    outcome: RunOutcome,
    exit_code: int,
) -> None:
    assert cli_module._report_exit_code(outcome) == exit_code


def test_report_input_loader_defensively_rejects_impossible_format() -> None:
    with pytest.raises(cli_module.CliUsageError, match="unsupported"):
        cli_module._load_report_input(
            type(
                "Arguments",
                (),
                {"input_format": "impossible", "input": DC_RESULT},
            )()
        )
