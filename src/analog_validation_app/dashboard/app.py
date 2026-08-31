"""Lazy local Tk Dashboard lifecycle; importing this module does not import Tk."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from ..errors import (
    ProductDashboardUnavailableError,
    ProductFeatureUnavailableError,
    ProductRequestError,
    ProductWorkerTimeoutError,
)
from ..models import ProductJobRequest, ProductSourceMode, ProductWorkerState
from ..worker import ProductJobService, ProductJobWorker
from .controller import DashboardController, DashboardWorkerPort
from .presenter import DashboardPresenter
from .state import DASHBOARD_HARDWARE_CLAIM
from .widgets import create_dashboard_widgets

DASHBOARD_SESSION_SCHEMA_VERSION = "dashboard-session.v1"
DEFAULT_DASHBOARD_POLL_MS = 50
MAX_DASHBOARD_POLL_MS = 1_000
MAX_DASHBOARD_SMOKE_MS = 60_000

TkLoader = Callable[[], tuple[object, object]]
DashboardWorkerFactory = Callable[[], DashboardWorkerPort]


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


def _idle_service_factory(request: ProductJobRequest) -> ProductJobService:
    del request
    raise ProductFeatureUnavailableError(
        "Step 5 Dashboard shell cannot start jobs; workflow wiring begins in Step 6"
    )


def _idle_worker_factory() -> ProductJobWorker:
    return ProductJobWorker(_idle_service_factory)


def _bounded_integer(name: str, value: object, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProductRequestError(f"{name} must be an integer")
    if value <= 0 or value > maximum:
        raise ProductRequestError(f"{name} must satisfy 1 <= value <= {maximum}")
    return value


def launch_dashboard(
    *,
    tk_loader: TkLoader | None = None,
    worker_factory: DashboardWorkerFactory = _idle_worker_factory,
    poll_interval_ms: int = DEFAULT_DASHBOARD_POLL_MS,
    auto_close_ms: int | None = None,
    withdraw: bool = False,
) -> DashboardSessionResult:
    """Launch the offline shell and return after bounded worker closure."""

    if tk_loader is not None and not callable(tk_loader):
        raise ProductRequestError("tk_loader must be callable or None")
    if not callable(worker_factory):
        raise ProductRequestError("worker_factory must be callable")
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

    presenter = DashboardPresenter()
    try:
        controller = DashboardController(presenter, worker_factory())
    except BaseException:
        root.destroy()
        raise
    closed = False
    widgets: Any = None

    def render() -> None:
        widgets.render(controller.state)

    def cancel_job() -> None:
        controller.request_cancel()
        render()

    def close_window() -> None:
        nonlocal closed
        if closed:
            return
        if controller.request_close():
            closed = True
            render()
            root.destroy()
        else:
            render()

    def poll_worker() -> None:
        if closed:
            return
        controller.poll()
        render()
        root.after(poll_ms, poll_worker)

    try:
        widgets = create_dashboard_widgets(
            root,
            tk,
            ttk,
            on_cancel=cancel_job,
            on_close=close_window,
        )
        root.protocol("WM_DELETE_WINDOW", close_window)
        widgets.render(controller.state)
        if withdraw:
            root.withdraw()
        root.after(0, poll_worker)
        if auto_close_ms is not None:
            root.after(auto_close_ms, close_window)
        root.mainloop()
    finally:
        if not closed:
            closed = controller.request_close()
            if closed:
                root.destroy()
    if not closed:
        raise ProductWorkerTimeoutError(
            "the Dashboard window could not close its worker within the bounded timeout"
        )
    state = controller.state
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
