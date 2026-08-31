from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Thread
from typing import Any, cast

import pytest

import analog_validation_app.dashboard.presenter as presenter_module
from analog_validation import EvidenceSource
from analog_validation import TestRunOutcome as RunOutcome
from analog_validation.exports import load_result_export_json
from analog_validation_app import (
    HumanReportPublication,
    ProductCatalogError,
    ProductJobEvent,
    ProductJobRequest,
    ProductJobResult,
    ProductJobType,
    ProductRequestError,
    ProductResultStatus,
    ProductSourceMode,
    ProductWorkerState,
    ReportArtifact,
    UserIssue,
    UserIssueCode,
    UserIssueSeverity,
    build_human_report_view,
)
from analog_validation_app.dashboard import (
    DashboardAction,
    DashboardActionType,
    DashboardPresenter,
    initial_dashboard_state,
)

ROOT = Path(__file__).resolve().parents[2]
DC_RESULT = ROOT / "test-data" / "golden" / "phase3_dc_sweep_result_v1.json"
HYSTERESIS_RESULT = ROOT / "test-data" / "golden" / "phase3_hysteresis_result_v1.json"


def request(
    job_id: str = "dashboard-job",
    *,
    source: ProductSourceMode = ProductSourceMode.SIMULATOR,
    job: ProductJobType = ProductJobType.READ,
    profile_name: str = "afe",
    profile_version: str = "1",
) -> ProductJobRequest:
    return ProductJobRequest(
        job_id,
        source,
        job,
        profile_name,
        profile_version,
    )


def result(
    selected: ProductJobRequest,
    *,
    status: ProductResultStatus = ProductResultStatus.COMPLETED,
    outcome: RunOutcome | None = RunOutcome.PASS,
    evidence: EvidenceSource = EvidenceSource.SYNTHETIC,
) -> ProductJobResult:
    return ProductJobResult(
        selected,
        status,
        evidence,
        ("Copied product limitation.",),
        outcome,
    )


def issue() -> UserIssue:
    return UserIssue(
        UserIssueCode.OPERATION_FAILED,
        UserIssueSeverity.ERROR,
        "The job stopped.",
        "A guarded boundary rejected the request.",
        "Review the configuration before retrying.",
        "ExampleFailure",
    )


def event(
    index: int,
    state: ProductWorkerState,
    *,
    selected_job: str = "dashboard-job",
    completed: int | None = None,
    total: int | None = None,
    selected_issue: UserIssue | None = None,
) -> ProductJobEvent:
    return ProductJobEvent(
        selected_job,
        index,
        datetime(2026, 8, 31, tzinfo=timezone.utc),
        state,
        f"Event {index}.",
        completed,
        total,
        selected_issue,
    )


def report_view(path: Path = DC_RESULT):
    return build_human_report_view(load_result_export_json(path))


def publication() -> HumanReportPublication:
    return HumanReportPublication(
        Path("C:/private/user/report"),
        (
            ReportArtifact("report.txt", "text/plain", 12, "a" * 64),
            ReportArtifact("chart.svg", "image/svg+xml", 34, "b" * 64),
        ),
    )


def test_presenter_starts_with_exact_headless_state_and_rejects_bad_seed() -> None:
    presenter = DashboardPresenter()
    seeded = DashboardPresenter(initial_dashboard_state())

    assert presenter.state.source.source_mode is ProductSourceMode.SIMULATOR
    assert seeded.state == presenter.state
    with pytest.raises(ProductRequestError, match="DashboardState"):
        DashboardPresenter(cast(Any, object()))


def test_initial_state_requires_one_default_and_one_compatible_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = presenter_module.list_product_sources()
    monkeypatch.setattr(
        presenter_module,
        "list_product_sources",
        lambda: tuple(cast(Any, source) for source in sources if not source.is_default),
    )
    with pytest.raises(ProductCatalogError, match="exactly one default"):
        presenter_module.initial_dashboard_state()

    monkeypatch.setattr(presenter_module, "list_product_sources", lambda: sources)
    monkeypatch.setattr(presenter_module, "list_product_profiles", lambda: ())
    with pytest.raises(ProductCatalogError, match="no compatible profile"):
        presenter_module.initial_dashboard_state()


def test_source_selection_rejects_a_catalog_with_no_compatible_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    presenter = DashboardPresenter()
    monkeypatch.setattr(presenter_module, "_compatible_profiles", lambda mode: ())

    with pytest.raises(ProductCatalogError, match="no compatible profile"):
        presenter.dispatch(
            DashboardAction(
                DashboardActionType.SELECT_SOURCE,
                source_mode=ProductSourceMode.CSV_REPLAY,
            )
        )


