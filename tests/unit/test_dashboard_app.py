from __future__ import annotations

from typing import Any, cast

import pytest

import analog_validation_app.dashboard.app as app_module
from analog_validation_app import (
    ProductDashboardUnavailableError,
    ProductRequestError,
    ProductSourceMode,
    ProductWorkerState,
    ProductWorkerTimeoutError,
)
from analog_validation_app.dashboard.app import (
    DASHBOARD_SESSION_SCHEMA_VERSION,
    DEFAULT_DASHBOARD_POLL_MS,
    MAX_DASHBOARD_POLL_MS,
    MAX_DASHBOARD_SMOKE_MS,
    DashboardSessionResult,
    launch_dashboard,
)


class FakeVariable:
    def __init__(self, *, master: object, value: str) -> None:
        self.value = value

    def set(self, value: str) -> None:
        self.value = value

    def get(self) -> object:
        return self.value


class FakeWidget:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.kwargs = dict(kwargs)
        self.rows: dict[str, tuple[object, ...]] = {}
        self.config: dict[str, object] = {}
        self.bindings: dict[str, Any] = {}

    def grid(self, **kwargs: object) -> None:
        pass

    def columnconfigure(self, column: object, **kwargs: object) -> None:
        pass

    def rowconfigure(self, row: object, **kwargs: object) -> None:
        pass

    def configure(self, **kwargs: object) -> None:
        self.config.update(kwargs)

    def bind(self, event: str, callback: Any) -> None:
        self.bindings[event] = callback

    def heading(self, column: str, **kwargs: object) -> None:
        pass

    def column(self, column: str, **kwargs: object) -> None:
        pass

    def get_children(self) -> tuple[str, ...]:
        return tuple(self.rows)

    def delete(self, item: str) -> None:
        del self.rows[item]

    def insert(
        self,
        parent: str,
        index: str,
        *,
        values: tuple[object, ...],
    ) -> str:
        item = f"row-{len(self.rows)}"
        self.rows[item] = values
        return item


class FakeTtk:
    def __init__(self) -> None:
        self.buttons: list[FakeWidget] = []
        self.created: list[FakeWidget] = []

    def _widget(self, *args: object, **kwargs: object) -> FakeWidget:
        selected = FakeWidget(*args, **kwargs)
        self.created.append(selected)
        return selected

    Frame = _widget
    LabelFrame = _widget
    Label = _widget
    Progressbar = _widget
    Treeview = _widget
    Entry = _widget
    Combobox = _widget
    Checkbutton = _widget

    def Button(self, *args: object, **kwargs: object) -> FakeWidget:
        selected = FakeWidget(*args, **kwargs)
        self.buttons.append(selected)
        self.created.append(selected)
        return selected


class FakeRoot(FakeWidget):
    def __init__(self, ttk: FakeTtk) -> None:
        super().__init__()
        self.ttk = ttk
        self.destroyed = False
        self.withdrawn = False
        self.paint_events: list[str] = []
        self.protocols: dict[str, Any] = {}
        self.scheduled: list[tuple[int, int, Any]] = []
        self.clock = 0
        self.sequence = 0
        self.cancel_invoked = False
        self.after_close_callbacks = False

    def title(self, value: str) -> None:
        pass

    def minsize(self, width: int, height: int) -> None:
        pass

    def protocol(self, name: str, callback: Any) -> None:
        self.protocols[name] = callback

    def withdraw(self) -> None:
        self.withdrawn = True
        self.paint_events.append("withdraw")

    def update_idletasks(self) -> None:
        self.paint_events.append("update_idletasks")

    def deiconify(self) -> None:
        self.withdrawn = False
        self.paint_events.append("deiconify")

    def after(self, delay: int, callback: Any) -> None:
        self.sequence += 1
        self.scheduled.append((self.clock + delay, self.sequence, callback))

    def destroy(self) -> None:
        self.destroyed = True

    def mainloop(self) -> None:
        steps = 0
        while self.scheduled and not self.destroyed and steps < 100:
            self.scheduled.sort(key=lambda value: (value[0], value[1]))
            due, _, callback = self.scheduled.pop(0)
            self.clock = due
            if not self.cancel_invoked and self.ttk.buttons:
                self.cancel_invoked = True
                cast(Any, self.ttk.buttons[0].kwargs["command"])()
            callback()
            steps += 1
        if self.destroyed and self.after_close_callbacks:
            self.protocols["WM_DELETE_WINDOW"]()
            for _, _, callback in tuple(self.scheduled):
                callback()


