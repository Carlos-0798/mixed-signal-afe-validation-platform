from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from typing import Any, cast

import pytest

from analog_validation import EvidenceSource, MeasurementStatus, MeasurementUnit
from analog_validation import TestRunOutcome as RunOutcome
from analog_validation_app import ProductRequestError, UserIssue, UserIssueCode
from analog_validation_app import UserIssueSeverity as IssueSeverity
from analog_validation_app.dashboard import (
    DASHBOARD_HARDWARE_CLAIM,
    DASHBOARD_STATE_SCHEMA_VERSION,
    MAX_DASHBOARD_ARTIFACTS,
    MAX_DASHBOARD_EVENT_HISTORY,
    MAX_DASHBOARD_PLOT_POINTS,
    MAX_DASHBOARD_TEXT_CHARS,
    DashboardAction,
    DashboardActionType,
    DashboardArtifactsPanel,
    DashboardArtifactView,
    DashboardLivePanel,
    DashboardLivePoint,
    DashboardPlotPanel,
    DashboardPlotPoint,
    DashboardProgressPanel,
    DashboardResultPanel,
    initial_dashboard_state,
)
from analog_validation_app.models import (
    ProductJobType,
    ProductResultStatus,
    ProductSourceMode,
    ProductWorkerState,
)


def issue() -> UserIssue:
    return UserIssue(
        UserIssueCode.OPERATION_FAILED,
        IssueSeverity.ERROR,
        "The operation stopped.",
        "A guarded boundary rejected it.",
        "Review the request before retrying.",
        "ExampleError",
    )


def artifact() -> DashboardArtifactView:
    return DashboardArtifactView("report.txt", "text/plain", 12, "a" * 64)


def plot_point() -> DashboardPlotPoint:
    return DashboardPlotPoint(0, "point-0", "INCLUDED", ("input=1 mV",))


def test_initial_state_is_immutable_simulator_first_and_text_explicit() -> None:
    state = initial_dashboard_state()

    assert DASHBOARD_STATE_SCHEMA_VERSION == "dashboard-state.v1"
    assert DASHBOARD_HARDWARE_CLAIM == "NO_NEW_HARDWARE_VALIDATION"
    assert MAX_DASHBOARD_ARTIFACTS == 16
    assert MAX_DASHBOARD_EVENT_HISTORY == 64
    assert MAX_DASHBOARD_PLOT_POINTS == 10_000
    assert MAX_DASHBOARD_TEXT_CHARS == 1_024
    assert state.source.source_mode is ProductSourceMode.SIMULATOR
    assert state.source.profile_identity == "afe/1"
    assert state.configuration.job_type is ProductJobType.READ
    assert state.configuration.can_run is False
    assert state.progress.worker_state is ProductWorkerState.IDLE
    assert state.live.active is False
    assert state.live.total_points == 0
    assert "NOT RUN" in state.result.summary
    assert state.hardware_claim == DASHBOARD_HARDWARE_CLAIM
    with pytest.raises(FrozenInstanceError):
        state.revision = 2  # type: ignore[misc]


def test_all_valid_dashboard_actions_are_explicit() -> None:
    assert (
        DashboardAction(
            DashboardActionType.SELECT_SOURCE,
            source_mode=ProductSourceMode.CSV_REPLAY,
        ).source_mode
        is ProductSourceMode.CSV_REPLAY
    )
    assert (
        DashboardAction(
            DashboardActionType.SELECT_PROFILE,
            profile_name="afe",
            profile_version="1",
        ).profile_name
        == "afe"
    )
    assert (
        DashboardAction(
            DashboardActionType.SELECT_JOB,
            job_type=ProductJobType.DC_ANALYSIS,
        ).job_type
        is ProductJobType.DC_ANALYSIS
    )
    for action_type in (
        DashboardActionType.REQUEST_CANCEL,
        DashboardActionType.REQUEST_CLOSE,
        DashboardActionType.CLEAR_RESULT,
    ):
        assert DashboardAction(action_type).action_type is action_type


