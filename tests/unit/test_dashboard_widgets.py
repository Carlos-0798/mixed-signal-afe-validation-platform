from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from analog_validation.exports import load_result_export_json
from analog_validation_app import (
    HumanReportPublication,
    ProductRequestError,
    ReportArtifact,
    UserIssue,
    UserIssueCode,
    UserIssueSeverity,
    build_human_report_view,
)
from analog_validation_app.dashboard import DashboardPresenter, initial_dashboard_state
from analog_validation_app.dashboard.widgets import (
    configure_dashboard_style,
    create_dashboard_widgets,
)

ROOT = Path(__file__).resolve().parents[2]
DC_RESULT = ROOT / "test-data" / "golden" / "phase3_dc_sweep_result_v1.json"


class FakeVariable:
    def __init__(self, *, master: object, value: str) -> None:
        self.master = master
        self.value = value

    def set(self, value: str) -> None:
        self.value = value


class FakeWidget:
    next_id = 1

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args = args
        self.kwargs = dict(kwargs)
        self.config: dict[str, object] = {}
        self.grid_calls: list[dict[str, object]] = []
        self.column_config: list[tuple[object, dict[str, object]]] = []
        self.row_config: list[tuple[object, dict[str, object]]] = []
        self.headings: dict[str, dict[str, object]] = {}
        self.columns: dict[str, dict[str, object]] = {}
        self.rows: dict[str, tuple[object, ...]] = {}
        self.yview_calls: list[tuple[object, ...]] = []
        self.set_calls: list[tuple[object, ...]] = []

    def grid(self, **kwargs: object) -> None:
        self.grid_calls.append(dict(kwargs))

    def columnconfigure(self, column: object, **kwargs: object) -> None:
        self.column_config.append((column, dict(kwargs)))

    def rowconfigure(self, row: object, **kwargs: object) -> None:
        self.row_config.append((row, dict(kwargs)))

    def configure(self, **kwargs: object) -> None:
        self.config.update(kwargs)

    def yview(self, *args: object) -> None:
        self.yview_calls.append(args)

    def set(self, *args: object) -> None:
        self.set_calls.append(args)

    def heading(self, column: str, **kwargs: object) -> None:
        self.headings[column] = dict(kwargs)

    def column(self, column: str, **kwargs: object) -> None:
        self.columns[column] = dict(kwargs)

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
        assert parent == ""
        assert index == "end"
        item = f"row-{FakeWidget.next_id}"
        FakeWidget.next_id += 1
        self.rows[item] = values
        return item


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


class FakeTtk:
    def __init__(self) -> None:
        self.created: list[FakeWidget] = []

    def _widget(self, *args: object, **kwargs: object) -> FakeWidget:
        selected = FakeWidget(*args, **kwargs)
        self.created.append(selected)
        return selected

    Frame = _widget
    LabelFrame = _widget
    Label = _widget
    Progressbar = _widget
    Button = _widget
    Treeview = _widget
    Scrollbar = _widget


def test_optional_style_supports_legacy_factories_and_fails_open() -> None:
    class LegacyStyle:
        def __init__(self) -> None:
            self.selected_theme = ""
            self.configured: list[str] = []

        def theme_names(self) -> tuple[str, ...]:
            return ("default", "clam")

        def theme_use(self, value: str) -> None:
            self.selected_theme = value

        def configure(self, name: str, **kwargs: object) -> None:
            self.configured.append(name)

        def map(self, name: str, **kwargs: object) -> None:
            return None

    class LegacyTtk:
        def __init__(self, style: LegacyStyle) -> None:
            self.style = style
            self.calls: list[tuple[object, ...]] = []

        def Style(self, *args: object) -> LegacyStyle:
            self.calls.append(args)
            if args:
                raise TypeError("legacy Style does not accept a root")
            return self.style

    root = FakeRoot()
    style = LegacyStyle()
    ttk = LegacyTtk(style)

    configure_dashboard_style(root, ttk)

    assert len(ttk.calls) == 2
    assert ttk.calls[1] == ()
    assert style.selected_theme == "clam"
    assert "Primary.TButton" in style.configured
    assert root.config["background"] == "#f4f7fb"

    class BrokenTtk:
        @staticmethod
        def Style(*args: object) -> object:
            raise RuntimeError("optional styling is unavailable")

    configure_dashboard_style(root, BrokenTtk())


