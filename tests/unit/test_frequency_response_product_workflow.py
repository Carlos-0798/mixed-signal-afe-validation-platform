from __future__ import annotations

import io
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic, sleep
from typing import Any, cast

import pytest

from analog_validation import (
    EvidenceSource,
    FrequencyResponseSimulatorConfig,
)
from analog_validation import TestRunOutcome as RunOutcome
from analog_validation_app import (
    DashboardApplication,
    DashboardWizardStep,
    FrequencyResponseJobService,
    ProductJobRequest,
    ProductJobType,
    ProductRequestError,
    ProductSourceMode,
    ProductWorkerState,
    ProductWorkflowConfiguration,
    ReportChartKind,
    build_human_report_view,
    execute_product_job,
    make_frequency_response_simulator_adapter_factory,
    prepare_product_job,
    render_human_report_svg,
)
from analog_validation_app.cli import (
    CLI_ENGINEERING_FAIL_EXIT_CODE,
    CliDependencies,
    main,
)


def _wait_for_result(application: DashboardApplication) -> None:
    deadline = monotonic() + 5.0
    while monotonic() < deadline:
        application.poll()
        if application.wizard_state.step is DashboardWizardStep.RESULT:
            return
        sleep(0.001)
    raise AssertionError("frequency-response Dashboard job did not reach Result")


def test_frequency_response_service_and_report_chain_are_traceable() -> None:
    prepared = prepare_product_job(
        ProductWorkflowConfiguration(
            ProductSourceMode.SIMULATOR,
            ProductJobType.FREQUENCY_RESPONSE_ANALYSIS,
        ),
        "frequency-service-chain",
    )

    service = prepared.service_factory(prepared.request)
    assert isinstance(service, FrequencyResponseJobService)
    execution = execute_product_job(
        prepared.request,
        prepared.service_factory,
        prepared.output_slot,
    )

    assert execution.worker_state is ProductWorkerState.SUCCEEDED
    assert execution.result is not None
    assert execution.result.test_run_outcome is RunOutcome.PASS
    assert execution.result.evidence_source is EvidenceSource.SYNTHETIC
    assert execution.output is not None
    assert len(execution.output.read_result.measurements) == 63
    bundle = execution.output.result_export
    assert bundle is not None
    metrics = {value.name: value.value for value in bundle.metrics}
    assert metrics["cutoff_frequency"] == pytest.approx(1000.0)
    assert len(bundle.points) == 21
    assert all(len(point.references) == 3 for point in bundle.points)

    view = build_human_report_view(bundle)
    assert view.chart_kind is ReportChartKind.FREQUENCY_RESPONSE
    assert view.title == "Frequency Response Validation Report"
    assert view.evidence_source is EvidenceSource.SYNTHETIC
    svg = render_human_report_svg(view)
    assert 'data-series="gain"' in svg
    assert 'data-marker="cutoff-target"' in svg
    assert 'data-marker="cutoff-frequency"' in svg
    assert "Frequency (Hz, logarithmic)" in svg
    assert "performed no new hardware validation" in svg
    assert "No finite plottable frequency-response points" in (
        render_human_report_svg(replace(view, points=()))
    )

    review = "\n".join(prepared.review_lines)
    assert "modeled cutoff 1000 Hz" in review
    assert "Reviewed cutoff target: 1000 Hz" in review


def test_frequency_response_factory_and_explicit_service_clock_are_checked() -> None:
    with pytest.raises(ProductRequestError, match="FrequencyResponseSimulatorConfig"):
        make_frequency_response_simulator_adapter_factory(
            cast(Any, object())
        )

    config = FrequencyResponseSimulatorConfig()
    factory = make_frequency_response_simulator_adapter_factory(config)
    with pytest.raises(ProductRequestError, match="FREQUENCY_RESPONSE_ANALYSIS"):
        factory(
            ProductJobRequest(
                "wrong-frequency-job",
                ProductSourceMode.SIMULATOR,
                ProductJobType.READ,
                "afe",
                "1",
            )
        )
    mismatched_factory = make_frequency_response_simulator_adapter_factory(
        replace(config, profile_name="different-profile")
    )
    with pytest.raises(ProductRequestError, match="profile identity"):
        mismatched_factory(
            ProductJobRequest(
                "mismatched-frequency-profile",
                ProductSourceMode.SIMULATOR,
                ProductJobType.FREQUENCY_RESPONSE_ANALYSIS,
                "afe",
                "1",
            )
        )

    fixed_time = datetime(2026, 9, 5, 18, 30, tzinfo=timezone.utc)
    prepared = prepare_product_job(
        ProductWorkflowConfiguration(
            ProductSourceMode.SIMULATOR,
            ProductJobType.FREQUENCY_RESPONSE_ANALYSIS,
        ),
        "frequency-explicit-clock",
        service_clock=lambda: fixed_time,
    )
    execution = execute_product_job(
        prepared.request,
        prepared.service_factory,
        prepared.output_slot,
    )
    assert execution.output is not None
    assert execution.output.result_export is not None
    assert execution.output.result_export.test_run_result.metadata.started_at == fixed_time


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"frequency_point_count": 9}, "frequency_point_count"),
        ({"frequency_channel": "afe.ch0.input"}, "channels must differ"),
        ({"frequency_minimum_hz": 0.0}, "frequency bounds"),
        ({"target_cutoff_frequency_hz": 100_000.0}, "target cutoff"),
        ({"simulated_cutoff_frequency_hz": 100_000.0}, "simulated cutoff"),
        ({"cutoff_relative_tolerance": 1.0}, "below one"),
        ({"cutoff_drop_db": 0.0}, "must be positive"),
        ({"frequency_input_amplitude": 3301.0}, "within 3.3 V"),
    ],
)
def test_frequency_response_configuration_rejects_invalid_contracts(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ProductRequestError, match=message):
        ProductWorkflowConfiguration(
            ProductSourceMode.SIMULATOR,
            ProductJobType.FREQUENCY_RESPONSE_ANALYSIS,
            **changes,  # type: ignore[arg-type]
        )