class FakeTk:
    class TclError(Exception):
        pass

    StringVar = FakeVariable
    BooleanVar = FakeVariable

    def __init__(self, root: FakeRoot) -> None:
        self.root = root

    def Tk(self) -> FakeRoot:
        return self.root


def fake_toolkit(*, after_close_callbacks: bool = False):
    ttk = FakeTtk()
    root = FakeRoot(ttk)
    root.after_close_callbacks = after_close_callbacks
    tk = FakeTk(root)
    return root, tk, ttk


def test_export_destination_dialog_uses_requested_format_and_safe_options() -> None:
    calls: list[dict[str, object]] = []

    def choose(**kwargs: object) -> str:
        calls.append(dict(kwargs))
        return r"C:\safe\analysis.csv"

    parent = object()
    selected = app_module._choose_export_destination(
        parent,
        "csv",
        dialog=choose,
    )

    assert selected == r"C:\safe\analysis.csv"
    assert calls == [
        {
            "parent": parent,
            "title": "Choose a new analysis result file",
            "defaultextension": ".csv",
            "initialfile": "analog-validation-result.csv",
            "filetypes": (("CSV analysis result", "*.csv"),),
            "confirmoverwrite": False,
        }
    ]


def test_export_destination_dialog_cancel_and_invalid_results_are_bounded() -> None:
    assert (
        app_module._choose_export_destination(
            object(),
            "json",
            dialog=lambda **_kwargs: "",
        )
        == ""
    )
    with pytest.raises(ProductRequestError, match="json or csv"):
        app_module._choose_export_destination(
            object(),
            "txt",
            dialog=lambda **_kwargs: "ignored",
        )
    with pytest.raises(ProductRequestError, match="path string"):
        app_module._choose_export_destination(
            object(),
            "json",
            dialog=lambda **_kwargs: cast(Any, None),
        )


def test_coefficient_dialog_distinguishes_new_save_from_existing_load() -> None:
    calls: list[dict[str, object]] = []

    def choose(**kwargs: object) -> str:
        calls.append(dict(kwargs))
        return r"C:\safe\coefficients.json"

    parent = object()
    assert (
        app_module._choose_coefficient_path(parent, "save", dialog=choose)
        == r"C:\safe\coefficients.json"
    )
    assert calls[-1]["confirmoverwrite"] is False
    assert calls[-1]["initialfile"] == "analog-validation-calibration.json"
    assert (
        app_module._choose_coefficient_path(parent, "load", dialog=choose)
        == r"C:\safe\coefficients.json"
    )
    assert "confirmoverwrite" not in calls[-1]
    assert "existing" in str(calls[-1]["title"])

    with pytest.raises(ProductRequestError, match="save or load"):
        app_module._choose_coefficient_path(parent, "apply", dialog=choose)
    with pytest.raises(ProductRequestError, match="path string"):
        app_module._choose_coefficient_path(
            parent,
            "load",
            dialog=lambda **_kwargs: cast(Any, None),
        )


def test_unsaved_result_confirmation_is_explicit_cancel_first_and_bounded() -> None:
    calls: list[dict[str, object]] = []

    def confirm(**kwargs: object) -> bool:
        calls.append(dict(kwargs))
        return False

    parent = object()
    assert (
        app_module._confirm_discard_unsaved_result(
            parent,
            "start a new test",
            dialog=confirm,
        )
        is False
    )
    assert calls == [
        {
            "parent": parent,
            "title": "Unsaved analysis result",
            "message": ("Discard the unsaved analysis result and start a new test?"),
            "detail": "Choose No to return to the result page and save it first.",
            "icon": "warning",
            "default": "no",
        }
    ]
    with pytest.raises(ProductRequestError, match="discard action"):
        app_module._confirm_discard_unsaved_result(
            parent,
            " padded ",
            dialog=confirm,
        )
    with pytest.raises(ProductRequestError, match="return a bool"):
        app_module._confirm_discard_unsaved_result(
            parent,
            "close the application",
            dialog=lambda **_kwargs: cast(Any, "yes"),
        )


