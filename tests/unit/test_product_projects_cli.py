from __future__ import annotations

import argparse
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import pytest

import analog_validation_app.projects as projects_module
from analog_validation import EvidenceSource
from analog_validation import TestRunOutcome as RunOutcome
from analog_validation_app import (
    MAX_VALIDATION_HISTORY_INPUTS,
    VALIDATION_RUN_MANIFEST_V1_SCHEMA_VERSION,
    ProductJobExecution,
    ProductJobType,
    ProductResultStatus,
    ProductSourceMode,
    ProductWorkerState,
    ProductWorkflowConfiguration,
    ProjectRunRecord,
    ValidationBatchCancellationToken,
    ValidationBatchPhase,
    ValidationBatchStatus,
    ValidationPreset,
    ValidationProject,
    ValidationRunManifest,
    cli,
    write_validation_project,
)
from analog_validation_app.cli import CliDependencies, build_parser, main

STAMP = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[2]


def offline_dependencies(calls: list[str] | None = None) -> CliDependencies:
    tracked = calls if calls is not None else []

    def forbidden_backend() -> Any:
        tracked.append("serial")
        raise AssertionError("project commands must not create a serial backend")

    return CliDependencies(
        serial_backend_factory=forbidden_backend,
        job_id_factory=lambda: "unused-job",
        event_id_factory=lambda: "unused-event",
    )


def run_cli(args: list[str], *, calls: list[str] | None = None) -> tuple[int, str, str]:
    output = io.StringIO()
    errors = io.StringIO()
    exit_code = main(
        args,
        stdout=output,
        stderr=errors,
        dependencies=offline_dependencies(calls),
    )
    return exit_code, output.getvalue(), errors.getvalue()


def create_project(
    tmp_path: Path,
    *,
    project_id: str = "afe-project",
    filename: str = "project.json",
) -> Path:
    path = tmp_path / filename
    exit_code, output, errors = run_cli(
        [
            "project",
            "create",
            "--output",
            str(path),
            "--project-id",
            project_id,
            "--name",
            "AFE project",
            "--description",
            "Offline acceptance suite",
            "--json",
        ]
    )
    assert exit_code == 0
    assert errors == ""
    assert json.loads(output)["project"]["project_id"] == project_id
    return path


