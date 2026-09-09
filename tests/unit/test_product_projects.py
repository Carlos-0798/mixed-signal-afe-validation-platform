from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

import pytest

from analog_validation import EvidenceSource
from analog_validation import TestRunOutcome as RunOutcome
from analog_validation_app import (
    MAX_VALIDATION_PRESETS,
    VALIDATION_RUN_INPUT_ARTIFACT_SCHEMA_VERSION,
    VALIDATION_RUN_MANIFEST_V1_SCHEMA_VERSION,
    VALIDATION_RUN_MANIFEST_V2_SCHEMA_VERSION,
    ProductJobExecution,
    ProductJobType,
    ProductProjectExistsError,
    ProductProjectFormatError,
    ProductProjectLimitError,
    ProductProjectPathError,
    ProductResultStatus,
    ProductSourceMode,
    ProductWorkerState,
    ProductWorkflowConfiguration,
    ProjectMetricDelta,
    ProjectRunComparisonEntry,
    ProjectRunMetric,
    ProjectRunRecord,
    SerialSourceConfig,
    ValidationBatchCancellationToken,
    ValidationBatchPhase,
    ValidationBatchStatus,
    ValidationPreset,
    ValidationProject,
    ValidationRunComparison,
    ValidationRunInputArtifact,
    ValidationRunManifest,
    build_default_validation_project,
    compare_validation_runs,
    dump_validation_project,
    dump_validation_run_manifest,
    load_validation_project,
    load_validation_run_manifest,
    prepare_product_job,
    projects,
    publish_validation_project_run,
    validation_project_from_dict,
    validation_project_to_dict,
    validation_run_comparison_to_dict,
    validation_run_manifest_from_dict,
    validation_run_manifest_to_dict,
    write_validation_project,
)
from analog_validation_app.issues import UserIssueCode, issue_from_exception

UTC = timezone.utc
STAMP = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
SHA = "a" * 64


