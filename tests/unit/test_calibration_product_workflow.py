from __future__ import annotations

import io
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic, sleep

import pytest

from analog_validation import EvidenceSource, MeasurementUnit
from analog_validation import TestRunOutcome as RunOutcome
from analog_validation.exports import load_calibration_coefficients_json
from analog_validation_app import (
    CalibrationJobService,
    DashboardApplication,
    DashboardWizardStep,
    ProductJobType,
    ProductRequestError,
    ProductSourceMode,
    ProductWorkerState,
    ProductWorkflowConfiguration,
    ReportChartKind,
    build_human_report_view,
    execute_product_job,
    prepare_product_job,
    render_human_report_svg,
)
from analog_validation_app.cli import CliDependencies, main


def _wait_for_result(application: DashboardApplication) -> None:
    deadline = monotonic() + 5.0
    while monotonic() < deadline:
        application.poll()
        if application.wizard_state.step is DashboardWizardStep.RESULT:
            return
        sleep(0.001)
    raise AssertionError("calibration Dashboard job did not reach Result")


def test_calibration_service_report_chain_preserves_synthetic_evidence() -> None:
    prepared = prepare_product_job(
        ProductWorkflowConfiguration(
            ProductSourceMode.SIMULATOR,
            ProductJobType.CALIBRATION_ANALYSIS,
            sample_count=8,
        ),
        "calibration-service-chain",
    )

    service = prepared.service_factory(prepared.request)
    assert isinstance(service, CalibrationJobService)
    execution = execute_product_job(
        prepared.request,
        prepared.service_factory,
        prepared.output_slot,
    )

    assert execution.worker_state is ProductWorkerState.SUCCEEDED
    assert execution.result is not None
    assert execution.result.test_run_outcome is RunOutcome.PASS
    assert execution.output is not None
    coefficients = execution.output.calibration_coefficients
    assert coefficients is not None
    assert coefficients.scale == 2.0
    assert coefficients.offset == 12.0
    assert coefficients.observed_source is EvidenceSource.SYNTHETIC
    assert coefficients.reference_source is EvidenceSource.SYNTHETIC
    assert execution.output.result_export is not None

    view = build_human_report_view(execution.output.result_export)
    assert view.chart_kind is ReportChartKind.CALIBRATION
    assert view.title == "Calibration Validation Report"
    assert view.evidence_source is EvidenceSource.SYNTHETIC
    svg = render_human_report_svg(view)
    assert 'data-series="before"' in svg
    assert 'data-series="after"' in svg
    assert "performed no new hardware validation" in svg
    assert "No finite plottable calibration errors" in render_human_report_svg(
        replace(view, points=())
    )


def test_calibration_product_configuration_rejects_unsafe_values_and_uses_clock() -> (
    None
):
    with pytest.raises(ProductRequestError, match="must differ"):
        ProductWorkflowConfiguration(
            ProductSourceMode.SIMULATOR,
            ProductJobType.CALIBRATION_ANALYSIS,
            primary_channel="same.channel",
            secondary_channel="same.channel",
        )
    with pytest.raises(ProductRequestError, match="cannot be negative"):
        ProductWorkflowConfiguration(
            ProductSourceMode.SIMULATOR,
            ProductJobType.CALIBRATION_ANALYSIS,
            max_calibration_rmse=-1.0,
        )

    fixed = datetime(2026, 9, 5, 15, 0, tzinfo=timezone.utc)
    prepared = prepare_product_job(
        ProductWorkflowConfiguration(
            ProductSourceMode.SIMULATOR,
            ProductJobType.CALIBRATION_ANALYSIS,
            sample_count=4,
            unit=MeasurementUnit.MILLIVOLT,
        ),
        "clocked-calibration",
        service_clock=lambda: fixed,
    )
    execution = execute_product_job(
        prepared.request,
        prepared.service_factory,
        prepared.output_slot,
    )
    assert execution.output is not None
    assert execution.output.result_export is not None
    assert execution.output.result_export.test_run_result.metadata.started_at == fixed


