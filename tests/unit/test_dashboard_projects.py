from __future__ import annotations

import shutil
import sys
from dataclasses import replace
from pathlib import Path
from threading import Event, Thread
from time import monotonic, sleep
from types import SimpleNamespace
from typing import Any

import pytest

from analog_validation import EvidenceSource
from analog_validation_app import ProductRequestError, ProductSourceMode
from analog_validation_app.dashboard import app as app_module
from analog_validation_app.dashboard import project_workspace as workspace_module
from analog_validation_app.dashboard.project_widgets import (
    ProjectPage,
    _batch_review_text,
    _bind_table_selection,
    _comparison_guidance_text,
    _history_empty_text,
    _history_input_archive_text,
    _project_next_action_text,
    _setup_capture_text,
    _short_list,
)
from analog_validation_app.dashboard.project_workspace import (
    ProjectWorkspace,
    _build_comparison_guidance,
)
from analog_validation_app.dashboard.wizard import DashboardWizardDraft
from analog_validation_app.projects import (
    VALIDATION_RUN_MANIFEST_V1_SCHEMA_VERSION,
    VALIDATION_RUN_MANIFEST_V3_SCHEMA_VERSION,
    ValidationBatchCancellationToken,
    ValidationBatchPhase,
    ValidationBatchProgress,
    ValidationBatchStatus,
    ValidationRunInputArtifact,
    compare_validation_runs,
)
from tests.unit.test_dashboard_app import FakeVariable, FakeWidget, fake_toolkit


def workspace(tmp_path: Path) -> ProjectWorkspace:
    model = ProjectWorkspace(lambda: False)
    model.create(str(tmp_path / "project.json"), "test-project", "Test project")
    return model


def finish(model: ProjectWorkspace) -> None:
    assert model._thread is not None
    model._thread.join(10)
    assert not model._thread.is_alive()
    model.poll()
    assert not model.busy


def run(
    model: ProjectWorkspace,
    path: Path,
    name: str,
    selected: tuple[str, ...] = ("dc-default",),
) -> None:
    model.review(selected, str(path), name)
    model.run(selected, str(path), name)
    finish(model)


def test_workspace_round_trip_batch_history_and_comparison(tmp_path: Path) -> None:
    model = workspace(tmp_path)
    model.open(str(tmp_path / "project.json"))
    model.poll()
    run(model, tmp_path / "run-1", "run-1")
    run(model, tmp_path / "run-2", "run-2", ("dc-default", "frequency-default"))
    paths = tuple(str(path) for path in model.history)
    model.compare(paths)
    assert model.comparison is not None
    assert model.comparison_guidance is not None
    assert model.comparison.changed_entries == 1
    assert "Batch" not in model.status
    model.clear_history()
    assert not model.history
    assert model.comparison_guidance is None
    assert all(Path(path).exists() for path in paths)
    model.load_history(paths)
    assert len(model.history) == 2
    assert model.comparison is None
    assert model.comparison_guidance is None


def test_project_first_use_guidance_follows_existing_workspace_permissions(
    tmp_path: Path,
) -> None:
    model = ProjectWorkspace(lambda: False)
    simulator = DashboardWizardDraft()

    assert "Create starter" in _project_next_action_text(model, (), "", "run-001")
    assert "SYNTHETIC" in _setup_capture_text(simulator)
    assert "does not run a test" in _setup_capture_text(simulator)
    assert "No run history" in _history_empty_text(0)
    assert "one verified run" in _history_empty_text(1)
    assert "2 verified runs" in _history_empty_text(2)

    model.create(str(tmp_path / "project.json"), "project", "Project")
    selected = ("dc-default",)
    assert "Select one or more presets" in _project_next_action_text(
        model, (), str(tmp_path / "run"), "run-001"
    )
    assert "Enter a run ID" in _project_next_action_text(
        model, selected, str(tmp_path / "run"), ""
    )
    assert "Choose a new output directory" in _project_next_action_text(
        model, selected, "", "run-001"
    )
    assert not model.reviewed_batch_matches(selected, str(tmp_path / "run"), "run-001")
    model.review(selected, str(tmp_path / "run"), "run-001")
    assert model.reviewed_batch_matches(selected, str(tmp_path / "run"), "run-001")
    assert not model.reviewed_batch_matches(selected, "\0", "run-001")
    assert "Ready to run" in _project_next_action_text(
        model, selected, str(tmp_path / "run"), "run-001"
    )
    assert "Inputs changed since Review" in _project_next_action_text(
        model, selected, str(tmp_path / "run"), "run-002"
    )
    model.run(selected, str(tmp_path / "run"), "run-001")
    assert "Batch active" in _project_next_action_text(
        model, selected, str(tmp_path / "run"), "run-001"
    )
    finish(model)

    model.add_preset("custom", "Custom", simulator.to_product_configuration())
    assert "UNSAVED PROJECT" in _project_next_action_text(
        model, selected, str(tmp_path / "run"), "run-001"
    )

    replay = replace(simulator, source_mode=ProductSourceMode.CSV_REPLAY)
    serial = replace(simulator, source_mode=ProductSourceMode.SERIAL_READ_ONLY)
    assert "CSV_REPLAY" in _setup_capture_text(replay)
    assert "cannot be stored" in _setup_capture_text(serial)


