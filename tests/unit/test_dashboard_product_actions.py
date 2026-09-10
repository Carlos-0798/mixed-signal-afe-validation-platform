"""Headless native-action boundaries and project/report callback wiring."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from analog_validation.exports import load_result_export_json
from analog_validation_app import (
    HumanReportPublication,
    ProductJobType,
    ProductRequestError,
    ProductSourceMode,
    ProductWorkflowConfiguration,
    ReportArtifact,
    build_human_report_view,
)
from analog_validation_app.dashboard import app as app_module
from analog_validation_app.dashboard.report_actions import ReportActions
from analog_validation_app.dashboard.wizard import (
    DashboardWizardDraft,
    DashboardWizardStep,
)
from tests.unit.test_dashboard_app import FakeWidget, fake_toolkit


def _publication(tmp_path: Path) -> HumanReportPublication:
    payload = b"<!doctype html><title>Saved report</title>"
    (tmp_path / "report.html").write_bytes(payload)
    return HumanReportPublication(
        tmp_path,
        (
            ReportArtifact(
                "report.html",
                "text/html",
                len(payload),
                hashlib.sha256(payload).hexdigest(),
            ),
        ),
    )


def test_report_directory_chooser_returns_new_path_or_cancel_without_writing(
    tmp_path: Path,
) -> None:
    calls: list[dict[str, Any]] = []
    parent = object()

    def choose(**options: Any) -> str:
        calls.append(options)
        return str(tmp_path / "new-report")

    assert app_module._choose_report_directory(parent, dialog=choose) == str(
        tmp_path / "new-report"
    )
    assert calls == [
        {
            "parent": parent,
            "title": "Name a NEW report folder",
            "initialfile": "validation-report",
            "defaultextension": "",
            "confirmoverwrite": False,
        }
    ]
    assert app_module._choose_report_directory(parent, dialog=lambda **_: "") == ""
    assert not tuple(tmp_path.iterdir())


@pytest.mark.parametrize("invalid", [None, False, Path("report")])
def test_report_chooser_rejects_nonstring_result(invalid: Any) -> None:
    with pytest.raises(ProductRequestError, match="path string"):
        app_module._choose_report_directory(object(), dialog=lambda **_: invalid)


@pytest.mark.parametrize("unsaved", [False, True])
@pytest.mark.parametrize("answer", [False, True])
def test_replace_setup_confirmation_is_explicit_and_defaults_to_keep_work(
    unsaved: bool, answer: bool
) -> None:
    calls: list[dict[str, Any]] = []

    def confirm(**options: Any) -> bool:
        calls.append(options)
        return answer

    assert (
        app_module._confirm_replace_setup(
            object(), has_unsaved_result=unsaved, dialog=confirm
        )
        is answer
    )
    assert calls[0]["default"] == "no"
    assert calls[0]["icon"] == "warning"
    assert ("result or coefficients" in calls[0]["detail"]) is unsaved
    assert "saved source configuration stays unchanged" in calls[0]["detail"]


@pytest.mark.parametrize("invalid", [None, "yes", 1])
def test_replace_confirmation_rejects_nonboolean_response(invalid: Any) -> None:
    with pytest.raises(ProductRequestError, match="return a bool"):
        app_module._confirm_replace_setup(
            object(), has_unsaved_result=False, dialog=lambda **_: invalid
        )


def test_open_saved_report_checks_content_and_passes_only_local_uri(
    tmp_path: Path,
) -> None:
    publication = _publication(tmp_path)
    opened: list[str] = []

    def open_local(uri: str) -> bool:
        opened.append(uri)
        return True

    app_module._open_published_report(publication, opener=open_local)
    assert opened == [(tmp_path / "report.html").resolve().as_uri()]
    with pytest.raises(ProductRequestError, match="No browser opened"):
        app_module._open_published_report(publication, opener=lambda _: False)


@pytest.mark.parametrize("same_length", [False, True])
def test_open_saved_report_rejects_modified_file_before_opener(
    tmp_path: Path, same_length: bool
) -> None:
    publication = _publication(tmp_path)
    path = tmp_path / "report.html"
    original = path.read_bytes()
    path.write_bytes(b"!" * len(original) if same_length else b"changed")
    opened: list[str] = []

    def unexpected_open(uri: str) -> bool:
        opened.append(uri)
        return True

    with pytest.raises(ProductRequestError, match="changed after publication"):
        app_module._open_published_report(publication, opener=unexpected_open)
    assert opened == []


def test_report_actions_bind_buttons_and_cache_rendered_state(tmp_path: Path) -> None:
    root, tk, ttk = fake_toolkit()
    calls: list[str] = []
    actions = ReportActions(
        root,
        tk,
        ttk,
        on_save=lambda: calls.append("save"),
        on_open=lambda: calls.append("open"),
    )
    actions.render(False, None)
    assert actions.save_button.config["state"] == "disabled"
    assert actions.open_button.config["state"] == "disabled"
    assert "finalized analysis" in actions.path.get()
    actions.render(True, None)
    assert actions.save_button.config["state"] == "normal"
    assert actions.open_button.config["state"] == "disabled"
    assert "complete result JSON" in actions.path.get()
    publication = _publication(tmp_path)
    actions.render(True, publication)
    assert actions.open_button.config["state"] == "normal"
    assert str(tmp_path) in actions.path.get()
    actions.save_button.kwargs["command"]()
    actions.open_button.kwargs["command"]()
    assert calls == ["save", "open"]
    actions.path.set("unchanged cache marker")
    actions.render(True, publication)
    assert actions.path.get() == "unchanged cache marker"
    actions.render(False, None)
    assert actions.open_button.config["state"] == "disabled"
    assert str(tmp_path) not in actions.path.get()


class _Form:
    def __init__(self) -> None:
        self.draft = DashboardWizardDraft()
        self.error: ProductRequestError | None = None
        self.loaded: list[DashboardWizardDraft] = []

    def snapshot(self) -> DashboardWizardDraft:
        if self.error is not None:
            raise self.error
        return self.draft

    def load(self, draft: DashboardWizardDraft) -> None:
        self.draft = draft
        self.error = None
        self.loaded.append(draft)


def _launch_callbacks(
    monkeypatch: pytest.MonkeyPatch, exercise: Callable[[Any], None]
) -> None:
    root, tk, ttk = fake_toolkit()
    captures = SimpleNamespace(root=root, form=_Form(), selection=[], render_calls=0)
    original_application = app_module.DashboardApplication

    def create_application(**kwargs: Any) -> Any:
        captures.application = original_application(**kwargs)
        return captures.application

    def render(*_args: Any) -> None:
        captures.render_calls += 1

    def build_widgets(*_args: Any, **callbacks: Any) -> Any:
        captures.callbacks = callbacks
        captures.workflow_page = object()
        return SimpleNamespace(
            form=captures.form,
            notebook=SimpleNamespace(select=captures.selection.append),
            workflow_page=captures.workflow_page,
            section_frames={"export": FakeWidget()},
            render=render,
        )

    def build_page(*args: Any, **kwargs: Any) -> Any:
        captures.workspace = args[4]
        captures.load_setup = kwargs["on_load_setup"]
        return SimpleNamespace(render=lambda: None)

    def build_import_page(*args: Any, **kwargs: Any) -> Any:
        captures.import_callbacks = kwargs
        captures.import_page = SimpleNamespace(
            render=lambda: None, has_unsaved_work=False
        )
        return captures.import_page

    def mainloop() -> None:
        captures.buttons = {widget.kwargs["text"]: widget for widget in ttk.buttons}
        exercise(captures)
        root.protocols["WM_DELETE_WINDOW"]()

    monkeypatch.setattr(app_module, "DashboardApplication", create_application)
    monkeypatch.setattr(app_module, "create_dashboard_workflow_widgets", build_widgets)
    monkeypatch.setattr(app_module, "ProjectPage", build_page)
    monkeypatch.setattr(app_module, "ImportPage", build_import_page)
    monkeypatch.setattr(app_module, "_confirm_discard_unsaved_result", lambda *_: True)
    monkeypatch.setattr(root, "mainloop", mainloop)
    result = app_module.launch_dashboard(tk_loader=lambda: (tk, ttk))
    assert result.closed_safely
    assert root.destroyed


def test_save_callback_cancel_skips_publication_then_error_keeps_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = (
        Path(__file__).resolve().parents[2]
        / "test-data"
        / "golden"
        / "phase3_dc_sweep_result_v1.json"
    )
    view = build_human_report_view(load_result_export_json(fixture))

    def exercise(captured: Any) -> None:
        application = captured.application
        application._dashboard.present_report(view)
        save_calls: list[str] = []

        def save(path: str) -> bool:
            save_calls.append(path)
            raise OSError("report storage unavailable")

        monkeypatch.setattr(application, "save_report_bundle", save)
        monkeypatch.setattr(app_module, "_choose_report_directory", lambda _: "")
        save_button = captured.buttons["Save report package…"]
        save_button.kwargs["command"]()
        assert save_calls == []
        assert application.wizard_state.issue is None
        monkeypatch.setattr(
            app_module, "_choose_report_directory", lambda _: "new-report"
        )
        before = application.dashboard_state.plot
        save_button.kwargs["command"]()
        assert save_calls == ["new-report"]
        assert application.wizard_state.issue is not None
        assert application.wizard_state.issue.technical_type == "OSError"
        assert application.dashboard_state.result.outcome is view.outcome
        assert (
            application.dashboard_state.result.evidence_source is view.evidence_source
        )
        assert application.dashboard_state.plot is before
        assert captured.render_calls >= 3

    _launch_callbacks(monkeypatch, exercise)


def test_report_open_callback_handles_absence_then_success_then_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    publication = _publication(tmp_path)

    def exercise(captured: Any) -> None:
        application = captured.application
        open_button = captured.buttons["Open saved report"]
        open_button.kwargs["command"]()
        assert application.wizard_state.issue is not None
        assert "Save a report package" in application.wizard_state.issue.what_happened
        application._report_publication = publication
        opened: list[HumanReportPublication] = []
        monkeypatch.setattr(app_module, "_open_published_report", opened.append)
        open_button.kwargs["command"]()
        assert opened == [publication]

        def fail_open(_publication: HumanReportPublication) -> None:
            raise ProductRequestError("browser unavailable")

        monkeypatch.setattr(app_module, "_open_published_report", fail_open)
        open_button.kwargs["command"]()
        assert application.report_publication is publication
        assert application.wizard_state.issue.what_happened == "browser unavailable"

    _launch_callbacks(monkeypatch, exercise)


def test_loading_callback_rejects_busy_batch_and_run_button_does_not_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = ProductWorkflowConfiguration(
        ProductSourceMode.SIMULATOR, ProductJobType.DC_ANALYSIS
    )

    def exercise(captured: Any) -> None:
        def unexpected_discovery() -> None:
            raise AssertionError("A busy project batch must block device discovery")

        monkeypatch.setattr(
            captured.application, "discover_ports", unexpected_discovery
        )
        captured.workspace._thread = object()
        before = captured.application.wizard_state
        try:
            assert not captured.load_setup(configuration)
            captured.callbacks["on_run"]()
            captured.callbacks["on_discover"]()
            assert "Wait for the project batch" in captured.workspace.status
            assert captured.application.wizard_state is before
            assert not captured.form.loaded
            assert not captured.selection
        finally:
            captured.workspace._thread = None

    _launch_callbacks(monkeypatch, exercise)


@pytest.mark.parametrize("malformed", [False, True])
def test_loading_cancel_preserves_scratch_then_confirmation_replaces_it(
    monkeypatch: pytest.MonkeyPatch, malformed: bool
) -> None:
    configuration = ProductWorkflowConfiguration(
        ProductSourceMode.SIMULATOR, ProductJobType.DC_ANALYSIS, sample_count=7
    )
    confirmations: list[bool] = []
    accepted = False

    def confirm(_root: object, *, has_unsaved_result: bool) -> bool:
        confirmations.append(has_unsaved_result)
        return accepted

    monkeypatch.setattr(app_module, "_confirm_replace_setup", confirm)

    def exercise(captured: Any) -> None:
        nonlocal accepted
        captured.form.draft = replace(captured.form.draft, sample_count="11")
        if malformed:
            captured.form.error = ProductRequestError("bad form field")
        original = captured.form.draft
        assert not captured.load_setup(configuration)
        assert captured.form.draft is original
        assert not captured.selection
        assert not captured.form.loaded
        accepted = True
        assert captured.load_setup(configuration)
        assert len(confirmations) == 2
        assert captured.form.snapshot().to_product_configuration() == configuration
        assert (
            captured.application.wizard_state.step is DashboardWizardStep.CONFIGURATION
        )
        assert not captured.application.wizard_state.can_run
        assert captured.selection == [captured.workflow_page]

    _launch_callbacks(monkeypatch, exercise)


def test_loading_rejected_by_application_leaves_navigation_and_form_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration = ProductWorkflowConfiguration(
        ProductSourceMode.SIMULATOR, ProductJobType.DC_ANALYSIS
    )

    def exercise(captured: Any) -> None:
        monkeypatch.setattr(
            captured.application,
            "load_preset_configuration",
            lambda *_args, **_kwargs: False,
        )
        assert not captured.load_setup(configuration)
        assert not captured.form.loaded
        assert not captured.selection

    _launch_callbacks(monkeypatch, exercise)