def write_project_replay(path: Path, *, dataset_id: str = "project-input") -> bytes:
    lines = [
        (
            "row_type,schema_version,dataset_id,record_id,raw_record_id,"
            "timestamp_utc,channel,value,unit,status,source,quality_flags,record_count"
        ),
        f"META,csv-replay.v1,{dataset_id},,,,,,,,,,",
    ]
    for index in range(5):
        lines.append(
            f"DATA,csv-replay.v1,{dataset_id},input-{index},input-{index},"
            f"2026-09-08T12:00:0{index}Z,afe.ch0.input,{100 + index},mV,"
            "VALID,SYNTHETIC,,"
        )
    lines.append(f"END,csv-replay.v1,{dataset_id},,,,,,,,,,5")
    payload = ("\n".join(lines) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def make_record(
    preset_id: str = "read-default",
    *,
    job_id: str | None = None,
    worker_state: ProductWorkerState = ProductWorkerState.SUCCEEDED,
    product_status: ProductResultStatus | None = ProductResultStatus.COMPLETED,
    outcome: RunOutcome | None = None,
    evidence: EvidenceSource | None = EvidenceSource.SYNTHETIC,
    metrics: tuple[ProjectRunMetric, ...] = (ProjectRunMetric("samples", 5, "count"),),
    result_artifact: str | None = None,
    result_sha256: str | None = None,
    coefficient_artifact: str | None = None,
    coefficient_sha256: str | None = None,
) -> ProjectRunRecord:
    return ProjectRunRecord(
        preset_id,
        job_id or f"run-01-{preset_id}",
        ProductSourceMode.SIMULATOR,
        ProductJobType.READ,
        "c" * 64,
        worker_state,
        product_status,
        outcome,
        evidence,
        5,
        metrics,
        ("Synthetic evidence only.",),
        None,
        result_artifact,
        result_sha256,
        coefficient_artifact,
        coefficient_sha256,
    )


def make_manifest(
    run_id: str = "run-01",
    *,
    project_id: str = "afe-project",
    records: tuple[ProjectRunRecord, ...] | None = None,
) -> ValidationRunManifest:
    return ValidationRunManifest(
        project_id,
        run_id,
        "0.1.0",
        "project.snapshot.json",
        "d" * 64,
        STAMP,
        STAMP + timedelta(seconds=1),
        records or (make_record(job_id=f"{run_id}-read"),),
    )


def default_project_file(tmp_path: Path) -> tuple[Path, ValidationProject]:
    project = build_default_validation_project("afe-project", "AFE project")
    path = tmp_path / "project.avp.json"
    write_validation_project(path, project)
    return path, project


def publish_default(tmp_path: Path, run_id: str = "run-01") -> tuple[Path, ValidationRunManifest]:
    _, project = default_project_file(tmp_path)
    output = tmp_path / run_id
    manifest = publish_validation_project_run(
        project,
        output,
        run_id,
        clock=lambda: STAMP,
    )
    return output, manifest


def test_default_project_is_six_preset_offline_suite() -> None:
    project = build_default_validation_project("afe-project", "AFE project", "Local")

    assert project.project_id == "afe-project"
    assert project.description == "Local"
    assert tuple(preset.preset_id for preset in project.presets) == (
        "read-default",
        "dc-default",
        "hysteresis-default",
        "calibration-default",
        "frequency-default",
        "live-default",
    )
    assert {preset.configuration.job_type for preset in project.presets} == set(
        ProductJobType
    )
    assert all(
        preset.configuration.source_mode is ProductSourceMode.SIMULATOR
        and preset.configuration.serial_config is None
        for preset in project.presets
    )


def test_project_json_round_trip_is_deterministic_and_does_not_open_replay(
    tmp_path: Path,
) -> None:
    replay = tmp_path / "inputs" / "does-not-exist.csv"
    preset = ValidationPreset(
        "replay-read",
        "Replay read",
        ProductWorkflowConfiguration(
            ProductSourceMode.CSV_REPLAY,
            ProductJobType.READ,
            replay_path=replay,
        ),
    )
    project = ValidationProject("afe-project", "AFE project", "", (preset,))
    path = tmp_path / "project.json"

    document = validation_project_to_dict(project, project_directory=tmp_path)
    presets = cast(list[dict[str, Any]], document["presets"])
    assert presets[0]["configuration"][
        "replay_path"
    ] == "inputs/does-not-exist.csv"
    assert validation_project_from_dict(document, project_directory=tmp_path) == project
    first = dump_validation_project(project, path=path)
    write_validation_project(path, project)
    loaded = load_validation_project(path)

    assert loaded == project
    assert path.read_text(encoding="utf-8") == first
    assert not replay.exists()


def test_project_replay_path_must_remain_inside_project(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.csv"
    preset = ValidationPreset(
        "outside",
        "Outside replay",
        ProductWorkflowConfiguration(
            ProductSourceMode.CSV_REPLAY,
            ProductJobType.READ,
            replay_path=outside,
        ),
    )
    project = ValidationProject("afe-project", "AFE", "", (preset,))

    with pytest.raises(ProductProjectFormatError, match="remain inside"):
        validation_project_to_dict(project, project_directory=tmp_path)

    document = validation_project_to_dict(
        build_default_validation_project("afe-project", "AFE"),
        project_directory=tmp_path,
    )
    presets = cast(list[dict[str, Any]], document["presets"])
    configuration = cast(dict[str, Any], presets[0]["configuration"])
    configuration["replay_path"] = "../outside.csv"
    with pytest.raises(ProductProjectFormatError, match="inside"):
        validation_project_from_dict(document, project_directory=tmp_path)


def test_replay_run_archives_exact_input_and_executes_the_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "inputs" / "source.csv"
    payload = write_project_replay(source)
    configuration = ProductWorkflowConfiguration(
        ProductSourceMode.CSV_REPLAY,
        ProductJobType.READ,
        replay_path=source,
        sample_count=5,
    )
    project = ValidationProject(
        "project",
        "Project",
        "",
        (ValidationPreset("replay-read", "Replay read", configuration),),
    )
    real_prepare = projects.prepare_product_job
    prepared_paths: list[Path] = []

    def observe_prepared(configuration: ProductWorkflowConfiguration, *args: Any, **kwargs: Any) -> Any:
        replay_path = cast(Path, configuration.replay_path)
        prepared_paths.append(replay_path)
        source.write_text("changed after archival", encoding="utf-8")
        return real_prepare(configuration, *args, **kwargs)

    monkeypatch.setattr(projects, "prepare_product_job", observe_prepared)
    output = tmp_path / "run"
    manifest = publish_validation_project_run(
        project,
        output,
        "run",
        project_directory=tmp_path,
        clock=lambda: STAMP,
    )

    assert manifest.schema_version == projects.VALIDATION_RUN_MANIFEST_SCHEMA_VERSION
    assert manifest.records[0].worker_state is ProductWorkerState.SUCCEEDED
    assert len(manifest.input_artifacts) == 1
    artifact = manifest.input_artifacts[0]
    assert artifact == ValidationRunInputArtifact(
        "replay-read",
        ProductSourceMode.CSV_REPLAY,
        "inputs/01-replay-read.csv",
        len(payload),
        hashlib.sha256(payload).hexdigest(),
    )
    assert artifact.schema_version == VALIDATION_RUN_INPUT_ARTIFACT_SCHEMA_VERSION
    assert len(prepared_paths) == 1
    assert prepared_paths[0].parent.name == "inputs"
    assert prepared_paths[0].name == "01-replay-read.csv"
    assert prepared_paths[0].parent.parent.name.endswith(".staging")
    assert prepared_paths[0] != source
    assert (output / artifact.artifact).read_bytes() == payload
    source.unlink()
    assert load_validation_run_manifest(output / "run-manifest.json") == manifest


def test_replay_archival_deduplicates_one_source_and_skips_not_started(
    tmp_path: Path,
) -> None:
    source = tmp_path / "inputs" / "shared.csv"
    payload = write_project_replay(source)
    configuration = ProductWorkflowConfiguration(
        ProductSourceMode.CSV_REPLAY,
        ProductJobType.READ,
        replay_path=source,
        sample_count=5,
    )
    project = ValidationProject(
        "project",
        "Project",
        "",
        (
            ValidationPreset("first", "First", configuration),
            ValidationPreset("second", "Second", configuration),
        ),
    )
    complete_output = tmp_path / "complete"
    complete = publish_validation_project_run(
        project,
        complete_output,
        "complete",
        project_directory=tmp_path,
        clock=lambda: STAMP,
    )

    assert tuple(artifact.preset_id for artifact in complete.input_artifacts) == (
        "first",
        "second",
    )
    assert len({artifact.artifact for artifact in complete.input_artifacts}) == 1
    complete_archive = complete_output / complete.input_artifacts[0].artifact
    assert complete_archive.read_bytes() == payload
    assert tuple((complete_output / "inputs").iterdir()) == (complete_archive,)

    cancellation = ValidationBatchCancellationToken()

    def cancel_second(event: projects.ValidationBatchProgress) -> None:
        if event.phase is ValidationBatchPhase.PREPARING and event.current_preset_number == 2:
            cancellation.request_cancel()

    output = tmp_path / "cancelled"
    manifest = publish_validation_project_run(
        project,
        output,
        "cancelled",
        project_directory=tmp_path,
        cancellation=cancellation,
        report_progress=cancel_second,
        clock=lambda: STAMP,
    )

    assert manifest.batch_status is ValidationBatchStatus.CANCELLED
    assert manifest.not_started_preset_ids == ("second",)
    assert tuple(artifact.preset_id for artifact in manifest.input_artifacts) == ("first",)
    archived = output / manifest.input_artifacts[0].artifact
    assert archived.read_bytes() == payload
    assert tuple((output / "inputs").iterdir()) == (archived,)


def test_v2_manifest_remains_exactly_readable_after_v3(tmp_path: Path) -> None:
    manifest = replace(
        make_manifest(),
        schema_version=VALIDATION_RUN_MANIFEST_V2_SCHEMA_VERSION,
    )
    document = validation_run_manifest_to_dict(manifest)

    assert document["schema_version"] == "validation-run-manifest.v2"
    assert "input_artifacts" not in document
    assert "input_artifact_count" not in cast(dict[str, Any], document["summary"])
    assert validation_run_manifest_from_dict(document) == manifest


def test_v3_input_artifact_contract_rejects_unsafe_or_inconsistent_values() -> None:
    valid = ValidationRunInputArtifact(
        "replay",
        ProductSourceMode.CSV_REPLAY,
        "inputs/01-replay.csv",
        10,
        SHA,
    )
    with pytest.raises(ProductProjectFormatError, match="inside inputs"):
        replace(valid, artifact="../source.csv")
    with pytest.raises(ProductProjectFormatError, match="CSV_REPLAY"):
        replace(valid, source_mode=ProductSourceMode.SIMULATOR)
    with pytest.raises(ProductProjectFormatError, match="size_bytes"):
        replace(valid, size_bytes=-1)
    with pytest.raises(ProductProjectFormatError, match="SHA-256"):
        replace(valid, sha256="not-a-digest")
    with pytest.raises(ProductProjectFormatError, match="schema"):
        replace(valid, schema_version="input-artifact.v999")
    with pytest.raises(ProductProjectFormatError, match="must be ValidationRunInputArtifact"):
        replace(make_manifest(), input_artifacts=cast(Any, (object(),)))
    with pytest.raises(ProductProjectFormatError, match="must be unique"):
        replace(make_manifest(), input_artifacts=(valid, valid))
    with pytest.raises(ProductProjectFormatError, match="v2 run manifest"):
        replace(
            make_manifest(),
            schema_version=VALIDATION_RUN_MANIFEST_V2_SCHEMA_VERSION,
            input_artifacts=(valid,),
        )

    replay_record = replace(
        make_record("replay"), source_mode=ProductSourceMode.CSV_REPLAY
    )
    with pytest.raises(ProductProjectFormatError, match="match executed CSV Replay"):
        make_manifest(records=(replay_record,))
    with pytest.raises(ProductProjectFormatError, match="match executed CSV Replay"):
        replace(make_manifest(records=(make_record(),)), input_artifacts=(valid,))


def test_v3_history_rejects_missing_tampered_or_size_mismatched_input(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.csv"
    configuration = ProductWorkflowConfiguration(
        ProductSourceMode.CSV_REPLAY,
        ProductJobType.READ,
        replay_path=source,
        sample_count=5,
    )
    project = ValidationProject(
        "project",
        "Project",
        "",
        (ValidationPreset("replay", "Replay", configuration),),
    )

    for label, mutation, message in (
        ("missing", lambda path: path.unlink(), "input artifact is missing"),
        ("tampered", lambda path: path.write_bytes(b"tampered"), "byte size mismatch"),
        (
            "same-size",
            lambda path: path.write_bytes(b"X" + path.read_bytes()[1:]),
            "SHA-256 mismatch",
        ),
    ):
        write_project_replay(source)
        output = tmp_path / label
        manifest = publish_validation_project_run(
            project,
            output,
            label,
            project_directory=tmp_path,
            clock=lambda: STAMP,
        )
        archived = output / manifest.input_artifacts[0].artifact
        mutation(archived)
        with pytest.raises((ProductProjectPathError, ProductProjectFormatError), match=message):
            load_validation_run_manifest(output / "run-manifest.json")


def test_v3_history_rejects_input_resolving_outside_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.csv"
    write_project_replay(source)
    configuration = ProductWorkflowConfiguration(
        ProductSourceMode.CSV_REPLAY,
        ProductJobType.READ,
        replay_path=source,
        sample_count=5,
    )
    project = ValidationProject(
        "project",
        "Project",
        "",
        (ValidationPreset("replay", "Replay", configuration),),
    )
    output = tmp_path / "run"
    manifest = publish_validation_project_run(
        project,
        output,
        "run",
        project_directory=tmp_path,
    )
    archived = output / manifest.input_artifacts[0].artifact
    outside = tmp_path.parent / "outside.csv"
    real_resolve = Path.resolve

    def escape_archive(path: Path, *args: Any, **kwargs: Any) -> Path:
        if path == archived:
            return outside
        return real_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", escape_archive)
    with pytest.raises(ProductProjectPathError, match="resolves outside"):
        load_validation_run_manifest(output / "run-manifest.json")


def test_replay_archival_failure_is_atomic(tmp_path: Path) -> None:
    source = tmp_path / "missing.csv"
    configuration = ProductWorkflowConfiguration(
        ProductSourceMode.CSV_REPLAY,
        ProductJobType.READ,
        replay_path=source,
    )
    project = ValidationProject(
        "project",
        "Project",
        "",
        (ValidationPreset("replay", "Replay", configuration),),
    )

    with pytest.raises(ProductProjectPathError, match="input could not be archived"):
        publish_validation_project_run(
            project,
            tmp_path / "run",
            "run",
            project_directory=tmp_path,
        )
    assert not (tmp_path / "run").exists()
    assert not tuple(tmp_path.glob(".run.*.staging"))


def test_oversized_replay_archival_is_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.csv"
    write_project_replay(source)
    project = ValidationProject(
        "project",
        "Project",
        "",
        (
            ValidationPreset(
                "replay",
                "Replay",
                ProductWorkflowConfiguration(
                    ProductSourceMode.CSV_REPLAY,
                    ProductJobType.READ,
                    replay_path=source,
                    sample_count=5,
                ),
            ),
        ),
    )
    monkeypatch.setattr(projects, "MAX_REPLAY_BYTES", 1)

    with pytest.raises(ProductProjectLimitError, match="exceeds its byte limit"):
        publish_validation_project_run(
            project,
            tmp_path / "run",
            "run",
            project_directory=tmp_path,
        )

    assert not (tmp_path / "run").exists()
    assert not tuple(tmp_path.glob(".run.*.staging"))


def test_replay_archival_handles_relative_paths_and_rejects_directory(
    tmp_path: Path,
) -> None:
    relative = Path("inputs/source.csv")
    write_project_replay(tmp_path / relative)
    configuration = ProductWorkflowConfiguration(
        ProductSourceMode.CSV_REPLAY,
        ProductJobType.READ,
        replay_path=relative,
        sample_count=5,
    )
    project = ValidationProject(
        "project",
        "Project",
        "",
        (ValidationPreset("replay", "Replay", configuration),),
    )

    manifest = publish_validation_project_run(
        project,
        tmp_path / "relative-run",
        "relative-run",
        project_directory=tmp_path,
    )
    assert manifest.input_artifacts[0].artifact == "inputs/01-replay.csv"

    directory_project = replace(
        project,
        presets=(
            replace(
                project.presets[0],
                configuration=replace(configuration, replay_path=tmp_path / "inputs"),
            ),
        ),
    )
    with pytest.raises(ProductProjectPathError, match="regular file"):
        publish_validation_project_run(
            directory_project,
            tmp_path / "directory-run",
            "directory-run",
            project_directory=tmp_path,
        )
    assert not (tmp_path / "directory-run").exists()


def test_replay_archive_write_error_is_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.csv"
    write_project_replay(source)
    configuration = ProductWorkflowConfiguration(
        ProductSourceMode.CSV_REPLAY,
        ProductJobType.READ,
        replay_path=source,
        sample_count=5,
    )
    project = ValidationProject(
        "project",
        "Project",
        "",
        (ValidationPreset("replay", "Replay", configuration),),
    )
    real_open = Path.open

    def fail_archive_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path.name == "01-replay.csv":
            raise OSError("archive destination failed")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_archive_open)
    with pytest.raises(ProductProjectPathError, match="could not be archived"):
        publish_validation_project_run(
            project,
            tmp_path / "run",
            "run",
            project_directory=tmp_path,
        )
    assert not (tmp_path / "run").exists()
    assert not tuple(tmp_path.glob(".run.*.staging"))


def test_project_publish_is_create_new_and_parent_must_exist(tmp_path: Path) -> None:
    path, project = default_project_file(tmp_path)

    with pytest.raises(ProductProjectExistsError):
        write_validation_project(path, project)
    with pytest.raises(ProductProjectPathError, match="parent"):
        write_validation_project(tmp_path / "missing" / "project.json", project)


def test_project_load_rejects_missing_directory_invalid_utf8_and_oversize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ProductProjectPathError, match="does not exist"):
        load_validation_project(tmp_path / "missing.json")
    with pytest.raises(ProductProjectPathError, match="regular file"):
        load_validation_project(tmp_path)

    invalid = tmp_path / "invalid.json"
    invalid.write_bytes(b"\xff")
    with pytest.raises(ProductProjectFormatError, match="UTF-8"):
        load_validation_project(invalid)

    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * (projects.MAX_VALIDATION_PROJECT_BYTES + 1))
    with pytest.raises(ProductProjectLimitError, match="byte limit"):
        load_validation_project(oversized)

    valid, _ = default_project_file(tmp_path)
    real_stat = Path.stat

    def shrinking_stat(path: Path, **kwargs: Any) -> os.stat_result:
        result = real_stat(path, **kwargs)
        if path == valid:
            values = list(result)
            values[6] = projects.MAX_VALIDATION_PROJECT_BYTES + 1
            return os.stat_result(values)
        return result

    monkeypatch.setattr(Path, "stat", shrinking_stat)
    with pytest.raises(ProductProjectLimitError, match="byte limit"):
        load_validation_project(valid)


