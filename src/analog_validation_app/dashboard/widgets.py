"""Tk/ttk rendering only; business state and lifecycle live elsewhere."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from analog_validation import EvidenceSource, TestRunOutcome

from ..errors import ProductFieldError, ProductRequestError
from ..models import ProductJobType, ProductResultStatus, ProductSourceMode
from .accessibility import TkAccessibilityBridge
from .state import DashboardLivePanel, DashboardState
from .themes import PALETTES, WORKBENCH, DashboardPalette
from .wizard import (
    DashboardExportFormat,
    DashboardWizardDraft,
    DashboardWizardState,
    DashboardWizardStep,
)

_SOURCE_DISPLAY_NAMES = {
    ProductSourceMode.SIMULATOR: "Simulator — synthetic data",
    ProductSourceMode.CSV_REPLAY: "CSV Replay — local file",
    ProductSourceMode.SERIAL_READ_ONLY: "Serial — read-only",
}
_JOB_DISPLAY_NAMES = {
    ProductJobType.READ: "Read samples",
    ProductJobType.DC_ANALYSIS: "DC analysis",
    ProductJobType.HYSTERESIS_ANALYSIS: "Hysteresis analysis",
    ProductJobType.CALIBRATION_ANALYSIS: "Calibration analysis",
    ProductJobType.FREQUENCY_RESPONSE_ANALYSIS: "Frequency response",
    ProductJobType.LIVE_MONITOR: "Live monitor",
}


def _source_display_name(source: ProductSourceMode) -> str:
    return _SOURCE_DISPLAY_NAMES[source]


def _job_display_name(job: ProductJobType) -> str:
    return _JOB_DISPLAY_NAMES[job]


def _source_value_from_display(value: str) -> ProductSourceMode:
    for source, display in _SOURCE_DISPLAY_NAMES.items():
        if value == display:
            return source
    raise ProductRequestError("source selection must be a listed choice")


def _job_value_from_display(value: str) -> ProductJobType:
    for job, display in _JOB_DISPLAY_NAMES.items():
        if value == display:
            return job
    raise ProductRequestError("test selection must be a listed choice")


def _plain_language_field_guide(source: ProductSourceMode, job: ProductJobType) -> str:
    """Explain the selected source and test without changing product behavior."""

    source_text = {
        ProductSourceMode.SIMULATOR: (
            "Source boundary: Simulator produces SYNTHETIC evidence; it does not "
            "validate hardware."
        ),
        ProductSourceMode.CSV_REPLAY: (
            "Source boundary: Replay reads the CSV you select and produces "
            "CSV_REPLAY evidence; it does not validate hardware."
        ),
        ProductSourceMode.SERIAL_READ_ONLY: (
            "Source boundary: selecting Serial read-only does not discover or open a "
            "port. Discovery and Run remain separate explicit actions, and source "
            "selection alone is not hardware validation."
        ),
    }[source]
    job_text = {
        ProductJobType.READ: (
            "READ collects finite observations and reports data quality; "
            "it does not issue an engineering PASS/FAIL."
        ),
        ProductJobType.DC_ANALYSIS: (
            "DC uses Primary as input and Secondary as output. R-squared closer to 1 "
            "means a straighter fit; lower RMSE means less average fit error. The "
            "reviewed limits decide PASS/FAIL."
        ),
        ProductJobType.HYSTERESIS_ANALYSIS: (
            "Hysteresis uses Primary as the swept signal and State as the boolean "
            "output. Width is the threshold separation between rising and falling "
            "transitions."
        ),
        ProductJobType.CALIBRATION_ANALYSIS: (
            "Calibration compares the Primary reference with the Secondary observed "
            "value. Coefficients can be saved and validated, but they are not applied "
            "automatically."
        ),
        ProductJobType.FREQUENCY_RESPONSE_ANALYSIS: (
            "Frequency response uses frequency, input-amplitude, and output-amplitude "
            "triples. It estimates amplitude cutoff only; it does not measure phase, "
            "run an FFT, or prove hardware bandwidth."
        ),
        ProductJobType.LIVE_MONITOR: (
            "Live Monitor is a finite session with a bounded display buffer. It "
            "reports acquisition and data quality, not an engineering PASS/FAIL."
        ),
    }[job]
    return f"{source_text}\nTest meaning: {job_text}"


def _workflow_action_guidance(wizard: DashboardWizardState) -> str:
    """Describe the real next action using the existing wizard permissions."""

    if wizard.step is DashboardWizardStep.SOURCE:
        return (
            "Next action: choose Source and Profile, then Continue. These selections "
            "only update the draft; they do not open a file or port."
        )
    if wizard.step is DashboardWizardStep.TEST:
        return "Next action: choose one Test, then Continue to its relevant fields."
    if wizard.step is DashboardWizardStep.CONFIGURATION:
        if wizard.issue is not None:
            return (
                "Setup needs attention: correct the highlighted field, then choose "
                "Validate setup again. No acquisition has started."
            )
        return (
            "Next action: complete the enabled fields, then choose Validate setup. "
            "Run stays unavailable until validation succeeds."
        )
    if wizard.step is DashboardWizardStep.REVIEW:
        if wizard.can_run:
            return (
                "Ready to run: review the compiled summary, then choose Run reviewed "
                "test. Previous step returns without starting acquisition."
            )
        return (
            "Run is unavailable because there is no valid compiled review. Return to "
            "the previous step and validate the setup again."
        )
    if wizard.step is DashboardWizardStep.RUN:
        return "Run in progress. Cancellation uses the run panel and waits for cleanup."
    return "Run finished. Use the result actions to save, revise, repeat, or finish."


def _windows_high_contrast_enabled() -> bool:
    """Read the current Windows high-contrast flag without changing OS settings."""

    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Control Panel\Accessibility\HighContrast",
        ) as key:
            flags = int(winreg.QueryValueEx(key, "Flags")[0])
    except (ImportError, OSError, TypeError, ValueError):
        return False
    return bool(flags & 1)


def _configure_high_contrast_style(style: Any, root: Any) -> None:
    """Use Windows system colors so the user's contrast scheme stays authoritative."""

    window = "SystemWindow"
    text = "SystemWindowText"
    highlight = "SystemHighlight"
    highlight_text = "SystemHighlightText"
    disabled = "SystemGrayText"
    style.configure(
        ".",
        background=window,
        foreground=text,
        font=("Segoe UI", 10),
        lightcolor=text,
        darkcolor=text,
        bordercolor=text,
        focuscolor=highlight,
    )
    for name in ("App.TFrame", "Header.TFrame", "Card.TFrame"):
        style.configure(name, background=window)
    style.configure("Accent.TFrame", background=highlight)
    for name in (
        "HeaderEyebrow.TLabel",
        "HeaderTitle.TLabel",
        "HeaderSubtitle.TLabel",
        "Title.TLabel",
        "Step.TLabel",
        "Body.TLabel",
        "Muted.TLabel",
        "Status.TLabel",
        "Evidence.TLabel",
        "Card.TLabelframe.Label",
    ):
        style.configure(name, background=window, foreground=text)
    for name in ("Badge.TLabel", "SafeBadge.TLabel"):
        style.configure(name, background=highlight, foreground=highlight_text)
    style.configure(
        "Card.TLabelframe",
        background=window,
        bordercolor=text,
        relief="solid",
        borderwidth=2,
    )
    style.configure(
        "Primary.TButton",
        background=highlight,
        foreground=highlight_text,
        bordercolor=text,
        borderwidth=2,
    )
    style.map(
        "Primary.TButton",
        background=[("disabled", window), ("!disabled", highlight)],
        foreground=[("disabled", disabled), ("!disabled", highlight_text)],
    )
    for name in ("Secondary.TButton", "Danger.TButton"):
        style.configure(
            name,
            background=window,
            foreground=text,
            bordercolor=text,
            borderwidth=2,
        )
        style.map(
            name,
            background=[
                ("disabled", window),
                ("pressed", highlight),
                ("active", highlight),
            ],
            foreground=[
                ("disabled", disabled),
                ("pressed", highlight_text),
                ("active", highlight_text),
            ],
        )
    style.configure(
        "Modern.Treeview",
        background=window,
        fieldbackground=window,
        foreground=text,
        bordercolor=text,
        borderwidth=2,
    )
    style.configure(
        "Modern.Treeview.Heading",
        background=window,
        foreground=text,
        bordercolor=text,
    )
    style.map(
        "Modern.Treeview",
        background=[("selected", highlight)],
        foreground=[("selected", highlight_text)],
    )
    style.map(
        "Modern.Treeview.Heading",
        background=[("active", highlight)],
        foreground=[("active", highlight_text)],
    )
    style.configure("Modern.TNotebook", background=window)
    style.map(
        "Modern.TNotebook.Tab",
        background=[("selected", highlight), ("!selected", window)],
        foreground=[("selected", highlight_text), ("!selected", text)],
    )
    style.configure(
        "TEntry",
        fieldbackground=window,
        foreground=text,
        insertcolor=text,
        selectbackground=highlight,
        selectforeground=highlight_text,
        bordercolor=text,
        borderwidth=2,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", highlight), ("!focus", text)],
        fieldbackground=[("disabled", window)],
        foreground=[("disabled", disabled)],
    )
    style.configure(
        "TCombobox",
        fieldbackground=window,
        background=window,
        foreground=text,
        arrowcolor=text,
        selectbackground=highlight,
        selectforeground=highlight_text,
        bordercolor=text,
        borderwidth=2,
    )
    style.map(
        "TCombobox",
        bordercolor=[("focus", highlight), ("!focus", text)],
        fieldbackground=[("disabled", window), ("readonly", window)],
        foreground=[("disabled", disabled), ("readonly", text)],
    )
    style.configure(
        "TCheckbutton",
        background=window,
        foreground=text,
        focuscolor=highlight,
    )
    style.map(
        "TCheckbutton",
        background=[("disabled", window), ("active", highlight)],
        foreground=[("disabled", disabled), ("active", highlight_text)],
    )
    for name in ("TEntry", "TCombobox", "TCheckbutton"):
        style.configure(
            f"Invalid.{name}",
            bordercolor=highlight,
            lightcolor=highlight,
            darkcolor=highlight,
            focuscolor=highlight,
            borderwidth=3,
        )
        style.map(
            f"Invalid.{name}",
            bordercolor=[("focus", highlight), ("!focus", highlight)],
        )
    style.configure(
        "TScrollbar",
        background=text,
        troughcolor=window,
        bordercolor=text,
        arrowcolor=window,
    )
    style.configure(
        "Accent.Horizontal.TProgressbar",
        background=highlight,
        troughcolor=window,
        bordercolor=text,
        lightcolor=highlight,
        darkcolor=highlight,
    )
    root_configure = getattr(root, "configure", None)
    if callable(root_configure):
        root_configure(background=window)


def configure_dashboard_style(
    root: Any,
    ttk_module: Any,
    *,
    high_contrast: bool | None = None,
) -> None:
    """Apply the restrained laboratory-console theme when ttk supports styling."""

    palette = getattr(root, "_avs_palette", WORKBENCH)
    use_high_contrast = (
        _windows_high_contrast_enabled() if high_contrast is None else high_contrast
    )
    try:
        root._avs_high_contrast = use_high_contrast
    except Exception:  # noqa: BLE001,S110 - foreign Tk facades may reject attributes
        pass
    style_factory = getattr(ttk_module, "Style", None)
    if not callable(style_factory):
        return
    try:
        try:
            style = style_factory(root)
        except TypeError:
            style = style_factory()
        theme_names = getattr(style, "theme_names", None)
        theme_use = getattr(style, "theme_use", None)
        if callable(theme_names) and callable(theme_use) and "clam" in theme_names():
            theme_use("clam")
        style.configure(
            ".",
            background=palette.background,
            foreground=palette.text,
            font=("Segoe UI", 10),
            lightcolor=palette.border,
            darkcolor=palette.border,
            bordercolor=palette.border,
            focuscolor=palette.accent,
        )
        style.configure("App.TFrame", background=palette.background)
        style.configure("Header.TFrame", background=palette.header)
        style.configure("Accent.TFrame", background=palette.accent)
        style.configure(
            "HeaderEyebrow.TLabel",
            background=palette.header,
            foreground=palette.accent,
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "HeaderTitle.TLabel",
            background=palette.header,
            foreground=palette.text,
            font=("Segoe UI Semibold", 20),
        )
        style.configure(
            "HeaderSubtitle.TLabel",
            background=palette.header,
            foreground=palette.muted,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Badge.TLabel",
            background=palette.raised,
            foreground=palette.accent,
            font=("Segoe UI Semibold", 10),
            padding=(9, 5),
        )
        style.configure(
            "SafeBadge.TLabel",
            background=palette.raised,
            foreground=palette.success,
            font=("Segoe UI Semibold", 10),
            padding=(9, 5),
        )
        style.configure(
            "Card.TLabelframe",
            background=palette.surface,
            bordercolor=palette.border,
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "Card.TLabelframe.Label",
            background=palette.surface,
            foreground=palette.text,
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "Card.TFrame",
            background=palette.surface,
        )
        style.configure(
            "Title.TLabel",
            background=palette.surface,
            foreground=palette.text,
            font=("Segoe UI Semibold", 13),
        )
        style.configure(
            "Step.TLabel",
            background=palette.surface,
            foreground=palette.accent,
            font=("Segoe UI Semibold", 12),
        )
        style.configure(
            "Body.TLabel",
            background=palette.surface,
            foreground=palette.text,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Muted.TLabel",
            background=palette.surface,
            foreground=palette.muted,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Status.TLabel",
            background=palette.surface,
            foreground=palette.accent,
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "Evidence.TLabel",
            background=palette.surface,
            foreground=palette.success,
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "Primary.TButton",
            background=palette.accent,
            foreground=palette.primary_text,
            font=("Segoe UI Semibold", 10),
            padding=(14, 8),
            borderwidth=1,
        )
        style.map(
            "Primary.TButton",
            background=[
                ("disabled", palette.background),
                ("pressed", palette.pressed),
                ("active", palette.active),
            ],
            foreground=[("disabled", palette.disabled_text)],
        )
        style.configure(
            "Secondary.TButton",
            background=palette.raised,
            foreground=palette.text,
            font=("Segoe UI", 10),
            padding=(12, 8),
            bordercolor=palette.border,
            borderwidth=1,
        )
        style.map(
            "Secondary.TButton",
            background=[
                ("disabled", palette.background),
                ("pressed", palette.pressed_surface),
                ("active", palette.hover_surface),
            ],
            foreground=[("disabled", palette.disabled_text)],
        )
        style.configure(
            "Danger.TButton",
            foreground=palette.danger,
            background=palette.raised,
            font=("Segoe UI Semibold", 10),
            padding=(10, 6),
            bordercolor=palette.danger,
            borderwidth=1,
        )
        style.map(
            "Danger.TButton",
            background=[
                ("disabled", palette.background),
                ("pressed", palette.pressed_surface),
                ("active", palette.hover_surface),
            ],
            foreground=[("disabled", palette.disabled_text)],
        )
        style.configure(
            "Modern.Treeview",
            background=palette.surface,
            fieldbackground=palette.surface,
            foreground=palette.text,
            rowheight=30,
            font=("Segoe UI", 10),
            bordercolor=palette.border,
            borderwidth=1,
        )
        style.configure(
            "Modern.Treeview.Heading",
            background=palette.raised,
            foreground=palette.text,
            font=("Segoe UI Semibold", 10),
            padding=(8, 7),
            bordercolor=palette.border,
        )
        style.map(
            "Modern.Treeview",
            background=[("selected", palette.selection)],
            foreground=[("selected", palette.selection_text)],
        )
        style.map(
            "Modern.Treeview.Heading",
            background=[("active", palette.hover_surface)],
        )
        style.configure(
            "Modern.TNotebook",
            background=palette.background,
            borderwidth=0,
            tabmargins=(18, 10, 18, 0),
        )
        style.configure(
            "Modern.TNotebook.Tab",
            font=("Segoe UI Semibold", 10),
            padding=(20, 10),
            borderwidth=0,
        )
        style.map(
            "Modern.TNotebook.Tab",
            background=[
                ("selected", palette.surface),
                ("!selected", palette.background),
            ],
            foreground=[("selected", palette.accent), ("!selected", palette.muted)],
        )
        style.configure(
            "TEntry",
            fieldbackground=palette.raised,
            foreground=palette.text,
            insertcolor=palette.text,
            selectbackground=palette.selection,
            selectforeground=palette.selection_text,
            bordercolor=palette.border,
            padding=(8, 6),
        )
        style.map(
            "TEntry",
            bordercolor=[("focus", palette.accent), ("!focus", palette.border)],
            fieldbackground=[("disabled", palette.background)],
            foreground=[("disabled", palette.disabled_text)],
        )
        style.configure(
            "TCombobox",
            fieldbackground=palette.raised,
            background=palette.raised,
            foreground=palette.text,
            arrowcolor=palette.accent,
            selectbackground=palette.selection,
            selectforeground=palette.selection_text,
            bordercolor=palette.border,
            padding=(7, 5),
        )
        style.map(
            "TCombobox",
            bordercolor=[("focus", palette.accent), ("!focus", palette.border)],
            fieldbackground=[
                ("disabled", palette.background),
                ("readonly", palette.raised),
            ],
            foreground=[
                ("disabled", palette.disabled_text),
                ("readonly", palette.text),
            ],
        )
        style.configure(
            "TCheckbutton",
            background=palette.surface,
            foreground=palette.text,
            focuscolor=palette.accent,
        )
        style.map(
            "TCheckbutton",
            background=[("active", palette.surface)],
            foreground=[("disabled", palette.disabled_text)],
        )
        for name in ("TEntry", "TCombobox", "TCheckbutton"):
            style.configure(
                f"Invalid.{name}",
                bordercolor=palette.danger,
                lightcolor=palette.danger,
                darkcolor=palette.danger,
                focuscolor=palette.danger,
            )
            style.map(
                f"Invalid.{name}",
                bordercolor=[("focus", palette.danger), ("!focus", palette.danger)],
            )
        style.configure(
            "TScrollbar",
            background=palette.raised,
            troughcolor=palette.background,
            bordercolor=palette.background,
            arrowcolor=palette.muted,
        )
        style.configure(
            "Accent.Horizontal.TProgressbar",
            background=palette.accent,
            troughcolor=palette.raised,
            bordercolor=palette.border,
            lightcolor=palette.accent,
            darkcolor=palette.accent,
            thickness=10,
        )
        root_configure = getattr(root, "configure", None)
        if callable(root_configure):
            root_configure(background=palette.background)
        if use_high_contrast:
            _configure_high_contrast_style(style, root)
        option_add = getattr(root, "option_add", None)
        if callable(option_add):
            for option, color in _popdown_colors(palette, use_high_contrast).items():
                option_add(f"*TCombobox*Listbox.{option}", color)
    except Exception:  # noqa: BLE001 - styling is optional; workflow remains usable
        return


