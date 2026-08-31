"""Headless Dashboard presenter that copies finalized product information."""

from __future__ import annotations

from dataclasses import replace
from threading import get_ident
from typing import Any, cast

from analog_validation import EvidenceSource, TestRunOutcome

from ..catalog import (
    ProductProfileDescriptor,
    ProductSourceDescriptor,
    get_product_profile,
    get_product_source,
    list_product_profiles,
    list_product_sources,
)
from ..errors import ProductCatalogError, ProductRequestError
from ..issues import UserIssue
from ..models import (
    ProductJobEvent,
    ProductJobRequest,
    ProductJobResult,
    ProductJobType,
    ProductResultStatus,
    ProductSourceMode,
    ProductWorkerState,
)
from ..presentation import HumanReportView, ReportScalar
from ..reporting import HumanReportPublication
from .state import (
    MAX_DASHBOARD_EVENT_HISTORY,
    DashboardAction,
    DashboardActionType,
    DashboardArtifactsPanel,
    DashboardArtifactView,
    DashboardConfigurationPanel,
    DashboardPlotPanel,
    DashboardPlotPoint,
    DashboardProgressPanel,
    DashboardResultPanel,
    DashboardSourcePanel,
    DashboardState,
)

_NOT_RUN = (
    "Physical AFE performance is NOT VERIFIED by opening this Dashboard.",
    "No wiring, protection, instrument accuracy, or reliability claim is created.",
)

_JOB_NAMES = {
    ProductJobType.READ: "Read observations",
    ProductJobType.DC_ANALYSIS: "DC analysis",
    ProductJobType.HYSTERESIS_ANALYSIS: "Hysteresis analysis",
}

_WORKER_STATUS = {
    ProductWorkerState.IDLE: "Idle — no job owns a resource.",
    ProductWorkerState.STARTING: "Starting the reviewed application service.",
    ProductWorkerState.RUNNING: "Running; progress is copied from worker events.",
    ProductWorkerState.CANCELLING: "Cancellation requested; waiting for bounded cleanup.",
    ProductWorkerState.SUCCEEDED: "Job completed and cleanup finished.",
    ProductWorkerState.FAILED: "Job stopped with a structured issue.",
    ProductWorkerState.CANCELLED: "Job cancelled and cleanup finished.",
}

_OUTCOME_STATUS = {
    TestRunOutcome.PASS: ProductResultStatus.COMPLETED,
    TestRunOutcome.FAIL: ProductResultStatus.COMPLETED,
    TestRunOutcome.INCOMPLETE: ProductResultStatus.INCOMPLETE,
    TestRunOutcome.UNSUPPORTED: ProductResultStatus.UNSUPPORTED,
    TestRunOutcome.ABORTED: ProductResultStatus.CANCELLED,
    TestRunOutcome.ERROR: ProductResultStatus.ERROR,
}


def _compatible_profiles(
    mode: ProductSourceMode,
) -> tuple[ProductProfileDescriptor, ...]:
    return tuple(
        profile for profile in list_product_profiles() if mode in profile.source_modes
    )


def _source_panel(
    source: ProductSourceDescriptor,
    profile: ProductProfileDescriptor,
) -> DashboardSourcePanel:
    if source.mode not in profile.source_modes:
        raise ProductCatalogError(
            f"profile {profile.identity} does not support {source.mode.value}"
        )
    connection = (
        "Disconnected — selecting a read-only profile does not open a serial port."
        if source.mode is ProductSourceMode.SERIAL_READ_ONLY
        else "Offline source selected — no physical device or port is open."
    )
    evidence = ", ".join(value.value for value in source.evidence_sources)
    return DashboardSourcePanel(
        source.mode,
        source.display_name,
        source.summary,
        profile.name,
        profile.version,
        profile.display_name,
        connection,
        f"Declared evidence class: {evidence}",
    )


def _configuration_panel(
    source: ProductSourceDescriptor,
    job_type: ProductJobType,
) -> DashboardConfigurationPanel:
    if job_type not in source.supported_jobs:
        raise ProductCatalogError(
            f"{source.mode.value} does not support {job_type.value}"
        )
    return DashboardConfigurationPanel(
        job_type,
        _JOB_NAMES[job_type],
        "Use the six-step wizard to configure and review this test.",
        "READ-ONLY DEFAULT: selection alone opens no adapter, serial port, file, or output path.",
        can_run=False,
    )


def _empty_progress() -> DashboardProgressPanel:
    return DashboardProgressPanel(
        ProductWorkerState.IDLE,
        _WORKER_STATUS[ProductWorkerState.IDLE],
    )


