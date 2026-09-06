from __future__ import annotations

from typing import Any, cast

import pytest

from analog_validation.transport import SerialPortInfo
from analog_validation_app import (
    DashboardWizardDraft,
    DashboardWizardState,
    DashboardWizardStep,
    ProductJobType,
    ProductRequestError,
    ProductSourceMode,
    UserIssue,
    UserIssueCode,
    UserIssueSeverity,
)
from analog_validation_app.dashboard import initial_dashboard_state
from analog_validation_app.dashboard.widgets import (
    _bind_mouse_wheel,
    _create_scrollable_page,
    _sync_vertical_scroll_state,
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
        self.visible = False
        self.focus_calls = 0

    def grid(self, **kwargs: object) -> None:
        self.visible = True

    def grid_remove(self) -> None:
        self.visible = False

    def columnconfigure(self, column: object, **kwargs: object) -> None:
        return None

    def rowconfigure(self, row: object, **kwargs: object) -> None:
        return None

    def configure(self, **kwargs: object) -> None:
        self.config.update(kwargs)

    def bind(self, event: str, callback: Any) -> None:
        self.bindings[event] = callback

    def focus_set(self) -> None:
        self.focus_calls += 1

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
        self.all_bindings: dict[str, Any] = {}

    def title(self, value: str) -> None:
        self.window_title = value

    def minsize(self, width: int, height: int) -> None:
        self.minimum = (width, height)

    def bind_all(self, event: str, callback: Any, **kwargs: object) -> None:
        self.all_bindings[event] = callback


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
    def choose_export_path(format_name: str) -> str:
        log.append(("choose-export", format_name))
        return f"chosen-result.{format_name}"

    def choose_coefficient_path(mode: str) -> str:
        log.append(("choose-coefficient", mode))
        return "chosen-coefficients.json"

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
        "on_choose_export_path": choose_export_path,
        "on_export": lambda path, format_name: log.append(
            ("export", path, format_name)
        ),
        "on_choose_coefficient_path": choose_coefficient_path,
        "on_save_coefficients": lambda path: log.append(("save-coefficients", path)),
        "on_load_coefficients": lambda path: log.append(("load-coefficients", path)),
        "on_modify": lambda: log.append("modify"),
        "on_repeat": lambda: log.append("repeat"),
        "on_new_test": lambda: log.append("new-test"),
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

    assert "Step 1 of 6" in widgets.step_value.value
    assert "Why it matters:" in widgets.guidance_value.value
    assert widgets.next_button.config["state"] == "normal"
    assert widgets.run_button.config["state"] == "disabled"
    assert widgets.modify_button.config["state"] == "disabled"
    assert widgets.new_test_button.config["state"] == "disabled"
    assert widgets.export_button.kwargs["style"] == "Primary.TButton"
    assert widgets.new_test_button.kwargs["style"] == "Secondary.TButton"
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
    widgets.form.export_format.set("json")
    widgets.export_browse_button.kwargs["command"]()
    widgets.export_button.kwargs["command"]()
    widgets.coefficient_browse_save_button.kwargs["command"]()
    widgets.coefficient_save_button.kwargs["command"]()
    widgets.coefficient_browse_load_button.kwargs["command"]()
    widgets.coefficient_load_button.kwargs["command"]()
    widgets.finish_button.kwargs["command"]()

    assert log[0:3] == [
        ("source", "SIMULATOR"),
        ("profile", "afe/1"),
        ("job", "READ"),
    ]
    assert log[3] == "next"
    assert log[4][0] == "review"  # type: ignore[index]
    assert isinstance(log[4][1], DashboardWizardDraft)  # type: ignore[index]
    assert log[5] == ("choose-export", "json")
    assert log[6] == ("export", "chosen-result.json", "json")
    assert log[7] == ("choose-coefficient", "save")
    assert log[8] == ("save-coefficients", "chosen-coefficients.json")
    assert log[9] == ("choose-coefficient", "load")
    assert log[10] == ("load-coefficients", "chosen-coefficients.json")
    assert log[11] == "close"


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
    widgets.step_value.set("unchanged-render-sentinel")
    widgets.render(initial_dashboard_state(), wizard)

    assert widgets.step_value.value == "unchanged-render-sentinel"
    assert "Receive-only reviewed" in widgets.review_value.value
    assert "INPUT_DATA" in widgets.issue_value.value
    assert "Export not completed" in widgets.export_value.value
    assert "Replay rejected" in widgets.export_value.value
    assert "MEMORY:1" in widgets.ports_value.value
    assert widgets.export_button.config["state"] == "normal"
    assert widgets.discover_button.config["state"] == "disabled"
    assert widgets.modify_button.config["state"] == "normal"
    assert widgets.repeat_button.config["state"] == "normal"
    assert widgets.new_test_button.config["state"] == "normal"
    assert "Run complete" in widgets.next_steps_value.value
    assert widgets.export_path_input.config["state"] == "normal"
    assert widgets.export_browse_button.config["state"] == "normal"
    with pytest.raises(ProductRequestError, match="DashboardState"):
        widgets.render(cast(Any, object()), wizard)
    with pytest.raises(ProductRequestError, match="DashboardWizardState"):
        widgets.render(initial_dashboard_state(), cast(Any, object()))
    with pytest.raises(ProductRequestError, match="DashboardWizardDraft"):
        widgets.form.load(cast(Any, object()))


def test_configuration_error_keeps_actionable_issue_panel_visible() -> None:
    widgets = create_dashboard_workflow_widgets(
        FakeRoot(), FakeTk(), FakeTtk(), **callbacks([])
    )
    failed = DashboardWizardState(
        1,
        DashboardWizardStep.CONFIGURATION,
        DashboardWizardDraft(sample_count="abc"),
        issue=issue(),
    )

    widgets.render(initial_dashboard_state(), failed)

    assert widgets.section_frames["review"].visible is True
    assert "Replay rejected" in widgets.issue_value.value


def test_frequency_configuration_uses_dedicated_fields_and_preserves_snapshot() -> None:
    widgets = create_dashboard_workflow_widgets(
        FakeRoot(), FakeTk(), FakeTtk(), **callbacks([])
    )
    draft = DashboardWizardDraft(
        job_type=ProductJobType.FREQUENCY_RESPONSE_ANALYSIS,
        frequency_channel="fixture.frequency",
        primary_channel="fixture.input",
        secondary_channel="fixture.output",
        frequency_point_count="41",
        frequency_minimum_hz="20",
        frequency_maximum_hz="20000",
        frequency_input_amplitude="750",
        simulated_cutoff_frequency_hz="1600",
        target_cutoff_frequency_hz="1500",
        cutoff_relative_tolerance="0.08",
        cutoff_drop_db="3.010299956639812",
    )
    wizard = DashboardWizardState(
        1,
        DashboardWizardStep.CONFIGURATION,
        draft,
    )

    widgets.render(initial_dashboard_state(), wizard)

    assert widgets.section_frames["frequency"].visible is True
    assert widgets.section_frames["signal"].visible is False
    assert widgets.section_frames["acceptance"].visible is False
    assert widgets.section_frames["calibration"].visible is False
    assert widgets.form.frequency_channel.get() == "fixture.frequency"
    assert widgets.form.simulated_cutoff_frequency_hz.get() == "1600"
    assert widgets.form.target_cutoff_frequency_hz.get() == "1500"

    widgets.form.target_cutoff_frequency_hz.set("1550")
    widgets.form.frequency_point_count.set("61")
    snapshot = widgets.form.snapshot()
    assert snapshot.job_type is ProductJobType.FREQUENCY_RESPONSE_ANALYSIS
    assert snapshot.frequency_channel == "fixture.frequency"
    assert snapshot.simulated_cutoff_frequency_hz == "1600"
    assert snapshot.target_cutoff_frequency_hz == "1550"
    assert snapshot.frequency_point_count == "61"


def test_live_monitor_configuration_and_result_controls_are_wired() -> None:
    log: list[object] = []
    selected = callbacks(log)
    selected.update(
        {
            "on_pause_live": lambda: log.append("pause-live"),
            "on_resume_live": lambda: log.append("resume-live"),
            "on_live_window": lambda seconds: log.append(("live-window", seconds)),
        }
    )
    widgets = create_dashboard_workflow_widgets(
        FakeRoot(), FakeTk(), FakeTtk(), **selected
    )
    draft = DashboardWizardDraft(
        job_type=ProductJobType.LIVE_MONITOR,
        sample_count="20",
        monitor_sample_interval_seconds="0.1",
        monitor_time_window_seconds="5",
        monitor_max_buffer_points="100",
        monitor_include_secondary=False,
        monitor_include_state=True,
    )
    widgets.render(
        initial_dashboard_state(),
        DashboardWizardState(1, DashboardWizardStep.CONFIGURATION, draft),
    )

    assert widgets.section_frames["monitor"].visible is True
    assert widgets.section_frames["frequency"].visible is False
    snapshot = widgets.form.snapshot()
    assert snapshot.job_type is ProductJobType.LIVE_MONITOR
    assert snapshot.sample_count == "20"
    assert snapshot.monitor_sample_interval_seconds == "0.1"
    assert snapshot.monitor_max_buffer_points == "100"
    assert snapshot.monitor_include_secondary is False
    assert snapshot.monitor_include_state is True

    widgets.result_widgets.pause_button.kwargs["command"]()
    widgets.result_widgets.resume_button.kwargs["command"]()
    widgets.result_widgets.live_window_value.set("15")
    widgets.result_widgets.live_window_select.bindings["<<ComboboxSelected>>"](None)
    assert log[-3:] == ["pause-live", "resume-live", ("live-window", 15.0)]

    widgets.result_widgets.live_window_value.set("not-a-number")
    with pytest.raises(ProductRequestError, match="must be numeric"):
        widgets.result_widgets.live_window_select.bindings["<<ComboboxSelected>>"](None)


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


def test_scrollable_page_tracks_width_and_routes_mouse_wheel() -> None:
    class FakeCanvas(FakeWidget):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, **kwargs)
            self.window_config: dict[str, object] = {}
            self.scroll_calls: list[tuple[int, str]] = []
            self.top_calls: list[float] = []

        def yview(self, *args: object) -> None:
            return None

        def create_window(self, *args: object, **kwargs: object) -> int:
            return 7

        def bbox(self, item: str) -> tuple[int, int, int, int]:
            assert item == "all"
            return (0, 0, 700, 1200)

        def winfo_height(self) -> int:
            return 600

        def itemconfigure(self, item: int, **kwargs: object) -> None:
            assert item == 7
            self.window_config.update(kwargs)

        def yview_scroll(self, amount: int, units: str) -> None:
            self.scroll_calls.append((amount, units))

        def yview_moveto(self, position: float) -> None:
            self.top_calls.append(position)

        def winfo_ismapped(self) -> bool:
            return True

    class FakeScrollbar(FakeWidget):
        def set(self, *args: object) -> None:
            return None

    class ScrollTk:
        Canvas = FakeCanvas

    class ScrollTtk(FakeTtk):
        Scrollbar = FakeScrollbar

    class WidthEvent:
        width = 720

    class WheelEvent:
        delta = -240

    root = FakeRoot()
    page, canvas = _create_scrollable_page(root, ScrollTk(), ScrollTtk())
    assert isinstance(canvas, FakeCanvas)
    page.bindings["<Configure>"](object())
    canvas.bindings["<Configure>"](WidthEvent())

    assert canvas.config["scrollregion"] == (0, 0, 700, 1200)
    assert canvas.window_config["width"] == 720

    _bind_mouse_wheel(root, (canvas, None))
    result = root.all_bindings["<MouseWheel>"](WheelEvent())

    assert result == "break"
    assert canvas.scroll_calls == [(2, "units")]