def test_fake_window_launch_poll_cancel_and_close_is_safe_and_path_free() -> None:
    root, tk, ttk = fake_toolkit(after_close_callbacks=True)

    session = launch_dashboard(
        tk_loader=lambda: (tk, ttk),
        poll_interval_ms=10,
        auto_close_ms=25,
        withdraw=True,
    )

    assert DASHBOARD_SESSION_SCHEMA_VERSION == "dashboard-session.v1"
    assert DEFAULT_DASHBOARD_POLL_MS == 50
    assert MAX_DASHBOARD_POLL_MS == 1_000
    assert MAX_DASHBOARD_SMOKE_MS == 60_000
    assert session.source_mode is ProductSourceMode.SIMULATOR
    assert session.profile_identity == "afe/1"
    assert session.worker_state is ProductWorkerState.IDLE
    assert session.closed_safely is True
    assert session.hardware_claim == "NO_NEW_HARDWARE_VALIDATION"
    assert root.withdrawn is True
    assert root.destroyed is True
    assert root.cancel_invoked is True


def test_mainloop_return_without_window_callback_still_closes_owned_worker() -> None:
    class ReturningRoot(FakeRoot):
        def mainloop(self) -> None:
            return

    ttk = FakeTtk()
    root = ReturningRoot(ttk)
    session = launch_dashboard(tk_loader=lambda: (FakeTk(root), ttk))

    assert session.closed_safely is True
    assert root.destroyed is True
    assert root.paint_events == ["withdraw", "update_idletasks", "deiconify"]


@pytest.mark.parametrize(
    "factory",
    [
        lambda: DashboardSessionResult(
            cast(Any, "SIMULATOR"), "afe/1", ProductWorkerState.IDLE, True
        ),
        lambda: DashboardSessionResult(
            ProductSourceMode.SIMULATOR, " afe/1", ProductWorkerState.IDLE, True
        ),
        lambda: DashboardSessionResult(
            ProductSourceMode.SIMULATOR, "afe/1", cast(Any, "IDLE"), True
        ),
        lambda: DashboardSessionResult(
            ProductSourceMode.SIMULATOR, "afe/1", ProductWorkerState.IDLE, False
        ),
        lambda: DashboardSessionResult(
            ProductSourceMode.SIMULATOR,
            "afe/1",
            ProductWorkerState.IDLE,
            True,
            "HARDWARE_VERIFIED",
        ),
        lambda: DashboardSessionResult(
            ProductSourceMode.SIMULATOR,
            "afe/1",
            ProductWorkerState.IDLE,
            True,
            schema_version="dashboard-session.v2",
        ),
    ],
)
def test_session_result_rejects_invalid_identity_and_claim(factory: Any) -> None:
    with pytest.raises(ProductRequestError):
        factory()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"tk_loader": object()},
        {"worker_factory": object()},
        {"poll_interval_ms": True},
        {"poll_interval_ms": 0},
        {"poll_interval_ms": MAX_DASHBOARD_POLL_MS + 1},
        {"auto_close_ms": 0},
        {"auto_close_ms": MAX_DASHBOARD_SMOKE_MS + 1},
        {"withdraw": "yes"},
    ],
)
def test_launch_rejects_invalid_injected_bounds(kwargs: dict[str, object]) -> None:
    with pytest.raises(ProductRequestError):
        launch_dashboard(**cast(Any, kwargs))


def test_tk_import_and_display_failures_are_beginner_readable() -> None:
    def missing() -> tuple[object, object]:
        raise ImportError("no tkinter")

    with pytest.raises(ProductDashboardUnavailableError, match="import Tkinter"):
        launch_dashboard(tk_loader=missing)
    with pytest.raises(ProductRequestError, match="must return"):
        launch_dashboard(tk_loader=cast(Any, lambda: (object(),)))

    class BrokenTk:
        class TclError(Exception):
            pass

        def Tk(self) -> object:
            raise self.TclError("no display")

    with pytest.raises(ProductDashboardUnavailableError, match="no local display"):
        launch_dashboard(tk_loader=lambda: (BrokenTk(), FakeTtk()))

    class ProgrammingErrorTk:
        class TclError(Exception):
            pass

        def Tk(self) -> object:
            raise RuntimeError("bug")

    with pytest.raises(RuntimeError, match="bug"):
        launch_dashboard(tk_loader=lambda: (ProgrammingErrorTk(), FakeTtk()))


