"""Real-window theme changes during a Simulator run and project editing."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep
from typing import Any

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Tk product target")
def test_theme_changes_preserve_running_job_and_project_selection(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip() == "THEME_SWITCHING_PASS"
    assert not completed.stderr


def _exercise(path: Path) -> None:
    import tkinter as tk
    from tkinter import ttk

    from analog_validation_app import ProductJobType
    from analog_validation_app.dashboard import widgets as widget_module
    from analog_validation_app.dashboard.application import DashboardApplication
    from analog_validation_app.dashboard.project_widgets import ProjectPage
    from analog_validation_app.dashboard.project_workspace import ProjectWorkspace
    from analog_validation_app.dashboard.themes import PALETTES

    widget_module._windows_high_contrast_enabled = lambda: False
    root: Any = tk.Tk()
    root.withdraw()
    application = DashboardApplication()
    projects = ProjectWorkspace(
        lambda: application.dashboard_state.progress.worker_state.is_active
    )
    try:

        def unexpected(*_args: object) -> None:
            raise AssertionError("Theme change invoked a business action")

        callbacks = {
            f"on_{name}": unexpected
            for name in (
                "source",
                "profile",
                "job",
                "back",
                "next",
                "review",
                "run",
                "cancel",
                "discover",
                "choose_export_path",
                "export",
                "modify",
                "repeat",
                "new_test",
                "close",
            )
        }
        widgets = widget_module.create_dashboard_workflow_widgets(
            root, tk, ttk, **callbacks
        )
        page = ProjectPage(
            root, tk, ttk, widgets.notebook, projects, unexpected, widgets.form.snapshot
        )
        projects.create(
            str(path / "project.json"), "appearance-check", "Theme acceptance"
        )
        page.render()
        rows = page.presets.get_children()
        assert len(rows) == 6
        page.presets.selection_set(rows[:2])
        page.destination.set("unsaved-output-directory")
        widgets.notebook.select(page.tab)
        root.deiconify()
        root.update()
        selector = root._avs_theme_select

        def change(name: str) -> None:
            root._avs_theme_value.set(name)
            selector.event_generate("<<ComboboxSelected>>")
            root.update()

        for name in PALETTES:
            before = projects.project
            change(name)
            assert projects.project is before
            assert page.presets.selection() == rows[:2]
            assert page.destination.get() == "unsaved-output-directory"
            assert widgets.notebook.select() == str(page.tab)
            assert (
                ttk.Style(root).lookup("Modern.Treeview", "fieldbackground")
                == PALETTES[name].surface
            )
        assert application.next()
        assert application.select_job(ProductJobType.LIVE_MONITOR)
        assert application.next()
        draft = replace(
            application.wizard_state.draft,
            sample_count="100",
            monitor_sample_interval_seconds="0.03",
        )
        assert application.prepare_review(draft)
        assert application.run()
        deadline = monotonic() + 10
        while not application.dashboard_state.live.points:
            application.poll()
            assert monotonic() < deadline
            sleep(0.01)
        widgets.render(application.dashboard_state, application.wizard_state)
        root.update()
        prepared = application._prepared
        canvas = widgets.result_widgets.live_canvas
        assert canvas.find_all()
        for name in PALETTES:
            state = application.dashboard_state
            points = state.live.points
            change(name)
            assert application.dashboard_state is state
            assert application._prepared is prepared
            assert application.dashboard_state.live.points == points
            assert canvas.cget("background") == PALETTES[name].surface
            assert canvas.itemcget(canvas.find_all()[1], "fill") == PALETTES[name].muted
        while application.dashboard_state.progress.worker_state.is_active:
            application.poll()
            widgets.render(application.dashboard_state, application.wizard_state)
            root.update()
            assert monotonic() < deadline
            sleep(0.01)
        assert application.dashboard_state.progress.worker_state.value == "SUCCEEDED"
        assert "SYNTHETIC" in application.dashboard_state.source.evidence_text
        final_state = application.dashboard_state
        for name in PALETTES:
            change(name)
            assert application.dashboard_state is final_state
    finally:
        application.request_close()
        root.destroy()


if __name__ == "__main__":
    _exercise(Path(sys.argv[1]))
    print("THEME_SWITCHING_PASS")