def test_short_scrollable_page_stays_at_top_and_ignores_mouse_wheel() -> None:
    class ShortCanvas(FakeWidget):
        def __init__(self) -> None:
            super().__init__()
            self.top_calls: list[float] = []
            self.scroll_calls: list[tuple[int, str]] = []

        def bbox(self, item: str) -> tuple[int, int, int, int]:
            assert item == "all"
            return (0, 0, 700, 500)

        def winfo_height(self) -> int:
            return 800

        def yview_moveto(self, position: float) -> None:
            self.top_calls.append(position)

        def yview_scroll(self, amount: int, units: str) -> None:
            self.scroll_calls.append((amount, units))

        def winfo_ismapped(self) -> bool:
            return True

    class WheelEvent:
        delta = -120

    canvas = ShortCanvas()
    scrollbar = FakeWidget()
    scrollbar.grid()

    assert _sync_vertical_scroll_state(canvas, scrollbar) is False
    assert canvas.config["scrollregion"] == (0, 0, 700, 800)
    assert canvas.top_calls == [0.0]
    assert scrollbar.visible is False

    root = FakeRoot()
    _bind_mouse_wheel(root, (canvas,))
    assert root.all_bindings["<MouseWheel>"](WheelEvent()) is None
    assert canvas.scroll_calls == []