def test_selection_actions_use_reviewed_catalog_and_clear_old_results() -> None:
    presenter = DashboardPresenter()
    replay = presenter.dispatch(
        DashboardAction(
            DashboardActionType.SELECT_SOURCE,
            source_mode=ProductSourceMode.CSV_REPLAY,
        )
    )
    assert replay.source.source_mode is ProductSourceMode.CSV_REPLAY
    assert replay.active_job_id is None

    dc = presenter.dispatch(
        DashboardAction(
            DashboardActionType.SELECT_JOB,
            job_type=ProductJobType.DC_ANALYSIS,
        )
    )
    assert dc.configuration.job_type is ProductJobType.DC_ANALYSIS

    serial = presenter.dispatch(
        DashboardAction(
            DashboardActionType.SELECT_SOURCE,
            source_mode=ProductSourceMode.SERIAL_READ_ONLY,
        )
    )
    assert serial.configuration.job_type is ProductJobType.READ
    assert "Disconnected" in serial.source.connection_text

    msp = presenter.dispatch(
        DashboardAction(
            DashboardActionType.SELECT_PROFILE,
            profile_name="msp430-equipment-health",
            profile_version="1",
        )
    )
    assert msp.source.profile_identity == "msp430-equipment-health/1"

    with pytest.raises(ProductCatalogError, match="does not support"):
        presenter.dispatch(
            DashboardAction(
                DashboardActionType.SELECT_JOB,
                job_type=ProductJobType.DC_ANALYSIS,
            )
        )

    presenter.dispatch(
        DashboardAction(
            DashboardActionType.SELECT_SOURCE,
            source_mode=ProductSourceMode.SIMULATOR,
        )
    )
    with pytest.raises(ProductCatalogError, match="does not support"):
        presenter.dispatch(
            DashboardAction(
                DashboardActionType.SELECT_PROFILE,
                profile_name="msp430-equipment-health",
                profile_version="1",
            )
        )


def test_lifecycle_actions_are_visible_and_active_results_cannot_be_cleared() -> None:
    presenter = DashboardPresenter()
    with pytest.raises(ProductRequestError, match="no active"):
        presenter.dispatch(DashboardAction(DashboardActionType.REQUEST_CANCEL))

    selected = request()
    presenter.begin_job(selected)
    with pytest.raises(ProductRequestError, match="active"):
        presenter.dispatch(DashboardAction(DashboardActionType.CLEAR_RESULT))
    cancelling = presenter.dispatch(DashboardAction(DashboardActionType.REQUEST_CANCEL))
    assert cancelling.progress.worker_state is ProductWorkerState.CANCELLING
    assert cancelling.progress.can_cancel is False
    closed = presenter.dispatch(DashboardAction(DashboardActionType.REQUEST_CLOSE))
    assert closed.close_requested is True

    presenter.present_worker_snapshot(ProductWorkerState.SUCCEEDED, request=selected)
    cleared = presenter.dispatch(DashboardAction(DashboardActionType.CLEAR_RESULT))
    assert cleared.active_job_id is None
    assert cleared.event_messages == ()

    with pytest.raises(ProductRequestError, match="DashboardAction"):
        presenter.dispatch(cast(Any, object()))


def test_begin_job_and_events_copy_progress_issue_and_bounded_history() -> None:
    presenter = DashboardPresenter()
    with pytest.raises(ProductRequestError, match="ProductJobRequest"):
        presenter.begin_job(cast(Any, object()))
    with pytest.raises(ProductRequestError, match="begin_job"):
        presenter.present_event(event(1, ProductWorkerState.STARTING))

    selected = request()
    started = presenter.begin_job(selected)
    assert started.active_job_id == selected.job_id
    assert started.progress.can_cancel is True

    presenter.present_event(event(1, ProductWorkerState.STARTING))
    running = presenter.present_event(
        event(2, ProductWorkerState.RUNNING, completed=1, total=3),
        dropped_event_count=4,
    )
    assert running.progress.completed == 1
    assert running.progress.dropped_event_count == 4
    assert running.event_messages[-1] == "#2 [RUNNING] Event 2."

    failed = presenter.present_event(
        event(3, ProductWorkerState.FAILED, selected_issue=issue())
    )
    assert failed.result.issue is not None
    assert failed.result.summary == "The job stopped."

    for bad_event, count in (
        (cast(Any, object()), 0),
        (event(4, ProductWorkerState.RUNNING), cast(Any, True)),
        (event(4, ProductWorkerState.RUNNING), -1),
        (event(4, ProductWorkerState.RUNNING, selected_job="other"), 0),
        (event(3, ProductWorkerState.FAILED, selected_issue=issue()), 0),
    ):
        with pytest.raises(ProductRequestError):
            presenter.present_event(bad_event, dropped_event_count=count)