def _empty_plot() -> DashboardPlotPanel:
    return DashboardPlotPanel(
        "Plot / point table",
        "No finalized report is loaded; the Dashboard does not invent preview data.",
    )


def _empty_result() -> DashboardResultPanel:
    return DashboardResultPanel(
        None,
        None,
        None,
        "NOT RUN — no engineering conclusion is available.",
        ("No finalized product result has been presented.",),
        _NOT_RUN,
    )


def _empty_artifacts() -> DashboardArtifactsPanel:
    return DashboardArtifactsPanel(
        "No artifacts are present; complete a reviewed analysis before exporting."
    )


def initial_dashboard_state() -> DashboardState:
    """Create the deterministic Simulator-first Dashboard state."""

    defaults = tuple(source for source in list_product_sources() if source.is_default)
    if len(defaults) != 1:
        raise ProductCatalogError(
            "the product catalog must define exactly one default source"
        )
    source = defaults[0]
    profiles = _compatible_profiles(source.mode)
    if not profiles:
        raise ProductCatalogError("the default source has no compatible profile")
    job_type = source.supported_jobs[0]
    return DashboardState(
        revision=0,
        source=_source_panel(source, profiles[0]),
        configuration=_configuration_panel(source, job_type),
        progress=_empty_progress(),
        plot=_empty_plot(),
        result=_empty_result(),
        artifacts=_empty_artifacts(),
        event_messages=(),
    )


def _scalar_text(value: ReportScalar) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(value, ".12g")
    return str(value)


def _report_point_values(view: HumanReportView) -> tuple[DashboardPlotPoint, ...]:
    return tuple(
        DashboardPlotPoint(
            point.index,
            point.label,
            point.disposition,
            tuple(
                f"{value.name}={_scalar_text(value.value)} {value.unit}"
                for value in point.values
            ),
        )
        for point in view.points
    )


def _product_not_verified(source: EvidenceSource) -> tuple[str, ...]:
    if source is EvidenceSource.BENCH_CONTROLLER:
        return (
            "Controller-side bench evidence does not validate physical AFE performance.",
            "External wiring, analog accuracy, protection, and reliability remain NOT VERIFIED.",
        )
    return _NOT_RUN