def test_history_input_archive_guidance_distinguishes_schema_and_content(
    tmp_path: Path,
) -> None:
    model = workspace(tmp_path)
    run(model, tmp_path / "simulator", "simulator")
    simulator = next(iter(model.history.values()))

    assert "Select one history row" in _history_input_archive_text(None, 0)
    assert "Keep two rows selected" in _history_input_archive_text(None, 2)
    assert "no executed CSV Replay input" in _history_input_archive_text(simulator, 1)

    legacy = replace(
        simulator,
        schema_version=VALIDATION_RUN_MANIFEST_V1_SCHEMA_VERSION,
        batch_status=None,
    )
    assert "predates retained Replay inputs" in _history_input_archive_text(legacy, 1)
    v2 = replace(simulator, schema_version="validation-run-manifest.v2")
    assert "validation-run-manifest.v2" in _history_input_archive_text(v2, 1)

    replay_record = replace(
        simulator.records[0],
        source_mode=ProductSourceMode.CSV_REPLAY,
        evidence_source=EvidenceSource.CSV_REPLAY,
    )
    replay = replace(
        simulator,
        run_id="replay",
        records=(replay_record,),
        input_artifacts=(
            ValidationRunInputArtifact(
                replay_record.preset_id,
                ProductSourceMode.CSV_REPLAY,
                "inputs/01-dc-default.csv",
                42,
                "a" * 64,
            ),
        ),
    )
    guidance = _history_input_archive_text(replay, 1)
    assert "1 preset reference" in guidance
    assert "1 stored file" in guidance
    assert "CSV_REPLAY" in guidance
    assert "not BENCH validation" in guidance
    v3 = replace(replay, schema_version=VALIDATION_RUN_MANIFEST_V3_SCHEMA_VERSION)
    assert "1 preset reference" in _history_input_archive_text(v3, 1)
    assert "predates" not in _history_input_archive_text(v3, 1)
    v3_simulator = replace(
        simulator, schema_version=VALIDATION_RUN_MANIFEST_V3_SCHEMA_VERSION
    )
    assert "no executed CSV Replay input" in _history_input_archive_text(
        v3_simulator, 1
    )


def test_review_summary_freezes_order_sources_evidence_and_destination(
    tmp_path: Path,
) -> None:
    model = workspace(tmp_path)
    selected = ("frequency-default", "dc-default")
    destination = tmp_path / "reviewed-run"

    assert model.reviewed_batch_summary is None
    assert "Review selected batch" in _batch_review_text(None)
    model.review(selected, str(destination), "reviewed-run")
    summary = model.reviewed_batch_summary
    assert summary is not None
    assert summary.project_id == "test-project"
    assert summary.run_id == "reviewed-run"
    assert summary.destination == destination.resolve()
    assert tuple(item.sequence for item in summary.items) == (1, 2)
    assert tuple(item.preset_id for item in summary.items) == selected
    assert tuple(item.evidence_label for item in summary.items) == (
        "SYNTHETIC",
        "SYNTHETIC",
    )
    text = _batch_review_text(summary)
    assert "FROZEN REVIEW" in text
    assert "create-new" in text
    assert "reviewed-run" in text
    assert str(destination.resolve()) in text

    model.run(selected, str(destination), "reviewed-run")
    assert model.reviewed_batch_summary is None
    finish(model)

    replay_path = tmp_path / "replay.csv"
    replay = replace(
        DashboardWizardDraft(),
        source_mode=ProductSourceMode.CSV_REPLAY,
        replay_path=str(replay_path),
    )
    model.add_preset("replay", "Replay", replay.to_product_configuration())
    model.save_copy(str(tmp_path / "replay-project.json"))
    model.review(("replay",), str(tmp_path / "replay-run"), "replay-run")
    replay_summary = model.reviewed_batch_summary
    assert replay_summary is not None
    assert replay_summary.items[0].evidence_label == "CSV_REPLAY"


