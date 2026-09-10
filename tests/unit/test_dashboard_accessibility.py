from __future__ import annotations

from analog_validation_app.dashboard.accessibility import (
    TkAccessibilityBridge,
    inspect_tk_accessibility,
)


class FakeAccessibleTk:
    def __init__(
        self,
        *,
        patchlevel: str = "9.1b0",
        screen_reader: object = 1,
        metadata_error: bool = False,
    ) -> None:
        self.patchlevel = patchlevel
        self.screen_reader = screen_reader
        self.metadata_error = metadata_error
        self.calls: list[tuple[object, ...]] = []

    def call(self, *args: object) -> object:
        self.calls.append(args)
        if args == ("info", "patchlevel"):
            return self.patchlevel
        if args == ("tk", "accessible", "check_screenreader"):
            return self.screen_reader
        if self.metadata_error:
            raise RuntimeError("metadata rejected")
        return ""

    def getboolean(self, value: object) -> bool:
        return bool(value)


class FakeRoot:
    def __init__(self, tk: object | None = None) -> None:
        if tk is not None:
            self.tk = tk


class FakeWidget:
    _w = ".field"


def test_inspect_tk_accessibility_reports_supported_runtime_and_reader() -> None:
    tk = FakeAccessibleTk()

    capability = inspect_tk_accessibility(FakeRoot(tk))

    assert capability.tk_patchlevel == "9.1b0"
    assert capability.metadata_api_available is True
    assert capability.screen_reader_active is True
    assert capability.reason == "tk-accessible-available"


def test_bridge_sets_metadata_and_announces_each_distinct_value_once() -> None:
    tk = FakeAccessibleTk()
    bridge = TkAccessibilityBridge(FakeRoot(tk))
    widget = FakeWidget()
    tk.calls.clear()

    assert bridge.describe(
        widget,
        role="Entry",
        name="Replay CSV path",
        description="Path to an existing replay file.",
        help_text="Choose a CSV_REPLAY file before continuing.",
    )
    assert bridge.announce_value(widget, "Replay path is required.")
    assert bridge.announce_value(widget, "Replay path is required.")

    assert tk.calls == [
        ("tk", "accessible", "set_acc_role", ".field", "Entry"),
        ("tk", "accessible", "set_acc_name", ".field", "Replay CSV path"),
        (
            "tk",
            "accessible",
            "set_acc_description",
            ".field",
            "Path to an existing replay file.",
        ),
        (
            "tk",
            "accessible",
            "set_acc_help",
            ".field",
            "Choose a CSV_REPLAY file before continuing.",
        ),
        (
            "tk",
            "accessible",
            "set_acc_value",
            ".field",
            "Replay path is required.",
        ),
        ("tk", "accessible", "emit_selection_change", ".field"),
    ]


def test_bridge_fails_closed_when_runtime_or_metadata_is_unavailable() -> None:
    unavailable = TkAccessibilityBridge(FakeRoot())
    assert unavailable.capability.tk_patchlevel == "unknown"
    assert unavailable.capability.metadata_api_available is False
    assert unavailable.capability.screen_reader_active is None
    assert unavailable.capability.reason == "tk-interpreter-unavailable"
    assert unavailable.describe(FakeWidget(), role="Entry", name="Field") is False
    assert unavailable.announce_value(FakeWidget(), "value") is False

    tk = FakeAccessibleTk(metadata_error=True)
    bridge = TkAccessibilityBridge(FakeRoot(tk))
    assert bridge.describe(FakeWidget(), role="Entry", name="Field") is False
    assert bridge.announce_value(FakeWidget(), "value") is False


def test_inspect_reports_tk_86_without_mistaking_keyboard_focus_for_uia() -> None:
    class Tk86(FakeAccessibleTk):
        def call(self, *args: object) -> object:
            if args == ("info", "patchlevel"):
                return "8.6.15"
            if args == ("tk", "accessible", "check_screenreader"):
                raise RuntimeError("unknown subcommand accessible")
            return super().call(*args)

    capability = inspect_tk_accessibility(FakeRoot(Tk86()))

    assert capability.tk_patchlevel == "8.6.15"
    assert capability.metadata_api_available is False
    assert capability.screen_reader_active is None
    assert capability.reason == "tk-accessible-command-unavailable"


def test_bridge_uses_widget_string_when_tk_path_attribute_is_absent() -> None:
    tk = FakeAccessibleTk(screen_reader=0)
    root = FakeRoot(tk)
    bridge = TkAccessibilityBridge(root)
    widget = object()
    tk.calls.clear()

    assert bridge.capability.screen_reader_active is False
    assert bridge.describe(widget, role="Label", name="Status")
    assert tk.calls[0] == (
        "tk",
        "accessible",
        "set_acc_role",
        str(widget),
        "Label",
    )


def test_inspect_keeps_probing_when_patchlevel_query_is_unavailable() -> None:
    class MissingPatchlevel(FakeAccessibleTk):
        def call(self, *args: object) -> object:
            if args == ("info", "patchlevel"):
                raise RuntimeError("patchlevel unavailable")
            return super().call(*args)

    capability = inspect_tk_accessibility(FakeRoot(MissingPatchlevel()))

    assert capability.tk_patchlevel == "unknown"
    assert capability.metadata_api_available is True
