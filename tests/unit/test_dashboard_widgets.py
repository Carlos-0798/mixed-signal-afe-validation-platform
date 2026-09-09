from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from analog_validation import (
    EvidenceSource,
    MeasurementStatus,
    MeasurementUnit,
)
from analog_validation import (
    TestRunOutcome as RunOutcome,
)
from analog_validation.exports import load_result_export_json
from analog_validation_app import (
    HumanReportPublication,
    ProductRequestError,
    ProductResultStatus,
    ReportArtifact,
    UserIssue,
    UserIssueCode,
    UserIssueSeverity,
    build_human_report_view,
)
from analog_validation_app.dashboard import (
    DashboardLivePanel,
    DashboardLivePoint,
    DashboardPresenter,
    DashboardResultPanel,
    initial_dashboard_state,
)
from analog_validation_app.dashboard.widgets import (
    _render_live_chart,
    _result_decision_text,
    _windows_high_contrast_enabled,
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
        self._avs_high_contrast = False

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
            self.configured: dict[str, dict[str, object]] = {}
            self.mapped: dict[str, dict[str, object]] = {}

        def theme_names(self) -> tuple[str, ...]:
            return ("default", "clam")

        def theme_use(self, value: str) -> None:
            self.selected_theme = value

        def configure(self, name: str, **kwargs: object) -> None:
            self.configured[name] = dict(kwargs)

        def map(self, name: str, **kwargs: object) -> None:
            self.mapped[name] = dict(kwargs)

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
    assert style.configured["App.TFrame"]["background"] == "#0b1220"
    assert style.configured["Modern.Treeview"]["rowheight"] == 30
    assert style.configured["TEntry"]["fieldbackground"] == "#17243a"
    assert style.configured["Accent.Horizontal.TProgressbar"]["background"] == (
        "#38bdf8"
    )
    assert "Modern.Treeview" in style.mapped
    assert root.config["background"] == "#0b1220"

    class BrokenTtk:
        @staticmethod
        def Style(*args: object) -> object:
            raise RuntimeError("optional styling is unavailable")

    configure_dashboard_style(root, BrokenTtk())


def test_high_contrast_style_uses_windows_system_colors() -> None:
    class RecordingStyle:
        def __init__(self) -> None:
            self.configured: dict[str, dict[str, object]] = {}
            self.mapped: dict[str, dict[str, object]] = {}

        @staticmethod
        def theme_names() -> tuple[str, ...]:
            return ("clam",)

        @staticmethod
        def theme_use(_value: str) -> None:
            return None

        def configure(self, name: str, **kwargs: object) -> None:
            self.configured[name] = dict(kwargs)

        def map(self, name: str, **kwargs: object) -> None:
            self.mapped[name] = dict(kwargs)

    style = RecordingStyle()

    class RecordingTtk:
        @staticmethod
        def Style(*_args: object) -> RecordingStyle:
            return style

    root = FakeRoot()
    configure_dashboard_style(root, RecordingTtk(), high_contrast=True)

    assert style.configured["."]["background"] == "SystemWindow"
    assert style.configured["."]["foreground"] == "SystemWindowText"
    assert style.configured["Primary.TButton"]["background"] == "SystemHighlight"
    assert style.configured["Primary.TButton"]["foreground"] == ("SystemHighlightText")
    assert style.configured["Card.TLabelframe"]["borderwidth"] == 2
    assert style.configured["Invalid.TEntry"]["borderwidth"] == 3
    assert style.mapped["Modern.Treeview"]["background"] == [
        ("selected", "SystemHighlight")
    ]
    assert root.config["background"] == "SystemWindow"
    assert root._avs_high_contrast is True

    class RigidRoot:
        __slots__ = ("config",)

        def __init__(self) -> None:
            self.config: dict[str, object] = {}

        def configure(self, **kwargs: object) -> None:
            self.config.update(kwargs)

    rigid_root = RigidRoot()
    configure_dashboard_style(rigid_root, RecordingTtk(), high_contrast=False)
    assert rigid_root.config["background"] == "#0b1220"


def test_high_contrast_detection_reads_enabled_bit_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import analog_validation_app.dashboard.widgets as widget_module

    class Key:
        def __enter__(self) -> object:
            return object()

        def __exit__(self, *_args: object) -> None:
            return None

    class Registry:
        HKEY_CURRENT_USER = object()

        @staticmethod
        def OpenKey(*_args: object) -> Key:
            return Key()

        @staticmethod
        def QueryValueEx(*_args: object) -> tuple[str, int]:
            return ("127", 1)

    monkeypatch.setattr(widget_module.sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "winreg", Registry())
    assert _windows_high_contrast_enabled() is True

    class BrokenRegistry(Registry):
        @staticmethod
        def QueryValueEx(*_args: object) -> tuple[str, int]:
            raise OSError("registry unavailable")

    monkeypatch.setitem(sys.modules, "winreg", BrokenRegistry())
    assert _windows_high_contrast_enabled() is False

    monkeypatch.setattr(widget_module.sys, "platform", "linux")
    assert _windows_high_contrast_enabled() is False


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
        widget for widget in ttk.created if widget.kwargs.get("orient") == "vertical"
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

    with pytest.raises(ProductRequestError, match="on_pause"):
        create_dashboard_widgets(
            FakeRoot(),
            FakeTk(),
            FakeTtk(),
            on_cancel=lambda: None,
            on_close=lambda: None,
            on_pause=cast(Any, object()),
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
    assert widgets.pause_button.config["state"] == "disabled"
    assert widgets.resume_button.config["state"] == "disabled"
    assert "Memory eviction is not a transport/event drop" in widgets.live_value.value
    assert "NO ENGINEERING DECISION" in widgets.decision_value.value
    assert "NO_NEW_HARDWARE_VALIDATION" in widgets.decision_value.value
    assert "No finalized product result" in widgets.result_value.value
    assert widgets.plot_table.rows == {}

    with pytest.raises(ProductRequestError, match="DashboardState"):
        widgets.render(cast(Any, object()))


@pytest.mark.parametrize(
    ("status", "outcome", "evidence", "expected"),
    [
        (
            ProductResultStatus.COMPLETED,
            RunOutcome.PASS,
            EvidenceSource.SYNTHETIC,
            ("PASS — reviewed criteria passed", "simulator-generated data only"),
        ),
        (
            ProductResultStatus.COMPLETED,
            None,
            EvidenceSource.CSV_REPLAY,
            ("NO ENGINEERING DECISION", "historical local-file evidence"),
        ),
        (
            ProductResultStatus.INCOMPLETE,
            RunOutcome.INCOMPLETE,
            EvidenceSource.HOST_TEST,
            ("INCOMPLETE", "host-side test evidence"),
        ),
        (
            ProductResultStatus.UNSUPPORTED,
            RunOutcome.UNSUPPORTED,
            EvidenceSource.SPICE_IDEAL,
            ("UNSUPPORTED", "ideal circuit-simulation evidence"),
        ),
        (
            ProductResultStatus.CANCELLED,
            RunOutcome.ABORTED,
            EvidenceSource.BENCH_CONTROLLER,
            ("CANCELLED", "controller-side bench evidence"),
        ),
        (
            ProductResultStatus.ERROR,
            RunOutcome.ERROR,
            EvidenceSource.BENCH_DMM,
            ("ERROR", "DMM bench evidence"),
        ),
        (
            ProductResultStatus.COMPLETED,
            RunOutcome.FAIL,
            EvidenceSource.BENCH_SCOPE,
            ("FAIL — reviewed criteria failed", "scope bench evidence"),
        ),
        (
            ProductResultStatus.COMPLETED,
            RunOutcome.PASS,
            EvidenceSource.SPICE_MODEL,
            ("PASS — reviewed criteria passed", "modeled circuit-simulation evidence"),
        ),
        (
            ProductResultStatus.COMPLETED,
            RunOutcome.PASS,
            EvidenceSource.THEORY,
            ("PASS — reviewed criteria passed", "theoretical evidence"),
        ),
    ],
)
def test_result_decision_summary_keeps_status_outcome_and_evidence_distinct(
    status: ProductResultStatus,
    outcome: RunOutcome | None,
    evidence: EvidenceSource,
    expected: tuple[str, str],
) -> None:
    base = initial_dashboard_state()
    result = DashboardResultPanel(
        status,
        outcome,
        evidence,
        "Final result summary.",
        ("One limitation.",),
        ("Physical AFE performance.",),
    )

    text = _result_decision_text(replace(base, result=result))

    assert expected[0] in text
    assert expected[1] in text
    assert "Claim boundary: NO_NEW_HARDWARE_VALIDATION" in text
    assert "Not verified: Physical AFE performance." in text


def test_live_chart_draws_analog_and_boolean_traces_without_analysis() -> None:
    class ChartCanvas:
        def __init__(self) -> None:
            self.deleted: list[object] = []
            self.lines: list[tuple[tuple[object, ...], dict[str, object]]] = []
            self.text: list[dict[str, object]] = []

        def delete(self, value: object) -> None:
            self.deleted.append(value)

        def create_line(self, *values: object, **kwargs: object) -> None:
            self.lines.append((values, dict(kwargs)))

        def create_text(self, *values: object, **kwargs: object) -> None:
            self.text.append(dict(kwargs))

        def winfo_width(self) -> int:
            return 640

        def winfo_height(self) -> int:
            return 220

    points = (
        DashboardLivePoint(
            1,
            0,
            0.0,
            "afe.ch0.input",
            100.0,
            MeasurementUnit.MILLIVOLT,
            MeasurementStatus.VALID,
        ),
        DashboardLivePoint(
            2,
            1,
            1.0,
            "afe.ch0.input",
            200.0,
            MeasurementUnit.MILLIVOLT,
            MeasurementStatus.VALID,
        ),
        DashboardLivePoint(
            3,
            1,
            1.0,
            "afe.ch0.threshold",
            1.0,
            MeasurementUnit.BOOLEAN,
            MeasurementStatus.VALID,
        ),
    )
    panel = DashboardLivePanel(
        False,
        False,
        False,
        False,
        "Live monitor finished.",
        points,
        3,
        3,
        0,
        3,
        0,
        0,
        0,
        5.0,
    )
    canvas = ChartCanvas()

    _render_live_chart(canvas, panel)

    assert canvas.deleted == ["all"]
    assert len(canvas.lines) >= 3
    labels = {str(item.get("text")) for item in canvas.text}
    assert "afe.ch0.input (mV)" in labels
    assert "afe.ch0.threshold (bool)" in labels


def test_live_chart_handles_empty_and_single_constant_series_with_fallback_size() -> (
    None
):
    class MinimalCanvas:
        def __init__(self) -> None:
            self.lines: list[tuple[object, ...]] = []
            self.text: list[str] = []

        def delete(self, value: object) -> None:
            assert value == "all"

        def create_line(self, *values: object, **kwargs: object) -> None:
            self.lines.append(values)

        def create_text(self, *values: object, **kwargs: object) -> None:
            self.text.append(str(kwargs.get("text")))

    empty = DashboardLivePanel(
        False,
        False,
        False,
        False,
        "Live monitor has no points.",
        (),
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        5.0,
    )
    empty_canvas = MinimalCanvas()
    _render_live_chart(empty_canvas, empty)
    assert "No live samples in the selected time window." in empty_canvas.text

    point = DashboardLivePoint(
        1,
        0,
        0.0,
        "afe.ch0.input",
        100.0,
        MeasurementUnit.MILLIVOLT,
        MeasurementStatus.VALID,
    )
    single = DashboardLivePanel(
        False,
        False,
        False,
        False,
        "Live monitor finished.",
        (point,),
        1,
        1,
        0,
        1,
        0,
        0,
        0,
        5.0,
    )
    single_canvas = MinimalCanvas()
    _render_live_chart(single_canvas, single)
    assert len(single_canvas.lines) >= 2
    assert "afe.ch0.input (mV)" in single_canvas.text


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
    assert "Engineering decision: PASS" in widgets.decision_value.value
    assert "SYNTHETIC" in widgets.decision_value.value
    assert "Follow the safe next step" in widgets.decision_value.value
    assert "Issue: OPERATION_FAILED" in widgets.result_value.value
    assert "Possible cause" in widgets.result_value.value
    assert "report.txt" in widgets.artifacts_value.value
    assert "C:/private" not in widgets.artifacts_value.value