def test_scroll_state_defensively_handles_missing_geometry() -> None:
    class MissingBounds(FakeWidget):
        @staticmethod
        def bbox(item: str) -> None:
            assert item == "all"

    class MissingHeight(FakeWidget):
        @staticmethod
        def bbox(item: str) -> tuple[int, int, int, int]:
            assert item == "all"
            return (0, 0, 400, 500)

    class UnlaidOut(MissingHeight):
        @staticmethod
        def winfo_height() -> int:
            return 1

    scrollbar = FakeWidget()
    missing_bounds = MissingBounds()
    missing_height = MissingHeight()
    unlaid_out = UnlaidOut()

    assert _sync_vertical_scroll_state(missing_bounds, scrollbar) is False
    assert _sync_vertical_scroll_state(missing_height, scrollbar) is False
    assert missing_height.config["scrollregion"] == (0, 0, 400, 500)
    assert _sync_vertical_scroll_state(unlaid_out, scrollbar) is False
    assert unlaid_out.config["scrollregion"] == (0, 0, 400, 500)


def test_export_location_chooser_preserves_path_on_cancel_and_rejects_bad_type() -> (
    None
):
    cancel_callbacks = callbacks([])
    cancel_callbacks["on_choose_export_path"] = lambda _format: ""
    cancelled = create_dashboard_workflow_widgets(
        FakeRoot(), FakeTk(), FakeTtk(), **cancel_callbacks
    )
    cancelled.form.export_path.set("existing.json")
    cancelled.export_browse_button.kwargs["command"]()
    assert cancelled.form.export_path.get() == "existing.json"

    invalid_callbacks = callbacks([])
    invalid_callbacks["on_choose_export_path"] = lambda _format: cast(Any, 42)
    invalid = create_dashboard_workflow_widgets(
        FakeRoot(), FakeTk(), FakeTtk(), **invalid_callbacks
    )
    with pytest.raises(ProductRequestError, match="path string"):
        invalid.export_browse_button.kwargs["command"]()


