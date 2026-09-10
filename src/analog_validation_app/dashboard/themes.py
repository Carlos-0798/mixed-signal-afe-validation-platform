"""Window-local presentation palettes; no project data or device dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class DashboardPalette:
    background: str
    surface: str
    raised: str
    header: str
    text: str
    muted: str
    accent: str
    primary_text: str
    active: str
    pressed: str
    hover_surface: str
    pressed_surface: str
    border: str
    danger: str
    success: str
    warning: str
    disabled_text: str
    selection: str
    selection_text: str
    violet: str

    @property
    def traces(self) -> tuple[str, ...]:
        return self.accent, self.success, self.warning, self.violet, self.danger


# Muted text, disabled labels and chart legends remain readable on their surfaces.
# The primary action uses its own foreground rather than assuming a dark header.
WORKBENCH = DashboardPalette(
    background="#22262d",
    surface="#2b3038",
    raised="#353c46",
    header="#22262d",
    text="#f2f4f7",
    muted="#c0c7d1",
    accent="#a9cafa",
    primary_text="#18222e",
    active="#bed8fc",
    pressed="#96b9ec",
    hover_surface="#424b57",
    pressed_surface="#3b444f",
    border="#778596",
    danger="#ffb4ad",
    success="#a3d5b6",
    warning="#e8cb94",
    disabled_text="#b0b8c4",
    selection="#415b7b",
    selection_text="#ffffff",
    violet="#d1b9ef",
)
DAYLIGHT = DashboardPalette(
    background="#edf0f4",
    surface="#ffffff",
    raised="#f4f6f9",
    header="#e3e8ef",
    text="#19232f",
    muted="#4e5c6e",
    accent="#215da0",
    primary_text="#ffffff",
    active="#194e89",
    pressed="#133e70",
    hover_surface="#e2e8f0",
    pressed_surface="#d5dfec",
    border="#8190a1",
    danger="#a32f35",
    success="#28603f",
    warning="#795617",
    disabled_text="#596574",
    selection="#215da0",
    selection_text="#ffffff",
    violet="#744294",
)
MIDNIGHT = DashboardPalette(
    background="#101215",
    surface="#191c20",
    raised="#25292f",
    header="#101215",
    text="#e4e7eb",
    muted="#adb5c0",
    accent="#a9bedc",
    primary_text="#111820",
    active="#c1d1e8",
    pressed="#96adce",
    hover_surface="#343b44",
    pressed_surface="#2c323a",
    border="#6b7583",
    danger="#edaaa7",
    success="#9ac7a7",
    warning="#d7c098",
    disabled_text="#9ca6b4",
    selection="#384d67",
    selection_text="#f4f6fa",
    violet="#c6b4df",
)

PALETTES = MappingProxyType(
    {
        "Workbench": WORKBENCH,
        "Daylight": DAYLIGHT,
        "Midnight": MIDNIGHT,
    }
)