def test_worker_factory_failure_destroys_created_root() -> None:
    root, tk, ttk = fake_toolkit()

    def broken_worker() -> object:
        raise RuntimeError("factory bug")

    with pytest.raises(RuntimeError, match="factory bug"):
        launch_dashboard(
            tk_loader=lambda: (tk, ttk),
            worker_factory=cast(Any, broken_worker),
        )
    assert root.destroyed is True


class TimeoutWorker:
    state = ProductWorkerState.IDLE
    request = None
    result = None
    issue = None
    dropped_event_count = 0

    @property
    def is_active(self) -> bool:
        return False

    def drain_events(self) -> tuple[object, ...]:
        return ()

    def request_cancel(self) -> bool:
        return False

    def close(self, timeout_s: float | None = None) -> None:
        raise ProductWorkerTimeoutError("close timeout")


def test_failed_bounded_close_returns_an_honest_timeout() -> None:
    root, tk, ttk = fake_toolkit()
    with pytest.raises(ProductWorkerTimeoutError, match="could not close"):
        launch_dashboard(
            tk_loader=lambda: (tk, ttk),
            worker_factory=cast(Any, TimeoutWorker),
            auto_close_ms=1,
        )
    assert root.destroyed is False


def test_six_step_window_callbacks_drive_the_headless_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class InteractiveRoot(FakeRoot):
        def _button(self, text: str) -> FakeWidget:
            return next(
                button
                for button in self.ttk.buttons
                if button.kwargs.get("text") == text
            )

        def _select(self, value: str) -> None:
            selected = next(
                widget
                for widget in self.ttk.created
                if "<<ComboboxSelected>>" in widget.bindings
                and cast(Any, widget.kwargs["textvariable"]).get() == value
            )
            selected.bindings["<<ComboboxSelected>>"](None)

        def mainloop(self) -> None:
            self._select("SIMULATOR")
            self._select("afe/1")
            cast(Any, self._button("Continue").kwargs["command"])()
            self._select("READ")
            cast(Any, self._button("Continue").kwargs["command"])()
            cast(Any, self._button("Find serial ports").kwargs["command"])()
            cast(Any, self._button("Validate setup").kwargs["command"])()
            cast(Any, self._button("Run reviewed test").kwargs["command"])()
            cast(Any, self._button("Cancel run safely").kwargs["command"])()
            cast(Any, self._button("Choose save location...").kwargs["command"])()
            cast(Any, self._button("Save analysis result").kwargs["command"])()
            cast(Any, self._button("Previous step").kwargs["command"])()
            if self.scheduled:
                self.scheduled.sort(key=lambda value: (value[0], value[1]))
                _, _, callback = self.scheduled.pop(0)
                callback()
            self.protocols["WM_DELETE_WINDOW"]()

    ttk = FakeTtk()
    root = InteractiveRoot(ttk)
    monkeypatch.setattr(
        app_module,
        "_choose_export_destination",
        lambda _parent, _format_name: "chosen-result.json",
    )
    session = launch_dashboard(tk_loader=lambda: (FakeTk(root), ttk))

    assert session.closed_safely is True
    assert root.destroyed is True


def test_review_callback_rejects_non_draft_payload_and_still_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, tk, ttk = fake_toolkit()

    def invalid_review(*args: object, **kwargs: object) -> object:
        cast(Any, kwargs["on_review"])(object())
        raise AssertionError("invalid review must stop widget creation")

    monkeypatch.setattr(app_module, "create_dashboard_workflow_widgets", invalid_review)
    with pytest.raises(ProductRequestError, match="wizard draft"):
        launch_dashboard(tk_loader=lambda: (tk, ttk))
    assert root.destroyed is True