def test_project_parser_exposes_five_bounded_actions() -> None:
    parser = build_parser()
    command_choices = next(
        action.choices
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    project_parser = cast(argparse.ArgumentParser, command_choices["project"])
    project_choices = next(
        action.choices
        for action in project_parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )

    assert tuple(project_choices) == ("create", "inspect", "run", "history", "compare")


def test_project_create_and_inspect_are_offline_and_beginner_readable(tmp_path: Path) -> None:
    calls: list[str] = []
    path = tmp_path / "project.json"
    exit_code, human, errors = run_cli(
        [
            "project",
            "create",
            "--output",
            str(path),
            "--project-id",
            "afe-project",
            "--name",
            "AFE project",
        ],
        calls=calls,
    )

    assert exit_code == 0
    assert errors == ""
    assert "Project: afe-project - AFE project" in human
    assert "Presets: 6" in human
    assert "Serial/device access: NONE" in human
    assert "Hardware performance validation: NOT CLAIMED" in human

    exit_code, machine, errors = run_cli(
        ["project", "inspect", "--input", str(path), "--json"], calls=calls
    )
    document = json.loads(machine)
    assert exit_code == 0
    assert errors == ""
    assert document["command"] == "project inspect"
    assert document["hardware_claim"] == "NO_NEW_HARDWARE_VALIDATION"
    assert len(document["project"]["presets"]) == 6
    assert calls == []


def test_project_run_history_and_compare_form_a_complete_cli_chain(tmp_path: Path) -> None:
    calls: list[str] = []
    project = create_project(tmp_path)
    run_paths: list[Path] = []
    for run_id in ("run-01", "run-02"):
        output = tmp_path / run_id
        exit_code, machine, errors = run_cli(
            [
                "project",
                "run",
                "--input",
                str(project),
                "--output",
                str(output),
                "--run-id",
                run_id,
                "--json",
            ],
            calls=calls,
        )
        document = json.loads(machine)
        assert exit_code == 0
        assert "[run " + run_id + "] PREPARING" in errors
        assert "FINISHED status=COMPLETE" in errors
        assert machine.lstrip().startswith("{")
        assert len(document["run_manifest"]["records"]) == 6
        assert document["run_manifest"]["batch_status"] == "COMPLETE"
        assert document["run_manifest"]["summary"] == {
            "completed_preset_count": 6,
            "engineering_failures": 0,
            "hardware_validation": False,
            "input_artifact_count": 0,
            "not_started_preset_count": 0,
            "operational_failures": 0,
            "planned_preset_count": 6,
            "record_count": 6,
        }
        run_paths.append(output / "run-manifest.json")

    exit_code, history, errors = run_cli(
        [
            "project",
            "history",
            "--run",
            str(run_paths[0]),
            "--run",
            str(run_paths[1]),
        ],
        calls=calls,
    )
    assert exit_code == 0
    assert errors == ""
    assert "Verified history manifests: 2" in history
    assert "engineering failures=0" in history

    exit_code, comparison, errors = run_cli(
        [
            "project",
            "compare",
            "--left",
            str(run_paths[0]),
            "--right",
            str(run_paths[1]),
            "--json",
        ],
        calls=calls,
    )
    document = json.loads(comparison)
    assert exit_code == 0
    assert errors == ""
    assert document["comparison"]["changed_entries"] == 0
    assert document["comparison"]["hardware_validation"] is False

    exit_code, human_comparison, errors = run_cli(
        [
            "project",
            "compare",
            "--left",
            str(run_paths[0]),
            "--right",
            str(run_paths[1]),
        ],
        calls=calls,
    )
    assert exit_code == 0
    assert errors == ""
    assert "Comparison: run-01 -> run-02" in human_comparison
    assert "read-default: UNCHANGED" in human_comparison
    assert calls == []


def test_project_run_can_select_one_exact_preset(tmp_path: Path) -> None:
    project = create_project(tmp_path)
    output = tmp_path / "run-one"

    exit_code, human, errors = run_cli(
        [
            "project",
            "run",
            "--input",
            str(project),
            "--output",
            str(output),
            "--run-id",
            "run-one",
            "--preset",
            "dc-default",
        ]
    )

    assert exit_code == 0
    assert "[run run-one] PREPARING preset 1/1 dc-default" in errors
    assert "FINISHED status=PARTIAL" in errors
    assert "Records: 1" in human
    assert "Batch status: PARTIAL" in human
    assert "Archived Replay inputs: 0" in human
    assert "dc-default: SUCCEEDED; outcome=PASS; evidence=SYNTHETIC" in human
    assert f"Run manifest: {output / 'run-manifest.json'}" in human


def test_project_run_human_output_identifies_archived_replay_input(
    tmp_path: Path,
) -> None:
    replay = tmp_path / "source.csv"
    replay.write_bytes(
        (ROOT / "test-data" / "golden" / "csv_replay_v1_valid.csv").read_bytes()
    )
    project = ValidationProject(
        "replay-project",
        "Replay project",
        "",
        (
            ValidationPreset(
                "replay-read",
                "Replay read",
                ProductWorkflowConfiguration(
                    ProductSourceMode.CSV_REPLAY,
                    ProductJobType.READ,
                    replay_path=replay,
                    sample_count=1,
                ),
            ),
        ),
    )
    project_path = tmp_path / "project.json"
    write_validation_project(project_path, project)
    output = tmp_path / "run"

    exit_code, human, errors = run_cli(
        [
            "project",
            "run",
            "--input",
            str(project_path),
            "--output",
            str(output),
            "--run-id",
            "run",
        ]
    )

    assert exit_code == 0
    assert "FINISHED status=COMPLETE" in errors
    assert "Archived Replay inputs: 1" in human
    assert "- Input for replay-read: inputs/01-replay-read.csv;" in human
    assert (output / "inputs" / "01-replay-read.csv").read_bytes() == replay.read_bytes()


@pytest.mark.parametrize(
    "worker_state, interrupted, expected_status, expected_exit",
    (
        (
            ProductWorkerState.CANCELLED,
            True,
            "CANCELLED",
            cli.CLI_CANCELLED_EXIT_CODE,
        ),
        (
            ProductWorkerState.FAILED,
            False,
            "ERROR",
            cli.CLI_OPERATION_ERROR_EXIT_CODE,
        ),
    ),
)
def test_project_cli_publishes_terminal_partial_history_for_cancel_or_cleanup_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    worker_state: ProductWorkerState,
    interrupted: bool,
    expected_status: str,
    expected_exit: int,
) -> None:
    project = create_project(tmp_path)

    def terminal_execution(*args: Any, **kwargs: Any) -> ProductJobExecution:
        return ProductJobExecution(
            args[0],
            worker_state,
            None,
            None,
            (),
            None,
            0,
            interrupted=interrupted,
            developer_error=RuntimeError("cleanup failed")
            if worker_state is ProductWorkerState.FAILED
            else None,
        )

    monkeypatch.setattr(
        projects_module, "execute_product_job", terminal_execution
    )
    output = tmp_path / expected_status.lower()
    exit_code, machine, errors = run_cli(
        [
            "project",
            "run",
            "--input",
            str(project),
            "--output",
            str(output),
            "--run-id",
            expected_status.lower(),
            "--preset",
            "read-default",
            "--preset",
            "dc-default",
            "--json",
        ]
    )
    document = json.loads(machine)

    assert exit_code == expected_exit
    assert document["run_manifest"]["batch_status"] == expected_status
    assert document["run_manifest"]["not_started_preset_ids"] == ["dc-default"]
    assert len(document["run_manifest"]["records"]) == 1
    assert f"FINISHED status={expected_status}" in errors