def test_frequency_response_cli_separates_model_from_acceptance_and_reports(
    tmp_path: Path,
) -> None:
    dependencies = CliDependencies(
        job_id_factory=lambda: "frequency-cli-chain",
        event_id_factory=lambda: "frequency-cli-event",
    )
    result_path = tmp_path / "frequency-result.json"
    report_path = tmp_path / "frequency-report"
    output = io.StringIO()

    assert (
        main(
            [
                "simulate",
                "frequency",
                "--output",
                str(result_path),
                "--json",
            ],
            stdout=output,
            dependencies=dependencies,
        )
        == 0
    )
    document = json.loads(output.getvalue())
    assert document["request"]["job_type"] == "FREQUENCY_RESPONSE_ANALYSIS"
    assert document["result"]["test_run_outcome"] == "PASS"
    assert document["result"]["evidence_source"] == "SYNTHETIC"
    assert result_path.is_file()

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
    chart = (report_path / "chart.svg").read_text(encoding="utf-8")
    assert 'data-series="gain"' in chart
    assert 'data-marker="cutoff-frequency"' in chart

    failed = io.StringIO()
    assert (
        main(
            [
                "simulate",
                "frequency",
                "--simulated-cutoff-hz",
                "2000",
                "--target-cutoff-hz",
                "1000",
                "--cutoff-relative-tolerance",
                "0.05",
                "--json",
            ],
            stdout=failed,
            dependencies=dependencies,
        )
        == CLI_ENGINEERING_FAIL_EXIT_CODE
    )
    failure_document = json.loads(failed.getvalue())
    assert failure_document["result"]["test_run_outcome"] == "FAIL"
    failed_metrics = {
        value["name"]: value["value"]
        for value in failure_document["result_export"]["metrics"]
    }
    assert failed_metrics["cutoff_frequency"] == pytest.approx(1948.0148061417415)

    human = io.StringIO()
    assert (
        main(
            ["simulate", "frequency", "--points", "10"],
            stdout=human,
            dependencies=dependencies,
        )
        == 0
    )
    assert "Estimated cutoff:" in human.getvalue()
    assert "Reference gain:" in human.getvalue()
    assert "Hardware performance validation: NOT CLAIMED" in human.getvalue()


def test_dashboard_frequency_response_runs_and_exports_without_hardware(
    tmp_path: Path,
) -> None:
    application = DashboardApplication(job_id_factory=lambda: "dashboard-frequency")
    assert application.next()
    assert application.select_job(ProductJobType.FREQUENCY_RESPONSE_ANALYSIS)
    assert application.next()
    draft = replace(
        application.wizard_state.draft,
        frequency_point_count="21",
        simulated_cutoff_frequency_hz="1000",
        target_cutoff_frequency_hz="1000",
    )
    assert application.prepare_review(draft)
    review = " ".join(application.wizard_state.review_lines)
    assert "FREQUENCY_RESPONSE_ANALYSIS" in review
    assert "evidence remains SYNTHETIC" in review
    assert "every requested point must be usable" in review
    assert application.run()
    _wait_for_result(application)

    assert application.dashboard_state.result.outcome is RunOutcome.PASS
    assert application.dashboard_state.plot.title == (
        "Frequency Response Validation Report"
    )
    assert "FREQUENCY_RESPONSE" in application.dashboard_state.plot.summary
    assert len(application.dashboard_state.plot.points) == 21
    assert application.has_unsaved_result is True

    destination = tmp_path / "dashboard-frequency.json"
    assert application.export_result(str(destination), "json")
    assert destination.is_file()
    assert application.has_unsaved_result is False
    assert application.request_close()