@pytest.mark.parametrize(
    "factory",
    [
        lambda: DashboardAction(cast(Any, "SELECT_SOURCE")),
        lambda: DashboardAction(DashboardActionType.SELECT_SOURCE),
        lambda: DashboardAction(
            DashboardActionType.SELECT_SOURCE,
            source_mode=ProductSourceMode.SIMULATOR,
            job_type=ProductJobType.READ,
        ),
        lambda: DashboardAction(DashboardActionType.SELECT_PROFILE),
        lambda: DashboardAction(
            DashboardActionType.SELECT_PROFILE,
            profile_name="afe",
        ),
        lambda: DashboardAction(
            DashboardActionType.SELECT_PROFILE,
            profile_name=" afe",
            profile_version="1",
        ),
        lambda: DashboardAction(
            DashboardActionType.SELECT_PROFILE,
            profile_name="afe",
            profile_version="1",
            source_mode=ProductSourceMode.SIMULATOR,
        ),
        lambda: DashboardAction(DashboardActionType.SELECT_JOB),
        lambda: DashboardAction(
            DashboardActionType.SELECT_JOB,
            job_type=ProductJobType.READ,
            profile_name="afe",
            profile_version="1",
        ),
        lambda: DashboardAction(
            DashboardActionType.REQUEST_CLOSE,
            source_mode=ProductSourceMode.SIMULATOR,
        ),
    ],
)
def test_action_contract_rejects_missing_or_mixed_payloads(factory: Any) -> None:
    with pytest.raises(ProductRequestError):
        factory()


def test_source_and_configuration_panels_validate_read_only_text_contract() -> None:
    state = initial_dashboard_state()
    source = state.source
    configuration = state.configuration

    with pytest.raises(ProductRequestError, match="source_mode"):
        replace(source, source_mode=cast(Any, "SIMULATOR"))
    for field, value in (
        ("source_name", ""),
        ("source_summary", " bad"),
        ("profile_name", "x" * (MAX_DASHBOARD_TEXT_CHARS + 1)),
        ("profile_version", "bad\nvalue"),
    ):
        with pytest.raises(ProductRequestError):
            replace(source, **cast(Any, {field: value}))
    with pytest.raises(ProductRequestError, match="read-only"):
        replace(source, read_only=False)
    with pytest.raises(ProductRequestError, match="job_type"):
        replace(configuration, job_type=cast(Any, "READ"))
    with pytest.raises(ProductRequestError):
        replace(configuration, summary="")
    with pytest.raises(ProductRequestError, match="can_run"):
        replace(configuration, can_run=cast(Any, "yes"))


def test_progress_panel_validates_counts_progress_and_cancel_semantics() -> None:
    active = DashboardProgressPanel(
        ProductWorkerState.RUNNING,
        "Running.",
        1,
        2,
        True,
        1,
        0,
        1,
    )
    assert active.completed == 1

    factories = (
        lambda: replace(active, worker_state=cast(Any, "RUNNING")),
        lambda: replace(active, status_text=""),
        lambda: replace(active, completed=None),
        lambda: replace(active, completed=True),
        lambda: replace(active, completed=3),
        lambda: replace(active, event_count=-1),
        lambda: replace(active, dropped_event_count=cast(Any, True)),
        lambda: replace(active, can_cancel=cast(Any, "yes")),
        lambda: replace(
            active,
            worker_state=ProductWorkerState.IDLE,
            can_cancel=True,
        ),
    )
    for factory in factories:
        with pytest.raises(ProductRequestError):
            factory()


def test_live_panel_validates_control_counts_and_visible_points() -> None:
    point = DashboardLivePoint(
        1,
        0,
        0.0,
        "afe.ch0.input",
        100.0,
        MeasurementUnit.MILLIVOLT,
        MeasurementStatus.VALID,
    )
    panel = DashboardLivePanel(
        True,
        False,
        True,
        False,
        "Live monitor running.",
        (point,),
        2,
        2,
        0,
        1,
        1,
        0,
        0,
        5.0,
    )
    assert panel.can_pause is True

    for factory in (
        lambda: replace(point, index=0),
        lambda: replace(point, elapsed_seconds=float("nan")),
        lambda: replace(point, channel=""),
        lambda: replace(point, value=float("inf")),
        lambda: replace(point, unit=cast(Any, "mV")),
        lambda: replace(point, status=cast(Any, "VALID")),
        lambda: replace(panel, active=cast(Any, 1)),
        lambda: replace(panel, can_pause=False),
        lambda: replace(panel, can_resume=True),
        lambda: replace(panel, points=cast(Any, [point])),
        lambda: replace(panel, points=(point,) * (MAX_DASHBOARD_PLOT_POINTS + 1)),
        lambda: replace(panel, pause_count=cast(Any, True)),
        lambda: replace(panel, retained_points=0),
        lambda: replace(panel, retained_points=0, evicted_points=2),
        lambda: replace(panel, evicted_points=1),
        lambda: replace(panel, valid_points=0),
        lambda: replace(panel, time_window_seconds=0.0),
    ):
        with pytest.raises(ProductRequestError):
            factory()


