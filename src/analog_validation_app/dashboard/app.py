"""Lazy local Tk Dashboard lifecycle; importing this module does not import Tk."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from ..errors import (
    ProductDashboardUnavailableError,
    ProductRequestError,
    ProductWorkerTimeoutError,
)
from ..models import ProductSourceMode, ProductWorkerState
from .application import DashboardApplication
from .controller import DashboardWorkerPort
from .state import DASHBOARD_HARDWARE_CLAIM
from .widgets import create_dashboard_workflow_widgets

DASHBOARD_SESSION_SCHEMA_VERSION = "dashboard-session.v1"
DEFAULT_DASHBOARD_POLL_MS = 50
MAX_DASHBOARD_POLL_MS = 1_000
MAX_DASHBOARD_SMOKE_MS = 60_000

TkLoader = Callable[[], tuple[object, object]]
DashboardWorkerFactory = Callable[[], DashboardWorkerPort]
SavePathDialog = Callable[..., object]
DiscardConfirmationDialog = Callable[..., object]


@dataclass(frozen=True, slots=True)
class DashboardSessionResult:
    """Summary returned only after the local window closes safely."""

    source_mode: ProductSourceMode
    profile_identity: str
    worker_state: ProductWorkerState
    closed_safely: bool
    hardware_claim: str = DASHBOARD_HARDWARE_CLAIM
    schema_version: str = DASHBOARD_SESSION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.source_mode, ProductSourceMode):
            raise ProductRequestError("source_mode must be a ProductSourceMode")
        if (
            not isinstance(self.profile_identity, str)
            or not self.profile_identity
            or self.profile_identity != self.profile_identity.strip()
            or not self.profile_identity.isprintable()
        ):
            raise ProductRequestError(
                "profile_identity must be a non-empty printable stripped string"
            )
        if not isinstance(self.worker_state, ProductWorkerState):
            raise ProductRequestError("worker_state must be a ProductWorkerState")
        if self.closed_safely is not True:
            raise ProductRequestError("DashboardSessionResult requires safe closure")
        if self.hardware_claim != DASHBOARD_HARDWARE_CLAIM:
            raise ProductRequestError(
                f"hardware_claim must remain {DASHBOARD_HARDWARE_CLAIM}"
            )
        if self.schema_version != DASHBOARD_SESSION_SCHEMA_VERSION:
            raise ProductRequestError(
                f"unsupported Dashboard session schema: {self.schema_version}"
            )


def _load_tk() -> tuple[object, object]:  # pragma: no cover - platform smoke gate
    import tkinter as tk
    from tkinter import ttk

    return tk, ttk


def _bounded_integer(name: str, value: object, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProductRequestError(f"{name} must be an integer")
    if value <= 0 or value > maximum:
        raise ProductRequestError(f"{name} must satisfy 1 <= value <= {maximum}")
    return value


def _choose_export_destination(
    parent: object,
    format_name: str,
    *,
    dialog: SavePathDialog | None = None,
) -> str:
    """Choose a path without creating or replacing a result file."""

    if format_name not in {"json", "csv"}:
        raise ProductRequestError("Dashboard export format must be json or csv")
    selected_dialog: SavePathDialog
    if dialog is None:  # pragma: no cover - exercised by the real Windows Tk gate
        from tkinter import filedialog

        selected_dialog = cast(SavePathDialog, filedialog.asksaveasfilename)
    else:
        selected_dialog = dialog
    selected = selected_dialog(
        parent=parent,
        title="Choose a new analysis result file",
        defaultextension=f".{format_name}",
        initialfile=f"analog-validation-result.{format_name}",
        filetypes=((f"{format_name.upper()} analysis result", f"*.{format_name}"),),
        confirmoverwrite=False,
    )
    if not isinstance(selected, str):
        raise ProductRequestError("Dashboard save dialog must return a path string")
    return selected


def _choose_coefficient_path(
    parent: object,
    mode: str,
    *,
    dialog: SavePathDialog | None = None,
) -> str:
    """Choose a coefficient JSON path without opening, creating, or applying it."""

    if mode not in {"save", "load"}:
        raise ProductRequestError("coefficient path mode must be save or load")
    selected_dialog: SavePathDialog
    if dialog is None:  # pragma: no cover - exercised by the real Windows Tk gate
        from tkinter import filedialog

        selected_dialog = cast(
            SavePathDialog,
            filedialog.asksaveasfilename
            if mode == "save"
            else filedialog.askopenfilename,
        )
    else:
        selected_dialog = dialog
    options: dict[str, object] = {
        "parent": parent,
        "title": (
            "Choose a new calibration coefficient file"
            if mode == "save"
            else "Choose an existing calibration coefficient file"
        ),
        "defaultextension": ".json",
        "filetypes": (("Calibration coefficients", "*.json"),),
    }
    if mode == "save":
        options.update(
            {
                "initialfile": "analog-validation-calibration.json",
                "confirmoverwrite": False,
            }
        )
    selected = selected_dialog(**options)
    if not isinstance(selected, str):
        raise ProductRequestError(
            "Dashboard coefficient dialog must return a path string"
        )
    return selected


def _confirm_discard_unsaved_result(
    parent: object,
    action: str,
    *,
    dialog: DiscardConfirmationDialog | None = None,
) -> bool:
    """Ask before an explicit UI action discards the only analysis copy."""

    if (
        not isinstance(action, str)
        or not action
        or action != action.strip()
        or not action.isprintable()
    ):
        raise ProductRequestError("discard action must be printable stripped text")
    selected_dialog: DiscardConfirmationDialog
    if dialog is None:  # pragma: no cover - exercised by the real Windows Tk gate
        from tkinter import messagebox

        selected_dialog = cast(DiscardConfirmationDialog, messagebox.askyesno)
    else:
        selected_dialog = dialog
    confirmed = selected_dialog(
        parent=parent,
        title="Unsaved analysis result",
        message=f"Discard the unsaved analysis result and {action}?",
        detail="Choose No to return to the result page and save it first.",
        icon="warning",
        default="no",
    )
    if not isinstance(confirmed, bool):
        raise ProductRequestError("Dashboard discard confirmation must return a bool")
    return confirmed


def launch_dashboard(
    *,
    tk_loader: TkLoader | None = None,
    worker_factory: DashboardWorkerFactory | None = None,
    poll_interval_ms: int = DEFAULT_DASHBOARD_POLL_MS,
    auto_close_ms: int | None = None,
    withdraw: bool = False,
) -> DashboardSessionResult:
    """Launch the offline shell and return after bounded worker closure."""

    if tk_loader is not None and not callable(tk_loader):
        raise ProductRequestError("tk_loader must be callable or None")
    if worker_factory is not None and not callable(worker_factory):
        raise ProductRequestError("worker_factory must be callable or None")
    poll_ms = _bounded_integer(
        "poll_interval_ms", poll_interval_ms, MAX_DASHBOARD_POLL_MS
    )
    if auto_close_ms is not None:
        auto_close_ms = _bounded_integer(
            "auto_close_ms", auto_close_ms, MAX_DASHBOARD_SMOKE_MS
        )
    if not isinstance(withdraw, bool):
        raise ProductRequestError("withdraw must be boolean")
    loader = tk_loader or _load_tk
    try:
        toolkit = loader()
    except (ImportError, ModuleNotFoundError) as error:
        raise ProductDashboardUnavailableError(
            "the local Python runtime could not import Tkinter"
        ) from error
    if not isinstance(toolkit, tuple) or len(toolkit) != 2:
        raise ProductRequestError("tk_loader must return (tk_module, ttk_module)")
    tk = cast(Any, toolkit[0])
    ttk = cast(Any, toolkit[1])
    try:
        root = tk.Tk()
    except BaseException as error:
        tcl_error = getattr(tk, "TclError", None)
        if isinstance(tcl_error, type) and isinstance(error, tcl_error):
            raise ProductDashboardUnavailableError(
                "Tkinter is installed but no local display could create the Dashboard"
            ) from error
        raise
    initial_hide = getattr(root, "withdraw", None)
    if callable(initial_hide):
        initial_hide()

    try:
        worker = None if worker_factory is None else worker_factory()
        application = DashboardApplication(worker=worker)
    except BaseException:
        root.destroy()
        raise
    closed = False
    widgets: Any = None

    def render() -> None:
        widgets.render(application.dashboard_state, application.wizard_state)

    def cancel_job() -> None:
        application.request_cancel()
        render()

    def select_source(value: str) -> None:
        application.select_source(ProductSourceMode(value))
        render()

    def select_profile(value: str) -> None:
        name, version = value.split("/", maxsplit=1)
        application.select_profile(name, version)
        render()

    def select_job(value: str) -> None:
        from ..models import ProductJobType

        application.select_job(ProductJobType(value))
        render()

    def previous_step() -> None:
        application.back()
        render()

    def next_step() -> None:
        application.next()
        render()

    def review_job(draft: object) -> None:
        from .wizard import DashboardWizardDraft

        if not isinstance(draft, DashboardWizardDraft):
            raise ProductRequestError("Dashboard review requires a wizard draft")
        application.prepare_review(draft)
        render()

    def run_job() -> None:
        application.run()
        render()

    def discover_ports() -> None:
        application.discover_ports()
        render()

    def export_result(path: str, format_name: str) -> None:
        application.export_result(path, format_name)
        render()

    def choose_export_path(format_name: str) -> str:
        return _choose_export_destination(root, format_name)

    def choose_coefficient_path(mode: str) -> str:
        return _choose_coefficient_path(root, mode)

    def save_coefficients(path: str) -> None:
        application.save_calibration_coefficients(path)
        render()

    def load_coefficients(path: str) -> None:
        application.load_calibration_coefficients(path)
        render()

    def pause_live_monitor() -> None:
        application.pause_live_monitor()
        render()

    def resume_live_monitor() -> None:
        application.resume_live_monitor()
        render()

    def change_live_window(seconds: float) -> None:
        application.set_live_time_window(seconds)
        render()

    def discard_is_confirmed(action: str) -> bool:
        return not application.has_unsaved_result or _confirm_discard_unsaved_result(
            root, action
        )

    def modify_setup() -> None:
        if not discard_is_confirmed("modify the setup"):
            return
        application.modify_setup()
        render()

    def review_same_setup() -> None:
        if not discard_is_confirmed("review the same setup again"):
            return
        application.review_same_setup()
        render()

    def start_new_test() -> None:
        if not discard_is_confirmed("start a new test"):
            return
        application.start_new_test()
        render()

    def close_window(*, bypass_unsaved_confirmation: bool = False) -> None:
        nonlocal closed
        if closed:
            return
        if not bypass_unsaved_confirmation and not discard_is_confirmed(
            "close the application"
        ):
            return
        if application.request_close():
            closed = True
            render()
            root.destroy()
        else:
            render()

    def poll_worker() -> None:
        if closed:
            return
        application.poll()
        render()
        root.after(poll_ms, poll_worker)

    try:
        widgets = create_dashboard_workflow_widgets(
            root,
            tk,
            ttk,
            on_source=select_source,
            on_profile=select_profile,
            on_job=select_job,
            on_back=previous_step,
            on_next=next_step,
            on_review=review_job,
            on_run=run_job,
            on_cancel=cancel_job,
            on_discover=discover_ports,
            on_choose_export_path=choose_export_path,
            on_export=export_result,
            on_modify=modify_setup,
            on_repeat=review_same_setup,
            on_new_test=start_new_test,
            on_close=close_window,
            on_choose_coefficient_path=choose_coefficient_path,
            on_save_coefficients=save_coefficients,
            on_load_coefficients=load_coefficients,
            on_pause_live=pause_live_monitor,
            on_resume_live=resume_live_monitor,
            on_live_window=change_live_window,
        )
        root.protocol("WM_DELETE_WINDOW", close_window)
        render()
        finish_layout = getattr(root, "update_idletasks", None)
        if callable(finish_layout):
            finish_layout()
        if not withdraw:
            show_window = getattr(root, "deiconify", None)
            if callable(show_window):
                show_window()
        root.after(0, poll_worker)
        if auto_close_ms is not None:
            root.after(
                auto_close_ms,
                lambda: close_window(bypass_unsaved_confirmation=True),
            )
        root.mainloop()
    finally:
        if not closed:
            closed = application.request_close()
            if closed:
                root.destroy()
    if not closed:
        raise ProductWorkerTimeoutError(
            "the Dashboard window could not close its worker within the bounded timeout"
        )
    state = application.dashboard_state
    return DashboardSessionResult(
        state.source.source_mode,
        state.source.profile_identity,
        state.progress.worker_state,
        True,
    )


__all__ = [
    "DASHBOARD_SESSION_SCHEMA_VERSION",
    "DEFAULT_DASHBOARD_POLL_MS",
    "MAX_DASHBOARD_POLL_MS",
    "MAX_DASHBOARD_SMOKE_MS",
    "DashboardSessionResult",
    "DashboardWorkerFactory",
    "TkLoader",
    "launch_dashboard",
]