@pytest.mark.parametrize("replay_first", (False, True))
def test_batch_preparation_failure_is_visible_without_fabricating_results(
    tmp_path: Path, replay_first: bool
) -> None:
    model = workspace(tmp_path)
    draft = replace(DashboardWizardDraft(), sample_count="1")
    if replay_first:
        path = tmp_path / "valid.csv"
        shutil.copyfile(
            Path(__file__).resolve().parents[2]
            / "test-data/golden/csv_replay_v1_valid.csv",
            path,
        )
        draft = replace(
            draft, source_mode=ProductSourceMode.CSV_REPLAY, replay_path=str(path)
        )
    model.add_preset("first", "First read", draft.to_product_configuration())
    missing = replace(
        draft,
        source_mode=ProductSourceMode.CSV_REPLAY,
        replay_path=str(tmp_path / "missing.csv"),
    )
    model.add_preset("missing", "Missing replay", missing.to_product_configuration())
    model.save_copy(str(tmp_path / "with-missing.json"))
    run(
        model,
        tmp_path / "partial-evidence",
        "partial-evidence",
        ("first", "missing", "frequency-default"),
    )
    manifest = next(iter(model.history.values()))
    assert manifest.schema_version == "validation-run-manifest.v4"
    assert manifest.batch_status is ValidationBatchStatus.ERROR
    assert tuple(record.preset_id for record in manifest.records) == ("first",)
    assert manifest.not_started_preset_ids == ("missing", "frequency-default")
    assert manifest.preparation_failure is not None
    assert manifest.preparation_failure.preset_id == "missing"
    assert "Preparation failed for preset missing" in model.status
    assert manifest.preparation_failure.message in model.status
    assert "No worker or result was created" in model.status
    assert "earlier results are retained" in model.status
    assert "operational failures: 1" in model.status

    ttk = SimpleNamespace(
        **{
            name: Widget
            for name in (
                "Frame",
                "LabelFrame",
                "Label",
                "Entry",
                "Button",
                "Treeview",
                "Scrollbar",
                "Progressbar",
            )
        }
    )
    page = ProjectPage(
        Widget(),
        SimpleNamespace(StringVar=FakeVariable),
        ttk,
        Widget(),
        model,
        lambda _: "",
        DashboardWizardDraft,
    )
    page.history.selection_set(page.history.get_children())
    page.render()
    explanation = page.input_archive_guide.get()
    assert "Preparation failed for preset missing" in explanation
    assert manifest.preparation_failure.message in explanation
    assert "No worker or result was created" in explanation
    assert len(page.input_artifacts.rows) == int(replay_first)
    assert "predates" not in explanation
    page.history.selection_set(())
    page.render()
    assert "Preparation failed" not in page.input_archive_guide.get()


def test_comparison_guidance_explains_evidence_coverage_and_delta_direction(
    tmp_path: Path,
) -> None:
    model = workspace(tmp_path)
    run(
        model,
        tmp_path / "baseline",
        "baseline",
        ("dc-default", "frequency-default"),
    )
    baseline = next(iter(model.history.values()))
    complete_candidate = replace(baseline, run_id="complete-candidate")
    complete_comparison = compare_validation_runs(baseline, complete_candidate)
    complete = _build_comparison_guidance(
        baseline, complete_candidate, complete_comparison
    )

    assert complete.same_project_snapshot
    assert complete.matched_result_ids == ("dc-default", "frequency-default")
    assert complete.baseline_only_result_ids == ()
    assert complete.candidate_only_result_ids == ()
    assert complete.evidence_label_match_ids == (
        "dc-default",
        "frequency-default",
    )
    assert complete.evidence_label_mismatch_ids == ()
    assert complete.evidence_unavailable_ids == ()

    replay_record = replace(
        baseline.records[0],
        job_id="candidate-dc-default",
        source_mode=ProductSourceMode.CSV_REPLAY,
        evidence_source=EvidenceSource.CSV_REPLAY,
        limitations=("CSV replay evidence only.",),
    )
    incomplete_candidate = replace(
        baseline,
        run_id="incomplete-candidate",
        project_sha256="e" * 64,
        records=(replay_record,),
        batch_status=ValidationBatchStatus.CANCELLED,
        not_started_preset_ids=("frequency-default",),
        input_artifacts=(
            ValidationRunInputArtifact(
                "dc-default",
                ProductSourceMode.CSV_REPLAY,
                "inputs/01-dc-default.csv",
                1,
                "a" * 64,
            ),
        ),
    )
    comparison = compare_validation_runs(baseline, incomplete_candidate)
    guidance = _build_comparison_guidance(baseline, incomplete_candidate, comparison)
    text = _comparison_guidance_text(guidance)

    assert guidance.project_id == "test-project"
    assert guidance.baseline_run_id == "baseline"
    assert guidance.candidate_run_id == "incomplete-candidate"
    assert not guidance.same_project_snapshot
    assert guidance.matched_result_ids == ("dc-default",)
    assert guidance.baseline_only_result_ids == ("frequency-default",)
    assert guidance.candidate_only_result_ids == ()
    assert guidance.candidate_not_started_ids == ("frequency-default",)
    assert guidance.evidence_label_mismatch_ids == ("dc-default",)
    assert guidance.baseline_evidence_labels == ("SYNTHETIC",)
    assert guidance.candidate_evidence_labels == ("CSV_REPLAY",)
    assert guidance.changed_preset_ids == (
        "dc-default",
        "frequency-default",
    )
    assert "SYNTHETIC" in text
    assert "CSV_REPLAY" in text
    assert "candidate - baseline" in text
    assert "does not by itself mean improvement or regression" in text
    assert "Do not treat mismatched evidence as like-for-like" in text

    unavailable_record = replace(
        baseline.records[0],
        job_id="candidate-no-evidence",
        evidence_source=None,
    )
    unavailable_candidate = replace(
        baseline,
        run_id="candidate-no-evidence",
        records=(unavailable_record, baseline.records[1]),
    )
    unavailable_comparison = compare_validation_runs(baseline, unavailable_candidate)
    unavailable = _build_comparison_guidance(
        baseline, unavailable_candidate, unavailable_comparison
    )
    assert unavailable.evidence_unavailable_ids == ("dc-default",)
    assert "Evidence is unavailable" in _comparison_guidance_text(unavailable)

    legacy_baseline = replace(
        baseline,
        schema_version=VALIDATION_RUN_MANIFEST_V1_SCHEMA_VERSION,
        batch_status=None,
    )
    legacy = _build_comparison_guidance(
        legacy_baseline,
        complete_candidate,
        compare_validation_runs(legacy_baseline, complete_candidate),
    )
    assert legacy.baseline_batch_status == "LEGACY_V1"
    assert _short_list(("a", "b", "c", "d", "e")) == "a, b, c, d, and 1 more"


