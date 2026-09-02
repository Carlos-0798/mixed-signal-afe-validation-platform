"""Real Tk keyboard-focus and display-scaling smoke for Phase 5 Step 7."""

from __future__ import annotations

import sys
from typing import Any

import pytest

from analog_validation_app.dashboard.widgets import create_dashboard_workflow_widgets


def _callback(*_args: object, **_kwargs: object) -> None:
    return None


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Tk product target")
@pytest.mark.parametrize("scaling", [1.0, 1.5, 2.0])
def test_real_tk_workflow_has_text_and_keyboard_targets_at_common_scaling(
    scaling: float,
) -> None:
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError as error:
        pytest.skip(f"local Tk support unavailable: {error}")
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"local Tk display unavailable: {error}")
    try:
        root.withdraw()
        root.tk.call("tk", "scaling", scaling)
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
            on_export=_callback,
            on_modify=_callback,
            on_repeat=_callback,
            on_new_test=_callback,
            on_close=_callback,
        )
        root.update_idletasks()
        focus_targets: tuple[Any, ...] = (
            widgets.source_select,
            widgets.profile_select,
            widgets.job_select,
            widgets.serial_port_select,
            widgets.back_button,
            widgets.next_button,
            widgets.review_button,
            widgets.run_button,
            widgets.discover_button,
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
    finally:
        root.destroy()
