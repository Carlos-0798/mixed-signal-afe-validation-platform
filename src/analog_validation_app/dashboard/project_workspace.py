"""Local project-page operations, independent of the GUI toolkit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from queue import Empty, Queue
from threading import Thread

from ..errors import ProductRequestError
from ..models import ProductJobType, ProductSourceMode
from ..product_workflows import ProductWorkflowConfiguration
from ..projects import (
    MAX_VALIDATION_HISTORY_INPUTS,
    ValidationBatchCancellationToken,
    ValidationBatchProgress,
    ValidationPreset,
    ValidationProject,
    ValidationRunComparison,
    ValidationRunManifest,
    build_default_validation_project,
    compare_validation_runs,
    load_validation_project,
    load_validation_run_manifest,
    publish_validation_project_run,
    write_validation_project,
)


@dataclass(frozen=True, slots=True)
class ProjectComparisonGuidance:
    """Read-only facts that help a user interpret one verified comparison."""

    project_id: str
    baseline_run_id: str
    candidate_run_id: str
    baseline_batch_status: str
    candidate_batch_status: str
    same_project_snapshot: bool
    changed_preset_ids: tuple[str, ...]
    matched_result_ids: tuple[str, ...]
    baseline_only_result_ids: tuple[str, ...]
    candidate_only_result_ids: tuple[str, ...]
    baseline_not_started_ids: tuple[str, ...]
    candidate_not_started_ids: tuple[str, ...]
    evidence_label_match_ids: tuple[str, ...]
    evidence_label_mismatch_ids: tuple[str, ...]
    evidence_unavailable_ids: tuple[str, ...]
    baseline_evidence_labels: tuple[str, ...]
    candidate_evidence_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProjectBatchReviewItem:
    """One preset copied from the immutable reviewed batch order."""

    sequence: int
    preset_id: str
    name: str
    source_mode: ProductSourceMode
    job_type: ProductJobType
    evidence_label: str


@dataclass(frozen=True, slots=True)
class ProjectBatchReviewSummary:
    """Presentation-only description of the exact batch authorized by Review."""

    project_id: str
    run_id: str
    destination: Path
    items: tuple[ProjectBatchReviewItem, ...]


_PROJECT_EVIDENCE_LABELS = {
    ProductSourceMode.SIMULATOR: "SYNTHETIC",
    ProductSourceMode.CSV_REPLAY: "CSV_REPLAY",
}


def _preparation_failure_summary(manifest: ValidationRunManifest) -> str:
    failure = manifest.preparation_failure
    if failure is None:
        return ""
    return (
        f"Preparation failed for preset {failure.preset_id} "
        f"({failure.issue_code.value}): {failure.message} "
        "No worker or result was created for this preset; earlier results are retained."
    )


def _batch_status(manifest: ValidationRunManifest) -> str:
    return (
        manifest.batch_status.value
        if manifest.batch_status is not None
        else "LEGACY_V1"
    )


def _evidence_labels(manifest: ValidationRunManifest) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            record.evidence_source.value
            for record in manifest.records
            if record.evidence_source is not None
        )
    )


def _build_comparison_guidance(
    baseline: ValidationRunManifest,
    candidate: ValidationRunManifest,
    comparison: ValidationRunComparison,
) -> ProjectComparisonGuidance:
    """Derive presentation facts without recalculating any result or metric."""

    matched = tuple(
        entry.preset_id
        for entry in comparison.entries
        if entry.left is not None and entry.right is not None
    )
    baseline_only = tuple(
        entry.preset_id
        for entry in comparison.entries
        if entry.left is not None and entry.right is None
    )
    candidate_only = tuple(
        entry.preset_id
        for entry in comparison.entries
        if entry.left is None and entry.right is not None
    )
    evidence_matches = tuple(
        entry.preset_id
        for entry in comparison.entries
        if entry.left is not None
        and entry.right is not None
        and entry.left.evidence_source is not None
        and entry.left.evidence_source is entry.right.evidence_source
    )
    evidence_mismatches = tuple(
        entry.preset_id
        for entry in comparison.entries
        if entry.left is not None
        and entry.right is not None
        and entry.left.evidence_source is not None
        and entry.right.evidence_source is not None
        and entry.left.evidence_source is not entry.right.evidence_source
    )
    evidence_unavailable = tuple(
        entry.preset_id
        for entry in comparison.entries
        if entry.left is not None
        and entry.right is not None
        and (
            entry.left.evidence_source is None
            or entry.right.evidence_source is None
        )
    )
    return ProjectComparisonGuidance(
        project_id=comparison.project_id,
        baseline_run_id=comparison.left_run_id,
        candidate_run_id=comparison.right_run_id,
        baseline_batch_status=_batch_status(baseline),
        candidate_batch_status=_batch_status(candidate),
        same_project_snapshot=not comparison.project_changed,
        changed_preset_ids=tuple(
            entry.preset_id for entry in comparison.entries if entry.changed
        ),
        matched_result_ids=matched,
        baseline_only_result_ids=baseline_only,
        candidate_only_result_ids=candidate_only,
        baseline_not_started_ids=baseline.not_started_preset_ids,
        candidate_not_started_ids=candidate.not_started_preset_ids,
        evidence_label_match_ids=evidence_matches,
        evidence_label_mismatch_ids=evidence_mismatches,
        evidence_unavailable_ids=evidence_unavailable,
        baseline_evidence_labels=_evidence_labels(baseline),
        candidate_evidence_labels=_evidence_labels(candidate),
    )


class ProjectWorkspace:
    """UI-thread state; background work communicates only through queues."""

    def __init__(self, other_busy: Callable[[], bool]) -> None:
        self.other_busy = other_busy
        self.project: ValidationProject | None = None
        self.path: Path | None = None
        self.dirty = False
        self.history: dict[Path, ValidationRunManifest] = {}
        self.comparison: ValidationRunComparison | None = None
        self.comparison_guidance: ProjectComparisonGuidance | None = None
        self.status = "Create a starter project or open a saved project."
        self.revision = 0
        self.progress: ValidationBatchProgress | None = None
        self.planned_presets = 0
        self._review: tuple[ValidationProject, tuple[str, ...], Path, str] | None = None
        self._thread: Thread | None = None
        self._cancellation: ValidationBatchCancellationToken | None = None
        self._mailbox: Queue[tuple[Path, ValidationRunManifest | Exception]] = Queue(1)
        self._progress_mailbox: Queue[ValidationBatchProgress] = Queue()

    @property
    def busy(self) -> bool:
        return self._thread is not None

    @property
    def cancellation_requested(self) -> bool:
        return (
            self._cancellation is not None
            and self._cancellation.is_cancellation_requested
        )

    @property
    def reviewed_batch(self) -> tuple[tuple[str, ...], Path, str] | None:
        if self._review is None:
            return None
        _, selected, destination, run_id = self._review
        return selected, destination, run_id

    @property
    def reviewed_batch_summary(self) -> ProjectBatchReviewSummary | None:
        if self._review is None:
            return None
        project, selected, destination, run_id = self._review
        presets = {preset.preset_id: preset for preset in project.presets}
        items = tuple(
            ProjectBatchReviewItem(
                sequence=index,
                preset_id=preset_id,
                name=presets[preset_id].name,
                source_mode=presets[preset_id].configuration.source_mode,
                job_type=presets[preset_id].configuration.job_type,
                evidence_label=_PROJECT_EVIDENCE_LABELS[
                    presets[preset_id].configuration.source_mode
                ],
            )
            for index, preset_id in enumerate(selected, start=1)
        )
        return ProjectBatchReviewSummary(
            project_id=project.project_id,
            run_id=run_id,
            destination=destination,
            items=items,
        )

    def reviewed_batch_matches(
        self, selected: tuple[str, ...], output: str, run_id: str
    ) -> bool:
        """Return whether the visible inputs still match the reviewed batch."""

        if self._review is None:
            return False
        try:
            destination = Path(output).resolve()
        except (OSError, ValueError):
            return False
        return self._review == (self.project, selected, destination, run_id)

    def _idle(self) -> None:
        if self.busy or self.other_busy():
            raise ProductRequestError("Wait for the active test to finish first.")

    def _changed(self, status: str) -> None:
        self.status = status
        self.revision += 1

    def _adopt(self, project: ValidationProject, path: Path) -> None:
        self.project, self.path = project, path.resolve()
        self.dirty = False
        self._review = None
        self._changed(
            f"Project: {project.name} | {len(project.presets)} presets | {self.path}"
        )

    def create(self, path: str, project_id: str, name: str) -> None:
        self._idle()
        self._check_discard()
        project = build_default_validation_project(project_id, name)
        self._adopt(project, write_validation_project(path, project))

    def open(self, path: str) -> None:
        self._idle()
        self._check_discard()
        self._adopt(load_validation_project(path), Path(path))

    def _check_discard(self) -> None:
        if self.dirty:
            raise ProductRequestError(
                "Save the modified project as a new file before switching projects."
            )

    def save_copy(self, path: str) -> None:
        self._idle()
        if self.project is None:
            raise ProductRequestError("Open or create a project first.")
        self._adopt(self.project, write_validation_project(path, self.project))

    def add_preset(
        self, preset_id: str, name: str, configuration: ProductWorkflowConfiguration
    ) -> None:
        self._idle()
        if self.project is None:
            raise ProductRequestError("Open or create a project first.")
        if configuration.replay_path is not None:
            configuration = replace(
                configuration, replay_path=configuration.replay_path.resolve()
            )
        preset = ValidationPreset(preset_id, name, configuration)
        self.project = replace(self.project, presets=(*self.project.presets, preset))
        self.dirty = True
        self._review = None
        self._changed(
            "Preset added. Save project as a new file before running or switching projects."
        )

    def configuration_for_setup(self, preset_id: str) -> ProductWorkflowConfiguration:
        """Copy a preset for editing; resolve Replay relative to the project file."""

        self._idle()
        if self.project is None or self.path is None:
            raise ProductRequestError("Open or create a project first.")
        preset = next(
            (item for item in self.project.presets if item.preset_id == preset_id),
            None,
        )
        if preset is None:
            raise ProductRequestError("Select an existing preset to load into Setup.")
        configuration = preset.configuration
        if configuration.replay_path is not None:
            path = configuration.replay_path
            if not path.is_absolute():
                path = self.path.parent / path
            configuration = replace(configuration, replay_path=path.resolve())
        return configuration

    def review(self, selected: tuple[str, ...], output: str, run_id: str) -> None:
        self._idle()
        self._review = None
        if self.project is None or self.path is None:
            raise ProductRequestError("Open or create a project first.")
        if self.dirty:
            raise ProductRequestError("Save the modified project before running it.")
        if not selected or len(set(selected)) != len(selected):
            raise ProductRequestError("Select one or more distinct presets.")
        presets = {item.preset_id: item for item in self.project.presets}
        if any(item not in presets for item in selected):
            raise ProductRequestError("Selected preset is not in the current project.")
        # Reuse the public identifier contract without opening any resources.
        ValidationPreset(run_id, "Run identifier", presets[selected[0]].configuration)
        if any(
            (run.project_id, run.run_id) == (self.project.project_id, run_id)
            for run in self.history.values()
        ):
            raise ProductRequestError(
                "Use a new run ID; this project/run is already in history."
            )
        if not output.strip():
            raise ProductRequestError("Choose a new run directory.")
        destination = Path(output).resolve()
        if destination.exists() or not destination.parent.is_dir():
            raise ProductRequestError(
                "Run directory must be new and its parent must exist."
            )
        if len(self.history) >= MAX_VALIDATION_HISTORY_INPUTS:
            raise ProductRequestError(
                "Clear the history view before adding another run."
            )
        self._review = self.project, selected, destination, run_id
        self._changed(
            f"Reviewed {len(selected)} presets in order: {', '.join(selected)}\n"
            f"Destination: {destination}\nOffline batch; results retain their evidence labels. "
            "Each preset runs sequentially; closing waits for this finite batch."
        )

    def run(self, selected: tuple[str, ...], output: str, run_id: str) -> None:
        self._idle()
        if not self.reviewed_batch_matches(selected, output, run_id):
            raise ProductRequestError(
                "Setup changed or has not been reviewed. Review the batch first."
            )
        assert self._review is not None
        project, selected, destination, run_id = self._review
        assert self.path is not None
        base = self.path.parent
        self._review = None
        self.progress = None
        self.planned_presets = len(selected)
        cancellation = ValidationBatchCancellationToken()
        self._cancellation = cancellation
        while True:
            try:
                self._progress_mailbox.get_nowait()
            except Empty:
                break

        def execute() -> None:
            try:
                value: ValidationRunManifest | Exception = (
                    publish_validation_project_run(
                        project,
                        destination,
                        run_id,
                        selected_preset_ids=selected,
                        project_directory=base,
                        cancellation=cancellation,
                        report_progress=self._progress_mailbox.put,
                    )
                )
            except Exception as error:  # noqa: BLE001 - deliver worker failures to the UI
                value = error
            self._mailbox.put((destination / "run-manifest.json", value))

        self._thread = Thread(target=execute, name="avs-project-batch", daemon=False)
        try:
            self._thread.start()
        except Exception:
            self._thread = None
            self._cancellation = None
            raise
        self._changed(
            f"Batch {run_id}: starting {len(selected)} reviewed presets; completed 0/{len(selected)}."
        )

    def request_cancel(self) -> bool:
        if not self.busy or self._cancellation is None:
            raise ProductRequestError("No project batch is active to cancel.")
        requested = self._cancellation.request_cancel()
        if requested:
            current = "the current preset"
            if self.progress is not None and self.progress.current_preset_id is not None:
                current = f"preset {self.progress.current_preset_id}"
            self._changed(
                f"Cancellation requested for {current}. Waiting for worker cleanup and manifest publication."
            )
        return requested

    def _drain_progress(self) -> None:
        latest: ValidationBatchProgress | None = None
        while True:
            try:
                latest = self._progress_mailbox.get_nowait()
            except Empty:
                break
        if latest is None:
            return
        self.progress = latest
        current = "none"
        if latest.current_preset_id is not None:
            current = (
                f"{latest.current_preset_id} "
                f"({latest.current_preset_number}/{latest.total_presets})"
            )
        self._changed(
            f"Batch {latest.run_id}: phase {latest.phase.value}; current preset {current}; "
            f"completed {latest.completed_presets}/{latest.total_presets}."
        )

    def poll(self) -> None:
        self._drain_progress()
        if self._thread is None or self._thread.is_alive():
            return
        self._thread.join()
        self._thread = None
        self._cancellation = None
        try:
            path, value = self._mailbox.get_nowait()
        except Empty:
            self._changed(
                "Batch stopped without a completion record. Inspect the destination before retrying."
            )
            return
        if isinstance(value, Exception):
            self._changed(f"Batch failed: {value}")
            return
        self.history[path] = value
        batch_status = (
            value.batch_status.value if value.batch_status is not None else "LEGACY_V1"
        )
        failure_summary = _preparation_failure_summary(value)
        failure_line = f"{failure_summary}\n" if failure_summary else ""
        self._changed(
            f"Batch {batch_status}: completed {len(value.records)}/{len(value.planned_preset_ids)}; "
            f"not started: {len(value.not_started_preset_ids)}; "
            f"engineering failures: {value.engineering_failures}; "
            f"operational failures: {value.operational_failures}.\n"
            f"{failure_line}Saved: {path}"
        )

    def load_history(self, paths: tuple[str, ...]) -> None:
        self._idle()
        resolved = tuple(Path(path).resolve() for path in paths)
        if len(resolved) != len(set(resolved)):
            raise ProductRequestError("Select each manifest only once.")
        if len(set(self.history) | set(resolved)) > MAX_VALIDATION_HISTORY_INPUTS:
            raise ProductRequestError("History view supports at most 64 manifests.")
        incoming = {path: load_validation_run_manifest(path) for path in resolved}
        combined = self.history | incoming
        identities = {(run.project_id, run.run_id) for run in combined.values()}
        if len(identities) != len(combined):
            raise ProductRequestError(
                "History contains duplicate project/run identities at different paths."
            )
        self.history.update(incoming)
        self.comparison = None
        self.comparison_guidance = None
        self._changed(
            f"Verified {len(incoming)} manifests; {len(self.history)} runs in this view."
        )

    def compare(self, paths: tuple[str, ...]) -> None:
        self._idle()
        if len(paths) != 2 or paths[0] == paths[1]:
            raise ProductRequestError(
                "Select exactly two different history rows to compare."
            )
        manifests = tuple(load_validation_run_manifest(path) for path in paths)
        comparison = compare_validation_runs(*manifests)
        self.comparison = comparison
        self.comparison_guidance = _build_comparison_guidance(
            manifests[0], manifests[1], comparison
        )
        self._changed(
            f"Comparison: {comparison.left_run_id} → {comparison.right_run_id}; {comparison.changed_entries} changed presets."
        )

    def clear_history(self) -> None:
        self._idle()
        self.history.clear()
        self.comparison = None
        self.comparison_guidance = None
        self._changed("History view cleared. Saved files remain on disk.")
