"""Legibility and repaint boundaries for the window-local appearance choices."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from analog_validation_app.dashboard.themes import PALETTES, DashboardPalette
from analog_validation_app.dashboard.widgets import _refresh_theme_widgets


def _luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [
        v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels
    ]
    return sum(
        v * weight for v, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True)
    )


def _contrast(foreground: str, background: str) -> float:
    light, dark = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


@pytest.mark.parametrize("palette", PALETTES.values(), ids=PALETTES)
def test_all_text_states_and_chart_legends_have_readable_contrast(
    palette: DashboardPalette,
) -> None:
    pairs = [
        (foreground, background)
        for foreground in (palette.text, palette.muted, palette.accent, palette.success)
        for background in (
            palette.background,
            palette.surface,
            palette.raised,
            palette.header,
        )
    ]
    pairs += [(color, palette.surface) for color in palette.traces]
    pairs += [
        (palette.disabled_text, palette.background),
        (palette.disabled_text, palette.surface),
        (palette.selection_text, palette.selection),
        *(
            (palette.primary_text, color)
            for color in (palette.accent, palette.active, palette.pressed)
        ),
        *(
            (text, color)
            for color in (
                palette.raised,
                palette.hover_surface,
                palette.pressed_surface,
            )
            for text in (palette.text, palette.danger)
        ),
    ]
    for foreground, background in pairs:
        assert _contrast(foreground, background) >= 4.5, (foreground, background)


@pytest.mark.parametrize("high_contrast", [False, True])
def test_repaint_updates_existing_popdown_and_canvas_without_replacing_widgets(
    high_contrast: bool,
) -> None:
    palette = PALETTES["Daylight"]
    canvas = SimpleNamespace(
        _avs_canvas_surface="surface", configure=Mock(), _avs_redraw=Mock()
    )
    scroll = SimpleNamespace(_avs_canvas_surface="background", configure=Mock())
    combo = SimpleNamespace(
        winfo_children=lambda: (), winfo_class=lambda: "TCombobox", tk=Mock()
    )
    combo.tk.call.return_value = ".combo.popdown"
    root = SimpleNamespace(
        winfo_children=lambda: (canvas, scroll, combo), winfo_class=lambda: "Tk"
    )
    _refresh_theme_widgets(root, palette, high_contrast)
    canvas._avs_redraw.assert_called_once_with()
    assert canvas._avs_palette is palette
    canvas.configure.assert_any_call(
        background="SystemWindow" if high_contrast else palette.surface
    )
    scroll.configure.assert_called_once_with(
        background="SystemWindow" if high_contrast else palette.background
    )
    combo.tk.call.assert_any_call(
        ".combo.popdown.f.l",
        "configure",
        "-foreground",
        "SystemWindowText" if high_contrast else palette.text,
    )