def test_coefficient_location_chooser_preserves_path_on_cancel_and_rejects_bad_type() -> (
    None
):
    cancel_callbacks = callbacks([])
    cancel_callbacks["on_choose_coefficient_path"] = lambda _mode: ""
    cancelled = create_dashboard_workflow_widgets(
        FakeRoot(), FakeTk(), FakeTtk(), **cancel_callbacks
    )
    cancelled.coefficient_path.set("existing.json")
    cancelled.coefficient_browse_save_button.kwargs["command"]()
    assert cancelled.coefficient_path.get() == "existing.json"

    invalid_callbacks = callbacks([])
    invalid_callbacks["on_choose_coefficient_path"] = lambda _mode: cast(Any, 42)
    invalid = create_dashboard_workflow_widgets(
        FakeRoot(), FakeTk(), FakeTtk(), **invalid_callbacks
    )
    with pytest.raises(ProductRequestError, match="path string"):
        invalid.coefficient_browse_load_button.kwargs["command"]()


def test_workflow_tabs_select_current_page_and_reset_its_scroll_position() -> None:
    class FakeNotebook(FakeWidget):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, **kwargs)
            self.pages: list[object] = []
            self.selected: object | None = None

        def add(self, page: object, **kwargs: object) -> None:
            self.pages.append(page)

        def select(self, page: object) -> None:
            self.selected = page

    class NotebookTtk(FakeTtk):
        Notebook = FakeNotebook

    class TopTrackingCanvas:
        def __init__(self) -> None:
            self.positions: list[float] = []

        def yview_moveto(self, position: float) -> None:
            self.positions.append(position)

    widgets = create_dashboard_workflow_widgets(
        FakeRoot(), FakeTk(), NotebookTtk(), **callbacks([])
    )
    workflow_canvas = TopTrackingCanvas()
    result_canvas = TopTrackingCanvas()
    widgets.scroll_canvases = (workflow_canvas, result_canvas)
    source = DashboardWizardState(0, DashboardWizardStep.SOURCE, DashboardWizardDraft())
    result = DashboardWizardState(1, DashboardWizardStep.RESULT, DashboardWizardDraft())

    widgets.render(initial_dashboard_state(), source)
    assert widgets.notebook.selected is widgets.workflow_page
    assert workflow_canvas.positions == [0.0]
    assert widgets.source_select.focus_calls == 1

    widgets.render(initial_dashboard_state(), result)
    assert widgets.notebook.selected is widgets.result_page
    assert result_canvas.positions == [0.0]
    assert widgets.result_widgets.plot_table.focus_calls == 1