@pytest.mark.parametrize(
    "payload, message",
    [
        ('{"schema_version": 1, "schema_version": 2}', "duplicate JSON field"),
        ('{"value": NaN}', "numeric constant"),
        ('{"value": 1}\x00', "NUL"),
        ("[", "not valid JSON"),
    ],
)
def test_project_load_rejects_noncanonical_json(
    tmp_path: Path, payload: str, message: str
) -> None:
    path = tmp_path / "bad.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(ProductProjectFormatError, match=message):
        load_validation_project(path)


def test_project_schema_is_exact_and_workflow_contract_is_rechecked(tmp_path: Path) -> None:
    project = build_default_validation_project("afe-project", "AFE")
    document = validation_project_to_dict(project, project_directory=tmp_path)

    extra = dict(document)
    extra["extra"] = True
    with pytest.raises(ProductProjectFormatError, match="fields"):
        validation_project_from_dict(extra, project_directory=tmp_path)

    wrong_schema = dict(document)
    wrong_schema["schema_version"] = "validation-project.v999"
    with pytest.raises(ProductProjectFormatError, match="unsupported"):
        validation_project_from_dict(wrong_schema, project_directory=tmp_path)

    invalid_workflow = json.loads(json.dumps(document))
    invalid_workflow["presets"][0]["configuration"]["sample_count"] = 0
    with pytest.raises(ProductProjectFormatError, match="product contract"):
        validation_project_from_dict(invalid_workflow, project_directory=tmp_path)


def test_saved_project_rejects_serial_configuration() -> None:
    serial = SerialSourceConfig("COM_TEST")
    configuration = ProductWorkflowConfiguration(
        ProductSourceMode.SERIAL_READ_ONLY,
        ProductJobType.READ,
        serial_config=serial,
        confirm_read_only=True,
    )
    with pytest.raises(ProductProjectFormatError, match="cannot contain Serial"):
        ValidationPreset("serial", "Serial", configuration)

    offline = ProductWorkflowConfiguration(ProductSourceMode.SIMULATOR, ProductJobType.READ)
    object.__setattr__(offline, "serial_config", serial)
    with pytest.raises(ProductProjectFormatError, match="persist serial"):
        ValidationPreset("serial-settings", "Serial settings", offline)


def test_publish_all_presets_creates_verified_immutable_history(tmp_path: Path) -> None:
    output, manifest = publish_default(tmp_path)
    manifest_path = output / projects.VALIDATION_RUN_MANIFEST_FILENAME

    assert manifest_path.is_file()
    assert len(manifest.records) == 6
    assert manifest.engineering_failures == 0
    assert manifest.operational_failures == 0
    assert all(record.source_mode is ProductSourceMode.SIMULATOR for record in manifest.records)
    assert all(record.evidence_source is EvidenceSource.SYNTHETIC for record in manifest.records)
    assert all(record.worker_state is ProductWorkerState.SUCCEEDED for record in manifest.records)
    assert all(record.product_status is ProductResultStatus.COMPLETED for record in manifest.records)
    assert load_validation_run_manifest(manifest_path) == manifest
    assert len(tuple(output.glob("*.result.json"))) == 4
    assert len(tuple(output.glob("*.coefficients.json"))) == 1
    assert (output / "project.snapshot.json").is_file()
    snapshot = output / "project.snapshot.json"
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == manifest.project_sha256
    assert all(len(record.configuration_sha256) == 64 for record in manifest.records)

    calibration = next(
        record for record in manifest.records if record.preset_id == "calibration-default"
    )
    assert calibration.coefficient_artifact is not None
    assert calibration.coefficient_sha256 is not None
    assert {metric.name for metric in calibration.metrics} >= {
        "before_rmse",
        "after_rmse",
    }
    live = next(record for record in manifest.records if record.preset_id == "live-default")
    assert {metric.name for metric in live.metrics} >= {
        "live_retained_points",
        "live_evicted_points",
        "live_invalid_points",
    }

    with pytest.raises(ProductProjectExistsError, match="already exists"):
        publish_validation_project_run(
            build_default_validation_project("afe-project", "AFE"),
            output,
            "run-01",
        )


def test_publish_selected_presets_preserves_requested_order(tmp_path: Path) -> None:
    project = build_default_validation_project("afe-project", "AFE")
    output = tmp_path / "selected"

    manifest = publish_validation_project_run(
        project,
        output,
        "run-selected",
        selected_preset_ids=("frequency-default", "read-default"),
        clock=lambda: STAMP,
    )

    assert tuple(record.preset_id for record in manifest.records) == (
        "frequency-default",
        "read-default",
    )
    assert manifest.batch_status is ValidationBatchStatus.PARTIAL
    assert manifest.planned_preset_ids == (
        "frequency-default",
        "read-default",
    )
    assert manifest.not_started_preset_ids == ()
    assert load_validation_run_manifest(
        output / projects.VALIDATION_RUN_MANIFEST_FILENAME
    ) == manifest


@pytest.mark.parametrize(
    "selection, error, message",
    [
        ("read-default", ProductProjectFormatError, "iterable"),
        (("read-default", "read-default"), ProductProjectFormatError, "repeat"),
        (("missing",), ProductProjectFormatError, "not present"),
        (tuple(f"preset-{index}" for index in range(MAX_VALIDATION_PRESETS + 1)), ProductProjectLimitError, "exceeds"),
    ],
)
def test_publish_rejects_invalid_selection(
    tmp_path: Path,
    selection: Any,
    error: type[Exception],
    message: str,
) -> None:
    project = build_default_validation_project("afe-project", "AFE")
    with pytest.raises(error, match=message):
        publish_validation_project_run(
            project,
            tmp_path / "run",
            "run-01",
            selected_preset_ids=selection,
        )