def _popdown_colors(palette: DashboardPalette, high_contrast: bool) -> dict[str, str]:
    return {
        "background": "SystemWindow" if high_contrast else palette.raised,
        "foreground": "SystemWindowText" if high_contrast else palette.text,
        "selectBackground": "SystemHighlight" if high_contrast else palette.selection,
        "selectForeground": (
            "SystemHighlightText" if high_contrast else palette.selection_text
        ),
    }


def _refresh_theme_widgets(
    widget: Any, palette: DashboardPalette, high_contrast: bool
) -> None:
    """Repaint existing non-ttk surfaces, preserving their contents and scroll state."""
    surface = getattr(widget, "_avs_canvas_surface", None)
    if surface is not None:
        widget._avs_palette = palette
        widget.configure(
            background="SystemWindow" if high_contrast else getattr(palette, surface)
        )
        if surface == "surface":
            widget.configure(
                highlightbackground=(
                    "SystemWindowText" if high_contrast else palette.border
                )
            )
            widget._avs_redraw()
    children = getattr(widget, "winfo_children", None)
    if not callable(children):
        return
    if widget.winfo_class() == "TCombobox":
        # option_add handles new popdowns; previously opened lists need repainting.
        popdown = widget.tk.call("ttk::combobox::PopdownWindow", str(widget))
        for option, color in _popdown_colors(palette, high_contrast).items():
            widget.tk.call(f"{popdown}.f.l", "configure", f"-{option.lower()}", color)
    for child in children():
        _refresh_theme_widgets(child, palette, high_contrast)


def _create_theme_selector(root: Any, parent: Any, tk: Any, ttk: Any) -> None:
    high_contrast = bool(getattr(root, "_avs_high_contrast", False))
    value = tk.StringVar(
        master=root, value="System contrast" if high_contrast else "Workbench"
    )
    bar = ttk.Frame(parent, style="Header.TFrame")
    bar.grid(row=3, column=1, columnspan=2, sticky="w", pady=(10, 0))
    ttk.Label(bar, text="Appearance (this window)", style="HeaderSubtitle.TLabel").grid(
        row=0, column=0, sticky="w", padx=(0, 10)
    )
    selector = ttk.Combobox(
        bar,
        textvariable=value,
        values=tuple(PALETTES),
        width=18,
        state="disabled" if high_contrast else "readonly",
        takefocus=True,
    )
    selector.grid(row=0, column=1, sticky="w")

    def select_palette() -> None:
        if high_contrast:
            value.set("System contrast")
            return
        palette = PALETTES[value.get()]
        root._avs_palette = palette
        configure_dashboard_style(root, ttk, high_contrast=False)
        _refresh_theme_widgets(root, palette, False)

    _bind_selection(selector, select_palette)
    root._avs_theme_select = selector
    root._avs_theme_value = value


def _callback(name: str, value: object) -> Callable[[], object]:
    if not callable(value):
        raise ProductRequestError(f"{name} must be callable")
    return value


def _result_text(state: DashboardState) -> str:
    result = state.result
    lines = [
        f"Summary: {result.summary}",
        "Limitations:",
        *(f"- {value}" for value in result.limitations),
        "Not verified:",
        *(f"- {value}" for value in result.not_verified),
    ]
    if result.issue is not None:
        lines.extend(
            (
                f"Issue: {result.issue.code.value}",
                f"What happened: {result.issue.what_happened}",
                f"Possible cause: {result.issue.possible_cause}",
                f"Safe next step: {result.issue.safe_next_step}",
            )
        )
    return "\n".join(lines)


def _result_decision_text(state: DashboardState) -> str:
    """Explain copied terminal fields without creating a new conclusion."""

    result = state.result
    status_text = (
        "NOT RUN — no finalized product result exists."
        if result.status is None
        else {
            ProductResultStatus.COMPLETED: (
                "COMPLETED — the workflow reached a finalized product result."
            ),
            ProductResultStatus.INCOMPLETE: (
                "INCOMPLETE — required data or capability was insufficient."
            ),
            ProductResultStatus.UNSUPPORTED: (
                "UNSUPPORTED — the reviewed source cannot perform this request."
            ),
            ProductResultStatus.CANCELLED: (
                "CANCELLED — execution stopped and cleanup reached a terminal state."
            ),
            ProductResultStatus.ERROR: (
                "ERROR — execution ended with a structured software issue."
            ),
        }[result.status]
    )
    outcome_text = (
        "NO ENGINEERING DECISION — no PASS/FAIL was recorded."
        if result.outcome is None
        else {
            TestRunOutcome.PASS: (
                "PASS — reviewed criteria passed for this evidence only."
            ),
            TestRunOutcome.FAIL: ("FAIL — reviewed criteria failed for this evidence."),
            TestRunOutcome.INCOMPLETE: (
                "INCOMPLETE — criteria could not produce a complete conclusion."
            ),
            TestRunOutcome.UNSUPPORTED: (
                "UNSUPPORTED — the requested engineering evaluation did not run."
            ),
            TestRunOutcome.ABORTED: (
                "ABORTED — no PASS/FAIL conclusion survived cancellation."
            ),
            TestRunOutcome.ERROR: (
                "ERROR — no valid engineering conclusion was produced."
            ),
        }[result.outcome]
    )
    evidence_text = (
        "No evidence class is available before a finalized result."
        if result.evidence_source is None
        else {
            EvidenceSource.THEORY: "theoretical evidence; no measurement occurred.",
            EvidenceSource.SYNTHETIC: (
                "simulator-generated data only; no physical hardware was validated."
            ),
            EvidenceSource.CSV_REPLAY: (
                "historical local-file evidence; replay is not a new bench measurement."
            ),
            EvidenceSource.SPICE_IDEAL: (
                "ideal circuit-simulation evidence; no physical circuit was measured."
            ),
            EvidenceSource.SPICE_MODEL: (
                "modeled circuit-simulation evidence; model accuracy is a limitation."
            ),
            EvidenceSource.HOST_TEST: (
                "host-side test evidence; it does not validate attached hardware."
            ),
            EvidenceSource.BENCH_DMM: (
                "DMM bench evidence limited to its recorded setup and lineage."
            ),
            EvidenceSource.BENCH_CONTROLLER: (
                "controller-side bench evidence limited to the recorded interface."
            ),
            EvidenceSource.BENCH_SCOPE: (
                "scope bench evidence limited to its recorded setup and lineage."
            ),
        }[result.evidence_source]
    )
    if result.status is None:
        next_action = "Complete Review and Run before treating this page as a result."
    elif result.issue is not None:
        next_action = "Follow the safe next step in Detailed result below."
    elif result.status is ProductResultStatus.COMPLETED:
        next_action = (
            "Review limitations, then save or continue with the result actions."
        )
    else:
        next_action = "Review limitations and do not report this run as PASS."
    evidence_name = (
        "NONE" if result.evidence_source is None else result.evidence_source.value
    )
    return "\n".join(
        (
            f"Run result: {status_text}",
            f"Engineering decision: {outcome_text}",
            f"Evidence: {evidence_name} — {evidence_text}",
            (
                f"Claim boundary: {state.hardware_claim}. "
                f"Not verified: {result.not_verified[0]}"
            ),
            f"Next action: {next_action}",
        )
    )


def _artifact_text(state: DashboardState) -> str:
    lines = [state.artifacts.summary]
    lines.extend(
        f"- {artifact.name} | {artifact.size_bytes} bytes | SHA-256 {artifact.sha256}"
        for artifact in state.artifacts.artifacts
    )
    return "\n".join(lines)


def _canvas_dimension(canvas: Any, name: str, fallback: int) -> int:
    getter = getattr(canvas, name, None)
    if not callable(getter):
        return fallback
    value = getter()
    return value if isinstance(value, int) and value > 1 else fallback


def _render_live_chart(
    canvas: Any,
    panel: DashboardLivePanel,
    *,
    high_contrast: bool = False,
) -> None:
    """Draw copied live points only; this renderer never evaluates measurements."""

    delete = getattr(canvas, "delete", None)
    create_line = getattr(canvas, "create_line", None)
    create_text = getattr(canvas, "create_text", None)
    if not callable(delete) or not callable(create_line) or not callable(create_text):
        return
    delete("all")
    width = _canvas_dimension(canvas, "winfo_width", 920)
    height = _canvas_dimension(canvas, "winfo_height", 220)
    left, right, top, bottom = 58.0, float(width - 18), 26.0, float(height - 34)
    palette = getattr(canvas, "_avs_palette", WORKBENCH)
    axis_color = "SystemWindowText" if high_contrast else palette.border
    text_color = "SystemWindowText" if high_contrast else palette.muted
    trace_colors = (
        ("SystemHighlight", "SystemWindowText") if high_contrast else palette.traces
    )
    create_line(left, top, left, bottom, right, bottom, fill=axis_color, width=1)
    create_text(left, 12, text="value", anchor="w", fill=text_color)
    create_text(
        right,
        height - 13,
        text="elapsed time (s)",
        anchor="e",
        fill=text_color,
    )
    points = tuple(point for point in panel.points if point.value is not None)
    if not points:
        create_text(
            (left + right) / 2,
            (top + bottom) / 2,
            text="No live samples in the selected time window.",
            fill=text_color,
        )
        return

    x_values = tuple(point.elapsed_seconds for point in points)
    x_min, x_max = min(x_values), max(x_values)
    if x_max <= x_min:
        x_min = float(min(point.index for point in points))
        x_max = float(max(point.index for point in points))
        if x_max <= x_min:
            x_max = x_min + 1.0

        def x_value(point: Any) -> float:
            return float(point.index)

    else:

        def x_value(point: Any) -> float:
            return float(point.elapsed_seconds)

    analog_values = tuple(
        float(point.value)
        for point in points
        if point.unit.value != "bool" and point.value is not None
    )
    y_min = min(analog_values) if analog_values else 0.0
    y_max = max(analog_values) if analog_values else 1.0
    if y_max <= y_min:
        padding = max(abs(y_min) * 0.05, 1.0)
        y_min -= padding
        y_max += padding

    def x_coordinate(point: Any) -> float:
        return left + ((x_value(point) - x_min) / (x_max - x_min)) * (right - left)

    def y_coordinate(point: Any) -> float:
        value = float(point.value)
        if point.unit.value == "bool":
            return top + (0.18 if value else 0.82) * (bottom - top)
        return bottom - ((value - y_min) / (y_max - y_min)) * (bottom - top)

    channels = tuple(dict.fromkeys(point.channel for point in points))
    for index, channel in enumerate(channels):
        color = trace_colors[index % len(trace_colors)]
        channel_points = tuple(point for point in points if point.channel == channel)
        coordinates = tuple(
            coordinate
            for point in channel_points
            for coordinate in (x_coordinate(point), y_coordinate(point))
        )
        if len(channel_points) >= 2:
            create_line(*coordinates, fill=color, width=2, smooth=False)
        elif channel_points:
            x_coord, y_coord = coordinates
            create_line(
                x_coord - 2,
                y_coord,
                x_coord + 2,
                y_coord,
                fill=color,
                width=3,
            )
        create_text(
            left + index * 190,
            height - 13,
            text=f"{channel} ({channel_points[0].unit.value})",
            anchor="w",
            fill=color,
        )


