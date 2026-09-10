from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import analog_validation_app.dashboard.application as application_module
from analog_validation import EvidenceSource
from analog_validation import TestRunOutcome as RunOutcome
from analog_validation.exports import dump_result_export_json, load_result_export_json
from analog_validation_app import (
    DashboardApplication,
    DashboardWizardDraft,
    DashboardWizardPresenter,
    DashboardWizardState,
    DashboardWizardStep,
    ProductJobType,
    ProductRequestError,
    ProductSourceMode,
    ProductWorkerState,
    ProductWorkflowConfiguration,
)
from tests.unit.test_dashboard_application import (
    advance_to_configuration,
    ready_dc_application,
    wait_for_result,
)


@pytest.mark.parametrize("job_type", tuple(ProductJobType))
@pytest.mark.parametrize(
    "source_mode", (ProductSourceMode.SIMULATOR, ProductSourceMode.CSV_REPLAY)
)
def test_loading_preset_invalidates_review_without_opening_missing_replay(
    tmp_path: Path, job_type: ProductJobType, source_mode: ProductSourceMode
) -> None:
    application = DashboardApplication()
    original = advance_to_configuration(application, ProductJobType.DC_ANALYSIS)
    assert application.prepare_review(original)
    assert application.wizard_state.can_run
    configuration = ProductWorkflowConfiguration(
        source_mode,
        job_type,
        sample_count=12,
        target_gain=1.2345678901234567,
        replay_path=tmp_path / "missing.csv"
        if source_mode is ProductSourceMode.CSV_REPLAY
        else None,
        replay_minimum=-1.25,
        replay_maximum=4000.5,
    )

    assert application.load_preset_configuration(configuration)

    state = application.wizard_state
    assert state.step is DashboardWizardStep.CONFIGURATION
    assert state.draft.to_product_configuration() == configuration
    assert not state.review_lines
    assert not state.can_run
    assert not state.export_available
    assert application.dashboard_state.active_job_id is None
    assert application.dashboard_state.progress.worker_state is ProductWorkerState.IDLE
    assert application.report_publication is None
    assert not tuple(tmp_path.iterdir())
    assert not application.run()
    assert application.request_close()


def test_unsaved_completed_analysis_requires_explicit_discard_before_preset_load() -> (
    None
):
    application = ready_dc_application()
    previous_draft = application.wizard_state.draft
    outcome = application.dashboard_state.result.outcome
    configuration = ProductWorkflowConfiguration(
        ProductSourceMode.SIMULATOR, ProductJobType.READ, sample_count=9
    )
    assert application.has_unsaved_result

    assert not application.load_preset_configuration(configuration)

    assert application.wizard_state.step is DashboardWizardStep.RESULT
    assert application.wizard_state.draft == previous_draft
    assert application.dashboard_state.result.outcome is outcome
    assert application.has_unsaved_result
    assert application.load_preset_configuration(configuration, discard_unsaved=True)
    assert application.wizard_state.step is DashboardWizardStep.CONFIGURATION
    assert application.wizard_state.draft.to_product_configuration() == configuration
    assert application.dashboard_state.result.outcome is None
    assert not application.has_unsaved_result
    assert application.request_close()


def test_loading_rejects_active_and_closed_dashboard_without_interrupting_work() -> (
    None
):
    application = DashboardApplication()
    draft = advance_to_configuration(application, ProductJobType.LIVE_MONITOR)
    assert application.prepare_review(
        replace(draft, sample_count="100", monitor_sample_interval_seconds="0.05")
    )
    configuration = ProductWorkflowConfiguration(
        ProductSourceMode.SIMULATOR, ProductJobType.READ
    )
    try:
        assert application.run()
        original = application.wizard_state.draft
        assert not application.load_preset_configuration(configuration)
        assert application.wizard_state.step is DashboardWizardStep.RUN
        assert application.wizard_state.draft == original
    finally:
        application.request_cancel()
        wait_for_result(application)
        assert application.request_close()
    assert not application.load_preset_configuration(configuration)
    assert application.is_closed