@pytest.mark.parametrize(
    "cancel_before_first, expected_records, expected_not_started",
    (
        (True, 0, ["read-default", "dc-default"]),
        (False, 1, ["dc-default"]),
    ),
)
def test_project_cli_pre_first_and_between_preset_cancellation_are_published(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cancel_before_first: bool,
    expected_records: int,
    expected_not_started: list[str],
) -> None:
    project = create_project(tmp_path)
    cancellation = ValidationBatchCancellationToken()
    if cancel_before_first:
        cancellation.request_cancel()
    publish = projects_module.publish_validation_project_run

    def controlled_publish(*args: Any, **kwargs: Any) -> Any:
        cli_reporter = kwargs["report_progress"]

        def report(event: Any) -> None:
            cli_reporter(event)
            if (
                not cancel_before_first
                and event.phase is ValidationBatchPhase.PREPARING
                and event.current_preset_number == 2
            ):
                cancellation.request_cancel()

        kwargs["cancellation"] = cancellation
        kwargs["report_progress"] = report
        return publish(*args, **kwargs)

    monkeypatch.setattr(cli, "publish_validation_project_run", controlled_publish)
    label = "pre-first" if cancel_before_first else "between"
    exit_code, machine, errors = run_cli(
        [
            "project",
            "run",
            "--input",
            str(project),
            "--output",
            str(tmp_path / label),
            "--run-id",
            label,
            "--preset",
            "read-default",
            "--preset",
            "dc-default",
            "--json",
        ]
    )
    document = json.loads(machine)

    assert exit_code == cli.CLI_CANCELLED_EXIT_CODE
    assert document["run_manifest"]["batch_status"] == "CANCELLED"
    assert len(document["run_manifest"]["records"]) == expected_records
    assert (
        document["run_manifest"]["not_started_preset_ids"]
        == expected_not_started
    )
    assert "FINISHED status=CANCELLED" in errors