def test_calibration_cli_saves_loads_and_reports_without_overwrite(
    tmp_path: Path,
) -> None:
    result_path = tmp_path / "calibration-result.json"
    coefficients_path = tmp_path / "calibration-coefficients.json"
    report_path = tmp_path / "calibration-report"
    output = io.StringIO()
    dependencies = CliDependencies(
        job_id_factory=lambda: "calibration-cli-chain",
        event_id_factory=lambda: "calibration-cli-event",
    )

    status = main(
        [
            "simulate",
            "calibration",
            "--points",
            "8",
            "--output",
            str(result_path),
            "--coefficients-output",
            str(coefficients_path),
            "--json",
        ],
        stdout=output,
        dependencies=dependencies,
    )
    assert status == 0
    document = json.loads(output.getvalue())
    assert document["request"]["job_type"] == "CALIBRATION_ANALYSIS"
    assert document["result"]["test_run_outcome"] == "PASS"
    assert document["calibration_coefficients"]["scale"] == 2.0
    assert document["coefficient_artifact"]["overwrite"] is False
    assert result_path.is_file()
    assert coefficients_path.is_file()

    loaded = load_calibration_coefficients_json(coefficients_path)
    assert loaded.coefficient_id == "afe-linear-calibration"
    inspection = io.StringIO()
    assert (
        main(
            [
                "coefficients",
                "inspect",
                "--input",
                str(coefficients_path),
                "--json",
            ],
            stdout=inspection,
            dependencies=dependencies,
        )
        == 0
    )
    inspected = json.loads(inspection.getvalue())
    assert inspected["coefficient_file"]["validated"] is True
    assert inspected["coefficient_file"]["applied"] is False
    assert inspected["hardware_claim"] == "NO_PERFORMANCE_VALIDATION"

    inspection_text = io.StringIO()
    assert (
        main(
            ["coefficients", "inspect", "--input", str(coefficients_path)],
            stdout=inspection_text,
            dependencies=dependencies,
        )
        == 0
    )
    assert "Calibration coefficients:" in inspection_text.getvalue()
    assert "Applied to measurements: NO" in inspection_text.getvalue()

    assert (
        main(
            [
                "report",
                "--input",
                str(result_path),
                "--output",
                str(report_path),
                "--json",
            ],
            stdout=io.StringIO(),
            dependencies=dependencies,
        )
        == 0
    )
    assert 'data-series="after"' in (report_path / "chart.svg").read_text(
        encoding="utf-8"
    )

    errors = io.StringIO()
    assert (
        main(
            [
                "simulate",
                "calibration",
                "--coefficients-output",
                str(coefficients_path),
            ],
            stderr=errors,
            dependencies=dependencies,
        )
        == 5
    )
    assert "OUTPUT_EXISTS" in errors.getvalue()

    text_result = tmp_path / "calibration-result-text.json"
    text_coefficients = tmp_path / "calibration-coefficients-text.json"
    text_output = io.StringIO()
    assert (
        main(
            [
                "simulate",
                "calibration",
                "--points",
                "4",
                "--output",
                str(text_result),
                "--coefficients-output",
                str(text_coefficients),
            ],
            stdout=text_output,
            dependencies=dependencies,
        )
        == 0
    )
    rendered = text_output.getvalue()
    assert "Calibration mapping:" in rendered
    assert f"Coefficient artifact: {text_coefficients.resolve()}" in rendered
    assert "Coefficient SHA-256:" in rendered


def test_coefficient_inspection_rejects_tampered_input_without_applying_it(
    tmp_path: Path,
) -> None:
    source = tmp_path / "tampered-coefficients.json"
    source.write_text('{"schema_version":"future"}\n', encoding="utf-8")
    output = io.StringIO()
    errors = io.StringIO()

    status = main(
        ["coefficients", "inspect", "--input", str(source), "--json"],
        stdout=output,
        stderr=errors,
    )

    assert status == 5
    assert output.getvalue() == ""
    issue = json.loads(errors.getvalue())
    assert issue["issue"]["code"] == "INPUT_DATA"
    assert issue["hardware_claim"] == "NO_PERFORMANCE_VALIDATION"


def test_dashboard_calibration_saves_and_validates_coefficients(
    tmp_path: Path,
) -> None:
    application = DashboardApplication(job_id_factory=lambda: "dashboard-calibration")
    assert application.next()
    assert application.select_job(ProductJobType.CALIBRATION_ANALYSIS)
    assert application.next()
    draft = replace(application.wizard_state.draft, sample_count="8")
    assert application.prepare_review(draft)
    assert "CALIBRATION_ANALYSIS" in " ".join(application.wizard_state.review_lines)
    assert application.run()
    _wait_for_result(application)

    assert application.wizard_state.coefficient_available is True
    assert application.wizard_state.can_save_coefficients is True
    assert application.dashboard_state.result.outcome is RunOutcome.PASS
    assert application.has_unsaved_result is True

    coefficient_path = tmp_path / "dashboard-coefficients.json"
    result_path = tmp_path / "dashboard-result.json"
    assert application.save_calibration_coefficients(str(coefficient_path))
    original_coefficients = coefficient_path.read_bytes()
    assert not application.save_calibration_coefficients(str(coefficient_path))
    assert coefficient_path.read_bytes() == original_coefficients
    assert application.wizard_state.issue is not None
    assert application.wizard_state.issue.code.value == "OUTPUT_EXISTS"
    assert application.has_unsaved_result is True
    assert application.export_result(str(result_path), "json")
    assert application.has_unsaved_result is False
    assert {
        artifact.name for artifact in application.dashboard_state.artifacts.artifacts
    } == {
        coefficient_path.name,
        result_path.name,
    }

    assert application.load_calibration_coefficients(str(coefficient_path))
    assert application.loaded_calibration_coefficients is not None
    assert "did not change or rerun" in application.wizard_state.coefficient_message
    assert not application.load_calibration_coefficients(str(tmp_path / "wrong.txt"))
    assert application.loaded_calibration_coefficients is not None
    assert application.wizard_state.issue is not None
    assert application.wizard_state.issue.code.value == "INVALID_REQUEST"

    assert application.start_new_test()
    assert application.loaded_calibration_coefficients is None
    assert application.request_close()


def test_dashboard_coefficient_actions_fail_closed_outside_result_or_bad_paths(
    tmp_path: Path,
) -> None:
    application = DashboardApplication()
    assert not application.save_calibration_coefficients(
        str(tmp_path / "not-available.json")
    )
    assert not application.load_calibration_coefficients(
        str(tmp_path / "not-available.json")
    )

    assert application.next()
    assert application.select_job(ProductJobType.CALIBRATION_ANALYSIS)
    assert application.next()
    assert application.prepare_review(
        replace(application.wizard_state.draft, sample_count="4")
    )
    assert application.run()
    _wait_for_result(application)
    assert not application.save_calibration_coefficients("")
    assert not application.save_calibration_coefficients(" padded.json ")
    assert application.request_close()