@dataclass(slots=True)
class DashboardWidgets:
    """Widget references updated from one immutable DashboardState."""

    source_value: Any
    profile_value: Any
    connection_value: Any
    evidence_value: Any
    configuration_value: Any
    safety_value: Any
    progress_value: Any
    live_value: Any
    live_window_value: Any
    plot_value: Any
    decision_value: Any
    result_value: Any
    artifacts_value: Any
    accessibility: TkAccessibilityBridge
    progress_label: Any
    live_label: Any
    plot_label: Any
    decision_label: Any
    result_label: Any
    artifacts_label: Any
    progress_bar: Any
    cancel_button: Any
    pause_button: Any
    resume_button: Any
    live_window_select: Any
    live_frame: Any
    live_canvas: Any
    plot_table: Any
    high_contrast: bool = False
    _rendered_revision: int = -1
    _last_live_panel: DashboardLivePanel | None = None

    def redraw_live_chart(self) -> None:
        if self._last_live_panel is not None:
            _render_live_chart(
                self.live_canvas,
                self._last_live_panel,
                high_contrast=self.high_contrast,
            )

    def render(self, state: DashboardState) -> None:
        """Render text and copied report rows; never infer engineering state."""

        if not isinstance(state, DashboardState):
            raise ProductRequestError("state must be a DashboardState")
        if state.revision == self._rendered_revision:
            return
        self.source_value.set(
            f"{state.source.source_name} ({state.source.source_mode.value})\n"
            f"{state.source.source_summary}"
        )
        self.profile_value.set(
            f"{state.source.profile_display_name}\n{state.source.profile_identity}"
        )
        self.connection_value.set(state.source.connection_text)
        self.evidence_value.set(state.source.evidence_text)
        self.configuration_value.set(
            f"{state.configuration.job_name} ({state.configuration.job_type.value})\n"
            f"{state.configuration.summary}\n"
            f"Run enabled: {'yes' if state.configuration.can_run else 'no'}"
        )
        self.safety_value.set(state.configuration.safety_review)
        progress = state.progress
        count = (
            "no numeric progress"
            if progress.total is None
            else f"{progress.completed}/{progress.total}"
        )
        progress_text = (
            f"State: {progress.worker_state.value}\n"
            f"{progress.status_text}\n"
            f"Progress: {count}; events: {progress.event_count}; "
            f"dropped: {progress.dropped_event_count}"
        )
        self.progress_value.set(progress_text)
        self.accessibility.announce_value(self.progress_label, progress_text)
        self.progress_bar.configure(
            maximum=1 if progress.total is None else progress.total,
            value=0 if progress.completed is None else progress.completed,
        )
        self.cancel_button.configure(
            state="normal" if progress.can_cancel else "disabled"
        )
        live = state.live
        live_text = (
            f"{live.summary}\n"
            f"Measurement status totals — valid: {live.valid_points}; "
            f"suspect: {live.suspect_points}; invalid: {live.invalid_points}. "
            f"Pause actions: {live.pause_count}. "
            "Memory eviction is not a transport/event drop."
        )
        self.live_value.set(live_text)
        self.accessibility.announce_value(self.live_label, live_text)
        self.live_window_value.set(format(live.time_window_seconds, "g"))
        self.pause_button.configure(state="normal" if live.can_pause else "disabled")
        self.resume_button.configure(state="normal" if live.can_resume else "disabled")
        self.live_window_select.configure(
            state="readonly"
            if state.configuration.job_type.value == "LIVE_MONITOR"
            else "disabled"
        )
        _set_grid_visible(
            self.live_frame,
            state.configuration.job_type.value == "LIVE_MONITOR",
        )
        self._last_live_panel = live
        self.redraw_live_chart()
        self.plot_value.set(state.plot.summary)
        self.accessibility.announce_value(self.plot_label, state.plot.summary)
        for item in self.plot_table.get_children():
            self.plot_table.delete(item)
        for point in state.plot.points:
            self.plot_table.insert(
                "",
                "end",
                values=(
                    point.index,
                    point.label,
                    point.disposition,
                    "; ".join(point.values),
                ),
            )
        decision_text = _result_decision_text(state)
        result_text = _result_text(state)
        artifact_text = _artifact_text(state)
        self.decision_value.set(decision_text)
        self.result_value.set(result_text)
        self.artifacts_value.set(artifact_text)
        self.accessibility.announce_value(self.decision_label, decision_text)
        self.accessibility.announce_value(self.result_label, result_text)
        self.accessibility.announce_value(self.artifacts_label, artifact_text)
        self._rendered_revision = state.revision


def create_dashboard_widgets(
    root: Any,
    tk_module: Any,
    ttk_module: Any,
    *,
    on_cancel: Callable[[], object],
    on_close: Callable[[], object],
    on_pause: Callable[[], object] | None = None,
    on_resume: Callable[[], object] | None = None,
    on_live_window: Callable[[float], object] | None = None,
    parent: Any | None = None,
    configure_window: bool = True,
) -> DashboardWidgets:
    """Create the six-region local Dashboard using injected Tk modules."""

    cancel = _callback("on_cancel", on_cancel)
    close = _callback("on_close", on_close)
    for name, callback in (
        ("on_pause", on_pause),
        ("on_resume", on_resume),
        ("on_live_window", on_live_window),
    ):
        if callback is not None and not callable(callback):
            raise ProductRequestError(f"{name} must be callable or None")
    pause = on_pause or (lambda: None)
    resume = on_resume or (lambda: None)
    change_window = on_live_window or (lambda _seconds: None)
    if root is None or tk_module is None or ttk_module is None:
        raise ProductRequestError("root, tk_module, and ttk_module are required")
    tk = tk_module
    ttk = ttk_module
    if not isinstance(configure_window, bool):
        raise ProductRequestError("configure_window must be boolean")
    configure_dashboard_style(root, ttk)
    host = root if parent is None else parent
    if configure_window:
        root.title("Analog Validation Studio")
        root.minsize(1040, 760)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

    container = ttk.Frame(host, padding=(18, 14), style="App.TFrame")
    container.grid(row=0, column=0, sticky="nsew")
    container.columnconfigure(0, weight=1)
    container.columnconfigure(1, weight=1)
    container.rowconfigure(3, weight=1)

    source_value = tk.StringVar(master=root, value="")
    profile_value = tk.StringVar(master=root, value="")
    connection_value = tk.StringVar(master=root, value="")
    evidence_value = tk.StringVar(master=root, value="")
    configuration_value = tk.StringVar(master=root, value="")
    safety_value = tk.StringVar(master=root, value="")
    progress_value = tk.StringVar(master=root, value="")
    live_value = tk.StringVar(master=root, value="")
    live_window_value = tk.StringVar(master=root, value="5")
    plot_value = tk.StringVar(master=root, value="")
    decision_value = tk.StringVar(master=root, value="")
    result_value = tk.StringVar(master=root, value="")
    artifacts_value = tk.StringVar(master=root, value="")

    source_frame = ttk.LabelFrame(
        container,
        text="Source & evidence",
        padding=12,
        style="Card.TLabelframe",
    )
    source_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 6))
    ttk.Label(
        source_frame,
        textvariable=source_value,
        wraplength=420,
        style="Body.TLabel",
    ).grid(row=0, column=0, sticky="w")
    ttk.Label(
        source_frame,
        textvariable=profile_value,
        wraplength=420,
        style="Muted.TLabel",
    ).grid(row=1, column=0, sticky="w", pady=(4, 0))
    ttk.Label(
        source_frame,
        textvariable=connection_value,
        wraplength=420,
        style="Muted.TLabel",
    ).grid(row=2, column=0, sticky="w", pady=(4, 0))
    ttk.Label(
        source_frame,
        textvariable=evidence_value,
        wraplength=420,
        style="Evidence.TLabel",
    ).grid(row=3, column=0, sticky="w", pady=(4, 0))

    config_frame = ttk.LabelFrame(
        container,
        text="Reviewed setup & safety boundary",
        padding=12,
        style="Card.TLabelframe",
    )
    config_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 6))
    ttk.Label(
        config_frame,
        textvariable=configuration_value,
        wraplength=420,
        style="Body.TLabel",
    ).grid(row=0, column=0, sticky="w")
    ttk.Label(
        config_frame,
        textvariable=safety_value,
        wraplength=420,
        style="Muted.TLabel",
    ).grid(row=1, column=0, sticky="w", pady=(6, 0))

    progress_frame = ttk.LabelFrame(
        container,
        text="Run status",
        padding=12,
        style="Card.TLabelframe",
    )
    progress_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=6)
    progress_frame.columnconfigure(0, weight=1)
    progress_label = ttk.Label(
        progress_frame,
        textvariable=progress_value,
        wraplength=720,
        style="Status.TLabel",
    )
    progress_label.grid(row=0, column=0, sticky="w")
    progress_bar = ttk.Progressbar(
        progress_frame,
        mode="determinate",
        style="Accent.Horizontal.TProgressbar",
    )
    progress_bar.grid(row=1, column=0, sticky="ew", pady=(6, 0))
    cancel_button = ttk.Button(
        progress_frame,
        text="Cancel run safely",
        command=cancel,
        takefocus=True,
        style="Danger.TButton",
    )
    cancel_button.grid(row=0, column=1, padx=(8, 0))
    if configure_window:
        ttk.Button(
            progress_frame,
            text="Finish & close",
            command=close,
            takefocus=True,
            style="Secondary.TButton",
        ).grid(row=1, column=1, padx=(8, 0), pady=(6, 0))

    live_frame = ttk.LabelFrame(
        container,
        text="Live traces — presentation only",
        padding=12,
        style="Card.TLabelframe",
    )
    live_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=6)
    live_frame.columnconfigure(0, weight=1)
    live_label = ttk.Label(
        live_frame,
        textvariable=live_value,
        wraplength=500,
        justify="left",
        style="Muted.TLabel",
    )
    live_label.grid(row=0, column=0, sticky="w")
    pause_button = ttk.Button(
        live_frame,
        text="Pause display acquisition",
        command=pause,
        takefocus=True,
        style="Secondary.TButton",
    )
    pause_button.grid(row=0, column=1, padx=(8, 0))
    resume_button = ttk.Button(
        live_frame,
        text="Resume acquisition",
        command=resume,
        takefocus=True,
        style="Primary.TButton",
    )
    resume_button.grid(row=0, column=2, padx=(8, 0))
    ttk.Label(live_frame, text="Visible window (s)", style="Muted.TLabel").grid(
        row=0, column=3, padx=(12, 4)
    )
    combobox_factory = getattr(ttk, "Combobox", ttk.Frame)
    live_window_select = combobox_factory(
        live_frame,
        textvariable=live_window_value,
        values=("0.5", "1", "5", "15", "30", "60"),
        state="readonly",
        width=8,
        takefocus=True,
    )
    live_window_select.grid(row=0, column=4, sticky="e")

    def apply_live_window() -> object:
        try:
            seconds = float(live_window_value.get())
        except (TypeError, ValueError) as error:
            raise ProductRequestError("live time window must be numeric") from error
        return change_window(seconds)

    _bind_selection(live_window_select, apply_live_window)
    canvas_factory = getattr(tk, "Canvas", None)
    high_contrast = bool(getattr(root, "_avs_high_contrast", False))
    if callable(canvas_factory):
        live_canvas = canvas_factory(
            live_frame,
            height=220,
            background="SystemWindow" if high_contrast else WORKBENCH.surface,
            highlightthickness=1,
            highlightbackground="SystemWindowText"
            if high_contrast
            else WORKBENCH.border,
        )
        live_canvas._avs_canvas_surface = "surface"
    else:
        live_canvas = ttk.Frame(live_frame, height=220, style="Card.TFrame")
    live_canvas.grid(row=1, column=0, columnspan=5, sticky="nsew", pady=(8, 0))

    plot_frame = ttk.LabelFrame(
        container,
        text="Observations / finalized analysis points",
        padding=12,
        style="Card.TLabelframe",
    )
    plot_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=6)
    plot_frame.columnconfigure(0, weight=1)
    plot_frame.rowconfigure(1, weight=1)
    plot_label = ttk.Label(
        plot_frame,
        textvariable=plot_value,
        wraplength=840,
        style="Muted.TLabel",
    )
    plot_label.grid(row=0, column=0, sticky="w")
    columns = ("index", "label", "disposition", "values")
    plot_table = ttk.Treeview(
        plot_frame,
        columns=columns,
        show="headings",
        height=8,
        takefocus=True,
        style="Modern.Treeview",
    )
    for column, heading, width in (
        ("index", "No.", 55),
        ("label", "Observation / point", 200),
        ("disposition", "Status", 110),
        ("values", "Values copied from the result", 480),
    ):
        plot_table.heading(column, text=heading)
        plot_table.column(column, width=width, stretch=column == "values")
    plot_table.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
    scrollbar_factory = getattr(ttk, "Scrollbar", None)
    yview = getattr(plot_table, "yview", None)
    if callable(scrollbar_factory) and callable(yview):
        scrollbar = scrollbar_factory(
            plot_frame,
            orient="vertical",
            command=yview,
        )
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(6, 0))
        plot_table.configure(yscrollcommand=scrollbar.set)

    result_frame = ttk.LabelFrame(
        container,
        text="Decision summary & evidence boundary",
        padding=12,
        style="Card.TLabelframe",
    )
    result_frame.grid(row=4, column=0, sticky="nsew", padx=(0, 6), pady=(6, 0))
    decision_label = ttk.Label(
        result_frame,
        textvariable=decision_value,
        wraplength=420,
        justify="left",
        style="Status.TLabel",
    )
    decision_label.grid(row=0, column=0, sticky="nw")
    ttk.Label(
        result_frame,
        text="DETAILED RESULT",
        style="Muted.TLabel",
    ).grid(row=1, column=0, sticky="w", pady=(10, 3))
    result_label = ttk.Label(
        result_frame,
        textvariable=result_value,
        wraplength=420,
        justify="left",
        style="Body.TLabel",
    )
    result_label.grid(row=2, column=0, sticky="nw")

    artifacts_frame = ttk.LabelFrame(
        container,
        text="Saved artifacts",
        padding=12,
        style="Card.TLabelframe",
    )
    artifacts_frame.grid(row=4, column=1, sticky="nsew", padx=(6, 0), pady=(6, 0))
    artifacts_label = ttk.Label(
        artifacts_frame,
        textvariable=artifacts_value,
        wraplength=420,
        justify="left",
        style="Body.TLabel",
    )
    artifacts_label.grid(row=0, column=0, sticky="nw")

    accessibility = TkAccessibilityBridge(root)
    for widget, role, name, help_text in (
        (
            progress_label,
            "Label",
            "Run status",
            "Announces worker state, progress counts, and cancellation cleanup.",
        ),
        (
            cancel_button,
            "Button",
            "Cancel run safely",
            "Requests cooperative cancellation and waits for cleanup.",
        ),
        (
            pause_button,
            "Button",
            "Pause display acquisition",
            "Pauses a live monitor at a safe checkpoint.",
        ),
        (
            resume_button,
            "Button",
            "Resume acquisition",
            "Resumes a paused finite live-monitor session.",
        ),
        (
            live_window_select,
            "Combobox",
            "Visible time window",
            "Selects the number of seconds shown by the live chart.",
        ),
        (
            live_label,
            "Label",
            "Live-monitor status",
            "Text alternative for live quality totals and memory eviction.",
        ),
        (
            plot_label,
            "Label",
            "Observation summary",
            "Text summary for the observation table and presentation chart.",
        ),
        (
            plot_table,
            "Table",
            "Observations and finalized analysis points",
            "Rows contain the exact presentation values copied from the result.",
        ),
        (
            decision_label,
            "Label",
            "Decision summary and evidence boundary",
            "Separates execution status, engineering decision, evidence meaning, claim boundary, and next action.",
        ),
        (
            result_label,
            "Label",
            "Detailed result",
            "Reports the copied result summary, limitations, unverified items, and issue recovery.",
        ),
        (
            artifacts_label,
            "Label",
            "Saved artifacts",
            "Reports create-new artifact paths and publication status.",
        ),
    ):
        accessibility.describe(
            widget,
            role=role,
            name=name,
            help_text=help_text,
        )

    widgets = DashboardWidgets(
        source_value=source_value,
        profile_value=profile_value,
        connection_value=connection_value,
        evidence_value=evidence_value,
        configuration_value=configuration_value,
        safety_value=safety_value,
        progress_value=progress_value,
        live_value=live_value,
        live_window_value=live_window_value,
        plot_value=plot_value,
        decision_value=decision_value,
        result_value=result_value,
        artifacts_value=artifacts_value,
        accessibility=accessibility,
        progress_label=progress_label,
        live_label=live_label,
        plot_label=plot_label,
        decision_label=decision_label,
        result_label=result_label,
        artifacts_label=artifacts_label,
        progress_bar=progress_bar,
        cancel_button=cancel_button,
        pause_button=pause_button,
        resume_button=resume_button,
        live_window_select=live_window_select,
        live_frame=live_frame,
        live_canvas=live_canvas,
        plot_table=plot_table,
        high_contrast=high_contrast,
    )
    bind_canvas = getattr(live_canvas, "bind", None)
    if callable(bind_canvas):
        bind_canvas("<Configure>", lambda _event: widgets.redraw_live_chart())
    live_canvas._avs_redraw = widgets.redraw_live_chart
    return widgets