def test_preset_edit_requires_save_and_preserves_original(tmp_path: Path) -> None:
    model = workspace(tmp_path)
    original = (tmp_path / "project.json").read_bytes()
    model.add_preset(
        "custom", "Custom", DashboardWizardDraft().to_product_configuration()
    )
    assert model.dirty
    for action in (
        lambda: model.open(str(tmp_path / "project.json")),
        lambda: model.create(str(tmp_path / "new.json"), "new", "New"),
        lambda: model.review(("custom",), str(tmp_path / "run"), "run"),
    ):
        with pytest.raises(ProductRequestError, match="Save"):
            action()
    model.save_copy(str(tmp_path / "copy.json"))
    assert not model.dirty
    assert original == (tmp_path / "project.json").read_bytes()
    model.open(str(tmp_path / "copy.json"))
    assert model.project is not None and len(model.project.presets) == 7
    run(model, tmp_path / "custom-run", "custom-run", ("custom",))


def test_workspace_rejects_missing_project_and_stale_review(tmp_path: Path) -> None:
    model = ProjectWorkspace(lambda: False)
    for action in (
        lambda: model.save_copy(str(tmp_path / "none.json")),
        lambda: model.add_preset(
            "custom", "Custom", DashboardWizardDraft().to_product_configuration()
        ),
        lambda: model.review(("dc-default",), str(tmp_path / "run"), "run"),
    ):
        with pytest.raises(ProductRequestError, match="project first"):
            action()
    model = workspace(tmp_path)
    for selected, output in (
        ((), "x"),
        (("dc-default", "dc-default"), "x"),
        (("missing",), "x"),
        (("dc-default",), ""),
        (("dc-default",), str(tmp_path)),
        (("dc-default",), str(tmp_path / "absent" / "run")),
    ):
        with pytest.raises(ProductRequestError):
            model.review(selected, output, "run")
    model.review(("dc-default",), str(tmp_path / "run"), "run")
    with pytest.raises(ProductRequestError, match="Setup changed"):
        model.run(("read-default",), str(tmp_path / "run"), "run")
    with pytest.raises(ProductRequestError):
        model.review(("missing",), str(tmp_path / "run"), "run")
    with pytest.raises(ProductRequestError, match="reviewed"):
        model.run(("dc-default",), str(tmp_path / "run"), "run")
    model.other_busy = lambda: True
    with pytest.raises(ProductRequestError, match="active test"):
        model.clear_history()


def test_batch_is_background_exclusive_and_failure_is_delivered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = workspace(tmp_path)
    entered, release = Event(), Event()

    def blocked(*args: Any, **kwargs: Any) -> Any:
        entered.set()
        assert release.wait(5)
        raise OSError("injected disk failure")

    monkeypatch.setattr(workspace_module, "publish_validation_project_run", blocked)
    model.review(("dc-default",), str(tmp_path / "run"), "run")
    model.run(("dc-default",), str(tmp_path / "run"), "run")
    try:
        assert entered.wait(5)
        assert model.busy
        model.poll()
        with pytest.raises(ProductRequestError, match="active test"):
            model.open(str(tmp_path / "project.json"))
    finally:
        release.set()
        finish(model)
    assert "injected disk failure" in model.status
    assert not model.history


def test_live_batch_progress_is_marshaled_to_the_ui_thread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = workspace(tmp_path)
    reported, release = Event(), Event()

    def blocked(*args: Any, **kwargs: Any) -> Any:
        kwargs["report_progress"](
            ValidationBatchProgress(
                "run",
                1,
                ValidationBatchPhase.RUNNING,
                "dc-default",
                1,
                2,
                0,
            )
        )
        reported.set()
        assert release.wait(5)
        raise OSError("injected completion failure")

    monkeypatch.setattr(workspace_module, "publish_validation_project_run", blocked)
    selected = ("dc-default", "frequency-default")
    model.review(selected, str(tmp_path / "run"), "run")
    model.run(selected, str(tmp_path / "run"), "run")
    try:
        assert reported.wait(5)
        model.poll()
        assert model.busy
        assert model.progress == ValidationBatchProgress(
            "run",
            1,
            ValidationBatchPhase.RUNNING,
            "dc-default",
            1,
            2,
            0,
        )
        assert "dc-default (1/2)" in model.status
        assert "completed 0/2" in model.status
        assert "RUNNING" in model.status
        assert model.request_cancel()
        assert "preset dc-default" in model.status
    finally:
        release.set()
        finish(model)
    assert "injected completion failure" in model.status


