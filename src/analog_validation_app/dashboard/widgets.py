"""Tk/ttk rendering only; business state and lifecycle live elsewhere."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..errors import ProductRequestError
from .state import DashboardState


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
) -> DashboardWidgets:
    """Create the six-region local Dashboard using injected Tk modules."""

    cancel = _callback("on_cancel", on_cancel)
    close = _callback("on_close", on_close)
    if root is None or tk_module is None or ttk_module is None:
        raise ProductRequestError("root, tk_module, and ttk_module are required")
    tk = tk_module
    ttk = ttk_module
    root.title("Analog Validation Studio — Software Dashboard")
    root.minsize(960, 720)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    container = ttk.Frame(root, padding=12)
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


__all__ = [
    "DashboardWidgets",
    "create_dashboard_widgets",
]