@dataclass(slots=True)
class DashboardFormVariables:
    """Tk variable bundle with one explicit conversion to a validated draft."""

    source: Any
    profile: Any
    job: Any
    primary_channel: Any
    secondary_channel: Any
    state_channel: Any
    operation: Any
    unit: Any
    sample_count: Any
    rising_count: Any
    falling_count: Any
    replay_path: Any
    replay_minimum: Any
    replay_maximum: Any
    serial_port: Any
    serial_baud_rate: Any
    serial_read_timeout: Any
    serial_max_polls: Any
    serial_expected_device_id: Any
    serial_afe_adc_aliases: Any
    serial_confirm_read_only: Any
    low_output_limit: Any
    high_output_limit: Any
    target_gain: Any
    gain_tolerance: Any
    max_abs_offset: Any
    min_r_squared: Any
    max_rmse: Any
    coefficient_id: Any
    coefficient_version: Any
    max_calibration_rmse: Any
    max_calibration_mean_absolute_error: Any
    max_calibration_absolute_error: Any
    minimum_calibration_rmse_reduction: Any
    minimum_high_threshold: Any
    maximum_high_threshold: Any
    minimum_low_threshold: Any
    maximum_low_threshold: Any
    minimum_width: Any
    maximum_width: Any
    maximum_width_span: Any
    export_path: Any
    export_format: Any
    frequency_channel: Any
    frequency_point_count: Any
    frequency_minimum_hz: Any
    frequency_maximum_hz: Any
    frequency_input_amplitude: Any
    simulated_cutoff_frequency_hz: Any
    target_cutoff_frequency_hz: Any
    cutoff_relative_tolerance: Any
    cutoff_drop_db: Any
    monitor_sample_interval_seconds: Any
    monitor_time_window_seconds: Any
    monitor_max_buffer_points: Any
    monitor_include_secondary: Any
    monitor_include_state: Any
    _base_draft: DashboardWizardDraft = field(
        default_factory=DashboardWizardDraft, init=False
    )

    def load(self, draft: DashboardWizardDraft) -> None:
        if not isinstance(draft, DashboardWizardDraft):
            raise ProductRequestError("draft must be a DashboardWizardDraft")
        for name in (
            "primary_channel",
            "secondary_channel",
            "state_channel",
            "frequency_channel",
            "sample_count",
            "rising_count",
            "falling_count",
            "frequency_point_count",
            "frequency_minimum_hz",
            "frequency_maximum_hz",
            "frequency_input_amplitude",
            "simulated_cutoff_frequency_hz",
            "target_cutoff_frequency_hz",
            "cutoff_relative_tolerance",
            "cutoff_drop_db",
            "monitor_sample_interval_seconds",
            "monitor_time_window_seconds",
            "monitor_max_buffer_points",
            "replay_path",
            "replay_minimum",
            "replay_maximum",
            "serial_port",
            "serial_baud_rate",
            "serial_read_timeout",
            "serial_max_polls",
            "serial_expected_device_id",
            "serial_afe_adc_aliases",
            "low_output_limit",
            "high_output_limit",
            "target_gain",
            "gain_tolerance",
            "max_abs_offset",
            "min_r_squared",
            "max_rmse",
            "coefficient_id",
            "coefficient_version",
            "max_calibration_rmse",
            "max_calibration_mean_absolute_error",
            "max_calibration_absolute_error",
            "minimum_calibration_rmse_reduction",
            "minimum_high_threshold",
            "maximum_high_threshold",
            "minimum_low_threshold",
            "maximum_low_threshold",
            "minimum_width",
            "maximum_width",
            "maximum_width_span",
            "export_path",
        ):
            getattr(self, name).set(getattr(draft, name))
        self.source.set(draft.source_mode.value)
        self.profile.set(f"{draft.profile_name}/{draft.profile_version}")
        self.job.set(draft.job_type.value)
        self.operation.set(draft.operation.value)
        self.unit.set(draft.unit.value)
        self.serial_confirm_read_only.set(draft.serial_confirm_read_only)
        self.monitor_include_secondary.set(draft.monitor_include_secondary)
        self.monitor_include_state.set(draft.monitor_include_state)
        self.export_format.set(draft.export_format.value)
        self._base_draft = draft

    def snapshot(self) -> DashboardWizardDraft:
        base = self._base_draft
        values = {
            name: str(getattr(self, name).get())
            for name in (
                "primary_channel",
                "secondary_channel",
                "state_channel",
                "frequency_channel",
                "sample_count",
                "rising_count",
                "falling_count",
                "frequency_point_count",
                "frequency_minimum_hz",
                "frequency_maximum_hz",
                "frequency_input_amplitude",
                "simulated_cutoff_frequency_hz",
                "target_cutoff_frequency_hz",
                "cutoff_relative_tolerance",
                "cutoff_drop_db",
                "monitor_sample_interval_seconds",
                "monitor_time_window_seconds",
                "monitor_max_buffer_points",
                "replay_path",
                "replay_minimum",
                "replay_maximum",
                "serial_port",
                "serial_baud_rate",
                "serial_read_timeout",
                "serial_max_polls",
                "serial_expected_device_id",
                "serial_afe_adc_aliases",
                "low_output_limit",
                "high_output_limit",
                "target_gain",
                "gain_tolerance",
                "max_abs_offset",
                "min_r_squared",
                "max_rmse",
                "coefficient_id",
                "coefficient_version",
                "max_calibration_rmse",
                "max_calibration_mean_absolute_error",
                "max_calibration_absolute_error",
                "minimum_calibration_rmse_reduction",
                "minimum_high_threshold",
                "maximum_high_threshold",
                "minimum_low_threshold",
                "maximum_low_threshold",
                "minimum_width",
                "maximum_width",
                "maximum_width_span",
                "export_path",
            )
        }
        try:
            operation = type(base.operation)(str(self.operation.get()))
        except (TypeError, ValueError) as error:
            raise ProductFieldError(
                "operation must be a listed read operation", "operation"
            ) from error
        try:
            unit = type(base.unit)(str(self.unit.get()))
        except (TypeError, ValueError) as error:
            raise ProductFieldError(
                "unit must be a listed measurement unit", "unit"
            ) from error
        try:
            export_format = DashboardExportFormat(str(self.export_format.get()))
        except (TypeError, ValueError) as error:
            raise ProductFieldError(
                "export_format must be json or csv", "export_format"
            ) from error
        return DashboardWizardDraft(
            source_mode=base.source_mode,
            job_type=base.job_type,
            profile_name=base.profile_name,
            profile_version=base.profile_version,
            operation=operation,
            unit=unit,
            serial_confirm_read_only=bool(self.serial_confirm_read_only.get()),
            monitor_include_secondary=bool(self.monitor_include_secondary.get()),
            monitor_include_state=bool(self.monitor_include_state.get()),
            export_format=export_format,
            **values,
        )


@dataclass(slots=True)
class DashboardWorkflowWidgets:
    """Six-step controls plus the existing finalized-result renderer."""

    result_widgets: DashboardWidgets
    accessibility: TkAccessibilityBridge
    form: DashboardFormVariables
    guidance_value: Any
    step_value: Any
    field_help_value: Any
    action_guidance_value: Any
    source_display_value: Any
    job_display_value: Any
    review_value: Any
    issue_value: Any
    ports_value: Any
    export_value: Any
    coefficient_value: Any
    next_steps_value: Any
    step_label: Any
    guidance_label: Any
    issue_label: Any
    source_select: Any
    profile_select: Any
    job_select: Any
    primary_channel_input: Any
    replay_browse_button: Any
    serial_port_select: Any
    export_path_input: Any
    export_browse_button: Any
    export_format_select: Any
    coefficient_path: Any
    coefficient_path_input: Any
    coefficient_browse_save_button: Any
    coefficient_browse_load_button: Any
    coefficient_save_button: Any
    coefficient_load_button: Any
    back_button: Any
    next_button: Any
    review_button: Any
    run_button: Any
    export_button: Any
    discover_button: Any
    modify_button: Any
    repeat_button: Any
    new_test_button: Any
    finish_button: Any
    notebook: Any
    workflow_page: Any
    result_page: Any
    section_frames: dict[str, Any]
    field_controls: dict[str, tuple[Any, str, str, str]]
    issue_field_id: str | None = None
    scroll_canvases: tuple[Any, Any] = (None, None)
    editable_controls: tuple[
        tuple[Any, str, tuple[str, ...], tuple[str, ...]], ...
    ] = ()
    _rendered_dashboard_revision: int = -1
    _rendered_wizard_revision: int = -1
    _current_draft: DashboardWizardDraft = field(default_factory=DashboardWizardDraft)
    _last_step: DashboardWizardStep | None = None
    _highlighted_field_id: str | None = None
    _rendered_issue_field_id: str | None = None

    def render(self, dashboard: DashboardState, wizard: DashboardWizardState) -> None:
        if not isinstance(dashboard, DashboardState):
            raise ProductRequestError("dashboard must be a DashboardState")
        if not isinstance(wizard, DashboardWizardState):
            raise ProductRequestError("wizard must be a DashboardWizardState")
        if self.issue_field_id is not None and not isinstance(self.issue_field_id, str):
            raise ProductRequestError("issue_field_id must be a string or None")
        issue_field_id = self.issue_field_id
        dashboard_changed = dashboard.revision != self._rendered_dashboard_revision
        wizard_changed = (
            wizard.revision != self._rendered_wizard_revision
            or issue_field_id != self._rendered_issue_field_id
        )
        if not dashboard_changed and not wizard_changed:
            return
        if dashboard_changed:
            self.result_widgets.render(dashboard)
            self._rendered_dashboard_revision = dashboard.revision
        if not wizard_changed:
            return
        if self._highlighted_field_id is not None:
            previous = self.field_controls.get(self._highlighted_field_id)
            if previous is not None:
                previous[0].configure(style=previous[1])
            self._highlighted_field_id = None
        guidance = wizard.guidance
        steps = (
            "01 Source",
            "02 Test",
            "03 Configure",
            "04 Review",
            "05 Run",
            "06 Result",
        )
        step_text = (
            "   ·   ".join(steps)
            + f"\nStep {guidance.number} of 6  —  {guidance.title}"
        )
        self.step_value.set(step_text)
        self.accessibility.announce_value(self.step_label, step_text)
        guidance_text = (
            f"{guidance.what}\n"
            f"Why it matters: {guidance.why}\n"
            f"Before continuing: {guidance.confirm}"
        )
        self.guidance_value.set(guidance_text)
        source = wizard.draft.source_mode.value
        job = wizard.draft.job_type.value
        self.field_help_value.set(
            _plain_language_field_guide(wizard.draft.source_mode, wizard.draft.job_type)
        )
        self.action_guidance_value.set(_workflow_action_guidance(wizard))
        self.source_display_value.set(_source_display_name(wizard.draft.source_mode))
        self.job_display_value.set(_job_display_name(wizard.draft.job_type))
        self.review_value.set(
            "Configuration has not been compiled."
            if not wizard.review_lines
            else "\n".join(f"- {line}" for line in wizard.review_lines)
        )
        lookup_field_id = (
            "frequency_unit"
            if issue_field_id == "unit" and job == "FREQUENCY_RESPONSE_ANALYSIS"
            else issue_field_id
        )
        field_control = (
            self.field_controls.get(lookup_field_id)
            if wizard.issue is not None and lookup_field_id is not None
            else None
        )
        field_guidance = (
            ""
            if field_control is None
            else (
                f"\nField to correct: {field_control[3]}. "
                "The cursor moved to this highlighted field."
            )
        )
        issue_text = (
            "No issue."
            if wizard.issue is None
            else (
                f"{wizard.issue.severity.value} [{wizard.issue.code.value}]\n"
                f"What happened: {wizard.issue.what_happened}\n"
                f"Possible cause: {wizard.issue.possible_cause}\n"
                f"Safe next step: {wizard.issue.safe_next_step}"
                f"{field_guidance}"
            )
        )
        self.issue_value.set(issue_text)
        self.accessibility.announce_value(self.issue_label, issue_text)
        self.ports_value.set(
            "Ports not discovered. Discovery never opens a port."
            if not wizard.discovered_ports
            else "Discovered logical IDs: "
            + ", ".join(port.port_id for port in wizard.discovered_ports)
        )
        self.export_value.set(
            "Export not completed.\n" + issue_text
            if wizard.step is DashboardWizardStep.RESULT and wizard.issue is not None
            else wizard.export_message
        )
        self.coefficient_value.set(wizard.coefficient_message)
        self.next_steps_value.set(
            (
                "Run complete. Save the analysis first if needed, then choose exactly "
                "one next action. Modifying preserves the visible result as a reference; "
                "starting a new test resets the form."
            )
            if wizard.step is DashboardWizardStep.RESULT
            else "Result actions become available after the current workflow finishes."
        )
        self.source_select.configure(
            values=tuple(_source_display_name(mode) for mode in wizard.source_modes)
        )
        self.profile_select.configure(values=wizard.profile_identities)
        self.job_select.configure(
            values=tuple(_job_display_name(job_type) for job_type in wizard.job_types)
        )
        self.serial_port_select.configure(
            values=tuple(port.port_id for port in wizard.discovered_ports)
        )
        self.source_select.configure(
            state=(
                "readonly" if wizard.step is DashboardWizardStep.SOURCE else "disabled"
            )
        )
        self.profile_select.configure(
            state=(
                "readonly" if wizard.step is DashboardWizardStep.SOURCE else "disabled"
            )
        )
        self.job_select.configure(
            state=(
                "readonly" if wizard.step is DashboardWizardStep.TEST else "disabled"
            )
        )
        for control, active_state, jobs, sources in self.editable_controls:
            enabled = (
                wizard.step is DashboardWizardStep.CONFIGURATION
                and (not jobs or job in jobs)
                and (not sources or source in sources)
            )
            control.configure(state=active_state if enabled else "disabled")
        export_state = "normal" if wizard.can_export else "disabled"
        self.export_path_input.configure(state=export_state)
        self.export_browse_button.configure(state=export_state)
        self.export_format_select.configure(
            state="readonly" if wizard.can_export else "disabled"
        )
        self.coefficient_path_input.configure(
            state="normal" if wizard.can_load_coefficients else "disabled"
        )
        self.coefficient_browse_save_button.configure(
            state="normal" if wizard.can_save_coefficients else "disabled"
        )
        self.coefficient_browse_load_button.configure(
            state="normal" if wizard.can_load_coefficients else "disabled"
        )
        self.coefficient_save_button.configure(
            state="normal" if wizard.can_save_coefficients else "disabled"
        )
        self.coefficient_load_button.configure(
            state="normal" if wizard.can_load_coefficients else "disabled"
        )
        for button, enabled in (
            (
                self.back_button,
                wizard.can_back and wizard.step is not DashboardWizardStep.RESULT,
            ),
            (self.next_button, wizard.can_next),
            (self.review_button, wizard.can_prepare_review),
            (self.run_button, wizard.can_run),
            (self.export_button, wizard.can_export),
            (
                self.discover_button,
                wizard.draft.source_mode.value == "SERIAL_READ_ONLY"
                and wizard.step.value in {"SOURCE", "CONFIGURATION"},
            ),
            (self.modify_button, wizard.can_modify_setup),
            (self.repeat_button, wizard.can_review_same_setup),
            (self.new_test_button, wizard.can_start_new_test),
            (self.finish_button, wizard.step is not DashboardWizardStep.RUN),
        ):
            button.configure(state="normal" if enabled else "disabled")
        step = wizard.step
        _set_grid_visible(
            self.section_frames["setup"],
            step
            in {
                DashboardWizardStep.SOURCE,
                DashboardWizardStep.TEST,
                DashboardWizardStep.CONFIGURATION,
            },
        )
        _set_grid_visible(
            self.section_frames["signal"],
            step is DashboardWizardStep.CONFIGURATION
            and job != "FREQUENCY_RESPONSE_ANALYSIS",
        )
        _set_grid_visible(
            self.section_frames["acceptance"],
            step is DashboardWizardStep.CONFIGURATION
            and job in {"DC_ANALYSIS", "HYSTERESIS_ANALYSIS"},
        )
        _set_grid_visible(
            self.section_frames["calibration"],
            step is DashboardWizardStep.CONFIGURATION and job == "CALIBRATION_ANALYSIS",
        )
        _set_grid_visible(
            self.section_frames["frequency"],
            step is DashboardWizardStep.CONFIGURATION
            and job == "FREQUENCY_RESPONSE_ANALYSIS",
        )
        _set_grid_visible(
            self.section_frames["monitor"],
            step is DashboardWizardStep.CONFIGURATION and job == "LIVE_MONITOR",
        )
        _set_grid_visible(
            self.section_frames["source_connection"],
            step
            in {
                DashboardWizardStep.SOURCE,
                DashboardWizardStep.CONFIGURATION,
            }
            and source in {"CSV_REPLAY", "SERIAL_READ_ONLY"},
        )
        _set_grid_visible(
            self.section_frames["replay_source"],
            step
            in {
                DashboardWizardStep.SOURCE,
                DashboardWizardStep.CONFIGURATION,
            }
            and source == "CSV_REPLAY",
        )
        _set_grid_visible(
            self.section_frames["serial_source"],
            step
            in {
                DashboardWizardStep.SOURCE,
                DashboardWizardStep.CONFIGURATION,
            }
            and source == "SERIAL_READ_ONLY",
        )
        _set_grid_visible(
            self.section_frames["field_guide"],
            step is DashboardWizardStep.CONFIGURATION,
        )
        _set_grid_visible(
            self.section_frames["review"],
            step is DashboardWizardStep.REVIEW or wizard.issue is not None,
        )
        _set_grid_visible(
            self.section_frames["workflow_actions"],
            step
            in {
                DashboardWizardStep.SOURCE,
                DashboardWizardStep.TEST,
                DashboardWizardStep.CONFIGURATION,
                DashboardWizardStep.REVIEW,
            },
        )
        _set_grid_visible(
            self.section_frames["export"],
            step is DashboardWizardStep.RESULT,
        )
        _set_grid_visible(
            self.section_frames["coefficients"],
            step is DashboardWizardStep.RESULT,
        )
        _set_grid_visible(
            self.section_frames["result_actions"],
            step is DashboardWizardStep.RESULT,
        )
        selector = getattr(self.notebook, "select", None)
        if callable(selector):
            selector(
                self.result_page
                if step in {DashboardWizardStep.RUN, DashboardWizardStep.RESULT}
                else self.workflow_page
            )
        if self._last_step is not step:
            canvas = (
                self.scroll_canvases[1]
                if step in {DashboardWizardStep.RUN, DashboardWizardStep.RESULT}
                else self.scroll_canvases[0]
            )
            move_to_top = getattr(canvas, "yview_moveto", None)
            if callable(move_to_top):
                move_to_top(0.0)
        should_load = (
            self._rendered_wizard_revision < 0
            or wizard.draft != self._current_draft
            or (
                self._last_step is DashboardWizardStep.RESULT
                and wizard.step is DashboardWizardStep.SOURCE
            )
        )
        if should_load:
            self.form.load(wizard.draft)
        if (
            self._last_step is DashboardWizardStep.RUN
            and wizard.step is DashboardWizardStep.RESULT
        ):
            # Every finalized analysis starts with a fresh create-new destination.
            self.form.export_path.set("")
        if field_control is not None and lookup_field_id is not None:
            field_control[0].configure(style=f"Invalid.{field_control[1]}")
            self._highlighted_field_id = lookup_field_id
            _focus_and_reveal_control(
                self.scroll_canvases[
                    1 if field_control[2] in {"export", "coefficients"} else 0
                ],
                field_control[0],
            )
        elif self._last_step is not wizard.step:
            focus_target = {
                DashboardWizardStep.SOURCE: self.source_select,
                DashboardWizardStep.TEST: self.job_select,
                DashboardWizardStep.CONFIGURATION: self.primary_channel_input,
                DashboardWizardStep.REVIEW: self.run_button,
                DashboardWizardStep.RUN: self.result_widgets.plot_table,
                DashboardWizardStep.RESULT: self.result_widgets.plot_table,
            }[wizard.step]
            set_focus = getattr(focus_target, "focus_set", None)
            if callable(set_focus):
                set_focus()
        self._rendered_wizard_revision = wizard.revision
        self._rendered_issue_field_id = issue_field_id
        self._current_draft = wizard.draft
        self._last_step = wizard.step