def test_step_changes_move_focus_to_a_safe_logical_target() -> None:
    widgets = create_dashboard_workflow_widgets(
        FakeRoot(), FakeTk(), FakeTtk(), **callbacks([])
    )
    draft = DashboardWizardDraft()
    sequence = (
        (DashboardWizardStep.SOURCE, widgets.source_select),
        (DashboardWizardStep.TEST, widgets.job_select),
        (DashboardWizardStep.CONFIGURATION, widgets.primary_channel_input),
        (DashboardWizardStep.REVIEW, widgets.run_button),
        (DashboardWizardStep.RUN, widgets.result_widgets.plot_table),
        (DashboardWizardStep.RESULT, widgets.result_widgets.plot_table),
    )

    for revision, (step, target) in enumerate(sequence):
        before = target.focus_calls
        review_lines = ("Reviewed.",) if step is DashboardWizardStep.REVIEW else ()
        widgets.render(
            initial_dashboard_state(),
            DashboardWizardState(revision, step, draft, review_lines=review_lines),
        )
        assert target.focus_calls == before + 1


def test_each_new_analysis_result_requires_a_fresh_export_destination() -> None:
    widgets = create_dashboard_workflow_widgets(
        FakeRoot(), FakeTk(), FakeTtk(), **callbacks([])
    )
    draft = DashboardWizardDraft(export_path="previous-result.json")
    running = DashboardWizardState(1, DashboardWizardStep.RUN, draft)
    result = DashboardWizardState(
        2,
        DashboardWizardStep.RESULT,
        draft,
        export_available=True,
        export_message="Choose a destination.",
    )

    widgets.render(initial_dashboard_state(), running)
    assert widgets.form.export_path.get() == "previous-result.json"

    widgets.render(initial_dashboard_state(), result)
    assert widgets.form.export_path.get() == ""


def test_mouse_wheel_defensive_paths_and_legacy_binding_are_safe() -> None:
    class WheelEvent:
        def __init__(self, delta: object) -> None:
            self.delta = delta

    class HiddenCanvas:
        @staticmethod
        def winfo_ismapped() -> bool:
            return False

    class VisibleWithoutScroll:
        @staticmethod
        def winfo_ismapped() -> bool:
            return True

    root = FakeRoot()
    _bind_mouse_wheel(root, (HiddenCanvas(), VisibleWithoutScroll()))
    callback = root.all_bindings["<MouseWheel>"]

    assert callback(WheelEvent(0)) is None
    assert callback(WheelEvent("120")) is None
    assert callback(WheelEvent(120)) is None

    class LegacyRoot:
        def __init__(self) -> None:
            self.callback: Any = None

        def bind_all(
            self,
            event: str,
            callback: Any,
            *args: object,
            **kwargs: object,
        ) -> None:
            if kwargs:
                raise TypeError("legacy bind_all has no add keyword")
            self.callback = callback

    legacy_root = LegacyRoot()
    _bind_mouse_wheel(legacy_root, (VisibleWithoutScroll(),))
    assert callable(legacy_root.callback)