def test_publish_rejects_invalid_target_clock_and_project(tmp_path: Path) -> None:
    project = build_default_validation_project("afe-project", "AFE")

    with pytest.raises(ProductProjectFormatError, match="ValidationProject"):
        publish_validation_project_run(cast(Any, object()), tmp_path / "run", "run-01")
    with pytest.raises(ProductProjectFormatError, match="callable"):
        publish_validation_project_run(project, tmp_path / "run", "run-01", clock=cast(Any, 1))
    with pytest.raises(ProductProjectFormatError, match="cancellation"):
        publish_validation_project_run(
            project, tmp_path / "run", "run-01", cancellation=cast(Any, object())
        )
    with pytest.raises(ProductProjectFormatError, match="report_progress"):
        publish_validation_project_run(
            project, tmp_path / "run", "run-01", report_progress=cast(Any, object())
        )
    with pytest.raises(ProductProjectPathError, match="parent"):
        publish_validation_project_run(
            project,
            tmp_path / "missing" / "run",
            "run-01",
        )


def test_run_manifest_round_trip_and_summary_are_exact() -> None:
    failed = make_record(
        "failed",
        job_id="failed-job",
        worker_state=ProductWorkerState.FAILED,
        product_status=ProductResultStatus.ERROR,
        outcome=RunOutcome.FAIL,
        evidence=None,
        metrics=(),
    )
    manifest = make_manifest(records=(make_record(), failed))
    document = validation_run_manifest_to_dict(manifest)

    assert document["summary"] == {
        "completed_preset_count": 2,
        "record_count": 2,
        "engineering_failures": 1,
        "operational_failures": 1,
        "planned_preset_count": 2,
        "not_started_preset_count": 0,
        "input_artifact_count": 0,
        "hardware_validation": False,
    }
    assert document["batch_status"] == "ERROR"
    assert document["planned_preset_ids"] == ["read-default", "failed"]
    assert document["not_started_preset_ids"] == []
    assert validation_run_manifest_from_dict(document) == manifest
    assert json.loads(dump_validation_run_manifest(manifest)) == document


def test_run_manifest_v1_remains_exactly_readable_and_reserializable() -> None:
    current = validation_run_manifest_to_dict(make_manifest())
    legacy = {
        key: value
        for key, value in current.items()
        if key
        not in {
            "batch_status",
            "planned_preset_ids",
            "not_started_preset_ids",
            "input_artifacts",
        }
    }
    legacy["schema_version"] = VALIDATION_RUN_MANIFEST_V1_SCHEMA_VERSION
    legacy["summary"] = {
        "record_count": 1,
        "engineering_failures": 0,
        "operational_failures": 0,
        "hardware_validation": False,
    }

    loaded = validation_run_manifest_from_dict(legacy)

    assert loaded.schema_version == VALIDATION_RUN_MANIFEST_V1_SCHEMA_VERSION
    assert loaded.batch_status is None
    assert loaded.planned_preset_ids == ("read-default",)
    assert loaded.not_started_preset_ids == ()
    assert validation_run_manifest_to_dict(loaded) == legacy


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"event_index": 0}, "event_index"),
        ({"phase": object()}, "phase"),
        ({"total_presets": 0}, "total_presets"),
        ({"completed_presets": 2}, "completed_presets"),
        ({"current_preset_number": None}, "provided together"),
        ({"current_preset_number": 0}, "within the batch"),
        (
            {
                "phase": ValidationBatchPhase.FINISHED,
                "batch_status": ValidationBatchStatus.COMPLETE,
            },
            "cannot name",
        ),
        (
            {
                "phase": ValidationBatchPhase.FINISHED,
                "current_preset_id": None,
                "current_preset_number": None,
            },
            "requires a batch status",
        ),
        ({"batch_status": ValidationBatchStatus.COMPLETE}, "only finished"),
    ],
)
def test_batch_progress_rejects_inconsistent_snapshots(
    changes: dict[str, object], message: str
) -> None:
    values: dict[str, object] = {
        "run_id": "run",
        "event_index": 1,
        "phase": ValidationBatchPhase.PREPARING,
        "current_preset_id": "preset",
        "current_preset_number": 1,
        "total_presets": 1,
        "completed_presets": 0,
        "batch_status": None,
    }
    values.update(changes)
    with pytest.raises(ProductProjectFormatError, match=message):
        projects.ValidationBatchProgress(**cast(Any, values))


def test_v1_and_v2_manifest_state_invariants_are_strict() -> None:
    record = make_record()
    cancelled = make_record(
        worker_state=ProductWorkerState.CANCELLED,
        product_status=ProductResultStatus.CANCELLED,
    )
    failed = make_record(
        worker_state=ProductWorkerState.FAILED,
        product_status=ProductResultStatus.ERROR,
    )
    base = {
        "project_id": "project",
        "run_id": "run",
        "software_version": "1",
        "project_artifact": "project.snapshot.json",
        "project_sha256": "d" * 64,
        "started_at": STAMP,
        "completed_at": STAMP,
        "records": (record,),
    }
    with pytest.raises(ProductProjectLimitError, match="planned presets exceed"):
        ValidationRunManifest(
            **cast(Any, base),
            planned_preset_ids=tuple(
                f"preset-{index}" for index in range(MAX_VALIDATION_PRESETS + 1)
            ),
        )
    invalid: tuple[tuple[dict[str, object], str], ...] = (
        ({"planned_preset_ids": cast(Any, ["read-default"])}, "must be a tuple"),
        ({"not_started_preset_ids": cast(Any, ["later"])}, "must be a tuple"),
        ({"planned_preset_ids": ("read-default", "read-default")}, "must be unique"),
        (
            {
                "planned_preset_ids": ("read-default", "later", "third"),
                "not_started_preset_ids": ("later", "later"),
            },
            "not-started preset IDs must be unique",
        ),
        (
            {
                "records": (),
                "schema_version": VALIDATION_RUN_MANIFEST_V1_SCHEMA_VERSION,
                "planned_preset_ids": ("read-default",),
            },
            "v1 run manifest must contain records",
        ),
        (
            {
                "schema_version": VALIDATION_RUN_MANIFEST_V1_SCHEMA_VERSION,
                "batch_status": ValidationBatchStatus.COMPLETE,
            },
            "cannot carry v2",
        ),
        ({"batch_status": cast(Any, "COMPLETE")}, "requires a ValidationBatchStatus"),
        ({"planned_preset_ids": ("other",)}, "absent from its planned order"),
        (
            {"records": (failed,), "batch_status": ValidationBatchStatus.COMPLETE},
            "failed records require ERROR",
        ),
        (
            {
                "records": (cancelled,),
                "batch_status": ValidationBatchStatus.COMPLETE,
            },
            "cancelled records require",
        ),
        ({"batch_status": ValidationBatchStatus.ERROR}, "requires a failed record"),
        (
            {"batch_status": ValidationBatchStatus.CANCELLED},
            "requires cancelled or not-started",
        ),
        (
            {
                "batch_status": ValidationBatchStatus.COMPLETE,
                "planned_preset_ids": ("read-default", "later"),
                "not_started_preset_ids": ("later",),
            },
            "cannot contain not-started",
        ),
    )
    for changes, message in invalid:
        values = dict(base)
        values.update(changes)
        with pytest.raises(ProductProjectFormatError, match=message):
            ValidationRunManifest(**cast(Any, values))

    inferred_values = dict(base)
    inferred_values["records"] = (cancelled,)
    inferred_cancel = ValidationRunManifest(**cast(Any, inferred_values))
    assert inferred_cancel.batch_status is ValidationBatchStatus.CANCELLED


def test_batch_cancel_before_first_preset_publishes_zero_record_manifest(
    tmp_path: Path,
) -> None:
    project = build_default_validation_project("project", "Project")
    cancellation = ValidationBatchCancellationToken()
    assert cancellation.request_cancel()
    assert not cancellation.request_cancel()
    progress: list[projects.ValidationBatchProgress] = []

    manifest = publish_validation_project_run(
        project,
        tmp_path / "cancelled",
        "cancelled",
        cancellation=cancellation,
        report_progress=progress.append,
        clock=lambda: STAMP,
    )

    assert manifest.batch_status is ValidationBatchStatus.CANCELLED
    assert manifest.records == ()
    assert manifest.planned_preset_ids == tuple(
        preset.preset_id for preset in project.presets
    )
    assert manifest.not_started_preset_ids == manifest.planned_preset_ids
    assert progress[-1].phase is ValidationBatchPhase.FINISHED
    assert progress[-1].batch_status is ValidationBatchStatus.CANCELLED
    assert progress[-1].completed_presets == 0
    assert load_validation_run_manifest(
        tmp_path / "cancelled" / "run-manifest.json"
    ) == manifest