def test_result_action_callbacks_are_wired_through_the_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, tk, ttk = fake_toolkit()
    callback_calls: list[str] = []

    class CallbackWidgets:
        invoked = False

        def __init__(self, selected_callbacks: dict[str, Any]) -> None:
            self.callbacks = selected_callbacks

        def render(self, dashboard: object, wizard: object) -> None:
            if self.invoked:
                return
            self.invoked = True
            for name in ("on_modify", "on_repeat", "on_new_test"):
                callback_calls.append(name)
                cast(Any, self.callbacks[name])()

    def capture_callbacks(*args: object, **kwargs: object) -> CallbackWidgets:
        return CallbackWidgets(dict(kwargs))

    monkeypatch.setattr(
        app_module, "create_dashboard_workflow_widgets", capture_callbacks
    )
    session = launch_dashboard(
        tk_loader=lambda: (tk, ttk),
        auto_close_ms=1,
    )

    assert callback_calls == ["on_modify", "on_repeat", "on_new_test"]
    assert session.closed_safely is True
    assert root.destroyed is True


def test_calibration_file_callbacks_are_wired_through_the_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, tk, ttk = fake_toolkit()
    callback_calls: list[object] = []

    class CoefficientWidgets:
        invoked = False

        def __init__(self, selected_callbacks: dict[str, Any]) -> None:
            self.callbacks = selected_callbacks

        def render(self, dashboard: object, wizard: object) -> None:
            if self.invoked:
                return
            self.invoked = True
            callback_calls.append(
                cast(Any, self.callbacks["on_choose_coefficient_path"])("save")
            )
            callback_calls.append(
                cast(Any, self.callbacks["on_save_coefficients"])("chosen.json")
            )
            callback_calls.append(
                cast(Any, self.callbacks["on_load_coefficients"])("chosen.json")
            )

    monkeypatch.setattr(
        app_module,
        "create_dashboard_workflow_widgets",
        lambda *args, **kwargs: CoefficientWidgets(dict(kwargs)),
    )
    monkeypatch.setattr(
        app_module,
        "_choose_coefficient_path",
        lambda _parent, mode: f"chosen-{mode}.json",
    )

    session = launch_dashboard(tk_loader=lambda: (tk, ttk), auto_close_ms=1)

    assert callback_calls == ["chosen-save.json", None, None]
    assert session.closed_safely is True
    assert root.destroyed is True


def test_live_monitor_callbacks_are_wired_through_the_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, tk, ttk = fake_toolkit()
    callback_calls: list[object] = []

    class LiveWidgets:
        invoked = False

        def __init__(self, selected_callbacks: dict[str, Any]) -> None:
            self.callbacks = selected_callbacks

        def render(self, dashboard: object, wizard: object) -> None:
            if self.invoked:
                return
            self.invoked = True
            callback_calls.append(cast(Any, self.callbacks["on_pause_live"])())
            callback_calls.append(cast(Any, self.callbacks["on_resume_live"])())
            callback_calls.append(cast(Any, self.callbacks["on_live_window"])(1.0))

    monkeypatch.setattr(
        app_module,
        "create_dashboard_workflow_widgets",
        lambda *args, **kwargs: LiveWidgets(dict(kwargs)),
    )

    session = launch_dashboard(tk_loader=lambda: (tk, ttk), auto_close_ms=1)

    assert callback_calls == [None, None, None]
    assert session.closed_safely is True
    assert root.destroyed is True


def test_unsaved_result_can_cancel_every_destructive_result_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, tk, ttk = fake_toolkit()
    prompted_actions: list[str] = []

    class GuardWidgets:
        invoked = False

        def __init__(self, selected_callbacks: dict[str, Any]) -> None:
            self.callbacks = selected_callbacks

        def render(self, dashboard: object, wizard: object) -> None:
            if self.invoked:
                return
            self.invoked = True
            for name in ("on_modify", "on_repeat", "on_new_test", "on_close"):
                cast(Any, self.callbacks[name])()

    monkeypatch.setattr(
        app_module,
        "create_dashboard_workflow_widgets",
        lambda *args, **kwargs: GuardWidgets(dict(kwargs)),
    )
    monkeypatch.setattr(
        app_module.DashboardApplication,
        "has_unsaved_result",
        property(lambda _application: True),
    )

    def deny_discard(_parent: object, action: str) -> bool:
        prompted_actions.append(action)
        return False

    monkeypatch.setattr(app_module, "_confirm_discard_unsaved_result", deny_discard)

    session = launch_dashboard(
        tk_loader=lambda: (tk, ttk),
        auto_close_ms=1,
    )

    assert prompted_actions == [
        "modify the setup",
        "review the same setup again",
        "start a new test",
        "close the application",
    ]
    assert session.closed_safely is True
    assert root.destroyed is True
