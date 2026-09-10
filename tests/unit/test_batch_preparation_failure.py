"""Failed later preparation preserves earlier evidence without inventing a run."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from analog_validation import EvidenceSource
from analog_validation_app import (
    VALIDATION_RUN_MANIFEST_SCHEMA_VERSION,
    VALIDATION_RUN_MANIFEST_V1_SCHEMA_VERSION,
    VALIDATION_RUN_MANIFEST_V2_SCHEMA_VERSION,
    VALIDATION_RUN_MANIFEST_V3_SCHEMA_VERSION,
    ProductJobType,
    ProductProjectFormatError,
    ProductProjectLimitError,
    ProductProjectPathError,
    ProductRequestError,
    ProductSourceMode,
    ProductWorkerState,
    ProductWorkflowConfiguration,
    UserIssueCode,
    ValidationBatchCancellationToken,
    ValidationBatchPhase,
    ValidationBatchPreparationFailure,
    ValidationBatchStatus,
    ValidationPreset,
    ValidationProject,
    load_validation_run_manifest,
    projects,
    publish_validation_project_run,
    validation_run_manifest_from_dict,
    validation_run_manifest_to_dict,
)


def _project(tmp_path: Path) -> ValidationProject:
    return ValidationProject(
        "recovery",
        "Recovery",
        "",
        (
            ValidationPreset(
                "complete",
                "Complete DC",
                ProductWorkflowConfiguration(
                    ProductSourceMode.SIMULATOR, ProductJobType.DC_ANALYSIS
                ),
            ),
            ValidationPreset(
                "unavailable",
                "Unavailable Replay",
                ProductWorkflowConfiguration(
                    ProductSourceMode.CSV_REPLAY,
                    ProductJobType.READ,
                    replay_path=tmp_path / "source.csv",
                ),
            ),
            ValidationPreset(
                "later",
                "Later Read",
                ProductWorkflowConfiguration(
                    ProductSourceMode.SIMULATOR, ProductJobType.READ
                ),
            ),
        ),
    )


def _publish(tmp_path: Path, **kwargs: Any) -> projects.ValidationRunManifest:
    return publish_validation_project_run(
        _project(tmp_path),
        tmp_path / "run",
        "run",
        project_directory=tmp_path,
        **kwargs,
    )


def test_later_missing_input_preserves_complete_artifact_and_does_not_start_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_execute = projects.execute_product_job
    executed: list[str] = []

    def execute(request: Any, *args: Any, **kwargs: Any) -> Any:
        executed.append(request.job_id)
        return real_execute(request, *args, **kwargs)

    monkeypatch.setattr(projects, "execute_product_job", execute)
    events: list[projects.ValidationBatchProgress] = []
    manifest = _publish(tmp_path, report_progress=events.append)
    assert manifest.schema_version == "validation-run-manifest.v4"
    assert manifest.batch_status is ValidationBatchStatus.ERROR
    assert manifest.not_started_preset_ids == ("unavailable", "later")
    assert executed == ["run-01-complete"]
    assert len(manifest.records) == 1
    record = manifest.records[0]
    assert record.worker_state is ProductWorkerState.SUCCEEDED
    assert record.evidence_source is EvidenceSource.SYNTHETIC
    assert record.result_artifact is not None
    payload = (tmp_path / "run" / record.result_artifact).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == record.result_sha256
    assert manifest.input_artifacts == ()
    assert manifest.preparation_failure is not None
    assert manifest.preparation_failure.preset_id == "unavailable"
    assert manifest.preparation_failure.issue_code is UserIssueCode.INPUT_DATA
    assert manifest.preparation_failure.technical_type == "ProductProjectPathError"
    assert manifest.operational_failures == 1
    assert manifest.engineering_failures == 0
    assert events[-1].phase is ValidationBatchPhase.FINISHED
    assert events[-1].completed_presets == 1
    assert not any(
        event.phase is ValidationBatchPhase.RUNNING
        and event.current_preset_id == "unavailable"
        for event in events
    )
    assert (
        load_validation_run_manifest(tmp_path / "run" / "run-manifest.json") == manifest
    )


def test_invalid_replay_is_an_executed_worker_failure_with_archived_input(
    tmp_path: Path,
) -> None:
    (tmp_path / "source.csv").write_text("invalid replay", encoding="utf-8")
    manifest = _publish(tmp_path)
    assert manifest.batch_status is ValidationBatchStatus.ERROR
    assert manifest.preparation_failure is None
    assert len(manifest.records) == 2
    failed = manifest.records[-1]
    assert failed.preset_id == "unavailable"
    assert failed.worker_state is ProductWorkerState.FAILED
    assert failed.measurement_count == 0
    assert failed.evidence_source is None
    assert manifest.not_started_preset_ids == ("later",)
    assert manifest.input_artifacts[0].preset_id == "unavailable"
    assert (
        load_validation_run_manifest(tmp_path / "run" / "run-manifest.json") == manifest
    )


def test_preparation_failure_after_copy_keeps_real_archived_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"source bytes retained although preparation rejected"
    (tmp_path / "source.csv").write_bytes(payload)
    real_prepare = projects.prepare_product_job

    def prepare(configuration: Any, *args: Any, **kwargs: Any) -> Any:
        if configuration.source_mode is ProductSourceMode.CSV_REPLAY:
            raise ProductRequestError(
                "Preset preparation rejected before a worker started."
            )
        return real_prepare(configuration, *args, **kwargs)

    monkeypatch.setattr(projects, "prepare_product_job", prepare)
    manifest = _publish(tmp_path)
    assert manifest.preparation_failure is not None
    assert manifest.preparation_failure.issue_code is UserIssueCode.INVALID_REQUEST
    assert len(manifest.records) == 1
    assert manifest.not_started_preset_ids == ("unavailable", "later")
    artifact = manifest.input_artifacts[0]
    assert artifact.preset_id == "unavailable"
    assert (tmp_path / "run" / artifact.artifact).read_bytes() == payload
    assert (
        load_validation_run_manifest(tmp_path / "run" / "run-manifest.json") == manifest
    )


def test_cancellation_before_preparation_does_not_open_missing_replay(
    tmp_path: Path,
) -> None:
    cancellation = ValidationBatchCancellationToken()

    def cancel(event: projects.ValidationBatchProgress) -> None:
        if (
            event.phase is ValidationBatchPhase.PREPARING
            and event.current_preset_id == "unavailable"
        ):
            cancellation.request_cancel()

    manifest = _publish(tmp_path, cancellation=cancellation, report_progress=cancel)
    assert manifest.batch_status is ValidationBatchStatus.CANCELLED
    assert manifest.preparation_failure is None
    assert manifest.not_started_preset_ids == ("unavailable", "later")


def test_observed_preparation_error_is_not_hidden_by_concurrent_cancellation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancellation = ValidationBatchCancellationToken()

    def archive(*args: Any, **kwargs: Any) -> Any:
        cancellation.request_cancel()
        raise ProductProjectPathError(
            "Replay input became unavailable during preparation."
        )

    monkeypatch.setattr(projects, "_archive_replay_input", archive)
    manifest = _publish(tmp_path, cancellation=cancellation)
    assert manifest.batch_status is ValidationBatchStatus.ERROR
    assert manifest.preparation_failure is not None


def test_final_publication_error_still_rejects_and_does_not_claim_saved_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_publish(*args: Any) -> None:
        raise OSError("Publication unavailable")

    monkeypatch.setattr(projects.os, "rename", fail_publish)
    with pytest.raises(ProductProjectPathError, match="could not be published"):
        _publish(tmp_path)
    assert not (tmp_path / "run").exists()
    assert not tuple(tmp_path.glob(".run.*.staging"))


@pytest.mark.parametrize(
    "schema",
    (
        VALIDATION_RUN_MANIFEST_V1_SCHEMA_VERSION,
        VALIDATION_RUN_MANIFEST_V2_SCHEMA_VERSION,
        VALIDATION_RUN_MANIFEST_V3_SCHEMA_VERSION,
        VALIDATION_RUN_MANIFEST_SCHEMA_VERSION,
    ),
)
def test_all_manifest_versions_keep_exact_shapes_and_round_trip(
    tmp_path: Path, schema: str
) -> None:
    manifest = _publish(tmp_path, selected_preset_ids=("complete",))
    historical = replace(
        manifest,
        schema_version=schema,
        batch_status=None
        if schema == VALIDATION_RUN_MANIFEST_V1_SCHEMA_VERSION
        else manifest.batch_status,
    )
    document = validation_run_manifest_to_dict(historical)
    assert ("preparation_failure" in document) is (
        schema == VALIDATION_RUN_MANIFEST_SCHEMA_VERSION
    )
    assert ("input_artifacts" in document) is (
        schema
        in {
            VALIDATION_RUN_MANIFEST_V3_SCHEMA_VERSION,
            VALIDATION_RUN_MANIFEST_SCHEMA_VERSION,
        }
    )
    assert (
        validation_run_manifest_to_dict(validation_run_manifest_from_dict(document))
        == document
    )
    if schema != VALIDATION_RUN_MANIFEST_SCHEMA_VERSION:
        document["preparation_failure"] = None
        with pytest.raises(ProductProjectFormatError, match="fields do not match"):
            validation_run_manifest_from_dict(document)


@pytest.mark.parametrize(
    "changes,message",
    (
        (
            {"preparation_failure": object()},
            "must be ValidationBatchPreparationFailure",
        ),
        ({"schema_version": VALIDATION_RUN_MANIFEST_V3_SCHEMA_VERSION}, "only v4"),
        ({"records": ()}, "earlier records"),
        ({"not_started_preset_ids": ()}, "not-started work"),
        (
            {
                "preparation_failure": ValidationBatchPreparationFailure(
                    "later", UserIssueCode.INPUT_DATA, "ReplayError", "Invalid input."
                )
            },
            "first not-started",
        ),
        ({"batch_status": ValidationBatchStatus.CANCELLED}, "requires ERROR"),
    ),
)
def test_preparation_failure_cannot_claim_a_worker_or_change_historical_shapes(
    tmp_path: Path,
    changes: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ProductProjectFormatError, match=message):
        replace(_publish(tmp_path), **changes)


@pytest.mark.parametrize(
    "changes",
    (
        {"preset_id": " invalid"},
        {"issue_code": "INPUT_DATA"},
        {"technical_type": ""},
        {"message": "x" * 1025},
    ),
)
def test_preparation_failure_validates_bounded_typed_fields(
    changes: dict[str, Any],
) -> None:
    fields: dict[str, Any] = {
        "preset_id": "replay",
        "issue_code": UserIssueCode.INPUT_DATA,
        "technical_type": "ReplayError",
        "message": "Invalid input.",
    }
    fields.update(changes)
    with pytest.raises((ProductProjectFormatError, ProductProjectLimitError)):
        ValidationBatchPreparationFailure(**fields)


def test_failure_archive_source_must_match_project_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_prepare(configuration: Any, *args: Any, **kwargs: Any) -> Any:
        if configuration.source_mode is ProductSourceMode.CSV_REPLAY:
            raise ProductRequestError("Configuration rejected.")
        return real_prepare(configuration, *args, **kwargs)

    (tmp_path / "source.csv").write_text("retained bytes", encoding="utf-8")
    real_prepare = projects.prepare_product_job
    monkeypatch.setattr(projects, "prepare_product_job", fail_prepare)
    _publish(tmp_path)
    snapshot_path = tmp_path / "run" / "project.snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["presets"][1]["configuration"]["source_mode"] = "SIMULATOR"
    snapshot["presets"][1]["configuration"]["replay_path"] = None
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    manifest_path = tmp_path / "run" / "run-manifest.json"
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    document["project_sha256"] = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(
        ProductProjectFormatError, match="must belong to a CSV Replay preset"
    ):
        load_validation_run_manifest(manifest_path)