def test_batch_cancel_between_presets_preserves_completed_and_marks_rest(
    tmp_path: Path,
) -> None:
    project = build_default_validation_project("project", "Project")
    cancellation = ValidationBatchCancellationToken()
    progress: list[projects.ValidationBatchProgress] = []

    def observe(event: Any) -> None:
        progress.append(event)
        if (
            event.phase is ValidationBatchPhase.PREPARING
            and event.current_preset_number == 2
        ):
            cancellation.request_cancel()

    manifest = publish_validation_project_run(
        project,
        tmp_path / "between",
        "between",
        selected_preset_ids=("read-default", "dc-default", "frequency-default"),
        cancellation=cancellation,
        report_progress=observe,
        clock=lambda: STAMP,
    )

    assert manifest.batch_status is ValidationBatchStatus.CANCELLED
    assert tuple(record.preset_id for record in manifest.records) == ("read-default",)
    assert manifest.not_started_preset_ids == ("dc-default", "frequency-default")
    assert progress[-1].completed_presets == 1
    assert all(event.total_presets == 3 for event in progress)


def test_batch_cancel_requested_as_worker_finishes_stops_before_next_preset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = build_default_validation_project("project", "Project")
    cancellation = ValidationBatchCancellationToken()
    execute = projects.execute_product_job

    def finish_then_cancel(*args: Any, **kwargs: Any) -> ProductJobExecution:
        execution = execute(*args, **kwargs)
        cancellation.request_cancel()
        return execution

    monkeypatch.setattr(projects, "execute_product_job", finish_then_cancel)
    manifest = publish_validation_project_run(
        project,
        tmp_path / "after-worker",
        "after-worker",
        selected_preset_ids=("read-default", "dc-default"),
        cancellation=cancellation,
        clock=lambda: STAMP,
    )

    assert manifest.batch_status is ValidationBatchStatus.CANCELLED
    assert tuple(record.preset_id for record in manifest.records) == ("read-default",)
    assert manifest.not_started_preset_ids == ("dc-default",)


def test_batch_cancel_during_worker_cleans_up_and_stops_later_presets(
    tmp_path: Path,
) -> None:
    project = build_default_validation_project("project", "Project")
    cancellation = ValidationBatchCancellationToken()
    progress: list[projects.ValidationBatchProgress] = []

    def observe(event: Any) -> None:
        progress.append(event)
        if event.phase is ValidationBatchPhase.RUNNING:
            cancellation.request_cancel()

    manifest = publish_validation_project_run(
        project,
        tmp_path / "during",
        "during",
        selected_preset_ids=("live-default", "read-default"),
        cancellation=cancellation,
        report_progress=observe,
        clock=lambda: STAMP,
    )

    assert manifest.batch_status is ValidationBatchStatus.CANCELLED
    assert len(manifest.records) == 1
    assert manifest.records[0].preset_id == "live-default"
    assert manifest.records[0].worker_state is ProductWorkerState.CANCELLED
    assert manifest.not_started_preset_ids == ("read-default",)
    assert ValidationBatchPhase.CANCELLING in tuple(event.phase for event in progress)


def test_worker_or_cleanup_error_stops_batch_and_publishes_error_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = build_default_validation_project("project", "Project")
    calls: list[str] = []

    def failed_execution(*args: Any, **kwargs: Any) -> ProductJobExecution:
        request = args[0]
        calls.append(request.job_id)
        return ProductJobExecution(
            request,
            ProductWorkerState.FAILED,
            None,
            None,
            (),
            None,
            0,
            developer_error=RuntimeError("cleanup failed"),
        )

    monkeypatch.setattr(projects, "execute_product_job", failed_execution)
    manifest = publish_validation_project_run(
        project,
        tmp_path / "error",
        "error",
        selected_preset_ids=("read-default", "dc-default"),
        clock=lambda: STAMP,
    )

    assert manifest.batch_status is ValidationBatchStatus.ERROR
    assert len(calls) == 1
    assert tuple(record.preset_id for record in manifest.records) == ("read-default",)
    assert manifest.not_started_preset_ids == ("dc-default",)


@pytest.mark.parametrize(
    "summary_key, value",
    [
        ("record_count", 99),
        ("engineering_failures", 99),
        ("operational_failures", 99),
        ("hardware_validation", True),
        ("planned_preset_count", 99),
        ("completed_preset_count", 99),
        ("not_started_preset_count", 99),
        ("input_artifact_count", 99),
    ],
)
def test_run_manifest_rejects_inconsistent_summary(
    summary_key: str, value: object
) -> None:
    document = validation_run_manifest_to_dict(make_manifest())
    cast(dict[str, object], document["summary"])[summary_key] = value

    with pytest.raises(ProductProjectFormatError):
        validation_run_manifest_from_dict(document)


def test_run_manifest_load_verifies_artifact_integrity(tmp_path: Path) -> None:
    output, manifest = publish_default(tmp_path)
    manifest_path = output / projects.VALIDATION_RUN_MANIFEST_FILENAME
    record = next(record for record in manifest.records if record.result_artifact)
    artifact = output / cast(str, record.result_artifact)
    original = artifact.read_bytes()
    artifact.write_bytes(original + b"tampered")

    with pytest.raises(ProductProjectFormatError, match="SHA-256 mismatch"):
        load_validation_run_manifest(manifest_path)
    assert load_validation_run_manifest(manifest_path, verify_artifacts=False) == manifest
    with pytest.raises(ProductProjectFormatError, match="boolean"):
        load_validation_run_manifest(manifest_path, verify_artifacts=cast(Any, 1))


def test_run_manifest_load_rejects_missing_and_oversized_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output, manifest = publish_default(tmp_path)
    manifest_path = output / projects.VALIDATION_RUN_MANIFEST_FILENAME
    record = next(record for record in manifest.records if record.result_artifact)
    artifact = output / cast(str, record.result_artifact)
    artifact.unlink()
    with pytest.raises(ProductProjectPathError, match="missing"):
        load_validation_run_manifest(manifest_path)

    second = tmp_path / "second"
    second.mkdir()
    output2, manifest2 = publish_default(second, "run-02")
    manifest_path2 = output2 / projects.VALIDATION_RUN_MANIFEST_FILENAME
    record2 = next(record for record in manifest2.records if record.result_artifact)
    artifact2 = output2 / cast(str, record2.result_artifact)
    real_stat = Path.stat

    def oversized_stat(path: Path, **kwargs: Any) -> os.stat_result:
        result = real_stat(path, **kwargs)
        if path == artifact2:
            values = list(result)
            values[6] = projects.MAX_RESULT_EXPORT_BYTES + 1
            return os.stat_result(values)
        return result

    monkeypatch.setattr(Path, "stat", oversized_stat)
    with pytest.raises(ProductProjectLimitError, match="byte limit"):
        load_validation_run_manifest(manifest_path2)


def test_identical_runs_compare_without_treating_hashes_as_semantic_change() -> None:
    left_record = make_record(
        result_artifact="left.json", result_sha256="a" * 64
    )
    right_record = replace(
        left_record,
        job_id="run-02-read",
        result_artifact="right.json",
        result_sha256="b" * 64,
    )
    comparison = compare_validation_runs(
        make_manifest("run-01", records=(left_record,)),
        make_manifest("run-02", records=(right_record,)),
    )
    document = validation_run_comparison_to_dict(comparison)

    assert comparison.changed_entries == 0
    assert document["hardware_validation"] is False
    assert document["changed_entries"] == 0
    assert cast(list[dict[str, Any]], document["entries"])[0]["changed"] is False


def test_comparison_reports_project_and_matching_preset_configuration_changes() -> None:
    left_record = make_record()
    right_record = replace(
        left_record,
        job_id="run-02-read",
        configuration_sha256="e" * 64,
    )
    comparison = compare_validation_runs(
        make_manifest("run-01", records=(left_record,)),
        replace(
            make_manifest("run-02", records=(right_record,)),
            project_sha256="f" * 64,
        ),
    )
    document = validation_run_comparison_to_dict(comparison)

    assert comparison.project_changed
    assert comparison.changed_entries == 1
    assert document["project_changed"] is True
    assert cast(list[dict[str, Any]], document["entries"])[0]["changed"] is True