@pytest.mark.parametrize("bad_argument", ("configuration", "discard_unsaved"))
def test_loading_bad_arguments_preserves_editable_draft(bad_argument: str) -> None:
    application = DashboardApplication()
    original = application.wizard_state.draft
    configuration = ProductWorkflowConfiguration(
        ProductSourceMode.SIMULATOR, ProductJobType.READ
    )
    if bad_argument == "configuration":
        accepted = application.load_preset_configuration(cast(Any, {}))
    else:
        accepted = application.load_preset_configuration(
            configuration, discard_unsaved=cast(Any, "yes")
        )
    assert not accepted
    assert application.wizard_state.draft == original
    assert application.wizard_state.issue is not None
    assert application.request_close()


@pytest.mark.parametrize("changed_catalog", ("profile", "source"))
def test_loading_rechecks_catalog_before_replacing_current_setup(
    monkeypatch: pytest.MonkeyPatch, changed_catalog: str
) -> None:
    application = DashboardApplication()
    draft = advance_to_configuration(application, ProductJobType.DC_ANALYSIS)
    assert application.prepare_review(draft)
    configuration = ProductWorkflowConfiguration(
        ProductSourceMode.SIMULATOR, ProductJobType.READ
    )
    if changed_catalog == "profile":
        monkeypatch.setattr(
            application_module,
            "get_product_profile",
            lambda *_: SimpleNamespace(source_modes=()),
        )
    else:
        monkeypatch.setattr(
            application_module,
            "get_product_source",
            lambda *_: SimpleNamespace(supported_jobs=()),
        )
    assert not application.load_preset_configuration(configuration)
    assert application.wizard_state.step is DashboardWizardStep.REVIEW
    assert application.wizard_state.draft == draft
    assert application.wizard_state.review_lines
    assert application.wizard_state.issue is not None
    assert application.request_close()


def test_wizard_preset_transition_rejects_running_serial_and_non_draft_values() -> None:
    draft = DashboardWizardDraft()
    presenter = DashboardWizardPresenter(
        DashboardWizardState(0, DashboardWizardStep.RUN, draft)
    )
    with pytest.raises(ProductRequestError, match="current run"):
        presenter.load_preset_draft(draft)
    assert presenter.state.step is DashboardWizardStep.RUN
    presenter = DashboardWizardPresenter()
    for value in (None, replace(draft, source_mode=ProductSourceMode.SERIAL_READ_ONLY)):
        with pytest.raises(ProductRequestError, match="offline wizard draft"):
            presenter.load_preset_draft(cast(Any, value))
        assert presenter.state.step is DashboardWizardStep.SOURCE
    state = presenter.load_preset_draft(draft)
    assert state.step is DashboardWizardStep.CONFIGURATION
    assert state.draft == draft
    assert state.issue is None


@pytest.mark.parametrize("expected_outcome", (RunOutcome.PASS, RunOutcome.FAIL))
def test_report_package_preserves_analysis_json_outcome_and_existing_exports(
    tmp_path: Path, expected_outcome: RunOutcome
) -> None:
    application = DashboardApplication()
    draft = advance_to_configuration(application, ProductJobType.DC_ANALYSIS)
    assert application.prepare_review(
        replace(
            draft,
            sample_count="24",
            target_gain="2" if expected_outcome is RunOutcome.PASS else "999",
        )
    )
    assert application.run()
    wait_for_result(application)
    assert application.dashboard_state.result.outcome is expected_outcome
    prior_json = tmp_path / "standalone.json"
    assert application.export_result(str(prior_json), "json")
    # A same-named earlier export must not duplicate the packaged result row.
    assert application.export_result(str(tmp_path / "result.json"), "json")
    package = tmp_path / "report"

    assert application.save_report_bundle(str(package))

    publication = application.report_publication
    assert publication is not None
    assert publication.output_directory == package
    assert application.dashboard_state.result.outcome is expected_outcome
    assert (
        application.dashboard_state.result.evidence_source is EvidenceSource.SYNTHETIC
    )
    assert not application.has_unsaved_result
    assert (package / "result.json").read_bytes() == prior_json.read_bytes()
    bundle = load_result_export_json(package / "result.json")
    assert (package / "result.json").read_text(
        encoding="utf-8"
    ) == dump_result_export_json(bundle)
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["outcome"] == expected_outcome.value
    assert manifest["evidence_source"] == "SYNTHETIC"
    result_artifact = next(
        item for item in manifest["artifacts"] if item["name"] == "result.json"
    )
    assert (
        result_artifact["sha256"] == hashlib.sha256(prior_json.read_bytes()).hexdigest()
    )
    names = [
        artifact.name for artifact in application.dashboard_state.artifacts.artifacts
    ]
    assert names.count("result.json") == 1
    assert "standalone.json" in names
    snapshot = {path.name: path.read_bytes() for path in package.iterdir()}

    assert not application.save_report_bundle(str(package))

    assert snapshot == {path.name: path.read_bytes() for path in package.iterdir()}
    assert application.report_publication is publication
    assert application.dashboard_state.result.outcome is expected_outcome
    assert application.wizard_state.issue is not None
    assert application.save_report_bundle(str(tmp_path / "retry-report"))
    assert application.wizard_state.issue is None
    assert application.request_close()