def test_batch_cancel_is_idempotent_and_publishes_cancelled_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = workspace(tmp_path)
    original = workspace_module.publish_validation_project_run
    entered = Event()

    def wait_for_cancel(*args: Any, **kwargs: Any) -> Any:
        token = kwargs["cancellation"]
        assert isinstance(token, ValidationBatchCancellationToken)
        entered.set()
        deadline = monotonic() + 5
        while not token.is_cancellation_requested:
            assert monotonic() < deadline
            sleep(0.001)
        return original(*args, **kwargs)

    monkeypatch.setattr(
        workspace_module, "publish_validation_project_run", wait_for_cancel
    )
    selected = ("dc-default", "frequency-default")
    destination = tmp_path / "cancelled"
    model.review(selected, str(destination), "run")
    model.run(selected, str(destination), "run")
    assert entered.wait(5)
    assert model.request_cancel()
    assert not model.request_cancel()
    assert model.cancellation_requested
    assert "Cancellation requested" in model.status
    finish(model)
    manifest = model.history[destination / "run-manifest.json"]
    assert manifest.batch_status is ValidationBatchStatus.CANCELLED
    assert manifest.records == ()
    assert manifest.not_started_preset_ids == selected
    assert model.progress is not None
    assert model.progress.phase is ValidationBatchPhase.FINISHED
    assert model.progress.batch_status is ValidationBatchStatus.CANCELLED
    assert not model.cancellation_requested
    assert "Batch CANCELLED" in model.status
    assert "not started: 2" in model.status


def test_cancel_requires_an_active_batch(tmp_path: Path) -> None:
    model = workspace(tmp_path)
    with pytest.raises(ProductRequestError, match="No project batch"):
        model.request_cancel()


def test_thread_start_failure_and_missing_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = workspace(tmp_path)
    model.review(("dc-default",), str(tmp_path / "run"), "run")
    with monkeypatch.context() as context:
        context.setattr(
            workspace_module.Thread,
            "start",
            lambda self: (_ for _ in ()).throw(RuntimeError("start failed")),
        )
        with pytest.raises(RuntimeError, match="start failed"):
            model.run(("dc-default",), str(tmp_path / "run"), "run")
    assert not model.busy
    assert not model.cancellation_requested
    thread = workspace_module.Thread(target=lambda: None)
    thread.start()
    thread.join()
    model._thread = thread
    model.poll()
    assert "without a completion" in model.status


def test_history_validation_is_atomic_and_rechecks_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = workspace(tmp_path)
    run(model, tmp_path / "one", "one")
    run(model, tmp_path / "two", "two")
    with pytest.raises(ProductRequestError, match="new run ID"):
        model.review(("dc-default",), str(tmp_path / "third"), "one")
    paths = tuple(str(path) for path in model.history)
    for selected in ((), (paths[0],), (paths[0], paths[0])):
        with pytest.raises(ProductRequestError, match="exactly two"):
            model.compare(selected)
    with pytest.raises(ProductRequestError, match="only once"):
        model.load_history((paths[0], paths[0]))
    shutil.copytree(tmp_path / "one", tmp_path / "duplicate")
    with pytest.raises(ProductRequestError, match="duplicate project/run"):
        model.load_history((str(tmp_path / "duplicate" / "run-manifest.json"),))
    assert len(model.history) == 2
    with monkeypatch.context() as context:
        context.setattr(workspace_module, "MAX_VALIDATION_HISTORY_INPUTS", 2)
        with pytest.raises(ProductRequestError, match="64 manifests"):
            model.load_history((str(tmp_path / "new.json"),))
        with pytest.raises(ProductRequestError, match="Clear the history"):
            model.review(("read-default",), str(tmp_path / "three"), "three")
    (tmp_path / "one" / "project.snapshot.json").write_text("{}", encoding="utf-8")
    with pytest.raises(Exception, match="SHA-256"):
        model.compare(paths)
    assert len(model.history) == 2


def test_replay_capture_resolves_path_and_serial_capture_is_rejected(
    tmp_path: Path,
) -> None:
    model = workspace(tmp_path)
    draft = DashboardWizardDraft(
        source_mode=ProductSourceMode.CSV_REPLAY, replay_path=str(tmp_path / "data.csv")
    )
    model.add_preset("replay", "Replay", draft.to_product_configuration())
    assert model.project is not None
    assert model.project.presets[-1].configuration.replay_path == tmp_path / "data.csv"
    from dataclasses import replace

    with pytest.raises(Exception, match="Serial"):
        model.add_preset(
            "serial",
            "Serial",
            replace(
                DashboardWizardDraft().to_product_configuration(),
                source_mode=ProductSourceMode.SERIAL_READ_ONLY,
            ),
        )