def test_project_snapshot_is_hash_verified_with_other_run_artifacts(tmp_path: Path) -> None:
    output, _ = publish_default(tmp_path)
    manifest_path = output / projects.VALIDATION_RUN_MANIFEST_FILENAME
    snapshot = output / projects.VALIDATION_PROJECT_SNAPSHOT_FILENAME
    snapshot.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ProductProjectFormatError, match="project artifact SHA-256"):
        load_validation_run_manifest(manifest_path)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("project-id", "project_id does not match"),
        ("unknown-preset", "preset is absent"),
        ("configuration", "configuration SHA-256 does not match"),
    ],
)
def test_project_snapshot_lineage_is_cross_checked(
    tmp_path: Path, mutation: str, message: str
) -> None:
    output, _ = publish_default(tmp_path)
    manifest_path = output / projects.VALIDATION_RUN_MANIFEST_FILENAME
    document = cast(dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8")))
    records = cast(list[dict[str, Any]], document["records"])
    if mutation == "project-id":
        document["project_id"] = "different-project"
    elif mutation == "unknown-preset":
        records[0]["preset_id"] = "unknown-preset"
        cast(list[str], document["planned_preset_ids"])[0] = "unknown-preset"
    else:
        records[0]["configuration_sha256"] = "0" * 64
    manifest_path.write_text(
        json.dumps(document, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    with pytest.raises(ProductProjectFormatError, match=message):
        load_validation_run_manifest(manifest_path)


def test_v2_snapshot_lineage_rejects_false_complete_or_partial_status(
    tmp_path: Path,
) -> None:
    output, _ = publish_default(tmp_path)
    manifest_path = output / projects.VALIDATION_RUN_MANIFEST_FILENAME
    original = cast(
        dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8"))
    )

    partial = json.loads(json.dumps(original))
    partial["batch_status"] = "PARTIAL"
    manifest_path.write_text(
        json.dumps(partial, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    with pytest.raises(ProductProjectFormatError, match="strict project subset"):
        load_validation_run_manifest(manifest_path)

    false_complete = json.loads(json.dumps(original))
    false_complete["records"] = false_complete["records"][:-1]
    false_complete["planned_preset_ids"] = false_complete["planned_preset_ids"][:-1]
    false_complete["summary"]["record_count"] -= 1
    false_complete["summary"]["planned_preset_count"] -= 1
    false_complete["summary"]["completed_preset_count"] -= 1
    manifest_path.write_text(
        json.dumps(false_complete, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ProductProjectFormatError, match="every project preset"):
        load_validation_run_manifest(manifest_path)


def test_v1_snapshot_lineage_still_rejects_unknown_record_preset(
    tmp_path: Path,
) -> None:
    output, _ = publish_default(tmp_path)
    manifest_path = output / projects.VALIDATION_RUN_MANIFEST_FILENAME
    document = cast(
        dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    document["schema_version"] = VALIDATION_RUN_MANIFEST_V1_SCHEMA_VERSION
    for key in (
        "batch_status",
        "planned_preset_ids",
        "not_started_preset_ids",
        "input_artifacts",
    ):
        del document[key]
    document["summary"] = {
        key: value
        for key, value in cast(dict[str, Any], document["summary"]).items()
        if key
        in {
            "record_count",
            "engineering_failures",
            "operational_failures",
            "hardware_validation",
        }
    }
    cast(list[dict[str, Any]], document["records"])[0]["preset_id"] = "unknown"
    manifest_path.write_text(
        json.dumps(document, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    with pytest.raises(ProductProjectFormatError, match="preset is absent"):
        load_validation_run_manifest(manifest_path)


def test_project_snapshot_lineage_rejects_non_utf8_content(tmp_path: Path) -> None:
    output, _ = publish_default(tmp_path)
    manifest_path = output / projects.VALIDATION_RUN_MANIFEST_FILENAME
    snapshot = output / projects.VALIDATION_PROJECT_SNAPSHOT_FILENAME
    snapshot.write_bytes(b"\xff")
    document = cast(dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8")))
    document["project_sha256"] = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    manifest_path.write_text(
        json.dumps(document, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    with pytest.raises(ProductProjectFormatError, match="UTF-8"):
        load_validation_run_manifest(manifest_path)


def test_comparison_detects_missing_records_status_and_metric_deltas() -> None:
    left_a = make_record("a", job_id="left-a")
    left_b = make_record("b", job_id="left-b")
    right_a = replace(
        left_a,
        job_id="right-a",
        product_status=ProductResultStatus.INCOMPLETE,
        metrics=(
            ProjectRunMetric("samples", 7, "count"),
            ProjectRunMetric("new", 1, "mV"),
        ),
    )
    right_c = make_record("c", job_id="right-c")

    comparison = compare_validation_runs(
        make_manifest("run-01", records=(left_a, left_b)),
        make_manifest("run-02", records=(right_a, right_c)),
    )

    assert tuple(entry.preset_id for entry in comparison.entries) == ("a", "b", "c")
    assert comparison.changed_entries == 3
    deltas = comparison.entries[0].metric_deltas
    assert deltas[0].delta == 2
    assert deltas[1].delta is None
    assert all(entry.changed for entry in comparison.entries)


def test_comparison_requires_manifests_from_same_project() -> None:
    with pytest.raises(ProductProjectFormatError, match="ValidationRunManifest"):
        compare_validation_runs(cast(Any, object()), make_manifest())
    with pytest.raises(ProductProjectFormatError, match="different projects"):
        compare_validation_runs(make_manifest(), make_manifest(project_id="other"))
    with pytest.raises(ProductProjectFormatError, match="ValidationRunComparison"):
        validation_run_comparison_to_dict(cast(Any, object()))
    with pytest.raises(ProductProjectFormatError, match="ValidationRunManifest"):
        validation_run_manifest_to_dict(cast(Any, object()))
    with pytest.raises(ProductProjectFormatError, match="ValidationProject"):
        validation_project_to_dict(cast(Any, object()), project_directory=Path.cwd())


def test_value_objects_enforce_bounded_typed_contracts() -> None:
    metric = ProjectRunMetric("gain", 2, "ratio")
    assert metric.value == 2.0
    with pytest.raises(ProductProjectFormatError, match="finite"):
        ProjectRunMetric("gain", float("inf"), "ratio")
    with pytest.raises(ProductProjectFormatError, match="numeric"):
        ProjectRunMetric("gain", cast(Any, True), "ratio")

    for kwargs in (
        {"source_mode": cast(Any, "SIMULATOR")},
        {"job_type": cast(Any, "READ")},
        {"worker_state": ProductWorkerState.RUNNING},
        {"product_status": cast(Any, "COMPLETED")},
        {"engineering_outcome": cast(Any, "PASS")},
        {"evidence": cast(Any, "SYNTHETIC")},
        {"metrics": cast(Any, [])},
        {"issue_code": cast(Any, "INVALID_REQUEST")},
    ):
        values: dict[str, Any] = {
            "preset_id": "read-default",
            "job_id": "job",
            "source_mode": ProductSourceMode.SIMULATOR,
            "job_type": ProductJobType.READ,
            "worker_state": ProductWorkerState.SUCCEEDED,
            "product_status": ProductResultStatus.COMPLETED,
            "engineering_outcome": None,
            "evidence": EvidenceSource.SYNTHETIC,
            "metrics": (),
            "issue_code": None,
        }
        values.update(kwargs)
        with pytest.raises(ProductProjectFormatError):
            ProjectRunRecord(
                values["preset_id"],
                values["job_id"],
                values["source_mode"],
                values["job_type"],
                "c" * 64,
                values["worker_state"],
                values["product_status"],
                values["engineering_outcome"],
                values["evidence"],
                0,
                values["metrics"],
                (),
                values["issue_code"],
            )


@pytest.mark.parametrize(
    "artifact,digest",
    [
        ("result.json", None),
        (None, SHA),
        ("../result.json", SHA),
        ("result.json", "bad"),
    ],
)
def test_run_record_rejects_invalid_artifact_pairs(
    artifact: str | None, digest: str | None
) -> None:
    with pytest.raises(ProductProjectFormatError):
        make_record(result_artifact=artifact, result_sha256=digest)


def test_project_and_manifest_collection_invariants() -> None:
    preset = ValidationPreset(
        "read", "Read", ProductWorkflowConfiguration(ProductSourceMode.SIMULATOR, ProductJobType.READ)
    )
    with pytest.raises(ProductProjectFormatError, match="tuple"):
        ValidationProject("project", "Project", "", cast(Any, [preset]))
    with pytest.raises(ProductProjectFormatError, match="at least"):
        ValidationProject("project", "Project", "", ())
    with pytest.raises(ProductProjectFormatError, match="unique"):
        ValidationProject("project", "Project", "", (preset, preset))
    with pytest.raises(ProductProjectLimitError, match="exceeds"):
        ValidationProject(
            "project",
            "Project",
            "",
            tuple(replace(preset, preset_id=f"preset-{index}") for index in range(MAX_VALIDATION_PRESETS + 1)),
        )

    record = make_record()
    with pytest.raises(ProductProjectFormatError, match="tuple"):
        ValidationRunManifest(
            "project",
            "run",
            "1",
            "project.snapshot.json",
            "d" * 64,
            STAMP,
            STAMP,
            cast(Any, [record]),
        )
    with pytest.raises(ProductProjectFormatError, match="contain records"):
        ValidationRunManifest(
            "project", "run", "1", "project.snapshot.json", "d" * 64, STAMP, STAMP, ()
        )
    with pytest.raises(ProductProjectFormatError, match="preset IDs"):
        make_manifest(records=(record, replace(record, job_id="other")))
    with pytest.raises(ProductProjectFormatError, match="job IDs"):
        make_manifest(records=(record, replace(record, preset_id="other")))
    with pytest.raises(ProductProjectFormatError, match="snapshot filename"):
        replace(make_manifest(), project_artifact="renamed-project.json")
    with pytest.raises(ProductProjectFormatError, match="precede"):
        ValidationRunManifest(
            "project",
            "run",
            "1",
            "project.snapshot.json",
            "d" * 64,
            STAMP,
            STAMP - timedelta(seconds=1),
            (record,),
        )


def test_comparison_value_object_invariants() -> None:
    record = make_record()
    delta = ProjectMetricDelta("samples", "count", 1, 2)
    assert delta.delta == 1
    assert delta.changed
    assert ProjectMetricDelta("samples", "count", None, 2).delta is None
    with pytest.raises(ProductProjectFormatError, match="finite"):
        ProjectMetricDelta("samples", "count", float("nan"), 2)

    with pytest.raises(ProductProjectFormatError, match="requires"):
        ProjectRunComparisonEntry("read-default", None, None, ())
    with pytest.raises(ProductProjectFormatError, match="match"):
        ProjectRunComparisonEntry("other", record, None, ())
    with pytest.raises(ProductProjectFormatError, match="ProjectRunRecord"):
        ProjectRunComparisonEntry("read-default", cast(Any, object()), None, ())
    with pytest.raises(ProductProjectFormatError, match="ProjectMetricDelta"):
        ProjectRunComparisonEntry("read-default", record, None, cast(Any, (object(),)))

    entry = ProjectRunComparisonEntry("read-default", record, record, (delta,))
    with pytest.raises(ProductProjectFormatError, match="contain entries"):
        ValidationRunComparison("project", "left", "right", "a" * 64, "b" * 64, ())
    with pytest.raises(ProductProjectFormatError, match="ProjectRunComparisonEntry"):
        ValidationRunComparison(
            "project", "left", "right", "a" * 64, "b" * 64, cast(Any, (object(),))
        )
    with pytest.raises(ProductProjectFormatError, match="unique"):
        ValidationRunComparison(
            "project", "left", "right", "a" * 64, "b" * 64, (entry, entry)
        )


def test_project_errors_have_safe_user_issue_mappings() -> None:
    assert issue_from_exception(ProductProjectExistsError("exists")).code is UserIssueCode.OUTPUT_EXISTS
    assert issue_from_exception(ProductProjectPathError("path")).code is UserIssueCode.OUTPUT_PATH
    assert issue_from_exception(ProductProjectFormatError("format")).code is UserIssueCode.INPUT_DATA
    assert issue_from_exception(ProductProjectLimitError("limit")).code is UserIssueCode.INPUT_DATA


def test_primitive_contract_guards_reject_ambiguous_values(tmp_path: Path) -> None:
    with pytest.raises(ProductProjectFormatError, match="lowercase"):
        projects._identifier("id", "Upper")

    for value in (None, "", " padded"):
        with pytest.raises(ProductProjectFormatError, match="non-empty stripped"):
            projects._text("text", value)
    with pytest.raises(ProductProjectLimitError, match="characters"):
        projects._text("text", "ab", maximum=1)
    with pytest.raises(ProductProjectFormatError, match="printable"):
        projects._text("text", "a\x07")

    with pytest.raises(ProductProjectFormatError, match="must be text"):
        projects._optional_text("description", None)
    with pytest.raises(ProductProjectFormatError, match="stripped"):
        projects._optional_text("description", " padded")
    with pytest.raises(ProductProjectLimitError, match="characters"):
        projects._optional_text("description", "ab", maximum=1)
    with pytest.raises(ProductProjectFormatError, match="printable"):
        projects._optional_text("description", "a\x07")

    with pytest.raises(ProductProjectFormatError, match="between"):
        projects._bounded_count("count", True, 2)
    with pytest.raises(ProductProjectFormatError, match="timezone-aware"):
        projects._timestamp("stamp", STAMP.replace(tzinfo=None))
    with pytest.raises(ProductProjectFormatError, match="must be text"):
        projects._enum("source", ProductSourceMode, 1)
    with pytest.raises(ProductProjectFormatError, match="unsupported"):
        projects._enum("source", ProductSourceMode, "UNKNOWN")
    with pytest.raises(ProductProjectFormatError, match="object"):
        projects._object("value", [], ())
    with pytest.raises(ProductProjectFormatError, match="array"):
        projects._array("value", {}, 1)
    with pytest.raises(ProductProjectLimitError, match="entries"):
        projects._array("value", [1, 2], 1)
    with pytest.raises(ProductProjectFormatError, match="only strings"):
        projects._string_array("values", [1], 1)
    with pytest.raises(ProductProjectFormatError, match="duplicates"):
        projects._string_array("values", ["same", "same"], 2)

    with pytest.raises(ProductProjectFormatError, match="content must be text"):
        projects._parse_json(cast(Any, b"{}"), maximum_bytes=10, label="JSON")
    with pytest.raises(ProductProjectFormatError, match="valid UTF-8"):
        projects._parse_json("\ud800", maximum_bytes=10, label="JSON")
    with pytest.raises(ProductProjectLimitError, match="byte limit"):
        projects._parse_json("{}", maximum_bytes=1, label="JSON")

    with pytest.raises(ProductProjectPathError, match="path-like"):
        projects._path(cast(Any, 1), label="path")

    class BadPath(os.PathLike[str]):
        def __fspath__(self) -> str:
            raise ValueError("bad")

    with pytest.raises(ProductProjectPathError, match="invalid"):
        projects._path(BadPath(), label="path")
    with pytest.raises(ProductProjectPathError, match="identify"):
        projects._path(Path("."), label="path")
    with pytest.raises(ProductProjectFormatError, match="non-empty relative"):
        projects._safe_relative_path(tmp_path, "", label="replay")
    with pytest.raises(ProductProjectFormatError, match="relative"):
        projects._safe_relative_path(
            tmp_path, str((tmp_path / "absolute.csv").resolve()), label="replay"
        )


def test_file_helpers_translate_io_failures_and_races(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("ok", encoding="utf-8")
    real_read_bytes = Path.read_bytes

    def failed_read(path: Path) -> bytes:
        if path == source:
            raise OSError("read failed")
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", failed_read)
    with pytest.raises(ProductProjectPathError, match="could not be read"):
        projects._read_bounded(source, maximum_bytes=10, label="source")
    monkeypatch.setattr(Path, "read_bytes", real_read_bytes)

    def grown_read(path: Path) -> bytes:
        if path == source:
            return b"123456"
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", grown_read)
    with pytest.raises(ProductProjectLimitError, match="byte limit"):
        projects._read_bounded(source, maximum_bytes=5, label="source")
    monkeypatch.setattr(Path, "read_bytes", real_read_bytes)

    destination = tmp_path / "destination.txt"
    real_exists = Path.exists

    def failed_exists(path: Path, **kwargs: Any) -> bool:
        if path == destination:
            raise OSError("exists failed")
        return real_exists(path, **kwargs)

    monkeypatch.setattr(Path, "exists", failed_exists)
    with pytest.raises(ProductProjectPathError, match="cannot be prepared"):
        projects._write_new_text(destination, "text", label="destination")
    monkeypatch.setattr(Path, "exists", real_exists)

    def link_exists(source_path: object, destination_path: object) -> None:
        raise FileExistsError("race")

    monkeypatch.setattr(projects.os, "link", link_exists)
    with pytest.raises(ProductProjectExistsError, match="already exists"):
        projects._write_new_text(destination, "text", label="destination")

    real_unlink = Path.unlink

    def failed_link(source_path: object, destination_path: object) -> None:
        raise OSError("link failed")

    def cleanup_fails(path: Path, *args: Any, **kwargs: Any) -> None:
        if kwargs.get("missing_ok"):
            raise OSError("cleanup failed")
        real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(projects.os, "link", failed_link)
    monkeypatch.setattr(Path, "unlink", cleanup_fails)
    with pytest.raises(ProductProjectPathError, match="could not be written"):
        projects._write_new_text(destination, "text", label="destination")


def test_schema_versions_and_collection_limits_are_enforced() -> None:
    configuration = ProductWorkflowConfiguration(
        ProductSourceMode.SIMULATOR, ProductJobType.READ
    )
    with pytest.raises(ProductProjectFormatError, match="configuration"):
        ValidationPreset("preset", "Preset", cast(Any, object()))
    with pytest.raises(ProductProjectFormatError, match="preset schema"):
        ValidationPreset("preset", "Preset", configuration, "preset.v999")

    preset = ValidationPreset("preset", "Preset", configuration)
    with pytest.raises(ProductProjectFormatError, match="project schema"):
        ValidationProject("project", "Project", "", (preset,), "project.v999")

    with pytest.raises(ProductProjectFormatError, match="cannot claim Serial"):
        replace(make_record(), source_mode=ProductSourceMode.SERIAL_READ_ONLY)
    with pytest.raises(ProductProjectLimitError, match="metrics exceeds"):
        replace(
            make_record(),
            metrics=tuple(
                ProjectRunMetric(f"metric-{index}", index, "count")
                for index in range(projects.MAX_VALIDATION_METRICS + 1)
            ),
        )
    metric = ProjectRunMetric("same", 1, "count")
    with pytest.raises(ProductProjectFormatError, match="unique"):
        replace(make_record(), metrics=(metric, metric))
    with pytest.raises(ProductProjectFormatError, match="limitations must be a tuple"):
        replace(make_record(), limitations=cast(Any, []))
    with pytest.raises(ProductProjectFormatError, match="run record schema"):
        replace(make_record(), schema_version="record.v999")

    records = tuple(
        make_record(
            f"preset-{index}",
            job_id=f"job-{index}",
            metrics=(),
        )
        for index in range(projects.MAX_VALIDATION_RUN_RECORDS + 1)
    )
    with pytest.raises(ProductProjectLimitError, match="records"):
        make_manifest(records=records)
    with pytest.raises(ProductProjectFormatError, match="manifest schema"):
        replace(make_manifest(), schema_version="manifest.v999")

    entry = ProjectRunComparisonEntry("read-default", make_record(), None, ())
    with pytest.raises(ProductProjectFormatError, match="comparison schema"):
        ValidationRunComparison(
            "project",
            "left",
            "right",
            "a" * 64,
            "b" * 64,
            (entry,),
            "compare.v999",
        )


def test_serial_settings_are_rejected_during_both_project_serialization_paths(
    tmp_path: Path,
) -> None:
    project = build_default_validation_project("project", "Project")
    serial = SerialSourceConfig("COM_TEST")
    object.__setattr__(project.presets[0].configuration, "serial_config", serial)
    with pytest.raises(ProductProjectFormatError, match="persist serial"):
        validation_project_to_dict(project, project_directory=tmp_path)

    clean = build_default_validation_project("project", "Project")
    document = validation_project_to_dict(clean, project_directory=tmp_path)
    cast(dict[str, Any], cast(list[Any], document["presets"])[0])["configuration"][
        "serial_config"
    ] = {}
    with pytest.raises(ProductProjectFormatError, match="serial connection"):
        validation_project_from_dict(document, project_directory=tmp_path)


def test_project_and_manifest_document_edge_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = build_default_validation_project("project", "Project")
    monkeypatch.setattr(
        projects,
        "dump_validation_project",
        lambda value, *, path: "x" * (projects.MAX_VALIDATION_PROJECT_BYTES + 1),
    )
    with pytest.raises(ProductProjectLimitError, match="byte limit"):
        write_validation_project(tmp_path / "too-large.json", project)

    with pytest.raises(ProductProjectFormatError, match="must be an object"):
        validation_run_manifest_from_dict([])

    document = validation_run_manifest_to_dict(make_manifest())
    document["schema_version"] = "manifest.v999"
    with pytest.raises(ProductProjectFormatError, match="manifest schema"):
        validation_run_manifest_from_dict(document)

    document = validation_run_manifest_to_dict(make_manifest())
    cast(list[dict[str, Any]], document["records"])[0]["result_artifact"] = 1
    with pytest.raises(ProductProjectFormatError, match="text or null"):
        validation_run_manifest_from_dict(document)

    document = validation_run_manifest_to_dict(make_manifest())
    document["started_at"] = 1
    with pytest.raises(ProductProjectFormatError, match="ISO-8601 string"):
        validation_run_manifest_from_dict(document)

    document = validation_run_manifest_to_dict(make_manifest())
    document["started_at"] = "not-a-date"
    with pytest.raises(ProductProjectFormatError, match="valid ISO-8601"):
        validation_run_manifest_from_dict(document)


def test_artifact_verification_translates_io_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output, manifest = publish_default(tmp_path)
    manifest_path = output / projects.VALIDATION_RUN_MANIFEST_FILENAME
    record = next(record for record in manifest.records if record.result_artifact)
    artifact = output / cast(str, record.result_artifact)
    real_read_bytes = Path.read_bytes

    def failed_read(path: Path) -> bytes:
        if path == artifact:
            raise OSError("artifact read failed")
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", failed_read)
    with pytest.raises(ProductProjectPathError, match="could not be verified"):
        load_validation_run_manifest(manifest_path)


def test_publish_records_operational_failure_without_inventing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = ValidationProject(
        "project",
        "Project",
        "",
        (
            ValidationPreset(
                "read",
                "Read",
                ProductWorkflowConfiguration(
                    ProductSourceMode.SIMULATOR, ProductJobType.READ
                ),
            ),
        ),
    )
    prepared = prepare_product_job(project.presets[0].configuration, "placeholder")

    def failed_execution(*args: Any, **kwargs: Any) -> ProductJobExecution:
        request = args[0]
        return ProductJobExecution(
            request,
            ProductWorkerState.FAILED,
            None,
            None,
            (),
            None,
            0,
        )

    monkeypatch.setattr(projects, "execute_product_job", failed_execution)
    output = tmp_path / "run"
    manifest = publish_validation_project_run(project, output, "run", clock=projects._now)

    assert prepared.request.job_type is ProductJobType.READ
    assert manifest.records[0].worker_state is ProductWorkerState.FAILED
    assert manifest.records[0].metrics == ()
    assert manifest.records[0].product_status is None
    assert manifest.operational_failures == 1
    assert load_validation_run_manifest(output / "run-manifest.json") == manifest


def test_publish_failure_paths_are_atomic_and_remove_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = ValidationProject(
        "project",
        "Project",
        "",
        (
            ValidationPreset(
                "read",
                "Read",
                ProductWorkflowConfiguration(
                    ProductSourceMode.SIMULATOR, ProductJobType.READ
                ),
            ),
        ),
    )

    monkeypatch.setattr(projects, "MAX_VALIDATION_RUN_MANIFEST_BYTES", 1)
    with pytest.raises(ProductProjectLimitError, match="byte limit"):
        publish_validation_project_run(project, tmp_path / "large", "large")
    assert not (tmp_path / "large").exists()
    assert not tuple(tmp_path.glob(".large.*.staging"))

    monkeypatch.setattr(
        projects,
        "MAX_VALIDATION_RUN_MANIFEST_BYTES",
        1_048_576,
    )

    def rename_exists(source: object, target: object) -> None:
        raise FileExistsError("race")

    monkeypatch.setattr(projects.os, "rename", rename_exists)
    with pytest.raises(ProductProjectExistsError, match="already exists"):
        publish_validation_project_run(project, tmp_path / "race", "race")
    assert not tuple(tmp_path.glob(".race.*.staging"))

    def rename_fails(source: object, target: object) -> None:
        raise OSError("publish failed")

    monkeypatch.setattr(projects.os, "rename", rename_fails)
    with pytest.raises(ProductProjectPathError, match="could not be published"):
        publish_validation_project_run(project, tmp_path / "failure", "failure")
    assert not tuple(tmp_path.glob(".failure.*.staging"))


def test_publish_preflight_translates_target_io_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = build_default_validation_project("project", "Project")
    target = tmp_path / "run"
    real_exists = Path.exists

    def failed_exists(path: Path, **kwargs: Any) -> bool:
        if path == target:
            raise OSError("target check failed")
        return real_exists(path, **kwargs)

    monkeypatch.setattr(Path, "exists", failed_exists)
    with pytest.raises(ProductProjectPathError, match="cannot be prepared"):
        publish_validation_project_run(project, target, "run")


def test_missing_comparison_side_serializes_as_null() -> None:
    left = make_record("left", job_id="left-job")
    right = make_record("right", job_id="right-job")
    comparison = compare_validation_runs(
        make_manifest("one", records=(left,)),
        make_manifest("two", records=(right,)),
    )
    document = validation_run_comparison_to_dict(comparison)
    entries = cast(list[dict[str, Any]], document["entries"])

    assert entries[0]["right"] is None
    assert entries[1]["left"] is None


def test_configuration_and_comparison_hashes_are_strict() -> None:
    with pytest.raises(ProductProjectFormatError, match="configuration_sha256"):
        replace(make_record(), configuration_sha256="bad")

    entry = ProjectRunComparisonEntry("read-default", make_record(), None, ())
    with pytest.raises(ProductProjectFormatError, match="left_project_sha256"):
        ValidationRunComparison(
            "project", "left", "right", "bad", "b" * 64, (entry,)
        )


def test_project_directory_is_explicitly_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = build_default_validation_project("project", "Project")
    with pytest.raises(ProductProjectPathError, match="path-like"):
        publish_validation_project_run(
            project,
            tmp_path / "bad-type",
            "bad-type",
            project_directory=cast(Any, 1),
        )
    with pytest.raises(ProductProjectPathError, match="must exist"):
        publish_validation_project_run(
            project,
            tmp_path / "missing-dir-run",
            "missing-dir-run",
            project_directory=tmp_path / "missing-project-directory",
        )

    class BadDirectory(os.PathLike[str]):
        def __fspath__(self) -> str:
            raise ValueError("bad directory")

    with pytest.raises(ProductProjectPathError, match="invalid"):
        publish_validation_project_run(
            project,
            tmp_path / "bad-directory-run",
            "bad-directory-run",
            project_directory=BadDirectory(),
        )

    monkeypatch.setattr(projects, "MAX_VALIDATION_PROJECT_BYTES", 1)
    with pytest.raises(ProductProjectLimitError, match="project snapshot"):
        publish_validation_project_run(
            project,
            tmp_path / "large-snapshot",
            "large-snapshot",
            project_directory=tmp_path,
        )
