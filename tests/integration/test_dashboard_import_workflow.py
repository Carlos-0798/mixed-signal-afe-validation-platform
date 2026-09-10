"""Real Tk external-CSV-to-report loop without any device connection."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import traceback
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path
from threading import Event
from time import monotonic
from typing import Any
from unittest.mock import patch


def test_real_tk_voltage_import_review_run_and_saved_report(tmp_path: Path) -> None:
    if sys.platform != "win32":
        import pytest

        pytest.skip("Windows Tk product target")
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=35,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip() == "IMPORT_WORKFLOW_PASS"
    assert not completed.stderr, completed.stderr


def _exercise_import_loop(
    tmp_path: Path,
    *,
    preview_hook: Callable[[Any, Any], None] | None = None,
) -> None:
    """Run with installed packages too; optional hook permits separate visual capture."""
    from analog_validation import CsvReplayAdapter, EvidenceSource
    from analog_validation.exports import load_result_export_json
    from analog_validation_app import (
        DashboardWizardStep,
        ProductJobType,
        ProductWorkerState,
        build_human_report_view,
    )
    from analog_validation_app.dashboard import app as app_module
    from analog_validation_app.dashboard import widgets as widget_module
    from analog_validation_app.dashboard.themes import PALETTES
    from analog_validation_app.import_packages import verify_voltage_import

    tmp_path.mkdir(parents=True, exist_ok=True)
    source_path = tmp_path / "external-voltage.csv"
    mapping_path = tmp_path / "voltage-mapping.json"
    package_path = tmp_path / "imported-voltage"
    report_path = tmp_path / "report-package"
    extra_headers = ",".join(f"Metadata{index}" for index in range(61))
    extra_values = ",".join("retained" for _index in range(61))
    raw_bytes = (
        f"Time,Input,Output,{extra_headers}\n"
        + "".join(
            f"2026-09-09T12:00:0{index}Z,{0.2 + index / 10},{400 + 200 * index},{extra_values}\n"
            for index in range(6)
        )
    ).encode("utf-8")
    source_path.write_bytes(raw_bytes)
    captured: dict[str, Any] = {}
    errors: list[BaseException] = []
    completed: list[bool] = []
    serial_calls: list[bool] = []
    dialog_calls: list[str] = []
    allow_reads = Event()
    replay_read = CsvReplayAdapter._read_measurement
    application_factory = app_module.DashboardApplication
    widget_factory = app_module.create_dashboard_workflow_widgets
    import_factory = app_module.ImportPage
    report_factory = app_module.ReportActions
    deadline = monotonic() + 25
    phase = -1

    def gated_read(adapter: Any, channel: str) -> Any:
        assert allow_reads.wait(5), "Test did not release the bounded replay read gate"
        return replay_read(adapter, channel)

    def forbidden_serial(*_args: Any, **_kwargs: Any) -> Any:
        serial_calls.append(True)
        raise AssertionError("CSV imports must not access a serial device")

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

    def choose(_root: Any, mode: str) -> str:
        dialog_calls.append(mode)
        return str(
            {
                "source": source_path,
                "load_mapping": mapping_path,
                "save_mapping": mapping_path,
                "output": package_path,
            }[mode]
        )

    def construct_import(*args: Any, **kwargs: Any) -> Any:
        page = import_factory(*args, **kwargs)
        root = args[0]
        root.tk.call("tk", "scaling", 1.0)
        root.geometry("1040x760")

        def visible_buttons() -> None:
            root.update_idletasks()
            assert page.canvas is not None
            page.canvas.yview_moveto(1)
            root.update_idletasks()
            assert page.raw_table.winfo_width() <= page.canvas.winfo_width()
            viewport = (
                page.canvas.winfo_rootx(),
                page.canvas.winfo_rooty(),
                page.canvas.winfo_rootx() + page.canvas.winfo_width(),
                page.canvas.winfo_rooty() + page.canvas.winfo_height(),
            )
            for button in (
                page.preview_button,
                page.save_button,
                page.publish_button,
                page.load_button,
            ):
                rectangle = (
                    button.winfo_rootx(),
                    button.winfo_rooty(),
                    button.winfo_rootx() + button.winfo_width(),
                    button.winfo_rooty() + button.winfo_height(),
                )
                assert button.winfo_viewable()
                assert (
                    viewport[0] <= rectangle[0] < rectangle[2] <= viewport[2]
                    and viewport[1] <= rectangle[1] < rectangle[3] <= viewport[3]
                ), (button.cget("text"), rectangle, viewport)

        def advance() -> None:
            nonlocal phase
            try:
                assert monotonic() < deadline, "CSV import-to-report UI timed out"
                widgets = captured["widgets"]
                application = captured["application"]
                reports = captured["reports"]
                if phase == -1:
                    root.deiconify()
                    widgets.notebook.select(page.tab)
                    phase = 0
                elif phase == 0:
                    root.deiconify()
                    widgets.notebook.select(page.tab)
                    root.update_idletasks()
                    assert page.canvas is not None
                    assert page.origin_entry.instate(("disabled",))
                    page.controls["select_source"].invoke()
                    assert page.source is not None, page.status.get()
                    assert page.source.raw_bytes == raw_bytes
                    assert len(page.source.columns) == 64
                    assert len(page.raw_table.get_children()) == 5
                    root.update_idletasks()
                    assert page.raw_table.winfo_width() <= page.canvas.winfo_width(), (
                        page.raw_table.winfo_width(),
                        page.canvas.winfo_width(),
                    )
                    page.raw_table.xview_moveto(1)
                    assert page.raw_table.xview()[0] > 0
                    page.raw_table.xview_moveto(0)
                    source_hash = hashlib.sha256(raw_bytes).hexdigest()
                    assert source_hash in page.snapshot.get()
                    for key, value in {
                        "name": "External voltage check",
                        "time_column": "Time",
                        "input_column": "Input",
                        "input_unit": "V",
                        "output_column": "Output",
                        "output_unit": "mV",
                    }.items():
                        page.variables[key].set(value)
                    page.preview_button.invoke()
                    assert page.preview is not None, page.status.get()
                    assert page.has_unsaved_work
                    # Invalidation happens immediately on a real Tk variable trace.
                    page.variables["minimum_mv"].set("-10")
                    assert page.preview is None
                    assert page.publish_button.instate(("disabled",))
                    assert page.has_unsaved_work
                    page.variables["minimum_mv"].set("0")
                    page.preview_button.invoke()
                    assert page.preview is not None
                    page.save_button.invoke()
                    assert mapping_path.is_file()
                    page.controls["load_mapping"].invoke()
                    assert page.preview is None
                    assert page.variables["input_column"].get() == "Input"
                    page.preview_button.invoke()
                    assert page.preview is not None
                    preview = page.preview
                    source_path.write_text(
                        "changed after source capture", encoding="utf-8"
                    )
                    # The wheel must reach this new tab rather than a hidden page.
                    page.canvas.yview_moveto(0)
                    root.update_idletasks()
                    assert page.canvas._avs_vertical_overflow, (
                        page.canvas.winfo_width(),
                        page.canvas.winfo_height(),
                        page.canvas.bbox("all"),
                        root.winfo_width(),
                        root.winfo_height(),
                    )
                    page.controls["name"].event_generate("<MouseWheel>", delta=-120)
                    root.update_idletasks()
                    assert page.canvas.yview()[0] > 0
                    for scaling in (1.0, 1.5):
                        root.tk.call("tk", "scaling", scaling)
                        for name in PALETTES:
                            state = application.dashboard_state
                            root._avs_theme_value.set(name)
                            root._avs_theme_select.event_generate(
                                "<<ComboboxSelected>>"
                            )
                            root.update_idletasks()
                            assert application.dashboard_state is state
                            assert page.preview is preview
                            assert widgets.notebook.select() == str(page.tab)
                            assert page.variables["output_unit"].get() == "mV"
                            visible_buttons()
                    page.publish_button.invoke()
                    publication = page.publication
                    assert publication is not None, page.status.get()
                    assert not page.has_unsaved_work
                    assert publication.output_directory == package_path.resolve()
                    assert (package_path / "source.csv").read_bytes() == raw_bytes
                    verify_voltage_import(package_path)
                    captured["package_bytes"] = {
                        path.name: path.read_bytes() for path in package_path.iterdir()
                    }
                    captured["configuration"] = publication.configuration
                    assert (
                        publication.configuration.job_type is ProductJobType.DC_ANALYSIS
                    )
                    assert page.load_button.instate(("!disabled",))
                    assert (
                        not application.dashboard_state.progress.worker_state.is_active
                    )
                    if preview_hook is not None:
                        preview_hook(root, page)
                    page.load_button.invoke()
                    assert widgets.notebook.select() == str(widgets.workflow_page)
                    assert (
                        application.wizard_state.step
                        is DashboardWizardStep.CONFIGURATION
                    )
                    assert (
                        widgets.form.snapshot().to_product_configuration()
                        == publication.configuration
                    )
                    assert widgets.run_button.instate(("disabled",))
                    widgets.review_button.invoke()
                    assert application.wizard_state.step is DashboardWizardStep.REVIEW
                    assert (
                        "Replay file validated before Run" in widgets.review_value.get()
                    )
                    assert (
                        "Hardware performance validation: NOT CLAIMED"
                        in widgets.review_value.get()
                    )
                    widgets.run_button.invoke()
                    page.render()
                    assert page.controls["select_source"].instate(("disabled",))
                    before = tuple(dialog_calls)
                    page.select_source()
                    assert tuple(dialog_calls) == before
                    allow_reads.set()
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
                    assert result.evidence_source is EvidenceSource.CSV_REPLAY
                    assert result.outcome is not None
                    assert application.has_unsaved_result
                    assert reports.save_button.instate(("!disabled",))
                    reports.save_button.invoke()
                    report = application.report_publication
                    assert report is not None
                    assert not application.has_unsaved_result
                    assert report.output_directory == report_path.resolve()
                    bundle = load_result_export_json(report_path / "result.json")
                    view = build_human_report_view(bundle)
                    assert view.evidence_source is EvidenceSource.CSV_REPLAY
                    assert view.outcome is result.outcome
                    manifest = json.loads(
                        (report_path / "manifest.json").read_text(encoding="utf-8")
                    )
                    assert (
                        manifest["canonical_result_sha256"]
                        == view.canonical_result_sha256
                    )
                    assert manifest["hardware_claim"] == "NO_NEW_HARDWARE_VALIDATION"
                    assert {path.name for path in report_path.iterdir()} == {
                        "report.html",
                        "report.md",
                        "report.txt",
                        "chart.svg",
                        "result.json",
                        "manifest.json",
                    }
                    for artifact in report.artifacts:
                        assert (
                            hashlib.sha256(
                                (report_path / artifact.name).read_bytes()
                            ).hexdigest()
                            == artifact.sha256
                        )
                    widgets.notebook.select(page.tab)
                    page.variables["name"].set("Next mapping draft")
                    assert page.preview is None
                    assert page.publication is None
                    assert page.load_button.instate(("disabled",))
                    assert captured["package_bytes"] == {
                        path.name: path.read_bytes() for path in package_path.iterdir()
                    }
                    assert (
                        widgets.form.snapshot().to_product_configuration()
                        == captured["configuration"]
                    )
                    assert not serial_calls
                    assert root.winfo_width() == 1040 and root.winfo_height() == 760
                    assert not page.has_unsaved_work
                    completed.append(True)
                    root.after(
                        0, lambda: root.tk.call(root.protocol("WM_DELETE_WINDOW"))
                    )
                    return
            except BaseException as error:  # noqa: BLE001 - callback failures are rethrown below
                allow_reads.set()
                errors.append(error)
                traceback.print_exc()
                root.quit()
                return
            root.after(20, advance)

        root.after(20, advance)
        return page

    with ExitStack() as patches:
        patches.enter_context(
            patch.object(CsvReplayAdapter, "_read_measurement", gated_read)
        )
        for name, replacement in {
            "DashboardApplication": construct_application,
            "create_dashboard_workflow_widgets": construct_widgets,
            "ImportPage": construct_import,
            "ReportActions": construct_reports,
            "_choose_import_path": choose,
            "_choose_report_directory": lambda *_args: str(report_path),
            "_confirm_replace_setup": lambda *_args, **_kwargs: True,
        }.items():
            patches.enter_context(patch.object(app_module, name, replacement))
        patches.enter_context(
            patch.object(widget_module, "_windows_high_contrast_enabled", lambda: False)
        )
        session = app_module.launch_dashboard(withdraw=True, poll_interval_ms=10)
    if errors:
        raise errors[0]
    assert completed == [True]
    assert session.closed_safely


if __name__ == "__main__":
    _exercise_import_loop(Path(sys.argv[1]))
    print("IMPORT_WORKFLOW_PASS")