class Widget(FakeWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.selected: tuple[str, ...] = ()
        self.running = False
        self.focused = ""
        self.seen = ""

    def bind(self, event: str, callback: Any, add: str = "") -> None:
        self.bindings[event] = callback

    def focus(self, row: str | None = None) -> str:
        if row is not None:
            self.focused = row
        return self.focused

    def see(self, row: str) -> None:
        self.seen = row

    def add(self, *args: Any, **kwargs: Any) -> None:
        pass

    def selection(self) -> tuple[str, ...]:
        return self.selected

    def selection_set(self, rows: Any) -> None:
        self.selected = tuple(rows)

    def insert(
        self,
        parent: str,
        index: str,
        *,
        values: tuple[Any, ...],
        iid: str | None = None,
    ) -> str:
        key = iid or str(len(self.rows))
        self.rows[key] = values
        return key

    def yview(self, *args: Any) -> None:
        pass

    xview = yview
    set = yview


def test_table_keyboard_ranges_shrink_reset_and_clamp() -> None:
    tree = Widget()
    _bind_table_selection(tree)
    press = lambda key: tree.bindings[key](None)
    assert press("<Shift-Up>") == "break"
    assert press("<Control-a>") == "break"
    for row in ("a", "b", "c", "d"):
        tree.insert("", "end", iid=row, values=(row,))
    press("<Control-A>")
    assert tree.selection() == ("a", "b", "c", "d")
    assert tree.focus() == tree.seen == "a"
    tree.selection_set(("b",))
    tree.focus("b")
    press("<Shift-Down>")
    assert tree.selection() == ("b", "c")
    press("<Shift-Down>")
    press("<Shift-Down>")
    assert tree.selection() == ("b", "c", "d")
    press("<Shift-Up>")
    assert tree.selection() == ("b", "c")
    press("<Shift-Up>")
    assert tree.selection() == ("b",)
    press("<Shift-Up>")
    press("<Shift-Up>")
    assert tree.selection() == ("a", "b")
    press("<Down>")  # Ordinary navigation/mouse selection starts a new anchor.
    tree.focus("c")
    tree.selection_set(("c",))
    press("<Shift-Up>")
    assert tree.selection() == ("b", "c")
    tree.focus("d")  # An external selection change also resets the anchor.
    tree.selection_set(("d",))
    press("<Shift-Up>")
    assert tree.selection() == ("c", "d")
    tree.rows.clear()  # A reload cannot retain a stale row anchor.
    tree.insert("", "end", iid="new", values=())
    press("<Shift-Down>")
    assert tree.selection() == ("new",)
    assert tree.focus() == tree.seen == "new"


def test_project_page_full_action_chain(tmp_path: Path) -> None:
    model = ProjectWorkspace(lambda: False)
    answers: dict[str, Any] = {
        "project-save": str(tmp_path / "project.json"),
        "project-open": str(tmp_path / "project.json"),
        "run-directory": str(tmp_path / "one"),
        "history": (),
    }
    ttk = SimpleNamespace(
        **{
            name: Widget
            for name in (
                "Frame",
                "LabelFrame",
                "Label",
                "Entry",
                "Button",
                "Treeview",
                "Scrollbar",
                "Progressbar",
            )
        }
    )
    page = ProjectPage(
        Widget(),
        SimpleNamespace(StringVar=FakeVariable),
        ttk,
        Widget(),
        model,
        lambda mode: answers[mode],
        DashboardWizardDraft,
    )
    assert page.project_id.get() == "validation-project"
    assert page.project_name.get() == "Analog validation project"
    assert "Create starter" in page.project_guide.get()
    assert "SYNTHETIC" in page.setup_capture_guide.get()
    assert "Review selected batch" in page.batch_review_guide.get()
    assert not page.batch_review.rows
    assert page.save_button.config["state"] == "disabled"
    assert page.add_preset_button.config["state"] == "disabled"
    assert page.review_button.config["state"] == "disabled"
    assert page.run_button.config["state"] == "disabled"
    assert page.compare_button.config["state"] == "disabled"
    assert page.clear_history_button.config["state"] == "disabled"
    page.act(page.create)
    page.act(page.open)
    assert len(page.presets.rows) == 6
    assert page.presets.kwargs["style"] == "Modern.Treeview"
    assert page.history.kwargs["style"] == "Modern.Treeview"
    assert page.input_artifacts.kwargs["style"] == "Modern.Treeview"
    assert page.comparison.kwargs["style"] == "Modern.Treeview"
    assert page.batch_review.kwargs["style"] == "Modern.Treeview"
    assert all(
        row[2] == "Simulator — synthetic data" for row in page.presets.rows.values()
    )
    assert "No run history" in page.comparison_guide.get()
    assert "Select one history row" in page.input_archive_guide.get()
    assert not page.input_artifacts.rows
    assert page.progress.kwargs["style"] == "Accent.Horizontal.TProgressbar"
    assert page.cancel_button.kwargs["style"] == "Danger.TButton"
    assert page.save_button.config["state"] == "normal"
    assert page.add_preset_button.config["state"] == "normal"
    assert page.review_button.config["state"] == "disabled"
    page.current_draft = lambda: (_ for _ in ()).throw(
        ProductRequestError("Setup is incomplete")
    )
    page.render()
    assert "preview is not ready" in page.setup_capture_guide.get()
    assert page.add_preset_button.config["state"] == "disabled"
    page.current_draft = DashboardWizardDraft
    page.render()
    assert page.add_preset_button.config["state"] == "normal"
    page.presets.selection_set(("dc-default",))
    page.act(page.choose_output)
    assert page.review_button.config["state"] == "normal"
    assert "Review selected batch" in page.project_guide.get()
    page.act(page.review)
    assert page.run_button.config["state"] == "normal"
    assert "Ready to run" in page.project_guide.get()
    assert "FROZEN REVIEW" in page.batch_review_guide.get()
    assert str((tmp_path / "one").resolve()) in page.batch_review_guide.get()
    assert tuple(page.batch_review.rows.values()) == (
        (
            "1/1",
            "dc-default",
            "Evaluate a synthetic DC transfer sweep",
            "Simulator — synthetic data",
            "DC analysis",
            "SYNTHETIC",
        ),
    )
    page.act(page.run)
    assert not page.batch_review.rows
    assert page.progress.config == {"maximum": 1, "value": 0}
    assert page.cancel_button.config["state"] == "normal"
    assert all(control.config["state"] == "disabled" for control in page.controls)
    finish(model)
    page.render()
    assert page.progress.config == {"maximum": 1, "value": 1}
    assert page.cancel_button.config["state"] == "disabled"
    assert page.run_button.config["state"] == "disabled"
    page.destination.set(str(tmp_path / "two"))
    page.run_id.set("run-002")
    page.presets.selection_set(("frequency-default",))
    page.act(page.review)
    page.act(page.run)
    finish(model)
    page.render()
    page.history.selection_set(page.history.get_children())
    page.render()
    assert "Keep two rows selected" in page.input_archive_guide.get()
    assert not page.input_artifacts.rows
    assert page.compare_button.config["state"] == "normal"
    page.act(page.compare)
    assert page.comparison.rows
    assert "Project identity: validation-project" in page.comparison_guide.get()
    assert "candidate - baseline" in page.comparison_guide.get()
    assert "SYNTHETIC" in page.comparison_guide.get()
    assert any("CHANGED" in row for row in page.comparison.rows.values())
    assert all(len(row) == 8 for row in page.history.rows.values())
    assert {row[2] for row in page.history.rows.values()} == {
        ValidationBatchStatus.PARTIAL.value
    }
    page.act(page.add_preset)
    assert model.dirty
    assert "UNSAVED PROJECT" in page.project_guide.get()
    assert page.review_button.config["state"] == "disabled"
    answers["project-save"] = str(tmp_path / "copy.json")
    page.act(page.save)
    assert not model.dirty
    answers["history"] = tuple(str(path) for path in model.history)
    page.act(page.load_history)
    source_manifest = next(iter(model.history.values()))
    replay_record = replace(
        source_manifest.records[0],
        source_mode=ProductSourceMode.CSV_REPLAY,
        evidence_source=EvidenceSource.CSV_REPLAY,
    )
    replay_manifest = replace(
        source_manifest,
        run_id="replay-input",
        records=(replay_record,),
        input_artifacts=(
            ValidationRunInputArtifact(
                replay_record.preset_id,
                ProductSourceMode.CSV_REPLAY,
                "inputs/01-dc-default.csv",
                42,
                "a" * 64,
            ),
        ),
    )
    replay_path = tmp_path / "replay-manifest.json"
    model.history[replay_path] = replay_manifest
    model._changed("Replay history added for presentation testing.")
    page.render()
    page.history.selection_set((str(replay_path),))
    page.render()
    assert "1 preset reference" in page.input_archive_guide.get()
    assert tuple(page.input_artifacts.rows.values()) == (
        (
            replay_record.preset_id,
            "inputs/01-dc-default.csv",
            42,
            "a" * 64,
        ),
    )
    legacy = replace(
        next(iter(model.history.values())),
        run_id="legacy-run",
        schema_version=VALIDATION_RUN_MANIFEST_V1_SCHEMA_VERSION,
        batch_status=None,
    )
    model.clear_history()
    page.render()
    assert not page.comparison.rows
    assert "No run history" in page.comparison_guide.get()
    model.history[tmp_path / "legacy-manifest.json"] = legacy
    model._changed("Legacy history added for presentation testing.")
    page.render()
    assert next(iter(page.history.rows.values()))[2] == "LEGACY_V1"
    page.history.selection_set(page.history.get_children())
    page.render()
    assert "predates retained Replay inputs" in page.input_archive_guide.get()
    model.clear_history()
    page.render()
    for mode in answers:
        answers[mode] = ""
    for action in (
        page.create,
        page.open,
        page.save,
        page.choose_output,
        page.load_history,
    ):
        page.act(action)
    page.act(page.compare)
    assert "exactly two" in page.status.get()
    page.act(page.request_cancel)
    assert "No project batch" in page.status.get()
    model.other_busy = lambda: True
    page.render()
    assert all(control.config["state"] == "disabled" for control in page.controls)
    assert page.cancel_button.config["state"] == "disabled"
    model.other_busy = lambda: False
    page.render()
    assert page.save_button.config["state"] == "normal"
    assert page.add_preset_button.config["state"] == "normal"
    assert page.review_button.config["state"] == "normal"
    assert page.run_button.config["state"] == "disabled"
    assert page.compare_button.config["state"] == "disabled"
    assert page.clear_history_button.config["state"] == "disabled"


def test_project_dialog_modes_are_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def choose(**kwargs: Any) -> str:
        calls.append(kwargs)
        return "selected"

    fake = SimpleNamespace(
        askopenfilenames=choose,
        askopenfilename=choose,
        asksaveasfilename=choose,
        askyesno=choose,
    )
    monkeypatch.setitem(
        sys.modules, "tkinter", SimpleNamespace(filedialog=fake, messagebox=fake)
    )
    for mode in (
        "history",
        "project-open",
        "project-save",
        "run-directory",
        "discard-project",
    ):
        assert app_module._choose_project_path(object(), mode) == "selected"
    assert calls[2]["defaultextension"] == ".json"
    assert calls[2]["initialfile"] == "validation-project.json"
    assert calls[3]["defaultextension"] == ""
    assert calls[2]["confirmoverwrite"] is False
    with pytest.raises(ProductRequestError, match="Unknown"):
        app_module._choose_project_path(object(), "invalid")


def test_project_page_is_connected_to_launch_and_close_waits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, tk, ttk = fake_toolkit()
    callbacks: dict[str, Any] = {}
    created: list[ProjectWorkspace] = []

    def widgets(*args: Any, **kwargs: Any) -> Any:
        callbacks.update(kwargs)
        return SimpleNamespace(
            notebook=object(),
            form=SimpleNamespace(snapshot=DashboardWizardDraft),
            section_frames={"export": FakeWidget()},
            render=lambda *args: None,
        )

    cleanup_entered, cleanup_release = Event(), Event()

    def page(*args: Any, **kwargs: Any) -> Any:
        assert callable(kwargs["on_load_setup"])
        model: ProjectWorkspace = args[4]
        created.append(model)
        assert args[5]("project-open") == "chosen"
        model._cancellation = ValidationBatchCancellationToken()

        def cleanup() -> None:
            while not model.cancellation_requested:
                sleep(0.001)
            cleanup_entered.set()
            assert cleanup_release.wait(5)

        model._thread = Thread(target=cleanup)
        model._thread.start()
        return SimpleNamespace(render=lambda: None)

    def mainloop() -> None:
        model = created[0]
        callbacks["on_run"]()
        assert "project batch" in model.status
        callbacks["on_discover"]()
        callbacks["on_close"]()
        assert not root.destroyed
        assert model.cancellation_requested
        assert cleanup_entered.wait(5)
        next(callback for delay, _, callback in root.scheduled if delay == 0)()
        assert not root.destroyed
        cleanup_release.set()
        thread = model._thread
        assert thread is not None
        thread.join(5)
        next(callback for delay, _, callback in root.scheduled if delay == 0)()
        assert root.destroyed

    monkeypatch.setattr(app_module, "create_dashboard_workflow_widgets", widgets)
    monkeypatch.setattr(app_module, "ProjectPage", page)
    monkeypatch.setattr(
        app_module, "ImportPage",
        lambda *args, **kwargs: SimpleNamespace(render=lambda: None, has_unsaved_work=False),
    )
    monkeypatch.setattr(app_module, "_choose_project_path", lambda *args: "chosen")
    monkeypatch.setattr(root, "mainloop", mainloop)
    assert app_module.launch_dashboard(tk_loader=lambda: (tk, ttk)).closed_safely


def test_unsaved_project_can_cancel_close(monkeypatch: pytest.MonkeyPatch) -> None:
    root, tk, ttk = fake_toolkit()
    callbacks: dict[str, Any] = {}
    answers = iter((False, True))

    def widgets(*args: Any, **kwargs: Any) -> Any:
        callbacks.update(kwargs)
        return SimpleNamespace(
            notebook=object(),
            form=SimpleNamespace(snapshot=DashboardWizardDraft),
            section_frames={"export": FakeWidget()},
            render=lambda *args: None,
        )

    def page(*args: Any, **kwargs: Any) -> Any:
        assert callable(kwargs["on_load_setup"])
        args[4].dirty = True
        return SimpleNamespace(render=lambda: None)

    def mainloop() -> None:
        callbacks["on_close"]()
        assert not root.destroyed
        callbacks["on_close"]()
        assert root.destroyed

    monkeypatch.setattr(app_module, "create_dashboard_workflow_widgets", widgets)
    monkeypatch.setattr(app_module, "ProjectPage", page)
    monkeypatch.setattr(
        app_module, "ImportPage",
        lambda *args, **kwargs: SimpleNamespace(render=lambda: None, has_unsaved_work=False),
    )
    monkeypatch.setattr(app_module, "_choose_project_path", lambda *args: next(answers))
    monkeypatch.setattr(root, "mainloop", mainloop)
    assert app_module.launch_dashboard(tk_loader=lambda: (tk, ttk)).closed_safely


def test_abnormal_event_loop_exit_does_not_claim_batch_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, tk, ttk = fake_toolkit()

    def page(*args: Any, **kwargs: Any) -> Any:
        assert callable(kwargs["on_load_setup"])
        args[4]._thread = SimpleNamespace(is_alive=lambda: True)
        return SimpleNamespace(render=lambda: None)

    monkeypatch.setattr(
        app_module,
        "create_dashboard_workflow_widgets",
        lambda *args, **kwargs: SimpleNamespace(
            notebook=object(),
            form=SimpleNamespace(snapshot=DashboardWizardDraft),
            section_frames={"export": FakeWidget()},
            render=lambda *args: None,
        ),
    )
    monkeypatch.setattr(app_module, "ProjectPage", page)
    monkeypatch.setattr(
        app_module, "ImportPage",
        lambda *args, **kwargs: SimpleNamespace(render=lambda: None, has_unsaved_work=False),
    )
    monkeypatch.setattr(root, "mainloop", lambda: None)
    with pytest.raises(app_module.ProductWorkerTimeoutError, match="project batch"):
        app_module.launch_dashboard(tk_loader=lambda: (tk, ttk))