def _focus_and_reveal_control(canvas: Any, control: Any) -> None:
    """Move keyboard focus and scroll a nested control into the visible page."""

    update = getattr(control, "update_idletasks", None)
    if callable(update):
        update()
    if canvas is not None:
        canvas_root_y = getattr(canvas, "winfo_rooty", None)
        canvas_height = getattr(canvas, "winfo_height", None)
        control_root_y = getattr(control, "winfo_rooty", None)
        control_height = getattr(control, "winfo_height", None)
        canvas_bbox = getattr(canvas, "bbox", None)
        canvas_yview = getattr(canvas, "yview", None)
        canvas_move = getattr(canvas, "yview_moveto", None)
        if (
            callable(canvas_root_y)
            and callable(canvas_height)
            and callable(control_root_y)
            and callable(control_height)
            and callable(canvas_bbox)
            and callable(canvas_yview)
            and callable(canvas_move)
        ):
            top = int(control_root_y())
            bottom = top + int(control_height())
            visible_top = int(canvas_root_y())
            visible_height = int(canvas_height())
            visible_bottom = visible_top + visible_height
            if top < visible_top or bottom > visible_bottom:
                bounds = canvas_bbox("all")
                view = canvas_yview()
                if (
                    isinstance(bounds, tuple)
                    and len(bounds) == 4
                    and isinstance(view, tuple)
                    and len(view) == 2
                ):
                    content_height = max(1, int(bounds[3]) - int(bounds[1]))
                    current_offset = float(view[0]) * content_height
                    target_offset = current_offset + top - visible_top - 24
                    maximum_offset = max(0, content_height - visible_height)
                    canvas_move(
                        min(max(target_offset, 0), maximum_offset) / content_height
                    )
    set_focus = getattr(control, "focus_set", None)
    if callable(set_focus):
        set_focus()


def _bind_selection(widget: Any, callback: Callable[[], object]) -> None:
    binder = getattr(widget, "bind", None)
    if callable(binder):
        binder("<<ComboboxSelected>>", lambda _event: callback())


def _set_grid_visible(widget: Any, visible: bool) -> None:
    """Use progressive disclosure when real Tk geometry methods are available."""

    method = getattr(widget, "grid" if visible else "grid_remove", None)
    if callable(method):
        method()


