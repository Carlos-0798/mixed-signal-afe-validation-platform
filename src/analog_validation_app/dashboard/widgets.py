"""Tk/ttk rendering only; business state and lifecycle live elsewhere."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..errors import ProductRequestError
from .state import DashboardState
from .wizard import (
    DashboardExportFormat,
    DashboardWizardDraft,
    DashboardWizardState,
    DashboardWizardStep,
)

_BACKGROUND = "#f4f7fb"
_SURFACE = "#ffffff"
_TEXT = "#172033"
_MUTED = "#5f6b7a"
_ACCENT = "#2563eb"
_ACCENT_ACTIVE = "#1d4ed8"
_BORDER = "#dbe3ee"
_DANGER = "#b42318"


def configure_dashboard_style(root: Any, ttk_module: Any) -> None:
    """Apply a restrained modern ttk theme when the toolkit supports styling."""

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
        style.configure("App.TFrame", background=_BACKGROUND)
        style.configure("Header.TFrame", background=_TEXT)
        style.configure(
            "HeaderTitle.TLabel",
            background=_TEXT,
            foreground="#ffffff",
            font=("Segoe UI Semibold", 18),
        )
        style.configure(
            "HeaderSubtitle.TLabel",
            background=_TEXT,
            foreground="#cbd5e1",
            font=("Segoe UI", 10),
        )
        style.configure(
            "Badge.TLabel",
            background="#dbeafe",
            foreground="#1e40af",
            font=("Segoe UI Semibold", 9),
            padding=(8, 4),
        )
        style.configure(
            "Card.TLabelframe",
            background=_SURFACE,
            bordercolor=_BORDER,
            relief="solid",
            borderwidth=1,
        )
        style.configure(
            "Card.TLabelframe.Label",
            background=_SURFACE,
            foreground=_TEXT,
            font=("Segoe UI Semibold", 10),
        )
        style.configure(
            "Card.TFrame",
            background=_SURFACE,
        )
        style.configure(
            "Title.TLabel",
            background=_SURFACE,
            foreground=_TEXT,
            font=("Segoe UI Semibold", 12),
        )
        style.configure(
            "Body.TLabel",
            background=_SURFACE,
            foreground=_TEXT,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Muted.TLabel",
            background=_SURFACE,
            foreground=_MUTED,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Primary.TButton",
            background=_ACCENT,
            foreground="#ffffff",
            font=("Segoe UI Semibold", 10),
            padding=(14, 8),
            borderwidth=0,
        )
        style.map(
            "Primary.TButton",
            background=[("active", _ACCENT_ACTIVE), ("disabled", "#cbd5e1")],
            foreground=[("disabled", "#64748b")],
        )
        style.configure(
            "Secondary.TButton",
            background="#eef2f7",
            foreground=_TEXT,
            font=("Segoe UI", 10),
            padding=(12, 8),
        )
        style.map(
            "Secondary.TButton",
            background=[("active", "#e2e8f0"), ("disabled", "#f1f5f9")],
            foreground=[("disabled", "#94a3b8")],
        )
        style.configure(
            "Danger.TButton",
            foreground=_DANGER,
            font=("Segoe UI Semibold", 9),
            padding=(10, 6),
        )
        style.configure(
            "Modern.Treeview",
            background=_SURFACE,
            fieldbackground=_SURFACE,
            foreground=_TEXT,
            rowheight=27,
            font=("Segoe UI", 9),
        )
        style.configure(
            "Modern.Treeview.Heading",
            background="#eaf0f7",
            foreground=_TEXT,
            font=("Segoe UI Semibold", 9),
            padding=(6, 6),
        )
        style.configure(
            "Modern.TNotebook",
            background=_BACKGROUND,
            borderwidth=0,
            tabmargins=(18, 10, 18, 0),
        )
        style.configure(
            "Modern.TNotebook.Tab",
            font=("Segoe UI Semibold", 10),
            padding=(18, 9),
        )
        style.map(
            "Modern.TNotebook.Tab",
            background=[("selected", _SURFACE), ("!selected", "#e2e8f0")],
            foreground=[("selected", _ACCENT), ("!selected", _MUTED)],
        )
        root_configure = getattr(root, "configure", None)
        if callable(root_configure):
            root_configure(background=_BACKGROUND)
    except Exception:  # noqa: BLE001 - styling is optional; workflow remains usable
        return


def _callback(name: str, value: object) -> Callable[[], object]:
    if not callable(value):
        raise ProductRequestError(f"{name} must be callable")
    return value


def _result_text(state: DashboardState) -> str:
    result = state.result
    status = "NOT RUN" if result.status is None else result.status.value
    outcome = "none" if result.outcome is None else result.outcome.value
    evidence = (
        "none" if result.evidence_source is None else result.evidence_source.value
    )
    lines = [
        f"Product status: {status}",
        f"Engineering outcome: {outcome}",
        f"Evidence source: {evidence}",
        f"Hardware claim: {state.hardware_claim}",
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


def _artifact_text(state: DashboardState) -> str:
    lines = [state.artifacts.summary]
    lines.extend(
        f"- {artifact.name} | {artifact.size_bytes} bytes | SHA-256 {artifact.sha256}"
        for artifact in state.artifacts.artifacts
    )
    return "\n".join(lines)


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
    plot_value: Any
    result_value: Any
    artifacts_value: Any
    progress_bar: Any
    cancel_button: Any
    plot_table: Any
    _rendered_revision: int = -1

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
        self.progress_value.set(
            f"State: {progress.worker_state.value}\n"
            f"{progress.status_text}\n"
            f"Progress: {count}; events: {progress.event_count}; "
            f"dropped: {progress.dropped_event_count}"
        )
        self.progress_bar.configure(
            maximum=1 if progress.total is None else progress.total,
            value=0 if progress.completed is None else progress.completed,
        )
        self.cancel_button.configure(
            state="normal" if progress.can_cancel else "disabled"
        )
        self.plot_value.set(state.plot.summary)
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
        self.result_value.set(_result_text(state))
        self.artifacts_value.set(_artifact_text(state))
        self._rendered_revision = state.revision


def create_dashboard_widgets(
    root: Any,
    tk_module: Any,
    ttk_module: Any,
    *,
    on_cancel: Callable[[], object],
    on_close: Callable[[], object],
    parent: Any | None = None,
    configure_window: bool = True,
) -> DashboardWidgets:
    """Create the six-region local Dashboard using injected Tk modules."""

    cancel = _callback("on_cancel", on_cancel)
    close = _callback("on_close", on_close)
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
    plot_value = tk.StringVar(master=root, value="")
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
        wraplength=500,
        style="Body.TLabel",
    ).grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(
        source_frame,
        textvariable=profile_value,
        wraplength=500,
        style="Muted.TLabel",
    ).grid(
        row=1, column=0, sticky="w", pady=(4, 0)
    )
    ttk.Label(
        source_frame,
        textvariable=connection_value,
        wraplength=500,
        style="Muted.TLabel",
    ).grid(
        row=2, column=0, sticky="w", pady=(4, 0)
    )
    ttk.Label(
        source_frame,
        textvariable=evidence_value,
        wraplength=500,
        style="Muted.TLabel",
    ).grid(
        row=3, column=0, sticky="w", pady=(4, 0)
    )

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
        wraplength=500,
        style="Body.TLabel",
    ).grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(
        config_frame,
        textvariable=safety_value,
        wraplength=500,
        style="Muted.TLabel",
    ).grid(
        row=1, column=0, sticky="w", pady=(6, 0)
    )

    progress_frame = ttk.LabelFrame(
        container,
        text="Run status",
        padding=12,
        style="Card.TLabelframe",
    )
    progress_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=6)
    progress_frame.columnconfigure(0, weight=1)
    ttk.Label(
        progress_frame,
        textvariable=progress_value,
        wraplength=900,
        style="Body.TLabel",
    ).grid(
        row=0, column=0, sticky="w"
    )
    progress_bar = ttk.Progressbar(progress_frame, mode="determinate")
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

    plot_frame = ttk.LabelFrame(
        container,
        text="Observations / finalized analysis points",
        padding=12,
        style="Card.TLabelframe",
    )
    plot_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=6)
    plot_frame.columnconfigure(0, weight=1)
    plot_frame.rowconfigure(1, weight=1)
    ttk.Label(
        plot_frame,
        textvariable=plot_value,
        wraplength=1020,
        style="Muted.TLabel",
    ).grid(
        row=0, column=0, sticky="w"
    )
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
        ("index", "No.", 60),
        ("label", "Observation / point", 230),
        ("disposition", "Status", 120),
        ("values", "Values copied from the result", 610),
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
        text="Result, evidence & limitations",
        padding=12,
        style="Card.TLabelframe",
    )
    result_frame.grid(row=4, column=0, sticky="nsew", padx=(0, 6), pady=(6, 0))
    ttk.Label(
        result_frame,
        textvariable=result_value,
        wraplength=500,
        justify="left",
        style="Body.TLabel",
    ).grid(row=0, column=0, sticky="nw")

    artifacts_frame = ttk.LabelFrame(
        container,
        text="Saved artifacts",
        padding=12,
        style="Card.TLabelframe",
    )
    artifacts_frame.grid(row=4, column=1, sticky="nsew", padx=(6, 0), pady=(6, 0))
    ttk.Label(
        artifacts_frame,
        textvariable=artifacts_value,
        wraplength=500,
        justify="left",
        style="Body.TLabel",
    ).grid(row=0, column=0, sticky="nw")

    return DashboardWidgets(
        source_value,
        profile_value,
        connection_value,
        evidence_value,
        configuration_value,
        safety_value,
        progress_value,
        plot_value,
        result_value,
        artifacts_value,
        progress_bar,
        cancel_button,
        plot_table,
    )


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
    serial_confirm_read_only: Any
    low_output_limit: Any
    high_output_limit: Any
    target_gain: Any
    gain_tolerance: Any
    max_abs_offset: Any
    min_r_squared: Any
    max_rmse: Any
    minimum_high_threshold: Any
    maximum_high_threshold: Any
    minimum_low_threshold: Any
    maximum_low_threshold: Any
    minimum_width: Any
    maximum_width: Any
    maximum_width_span: Any
    export_path: Any
    export_format: Any
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
            "sample_count",
            "rising_count",
            "falling_count",
            "replay_path",
            "replay_minimum",
            "replay_maximum",
            "serial_port",
            "serial_baud_rate",
            "serial_read_timeout",
            "serial_max_polls",
            "low_output_limit",
            "high_output_limit",
            "target_gain",
            "gain_tolerance",
            "max_abs_offset",
            "min_r_squared",
            "max_rmse",
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
                "sample_count",
                "rising_count",
                "falling_count",
                "replay_path",
                "replay_minimum",
                "replay_maximum",
                "serial_port",
                "serial_baud_rate",
                "serial_read_timeout",
                "serial_max_polls",
                "low_output_limit",
                "high_output_limit",
                "target_gain",
                "gain_tolerance",
                "max_abs_offset",
                "min_r_squared",
                "max_rmse",
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
        return DashboardWizardDraft(
            source_mode=base.source_mode,
            job_type=base.job_type,
            profile_name=base.profile_name,
            profile_version=base.profile_version,
            operation=type(base.operation)(str(self.operation.get())),
            unit=type(base.unit)(str(self.unit.get())),
            serial_confirm_read_only=bool(self.serial_confirm_read_only.get()),
            export_format=DashboardExportFormat(str(self.export_format.get())),
            **values,
        )


@dataclass(slots=True)
class DashboardWorkflowWidgets:
    """Six-step controls plus the existing finalized-result renderer."""

    result_widgets: DashboardWidgets
    form: DashboardFormVariables
    guidance_value: Any
    step_value: Any
    field_help_value: Any
    review_value: Any
    issue_value: Any
    ports_value: Any
    export_value: Any
    next_steps_value: Any
    source_select: Any
    profile_select: Any
    job_select: Any
    serial_port_select: Any
    export_path_input: Any
    export_format_select: Any
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
    scroll_canvases: tuple[Any, Any] = (None, None)
    editable_controls: tuple[
        tuple[Any, str, tuple[str, ...], tuple[str, ...]], ...
    ] = ()
    _rendered_dashboard_revision: int = -1
    _rendered_wizard_revision: int = -1
    _current_draft: DashboardWizardDraft = field(default_factory=DashboardWizardDraft)
    _last_step: DashboardWizardStep | None = None

    def render(self, dashboard: DashboardState, wizard: DashboardWizardState) -> None:
        if not isinstance(dashboard, DashboardState):
            raise ProductRequestError("dashboard must be a DashboardState")
        if not isinstance(wizard, DashboardWizardState):
            raise ProductRequestError("wizard must be a DashboardWizardState")
        dashboard_changed = dashboard.revision != self._rendered_dashboard_revision
        wizard_changed = wizard.revision != self._rendered_wizard_revision
        if not dashboard_changed and not wizard_changed:
            return
        if dashboard_changed:
            self.result_widgets.render(dashboard)
            self._rendered_dashboard_revision = dashboard.revision
        if not wizard_changed:
            return
        guidance = wizard.guidance
        steps = (
            "01 Source",
            "02 Test",
            "03 Configure",
            "04 Review",
            "05 Run",
            "06 Result",
        )
        self.step_value.set(
            "   ·   ".join(steps)
            + f"\nStep {guidance.number} of 6  —  {guidance.title}"
        )
        self.guidance_value.set(
            f"{guidance.what}\n"
            f"Why it matters: {guidance.why}\n"
            f"Before continuing: {guidance.confirm}"
        )
        source = wizard.draft.source_mode.value
        job = wizard.draft.job_type.value
        self.field_help_value.set(
            f"Active setup: {source} · {job}. "
            "Only relevant controls are editable; disabled controls grant no permissions."
        )
        self.review_value.set(
            "Configuration has not been compiled."
            if not wizard.review_lines
            else "\n".join(f"- {line}" for line in wizard.review_lines)
        )
        issue_text = (
            "No issue."
            if wizard.issue is None
            else (
                f"{wizard.issue.severity.value} [{wizard.issue.code.value}]\n"
                f"What happened: {wizard.issue.what_happened}\n"
                f"Possible cause: {wizard.issue.possible_cause}\n"
                f"Safe next step: {wizard.issue.safe_next_step}"
            )
        )
        self.issue_value.set(issue_text)
        self.ports_value.set(
            "Ports not discovered. Discovery never opens a port."
            if not wizard.discovered_ports
            else "Discovered logical IDs: "
            + ", ".join(port.port_id for port in wizard.discovered_ports)
        )
        self.export_value.set(
            "Export not completed.\n" + issue_text
            if wizard.step is DashboardWizardStep.RESULT
            and wizard.issue is not None
            else wizard.export_message
        )
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
            values=tuple(mode.value for mode in wizard.source_modes)
        )
        self.profile_select.configure(values=wizard.profile_identities)
        self.job_select.configure(
            values=tuple(job_type.value for job_type in wizard.job_types)
        )
        self.serial_port_select.configure(
            values=tuple(port.port_id for port in wizard.discovered_ports)
        )
        self.source_select.configure(
            state=(
                "readonly"
                if wizard.step is DashboardWizardStep.SOURCE
                else "disabled"
            )
        )
        self.profile_select.configure(
            state=(
                "readonly"
                if wizard.step is DashboardWizardStep.SOURCE
                else "disabled"
            )
        )
        self.job_select.configure(
            state=(
                "readonly"
                if wizard.step is DashboardWizardStep.TEST
                else "disabled"
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
        self.export_format_select.configure(
            state="readonly" if wizard.can_export else "disabled"
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
            step is DashboardWizardStep.CONFIGURATION,
        )
        _set_grid_visible(
            self.section_frames["acceptance"],
            step is DashboardWizardStep.CONFIGURATION
            and job in {"DC_ANALYSIS", "HYSTERESIS_ANALYSIS"},
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
        self._rendered_wizard_revision = wizard.revision
        self._current_draft = wizard.draft
        self._last_step = wizard.step


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
) -> tuple[Any, Any | None]:
    """Create one width-tracking page with a visible vertical scrollbar."""

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
        background=_BACKGROUND,
        borderwidth=0,
        highlightthickness=0,
        yscrollincrement=32,
    )
    scrollbar = scrollbar_factory(host, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    page = ttk_module.Frame(canvas, style="App.TFrame")
    window_id = canvas.create_window((0, 0), window=page, anchor="nw")

    def sync_scroll_region(_event: object) -> None:
        canvas.configure(scrollregion=canvas.bbox("all"))

    def sync_page_width(event: object) -> None:
        width = getattr(event, "width", None)
        if isinstance(width, int) and width > 0:
            canvas.itemconfigure(window_id, width=width)

    page.bind("<Configure>", sync_scroll_region)
    canvas.bind("<Configure>", sync_page_width)
    return page, canvas


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
    on_review: Callable[[DashboardWizardDraft], object],
    on_run: Callable[[], object],
    on_cancel: Callable[[], object],
    on_discover: Callable[[], object],
    on_export: Callable[[str, str], object],
    on_modify: Callable[[], object],
    on_repeat: Callable[[], object],
    on_new_test: Callable[[], object],
    on_close: Callable[[], object],
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
    if root is None or tk_module is None or ttk_module is None:
        raise ProductRequestError("root, tk_module, and ttk_module are required")
    tk = tk_module
    ttk = ttk_module
    configure_dashboard_style(root, ttk)
    root.title("Analog Validation Studio")
    root.minsize(1180, 780)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(1, weight=1)

    header = ttk.Frame(root, padding=(20, 14), style="Header.TFrame")
    header.grid(row=0, column=0, sticky="ew")
    header.columnconfigure(0, weight=1)
    ttk.Label(
        header,
        text="Analog Validation Studio",
        style="HeaderTitle.TLabel",
    ).grid(row=0, column=0, sticky="w")
    ttk.Label(
        header,
        text=(
            "Offline, evidence-aware test workflow · simulator-first · "
            "hardware claims remain explicit"
        ),
        style="HeaderSubtitle.TLabel",
    ).grid(row=1, column=0, sticky="w", pady=(3, 0))
    ttk.Label(
        header,
        text="READ-ONLY BY DEFAULT",
        style="Badge.TLabel",
    ).grid(row=0, column=1, rowspan=2, sticky="e")

    notebook_factory = getattr(ttk, "Notebook", None)
    if callable(notebook_factory):
        notebook = notebook_factory(root, style="Modern.TNotebook")
        notebook.grid(row=1, column=0, sticky="nsew")
        workflow_tab = ttk.Frame(notebook, style="App.TFrame")
        result_tab = ttk.Frame(notebook, style="App.TFrame")
        notebook.add(workflow_tab, text="Setup & run")
        notebook.add(result_tab, text="Results & evidence")
        workflow_page, workflow_scroll_canvas = _create_scrollable_page(
            workflow_tab, tk, ttk
        )
        result_host, result_scroll_canvas = _create_scrollable_page(
            result_tab, tk, ttk
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
    result_content_host.grid(row=2, column=0, sticky="nsew")
    result_content_host.columnconfigure(0, weight=1)
    result_content_host.rowconfigure(0, weight=1)
    result_widgets = create_dashboard_widgets(
        root,
        tk,
        ttk,
        on_cancel=on_cancel,
        on_close=on_close,
        parent=result_content_host,
        configure_window=False,
    )

    string_var = tk.StringVar
    boolean_var = getattr(tk, "BooleanVar", string_var)
    form = DashboardFormVariables(  # type: ignore[call-arg]
        *(string_var(master=root, value="") for _ in range(18)),
        boolean_var(master=root, value=False),
        *(string_var(master=root, value="") for _ in range(15)),
        string_var(master=root, value="json"),
    )
    step_value = string_var(master=root, value="")
    guidance_value = string_var(master=root, value="")
    field_help_value = string_var(master=root, value="")
    review_value = string_var(master=root, value="")
    issue_value = string_var(master=root, value="")
    ports_value = string_var(master=root, value="")
    export_value = string_var(master=root, value="")
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
    for column in range(6):
        wizard_frame.columnconfigure(column, weight=1)
    ttk.Label(
        wizard_frame,
        textvariable=step_value,
        justify="left",
        style="Title.TLabel",
    ).grid(
        row=0, column=0, columnspan=6, sticky="w"
    )
    ttk.Label(
        wizard_frame,
        textvariable=guidance_value,
        wraplength=1210,
        justify="left",
        style="Muted.TLabel",
    ).grid(row=1, column=0, columnspan=6, sticky="w", pady=(5, 10))

    setup_frame = ttk.LabelFrame(
        wizard_frame,
        text="Test setup",
        padding=10,
        style="Card.TLabelframe",
    )
    setup_frame.grid(row=2, column=0, columnspan=6, sticky="ew")
    for column in range(6):
        setup_frame.columnconfigure(column, weight=1)

    source_select = combobox(
        setup_frame, textvariable=form.source, state="readonly", takefocus=True
    )
    profile_select = combobox(
        setup_frame, textvariable=form.profile, state="readonly", takefocus=True
    )
    job_select = combobox(
        setup_frame, textvariable=form.job, state="readonly", takefocus=True
    )
    primary_channel_input = entry(setup_frame, textvariable=form.primary_channel)
    secondary_channel_input = entry(setup_frame, textvariable=form.secondary_channel)
    state_channel_input = entry(setup_frame, textvariable=form.state_channel)
    for column, label, widget in (
        (0, "Source", source_select),
        (1, "Profile", profile_select),
        (2, "Test", job_select),
        (3, "Primary channel", primary_channel_input),
        (4, "Secondary channel", secondary_channel_input),
        (5, "State channel", state_channel_input),
    ):
        ttk.Label(setup_frame, text=label, style="Muted.TLabel").grid(
            row=0, column=column, sticky="w"
        )
        widget.grid(row=1, column=column, sticky="ew", padx=(0, 8), pady=(3, 0))

    signal_frame = ttk.LabelFrame(
        wizard_frame,
        text="Signal & sampling",
        padding=10,
        style="Card.TLabelframe",
    )
    signal_frame.grid(row=3, column=0, columnspan=6, sticky="ew", pady=(8, 0))
    for column in range(6):
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
        ("Samples / DC points", sample_count_input),
        ("Rising samples", rising_count_input),
        ("Falling samples", falling_count_input),
        ("Target gain", target_gain_input),
    )
    for column, (label, widget) in enumerate(config_fields):
        ttk.Label(signal_frame, text=label, style="Muted.TLabel").grid(
            row=0, column=column, sticky="w"
        )
        widget.grid(row=1, column=column, sticky="ew", padx=(0, 8), pady=(3, 0))

    acceptance_frame = ttk.LabelFrame(
        wizard_frame,
        text="Acceptance criteria — analysis tests only",
        padding=10,
        style="Card.TLabelframe",
    )
    acceptance_frame.grid(
        row=4, column=0, columnspan=6, sticky="ew", pady=(8, 0)
    )
    for column in range(6):
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
        row = (index // 6) * 2
        column = index % 6
        ttk.Label(acceptance_frame, text=label, style="Muted.TLabel").grid(
            row=row, column=column, sticky="w"
        )
        selected_input = entry(acceptance_frame, textvariable=variable)
        selected_input.grid(
            row=row + 1, column=column, sticky="ew", padx=(0, 6)
        )
        acceptance_inputs.append(selected_input)
    ttk.Label(
        acceptance_frame,
        text="Maximum width span",
        style="Muted.TLabel",
    ).grid(
        row=4, column=0, sticky="w"
    )
    maximum_width_span_input = entry(
        acceptance_frame, textvariable=form.maximum_width_span
    )
    maximum_width_span_input.grid(
        row=5, column=0, sticky="ew", padx=(0, 6)
    )

    source_frame = ttk.LabelFrame(
        wizard_frame,
        text="Source connection — opened only after explicit Run",
        padding=10,
        style="Card.TLabelframe",
    )
    source_frame.grid(row=5, column=0, columnspan=6, sticky="ew", pady=(8, 0))
    for column in range(6):
        source_frame.columnconfigure(column, weight=1)

    replay_path_input = entry(source_frame, textvariable=form.replay_path)
    replay_minimum_input = entry(source_frame, textvariable=form.replay_minimum)
    replay_maximum_input = entry(source_frame, textvariable=form.replay_maximum)
    replay_fields = (
        ("Replay CSV path", replay_path_input),
        ("Replay minimum", replay_minimum_input),
        ("Replay maximum", replay_maximum_input),
    )
    for column, (label, widget) in enumerate(replay_fields):
        ttk.Label(source_frame, text=label, style="Muted.TLabel").grid(
            row=0, column=column, sticky="w"
        )
        widget.grid(row=1, column=column, sticky="ew", padx=(0, 8), pady=(3, 0))

    serial_port_select = combobox(
        source_frame,
        textvariable=form.serial_port,
        state="normal",
        takefocus=True,
    )
    serial_baud_input = entry(source_frame, textvariable=form.serial_baud_rate)
    serial_timeout_input = entry(
        source_frame, textvariable=form.serial_read_timeout
    )
    serial_polls_input = entry(source_frame, textvariable=form.serial_max_polls)
    serial_fields = (
        ("Serial port", serial_port_select),
        ("Baud rate", serial_baud_input),
        ("Read timeout (s)", serial_timeout_input),
        ("Maximum polls", serial_polls_input),
    )
    for column, (label, widget) in enumerate(serial_fields):
        ttk.Label(source_frame, text=label, style="Muted.TLabel").grid(
            row=2, column=column, sticky="w", pady=(8, 0)
        )
        widget.grid(row=3, column=column, sticky="ew", padx=(0, 8), pady=(3, 0))
    serial_confirmation = checkbutton(
        source_frame,
        text="I confirm that this serial session is receive-only",
        variable=form.serial_confirm_read_only,
        takefocus=True,
    )
    serial_confirmation.grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))

    ttk.Label(
        source_frame,
        textvariable=field_help_value,
        wraplength=600,
        justify="left",
        style="Muted.TLabel",
    ).grid(row=4, column=3, columnspan=3, sticky="w", pady=(8, 0))
    ttk.Label(
        source_frame,
        textvariable=ports_value,
        wraplength=1210,
        justify="left",
        style="Muted.TLabel",
    ).grid(row=5, column=0, columnspan=6, sticky="w", pady=(6, 0))

    review_frame = ttk.Frame(wizard_frame, style="Card.TFrame")
    review_frame.grid(row=6, column=0, columnspan=6, sticky="ew", pady=(8, 0))
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
        wraplength=590,
        justify="left",
        style="Body.TLabel",
    ).grid(row=0, column=0, sticky="nw")
    ttk.Label(
        issue_summary,
        textvariable=issue_value,
        wraplength=590,
        justify="left",
        style="Body.TLabel",
    ).grid(row=0, column=0, sticky="nw")

    action_frame = ttk.Frame(wizard_frame, style="Card.TFrame")
    action_frame.grid(row=7, column=0, columnspan=6, sticky="ew", pady=(10, 0))
    for column in range(5):
        action_frame.columnconfigure(column, weight=1)
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
    review_button = ttk.Button(
        action_frame,
        text="Validate setup",
        command=lambda: on_review(form.snapshot()),
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
        button.grid(row=0, column=column, sticky="ew", padx=(0, 8))

    export_frame = ttk.LabelFrame(
        result_host,
        text="Save finalized analysis — existing files are never overwritten",
        padding=10,
        style="Card.TLabelframe",
    )
    export_frame.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 0))
    for column in range(7):
        export_frame.columnconfigure(column, weight=1)
    ttk.Label(
        export_frame,
        textvariable=export_value,
        wraplength=600,
        justify="left",
        style="Muted.TLabel",
    ).grid(row=0, column=0, rowspan=2, columnspan=3, sticky="w")
    ttk.Label(export_frame, text="Destination path", style="Muted.TLabel").grid(
        row=0, column=3, columnspan=2, sticky="w"
    )
    export_path_input = entry(export_frame, textvariable=form.export_path)
    export_path_input.grid(
        row=1, column=3, columnspan=2, sticky="ew", padx=(0, 8), pady=(3, 0)
    )
    ttk.Label(export_frame, text="Format", style="Muted.TLabel").grid(
        row=0, column=5, sticky="w"
    )
    export_format_select = combobox(
        export_frame,
        textvariable=form.export_format,
        values=("json", "csv"),
        state="readonly",
        takefocus=True,
    )
    export_format_select.grid(row=1, column=5, sticky="ew", pady=(3, 0))
    export_button = ttk.Button(
        export_frame,
        text="Save analysis result",
        command=lambda: on_export(
            str(form.export_path.get()), str(form.export_format.get())
        ),
        takefocus=True,
        style="Primary.TButton",
    )
    export_button.grid(row=1, column=6, sticky="ew", padx=(8, 0), pady=(3, 0))

    next_steps_frame = ttk.LabelFrame(
        result_host,
        text="What would you like to do next?",
        padding=10,
        style="Card.TLabelframe",
    )
    next_steps_frame.grid(
        row=1, column=0, sticky="ew", padx=18, pady=(8, 0)
    )
    for column in range(4):
        next_steps_frame.columnconfigure(column, weight=1)
    ttk.Label(
        next_steps_frame,
        textvariable=next_steps_value,
        wraplength=1210,
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
        style="Primary.TButton",
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

    all_jobs = ("READ", "DC_ANALYSIS", "HYSTERESIS_ANALYSIS")
    editable_controls = (
        (primary_channel_input, "normal", all_jobs, ()),
        (secondary_channel_input, "normal", ("DC_ANALYSIS",), ()),
        (state_channel_input, "normal", ("HYSTERESIS_ANALYSIS",), ()),
        (operation_select, "readonly", ("READ",), ()),
        (unit_select, "readonly", all_jobs, ()),
        (sample_count_input, "normal", ("READ", "DC_ANALYSIS"), ()),
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
        (replay_path_input, "normal", all_jobs, ("CSV_REPLAY",)),
        (replay_minimum_input, "normal", all_jobs, ("CSV_REPLAY",)),
        (replay_maximum_input, "normal", all_jobs, ("CSV_REPLAY",)),
        (serial_port_select, "normal", ("READ",), ("SERIAL_READ_ONLY",)),
        (serial_baud_input, "normal", ("READ",), ("SERIAL_READ_ONLY",)),
        (serial_timeout_input, "normal", ("READ",), ("SERIAL_READ_ONLY",)),
        (serial_polls_input, "normal", ("READ",), ("SERIAL_READ_ONLY",)),
        (serial_confirmation, "normal", ("READ",), ("SERIAL_READ_ONLY",)),
    )

    widgets = DashboardWorkflowWidgets(
        result_widgets=result_widgets,
        form=form,
        guidance_value=guidance_value,
        step_value=step_value,
        field_help_value=field_help_value,
        review_value=review_value,
        issue_value=issue_value,
        ports_value=ports_value,
        export_value=export_value,
        next_steps_value=next_steps_value,
        source_select=source_select,
        profile_select=profile_select,
        job_select=job_select,
        serial_port_select=serial_port_select,
        export_path_input=export_path_input,
        export_format_select=export_format_select,
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
            "source_connection": source_frame,
            "review": review_frame,
            "workflow_actions": action_frame,
            "export": export_frame,
            "result_actions": next_steps_frame,
        },
        scroll_canvases=(workflow_scroll_canvas, result_scroll_canvas),
        editable_controls=editable_controls,
    )
    _bind_mouse_wheel(
        root,
        (workflow_scroll_canvas, result_scroll_canvas),
    )
    _bind_selection(source_select, lambda: on_source(str(form.source.get())))
    _bind_selection(profile_select, lambda: on_profile(str(form.profile.get())))
    _bind_selection(job_select, lambda: on_job(str(form.job.get())))
    return widgets


__all__ = [
    "DashboardFormVariables",
    "DashboardWidgets",
    "DashboardWorkflowWidgets",
    "configure_dashboard_style",
    "create_dashboard_widgets",
    "create_dashboard_workflow_widgets",
]
