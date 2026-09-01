from __future__ import annotations

from typing import Any, cast

import pytest

from analog_validation.transport import SerialPortInfo
from analog_validation_app import (
    DashboardWizardDraft,
    DashboardWizardState,
    DashboardWizardStep,
    ProductRequestError,
    ProductSourceMode,
    UserIssue,
    UserIssueCode,
    UserIssueSeverity,
)
from analog_validation_app.dashboard import initial_dashboard_state
from analog_validation_app.dashboard.widgets import (
    create_dashboard_widgets,
    create_dashboard_workflow_widgets,
)


class FakeVariable:
    def __init__(self, *, master: object, value: object) -> None:
        self.value = value

    def set(self, value: object) -> None:
        self.value = value

    def get(self) -> object:
        return self.value


class FakeWidget:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.kwargs = dict(kwargs)
        self.config: dict[str, object] = {}
        self.bindings: dict[str, Any] = {}
        self.rows: dict[str, tuple[object, ...]] = {}

    def grid(self, **kwargs: object) -> None:
        return None

    def columnconfigure(self, column: object, **kwargs: object) -> None:
        return None

    def rowconfigure(self, row: object, **kwargs: object) -> None:
        return None

    def configure(self, **kwargs: object) -> None:
        self.config.update(kwargs)

    def bind(self, event: str, callback: Any) -> None:
        self.bindings[event] = callback

    def heading(self, column: str, **kwargs: object) -> None:
        return None

    def column(self, column: str, **kwargs: object) -> None:
        return None

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
        key = f"row-{len(self.rows)}"
        self.rows[key] = values
        return key


class FakeRoot(FakeWidget):
    def __init__(self) -> None:
        super().__init__()
        self.window_title = ""
        self.minimum = (0, 0)

    def title(self, value: str) -> None:
        self.window_title = value

    def minsize(self, width: int, height: int) -> None:
        self.minimum = (width, height)


class FakeTk:
    StringVar = FakeVariable
    BooleanVar = FakeVariable


class FakeTtk:
    Frame = FakeWidget
    LabelFrame = FakeWidget
    Label = FakeWidget
    Progressbar = FakeWidget
    Button = FakeWidget
    Treeview = FakeWidget
    Entry = FakeWidget
    Combobox = FakeWidget
    Checkbutton = FakeWidget


def callbacks(log: list[object]) -> dict[str, Any]:
    return {
        "on_source": lambda value: log.append(("source", value)),
        "on_profile": lambda value: log.append(("profile", value)),
        "on_job": lambda value: log.append(("job", value)),
        "on_back": lambda: log.append("back"),
        "on_next": lambda: log.append("next"),
        "on_review": lambda value: log.append(("review", value)),
        "on_run": lambda: log.append("run"),
        "on_cancel": lambda: log.append("cancel"),
        "on_discover": lambda: log.append("discover"),
        "on_export": lambda path, format_name: log.append(
            ("export", path, format_name)
        ),
        "on_close": lambda: log.append("close"),
    }


def issue() -> UserIssue:
    return UserIssue(
        UserIssueCode.INPUT_DATA,
        UserIssueSeverity.ERROR,
        "Replay rejected.",
        "The schema did not match.",
        "Choose a valid replay.",
        "ReplayFormatError",
    )


def test_workflow_widgets_render_six_steps_and_emit_only_typed_callbacks() -> None:
    log: list[object] = []
    widgets = create_dashboard_workflow_widgets(
        FakeRoot(), FakeTk(), FakeTtk(), **callbacks(log)
    )
    initial = DashboardWizardState(
        0, DashboardWizardStep.SOURCE, DashboardWizardDraft()
    )
    widgets.render(initial_dashboard_state(), initial)

    assert "Current: 1." in widgets.step_value.value
    assert "What:" in widgets.guidance_value.value
    assert widgets.next_button.config["state"] == "normal"
    assert widgets.run_button.config["state"] == "disabled"
    assert widgets.source_select.config["values"] == (
        "SIMULATOR",
        "CSV_REPLAY",
        "SERIAL_READ_ONLY",
    )

    widgets.source_select.bindings["<<ComboboxSelected>>"](None)
    widgets.profile_select.bindings["<<ComboboxSelected>>"](None)
    widgets.job_select.bindings["<<ComboboxSelected>>"](None)
    widgets.next_button.kwargs["command"]()
    widgets.review_button.kwargs["command"]()
    widgets.form.export_path.set("result.json")
    widgets.form.export_format.set("json")
    widgets.export_button.kwargs["command"]()

    assert log[0:3] == [
        ("source", "SIMULATOR"),
        ("profile", "afe/1"),
        ("job", "READ"),
    ]
    assert log[3] == "next"
    assert log[4][0] == "review"  # type: ignore[index]
    assert isinstance(log[4][1], DashboardWizardDraft)  # type: ignore[index]
    assert log[5] == ("export", "result.json", "json")


def test_workflow_render_shows_review_ports_issue_and_export_permissions() -> None:
    widgets = create_dashboard_workflow_widgets(
        FakeRoot(), FakeTk(), FakeTtk(), **callbacks([])
    )
    draft = DashboardWizardDraft(
        source_mode=ProductSourceMode.SERIAL_READ_ONLY,
        serial_port="MEMORY:1",
        serial_confirm_read_only=True,
    )
    wizard = DashboardWizardState(
        1,
        DashboardWizardStep.RESULT,
        draft,
        ("Receive-only reviewed.",),
        (SerialPortInfo("MEMORY:1", "Memory port"),),
        issue(),
        True,
        "Choose a destination.",
    )

    widgets.render(initial_dashboard_state(), wizard)
    widgets.render(initial_dashboard_state(), wizard)

    assert "Receive-only reviewed" in widgets.review_value.value
    assert "INPUT_DATA" in widgets.issue_value.value
    assert "MEMORY:1" in widgets.ports_value.value
    assert widgets.export_button.config["state"] == "normal"
    assert widgets.discover_button.config["state"] == "disabled"
    with pytest.raises(ProductRequestError, match="DashboardWizardState"):
        widgets.render(initial_dashboard_state(), cast(Any, object()))
    with pytest.raises(ProductRequestError, match="DashboardWizardDraft"):
        widgets.form.load(cast(Any, object()))


def test_widget_builders_reject_invalid_optional_host_and_workflow_inputs() -> None:
    with pytest.raises(ProductRequestError, match="configure_window"):
        create_dashboard_widgets(
            FakeRoot(),
            FakeTk(),
            FakeTtk(),
            on_cancel=lambda: None,
            on_close=lambda: None,
            configure_window=cast(Any, "yes"),
        )

    values = callbacks([])
    for name in tuple(values):
        invalid = dict(values)
        invalid[name] = object()
        with pytest.raises(ProductRequestError, match=name):
            create_dashboard_workflow_widgets(
                FakeRoot(), FakeTk(), FakeTtk(), **cast(Any, invalid)
            )
    for root, tk, ttk in (
        (None, FakeTk(), FakeTtk()),
        (FakeRoot(), None, FakeTtk()),
        (FakeRoot(), FakeTk(), None),
    ):
        with pytest.raises(ProductRequestError, match="required"):
            create_dashboard_workflow_widgets(root, tk, ttk, **cast(Any, values))


def test_bind_selection_is_optional_for_minimal_injected_toolkits() -> None:
    class NoBindWidget:
        pass

    from analog_validation_app.dashboard.widgets import _bind_selection

    _bind_selection(NoBindWidget(), lambda: None)