def test_worker_snapshot_validates_types_and_copies_terminal_result_and_issue() -> None:
    presenter = DashboardPresenter()
    selected = request()
    selected_result = result(selected)
    selected_issue = issue()

    state = presenter.present_worker_snapshot(
        ProductWorkerState.SUCCEEDED,
        request=selected,
        result=selected_result,
        issue=selected_issue,
        dropped_event_count=2,
    )
    assert state.active_job_id == selected.job_id
    assert state.progress.worker_state is ProductWorkerState.SUCCEEDED
    assert state.result.outcome is RunOutcome.PASS
    assert state.result.issue == selected_issue

    invalid_calls = (
        lambda: presenter.present_worker_snapshot(cast(Any, "IDLE")),
        lambda: presenter.present_worker_snapshot(
            ProductWorkerState.IDLE, request=cast(Any, object())
        ),
        lambda: presenter.present_worker_snapshot(
            ProductWorkerState.IDLE, result=cast(Any, object())
        ),
        lambda: presenter.present_worker_snapshot(
            ProductWorkerState.IDLE, issue=cast(Any, object())
        ),
        lambda: presenter.present_worker_snapshot(
            ProductWorkerState.IDLE, dropped_event_count=cast(Any, True)
        ),
        lambda: presenter.present_worker_snapshot(
            ProductWorkerState.IDLE, dropped_event_count=-1
        ),
    )
    for call in invalid_calls:
        with pytest.raises(ProductRequestError):
            call()


def test_result_issue_and_bench_boundary_are_copied_without_promotion() -> None:
    presenter = DashboardPresenter()
    selected = request(
        source=ProductSourceMode.SERIAL_READ_ONLY,
        profile_name="msp430-equipment-health",
    )
    presenter.begin_job(selected)
    bench = result(
        selected,
        evidence=EvidenceSource.BENCH_CONTROLLER,
    )
    state = presenter.present_result(bench)

    assert state.result.evidence_source is EvidenceSource.BENCH_CONTROLLER
    assert "does not validate physical AFE" in state.result.not_verified[0]
    assert state.result.issue is None
    state = presenter.present_issue(issue())
    assert state.result.issue is not None

    with pytest.raises(ProductRequestError, match="ProductJobResult"):
        presenter.present_result(cast(Any, object()))
    with pytest.raises(ProductRequestError, match="does not match"):
        presenter.present_result(result(request("other")))
    with pytest.raises(ProductRequestError, match="UserIssue"):
        presenter.present_issue(cast(Any, object()))


def test_report_view_and_publication_copy_points_values_and_path_free_artifacts() -> (
    None
):
    assert presenter_module._scalar_text(True) == "true"
    assert presenter_module._scalar_text(False) == "false"
    presenter = DashboardPresenter()
    dc = presenter.present_report(report_view())
    assert dc.plot.total_points == len(dc.plot.points)
    assert "input=" in dc.plot.points[0].values[0]
    assert dc.result.outcome is RunOutcome.PASS
    assert dc.artifacts.artifacts == ()

    hysteresis = presenter.present_report(report_view(HYSTERESIS_RESULT), publication())
    assert any(
        "direction=RISING" in value for value in hysteresis.plot.points[0].values
    )
    assert any("state=" in value for value in hysteresis.plot.points[0].values)
    assert tuple(value.name for value in hysteresis.artifacts.artifacts) == (
        "report.txt",
        "chart.svg",
    )
    assert "C:/private" not in hysteresis.artifacts.summary

    with pytest.raises(ProductRequestError, match="HumanReportView"):
        presenter.present_report(cast(Any, object()))
    with pytest.raises(ProductRequestError, match="HumanReportPublication"):
        presenter.present_report(report_view(), cast(Any, object()))


def test_presenter_rejects_updates_from_a_non_owner_thread() -> None:
    presenter = DashboardPresenter()
    errors: list[BaseException] = []

    def update() -> None:
        try:
            presenter.dispatch(DashboardAction(DashboardActionType.REQUEST_CLOSE))
        except BaseException as error:  # noqa: BLE001 - captured test evidence
            errors.append(error)

    thread = Thread(target=update)
    thread.start()
    thread.join(2.0)

    assert not thread.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], ProductRequestError)
    assert "creating UI thread" in str(errors[0])
