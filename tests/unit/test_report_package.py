"""Canonical-result report packages retain frozen results and atomic publication."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from analog_validation.exports import (
    dump_result_export_json,
    load_result_export_json,
)
from analog_validation_app import (
    ProductJobType,
    ProductReportExistsError,
    ProductReportFormatError,
    ProductReportPathError,
    ProductSourceMode,
    ProductWorkerState,
    ProductWorkflowConfiguration,
    build_human_report_view,
    execute_product_job,
    prepare_product_job,
    publish_human_report,
    reporting,
)

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "test-data" / "golden"
DC_RESULT = GOLDEN_DIR / "phase3_dc_sweep_result_v1.json"


@pytest.mark.parametrize(
    "job_type",
    [
        ProductJobType.DC_ANALYSIS,
        ProductJobType.HYSTERESIS_ANALYSIS,
        ProductJobType.CALIBRATION_ANALYSIS,
        ProductJobType.FREQUENCY_RESPONSE_ANALYSIS,
    ],
)
def test_simulator_analysis_packages_preserve_complete_result(
    tmp_path: Path, job_type: ProductJobType
) -> None:
    prepared = prepare_product_job(
        ProductWorkflowConfiguration(ProductSourceMode.SIMULATOR, job_type),
        f"package-{job_type.value.lower()}",
    )
    execution = execute_product_job(
        prepared.request, prepared.service_factory, prepared.output_slot
    )
    assert execution.worker_state is ProductWorkerState.SUCCEEDED
    assert execution.output is not None
    bundle = execution.output.result_export
    assert bundle is not None
    view = build_human_report_view(bundle)

    publication = publish_human_report(tmp_path / "package", view, result_bundle=bundle)

    reopened = load_result_export_json(publication.output_directory / "result.json")
    assert reopened == bundle
    assert build_human_report_view(reopened) == view
    assert view.evidence_source.value == "SYNTHETIC"


@pytest.mark.parametrize(
    "filename",
    ["phase3_dc_sweep_result_v1.json", "phase3_hysteresis_result_v1.json"],
)
def test_package_roundtrips_canonical_result_without_changing_rendered_reports(
    tmp_path: Path, filename: str
) -> None:
    bundle = load_result_export_json(GOLDEN_DIR / filename)
    view = build_human_report_view(bundle)
    original = publish_human_report(tmp_path / "original", view)
    publication = publish_human_report(tmp_path / "package", view, result_bundle=bundle)

    assert tuple(artifact.name for artifact in publication.artifacts) == (
        "report.txt",
        "report.md",
        "report.html",
        "chart.svg",
        "result.json",
        "manifest.json",
    )
    for artifact in original.artifacts[:-1]:
        assert publication.artifact(artifact.name) == artifact
        assert (publication.output_directory / artifact.name).read_bytes() == (
            original.output_directory / artifact.name
        ).read_bytes()
    result_path = publication.output_directory / "result.json"
    assert result_path.read_bytes() == dump_result_export_json(bundle).encode("utf-8")
    assert load_result_export_json(result_path) == bundle
    manifest = json.loads(
        (publication.output_directory / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["schema_version"] == "human-report-manifest.v1"
    assert (
        manifest["evidence_source"]
        == bundle.test_run_result.metadata.evidence_source.value
    )
    assert manifest["hardware_claim"] == "NO_NEW_HARDWARE_VALIDATION"
    result_artifact = publication.artifact("result.json")
    assert result_artifact.media_type == "application/json; charset=utf-8"
    assert result_artifact.sha256 == view.canonical_result_sha256
    assert manifest["canonical_result_sha256"] == result_artifact.sha256
    assert manifest["artifacts"] == [
        {
            "name": artifact.name,
            "media_type": artifact.media_type,
            "size_bytes": artifact.size_bytes,
            "sha256": artifact.sha256,
        }
        for artifact in publication.artifacts[:-1]
    ]
    for artifact in publication.artifacts:
        payload = (publication.output_directory / artifact.name).read_bytes()
        assert len(payload) == artifact.size_bytes
        assert hashlib.sha256(payload).hexdigest() == artifact.sha256


def test_explicitly_omitting_result_preserves_original_package(tmp_path: Path) -> None:
    view = build_human_report_view(load_result_export_json(DC_RESULT))
    original = publish_human_report(tmp_path / "original", view)
    explicit_none = publish_human_report(
        tmp_path / "explicit-none", view, result_bundle=None
    )

    assert explicit_none.artifacts == original.artifacts
    assert not (explicit_none.output_directory / "result.json").exists()
    for artifact in original.artifacts:
        assert (original.output_directory / artifact.name).read_bytes() == (
            explicit_none.output_directory / artifact.name
        ).read_bytes()


@pytest.mark.parametrize("invalid", [object(), {}, "result.json"])
def test_package_rejects_wrong_bundle_type_without_writes(
    tmp_path: Path, invalid: Any
) -> None:
    view = build_human_report_view(load_result_export_json(DC_RESULT))

    with pytest.raises(ProductReportFormatError, match="ResultExportBundle"):
        publish_human_report(tmp_path / "invalid", view, result_bundle=invalid)

    assert not tuple(tmp_path.iterdir())


@pytest.mark.parametrize(
    "changes",
    [
        {"title": "A different display title"},
        {"canonical_result_sha256": "0" * 64},
        {"metrics": ()},
    ],
)
def test_package_rejects_mismatched_view_before_creating_staging(
    tmp_path: Path, changes: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_result_export_json(DC_RESULT)
    changed_view = replace(build_human_report_view(bundle), **changes)

    def unexpected_staging(**_: Any) -> str:
        raise AssertionError("invalid result must be rejected before staging")

    monkeypatch.setattr(reporting.tempfile, "mkdtemp", unexpected_staging)
    with pytest.raises(ProductReportFormatError, match="does not match"):
        publish_human_report(tmp_path / "mismatch", changed_view, result_bundle=bundle)

    assert not tuple(tmp_path.iterdir())


@pytest.mark.parametrize("failing_name", ["result.json", "manifest.json"])
def test_package_write_failure_never_publishes_partial_report(
    tmp_path: Path, failing_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_result_export_json(DC_RESULT)
    view = build_human_report_view(bundle)
    original_write = reporting._write_staging_file
    observed: list[str] = []

    def fail_write(path: Path, payload: bytes) -> None:
        observed.append(path.name)
        if path.name == failing_name:
            raise OSError("package disk failure")
        original_write(path, payload)

    monkeypatch.setattr(reporting, "_write_staging_file", fail_write)
    with pytest.raises(ProductReportPathError, match="could not be published"):
        publish_human_report(tmp_path / "package", view, result_bundle=bundle)

    assert failing_name in observed
    assert not tuple(tmp_path.iterdir())


def test_package_publish_failure_cleans_all_staged_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_result_export_json(DC_RESULT)
    view = build_human_report_view(bundle)

    def fail_rename(staging: Path, destination: Path) -> None:
        assert not destination.exists()
        assert {path.name for path in staging.iterdir()} == {
            "report.txt",
            "report.md",
            "report.html",
            "chart.svg",
            "result.json",
            "manifest.json",
        }
        raise OSError("package publication failure")

    monkeypatch.setattr(reporting.os, "rename", fail_rename)
    with pytest.raises(ProductReportPathError, match="could not be published"):
        publish_human_report(tmp_path / "package", view, result_bundle=bundle)

    assert not tuple(tmp_path.iterdir())


def test_package_existing_destination_preserves_every_byte(tmp_path: Path) -> None:
    bundle = load_result_export_json(DC_RESULT)
    view = build_human_report_view(bundle)
    destination = tmp_path / "package"
    publish_human_report(destination, view, result_bundle=bundle)
    original = {path.name: path.read_bytes() for path in destination.iterdir()}

    with pytest.raises(ProductReportExistsError):
        publish_human_report(destination, view, result_bundle=bundle)

    assert original == {path.name: path.read_bytes() for path in destination.iterdir()}
    assert tuple(tmp_path.iterdir()) == (destination,)
