"""Actual Windows Tk controls drive the offline project workflow without devices."""

from __future__ import annotations

import subprocess
import sys
import traceback
from pathlib import Path
from threading import Event
from time import monotonic
from typing import Any

import pytest

from analog_validation_app.dashboard import app as app_module
from analog_validation_app.dashboard import project_workspace as workspace_module
from analog_validation_app.projects import ValidationBatchStatus


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Tk product target")
@pytest.mark.parametrize("scaling", [1.0, 1.25, 1.5, 1.75, 2.0])
def test_real_tk_project_batch_history_comparison_and_close(
    tmp_path: Path, scaling: float
) -> None:
    # Each scale owns exactly one Tcl interpreter in a fresh process. A missing
    # Tk runtime, callback assertion, crash, or timeout is a failure, never a skip.
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), str(tmp_path), str(scaling)],
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip() == "PROJECT_UI_ACCEPTANCE_PASS"
    assert not completed.stderr, completed.stderr


def _exercise_project_workflow(tmp_path: Path, scaling: float) -> None:
    errors: list[BaseException] = []
    result: list[str] = []
    factory = app_module.ProjectPage
    publish = workspace_module.publish_validation_project_run
    cancel_gate_entered = Event()

    def descendants(widget: Any) -> tuple[Any, ...]:
        children = tuple(widget.winfo_children())
        return children + tuple(
            nested for child in children for nested in descendants(child)
        )

    def cancellable_publish(*args: Any, **kwargs: Any) -> Any:
        if args[2] == "first":
            cancel_gate_entered.set()
            token = kwargs["cancellation"]
            deadline = monotonic() + 5
            while not token.is_cancellation_requested:
                assert monotonic() < deadline, "Dashboard did not forward cancellation"
        return publish(*args, **kwargs)

    def construct(*args: Any) -> Any:
        page = factory(*args)
        root = args[0]
        root.tk.call("tk", "scaling", scaling)
        root.geometry("1040x760")
        args[3].select(page.tab)
        deadline = monotonic() + 15
        phase = 0

        def advance() -> None:
            nonlocal phase
            try:
                assert monotonic() < deadline, "Project UI workflow timed out"
                if phase == 0:
                    assert "Create starter" in page.project_guide.get()
                    assert "SYNTHETIC" in page.setup_capture_guide.get()
                    assert page.save_button.instate(("disabled",))
                    assert page.add_preset_button.instate(("disabled",))
                    assert page.review_button.instate(("disabled",))
                    assert page.run_button.instate(("disabled",))
                    assert page.compare_button.instate(("disabled",))
                    page.act(page.create)
                    page.presets.selection_set(("dc-default", "frequency-default"))
                    page.destination.set(str(tmp_path / "first"))
                    page.run_id.set("first")
                    page.render()
                    assert page.review_button.instate(("!disabled",))
                    assert "Review selected batch" in page.project_guide.get()
                    page.act(page.review)
                    assert page.run_button.instate(("!disabled",))
                    assert "Ready to run" in page.project_guide.get()
                    assert "FROZEN REVIEW" in page.batch_review_guide.get()
                    review_rows = page.batch_review.get_children()
                    assert len(review_rows) == 2
                    review_values = tuple(
                        page.batch_review.item(row, "values") for row in review_rows
                    )
                    assert tuple(row[1] for row in review_values) == (
                        "dc-default",
                        "frequency-default",
                    )
                    assert {row[5] for row in review_values} == {"SYNTHETIC"}
                    page.act(page.run)
                    assert not page.batch_review.get_children()
                    assert page.workspace.busy
                    assert cancel_gate_entered.wait(5)
                    page.act(page.request_cancel)
                    assert page.workspace.cancellation_requested
                    assert page.cancel_button.instate(("disabled",))
                    phase = 1
                elif phase == 1 and not page.workspace.busy:
                    assert len(page.history.get_children()) == 1
                    cancelled = next(iter(page.workspace.history.values()))
                    assert cancelled.batch_status is ValidationBatchStatus.CANCELLED
                    assert cancelled.records == ()
                    assert cancelled.not_started_preset_ids == (
                        "dc-default",
                        "frequency-default",
                    )
                    assert page.run_button.instate(("disabled",))
                    assert "one verified run" in page.comparison_guide.get()
                    page.presets.selection_set(("dc-default",))
                    page.destination.set(str(tmp_path / "second"))
                    page.run_id.set("second")
                    page.act(page.review)
                    page.act(page.run)
                    assert page.workspace.busy
                    phase = 2
                elif phase == 2 and not page.workspace.busy:
                    root.deiconify()
                    args[3].select(page.tab)
                    page.history.master.master.master.master.yview_moveto(1.0)
                    phase = 3
                elif phase == 3:
                    assert root.winfo_width() == 1040
                    root_left = root.winfo_rootx()
                    root_right = root_left + root.winfo_width()
                    clipped_buttons = {
                        str(widget.cget("text")): (
                            widget.winfo_rootx() - root_left,
                            widget.winfo_rootx() + widget.winfo_width() - root_left,
                        )
                        for widget in descendants(page.tab)
                        if widget.winfo_class() == "TButton"
                        and not (
                            root_left <= widget.winfo_rootx()
                            and widget.winfo_rootx() + widget.winfo_width()
                            <= root_right
                        )
                    }
                    assert not clipped_buttons, clipped_buttons
                    rows = page.history.get_children()
                    assert len(rows) == 2
                    values = tuple(page.history.item(row, "values") for row in rows)
                    assert values[0][2] == ValidationBatchStatus.CANCELLED.value
                    assert values[1][2] == ValidationBatchStatus.PARTIAL.value
                    # Generate real Tk key events, not selection_set as a proxy
                    # for keyboard operation. Parent-process tests stay headless.
                    root.focus_force()
                    page.history.focus_force()
                    root.update()
                    assert root.focus_get() == page.history, (
                        root.focus_get(),
                        page.history.winfo_viewable(),
                    )
                    page.history.focus(rows[0])
                    page.history.selection_set((rows[0],))
                    page.history.event_generate("<Shift-Down>")
                    assert page.history.selection() == rows, (
                        page.history.selection(),
                        rows,
                        root.focus_get(),
                        page.history.winfo_ismapped(),
                        page.history.bind("<Shift-Down>"),
                    )
                    page.history.event_generate("<Shift-Up>")
                    assert page.history.selection() == (rows[0],)
                    page.history.event_generate("<Control-a>")
                    assert page.history.selection() == rows
                    page.render()
                    assert page.compare_button.instate(("!disabled",))
                    page.act(page.compare)
                    assert page.workspace.comparison is not None
                    assert page.workspace.comparison.changed_entries == 1
                    assert page.comparison.get_children()
                    guidance = page.comparison_guide.get()
                    assert "Project identity: validation-project" in guidance
                    assert "candidate-only dc-default" in guidance
                    assert "SYNTHETIC" in guidance
                    assert "candidate - baseline" in guidance
                    assert all(
                        root.tk.getboolean(widget.cget("takefocus"))
                        for widget in page.controls
                    )
                    assert page.tab.winfo_reqwidth() > 0
                    assert all(Path(path).is_file() for path in rows)
                    result.append("completed")
                    root.event_generate("<<ProjectWorkflowComplete>>")
                    root.after(
                        0, lambda: root.tk.call(root.protocol("WM_DELETE_WINDOW"))
                    )
                    return
            except BaseException as error:  # noqa: BLE001 - propagate callback assertions after mainloop
                errors.append(error)
                traceback.print_exc()
                root.quit()
                return
            root.after(20, advance)

        root.after(20, advance)
        return page

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(app_module, "ProjectPage", construct)
        patch.setattr(
            workspace_module, "publish_validation_project_run", cancellable_publish
        )
        patch.setattr(
            app_module,
            "_choose_project_path",
            lambda *args: str(tmp_path / "project.json"),
        )
        session = app_module.launch_dashboard(withdraw=True)
    if errors:
        raise errors[0]
    assert result == ["completed"]
    assert session.closed_safely


if __name__ == "__main__":
    _exercise_project_workflow(Path(sys.argv[1]), float(sys.argv[2]))
    print("PROJECT_UI_ACCEPTANCE_PASS")
