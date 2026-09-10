"""Lazy local Tk Dashboard lifecycle; importing this module does not import Tk."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from ..errors import (
    ProductDashboardUnavailableError,
    ProductRequestError,
    ProductWorkerTimeoutError,
)
from ..models import ProductSourceMode, ProductWorkerState
from ..product_workflows import ProductWorkflowConfiguration
from ..reporting import REPORT_HTML_FILENAME, HumanReportPublication
from .application import DashboardApplication
from .controller import DashboardWorkerPort
from .import_page import ImportPage
from .project_widgets import ProjectPage
from .project_workspace import ProjectWorkspace
from .report_actions import ReportActions
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


def _choose_replay_path(
    parent: object,
    *,
    dialog: SavePathDialog | None = None,
) -> str:
    """Choose one existing CSV path without reading it before Review."""

    selected_dialog: SavePathDialog
    if dialog is None:  # pragma: no cover - exercised by the real Windows Tk gate
        from tkinter import filedialog

        selected_dialog = cast(SavePathDialog, filedialog.askopenfilename)
    else:
        selected_dialog = dialog
    selected = selected_dialog(
        parent=parent,
        title="Choose a CSV Replay file",
        filetypes=(("CSV Replay", "*.csv"),),
    )
    if not isinstance(selected, str):
        raise ProductRequestError("Dashboard replay dialog must return a path string")
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


def _choose_project_path(parent: object, mode: str) -> object:
    """Native file selection is only invoked by an explicit project-page action."""
    from tkinter import filedialog, messagebox

    options: dict[str, Any] = {"parent": parent}
    if mode == "discard-project":
        return messagebox.askyesno(
            **options,
            title="Unsaved project changes",
            message="Discard unsaved project changes and close?",
            detail="Choose No to save the project as a new file first.",
            default="no",
        )
    if mode == "history":
        return filedialog.askopenfilenames(
            **options,
            title="Choose run-manifest.json files",
            filetypes=(("Run manifests", "*.json"),),
        )
    if mode == "project-open":
        return filedialog.askopenfilename(
            **options,
            title="Open test project",
            filetypes=(("Test projects", "*.json"),),
        )
    if mode not in {"project-save", "run-directory"}:
        raise ProductRequestError("Unknown project path selection.")
    return filedialog.asksaveasfilename(
        **options,
        title="Save a new test project"
        if mode == "project-save"
        else "Choose a NEW run directory name",
        initialfile=(
            "validation-project.json" if mode == "project-save" else "run-001"
        ),
        defaultextension=".json" if mode == "project-save" else "",
        confirmoverwrite=False,
    )


def _choose_report_directory(
    parent: object, *, dialog: SavePathDialog | None = None
) -> str:
    if dialog is None:  # pragma: no cover - native chooser
        from tkinter import filedialog

        dialog = cast(SavePathDialog, filedialog.asksaveasfilename)
    selected = dialog(
        parent=parent,
        title="Name a NEW report folder",
        initialfile="validation-report",
        defaultextension="",
        confirmoverwrite=False,
    )
    if not isinstance(selected, str):
        raise ProductRequestError("Report folder selection must be a path string")
    return selected


def _choose_import_path(
    parent: object,
    mode: str,
    *,
    dialog: SavePathDialog | None = None,
) -> str:
    """Choose an import input or new output without reading or writing it."""
    if mode not in {"source", "load_mapping", "save_mapping", "output"}:
        raise ProductRequestError("Unknown import file selection mode")
    saving = mode in {"save_mapping", "output"}
    if dialog is None:  # pragma: no cover - native platform file picker
        from tkinter import filedialog

        dialog = cast(
            SavePathDialog,
            filedialog.asksaveasfilename if saving else filedialog.askopenfilename,
        )
    options: dict[str, object] = {
        "parent": parent,
        "title": {
            "source": "Choose a UTF-8 voltage table",
            "load_mapping": "Choose a saved import mapping",
            "save_mapping": "Save mapping to a NEW JSON file",
            "output": "Name a NEW import package folder",
        }[mode],
    }
    if mode == "source":
        options["filetypes"] = (("Delimited text", "*.csv *.tsv *.txt"), ("All files", "*.*"))
    elif mode != "output":
        options["filetypes"] = (("Import mapping JSON", "*.json"),)
    if saving:
        options["confirmoverwrite"] = False
        options["initialfile"] = "voltage-import" if mode == "output" else "voltage-mapping.json"
        options["defaultextension"] = "" if mode == "output" else ".json"
    selected = dialog(**options)
    if not isinstance(selected, str):
        raise ProductRequestError("Import file selection must return a path string")
    return selected


def _confirm_discard_import(
    parent: object, *, dialog: DiscardConfirmationDialog | None = None
) -> bool:
    if dialog is None:  # pragma: no cover - native confirmation
        from tkinter import messagebox

        dialog = cast(DiscardConfirmationDialog, messagebox.askyesno)
    selected = dialog(
        parent=parent,
        title="Close with an unpublished import?",
        message="The reviewed import has not been saved as a package. Close anyway?",
        detail="The original input file stays unchanged. Choose No to return and save the import package.",
        icon="warning",
        default="no",
    )
    if not isinstance(selected, bool):
        raise ProductRequestError("Import close confirmation must return a bool")
    return selected


def _confirm_replace_setup(
    parent: object,
    *,
    has_unsaved_result: bool,
    dialog: DiscardConfirmationDialog | None = None,
) -> bool:
    if dialog is None:  # pragma: no cover - native confirmation
        from tkinter import messagebox

        dialog = cast(DiscardConfirmationDialog, messagebox.askyesno)
    confirmed = dialog(
        parent=parent,
        title="Load configuration into Setup",
        message="Replace the current setup with the selected configuration?",
        detail=(
            "The current result or coefficients have not been saved and will be discarded. "
            if has_unsaved_result
            else "Current setup edits and its previous review will be replaced. "
        )
        + "The saved source configuration stays unchanged. Choose No to keep the current work.",
        icon="warning",
        default="no",
    )
    if not isinstance(confirmed, bool):
        raise ProductRequestError("Setup confirmation must return a bool")
    return confirmed


def _open_published_report(
    publication: HumanReportPublication, *, opener: Callable[[str], bool] | None = None
) -> None:
    artifact = next(
        item for item in publication.artifacts if item.name == REPORT_HTML_FILENAME
    )
    path = publication.output_directory / artifact.name
    payload = path.read_bytes()
    if (
        len(payload) != artifact.size_bytes
        or hashlib.sha256(payload).hexdigest() != artifact.sha256
    ):
        raise ProductRequestError(
            "Saved report changed after publication; save a new report package"
        )
    if opener is None:  # pragma: no cover - explicit user action opens local HTML
        import webbrowser

        opener = webbrowser.open
    if not opener(path.resolve().as_uri()):
        raise ProductRequestError(
            "No browser opened the report; open report.html in the saved folder"
        )


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
    project_page: ProjectPage | None = None
    import_page: ImportPage | None = None
    report_actions: ReportActions | None = None
    projects = ProjectWorkspace(
        lambda: application.dashboard_state.progress.worker_state.is_active
    )
    close_pending = False

    def render() -> None:
        widgets.issue_field_id = application.issue_field_id
        widgets.render(application.dashboard_state, application.wizard_state)
        if project_page is not None:
            project_page.render()
        if import_page is not None:
            import_page.render()
        if report_actions is not None:
            report_actions.render(
                application.wizard_state.can_export, application.report_publication
            )

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

        if isinstance(draft, BaseException):
            application.present_input_error(draft)
            render()
            return
        if not isinstance(draft, DashboardWizardDraft):
            raise ProductRequestError("Dashboard review requires a wizard draft")
        application.prepare_review(draft)
        render()

    def run_job() -> None:
        if projects.busy:
            projects._changed(
                "Wait for the project batch to finish before starting a single test."
            )
            render()
            return
        application.run()
        render()

    def discover_ports() -> None:
        if projects.busy:
            return
        application.discover_ports()
        render()

    def export_result(path: str, format_name: str) -> None:
        application.export_result(path, format_name)
        render()

    def choose_export_path(format_name: str) -> str:
        return _choose_export_destination(root, format_name)

    def save_report() -> None:
        try:
            selected = _choose_report_directory(root)
            if selected:
                application.save_report_bundle(selected)
        except BaseException as error:  # noqa: BLE001 - native callback boundary
            application.present_input_error(error)
        render()

    def open_report() -> None:
        try:
            if application.report_publication is None:
                raise ProductRequestError("Save a report package before opening it")
            _open_published_report(application.report_publication)
        except BaseException as error:  # noqa: BLE001 - native callback boundary
            application.present_input_error(error)
        render()

    def load_preset_setup(configuration: ProductWorkflowConfiguration) -> bool:
        from .wizard import DashboardWizardDraft

        if projects.busy or application.dashboard_state.progress.worker_state.is_active:
            return False
        try:
            has_edits = widgets.form.snapshot() != DashboardWizardDraft()
        except ProductRequestError:
            has_edits = True
        if (has_edits or application.has_unsaved_result) and not _confirm_replace_setup(
            root, has_unsaved_result=application.has_unsaved_result
        ):
            return False
        accepted = application.load_preset_configuration(
            configuration, discard_unsaved=True
        )
        if accepted:
            # Explicitly replace scratch fields even when the stored draft is identical.
            widgets.form.load(application.wizard_state.draft)
        render()
        if accepted and widgets.notebook is not None:
            widgets.notebook.select(widgets.workflow_page)
        return accepted

    def choose_replay_path() -> str:
        return _choose_replay_path(root)

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
        nonlocal closed, close_pending
        if closed:
            return
        if projects.busy:
            close_pending = True
            if not projects.cancellation_requested:
                projects.request_cancel()
            render()
            return
        close_pending = False
        if (
            projects.dirty
            and not bypass_unsaved_confirmation
            and not _choose_project_path(root, "discard-project")
        ):
            return
        if not bypass_unsaved_confirmation and not discard_is_confirmed(
            "close the application"
        ):
            return
        if (
            import_page is not None
            and import_page.has_unsaved_work
            and not bypass_unsaved_confirmation
            and not _confirm_discard_import(root)
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
        projects.poll()
        render()
        if close_pending and not projects.busy:
            close_window()
            if closed:
                return
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
            on_choose_replay_path=choose_replay_path,
            on_choose_coefficient_path=choose_coefficient_path,
            on_save_coefficients=save_coefficients,
            on_load_coefficients=load_coefficients,
            on_pause_live=pause_live_monitor,
            on_resume_live=resume_live_monitor,
            on_live_window=change_live_window,
        )
        if getattr(widgets, "notebook", None) is not None:
            project_page = ProjectPage(
                root,
                tk,
                ttk,
                widgets.notebook,
                projects,
                lambda mode: _choose_project_path(root, mode),
                widgets.form.snapshot,
                on_load_setup=load_preset_setup,
            )
            import_page = ImportPage(
                root,
                tk,
                ttk,
                widgets.notebook,
                on_load_setup=load_preset_setup,
                is_busy=lambda: projects.busy
                or application.dashboard_state.progress.worker_state.is_active,
                choose_path=lambda mode: _choose_import_path(root, mode),
            )
        report_actions = ReportActions(
            widgets.section_frames["export"],
            tk,
            ttk,
            on_save=save_report,
            on_open=open_report,
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
    if projects.busy:
        raise ProductWorkerTimeoutError(
            "The Dashboard event loop ended while a project batch was still running."
        )
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
