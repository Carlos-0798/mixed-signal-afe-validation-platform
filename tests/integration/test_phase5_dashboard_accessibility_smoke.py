"""Real Tk keyboard-focus and display-scaling smoke for Phase 5 Step 7."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from analog_validation_app.dashboard.widgets import create_dashboard_workflow_widgets


def _callback(*_args: object, **_kwargs: object) -> None:
    return None


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Tk product target")
@pytest.mark.parametrize(
    "appearance", ["Workbench", "Daylight", "Midnight", "System contrast"]
)
@pytest.mark.parametrize("scaling", [1.0, 1.25, 1.5, 1.75, 2.0])
def test_real_tk_workflow_has_text_and_keyboard_targets_at_common_scaling(
    scaling: float,
    appearance: str,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            str(scaling),
            appearance,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip() == "DASHBOARD_ACCESSIBILITY_PASS"
    assert not completed.stderr


def _exercise_dashboard_accessibility(scaling: float, appearance: str) -> None:
    import tkinter as tk
    from tkinter import ttk

    import analog_validation_app.dashboard.widgets as widget_module
    from analog_validation_app import ProductSourceMode
    from analog_validation_app.dashboard.application import DashboardApplication
    from analog_validation_app.dashboard.themes import PALETTES, WORKBENCH
    from analog_validation_app.dashboard.wizard import (
        DashboardWizardState,
        DashboardWizardStep,
    )

    high_contrast = appearance == "System contrast"
    widget_module._windows_high_contrast_enabled = lambda: high_contrast

    root: Any = tk.Tk()
    application: DashboardApplication | None = None
    try:
        root.withdraw()
        root.tk.call("tk", "scaling", scaling)
        root.geometry("1040x760")
        widgets = create_dashboard_workflow_widgets(
            root,
            tk,
            ttk,
            on_source=_callback,
            on_profile=_callback,
            on_job=_callback,
            on_back=_callback,
            on_next=_callback,
            on_review=_callback,
            on_run=_callback,
            on_cancel=_callback,
            on_discover=_callback,
            on_choose_export_path=_callback,
            on_export=_callback,
            on_modify=_callback,
            on_repeat=_callback,
            on_new_test=_callback,
            on_close=_callback,
        )
        application = DashboardApplication()
        widgets.render(application.dashboard_state, application.wizard_state)
        root.deiconify()
        root.update_idletasks()
        root.update()
        selector = root._avs_theme_select
        if not high_contrast:
            root._avs_theme_value.set(appearance)
            selector.event_generate("<<ComboboxSelected>>")
            root.update()
        assert root._avs_theme_value.get() == appearance
        assert selector.instate(("disabled",)) == high_contrast
        palette = PALETTES.get(appearance, WORKBENCH)
        style = ttk.Style(root)
        expected_background = "SystemWindow" if high_contrast else palette.background
        expected_surface = "SystemWindow" if high_contrast else palette.surface
        expected_accent = "SystemHighlight" if high_contrast else palette.accent
        assert style.lookup("App.TFrame", "background") == expected_background
        assert style.lookup("Card.TLabelframe", "background") == expected_surface
        assert style.lookup("Modern.Treeview", "rowheight") == 30
        assert style.lookup("Accent.Horizontal.TProgressbar", "background") == (
            expected_accent
        )
        assert root.minsize() == (1040, 760)
        assert root.winfo_width() == 1040
        assert root.winfo_height() == 760
        assert widgets.source_display_value.get() == "Simulator — synthetic data"
        assert widgets.job_display_value.get() == "Read samples"
        accessibility = widgets.accessibility.capability
        assert accessibility.tk_patchlevel == str(root.tk.call("info", "patchlevel"))
        if accessibility.metadata_api_available:
            assert accessibility.reason == "tk-accessible-available"
            assert accessibility.screen_reader_active in (False, True)
        else:
            assert accessibility.reason == "tk-accessible-command-unavailable"
            assert accessibility.screen_reader_active is None

        def descendants(widget: Any) -> tuple[Any, ...]:
            children = tuple(widget.winfo_children())
            return children + tuple(
                nested for child in children for nested in descendants(child)
            )

        visible_text: set[str] = set()
        for widget in descendants(root):
            try:
                visible_text.add(str(widget.cget("text")))
            except tk.TclError:
                pass
        assert {
            "VALIDATION WORKSPACE",
            "LOCAL / OFFLINE",
            "READ-ONLY DEFAULT",
            "EVIDENCE LABELED",
        } <= visible_text
        root_left = root.winfo_rootx()
        root_right = root_left + root.winfo_width()
        clipped_controls = {
            name
            for name, widget in (
                ("appearance", selector),
                ("source", widgets.source_select),
                ("profile", widgets.profile_select),
                ("job", widgets.job_select),
                ("primary channel", widgets.primary_channel_input),
                ("previous", widgets.back_button),
                ("continue", widgets.next_button),
                ("validate", widgets.review_button),
                ("run", widgets.run_button),
                ("discover", widgets.discover_button),
            )
            if not (
                root_left <= widget.winfo_rootx()
                and widget.winfo_rootx() + widget.winfo_width() <= root_right
            )
        }
        assert not clipped_controls, clipped_controls
        readable_widths = {
            name: widget.winfo_width()
            for name, widget in (
                ("source", widgets.source_select),
                ("profile", widgets.profile_select),
                ("job", widgets.job_select),
                ("primary channel", widgets.primary_channel_input),
            )
            if widget.winfo_width() < 240
        }
        assert not readable_widths, readable_widths
        focus_targets: tuple[Any, ...] = (
            selector,
            widgets.source_select,
            widgets.profile_select,
            widgets.job_select,
            widgets.replay_browse_button,
            widgets.serial_port_select,
            widgets.back_button,
            widgets.next_button,
            widgets.review_button,
            widgets.run_button,
            widgets.discover_button,
            widgets.export_browse_button,
            widgets.export_button,
            widgets.modify_button,
            widgets.repeat_button,
            widgets.new_test_button,
            widgets.finish_button,
            widgets.result_widgets.cancel_button,
            widgets.result_widgets.plot_table,
        )

        assert all(
            root.tk.getboolean(widget.cget("takefocus")) for widget in focus_targets
        )
        assert all(root.tk.call("tk_focusNext", widget._w) for widget in focus_targets)
        assert root.winfo_reqwidth() > 0
        assert root.winfo_reqheight() > 0

        assert application.select_source(ProductSourceMode.CSV_REPLAY)
        assert application.next()
        assert application.next()
        widgets.render(application.dashboard_state, application.wizard_state)
        root.update_idletasks()
        assert widgets.section_frames["replay_source"].winfo_ismapped()
        assert not widgets.section_frames["serial_source"].winfo_ismapped()
        assert widgets.source_display_value.get() == "CSV Replay — local file"
        assert root_left <= widgets.replay_browse_button.winfo_rootx()
        assert (
            widgets.replay_browse_button.winfo_rootx()
            + widgets.replay_browse_button.winfo_width()
            <= root_right
        )
        assert widgets.section_frames["field_guide"].winfo_ismapped()
        assert "CSV_REPLAY" in widgets.field_help_value.get()
        assert "Run stays unavailable" in widgets.action_guidance_value.get()
        assert application.prepare_review(application.wizard_state.draft) is False
        assert application.issue_field_id == "replay_path"
        widgets.issue_field_id = application.issue_field_id
        widgets.render(application.dashboard_state, application.wizard_state)
        root.update_idletasks()
        root.update()
        replay_control = widgets.field_controls["replay_path"][0]
        workflow_canvas = widgets.scroll_canvases[0]
        assert root.focus_get() == replay_control
        assert replay_control.cget("style") == "Invalid.TEntry"
        assert "Replay CSV path" in widgets.issue_value.get()
        assert workflow_canvas.winfo_rooty() <= replay_control.winfo_rooty()
        assert (
            replay_control.winfo_rooty() + replay_control.winfo_height()
            <= workflow_canvas.winfo_rooty() + workflow_canvas.winfo_height()
        )
        # A theme change must not clear a validation error, draft, focus or scroll.
        for choice in PALETTES:
            if high_contrast:
                continue
            before = (application.dashboard_state, application.wizard_state)
            position = workflow_canvas.yview()
            replay_control.delete(0, "end")
            replay_control.insert(0, "unsaved-input.csv")
            root._avs_theme_value.set(choice)
            selector.event_generate("<<ComboboxSelected>>")
            root.update()
            assert before == (application.dashboard_state, application.wizard_state)
            assert replay_control.get() == "unsaved-input.csv"
            assert replay_control.cget("style") == "Invalid.TEntry"
            assert root.focus_get() == replay_control
            assert workflow_canvas.yview() == position
            assert workflow_canvas.cget("background") == PALETTES[choice].background
            assert (
                style.lookup("Invalid.TEntry", "bordercolor", ("focus",))
                == PALETTES[choice].danger
            )
            for name in ("Primary.TButton", "TCombobox"):
                assert (
                    style.lookup(name, "foreground", ("disabled", "active", "readonly"))
                    == PALETTES[choice].disabled_text
                )
            popdown = root.tk.call("ttk::combobox::PopdownWindow", str(selector))
            assert (
                root.tk.call(f"{popdown}.f.l", "cget", "-background")
                == PALETTES[choice].raised
            )

        assert application.back()
        widgets.issue_field_id = application.issue_field_id
        widgets.render(application.dashboard_state, application.wizard_state)
        root.update_idletasks()
        assert replay_control.cget("style") == "TEntry"

        result_state = DashboardWizardState(
            revision=application.wizard_state.revision + 1,
            step=DashboardWizardStep.RESULT,
            draft=application.wizard_state.draft,
        )
        widgets.render(application.dashboard_state, result_state)
        root.update_idletasks()
        root.update()
        assert "NO ENGINEERING DECISION" in widgets.result_widgets.decision_value.get()
        assert "NO_NEW_HARDWARE_VALIDATION" in (
            widgets.result_widgets.decision_value.get()
        )
        result_targets = (
            widgets.export_path_input,
            widgets.export_browse_button,
            widgets.export_format_select,
            widgets.export_button,
            widgets.coefficient_path_input,
            widgets.coefficient_browse_save_button,
            widgets.coefficient_save_button,
            widgets.coefficient_browse_load_button,
            widgets.coefficient_load_button,
            widgets.modify_button,
            widgets.repeat_button,
            widgets.new_test_button,
            widgets.finish_button,
        )
        clipped_result_controls = {
            str(widget): (widget.winfo_rootx(), widget.winfo_width())
            for widget in result_targets
            if not (
                root_left <= widget.winfo_rootx()
                and widget.winfo_rootx() + widget.winfo_width() <= root_right
            )
        }
        assert not clipped_result_controls, clipped_result_controls
        assert min(widget.winfo_width() for widget in result_targets) >= 180
    finally:
        if application is not None:
            application.request_close()
        root.destroy()


if __name__ == "__main__":
    _exercise_dashboard_accessibility(float(sys.argv[1]), sys.argv[2])
    print("DASHBOARD_ACCESSIBILITY_PASS")