def test_plot_contract_is_bounded_and_uses_only_display_rows() -> None:
    point = plot_point()
    panel = DashboardPlotPanel("Plot", "Copied points.", (point,), 1)
    assert panel.points == (point,)

    for factory in (
        lambda: replace(point, index=-1),
        lambda: replace(point, label=""),
        lambda: replace(point, disposition=" bad"),
        lambda: replace(point, values=cast(Any, "input=1")),
        lambda: replace(panel, title=""),
        lambda: replace(panel, points=cast(Any, [point])),
        lambda: replace(panel, points=cast(Any, (object(),))),
        lambda: replace(panel, points=(point,) * (MAX_DASHBOARD_PLOT_POINTS + 1)),
        lambda: replace(panel, total_points=0),
        lambda: replace(panel, total_points=MAX_DASHBOARD_PLOT_POINTS + 1),
    ):
        with pytest.raises(ProductRequestError):
            factory()


def test_result_and_artifact_contracts_reject_invalid_views() -> None:
    result = DashboardResultPanel(
        ProductResultStatus.COMPLETED,
        RunOutcome.PASS,
        EvidenceSource.SYNTHETIC,
        "Copied result.",
        ("Software only.",),
        ("Hardware remains not verified.",),
        issue(),
    )
    selected_artifact = artifact()
    artifacts = DashboardArtifactsPanel("One artifact.", (selected_artifact,))
    assert result.issue is not None
    assert artifacts.artifacts[0].name == "report.txt"

    for factory in (
        lambda: replace(result, status=cast(Any, "COMPLETED")),
        lambda: replace(result, outcome=cast(Any, "PASS")),
        lambda: replace(result, evidence_source=cast(Any, "SYNTHETIC")),
        lambda: replace(result, summary=""),
        lambda: replace(result, limitations=cast(Any, "bad")),
        lambda: replace(result, limitations=()),
        lambda: replace(result, not_verified=()),
        lambda: replace(result, issue=cast(Any, object())),
        lambda: replace(selected_artifact, name=""),
        lambda: replace(selected_artifact, size_bytes=-1),
        lambda: replace(selected_artifact, sha256="bad"),
        lambda: replace(artifacts, summary=""),
        lambda: replace(artifacts, artifacts=cast(Any, [selected_artifact])),
        lambda: replace(artifacts, artifacts=cast(Any, (object(),))),
        lambda: replace(
            artifacts,
            artifacts=(selected_artifact,) * (MAX_DASHBOARD_ARTIFACTS + 1),
        ),
    ):
        with pytest.raises(ProductRequestError):
            factory()


def test_dashboard_state_rejects_invalid_composition_and_identity() -> None:
    state = initial_dashboard_state()

    for factory in (
        lambda: replace(state, revision=cast(Any, "0")),
        lambda: replace(state, revision=-1),
        lambda: replace(state, source=cast(Any, object())),
        lambda: replace(state, event_messages=cast(Any, "message")),
        lambda: replace(
            state,
            event_messages=("message",) * (MAX_DASHBOARD_EVENT_HISTORY + 1),
        ),
        lambda: replace(state, active_job_id=" bad"),
        lambda: replace(state, close_requested=cast(Any, "yes")),
        lambda: replace(state, hardware_claim="HARDWARE_VERIFIED"),
        lambda: replace(state, schema_version="dashboard-state.v2"),
    ):
        with pytest.raises(ProductRequestError):
            factory()
