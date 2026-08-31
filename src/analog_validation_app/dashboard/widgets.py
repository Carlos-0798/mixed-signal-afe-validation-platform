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
)


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

    def render(self, state: DashboardState) -> None:
        """Render text and copied report rows; never infer engineering state."""

        if not isinstance(state, DashboardState):
            raise ProductRequestError("state must be a DashboardState")
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
    host = root if parent is None else parent
    if configure_window:
        root.title("Analog Validation Studio — Software Dashboard")
        root.minsize(960, 720)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

    container = ttk.Frame(host, padding=12)
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

    source_frame = ttk.LabelFrame(container, text="1. Source / Profile", padding=8)
    source_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 6))
    ttk.Label(source_frame, textvariable=source_value, wraplength=430).grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(source_frame, textvariable=profile_value, wraplength=430).grid(
        row=1, column=0, sticky="w", pady=(4, 0)
    )
    ttk.Label(source_frame, textvariable=connection_value, wraplength=430).grid(
        row=2, column=0, sticky="w", pady=(4, 0)
    )
    ttk.Label(source_frame, textvariable=evidence_value, wraplength=430).grid(
        row=3, column=0, sticky="w", pady=(4, 0)
    )

    config_frame = ttk.LabelFrame(
        container, text="2. Configuration / Safe review", padding=8
    )
    config_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 6))
    ttk.Label(config_frame, textvariable=configuration_value, wraplength=430).grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(config_frame, textvariable=safety_value, wraplength=430).grid(
        row=1, column=0, sticky="w", pady=(6, 0)
    )

    progress_frame = ttk.LabelFrame(container, text="3. Progress", padding=8)
    progress_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=6)
    progress_frame.columnconfigure(0, weight=1)
    ttk.Label(progress_frame, textvariable=progress_value, wraplength=760).grid(
        row=0, column=0, sticky="w"
    )
    progress_bar = ttk.Progressbar(progress_frame, mode="determinate")
    progress_bar.grid(row=1, column=0, sticky="ew", pady=(6, 0))
    cancel_button = ttk.Button(progress_frame, text="Cancel safely", command=cancel)
    cancel_button.grid(row=0, column=1, padx=(8, 0))
    ttk.Button(progress_frame, text="Close", command=close).grid(
        row=1, column=1, padx=(8, 0), pady=(6, 0)
    )

    plot_frame = ttk.LabelFrame(
        container, text="4. Plot / finalized point table", padding=8
    )
    plot_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=6)
    plot_frame.columnconfigure(0, weight=1)
    plot_frame.rowconfigure(1, weight=1)
    ttk.Label(plot_frame, textvariable=plot_value, wraplength=860).grid(
        row=0, column=0, sticky="w"
    )
    columns = ("index", "label", "disposition", "values")
    plot_table = ttk.Treeview(plot_frame, columns=columns, show="headings", height=8)
    for column, heading, width in (
        ("index", "Index", 60),
        ("label", "Label", 180),
        ("disposition", "Disposition", 120),
        ("values", "Copied values", 520),
    ):
        plot_table.heading(column, text=heading)
        plot_table.column(column, width=width, stretch=column == "values")
    plot_table.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

    result_frame = ttk.LabelFrame(container, text="5. Result / Evidence", padding=8)
    result_frame.grid(row=4, column=0, sticky="nsew", padx=(0, 6), pady=(6, 0))
    ttk.Label(
        result_frame, textvariable=result_value, wraplength=430, justify="left"
    ).grid(row=0, column=0, sticky="nw")

    artifacts_frame = ttk.LabelFrame(container, text="6. Artifacts", padding=8)
    artifacts_frame.grid(row=4, column=1, sticky="nsew", padx=(6, 0), pady=(6, 0))
    ttk.Label(
        artifacts_frame,
        textvariable=artifacts_value,
        wraplength=430,
        justify="left",
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
    source_select: Any
    profile_select: Any
    job_select: Any
    serial_port_select: Any
    back_button: Any
    next_button: Any
    review_button: Any
    run_button: Any
    export_button: Any
    discover_button: Any
    _rendered_wizard_revision: int = -1
    _current_draft: DashboardWizardDraft = field(default_factory=DashboardWizardDraft)

    def render(self, dashboard: DashboardState, wizard: DashboardWizardState) -> None:
        if not isinstance(wizard, DashboardWizardState):
            raise ProductRequestError("wizard must be a DashboardWizardState")
        self.result_widgets.render(dashboard)
        guidance = wizard.guidance
        self.step_value.set(
            "1 Source  >  2 Test  >  3 Configure  >  4 Review  >  5 Run  >  6 Result\n"
            f"Current: {guidance.number}. {guidance.title}"
        )
        self.guidance_value.set(
            f"What: {guidance.what}\nWhy: {guidance.why}\nConfirm: {guidance.confirm}"
        )
        source = wizard.draft.source_mode.value
        job = wizard.draft.job_type.value
        self.field_help_value.set(
            f"Active source/test: {source} / {job}. "
            "Only matching fields are compiled; unused fields do not grant permissions."
        )
        self.review_value.set(
            "Configuration has not been compiled."
            if not wizard.review_lines
            else "\n".join(f"- {line}" for line in wizard.review_lines)
        )
        self.issue_value.set(
            "No issue."
            if wizard.issue is None
            else (
                f"{wizard.issue.severity.value} [{wizard.issue.code.value}]\n"
                f"What happened: {wizard.issue.what_happened}\n"
                f"Possible cause: {wizard.issue.possible_cause}\n"
                f"Safe next step: {wizard.issue.safe_next_step}"
            )
        )
        self.ports_value.set(
            "Ports not discovered. Discovery never opens a port."
            if not wizard.discovered_ports
            else "Discovered logical IDs: "
            + ", ".join(port.port_id for port in wizard.discovered_ports)
        )
        self.export_value.set(wizard.export_message)
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
        for button, enabled in (
            (self.back_button, wizard.can_back),
            (self.next_button, wizard.can_next),
            (self.review_button, wizard.can_prepare_review),
            (self.run_button, wizard.can_run),
            (self.export_button, wizard.can_export),
            (
                self.discover_button,
                wizard.draft.source_mode.value == "SERIAL_READ_ONLY"
                and wizard.step.value in {"SOURCE", "CONFIGURATION"},
            ),
        ):
            button.configure(state="normal" if enabled else "disabled")
        if wizard.revision != self._rendered_wizard_revision:
            self.form.load(wizard.draft)
            self._rendered_wizard_revision = wizard.revision
        self._current_draft = wizard.draft


def _bind_selection(widget: Any, callback: Callable[[], object]) -> None:
    binder = getattr(widget, "bind", None)
    if callable(binder):
        binder("<<ComboboxSelected>>", lambda _event: callback())


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
    on_close: Callable[[], object],
) -> DashboardWorkflowWidgets:
    """Create the fixed six-step UI while keeping decisions in headless layers."""

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
    root.title("Analog Validation Studio — Six-step Validation Workflow")
    root.minsize(1180, 900)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(1, weight=1)

    result_host = ttk.Frame(root)
    result_host.grid(row=1, column=0, sticky="nsew")
    result_host.columnconfigure(0, weight=1)
    result_host.rowconfigure(0, weight=1)
    result_widgets = create_dashboard_widgets(
        root,
        tk,
        ttk,
        on_cancel=on_cancel,
        on_close=on_close,
        parent=result_host,
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

    entry = getattr(ttk, "Entry", ttk.Label)
    combobox = getattr(ttk, "Combobox", entry)
    checkbutton = getattr(ttk, "Checkbutton", ttk.Button)

    wizard_frame = ttk.LabelFrame(root, text="Beginner workflow", padding=10)
    wizard_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 0))
    for column in range(6):
        wizard_frame.columnconfigure(column, weight=1)
    ttk.Label(wizard_frame, textvariable=step_value, justify="left").grid(
        row=0, column=0, columnspan=6, sticky="w"
    )
    ttk.Label(
        wizard_frame, textvariable=guidance_value, wraplength=1120, justify="left"
    ).grid(row=1, column=0, columnspan=6, sticky="w", pady=(4, 8))

    source_select = combobox(wizard_frame, textvariable=form.source, state="readonly")
    profile_select = combobox(wizard_frame, textvariable=form.profile, state="readonly")
    job_select = combobox(wizard_frame, textvariable=form.job, state="readonly")
    for column, label, widget in (
        (0, "Source", source_select),
        (1, "Profile", profile_select),
        (2, "Test", job_select),
        (3, "Primary channel", entry(wizard_frame, textvariable=form.primary_channel)),
        (
            4,
            "Secondary channel",
            entry(wizard_frame, textvariable=form.secondary_channel),
        ),
        (5, "State channel", entry(wizard_frame, textvariable=form.state_channel)),
    ):
        ttk.Label(wizard_frame, text=label).grid(row=2, column=column, sticky="w")
        widget.grid(row=3, column=column, sticky="ew", padx=(0, 6))

    operation_select = combobox(
        wizard_frame,
        textvariable=form.operation,
        values=("ANALOG", "DIGITAL"),
        state="readonly",
    )
    unit_select = combobox(
        wizard_frame,
        textvariable=form.unit,
        values=("V", "mV", "boolean", "unitless"),
        state="readonly",
    )
    config_fields = (
        ("Operation", operation_select),
        ("Unit", unit_select),
        ("Samples / DC points", entry(wizard_frame, textvariable=form.sample_count)),
        ("Rising count", entry(wizard_frame, textvariable=form.rising_count)),
        ("Falling count", entry(wizard_frame, textvariable=form.falling_count)),
        ("Target gain", entry(wizard_frame, textvariable=form.target_gain)),
    )
    for column, (label, widget) in enumerate(config_fields):
        ttk.Label(wizard_frame, text=label).grid(row=4, column=column, sticky="w")
        widget.grid(row=5, column=column, sticky="ew", padx=(0, 6))

    acceptance_frame = ttk.LabelFrame(
        wizard_frame, text="Reviewed acceptance criteria", padding=6
    )
    acceptance_frame.grid(row=6, column=0, columnspan=6, sticky="ew", pady=(6, 0))
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
    for index, (label, variable) in enumerate(acceptance_fields):
        row = (index // 6) * 2
        column = index % 6
        ttk.Label(acceptance_frame, text=label).grid(row=row, column=column, sticky="w")
        entry(acceptance_frame, textvariable=variable).grid(
            row=row + 1, column=column, sticky="ew", padx=(0, 6)
        )
    ttk.Label(acceptance_frame, text="Maximum width span").grid(
        row=4, column=0, sticky="w"
    )
    entry(acceptance_frame, textvariable=form.maximum_width_span).grid(
        row=5, column=0, sticky="ew", padx=(0, 6)
    )

    replay_fields = (
        ("Replay CSV path", form.replay_path),
        ("Replay minimum", form.replay_minimum),
        ("Replay maximum", form.replay_maximum),
    )
    for column, (label, variable) in enumerate(replay_fields):
        ttk.Label(wizard_frame, text=label).grid(row=7, column=column, sticky="w")
        entry(wizard_frame, textvariable=variable).grid(
            row=8, column=column, sticky="ew", padx=(0, 6)
        )

    serial_port_select = combobox(
        wizard_frame, textvariable=form.serial_port, state="normal"
    )
    serial_fields = (
        ("Serial port", serial_port_select),
        ("Baud", entry(wizard_frame, textvariable=form.serial_baud_rate)),
        (
            "Read timeout (s)",
            entry(wizard_frame, textvariable=form.serial_read_timeout),
        ),
        ("Max polls", entry(wizard_frame, textvariable=form.serial_max_polls)),
    )
    for offset, (label, widget) in enumerate(serial_fields, start=0):
        column = offset
        ttk.Label(wizard_frame, text=label).grid(row=9, column=column, sticky="w")
        widget.grid(row=10, column=column, sticky="ew", padx=(0, 6))
    checkbutton(
        wizard_frame,
        text="I confirm receive-only operation",
        variable=form.serial_confirm_read_only,
    ).grid(row=11, column=0, columnspan=3, sticky="w")

    ttk.Label(
        wizard_frame, textvariable=field_help_value, wraplength=1120, justify="left"
    ).grid(row=11, column=3, columnspan=3, sticky="w")
    ttk.Label(
        wizard_frame, textvariable=ports_value, wraplength=1120, justify="left"
    ).grid(row=12, column=0, columnspan=6, sticky="w")
    ttk.Label(
        wizard_frame, textvariable=review_value, wraplength=1120, justify="left"
    ).grid(row=13, column=0, columnspan=3, sticky="nw", pady=(6, 0))
    ttk.Label(
        wizard_frame, textvariable=issue_value, wraplength=1120, justify="left"
    ).grid(row=13, column=3, columnspan=3, sticky="nw", pady=(6, 0))

    back_button = ttk.Button(wizard_frame, text="Back", command=on_back)
    next_button = ttk.Button(wizard_frame, text="Next", command=on_next)
    review_button = ttk.Button(
        wizard_frame,
        text="Validate & review",
        command=lambda: on_review(form.snapshot()),
    )
    run_button = ttk.Button(wizard_frame, text="Run reviewed job", command=on_run)
    discover_button = ttk.Button(
        wizard_frame, text="Discover ports", command=on_discover
    )
    export_button = ttk.Button(
        wizard_frame,
        text="Export (no overwrite)",
        command=lambda: on_export(
            str(form.export_path.get()), str(form.export_format.get())
        ),
    )
    for column, button in enumerate(
        (
            back_button,
            next_button,
            review_button,
            run_button,
            discover_button,
            export_button,
        )
    ):
        button.grid(row=14, column=column, sticky="ew", padx=(0, 6), pady=(8, 0))
    entry(wizard_frame, textvariable=form.export_path).grid(
        row=15, column=3, columnspan=2, sticky="ew", pady=(6, 0)
    )
    combobox(
        wizard_frame,
        textvariable=form.export_format,
        values=("json", "csv"),
        state="readonly",
    ).grid(row=15, column=5, sticky="ew", pady=(6, 0))
    ttk.Label(
        wizard_frame, textvariable=export_value, wraplength=1120, justify="left"
    ).grid(row=15, column=0, columnspan=3, sticky="w", pady=(6, 0))

    widgets = DashboardWorkflowWidgets(
        result_widgets,
        form,
        guidance_value,
        step_value,
        field_help_value,
        review_value,
        issue_value,
        ports_value,
        export_value,
        source_select,
        profile_select,
        job_select,
        serial_port_select,
        back_button,
        next_button,
        review_button,
        run_button,
        export_button,
        discover_button,
    )
    _bind_selection(source_select, lambda: on_source(str(form.source.get())))
    _bind_selection(profile_select, lambda: on_profile(str(form.profile.get())))
    _bind_selection(job_select, lambda: on_job(str(form.job.get())))
    return widgets


__all__ = [
    "DashboardFormVariables",
    "DashboardWidgets",
    "DashboardWorkflowWidgets",
    "create_dashboard_widgets",
    "create_dashboard_workflow_widgets",
]