def test_project_command_errors_are_structured_and_never_touch_serial(tmp_path: Path) -> None:
    calls: list[str] = []
    exit_code, _, errors = run_cli(["project"], calls=calls)
    assert exit_code == cli.CLI_USAGE_EXIT_CODE
    assert "project requires an ACTION" in errors

    project = create_project(tmp_path)
    exit_code, _, errors = run_cli(
        [
            "project",
            "run",
            "--input",
            str(project),
            "--output",
            str(tmp_path / "run"),
            "--run-id",
            "run",
            "--preset",
            "missing",
            "--json",
        ],
        calls=calls,
    )
    issue = json.loads(errors)
    assert exit_code == cli.CLI_OPERATION_ERROR_EXIT_CODE
    assert issue["issue"]["code"] == "INPUT_DATA"
    assert calls == []


def test_project_history_rejects_mixed_projects_and_excessive_inputs(
    tmp_path: Path,
) -> None:
    project = create_project(tmp_path)
    first = tmp_path / "first"
    assert run_cli(
        [
            "project",
            "run",
            "--input",
            str(project),
            "--output",
            str(first),
            "--run-id",
            "first",
            "--preset",
            "read-default",
        ]
    )[0] == 0
    other_project = create_project(
        tmp_path,
        project_id="other-project",
        filename="other-project.json",
    )
    second = tmp_path / "second"
    assert run_cli(
        [
            "project",
            "run",
            "--input",
            str(other_project),
            "--output",
            str(second),
            "--run-id",
            "second",
            "--preset",
            "read-default",
        ]
    )[0] == 0

    exit_code, _, errors = run_cli(
        [
            "project",
            "history",
            "--run",
            str(first / "run-manifest.json"),
            "--run",
            str(second / "run-manifest.json"),
        ]
    )
    assert exit_code == cli.CLI_USAGE_EXIT_CODE
    assert "one project" in errors

    exit_code, _, errors = run_cli(
        [
            "project",
            "history",
            "--run",
            str(first / "run-manifest.json"),
            "--run",
            str(first / "run-manifest.json"),
        ]
    )
    assert exit_code == cli.CLI_USAGE_EXIT_CODE
    assert "cannot repeat" in errors

    namespace = argparse.Namespace(
        project_action="history",
        run_files=[Path("run.json")] * (MAX_VALIDATION_HISTORY_INPUTS + 1),
    )
    with pytest.raises(cli.CliUsageError, match="bounded"):
        cli._execute_project_action(namespace)


def record_for_status(
    *,
    worker: ProductWorkerState = ProductWorkerState.SUCCEEDED,
    status: ProductResultStatus | None = ProductResultStatus.COMPLETED,
    outcome: RunOutcome | None = None,
) -> ProjectRunRecord:
    return ProjectRunRecord(
        "preset",
        "job",
        ProductSourceMode.SIMULATOR,
        ProductJobType.READ,
        "c" * 64,
        worker,
        status,
        outcome,
        EvidenceSource.SYNTHETIC,
        1,
        (),
        (),
    )


@pytest.mark.parametrize(
    "record, expected",
    [
        (record_for_status(worker=ProductWorkerState.CANCELLED, status=ProductResultStatus.CANCELLED), cli.CLI_CANCELLED_EXIT_CODE),
        (record_for_status(worker=ProductWorkerState.FAILED, status=ProductResultStatus.ERROR), cli.CLI_OPERATION_ERROR_EXIT_CODE),
        (record_for_status(status=ProductResultStatus.UNSUPPORTED), cli.CLI_UNSUPPORTED_EXIT_CODE),
        (record_for_status(status=ProductResultStatus.INCOMPLETE), cli.CLI_INCOMPLETE_EXIT_CODE),
        (record_for_status(outcome=RunOutcome.FAIL), cli.CLI_ENGINEERING_FAIL_EXIT_CODE),
        (record_for_status(outcome=RunOutcome.PASS), 0),
    ],
)
def test_project_batch_exit_code_preserves_failure_classes(
    record: ProjectRunRecord, expected: int
) -> None:
    manifest = ValidationRunManifest(
        "project",
        "run",
        "1",
        "project.snapshot.json",
        "d" * 64,
        STAMP,
        STAMP,
        (record,),
        schema_version=VALIDATION_RUN_MANIFEST_V1_SCHEMA_VERSION,
    )
    assert cli._project_run_exit_code(manifest) == expected