class DashboardPresenter:
    """Own one immutable state sequence on the creating UI/main thread."""

    def __init__(self, state: DashboardState | None = None) -> None:
        if state is not None and not isinstance(state, DashboardState):
            raise ProductRequestError("state must be a DashboardState or None")
        self._owner_thread_id = get_ident()
        self._state = state or initial_dashboard_state()

    @property
    def state(self) -> DashboardState:
        """Return the latest immutable state."""

        return self._state

    def _require_owner(self) -> None:
        if get_ident() != self._owner_thread_id:
            raise ProductRequestError(
                "Dashboard presenter updates must run on the creating UI thread"
            )

    def _replace(self, **changes: Any) -> DashboardState:
        self._require_owner()
        candidate = replace(self._state, **changes)
        if candidate == self._state:
            return self._state
        self._state = replace(candidate, revision=self._state.revision + 1)
        return self._state

    def dispatch(self, action: DashboardAction) -> DashboardState:
        """Apply one validated user selection or lifecycle intent."""

        self._require_owner()
        if not isinstance(action, DashboardAction):
            raise ProductRequestError("action must be a DashboardAction")
        if action.action_type is DashboardActionType.SELECT_SOURCE:
            source = get_product_source(cast(ProductSourceMode, action.source_mode))
            profiles = _compatible_profiles(source.mode)
            if not profiles:
                raise ProductCatalogError(
                    f"source {source.mode.value} has no compatible profile"
                )
            job = (
                self._state.configuration.job_type
                if self._state.configuration.job_type in source.supported_jobs
                else source.supported_jobs[0]
            )
            return self._replace(
                source=_source_panel(source, profiles[0]),
                configuration=_configuration_panel(source, job),
                progress=_empty_progress(),
                plot=_empty_plot(),
                result=_empty_result(),
                artifacts=_empty_artifacts(),
                event_messages=(),
                active_job_id=None,
            )
        if action.action_type is DashboardActionType.SELECT_PROFILE:
            profile = get_product_profile(
                cast(str, action.profile_name), cast(str, action.profile_version)
            )
            source = get_product_source(self._state.source.source_mode)
            return self._replace(source=_source_panel(source, profile))
        if action.action_type is DashboardActionType.SELECT_JOB:
            source = get_product_source(self._state.source.source_mode)
            return self._replace(
                configuration=_configuration_panel(
                    source, cast(ProductJobType, action.job_type)
                )
            )
        if action.action_type is DashboardActionType.REQUEST_CANCEL:
            progress = self._state.progress
            if not progress.worker_state.is_active:
                raise ProductRequestError("no active Dashboard job can be cancelled")
            return self._replace(
                progress=replace(
                    progress,
                    worker_state=ProductWorkerState.CANCELLING,
                    status_text=_WORKER_STATUS[ProductWorkerState.CANCELLING],
                    can_cancel=False,
                )
            )
        if action.action_type is DashboardActionType.REQUEST_CLOSE:
            return self._replace(close_requested=True)
        if action.action_type is DashboardActionType.CLEAR_RESULT:
            if self._state.progress.worker_state.is_active:
                raise ProductRequestError(
                    "an active Dashboard result cannot be cleared"
                )
            return self._replace(
                plot=_empty_plot(),
                result=_empty_result(),
                artifacts=_empty_artifacts(),
                event_messages=(),
                active_job_id=None,
            )
        raise ProductRequestError(  # pragma: no cover - exhaustive enum guard
            f"unsupported Dashboard action: {action.action_type}"
        )

    def begin_job(self, request: ProductJobRequest) -> DashboardState:
        """Present one already-reviewed worker request without creating resources."""

        self._require_owner()
        if not isinstance(request, ProductJobRequest):
            raise ProductRequestError("request must be a ProductJobRequest")
        source = get_product_source(request.source_mode)
        profile = get_product_profile(request.profile_name, request.profile_version)
        return self._replace(
            source=_source_panel(source, profile),
            configuration=_configuration_panel(source, request.job_type),
            progress=DashboardProgressPanel(
                ProductWorkerState.STARTING,
                _WORKER_STATUS[ProductWorkerState.STARTING],
                can_cancel=True,
            ),
            plot=_empty_plot(),
            result=_empty_result(),
            artifacts=_empty_artifacts(),
            event_messages=(),
            active_job_id=request.job_id,
        )

    def present_review(
        self,
        request: ProductJobRequest,
        review_lines: tuple[str, ...],
    ) -> DashboardState:
        """Show the exact compiled job before Run without opening its resource."""

        self._require_owner()
        if not isinstance(request, ProductJobRequest):
            raise ProductRequestError("request must be a ProductJobRequest")
        if not isinstance(review_lines, tuple) or not review_lines:
            raise ProductRequestError("review_lines must be a non-empty tuple")
        source = get_product_source(request.source_mode)
        profile = get_product_profile(request.profile_name, request.profile_version)
        panel = _configuration_panel(source, request.job_type)
        return self._replace(
            source=_source_panel(source, profile),
            configuration=replace(
                panel,
                summary="Configuration compiled and ready for explicit Run.",
                safety_review=" | ".join(review_lines),
                can_run=True,
            ),
            progress=_empty_progress(),
            plot=_empty_plot(),
            result=_empty_result(),
            artifacts=_empty_artifacts(),
            event_messages=(),
            active_job_id=None,
        )

    def present_event(
        self,
        event: ProductJobEvent,
        *,
        dropped_event_count: int = 0,
    ) -> DashboardState:
        """Copy one worker event into bounded text and progress state."""

        self._require_owner()
        if not isinstance(event, ProductJobEvent):
            raise ProductRequestError("event must be a ProductJobEvent")
        if isinstance(dropped_event_count, bool) or not isinstance(
            dropped_event_count, int
        ):
            raise ProductRequestError("dropped_event_count must be an integer")
        if dropped_event_count < 0:
            raise ProductRequestError("dropped_event_count must be non-negative")
        if self._state.active_job_id is None:
            raise ProductRequestError("begin_job must precede Dashboard worker events")
        if event.job_id != self._state.active_job_id:
            raise ProductRequestError(
                "worker event job_id does not match Dashboard job"
            )
        if event.index <= self._state.progress.last_event_index:
            raise ProductRequestError("Dashboard worker event indexes must increase")
        line = f"#{event.index} [{event.state.value}] {event.message}"
        history = (self._state.event_messages + (line,))[-MAX_DASHBOARD_EVENT_HISTORY:]
        progress = DashboardProgressPanel(
            event.state,
            event.message,
            event.completed,
            event.total,
            event.state in {ProductWorkerState.STARTING, ProductWorkerState.RUNNING},
            self._state.progress.event_count + 1,
            dropped_event_count,
            event.index,
        )
        result = self._state.result
        if event.issue is not None:
            result = replace(
                result,
                summary=event.issue.what_happened,
                issue=event.issue,
            )
        return self._replace(
            progress=progress,
            result=result,
            event_messages=history,
        )

    def present_worker_snapshot(
        self,
        worker_state: ProductWorkerState,
        *,
        request: ProductJobRequest | None = None,
        result: ProductJobResult | None = None,
        issue: UserIssue | None = None,
        dropped_event_count: int = 0,
    ) -> DashboardState:
        """Synchronize non-event worker fields after one bounded UI poll."""

        self._require_owner()
        if not isinstance(worker_state, ProductWorkerState):
            raise ProductRequestError("worker_state must be a ProductWorkerState")
        if request is not None and not isinstance(request, ProductJobRequest):
            raise ProductRequestError("request must be ProductJobRequest or None")
        if result is not None and not isinstance(result, ProductJobResult):
            raise ProductRequestError("result must be ProductJobResult or None")
        if issue is not None and not isinstance(issue, UserIssue):
            raise ProductRequestError("issue must be UserIssue or None")
        if isinstance(dropped_event_count, bool) or not isinstance(
            dropped_event_count, int
        ):
            raise ProductRequestError("dropped_event_count must be an integer")
        if dropped_event_count < 0:
            raise ProductRequestError("dropped_event_count must be non-negative")
        if request is not None and self._state.active_job_id != request.job_id:
            self.begin_job(request)
        progress = self._state.progress
        progress = replace(
            progress,
            worker_state=worker_state,
            status_text=(
                progress.status_text
                if progress.worker_state is worker_state
                else _WORKER_STATUS[worker_state]
            ),
            can_cancel=worker_state
            in {ProductWorkerState.STARTING, ProductWorkerState.RUNNING},
            dropped_event_count=dropped_event_count,
        )
        self._replace(progress=progress)
        if result is not None:
            self.present_result(result)
        if issue is not None:
            self.present_issue(issue)
        return self._state

    def present_result(self, result: ProductJobResult) -> DashboardState:
        """Copy one terminal product result without changing its outcome."""

        self._require_owner()
        if not isinstance(result, ProductJobResult):
            raise ProductRequestError("result must be a ProductJobResult")
        if self._state.active_job_id != result.request.job_id:
            raise ProductRequestError("product result does not match Dashboard job")
        outcome = (
            "none" if result.test_run_outcome is None else result.test_run_outcome.value
        )
        panel = DashboardResultPanel(
            result.status,
            result.test_run_outcome,
            result.evidence_source,
            f"Product status {result.status.value}; engineering outcome {outcome}.",
            result.limitations,
            _product_not_verified(result.evidence_source),
        )
        return self._replace(result=panel)

    def present_issue(self, issue: UserIssue) -> DashboardState:
        """Present structured what/why/next-step text without parsing messages."""

        self._require_owner()
        if not isinstance(issue, UserIssue):
            raise ProductRequestError("issue must be a UserIssue")
        return self._replace(
            result=replace(
                self._state.result,
                summary=issue.what_happened,
                issue=issue,
            )
        )

    def present_report(
        self,
        view: HumanReportView,
        publication: HumanReportPublication | None = None,
    ) -> DashboardState:
        """Copy an existing report view and optional path-free artifact identities."""

        self._require_owner()
        if not isinstance(view, HumanReportView):
            raise ProductRequestError("view must be a HumanReportView")
        if publication is not None and not isinstance(
            publication, HumanReportPublication
        ):
            raise ProductRequestError(
                "publication must be a HumanReportPublication or None"
            )
        points = _report_point_values(view)
        artifacts = (
            ()
            if publication is None
            else tuple(
                DashboardArtifactView(
                    artifact.name,
                    artifact.media_type,
                    artifact.size_bytes,
                    artifact.sha256,
                )
                for artifact in publication.artifacts
            )
        )
        artifact_panel = DashboardArtifactsPanel(
            (
                "No report directory was published; the finalized view is in memory."
                if publication is None
                else f"{len(artifacts)} report artifacts published; absolute path is hidden in this view."
            ),
            artifacts,
        )
        return self._replace(
            plot=DashboardPlotPanel(
                view.title,
                f"{view.chart_kind.value}; copied {len(points)} finalized report points.",
                points,
                len(points),
            ),
            result=DashboardResultPanel(
                _OUTCOME_STATUS[view.outcome],
                view.outcome,
                view.evidence_source,
                view.summary,
                view.limitations,
                view.not_verified,
            ),
            artifacts=artifact_panel,
        )


__all__ = [
    "DashboardPresenter",
    "initial_dashboard_state",
]