def test_report_failure_keeps_unsaved_analysis_and_recovery_clears_issue(
    tmp_path: Path,
) -> None:
    application = ready_dc_application()
    assert not application.save_report_bundle(str(tmp_path / "absent" / "report"))
    assert application.report_publication is None
    assert application.has_unsaved_result
    assert application.dashboard_state.result.outcome is RunOutcome.PASS
    assert not tuple(tmp_path.iterdir())
    assert application.save_report_bundle(str(tmp_path / "recovered"))
    assert application.wizard_state.issue is None
    assert not application.has_unsaved_result
    assert application.request_close()


def test_report_is_unavailable_without_finalized_analysis(tmp_path: Path) -> None:
    application = DashboardApplication()
    assert not application.save_report_bundle(str(tmp_path / "initial"))
    draft = advance_to_configuration(application)
    assert application.prepare_review(draft)
    assert application.run()
    wait_for_result(application)
    assert not application.save_report_bundle(str(tmp_path / "read-report"))
    assert application.report_publication is None
    assert application.dashboard_state.result.outcome is None
    assert not tuple(tmp_path.iterdir())
    assert application.request_close()


def test_calibration_report_does_not_replace_separate_coefficient_save(
    tmp_path: Path,
) -> None:
    application = DashboardApplication()
    draft = advance_to_configuration(application, ProductJobType.CALIBRATION_ANALYSIS)
    assert application.prepare_review(replace(draft, sample_count="12"))
    assert application.run()
    wait_for_result(application)
    assert application.wizard_state.can_save_coefficients
    assert application.has_unsaved_result

    assert application.save_report_bundle(str(tmp_path / "report"))

    assert application.has_unsaved_result
    assert application.wizard_state.can_save_coefficients
    assert application.save_calibration_coefficients(
        str(tmp_path / "coefficients.json")
    )
    assert not application.has_unsaved_result
    assert application.save_report_bundle(str(tmp_path / "second-report"))
    assert "coefficients.json" in {
        artifact.name for artifact in application.dashboard_state.artifacts.artifacts
    }
    assert application.request_close()


@pytest.mark.parametrize("action", ("modify", "load"))
def test_leaving_saved_report_clears_publication_reference_without_deleting_files(
    tmp_path: Path, action: str
) -> None:
    application = ready_dc_application()
    package = tmp_path / "report"
    assert application.save_report_bundle(str(package))
    snapshot = {path.name: path.read_bytes() for path in package.iterdir()}
    if action == "modify":
        assert application.modify_setup()
    else:
        assert application.load_preset_configuration(
            ProductWorkflowConfiguration(
                ProductSourceMode.SIMULATOR, ProductJobType.READ
            )
        )
    assert application.report_publication is None
    assert not application.wizard_state.can_export
    assert snapshot == {path.name: path.read_bytes() for path in package.iterdir()}
    assert application.request_close()