def test_project_batch_exit_code_uses_manifest_level_cancel_without_records() -> None:
    manifest = ValidationRunManifest(
        "project",
        "run",
        "1",
        "project.snapshot.json",
        "d" * 64,
        STAMP,
        STAMP,
        (),
        batch_status=ValidationBatchStatus.CANCELLED,
        planned_preset_ids=("preset",),
        not_started_preset_ids=("preset",),
    )

    assert cli._project_run_exit_code(manifest) == cli.CLI_CANCELLED_EXIT_CODE

    failed = ValidationRunManifest(
        "project",
        "error",
        "1",
        "project.snapshot.json",
        "d" * 64,
        STAMP,
        STAMP,
        (
            record_for_status(
                worker=ProductWorkerState.FAILED,
                status=ProductResultStatus.ERROR,
            ),
        ),
    )
    assert cli._project_run_exit_code(failed) == cli.CLI_OPERATION_ERROR_EXIT_CODE


def test_project_presentation_rejects_internal_shape_drift() -> None:
    for document, message in (
        ({"command": "x", "project": {"project_id": "x", "name": "x", "presets": None}}, "project presentation"),
        ({"command": "x", "project": {"project_id": "x", "name": "x", "presets": [None]}}, "preset presentation"),
        ({"command": "x", "project": {"project_id": "x", "name": "x", "presets": [{"configuration": None}]}}, "configuration presentation"),
        ({"command": "x", "run_manifest": {"run_id": "x", "records": None}}, "run presentation"),
        ({"command": "x", "run_manifest": {"run_id": "x", "records": [], "input_artifacts": {}}}, "input-artifact presentation"),
        ({"command": "x", "run_manifest": {"run_id": "x", "records": [], "input_artifacts": [None]}}, "input-artifact presentation"),
        ({"command": "x", "run_manifest": {"run_id": "x", "records": [], "not_started_preset_ids": None}}, "not-started presentation"),
        ({"command": "x", "run_manifest": {"run_id": "x", "records": [None]}}, "run record presentation"),
        ({"command": "x", "runs": [None]}, "history presentation"),
        ({"command": "x", "runs": [{"manifest": {}}]}, "history summary"),
        ({"command": "x", "comparison": {"left_run_id": "a", "right_run_id": "b", "changed_entries": 0, "entries": None}}, "comparison presentation"),
        ({"command": "x", "comparison": {"left_run_id": "a", "right_run_id": "b", "changed_entries": 0, "entries": [None]}}, "comparison entry"),
    ):
        with pytest.raises(cli.ProductServiceError, match=message):
            cli._write_project_document(cast(dict[str, object], document), io.StringIO())

    stream = io.StringIO()
    cli._write_project_document(
        {
            "command": "project run",
            "run_directory": ".",
            "run_manifest": {
                "run_id": "cancelled",
                "batch_status": "CANCELLED",
                "not_started_preset_ids": ["preset"],
                "records": [],
            },
        },
        stream,
    )
    assert "Not started: preset" in stream.getvalue()

    with pytest.raises(cli.ProductServiceError, match="project path"):
        cli._project_document(
            "x",
            project=cast(Any, cli.build_default_validation_project("project", "P")),
        )
    manifest = ValidationRunManifest(
        "project",
        "run",
        "1",
        "project.snapshot.json",
        "d" * 64,
        STAMP,
        STAMP,
        (record_for_status(),),
    )
    with pytest.raises(cli.ProductServiceError, match="run directory"):
        cli._project_document("x", run=manifest)