def issue() -> UserIssue:
    return UserIssue(
        UserIssueCode.OPERATION_FAILED,
        UserIssueSeverity.ERROR,
        "The job stopped.",
        "A guarded boundary rejected it.",
        "Review the configuration.",
        "ExampleError",
    )


def test_widget_builder_creates_six_text_regions_without_business_actions() -> None:
    root = FakeRoot()
    ttk = FakeTtk()
    calls: list[str] = []
    widgets = create_dashboard_widgets(
        root,
        FakeTk(),
        ttk,
        on_cancel=lambda: calls.append("cancel"),
        on_close=lambda: calls.append("close"),
    )

    assert root.window_title == "Analog Validation Studio"
    assert root.minimum == (1040, 760)
    assert len(ttk.created) >= 20
    assert set(widgets.plot_table.headings) == {
        "index",
        "label",
        "disposition",
        "values",
    }
    scrollbars = [
        widget
        for widget in ttk.created
        if widget.kwargs.get("orient") == "vertical"
    ]
    assert len(scrollbars) == 1
    scrollbar = scrollbars[0]
    assert scrollbar.kwargs["command"] == widgets.plot_table.yview
    assert scrollbar.grid_calls == [
        {"row": 1, "column": 1, "sticky": "ns", "pady": (6, 0)}
    ]
    assert widgets.plot_table.config["yscrollcommand"] == scrollbar.set
    widgets.cancel_button.kwargs["command"]()
    assert calls == ["cancel"]


@pytest.mark.parametrize(
    "arguments",
    [
        (None, FakeTk(), FakeTtk(), lambda: None, lambda: None),
        (FakeRoot(), None, FakeTtk(), lambda: None, lambda: None),
        (FakeRoot(), FakeTk(), None, lambda: None, lambda: None),
        (FakeRoot(), FakeTk(), FakeTtk(), object(), lambda: None),
        (FakeRoot(), FakeTk(), FakeTtk(), lambda: None, object()),
    ],
)
def test_widget_builder_rejects_missing_toolkit_or_callbacks(
    arguments: tuple[object, object, object, object, object],
) -> None:
    root, tk, ttk, cancel, close = arguments
    with pytest.raises(ProductRequestError):
        create_dashboard_widgets(
            root,
            tk,
            ttk,
            on_cancel=cast(Any, cancel),
            on_close=cast(Any, close),
        )


def test_render_uses_text_for_state_evidence_and_disables_idle_cancel() -> None:
    widgets = create_dashboard_widgets(
        FakeRoot(),
        FakeTk(),
        FakeTtk(),
        on_cancel=lambda: None,
        on_close=lambda: None,
    )
    widgets.render(initial_dashboard_state())

    assert "Simulator" in widgets.source_value.value
    assert "afe/1" in widgets.profile_value.value
    assert "SYNTHETIC" in widgets.evidence_value.value
    assert "Run enabled: no" in widgets.configuration_value.value
    assert "State: IDLE" in widgets.progress_value.value
    assert widgets.progress_bar.config == {"maximum": 1, "value": 0}
    assert widgets.cancel_button.config["state"] == "disabled"
    assert "NO_NEW_HARDWARE_VALIDATION" in widgets.result_value.value
    assert widgets.plot_table.rows == {}

    with pytest.raises(ProductRequestError, match="DashboardState"):
        widgets.render(cast(Any, object()))


def test_render_copies_report_rows_artifacts_and_structured_issue() -> None:
    presenter = DashboardPresenter()
    view = build_human_report_view(load_result_export_json(DC_RESULT))
    publication = HumanReportPublication(
        Path("C:/private/report"),
        (ReportArtifact("report.txt", "text/plain", 12, "a" * 64),),
    )
    presenter.present_report(view, publication)
    presenter.present_issue(issue())
    widgets = create_dashboard_widgets(
        FakeRoot(),
        FakeTk(),
        FakeTtk(),
        on_cancel=lambda: None,
        on_close=lambda: None,
    )

    widgets.render(presenter.state)
    first_rows = dict(widgets.plot_table.rows)
    widgets.render(presenter.state)

    assert first_rows
    assert widgets.plot_table.rows == first_rows
    assert len(widgets.plot_table.rows) == len(view.points)
    assert "Engineering outcome: PASS" in widgets.result_value.value
    assert "Issue: OPERATION_FAILED" in widgets.result_value.value
    assert "Possible cause" in widgets.result_value.value
    assert "report.txt" in widgets.artifacts_value.value
    assert "C:/private" not in widgets.artifacts_value.value
