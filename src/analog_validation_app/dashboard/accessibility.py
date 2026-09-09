"""Runtime-gated Tk accessibility metadata for the local Dashboard."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TkAccessibilityCapability:
    """What the active Tcl/Tk interpreter can expose to assistive technology."""

    tk_patchlevel: str
    metadata_api_available: bool
    screen_reader_active: bool | None
    reason: str


def inspect_tk_accessibility(root: Any) -> TkAccessibilityCapability:
    """Probe the official ``tk accessible`` command without changing OS state."""

    interpreter = getattr(root, "tk", None)
    if interpreter is None:
        return TkAccessibilityCapability(
            tk_patchlevel="unknown",
            metadata_api_available=False,
            screen_reader_active=None,
            reason="tk-interpreter-unavailable",
        )
    try:
        patchlevel = str(interpreter.call("info", "patchlevel"))
    except Exception:  # noqa: BLE001 - injected Tcl/Tk boundary
        patchlevel = "unknown"
    try:
        reader_state = interpreter.call(
            "tk", "accessible", "check_screenreader"
        )
    except Exception:  # noqa: BLE001 - injected Tcl/Tk boundary
        return TkAccessibilityCapability(
            tk_patchlevel=patchlevel,
            metadata_api_available=False,
            screen_reader_active=None,
            reason="tk-accessible-command-unavailable",
        )
    return TkAccessibilityCapability(
        tk_patchlevel=patchlevel,
        metadata_api_available=True,
        screen_reader_active=bool(reader_state),
        reason="tk-accessible-available",
    )


@dataclass(slots=True)
class TkAccessibilityBridge:
    """Apply Tk 9.1 metadata when supported and otherwise fail closed."""

    root: Any
    capability: TkAccessibilityCapability = field(init=False)
    _last_values: dict[str, str] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self.capability = inspect_tk_accessibility(self.root)

    @staticmethod
    def _widget_path(widget: Any) -> str:
        return str(getattr(widget, "_w", widget))

    def describe(
        self,
        widget: Any,
        *,
        role: str,
        name: str,
        description: str | None = None,
        help_text: str | None = None,
    ) -> bool:
        """Assign stable name/role/help metadata on a capable runtime."""

        if not self.capability.metadata_api_available:
            return False
        path = self._widget_path(widget)
        commands: list[tuple[str, str]] = [
            ("set_acc_role", role),
            ("set_acc_name", name),
        ]
        if description is not None:
            commands.append(("set_acc_description", description))
        if help_text is not None:
            commands.append(("set_acc_help", help_text))
        try:
            for operation, value in commands:
                self.root.tk.call("tk", "accessible", operation, path, value)
        except Exception:  # noqa: BLE001 - injected Tcl/Tk boundary
            return False
        return True

    def announce_value(self, widget: Any, value: str) -> bool:
        """Publish one notification when a dynamic text value actually changes."""

        if not self.capability.metadata_api_available:
            return False
        path = self._widget_path(widget)
        if self._last_values.get(path) == value:
            return True
        try:
            self.root.tk.call(
                "tk", "accessible", "set_acc_value", path, value
            )
            self.root.tk.call(
                "tk", "accessible", "emit_selection_change", path
            )
        except Exception:  # noqa: BLE001 - injected Tcl/Tk boundary
            return False
        self._last_values[path] = value
        return True


__all__ = [
    "TkAccessibilityBridge",
    "TkAccessibilityCapability",
    "inspect_tk_accessibility",
]