def _create_scrollable_page(
    parent: Any,
    tk_module: Any,
    ttk_module: Any,
    *,
    high_contrast: bool = False,
) -> tuple[Any, Any | None]:
    """Create a top-anchored page that scrolls only when its content overflows."""

    canvas_factory = getattr(tk_module, "Canvas", None)
    scrollbar_factory = getattr(ttk_module, "Scrollbar", None)
    if not callable(canvas_factory) or not callable(scrollbar_factory):
        page = ttk_module.Frame(parent, style="App.TFrame")
        page.grid(row=0, column=0, sticky="nsew")
        return page, None

    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(0, weight=1)
    host = ttk_module.Frame(parent, style="App.TFrame")
    host.grid(row=0, column=0, sticky="nsew")
    host.columnconfigure(0, weight=1)
    host.rowconfigure(0, weight=1)
    canvas = canvas_factory(
        host,
        background="SystemWindow" if high_contrast else WORKBENCH.background,
        borderwidth=0,
        highlightthickness=0,
        yscrollincrement=32,
    )
    canvas._avs_canvas_surface = "background"
    scrollbar = scrollbar_factory(host, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    scrollbar.grid_remove()
    canvas._avs_vertical_overflow = False
    page = ttk_module.Frame(canvas, style="App.TFrame")
    window_id = canvas.create_window((0, 0), window=page, anchor="nw")

    def sync_scroll_region(_event: object) -> None:
        _sync_vertical_scroll_state(canvas, scrollbar)

    def sync_page_width(event: object) -> None:
        width = getattr(event, "width", None)
        if isinstance(width, int) and width > 0:
            canvas.itemconfigure(window_id, width=width)
        _sync_vertical_scroll_state(canvas, scrollbar)

    page.bind("<Configure>", sync_scroll_region)
    canvas.bind("<Configure>", sync_page_width)
    return page, canvas


def _sync_vertical_scroll_state(canvas: Any, scrollbar: Any) -> bool:
    """Clamp short pages to the top and expose scrolling only for overflow."""

    bbox = canvas.bbox("all")
    if not isinstance(bbox, tuple) or len(bbox) != 4:
        return False
    height_getter = getattr(canvas, "winfo_height", None)
    if not callable(height_getter):
        canvas.configure(scrollregion=bbox)
        return False
    viewport_height = height_getter()
    if not isinstance(viewport_height, int) or viewport_height <= 1:
        canvas.configure(scrollregion=bbox)
        return False
    left, top, right, bottom = bbox
    content_height = bottom - top
    overflow = content_height > viewport_height + 1
    scroll_bottom = bottom if overflow else top + viewport_height
    canvas.configure(scrollregion=(left, top, right, scroll_bottom))
    canvas._avs_vertical_overflow = overflow
    if not overflow:
        move_to = getattr(canvas, "yview_moveto", None)
        if callable(move_to):
            move_to(0.0)
    if overflow:
        scrollbar.grid()
    else:
        scrollbar.grid_remove()
    return overflow


def _bind_mouse_wheel(root: Any, canvases: tuple[Any, ...]) -> None:
    """Route the Windows mouse wheel to the currently visible workflow page."""

    available = tuple(canvas for canvas in canvases if canvas is not None)
    bind_all = getattr(root, "bind_all", None)
    if not available or not callable(bind_all):
        return

    def scroll_visible_page(event: object) -> str | None:
        delta = getattr(event, "delta", 0)
        if not isinstance(delta, int) or delta == 0:
            return None
        for canvas in available:
            is_mapped = getattr(canvas, "winfo_ismapped", None)
            if callable(is_mapped) and not is_mapped():
                continue
            if not bool(getattr(canvas, "_avs_vertical_overflow", True)):
                continue
            scroll = getattr(canvas, "yview_scroll", None)
            if callable(scroll):
                steps = max(1, abs(delta) // 120)
                scroll(-steps if delta > 0 else steps, "units")
                return "break"
        return None

    try:
        bind_all("<MouseWheel>", scroll_visible_page, add="+")
    except TypeError:
        bind_all("<MouseWheel>", scroll_visible_page)


def create_dashboard_workflow_widgets(
    root: Any,
    tk_module: Any,
    ttk_module: Any,
    *,
    on_source: Callable[[str], object],
    on_profile: Callable[[str], object],
    on_job: Callable[[str], object],
    on_back: Callable[[], object],
    on_next: Callable[[], object],
    on_review: Callable[[DashboardWizardDraft | BaseException], object],
    on_run: Callable[[], object],
    on_cancel: Callable[[], object],
    on_discover: Callable[[], object],
    on_choose_export_path: Callable[[str], str | None],
    on_export: Callable[[str, str], object],
    on_modify: Callable[[], object],
    on_repeat: Callable[[], object],
    on_new_test: Callable[[], object],
    on_close: Callable[[], object],
    on_choose_replay_path: Callable[[], str | None] | None = None,
    on_choose_coefficient_path: Callable[[str], str | None] | None = None,
    on_save_coefficients: Callable[[str], object] | None = None,
    on_load_coefficients: Callable[[str], object] | None = None,
    on_pause_live: Callable[[], object] | None = None,
    on_resume_live: Callable[[], object] | None = None,
    on_live_window: Callable[[float], object] | None = None,
) -> DashboardWorkflowWidgets:
    """Create the guided UI while keeping every decision in headless layers."""

    callbacks = {
        name: value
        for name, value in (
            ("on_source", on_source),
            ("on_profile", on_profile),
            ("on_job", on_job),
            ("on_back", on_back),
            ("on_next", on_next),
            ("on_review", on_review),
            ("on_run", on_run),
            ("on_cancel", on_cancel),
            ("on_discover", on_discover),
            ("on_choose_export_path", on_choose_export_path),
            ("on_export", on_export),
            ("on_modify", on_modify),
            ("on_repeat", on_repeat),
            ("on_new_test", on_new_test),
            ("on_close", on_close),
        )
    }
    for name, callback in callbacks.items():
        if not callable(callback):
            raise ProductRequestError(f"{name} must be callable")
    for optional_name, optional_callback in (
        ("on_choose_replay_path", on_choose_replay_path),
        ("on_choose_coefficient_path", on_choose_coefficient_path),
        ("on_save_coefficients", on_save_coefficients),
        ("on_load_coefficients", on_load_coefficients),
        ("on_pause_live", on_pause_live),
        ("on_resume_live", on_resume_live),
        ("on_live_window", on_live_window),
    ):
        if optional_callback is not None and not callable(optional_callback):
            raise ProductRequestError(f"{optional_name} must be callable or None")
    choose_replay_path_callback = on_choose_replay_path or (lambda: "")
    choose_coefficient_path_callback = on_choose_coefficient_path or (lambda _mode: "")
    save_coefficients_callback = on_save_coefficients or (lambda _path: None)
    load_coefficients_callback = on_load_coefficients or (lambda _path: None)
    pause_live_callback = on_pause_live or (lambda: None)
    resume_live_callback = on_resume_live or (lambda: None)
    live_window_callback = on_live_window or (lambda _seconds: None)
    if root is None or tk_module is None or ttk_module is None:
        raise ProductRequestError("root, tk_module, and ttk_module are required")
    tk = tk_module
    ttk = ttk_module
    configure_dashboard_style(root, ttk)
    root.title("Analog Validation Studio")
    root.minsize(1040, 760)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(1, weight=1)

    header = ttk.Frame(root, padding=(24, 16), style="Header.TFrame")
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(1, weight=1)
    ttk.Frame(header, width=4, style="Accent.TFrame").grid(
        row=0,
        column=0,
        rowspan=3,
        sticky="ns",
        padx=(0, 14),
    )
    ttk.Label(
        header,
        text="VALIDATION WORKSPACE",
        style="HeaderEyebrow.TLabel",
    ).grid(row=0, column=1, sticky="w")
    ttk.Label(
        header,
        text="Analog Validation Studio",
        style="HeaderTitle.TLabel",
    ).grid(row=1, column=1, sticky="w", pady=(2, 0))
    ttk.Label(
        header,
        text=(
            "Offline, evidence-aware test workflow · simulator-first · "
            "hardware claims remain explicit"
        ),
        style="HeaderSubtitle.TLabel",
    ).grid(row=2, column=1, sticky="w", pady=(3, 0))
    badge_frame = ttk.Frame(header, style="Header.TFrame")
    badge_frame.grid(row=0, column=2, rowspan=3, sticky="e")
    for row, (text, style_name) in enumerate(
        (
            ("LOCAL / OFFLINE", "Badge.TLabel"),
            ("READ-ONLY DEFAULT", "SafeBadge.TLabel"),
            ("EVIDENCE LABELED", "Badge.TLabel"),
        )
    ):
        ttk.Label(badge_frame, text=text, style=style_name).grid(
            row=row,
            column=0,
            sticky="e",
            pady=(4 if row else 0, 0),
        )
    _create_theme_selector(root, header, tk, ttk)

    notebook_factory = getattr(ttk, "Notebook", None)
    if callable(notebook_factory):
        notebook = notebook_factory(root, style="Modern.TNotebook")
        notebook.grid(row=1, column=0, sticky="nsew")
        workflow_tab = ttk.Frame(notebook, style="App.TFrame")
        result_tab = ttk.Frame(notebook, style="App.TFrame")
        notebook.add(workflow_tab, text="Setup & run")
        notebook.add(result_tab, text="Results & evidence")
        high_contrast = bool(getattr(root, "_avs_high_contrast", False))
        workflow_page, workflow_scroll_canvas = _create_scrollable_page(
            workflow_tab,
            tk,
            ttk,
            high_contrast=high_contrast,
        )
        result_host, result_scroll_canvas = _create_scrollable_page(
            result_tab,
            tk,
            ttk,
            high_contrast=high_contrast,
        )
        workflow_grid_row = 0
    else:
        notebook = None
        workflow_page = root
        workflow_tab = workflow_page
        workflow_scroll_canvas = None
        workflow_grid_row = 1
        result_host = ttk.Frame(root, style="App.TFrame")
        result_host.grid(row=2, column=0, sticky="nsew")
        result_tab = result_host
        result_scroll_canvas = None
    workflow_page.columnconfigure(0, weight=1)
    result_host.columnconfigure(0, weight=1)
    result_content_host = ttk.Frame(result_host, style="App.TFrame")
    result_content_host.grid(row=3, column=0, sticky="nsew")
    result_content_host.columnconfigure(0, weight=1)
    result_content_host.rowconfigure(0, weight=1)
    result_widgets = create_dashboard_widgets(
        root,
        tk,
        ttk,
        on_cancel=on_cancel,
        on_close=on_close,
        on_pause=pause_live_callback,
        on_resume=resume_live_callback,
        on_live_window=live_window_callback,
        parent=result_content_host,
        configure_window=False,
    )

    string_var = tk.StringVar
    boolean_var = getattr(tk, "BooleanVar", string_var)

    def text_variable() -> Any:
        return string_var(master=root, value="")

    form = DashboardFormVariables(
        source=text_variable(),
        profile=text_variable(),
        job=text_variable(),
        primary_channel=text_variable(),
        secondary_channel=text_variable(),
        state_channel=text_variable(),
        operation=text_variable(),
        unit=text_variable(),
        sample_count=text_variable(),
        rising_count=text_variable(),
        falling_count=text_variable(),
        replay_path=text_variable(),
        replay_minimum=text_variable(),
        replay_maximum=text_variable(),
        serial_port=text_variable(),
        serial_baud_rate=text_variable(),
        serial_read_timeout=text_variable(),
        serial_max_polls=text_variable(),
        serial_expected_device_id=text_variable(),
        serial_afe_adc_aliases=text_variable(),
        serial_confirm_read_only=boolean_var(master=root, value=False),
        low_output_limit=text_variable(),
        high_output_limit=text_variable(),
        target_gain=text_variable(),
        gain_tolerance=text_variable(),
        max_abs_offset=text_variable(),
        min_r_squared=text_variable(),
        max_rmse=text_variable(),
        coefficient_id=text_variable(),
        coefficient_version=text_variable(),
        max_calibration_rmse=text_variable(),
        max_calibration_mean_absolute_error=text_variable(),
        max_calibration_absolute_error=text_variable(),
        minimum_calibration_rmse_reduction=text_variable(),
        minimum_high_threshold=text_variable(),
        maximum_high_threshold=text_variable(),
        minimum_low_threshold=text_variable(),
        maximum_low_threshold=text_variable(),
        minimum_width=text_variable(),
        maximum_width=text_variable(),
        maximum_width_span=text_variable(),
        export_path=text_variable(),
        export_format=string_var(master=root, value="json"),
        frequency_channel=text_variable(),
        frequency_point_count=text_variable(),
        frequency_minimum_hz=text_variable(),
        frequency_maximum_hz=text_variable(),
        frequency_input_amplitude=text_variable(),
        simulated_cutoff_frequency_hz=text_variable(),
        target_cutoff_frequency_hz=text_variable(),
        cutoff_relative_tolerance=text_variable(),
        cutoff_drop_db=text_variable(),
        monitor_sample_interval_seconds=text_variable(),
        monitor_time_window_seconds=text_variable(),
        monitor_max_buffer_points=text_variable(),
        monitor_include_secondary=boolean_var(master=root, value=True),
        monitor_include_state=boolean_var(master=root, value=True),
    )
    step_value = string_var(master=root, value="")
    guidance_value = string_var(master=root, value="")
    field_help_value = string_var(master=root, value="")
    action_guidance_value = string_var(master=root, value="")
    source_display_value = string_var(master=root, value="")
    job_display_value = string_var(master=root, value="")
    review_value = string_var(master=root, value="")
    issue_value = string_var(master=root, value="")
    ports_value = string_var(master=root, value="")
    export_value = string_var(master=root, value="")
    coefficient_value = string_var(master=root, value="")
    coefficient_path = string_var(master=root, value="")
    next_steps_value = string_var(master=root, value="")

    entry = getattr(ttk, "Entry", ttk.Label)
    combobox = getattr(ttk, "Combobox", entry)
    checkbutton = getattr(ttk, "Checkbutton", ttk.Button)

    wizard_frame = ttk.LabelFrame(
        workflow_page,
        text="Guided validation workflow",
        padding=14,
        style="Card.TLabelframe",
    )
    wizard_frame.grid(
        row=workflow_grid_row,
        column=0,
        sticky="nsew",
        padx=18,
        pady=14,
    )
    for column in range(3):
        wizard_frame.columnconfigure(column, weight=1)
    step_label = ttk.Label(
        wizard_frame,
        textvariable=step_value,
        justify="left",
        style="Step.TLabel",
    )
    step_label.grid(row=0, column=0, columnspan=3, sticky="w")
    guidance_label = ttk.Label(
        wizard_frame,
        textvariable=guidance_value,
        wraplength=760,
        justify="left",
        style="Muted.TLabel",
    )
    guidance_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(5, 10))

    setup_frame = ttk.LabelFrame(
        wizard_frame,
        text="Test setup",
        padding=10,
        style="Card.TLabelframe",
    )
    setup_frame.grid(row=2, column=0, columnspan=3, sticky="ew")
    for column in range(3):
        setup_frame.columnconfigure(column, weight=1)

    source_select = combobox(
        setup_frame,
        textvariable=source_display_value,
        state="readonly",
        takefocus=True,
    )
    profile_select = combobox(
        setup_frame, textvariable=form.profile, state="readonly", takefocus=True
    )
    job_select = combobox(
        setup_frame,
        textvariable=job_display_value,
        state="readonly",
        takefocus=True,
    )
    primary_channel_input = entry(setup_frame, textvariable=form.primary_channel)
    secondary_channel_input = entry(setup_frame, textvariable=form.secondary_channel)
    state_channel_input = entry(setup_frame, textvariable=form.state_channel)
    for index, (label, widget) in enumerate(
        (
            ("Source", source_select),
            ("Profile", profile_select),
            ("Test", job_select),
            ("Primary channel", primary_channel_input),
            ("Secondary channel", secondary_channel_input),
            ("State channel", state_channel_input),
        )
    ):
        row = (index // 3) * 2
        column = index % 3
        ttk.Label(setup_frame, text=label, style="Muted.TLabel").grid(
            row=row, column=column, sticky="w"
        )
        widget.grid(
            row=row + 1,
            column=column,
            sticky="ew",
            padx=(0, 8),
            pady=(3, 0),
        )

    signal_frame = ttk.LabelFrame(
        wizard_frame,
        text="Signal & sampling",
        padding=10,
        style="Card.TLabelframe",
    )
    signal_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 0))
    for column in range(3):
        signal_frame.columnconfigure(column, weight=1)

    operation_select = combobox(
        signal_frame,
        textvariable=form.operation,
        values=("ANALOG", "DIGITAL"),
        state="readonly",
        takefocus=True,
    )
    unit_select = combobox(
        signal_frame,
        textvariable=form.unit,
        values=("V", "mV", "boolean", "unitless"),
        state="readonly",
        takefocus=True,
    )
    sample_count_input = entry(signal_frame, textvariable=form.sample_count)
    rising_count_input = entry(signal_frame, textvariable=form.rising_count)
    falling_count_input = entry(signal_frame, textvariable=form.falling_count)
    target_gain_input = entry(signal_frame, textvariable=form.target_gain)
    config_fields = (
        ("Operation", operation_select),
        ("Unit", unit_select),
        ("Samples / DC points (1–10k)", sample_count_input),
        ("Rising samples (2–10k)", rising_count_input),
        ("Falling samples (2–10k)", falling_count_input),
        ("Target gain", target_gain_input),
    )
    for index, (label, widget) in enumerate(config_fields):
        row = (index // 3) * 2
        column = index % 3
        ttk.Label(signal_frame, text=label, style="Muted.TLabel").grid(
            row=row, column=column, sticky="w"
        )
        widget.grid(
            row=row + 1,
            column=column,
            sticky="ew",
            padx=(0, 8),
            pady=(3, 0),
        )
    ttk.Label(
        signal_frame,
        text=(
            "Count limits: READ/DC/calibration 1–10,000; hysteresis at least 2 per direction "
            "and 10,000 combined."
        ),
        style="Muted.TLabel",
        justify="left",
    ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))

    acceptance_frame = ttk.LabelFrame(
        wizard_frame,
        text="Acceptance criteria — analysis tests only",
        padding=10,
        style="Card.TLabelframe",
    )
    acceptance_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 0))
    for column in range(3):
        acceptance_frame.columnconfigure(column, weight=1)
    acceptance_fields = (
        ("Low output", form.low_output_limit),
        ("High output", form.high_output_limit),
        ("Gain tolerance", form.gain_tolerance),
        ("Max abs offset", form.max_abs_offset),
        ("Minimum R squared", form.min_r_squared),
        ("Max RMSE", form.max_rmse),
        ("Minimum high threshold", form.minimum_high_threshold),
        ("Maximum high threshold", form.maximum_high_threshold),
        ("Minimum low threshold", form.minimum_low_threshold),
        ("Maximum low threshold", form.maximum_low_threshold),
        ("Minimum width", form.minimum_width),
        ("Maximum width", form.maximum_width),
    )
    acceptance_inputs: list[Any] = []
    for index, (label, variable) in enumerate(acceptance_fields):
        row = (index // 3) * 2
        column = index % 3
        ttk.Label(acceptance_frame, text=label, style="Muted.TLabel").grid(
            row=row, column=column, sticky="w"
        )
        selected_input = entry(acceptance_frame, textvariable=variable)
        selected_input.grid(row=row + 1, column=column, sticky="ew", padx=(0, 6))
        acceptance_inputs.append(selected_input)
    ttk.Label(
        acceptance_frame,
        text="Maximum width span",
        style="Muted.TLabel",
    ).grid(row=8, column=0, sticky="w")
    maximum_width_span_input = entry(
        acceptance_frame, textvariable=form.maximum_width_span
    )
    maximum_width_span_input.grid(row=9, column=0, sticky="ew", padx=(0, 6))

    calibration_frame = ttk.LabelFrame(
        wizard_frame,
        text="Calibration identity & acceptance criteria",
        padding=10,
        style="Card.TLabelframe",
    )
    calibration_frame.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(8, 0))
    for column in range(3):
        calibration_frame.columnconfigure(column, weight=1)
    calibration_fields = (
        ("Coefficient ID", form.coefficient_id),
        ("Coefficient version", form.coefficient_version),
        ("Max after RMSE", form.max_calibration_rmse),
        (
            "Max after mean absolute error",
            form.max_calibration_mean_absolute_error,
        ),
        ("Max after absolute error", form.max_calibration_absolute_error),
        ("Minimum RMSE reduction", form.minimum_calibration_rmse_reduction),
    )
    calibration_inputs: list[Any] = []
    for index, (label, variable) in enumerate(calibration_fields):
        row = (index // 3) * 2
        column = index % 3
        ttk.Label(calibration_frame, text=label, style="Muted.TLabel").grid(
            row=row, column=column, sticky="w"
        )
        selected_input = entry(calibration_frame, textvariable=variable)
        selected_input.grid(row=row + 1, column=column, sticky="ew", padx=(0, 6))
        calibration_inputs.append(selected_input)
    ttk.Label(
        calibration_frame,
        text=(
            "Primary channel = observed values; secondary channel = trusted reference "
            "values. Both remain explicitly labeled by the selected evidence source."
        ),
        style="Muted.TLabel",
        justify="left",
    ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))

    frequency_frame = ttk.LabelFrame(
        wizard_frame,
        text="Frequency sweep model & cutoff acceptance",
        padding=10,
        style="Card.TLabelframe",
    )
    frequency_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(8, 0))
    for column in range(3):
        frequency_frame.columnconfigure(column, weight=1)
    frequency_channel_input = entry(
        frequency_frame, textvariable=form.frequency_channel
    )
    frequency_unit_select = combobox(
        frequency_frame,
        textvariable=form.unit,
        values=("V", "mV"),
        state="readonly",
        takefocus=True,
    )
    frequency_point_count_input = entry(
        frequency_frame, textvariable=form.frequency_point_count
    )
    frequency_minimum_input = entry(
        frequency_frame, textvariable=form.frequency_minimum_hz
    )
    frequency_maximum_input = entry(
        frequency_frame, textvariable=form.frequency_maximum_hz
    )
    frequency_input_amplitude_input = entry(
        frequency_frame, textvariable=form.frequency_input_amplitude
    )
    simulated_cutoff_input = entry(
        frequency_frame, textvariable=form.simulated_cutoff_frequency_hz
    )
    target_cutoff_input = entry(
        frequency_frame, textvariable=form.target_cutoff_frequency_hz
    )
    cutoff_tolerance_input = entry(
        frequency_frame, textvariable=form.cutoff_relative_tolerance
    )
    cutoff_drop_input = entry(frequency_frame, textvariable=form.cutoff_drop_db)
    frequency_fields = (
        ("Frequency channel", frequency_channel_input),
        ("Amplitude unit", frequency_unit_select),
        ("Log points (10–10k)", frequency_point_count_input),
        ("Minimum frequency (Hz)", frequency_minimum_input),
        ("Maximum frequency (Hz)", frequency_maximum_input),
        ("Simulator input amplitude", frequency_input_amplitude_input),
        ("Simulator model cutoff (Hz)", simulated_cutoff_input),
        ("Acceptance target cutoff (Hz)", target_cutoff_input),
        ("Relative tolerance (0–1)", cutoff_tolerance_input),
        ("Cutoff drop (dB)", cutoff_drop_input),
    )
    for index, (label, widget) in enumerate(frequency_fields):
        row = (index // 3) * 2
        column = index % 3
        ttk.Label(frequency_frame, text=label, style="Muted.TLabel").grid(
            row=row, column=column, sticky="w", pady=((6, 0) if row else 0)
        )
        widget.grid(row=row + 1, column=column, sticky="ew", padx=(0, 6))
    ttk.Label(
        frequency_frame,
        text=(
            "Primary and secondary channels are input and output amplitudes. "
            "Simulator model values generate SYNTHETIC observations; the acceptance "
            "target is evaluated independently. CSV Replay ignores simulator-only fields."
        ),
        style="Muted.TLabel",
        justify="left",
    ).grid(row=8, column=0, columnspan=3, sticky="w", pady=(6, 0))

    monitor_frame = ttk.LabelFrame(
        wizard_frame,
        text="Live monitor — finite session and bounded memory",
        padding=10,
        style="Card.TLabelframe",
    )
    monitor_frame.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(8, 0))
    for column in range(3):
        monitor_frame.columnconfigure(column, weight=1)
    monitor_interval_input = entry(
        monitor_frame, textvariable=form.monitor_sample_interval_seconds
    )
    monitor_window_input = entry(
        monitor_frame, textvariable=form.monitor_time_window_seconds
    )
    monitor_buffer_input = entry(
        monitor_frame, textvariable=form.monitor_max_buffer_points
    )
    for column, (label, widget) in enumerate(
        (
            ("Cycle interval (seconds)", monitor_interval_input),
            ("Visible time window (seconds)", monitor_window_input),
            ("Maximum retained points", monitor_buffer_input),
        )
    ):
        ttk.Label(monitor_frame, text=label, style="Muted.TLabel").grid(
            row=0, column=column, sticky="w"
        )
        widget.grid(row=1, column=column, sticky="ew", padx=(0, 8), pady=(3, 0))
    monitor_secondary = checkbutton(
        monitor_frame,
        text="Include secondary analog trace",
        variable=form.monitor_include_secondary,
        takefocus=True,
    )
    monitor_secondary.grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
    monitor_state = checkbutton(
        monitor_frame,
        text="Include boolean state trace",
        variable=form.monitor_include_state,
        takefocus=True,
    )
    monitor_state.grid(row=2, column=1, sticky="w", padx=(0, 8), pady=(6, 0))
    ttk.Label(
        monitor_frame,
        text=(
            "This is a finite acquisition, not a background daemon. Pause stops at "
            "safe checkpoints; the oldest display points are evicted when the memory "
            "bound is reached."
        ),
        style="Muted.TLabel",
        justify="left",
    ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))

    source_frame = ttk.LabelFrame(
        wizard_frame,
        text="Selected source details — data opens only after explicit Run",
        padding=10,
        style="Card.TLabelframe",
    )
    source_frame.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(8, 0))
    source_frame.columnconfigure(0, weight=1)

    replay_source_frame = ttk.Frame(source_frame, style="Card.TFrame")
    replay_source_frame.grid(row=0, column=0, sticky="ew")
    for column, weight in enumerate((3, 1, 1, 1)):
        replay_source_frame.columnconfigure(column, weight=weight)

    replay_path_input = entry(replay_source_frame, textvariable=form.replay_path)
    replay_minimum_input = entry(replay_source_frame, textvariable=form.replay_minimum)
    replay_maximum_input = entry(replay_source_frame, textvariable=form.replay_maximum)
    replay_fields = (
        ("Replay CSV path (required)", replay_path_input, 0, 1),
        ("Minimum accepted value (optional)", replay_minimum_input, 2, 1),
        ("Maximum accepted value (optional)", replay_maximum_input, 3, 1),
    )
    for label, widget, column, columnspan in replay_fields:
        ttk.Label(replay_source_frame, text=label, style="Muted.TLabel").grid(
            row=0, column=column, columnspan=columnspan, sticky="w"
        )
        widget.grid(
            row=1,
            column=column,
            columnspan=columnspan,
            sticky="ew",
            padx=(0, 8),
            pady=(3, 0),
        )

    def choose_replay_path() -> None:
        selected = choose_replay_path_callback()
        if not isinstance(selected, str):
            raise ProductRequestError(
                "on_choose_replay_path must return a replay path string"
            )
        if selected:
            form.replay_path.set(selected)

    replay_browse_button = ttk.Button(
        replay_source_frame,
        text="Choose CSV file...",
        command=choose_replay_path,
        takefocus=True,
        style="Secondary.TButton",
    )
    replay_browse_button.grid(row=1, column=1, sticky="ew", padx=(0, 8))

    serial_source_frame = ttk.Frame(source_frame, style="Card.TFrame")
    serial_source_frame.grid(row=1, column=0, sticky="ew")
    for column in range(3):
        serial_source_frame.columnconfigure(column, weight=1)

    serial_port_select = combobox(
        serial_source_frame,
        textvariable=form.serial_port,
        state="normal",
        takefocus=True,
    )
    serial_baud_input = entry(serial_source_frame, textvariable=form.serial_baud_rate)
    serial_timeout_input = entry(
        serial_source_frame, textvariable=form.serial_read_timeout
    )
    serial_polls_input = entry(serial_source_frame, textvariable=form.serial_max_polls)
    serial_expected_device_input = entry(
        serial_source_frame, textvariable=form.serial_expected_device_id
    )
    serial_aliases_input = entry(
        serial_source_frame, textvariable=form.serial_afe_adc_aliases
    )
    serial_fields = (
        ("Serial port", serial_port_select),
        ("Baud rate", serial_baud_input),
        ("Read timeout (s)", serial_timeout_input),
        ("Maximum polls", serial_polls_input),
    )
    for index, (label, widget) in enumerate(serial_fields):
        row = (index // 3) * 2
        column = index % 3
        ttk.Label(serial_source_frame, text=label, style="Muted.TLabel").grid(
            row=row, column=column, sticky="w", pady=(8, 0)
        )
        widget.grid(
            row=row + 1,
            column=column,
            sticky="ew",
            padx=(0, 8),
            pady=(3, 0),
        )
    ttk.Label(
        serial_source_frame,
        text="Expected capability device ID (optional)",
        style="Muted.TLabel",
    ).grid(row=4, column=0, sticky="w", pady=(8, 0))
    serial_expected_device_input.grid(
        row=5,
        column=0,
        sticky="ew",
        padx=(0, 8),
        pady=(3, 0),
    )
    ttk.Label(
        serial_source_frame,
        text="AFE ADC aliases (comma-separated native=canonical pairs)",
        style="Muted.TLabel",
    ).grid(row=4, column=1, columnspan=2, sticky="w", pady=(8, 0))
    serial_aliases_input.grid(
        row=5,
        column=1,
        columnspan=2,
        sticky="ew",
        pady=(3, 0),
    )
    serial_confirmation = checkbutton(
        serial_source_frame,
        text="I confirm that this serial session is receive-only",
        variable=form.serial_confirm_read_only,
        takefocus=True,
    )
    serial_confirmation.grid(row=6, column=0, sticky="w", pady=(8, 0))

    ttk.Label(
        serial_source_frame,
        textvariable=ports_value,
        wraplength=760,
        justify="left",
        style="Muted.TLabel",
    ).grid(row=7, column=0, columnspan=3, sticky="w", pady=(6, 0))

    field_guide_frame = ttk.LabelFrame(
        wizard_frame,
        text="Plain-language field guide",
        padding=10,
        style="Card.TLabelframe",
    )
    field_guide_frame.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(8, 0))
    field_guide_label = ttk.Label(
        field_guide_frame,
        textvariable=field_help_value,
        wraplength=900,
        justify="left",
        style="Body.TLabel",
    )
    field_guide_label.grid(row=0, column=0, sticky="w")

    review_frame = ttk.Frame(wizard_frame, style="Card.TFrame")
    review_frame.grid(row=10, column=0, columnspan=3, sticky="ew", pady=(8, 0))
    review_frame.columnconfigure(0, weight=1)
    review_frame.columnconfigure(1, weight=1)
    review_summary = ttk.LabelFrame(
        review_frame,
        text="Compiled review",
        padding=10,
        style="Card.TLabelframe",
    )
    review_summary.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
    issue_summary = ttk.LabelFrame(
        review_frame,
        text="Issues & safe next step",
        padding=10,
        style="Card.TLabelframe",
    )
    issue_summary.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
    ttk.Label(
        review_summary,
        textvariable=review_value,
        wraplength=440,
        justify="left",
        style="Body.TLabel",
    ).grid(row=0, column=0, sticky="nw")
    issue_label = ttk.Label(
        issue_summary,
        textvariable=issue_value,
        wraplength=440,
        justify="left",
        style="Body.TLabel",
    )
    issue_label.grid(row=0, column=0, sticky="nw")

    action_frame = ttk.Frame(wizard_frame, style="Card.TFrame")
    action_frame.grid(row=11, column=0, columnspan=3, sticky="ew", pady=(10, 0))
    for column in range(5):
        action_frame.columnconfigure(column, weight=1)
    action_guidance_label = ttk.Label(
        action_frame,
        textvariable=action_guidance_value,
        wraplength=900,
        justify="left",
        style="Muted.TLabel",
    )
    action_guidance_label.grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 6))
    back_button = ttk.Button(
        action_frame,
        text="Previous step",
        command=on_back,
        takefocus=True,
        style="Secondary.TButton",
    )
    next_button = ttk.Button(
        action_frame,
        text="Continue",
        command=on_next,
        takefocus=True,
        style="Primary.TButton",
    )

    def review_form() -> object:
        try:
            value: DashboardWizardDraft | BaseException = form.snapshot()
        except BaseException as error:  # noqa: BLE001 - Tk callback boundary
            value = error
        return on_review(value)

    review_button = ttk.Button(
        action_frame,
        text="Validate setup",
        command=review_form,
        takefocus=True,
        style="Primary.TButton",
    )
    run_button = ttk.Button(
        action_frame,
        text="Run reviewed test",
        command=on_run,
        takefocus=True,
        style="Primary.TButton",
    )
    discover_button = ttk.Button(
        action_frame,
        text="Find serial ports",
        command=on_discover,
        takefocus=True,
        style="Secondary.TButton",
    )
    for column, button in enumerate(
        (
            back_button,
            next_button,
            review_button,
            run_button,
            discover_button,
        )
    ):
        button.grid(row=1, column=column, sticky="ew", padx=(0, 8))

    export_frame = ttk.LabelFrame(
        result_host,
        text="Save finalized analysis — existing files are never overwritten",
        padding=10,
        style="Card.TLabelframe",
    )
    export_frame.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 0))
    for column in range(4):
        export_frame.columnconfigure(column, weight=1)
    ttk.Label(
        export_frame,
        textvariable=export_value,
        wraplength=760,
        justify="left",
        style="Muted.TLabel",
    ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
    ttk.Label(export_frame, text="Destination path", style="Muted.TLabel").grid(
        row=1, column=0, columnspan=2, sticky="w"
    )
    export_path_input = entry(export_frame, textvariable=form.export_path)
    export_path_input.grid(row=2, column=0, sticky="ew", padx=(0, 8), pady=(3, 0))

    def choose_export_path() -> None:
        selected = on_choose_export_path(str(form.export_format.get()))
        if selected is None or selected == "":
            return
        if not isinstance(selected, str):
            raise ProductRequestError("on_choose_export_path must return a path string")
        form.export_path.set(selected)

    export_browse_button = ttk.Button(
        export_frame,
        text="Choose save location...",
        command=choose_export_path,
        takefocus=True,
        style="Secondary.TButton",
    )
    export_browse_button.grid(row=2, column=1, sticky="ew", padx=(0, 8), pady=(3, 0))
    ttk.Label(export_frame, text="Format", style="Muted.TLabel").grid(
        row=1, column=2, sticky="w"
    )
    export_format_select = combobox(
        export_frame,
        textvariable=form.export_format,
        values=("json", "csv"),
        state="readonly",
        takefocus=True,
    )
    export_format_select.grid(row=2, column=2, sticky="ew", pady=(3, 0))
    export_button = ttk.Button(
        export_frame,
        text="Save analysis result",
        command=lambda: on_export(
            str(form.export_path.get()), str(form.export_format.get())
        ),
        takefocus=True,
        style="Primary.TButton",
    )
    export_button.grid(row=2, column=3, sticky="ew", padx=(8, 0), pady=(3, 0))

    coefficient_frame = ttk.LabelFrame(
        result_host,
        text="Calibration coefficient artifact — strict JSON, never auto-applied",
        padding=10,
        style="Card.TLabelframe",
    )
    coefficient_frame.grid(row=1, column=0, sticky="ew", padx=18, pady=(8, 0))
    for column in range(4):
        coefficient_frame.columnconfigure(column, weight=1)
    ttk.Label(
        coefficient_frame,
        textvariable=coefficient_value,
        wraplength=920,
        justify="left",
        style="Muted.TLabel",
    ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
    ttk.Label(
        coefficient_frame,
        text="Coefficient JSON path",
        style="Muted.TLabel",
    ).grid(row=1, column=0, columnspan=4, sticky="w")
    coefficient_path_input = entry(
        coefficient_frame,
        textvariable=coefficient_path,
    )
    coefficient_path_input.grid(
        row=2,
        column=0,
        columnspan=2,
        sticky="ew",
        padx=(0, 8),
        pady=(3, 0),
    )

    def choose_coefficient_path(mode: str) -> None:
        selected = choose_coefficient_path_callback(mode)
        if selected is None or selected == "":
            return
        if not isinstance(selected, str):
            raise ProductRequestError(
                "on_choose_coefficient_path must return a path string"
            )
        coefficient_path.set(selected)

    coefficient_browse_save_button = ttk.Button(
        coefficient_frame,
        text="Choose save location...",
        command=lambda: choose_coefficient_path("save"),
        takefocus=True,
        style="Secondary.TButton",
    )
    coefficient_browse_save_button.grid(
        row=2, column=2, sticky="ew", padx=(0, 8), pady=(3, 0)
    )
    coefficient_save_button = ttk.Button(
        coefficient_frame,
        text="Save coefficients",
        command=lambda: save_coefficients_callback(str(coefficient_path.get())),
        takefocus=True,
        style="Primary.TButton",
    )
    coefficient_save_button.grid(row=2, column=3, sticky="ew", pady=(3, 0))
    coefficient_browse_load_button = ttk.Button(
        coefficient_frame,
        text="Choose existing file...",
        command=lambda: choose_coefficient_path("load"),
        takefocus=True,
        style="Secondary.TButton",
    )
    coefficient_browse_load_button.grid(
        row=3, column=2, sticky="ew", padx=(0, 8), pady=(6, 0)
    )
    coefficient_load_button = ttk.Button(
        coefficient_frame,
        text="Load & validate",
        command=lambda: load_coefficients_callback(str(coefficient_path.get())),
        takefocus=True,
        style="Secondary.TButton",
    )
    coefficient_load_button.grid(row=3, column=3, sticky="ew", pady=(6, 0))

    next_steps_frame = ttk.LabelFrame(
        result_host,
        text="What would you like to do next?",
        padding=10,
        style="Card.TLabelframe",
    )
    next_steps_frame.grid(row=2, column=0, sticky="ew", padx=18, pady=(8, 0))
    for column in range(4):
        next_steps_frame.columnconfigure(column, weight=1)
    ttk.Label(
        next_steps_frame,
        textvariable=next_steps_value,
        wraplength=920,
        justify="left",
        style="Muted.TLabel",
    ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
    modify_button = ttk.Button(
        next_steps_frame,
        text="Modify setup",
        command=on_modify,
        takefocus=True,
        style="Secondary.TButton",
    )
    repeat_button = ttk.Button(
        next_steps_frame,
        text="Review same setup",
        command=on_repeat,
        takefocus=True,
        style="Secondary.TButton",
    )
    new_test_button = ttk.Button(
        next_steps_frame,
        text="Start new test",
        command=on_new_test,
        takefocus=True,
        style="Secondary.TButton",
    )
    finish_button = ttk.Button(
        next_steps_frame,
        text="Finish & close",
        command=on_close,
        takefocus=True,
        style="Secondary.TButton",
    )
    for column, button in enumerate(
        (modify_button, repeat_button, new_test_button, finish_button)
    ):
        button.grid(row=1, column=column, sticky="ew", padx=(0, 8))

    all_jobs = (
        "READ",
        "DC_ANALYSIS",
        "HYSTERESIS_ANALYSIS",
        "CALIBRATION_ANALYSIS",
        "FREQUENCY_RESPONSE_ANALYSIS",
        "LIVE_MONITOR",
    )
    editable_controls = (
        (primary_channel_input, "normal", all_jobs, ()),
        (
            secondary_channel_input,
            "normal",
            (
                "DC_ANALYSIS",
                "CALIBRATION_ANALYSIS",
                "FREQUENCY_RESPONSE_ANALYSIS",
                "LIVE_MONITOR",
            ),
            (),
        ),
        (
            state_channel_input,
            "normal",
            ("HYSTERESIS_ANALYSIS", "LIVE_MONITOR"),
            (),
        ),
        (operation_select, "readonly", ("READ",), ()),
        (unit_select, "readonly", all_jobs, ()),
        (
            sample_count_input,
            "normal",
            ("READ", "DC_ANALYSIS", "CALIBRATION_ANALYSIS", "LIVE_MONITOR"),
            (),
        ),
        (rising_count_input, "normal", ("HYSTERESIS_ANALYSIS",), ()),
        (falling_count_input, "normal", ("HYSTERESIS_ANALYSIS",), ()),
        (target_gain_input, "normal", ("DC_ANALYSIS",), ()),
        *tuple(
            (control, "normal", ("DC_ANALYSIS",), ())
            for control in acceptance_inputs[:6]
        ),
        *tuple(
            (control, "normal", ("HYSTERESIS_ANALYSIS",), ())
            for control in (*acceptance_inputs[6:], maximum_width_span_input)
        ),
        *tuple(
            (control, "normal", ("CALIBRATION_ANALYSIS",), ())
            for control in calibration_inputs
        ),
        (
            frequency_channel_input,
            "normal",
            ("FREQUENCY_RESPONSE_ANALYSIS",),
            (),
        ),
        (
            frequency_unit_select,
            "readonly",
            ("FREQUENCY_RESPONSE_ANALYSIS",),
            (),
        ),
        *tuple(
            (control, "normal", ("FREQUENCY_RESPONSE_ANALYSIS",), ())
            for control in (
                frequency_point_count_input,
                frequency_minimum_input,
                frequency_maximum_input,
                target_cutoff_input,
                cutoff_tolerance_input,
                cutoff_drop_input,
            )
        ),
        *tuple(
            (control, "normal", ("LIVE_MONITOR",), ())
            for control in (
                monitor_interval_input,
                monitor_window_input,
                monitor_buffer_input,
                monitor_secondary,
                monitor_state,
            )
        ),
        *tuple(
            (
                control,
                "normal",
                ("FREQUENCY_RESPONSE_ANALYSIS",),
                ("SIMULATOR",),
            )
            for control in (
                frequency_input_amplitude_input,
                simulated_cutoff_input,
            )
        ),
        (replay_path_input, "normal", all_jobs, ("CSV_REPLAY",)),
        (replay_minimum_input, "normal", all_jobs, ("CSV_REPLAY",)),
        (replay_maximum_input, "normal", all_jobs, ("CSV_REPLAY",)),
        (
            serial_port_select,
            "normal",
            ("READ", "LIVE_MONITOR"),
            ("SERIAL_READ_ONLY",),
        ),
        (
            serial_baud_input,
            "normal",
            ("READ", "LIVE_MONITOR"),
            ("SERIAL_READ_ONLY",),
        ),
        (
            serial_timeout_input,
            "normal",
            ("READ", "LIVE_MONITOR"),
            ("SERIAL_READ_ONLY",),
        ),
        (
            serial_polls_input,
            "normal",
            ("READ", "LIVE_MONITOR"),
            ("SERIAL_READ_ONLY",),
        ),
        (
            serial_expected_device_input,
            "normal",
            ("READ", "LIVE_MONITOR"),
            ("SERIAL_READ_ONLY",),
        ),
        (
            serial_aliases_input,
            "normal",
            ("READ", "LIVE_MONITOR"),
            ("SERIAL_READ_ONLY",),
        ),
        (
            serial_confirmation,
            "normal",
            ("READ", "LIVE_MONITOR"),
            ("SERIAL_READ_ONLY",),
        ),
    )
    field_controls: dict[str, tuple[Any, str, str, str]] = {
        "source_mode": (source_select, "TCombobox", "setup", "Source"),
        "profile_name": (profile_select, "TCombobox", "setup", "Profile"),
        "profile_version": (profile_select, "TCombobox", "setup", "Profile"),
        "job_type": (job_select, "TCombobox", "setup", "Test"),
        "primary_channel": (
            primary_channel_input,
            "TEntry",
            "setup",
            "Primary channel",
        ),
        "secondary_channel": (
            secondary_channel_input,
            "TEntry",
            "setup",
            "Secondary channel",
        ),
        "state_channel": (
            state_channel_input,
            "TEntry",
            "setup",
            "State channel",
        ),
        "operation": (operation_select, "TCombobox", "signal", "Operation"),
        "unit": (unit_select, "TCombobox", "signal", "Unit"),
        "sample_count": (
            sample_count_input,
            "TEntry",
            "signal",
            "Samples / DC points",
        ),
        "rising_count": (
            rising_count_input,
            "TEntry",
            "signal",
            "Rising samples",
        ),
        "falling_count": (
            falling_count_input,
            "TEntry",
            "signal",
            "Falling samples",
        ),
        "target_gain": (target_gain_input, "TEntry", "signal", "Target gain"),
        "low_output_limit": (
            acceptance_inputs[0],
            "TEntry",
            "acceptance",
            "Low output",
        ),
        "high_output_limit": (
            acceptance_inputs[1],
            "TEntry",
            "acceptance",
            "High output",
        ),
        "gain_tolerance": (
            acceptance_inputs[2],
            "TEntry",
            "acceptance",
            "Gain tolerance",
        ),
        "max_abs_offset": (
            acceptance_inputs[3],
            "TEntry",
            "acceptance",
            "Max abs offset",
        ),
        "min_r_squared": (
            acceptance_inputs[4],
            "TEntry",
            "acceptance",
            "Minimum R squared",
        ),
        "max_rmse": (
            acceptance_inputs[5],
            "TEntry",
            "acceptance",
            "Max RMSE",
        ),
        "minimum_high_threshold": (
            acceptance_inputs[6],
            "TEntry",
            "acceptance",
            "Minimum high threshold",
        ),
        "maximum_high_threshold": (
            acceptance_inputs[7],
            "TEntry",
            "acceptance",
            "Maximum high threshold",
        ),
        "minimum_low_threshold": (
            acceptance_inputs[8],
            "TEntry",
            "acceptance",
            "Minimum low threshold",
        ),
        "maximum_low_threshold": (
            acceptance_inputs[9],
            "TEntry",
            "acceptance",
            "Maximum low threshold",
        ),
        "minimum_width": (
            acceptance_inputs[10],
            "TEntry",
            "acceptance",
            "Minimum width",
        ),
        "maximum_width": (
            acceptance_inputs[11],
            "TEntry",
            "acceptance",
            "Maximum width",
        ),
        "maximum_width_span": (
            maximum_width_span_input,
            "TEntry",
            "acceptance",
            "Maximum width span",
        ),
        "coefficient_id": (
            calibration_inputs[0],
            "TEntry",
            "calibration",
            "Coefficient ID",
        ),
        "coefficient_version": (
            calibration_inputs[1],
            "TEntry",
            "calibration",
            "Coefficient version",
        ),
        "max_calibration_rmse": (
            calibration_inputs[2],
            "TEntry",
            "calibration",
            "Max after RMSE",
        ),
        "max_calibration_mean_absolute_error": (
            calibration_inputs[3],
            "TEntry",
            "calibration",
            "Max after mean absolute error",
        ),
        "max_calibration_absolute_error": (
            calibration_inputs[4],
            "TEntry",
            "calibration",
            "Max after absolute error",
        ),
        "minimum_calibration_rmse_reduction": (
            calibration_inputs[5],
            "TEntry",
            "calibration",
            "Minimum RMSE reduction",
        ),
        "frequency_channel": (
            frequency_channel_input,
            "TEntry",
            "frequency",
            "Frequency channel",
        ),
        "frequency_unit": (
            frequency_unit_select,
            "TCombobox",
            "frequency",
            "Amplitude unit",
        ),
        "frequency_point_count": (
            frequency_point_count_input,
            "TEntry",
            "frequency",
            "Log points",
        ),
        "frequency_minimum_hz": (
            frequency_minimum_input,
            "TEntry",
            "frequency",
            "Minimum frequency",
        ),
        "frequency_maximum_hz": (
            frequency_maximum_input,
            "TEntry",
            "frequency",
            "Maximum frequency",
        ),
        "frequency_input_amplitude": (
            frequency_input_amplitude_input,
            "TEntry",
            "frequency",
            "Simulator input amplitude",
        ),
        "simulated_cutoff_frequency_hz": (
            simulated_cutoff_input,
            "TEntry",
            "frequency",
            "Simulator model cutoff",
        ),
        "target_cutoff_frequency_hz": (
            target_cutoff_input,
            "TEntry",
            "frequency",
            "Acceptance target cutoff",
        ),
        "cutoff_relative_tolerance": (
            cutoff_tolerance_input,
            "TEntry",
            "frequency",
            "Relative tolerance",
        ),
        "cutoff_drop_db": (
            cutoff_drop_input,
            "TEntry",
            "frequency",
            "Cutoff drop",
        ),
        "monitor_sample_interval_seconds": (
            monitor_interval_input,
            "TEntry",
            "monitor",
            "Cycle interval",
        ),
        "monitor_time_window_seconds": (
            monitor_window_input,
            "TEntry",
            "monitor",
            "Visible time window",
        ),
        "monitor_max_buffer_points": (
            monitor_buffer_input,
            "TEntry",
            "monitor",
            "Maximum retained points",
        ),
        "monitor_include_secondary": (
            monitor_secondary,
            "TCheckbutton",
            "monitor",
            "Include secondary analog trace",
        ),
        "monitor_include_state": (
            monitor_state,
            "TCheckbutton",
            "monitor",
            "Include boolean state trace",
        ),
        "replay_path": (
            replay_path_input,
            "TEntry",
            "source_connection",
            "Replay CSV path",
        ),
        "replay_minimum": (
            replay_minimum_input,
            "TEntry",
            "source_connection",
            "Replay minimum",
        ),
        "replay_maximum": (
            replay_maximum_input,
            "TEntry",
            "source_connection",
            "Replay maximum",
        ),
        "serial_port": (
            serial_port_select,
            "TCombobox",
            "source_connection",
            "Serial port",
        ),
        "serial_baud_rate": (
            serial_baud_input,
            "TEntry",
            "source_connection",
            "Baud rate",
        ),
        "serial_read_timeout": (
            serial_timeout_input,
            "TEntry",
            "source_connection",
            "Read timeout",
        ),
        "serial_max_polls": (
            serial_polls_input,
            "TEntry",
            "source_connection",
            "Maximum polls",
        ),
        "serial_expected_device_id": (
            serial_expected_device_input,
            "TEntry",
            "source_connection",
            "Expected capability device ID",
        ),
        "serial_afe_adc_aliases": (
            serial_aliases_input,
            "TEntry",
            "source_connection",
            "AFE ADC aliases",
        ),
        "serial_confirm_read_only": (
            serial_confirmation,
            "TCheckbutton",
            "source_connection",
            "Receive-only confirmation",
        ),
        "export_path": (
            export_path_input,
            "TEntry",
            "export",
            "Destination path",
        ),
        "export_format": (
            export_format_select,
            "TCombobox",
            "export",
            "Export format",
        ),
        "coefficient_path": (
            coefficient_path_input,
            "TEntry",
            "coefficients",
            "Coefficient file path",
        ),
    }

    accessibility = result_widgets.accessibility
    if notebook is not None:
        accessibility.describe(
            notebook,
            role="Notebook",
            name="Validation workflow and results",
            help_text="Use the Setup and Results tabs to review the current local run.",
        )
    accessibility.describe(
        step_label,
        role="Label",
        name="Workflow step",
        help_text="Announces the active step in the six-step workflow.",
    )
    accessibility.describe(
        guidance_label,
        role="Label",
        name="Step guidance",
        help_text="Explains what to do, why it matters, and what to confirm.",
    )
    accessibility.describe(
        field_guide_label,
        role="Label",
        name="Plain-language field guide",
        help_text="Explains the selected source boundary and test terms.",
    )
    accessibility.describe(
        action_guidance_label,
        role="Label",
        name="Available action guidance",
        help_text="Explains the next available action and why Run may be unavailable.",
    )
    accessibility.describe(
        issue_label,
        role="Label",
        name="Issues and safe next step",
        help_text="Announces the first blocking issue and its recovery action.",
    )
    described_controls: set[int] = set()
    role_by_style = {
        "TCombobox": "Combobox",
        "TEntry": "Entry",
        "TCheckbutton": "Checkbutton",
    }
    for control, style_name, section_name, display_name in field_controls.values():
        identity = id(control)
        if identity in described_controls:
            continue
        described_controls.add(identity)
        section_text = section_name.replace("_", " ")
        accessibility.describe(
            control,
            role=role_by_style[style_name],
            name=display_name,
            help_text=(
                f"Configuration field in {section_text}. "
                "Correct any reported issue before running."
            ),
        )
    for button, name, help_text in (
        (back_button, "Previous step", "Returns to the previous workflow step."),
        (next_button, "Continue", "Advances after the current step is complete."),
        (
            review_button,
            "Validate setup",
            "Compiles and validates the setup without starting acquisition.",
        ),
        (
            run_button,
            "Run reviewed test",
            "Starts only the configuration that passed review.",
        ),
        (
            discover_button,
            "Find serial ports",
            "Explicitly discovers serial ports; this action may access the operating system.",
        ),
        (
            replay_browse_button,
            "Choose CSV Replay file",
            "Selects an existing local CSV file without reading it before Review.",
        ),
        (
            export_browse_button,
            "Choose analysis save location",
            "Selects a new destination without overwriting an existing file.",
        ),
        (
            export_button,
            "Save analysis result",
            "Publishes a finalized analysis result to a new file.",
        ),
        (
            coefficient_browse_save_button,
            "Choose coefficient save location",
            "Selects a new destination for calibration coefficients.",
        ),
        (
            coefficient_save_button,
            "Save coefficients",
            "Saves reviewed calibration coefficients to a new file.",
        ),
        (
            coefficient_browse_load_button,
            "Choose existing coefficient file",
            "Selects a coefficient file for validation only.",
        ),
        (
            coefficient_load_button,
            "Load and validate coefficients",
            "Validates coefficient metadata without applying it to acquisition.",
        ),
        (modify_button, "Modify setup", "Returns to configuration for changes."),
        (
            repeat_button,
            "Review same setup",
            "Creates a fresh review of the same setup before another run.",
        ),
        (new_test_button, "Start new test", "Clears the draft for a new test."),
        (finish_button, "Finish and close", "Closes after active cleanup is complete."),
    ):
        accessibility.describe(
            button,
            role="Button",
            name=name,
            help_text=help_text,
        )

    widgets = DashboardWorkflowWidgets(
        result_widgets=result_widgets,
        accessibility=accessibility,
        form=form,
        guidance_value=guidance_value,
        step_value=step_value,
        field_help_value=field_help_value,
        action_guidance_value=action_guidance_value,
        source_display_value=source_display_value,
        job_display_value=job_display_value,
        review_value=review_value,
        issue_value=issue_value,
        ports_value=ports_value,
        export_value=export_value,
        coefficient_value=coefficient_value,
        next_steps_value=next_steps_value,
        step_label=step_label,
        guidance_label=guidance_label,
        issue_label=issue_label,
        source_select=source_select,
        profile_select=profile_select,
        job_select=job_select,
        primary_channel_input=primary_channel_input,
        replay_browse_button=replay_browse_button,
        serial_port_select=serial_port_select,
        export_path_input=export_path_input,
        export_browse_button=export_browse_button,
        export_format_select=export_format_select,
        coefficient_path=coefficient_path,
        coefficient_path_input=coefficient_path_input,
        coefficient_browse_save_button=coefficient_browse_save_button,
        coefficient_browse_load_button=coefficient_browse_load_button,
        coefficient_save_button=coefficient_save_button,
        coefficient_load_button=coefficient_load_button,
        back_button=back_button,
        next_button=next_button,
        review_button=review_button,
        run_button=run_button,
        export_button=export_button,
        discover_button=discover_button,
        modify_button=modify_button,
        repeat_button=repeat_button,
        new_test_button=new_test_button,
        finish_button=finish_button,
        notebook=notebook,
        workflow_page=workflow_tab,
        result_page=result_tab,
        section_frames={
            "setup": setup_frame,
            "signal": signal_frame,
            "acceptance": acceptance_frame,
            "calibration": calibration_frame,
            "frequency": frequency_frame,
            "monitor": monitor_frame,
            "source_connection": source_frame,
            "replay_source": replay_source_frame,
            "serial_source": serial_source_frame,
            "field_guide": field_guide_frame,
            "review": review_frame,
            "workflow_actions": action_frame,
            "export": export_frame,
            "coefficients": coefficient_frame,
            "result_actions": next_steps_frame,
        },
        field_controls=field_controls,
        scroll_canvases=(workflow_scroll_canvas, result_scroll_canvas),
        editable_controls=editable_controls,
    )
    _bind_mouse_wheel(
        root,
        (workflow_scroll_canvas, result_scroll_canvas),
    )
    _bind_selection(
        source_select,
        lambda: on_source(
            _source_value_from_display(str(source_display_value.get())).value
        ),
    )
    _bind_selection(profile_select, lambda: on_profile(str(form.profile.get())))
    _bind_selection(
        job_select,
        lambda: on_job(_job_value_from_display(str(job_display_value.get())).value),
    )
    return widgets


__all__ = [
    "DashboardFormVariables",
    "DashboardWidgets",
    "DashboardWorkflowWidgets",
    "configure_dashboard_style",
    "create_dashboard_widgets",
    "create_dashboard_workflow_widgets",
]
