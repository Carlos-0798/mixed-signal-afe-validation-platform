"""Real Tk project-to-setup-to-report flow using only synthetic input."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import traceback
from pathlib import Path
from time import monotonic
from typing import Any

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Tk product target")
def test_real_tk_stored_preset_review_and_saved_report_package(tmp_path: Path) -> None:
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=35,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip() == "PRODUCT_LOOP_PASS"
    assert not completed.stderr, completed.stderr


def _exercise_product_loop(tmp_path: Path) -> None:
    from analog_validation import EvidenceSource
    from analog_validation.exports import load_result_export_json
    from analog_validation_app import (
        DashboardWizardStep,
        ProductJobType,
        ProductWorkerState,
        UserIssueCode,
        build_human_report_view,
    )
    from analog_validation_app.dashboard import app as app_module
    from analog_validation_app.dashboard import widgets as widget_module
    from analog_validation_app.dashboard.themes import PALETTES

    captured: dict[str, Any] = {}
    errors: list[BaseException] = []
    opened: list[Any] = []
    confirmations: list[bool] = []
    completed: list[bool] = []
    project_path = tmp_path / "project.json"
    report_path = tmp_path / "report-package"
    application_factory = app_module.DashboardApplication
    widget_factory = app_module.create_dashboard_workflow_widgets
    page_factory = app_module.ProjectPage
    report_factory = app_module.ReportActions
    allow_replace = True
    deadline = monotonic() + 20
    phase = 0

    def forbidden_serial(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError(
            "The Simulator product loop must not access serial devices"
        )

    def construct_application(**kwargs: Any) -> Any:
        application = application_factory(
            serial_backend_factory=forbidden_serial, **kwargs
        )
        captured["application"] = application
        return application

    def construct_widgets(*args: Any, **kwargs: Any) -> Any:
        widgets = widget_factory(*args, **kwargs)
        captured["widgets"] = widgets
        return widgets

    def construct_reports(*args: Any, **kwargs: Any) -> Any:
        reports = report_factory(*args, **kwargs)
        captured["reports"] = reports
        return reports

    def confirm_replace(_root: Any, *, has_unsaved_result: bool) -> bool:
        confirmations.append(has_unsaved_result)
        return allow_replace

    def construct_page(*args: Any, **kwargs: Any) -> Any:
        nonlocal phase, allow_replace
        page = page_factory(*args, **kwargs)
        root = args[0]
        captured["root"] = root
        root.tk.call("tk", "scaling", 1.0)
        root.geometry("1040x760")

        def advance() -> None:
            nonlocal phase, allow_replace
            try:
                assert monotonic() < deadline, "Project-to-report UI timed out"
                widgets = captured["widgets"]
                application = captured["application"]
                reports = captured["reports"]
                if phase == 0:
                    root.deiconify()
                    widgets.notebook.select(page.tab)
                    create_button = next(
                        control
                        for control in page.controls
                        if control.winfo_class() == "TButton"
                        and control.cget("text") == "Create starter…"
                    )
                    create_button.invoke()
                    assert project_path.is_file()
                    captured["project_bytes"] = project_path.read_bytes()
                    captured["project"] = page.workspace.project
                    stored = page.workspace.configuration_for_setup("dc-default")
                    assert stored.job_type is ProductJobType.DC_ANALYSIS
                    captured["stored"] = stored
                    page.presets.selection_set(("dc-default",))
                    page.render()
                    assert page.load_setup_button.instate(("!disabled",))
                    page.load_setup_button.invoke()
                    assert widgets.notebook.select() == str(widgets.workflow_page)
                    assert (
                        application.wizard_state.step
                        is DashboardWizardStep.CONFIGURATION
                    )
                    assert widgets.form.snapshot().to_product_configuration() == stored
                    assert widgets.run_button.instate(("disabled",))
                    assert (
                        not application.dashboard_state.progress.worker_state.is_active
                    )
                    assert reports.save_button.instate(("disabled",))
                    assert reports.open_button.instate(("disabled",))

                    # Declining replacement must preserve a user's unreviewed edits.
                    widgets.form.sample_count.set(str(stored.sample_count + 1))
                    edited = widgets.form.snapshot()
                    widgets.notebook.select(page.tab)
                    before_confirm = len(confirmations)
                    allow_replace = False
                    page.load_setup_button.invoke()
                    assert len(confirmations) == before_confirm + 1
                    assert widgets.form.snapshot() == edited
                    assert widgets.notebook.select() == str(page.tab)
                    assert (
                        not application.dashboard_state.progress.worker_state.is_active
                    )
                    allow_replace = True
                    page.load_setup_button.invoke()
                    assert widgets.form.snapshot().to_product_configuration() == stored
                    assert widgets.notebook.select() == str(widgets.workflow_page)
                    assert widgets.run_button.instate(("disabled",))
                    widgets.review_button.invoke()
                    assert application.wizard_state.step is DashboardWizardStep.REVIEW
                    assert widgets.run_button.instate(("!disabled",))
                    assert "SYNTHETIC" in widgets.review_value.get()
                    widgets.run_button.invoke()
                    phase = 1
                elif (
                    phase == 1
                    and application.wizard_state.step is DashboardWizardStep.RESULT
                ):
                    result = application.dashboard_state.result
                    assert (
                        application.dashboard_state.progress.worker_state
                        is ProductWorkerState.SUCCEEDED
                    )
                    assert result.evidence_source is EvidenceSource.SYNTHETIC
                    assert result.outcome is not None
                    assert application.has_unsaved_result
                    assert reports.save_button.instate(("!disabled",))
                    root.update_idletasks()
                    canvas = widgets.scroll_canvases[1]
                    viewport = (
                        canvas.winfo_rootx(),
                        canvas.winfo_rooty(),
                        canvas.winfo_rootx() + canvas.winfo_width(),
                        canvas.winfo_rooty() + canvas.winfo_height(),
                    )
                    # Invoke is also possible on off-screen controls: explicitly
                    # verify both report actions fit the actual visible viewport.
                    for button in (reports.save_button, reports.open_button):
                        rectangle = (
                            button.winfo_rootx(),
                            button.winfo_rooty(),
                            button.winfo_rootx() + button.winfo_width(),
                            button.winfo_rooty() + button.winfo_height(),
                        )
                        assert button.winfo_viewable()
                        assert (
                            viewport[0] <= rectangle[0] < rectangle[2] <= viewport[2]
                            and viewport[1]
                            <= rectangle[1]
                            < rectangle[3]
                            <= viewport[3]
                        ), (button.cget("text"), rectangle, viewport)
                    reports.save_button.invoke()
                    publication = application.report_publication
                    assert publication is not None
                    assert publication.output_directory == report_path.resolve()
                    assert not application.has_unsaved_result
                    assert reports.open_button.instate(("!disabled",))
                    bundle = load_result_export_json(report_path / "result.json")
                    view = build_human_report_view(bundle)
                    assert view.outcome is result.outcome
                    assert view.evidence_source is EvidenceSource.SYNTHETIC
                    manifest = json.loads(
                        (report_path / "manifest.json").read_text(encoding="utf-8")
                    )
                    assert (
                        manifest["canonical_result_sha256"]
                        == view.canonical_result_sha256
                    )
                    assert manifest["hardware_claim"] == "NO_NEW_HARDWARE_VALIDATION"
                    saved = {
                        path.name: path.read_bytes() for path in report_path.iterdir()
                    }
                    assert set(saved) == {
                        "report.html",
                        "report.md",
                        "report.txt",
                        "chart.svg",
                        "result.json",
                        "manifest.json",
                    }
                    for artifact in publication.artifacts:
                        assert (
                            hashlib.sha256(saved[artifact.name]).hexdigest()
                            == artifact.sha256
                        )
                    reports.open_button.invoke()
                    assert opened == [publication]

                    # A second save attempts the same path, preserving prior evidence.
                    reports.save_button.invoke()
                    assert application.wizard_state.issue is not None
                    assert (
                        application.wizard_state.issue.code
                        is UserIssueCode.OUTPUT_EXISTS
                    )
                    assert "already exists" in widgets.issue_value.get()
                    assert application.report_publication is publication
                    assert application.dashboard_state.result.outcome is result.outcome
                    assert application.wizard_state.can_export
                    assert saved == {
                        path.name: path.read_bytes() for path in report_path.iterdir()
                    }

                    for name in PALETTES:
                        state = application.dashboard_state
                        root._avs_theme_value.set(name)
                        root._avs_theme_select.event_generate("<<ComboboxSelected>>")
                        root.update_idletasks()
                        assert application.dashboard_state is state
                        assert application.report_publication is publication
                        assert (
                            application.dashboard_state.result.outcome is result.outcome
                        )
                        assert (
                            widgets.form.snapshot().to_product_configuration()
                            == captured["stored"]
                        )
                    assert root.winfo_width() == 1040
                    assert root.winfo_height() == 760
                    assert page.workspace.project is captured["project"]
                    assert project_path.read_bytes() == captured["project_bytes"]
                    assert not tuple(tmp_path.glob(".report-package.*.tmp"))
                    completed.append(True)
                    root.after(
                        0, lambda: root.tk.call(root.protocol("WM_DELETE_WINDOW"))
                    )
                    return
            except BaseException as error:  # noqa: BLE001 - rethrow callback failures after mainloop
                errors.append(error)
                traceback.print_exc()
                root.quit()
                return
            root.after(20, advance)

        root.after(20, advance)
        return page

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(app_module, "DashboardApplication", construct_application)
        patch.setattr(
            app_module, "create_dashboard_workflow_widgets", construct_widgets
        )
        patch.setattr(app_module, "ProjectPage", construct_page)
        patch.setattr(app_module, "ReportActions", construct_reports)
        patch.setattr(app_module, "_choose_project_path", lambda *_: str(project_path))
        patch.setattr(
            app_module, "_choose_report_directory", lambda *_: str(report_path)
        )
        patch.setattr(app_module, "_open_published_report", opened.append)
        patch.setattr(app_module, "_confirm_replace_setup", confirm_replace)
        patch.setattr(widget_module, "_windows_high_contrast_enabled", lambda: False)
        session = app_module.launch_dashboard(withdraw=True, poll_interval_ms=10)
    if errors:
        raise errors[0]
    assert completed == [True]
    assert session.closed_safely


if __name__ == "__main__":
    _exercise_product_loop(Path(sys.argv[1]))
    print("PRODUCT_LOOP_PASS")
