"""Project-page controls; all Tk access stays on the UI thread."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..errors import ProductRequestError
from ..models import ProductSourceMode
from ..product_workflows import ProductWorkflowConfiguration
from ..projects import (
    VALIDATION_RUN_MANIFEST_SCHEMA_VERSION,
    VALIDATION_RUN_MANIFEST_V3_SCHEMA_VERSION,
    ProjectRunRecord,
    ValidationRunManifest,
)
from .project_workspace import (
    ProjectBatchReviewSummary,
    ProjectComparisonGuidance,
    ProjectWorkspace,
    _preparation_failure_summary,
)
from .widgets import (
    _bind_mouse_wheel,
    _create_scrollable_page,
    _job_display_name,
    _source_display_name,
)
from .wizard import DashboardWizardDraft


def _bind_table_selection(tree: Any) -> None:
    """Supply keyboard range selection missing from some shipped Tk themes."""
    anchor: str | None = None
    previous: tuple[str, tuple[str, ...]] | None = None

    def reset(event: Any = None) -> None:
        nonlocal anchor, previous
        anchor, previous = None, None

    def select_all(event: Any) -> str:
        reset()
        rows = tree.get_children()
        tree.selection_set(rows)
        if rows and tree.focus() not in rows:
            tree.focus(rows[0])
            tree.see(rows[0])
        return "break"

    def extend(event: Any, direction: int) -> str:
        nonlocal anchor, previous
        rows = tree.get_children()
        if not rows:
            reset()
            return "break"
        focused = tree.focus()
        snapshot = (focused, tuple(tree.selection()))
        if anchor not in rows or previous != snapshot:
            anchor = focused if focused in rows else rows[0]
        position = rows.index(focused) if focused in rows else 0
        target = rows[max(0, min(len(rows) - 1, position + direction))]
        start, end = sorted((rows.index(anchor), rows.index(target)))
        tree.selection_set(rows[start : end + 1])
        tree.focus(target)
        tree.see(target)
        previous = (target, tuple(tree.selection()))
        return "break"

    for sequence in ("<Button-1>", "<Up>", "<Down>", "<Home>", "<End>"):
        tree.bind(sequence, reset, add="+")
    tree.bind("<Control-a>", select_all)
    tree.bind("<Control-A>", select_all)
    tree.bind("<Shift-Up>", lambda event: extend(event, -1))
    tree.bind("<Shift-Down>", lambda event: extend(event, 1))


def _record_text(record: ProjectRunRecord | None) -> str:
    if record is None:
        return "absent"
    outcome = (
        "none"
        if record.engineering_outcome is None
        else record.engineering_outcome.value
    )
    evidence = (
        "none" if record.evidence_source is None else record.evidence_source.value
    )
    status = "none" if record.product_status is None else record.product_status.value
    return f"{record.worker_state.value} / {status} / {outcome} / {evidence}"


def _short_list(values: tuple[str, ...]) -> str:
    if not values:
        return "none"
    visible = values[:4]
    text = ", ".join(visible)
    remaining = len(values) - len(visible)
    return text if not remaining else f"{text}, and {remaining} more"


def _comparison_guidance_text(guidance: ProjectComparisonGuidance) -> str:
    """Explain immutable comparison facts without assigning new conclusions."""

    snapshot = "UNCHANGED" if guidance.same_project_snapshot else "CHANGED"
    baseline_evidence = _short_list(guidance.baseline_evidence_labels)
    candidate_evidence = _short_list(guidance.candidate_evidence_labels)
    if guidance.evidence_label_mismatch_ids:
        evidence_note = (
            "Do not treat mismatched evidence as like-for-like: "
            f"{_short_list(guidance.evidence_label_mismatch_ids)}."
        )
    elif guidance.evidence_unavailable_ids:
        evidence_note = (
            "Evidence is unavailable on one or both sides for: "
            f"{_short_list(guidance.evidence_unavailable_ids)}."
        )
    else:
        evidence_note = (
            "Matched results keep the same evidence labels. Confirm configuration "
            "and requirement direction before drawing a conclusion."
        )
    missing_note = (
        f"baseline-only {_short_list(guidance.baseline_only_result_ids)}; "
        f"candidate-only {_short_list(guidance.candidate_only_result_ids)}; "
        f"not started in baseline {_short_list(guidance.baseline_not_started_ids)}; "
        "not started in candidate "
        f"{_short_list(guidance.candidate_not_started_ids)}"
    )
    return (
        f"Project identity: {guidance.project_id} (same project ID). "
        f"Baseline {guidance.baseline_run_id} [{guidance.baseline_batch_status}] → "
        f"candidate {guidance.candidate_run_id} "
        f"[{guidance.candidate_batch_status}]. Project snapshot: {snapshot}.\n"
        f"Result coverage: {len(guidance.matched_result_ids)} matched; {missing_note}.\n"
        f"Evidence labels — baseline: {baseline_evidence}; candidate: "
        f"{candidate_evidence}. {evidence_note}\n"
        f"Changed presets: {len(guidance.changed_preset_ids)} — "
        f"{_short_list(guidance.changed_preset_ids)}. Numeric delta = candidate - "
        "baseline; its sign does not by itself mean improvement or regression."
    )


def _history_empty_text(run_count: int) -> str:
    if run_count == 0:
        return (
            "No run history is loaded yet. Complete a project batch or load an "
            "existing run manifest; saved files are never scanned automatically."
        )
    if run_count == 1:
        return (
            "History contains one verified run. Add or load one more run from the "
            "same project before comparing."
        )
    return (
        f"History contains {run_count} verified runs. Select exactly two rows; "
        "the first visible row is baseline and the second is candidate."
    )


def _history_input_archive_text(
    manifest: ValidationRunManifest | None, selected_count: int
) -> str:
    """Explain input retention without implying hardware or author verification."""

    if selected_count == 0:
        return (
            "Select one history row to inspect its retained Replay inputs. "
            "Select two rows to compare finalized results."
        )
    if selected_count > 1:
        return (
            "Keep two rows selected for comparison, or select one row to inspect "
            "its retained Replay inputs."
        )
    if manifest is None:  # pragma: no cover - tree/workspace consistency guard
        return "The selected history row is no longer available. Refresh the view."
    failure_summary = _preparation_failure_summary(manifest)
    prefix = f"{failure_summary}\n" if failure_summary else ""
    if manifest.schema_version not in {
        VALIDATION_RUN_MANIFEST_V3_SCHEMA_VERSION,
        VALIDATION_RUN_MANIFEST_SCHEMA_VERSION,
    }:
        return (
            f"Run {manifest.run_id} uses {manifest.schema_version}, which predates "
            "retained Replay inputs. Its original CSV may still be required."
        )
    if not manifest.input_artifacts:
        return (
            f"{prefix}Run {manifest.run_id} has no executed CSV Replay input to display. "
            "This is expected for Simulator-only runs or Replay presets that never "
            "started."
        )
    references = len(manifest.input_artifacts)
    stored_files = len({artifact.artifact for artifact in manifest.input_artifacts})
    return (
        f"{prefix}Run {manifest.run_id}: {references} preset reference"
        f"{'s' if references != 1 else ''}, {stored_files} stored file"
        f"{'s' if stored_files != 1 else ''}. The manifest records path, bytes, and "
        "SHA-256; loading or comparing the saved manifest rechecks them. Evidence "
        "remains CSV_REPLAY, not BENCH validation."
    )


def _setup_capture_text(draft: DashboardWizardDraft) -> str:
    source = _source_display_name(draft.source_mode)
    job = _job_display_name(draft.job_type)
    if draft.source_mode is ProductSourceMode.SERIAL_READ_ONLY:
        return (
            f"Current Setup: {source} / {job}. Serial configuration cannot be "
            "stored in a project; choose Simulator or CSV Replay first. No port "
            "is discovered or opened here."
        )
    evidence = (
        "SYNTHETIC"
        if draft.source_mode is ProductSourceMode.SIMULATOR
        else "CSV_REPLAY"
    )
    return (
        f"Current Setup to capture: {source} / {job}. Adding stores configuration "
        f"only and does not run a test; later evidence remains {evidence}."
    )


def _project_next_action_text(
    workspace: ProjectWorkspace,
    selected: tuple[str, ...],
    destination: str,
    run_id: str,
) -> str:
    if workspace.project is None:
        return (
            "Getting started: Create starter… writes a new project with six "
            "Simulator presets, or Open project… loads an existing local file."
        )
    if workspace.busy:
        return (
            "Batch active: follow the phase and completed count below. Cancel "
            "requests worker cleanup before the manifest is published."
        )
    if workspace.dirty:
        return (
            "UNSAVED PROJECT: Save project as… to a new file before Review, "
            "running, or switching projects."
        )
    if workspace.reviewed_batch is not None:
        if workspace.reviewed_batch_matches(selected, destination, run_id):
            return (
                f"Ready to run: {len(selected)} presets were reviewed for "
                f"{run_id}. Run reviewed batch is now available."
            )
        return (
            "Inputs changed since Review. Review selected batch again to freeze "
            "the visible preset order, run ID, and new output directory."
        )
    if not selected:
        return "Next: Select one or more presets from the current project."
    if not run_id.strip():
        return "Next: Enter a run ID, then choose a new output directory."
    if not destination.strip():
        return "Next: Choose a new output directory, then Review selected batch."
    return (
        f"Next: Review selected batch to freeze {len(selected)} presets, run ID "
        "and destination before Run becomes available."
    )


def _batch_review_text(summary: ProjectBatchReviewSummary | None) -> str:
    if summary is None:
        return (
            "Review summary: choose the batch inputs above, then Review selected "
            "batch. No preset is authorized to run yet."
        )
    evidence = ", ".join(dict.fromkeys(item.evidence_label for item in summary.items))
    return (
        f"FROZEN REVIEW — Project {summary.project_id} · Run {summary.run_id} · "
        f"{len(summary.items)} presets · evidence {evidence}.\n"
        f"create-new destination: {summary.destination}. It must remain absent "
        "until Run publishes the completed or partial manifest."
    )


class ProjectPage:
    def __init__(
        self,
        root: Any,
        tk: Any,
        ttk: Any,
        notebook: Any,
        workspace: ProjectWorkspace,
        choose: Callable[[str], Any],
        current_draft: Callable[[], DashboardWizardDraft],
        on_load_setup: Callable[[ProductWorkflowConfiguration], bool] | None = None,
    ) -> None:
        self.workspace = workspace
        self.choose = choose
        self.current_draft = current_draft
        self.on_load_setup = on_load_setup
        self._revision = -1
        self._control_state: tuple[bool, bool, bool] | None = None
        self._project: object = None
        self._history: tuple[object, ...] = ()
        self._input_archive_state: object = None
        self._comparison: object = None
        self._batch_review: object = None
        tab = ttk.Frame(notebook, style="App.TFrame")
        notebook.add(tab, text="Projects & history")
        self.tab = tab
        page, canvas = _create_scrollable_page(
            tab,
            tk,
            ttk,
            high_contrast=bool(getattr(root, "_avs_high_contrast", False)),
        )
        _bind_mouse_wheel(root, (canvas,))
        page.columnconfigure(0, weight=1)
        self.controls: list[Any] = []

        def variable(value: str = "") -> Any:
            return tk.StringVar(master=root, value=value)

        self.project_id = variable("validation-project")
        self.project_name = variable("Analog validation project")
        self.preset_id = variable("custom-preset")
        self.preset_name = variable("Custom test")
        self.destination = variable()
        self.run_id = variable("run-001")
        self.status = variable()
        self.project_guide = variable()
        self.setup_capture_guide = variable()
        self.batch_review_guide = variable(_batch_review_text(None))
        self.comparison_guide = variable(_history_empty_text(0))
        self.input_archive_guide = variable(_history_input_archive_text(None, 0))

        def card(title: str, row: int) -> Any:
            frame = ttk.LabelFrame(
                page, text=title, padding=12, style="Card.TLabelframe"
            )
            frame.grid(row=row, column=0, sticky="ew", padx=18, pady=8)
            frame.columnconfigure(1, weight=1)
            return frame

        def entry(frame: Any, label: str, value: Any, row: int) -> None:
            ttk.Label(frame, text=label, style="Body.TLabel").grid(
                row=row, column=0, sticky="w", padx=4
            )
            widget = ttk.Entry(frame, textvariable=value, takefocus=True)
            widget.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
            self.controls.append(widget)

        def button(
            frame: Any,
            label: str,
            action: Callable[[], Any],
            row: int,
            column: int,
            style: str = "Secondary.TButton",
        ) -> Any:
            widget = ttk.Button(
                frame,
                text=label,
                command=lambda: self.act(action),
                takefocus=True,
                style=style,
            )
            widget.grid(row=row, column=column, sticky="w", padx=4, pady=4)
            self.controls.append(widget)
            return widget

        def table(frame: Any, columns: tuple[str, ...], row: int, height: int) -> Any:
            host = ttk.Frame(frame, style="Card.TFrame")
            host.grid(row=row, column=0, columnspan=3, sticky="nsew", pady=6)
            host.columnconfigure(0, weight=1)
            tree = ttk.Treeview(
                host,
                columns=columns,
                show="headings",
                height=height,
                selectmode="extended",
                takefocus=True,
                style="Modern.Treeview",
            )
            initial_width = max(100, min(160, 990 // len(columns)))
            for column in columns:
                tree.heading(column, text=column)
                tree.column(
                    column,
                    width=initial_width,
                    minwidth=90,
                    stretch=True,
                )
            tree.grid(row=0, column=0, sticky="nsew")
            vertical = ttk.Scrollbar(host, orient="vertical", command=tree.yview)
            horizontal = ttk.Scrollbar(host, orient="horizontal", command=tree.xview)
            vertical.grid(row=0, column=1, sticky="ns")
            horizontal.grid(row=1, column=0, sticky="ew")
            tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
            _bind_table_selection(tree)
            return tree

        intro = ttk.Frame(page, padding=(18, 14), style="Card.TFrame")
        intro.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 4))
        ttk.Label(
            intro,
            text="PROJECT WORKSPACE",
            style="Step.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            intro,
            text=(
                "Build reusable Simulator presets, review each batch, and compare "
                "saved evidence without changing its original classification."
            ),
            wraplength=1050,
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Label(
            intro,
            textvariable=self.project_guide,
            wraplength=1050,
            justify="left",
            style="Status.TLabel",
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))

        project = card("1. Project — reusable offline test setups", 1)
        entry(project, "Project ID", self.project_id, 0)
        entry(project, "Project name", self.project_name, 1)
        button(project, "Create starter…", self.create, 2, 0, "Primary.TButton")
        button(project, "Open project…", self.open, 2, 1)
        self.save_button = button(project, "Save project as…", self.save, 2, 2)
        ttk.Label(
            project,
            text="Create supplies six Simulator presets. Save as writes a new project file.",
            style="Muted.TLabel",
        ).grid(row=3, column=0, columnspan=3, sticky="w")

        presets = card("2. Presets — Ctrl / Shift selects multiple rows", 2)
        self.presets = table(presets, ("Preset", "Name", "Source", "Test"), 0, 6)
        button(
            presets,
            "Select all",
            lambda: self.presets.selection_set(self.presets.get_children()),
            1,
            0,
        )
        self.load_setup_button = button(
            presets, "Load selected into Setup", self.load_setup, 1, 1
        )
        entry(presets, "New preset ID", self.preset_id, 2)
        entry(presets, "New preset name", self.preset_name, 3)
        self.add_preset_button = button(
            presets,
            "Add current Setup as preset",
            self.add_preset,
            4,
            1,
            "Primary.TButton",
        )
        ttk.Label(
            presets,
            textvariable=self.setup_capture_guide,
            wraplength=950,
            justify="left",
            style="Status.TLabel",
        ).grid(row=5, column=0, columnspan=3, sticky="w")

        batch = card("3. Batch — review, then run", 3)
        entry(batch, "Run ID", self.run_id, 0)
        entry(batch, "New output directory", self.destination, 1)
        button(batch, "Choose directory name…", self.choose_output, 1, 2)
        self.review_button = button(
            batch, "Review selected batch", self.review, 2, 0
        )
        self.run_button = button(
            batch, "Run reviewed batch", self.run, 2, 1, "Primary.TButton"
        )
        self.cancel_button = ttk.Button(
            batch,
            text="Cancel batch safely",
            command=lambda: self.act(self.request_cancel),
            takefocus=True,
            style="Danger.TButton",
        )
        self.cancel_button.grid(row=2, column=2, sticky="ew", padx=4, pady=4)
        self.progress = ttk.Progressbar(
            batch,
            mode="determinate",
            style="Accent.Horizontal.TProgressbar",
        )
        self.progress.grid(row=3, column=0, columnspan=3, sticky="ew", pady=5)
        ttk.Label(
            batch,
            textvariable=self.status,
            wraplength=950,
            justify="left",
            style="Status.TLabel",
        ).grid(row=4, column=0, columnspan=3, sticky="w")
        ttk.Label(
            batch,
            textvariable=self.batch_review_guide,
            wraplength=950,
            justify="left",
            style="Status.TLabel",
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self.batch_review = table(
            batch,
            ("Order", "Preset", "Name", "Source", "Test", "Evidence"),
            6,
            5,
        )

        history = card("4. History — one row shows inputs; two rows compare", 4)
        button(history, "Load run manifests…", self.load_history, 0, 0)
        self.compare_button = button(
            history,
            "Compare selected runs",
            self.compare,
            0,
            1,
            "Primary.TButton",
        )
        self.clear_history_button = button(
            history, "Clear view", workspace.clear_history, 0, 2
        )
        self.history = table(
            history,
            (
                "Project",
                "Run",
                "Batch status",
                "Planned",
                "Completed",
                "Not started",
                "Engineering failures",
                "Operational failures",
            ),
            1,
            6,
        )
        ttk.Label(
            history,
            textvariable=self.input_archive_guide,
            wraplength=950,
            justify="left",
            style="Status.TLabel",
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(2, 4))
        self.input_artifacts = table(
            history,
            ("Preset", "Archived path", "Bytes", "SHA-256"),
            3,
            4,
        )
        ttk.Label(
            history,
            textvariable=self.comparison_guide,
            wraplength=950,
            justify="left",
            style="Status.TLabel",
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(2, 6))
        self.comparison = table(
            history,
            ("Preset / metric", "Baseline", "Candidate", "Delta / change", "Unit"),
            5,
            8,
        )
        ttk.Label(
            history,
            text="Select rows with Ctrl+click, Shift+Up/Down, or Ctrl+A. Comparison order follows the history rows (first = baseline). Results retain their original evidence; software PASS does not validate hardware.",
            wraplength=950,
            style="Muted.TLabel",
        ).grid(row=6, column=0, columnspan=3, sticky="w")
        self.render()

    def act(self, action: Callable[[], Any]) -> None:
        try:
            action()
        except Exception as error:  # noqa: BLE001 - preserve the window and display action failures
            self.workspace._changed(f"Could not complete action: {error}")
        self.render()

    def create(self) -> None:
        path = self.choose("project-save")
        if path:
            self.workspace.create(path, self.project_id.get(), self.project_name.get())

    def open(self) -> None:
        path = self.choose("project-open")
        if path:
            self.workspace.open(path)

    def save(self) -> None:
        path = self.choose("project-save")
        if path:
            self.workspace.save_copy(path)

    def add_preset(self) -> None:
        self.workspace.add_preset(
            self.preset_id.get(),
            self.preset_name.get(),
            self.current_draft().to_product_configuration(),
        )

    def load_setup(self) -> None:
        selected = self.selection(self.presets)
        if len(selected) != 1:
            raise ProductRequestError("Select exactly one preset to load into Setup.")
        if self.on_load_setup is None:
            raise ProductRequestError("Loading presets into Setup is unavailable.")
        configuration = self.workspace.configuration_for_setup(selected[0])
        if self.on_load_setup(configuration):
            self.workspace._changed(
                f"Loaded {selected[0]} into Setup for editing. The saved preset is "
                "unchanged; Review is required before running."
            )

    def choose_output(self) -> None:
        path = self.choose("run-directory")
        if path:
            self.destination.set(path)

    def selection(self, table: Any) -> tuple[str, ...]:
        selected = set(table.selection())
        return tuple(str(key) for key in table.get_children() if key in selected)

    def review(self) -> None:
        self.workspace.review(
            self.selection(self.presets), self.destination.get(), self.run_id.get()
        )

    def run(self) -> None:
        self.workspace.run(
            self.selection(self.presets), self.destination.get(), self.run_id.get()
        )

    def request_cancel(self) -> None:
        self.workspace.request_cancel()

    def load_history(self) -> None:
        paths = self.choose("history")
        if paths:
            self.workspace.load_history(tuple(paths))

    def compare(self) -> None:
        self.workspace.compare(self.selection(self.history))

    @staticmethod
    def clear(table: Any) -> None:
        for row in table.get_children():
            table.delete(row)

    def _render_input_archive(self, selected_history: tuple[str, ...]) -> None:
        manifest = None
        if len(selected_history) == 1:
            manifest = next(
                (
                    value
                    for path, value in self.workspace.history.items()
                    if str(path) == selected_history[0]
                ),
                None,
            )
        state = (selected_history, manifest)
        if state == self._input_archive_state:
            return
        self._input_archive_state = state
        self.input_archive_guide.set(
            _history_input_archive_text(manifest, len(selected_history))
        )
        self.clear(self.input_artifacts)
        if manifest is not None:
            for artifact in manifest.input_artifacts:
                self.input_artifacts.insert(
                    "",
                    "end",
                    values=(
                        artifact.preset_id,
                        artifact.artifact,
                        artifact.size_bytes,
                        artifact.sha256,
                    ),
                )

    def _update_contextual_state(
        self, *, project_busy: bool, other_busy: bool
    ) -> None:
        workspace = self.workspace
        selected_presets = self.selection(self.presets)
        destination = str(self.destination.get())
        run_id = str(self.run_id.get())
        try:
            draft = self.current_draft()
        except ProductRequestError:
            draft = None
        self.project_guide.set(
            _project_next_action_text(
                workspace, selected_presets, destination, run_id
            )
        )
        self.setup_capture_guide.set(
            _setup_capture_text(draft)
            if draft is not None
            else (
                "Current Setup preview is not ready. Complete or correct Setup & "
                "run before adding a preset; no test is started here."
            )
        )
        if workspace.comparison_guidance is None:
            self.comparison_guide.set(_history_empty_text(len(workspace.history)))

        blocked = project_busy or other_busy

        def state(allowed: bool) -> str:
            return "normal" if allowed and not blocked else "disabled"

        project_ready = workspace.project is not None
        self.load_setup_button.configure(
            state=state(
                project_ready
                and len(selected_presets) == 1
                and self.on_load_setup is not None
            )
        )
        self.save_button.configure(state=state(project_ready))
        self.add_preset_button.configure(
            state=state(
                project_ready
                and draft is not None
                and draft.source_mode is not ProductSourceMode.SERIAL_READ_ONLY
            )
        )
        self.review_button.configure(
            state=state(
                project_ready
                and not workspace.dirty
                and bool(selected_presets)
                and bool(destination.strip())
                and bool(run_id.strip())
            )
        )
        self.run_button.configure(
            state=state(
                workspace.reviewed_batch_matches(
                    selected_presets, destination, run_id
                )
            )
        )
        selected_history = self.selection(self.history)
        self._render_input_archive(selected_history)
        self.compare_button.configure(
            state=state(
                len(selected_history) == 2
                and selected_history[0] != selected_history[1]
            )
        )
        self.clear_history_button.configure(state=state(bool(workspace.history)))

    def render(self) -> None:
        workspace = self.workspace
        project_busy = workspace.busy
        other_busy = workspace.other_busy()
        control_state = (
            project_busy,
            other_busy,
            workspace.cancellation_requested,
        )
        if control_state != self._control_state:
            for control in self.controls:
                control.configure(
                    state="disabled" if project_busy or other_busy else "normal"
                )
            self.cancel_button.configure(
                state=(
                    "normal"
                    if project_busy and not workspace.cancellation_requested
                    else "disabled"
                )
            )
            self._control_state = control_state
        self._update_contextual_state(
            project_busy=project_busy, other_busy=other_busy
        )
        if workspace.revision == self._revision:
            return
        self._revision = workspace.revision
        self.status.set(workspace.status)
        progress = workspace.progress
        self.progress.configure(
            maximum=(
                progress.total_presets
                if progress is not None
                else max(1, workspace.planned_presets)
            ),
            value=0 if progress is None else progress.completed_presets,
        )
        if workspace.project is not self._project:
            self._project = workspace.project
            self.clear(self.presets)
            if workspace.project is not None:
                self.project_id.set(workspace.project.project_id)
                self.project_name.set(workspace.project.name)
                for preset in workspace.project.presets:
                    self.presets.insert(
                        "",
                        "end",
                        iid=preset.preset_id,
                        values=(
                            preset.preset_id,
                            preset.name,
                            _source_display_name(preset.configuration.source_mode),
                            _job_display_name(preset.configuration.job_type),
                        ),
                    )
                self.presets.selection_set(self.presets.get_children())
        batch_review = workspace.reviewed_batch_summary
        if batch_review != self._batch_review:
            self._batch_review = batch_review
            self.clear(self.batch_review)
            if batch_review is not None:
                total = len(batch_review.items)
                for item in batch_review.items:
                    self.batch_review.insert(
                        "",
                        "end",
                        values=(
                            f"{item.sequence}/{total}",
                            item.preset_id,
                            item.name,
                            _source_display_name(item.source_mode),
                            _job_display_name(item.job_type),
                            item.evidence_label,
                        ),
                    )
        self.batch_review_guide.set(_batch_review_text(batch_review))
        history = tuple(workspace.history.items())
        if history != self._history:
            self._history = history
            self.clear(self.history)
            for path, manifest in history:
                self.history.insert(
                    "",
                    "end",
                    iid=str(path),
                    values=(
                        manifest.project_id,
                        manifest.run_id,
                        manifest.batch_status.value
                        if manifest.batch_status is not None
                        else "LEGACY_V1",
                        len(manifest.planned_preset_ids),
                        len(manifest.records),
                        len(manifest.not_started_preset_ids),
                        manifest.engineering_failures,
                        manifest.operational_failures,
                    ),
                )
            self._render_input_archive(self.selection(self.history))
        if workspace.comparison is not self._comparison:
            self._comparison = workspace.comparison
            self.clear(self.comparison)
            if workspace.comparison is not None:
                for entry in workspace.comparison.entries:
                    self.comparison.insert(
                        "",
                        "end",
                        values=(
                            entry.preset_id,
                            _record_text(entry.left),
                            _record_text(entry.right),
                            "CHANGED" if entry.changed else "UNCHANGED",
                            "",
                        ),
                    )
                    for metric in entry.metric_deltas:
                        self.comparison.insert(
                            "",
                            "end",
                            values=(
                                f"  {metric.name}",
                                metric.left_value,
                                metric.right_value,
                                metric.delta,
                                metric.unit,
                            ),
                        )
                    self.comparison.insert(
                        "",
                        "end",
                        values=(
                            "  Configuration SHA-256",
                            entry.left.configuration_sha256 if entry.left else "absent",
                            entry.right.configuration_sha256
                            if entry.right
                            else "absent",
                            "",
                            "",
                        ),
                    )
        guidance = workspace.comparison_guidance
        self.comparison_guide.set(
            _comparison_guidance_text(guidance)
            if guidance is not None
            else _history_empty_text(len(history))
        )
        self._update_contextual_state(
            project_busy=project_busy, other_busy=other_busy
        )
