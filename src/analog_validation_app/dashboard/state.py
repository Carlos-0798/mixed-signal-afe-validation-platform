"""Immutable, headless state contracts for the local product Dashboard."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from analog_validation import EvidenceSource, TestRunOutcome

from ..errors import ProductRequestError
from ..issues import UserIssue
from ..models import (
    ProductJobType,
    ProductResultStatus,
    ProductSourceMode,
    ProductWorkerState,
)

DASHBOARD_STATE_SCHEMA_VERSION = "dashboard-state.v1"
DASHBOARD_HARDWARE_CLAIM = "NO_NEW_HARDWARE_VALIDATION"
MAX_DASHBOARD_ARTIFACTS = 16
MAX_DASHBOARD_EVENT_HISTORY = 64
MAX_DASHBOARD_PLOT_POINTS = 10_000
MAX_DASHBOARD_TEXT_CHARS = 1_024


class DashboardActionType(str, Enum):
    """Explicit user intents accepted by the headless presenter."""

    SELECT_SOURCE = "SELECT_SOURCE"
    SELECT_PROFILE = "SELECT_PROFILE"
    SELECT_JOB = "SELECT_JOB"
    REQUEST_CANCEL = "REQUEST_CANCEL"
    REQUEST_CLOSE = "REQUEST_CLOSE"
    CLEAR_RESULT = "CLEAR_RESULT"


def _text(name: str, value: object, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise ProductRequestError(f"{name} must be a stripped string")
    if not value and not allow_empty:
        raise ProductRequestError(f"{name} cannot be empty")
    if len(value) > MAX_DASHBOARD_TEXT_CHARS:
        raise ProductRequestError(
            f"{name} exceeds {MAX_DASHBOARD_TEXT_CHARS} characters"
        )
    if value and not value.isprintable():
        raise ProductRequestError(f"{name} must contain only printable characters")
    return value


def _text_tuple(
    name: str,
    values: object,
    *,
    maximum: int = MAX_DASHBOARD_EVENT_HISTORY,
    allow_empty: bool = True,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ProductRequestError(f"{name} must be an iterable")
    frozen = tuple(values)
    if not allow_empty and not frozen:
        raise ProductRequestError(f"{name} cannot be empty")
    if len(frozen) > maximum:
        raise ProductRequestError(f"{name} exceeds {maximum} entries")
    return tuple(_text(name, value) for value in frozen)


@dataclass(frozen=True, slots=True)
class DashboardAction:
    """One validated state-transition request from widgets or a controller."""

    action_type: DashboardActionType
    source_mode: ProductSourceMode | None = None
    profile_name: str | None = None
    profile_version: str | None = None
    job_type: ProductJobType | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.action_type, DashboardActionType):
            raise ProductRequestError("action_type must be a DashboardActionType")
        has_source = self.source_mode is not None
        has_profile = self.profile_name is not None or self.profile_version is not None
        has_job = self.job_type is not None
        if self.action_type is DashboardActionType.SELECT_SOURCE:
            if not isinstance(self.source_mode, ProductSourceMode):
                raise ProductRequestError("SELECT_SOURCE requires one source_mode")
            if has_profile or has_job:
                raise ProductRequestError("SELECT_SOURCE accepts only source_mode")
        elif self.action_type is DashboardActionType.SELECT_PROFILE:
            if self.profile_name is None or self.profile_version is None:
                raise ProductRequestError(
                    "SELECT_PROFILE requires profile_name and profile_version"
                )
            _text("profile_name", self.profile_name)
            _text("profile_version", self.profile_version)
            if has_source or has_job:
                raise ProductRequestError(
                    "SELECT_PROFILE accepts only an exact profile identity"
                )
        elif self.action_type is DashboardActionType.SELECT_JOB:
            if not isinstance(self.job_type, ProductJobType):
                raise ProductRequestError("SELECT_JOB requires one job_type")
            if has_source or has_profile:
                raise ProductRequestError("SELECT_JOB accepts only job_type")
        elif has_source or has_profile or has_job:
            raise ProductRequestError(
                f"{self.action_type.value} does not accept a selection payload"
            )


@dataclass(frozen=True, slots=True)
class DashboardSourcePanel:
    """Source, profile, connection, and evidence text shown together."""

    source_mode: ProductSourceMode
    source_name: str
    source_summary: str
    profile_name: str
    profile_version: str
    profile_display_name: str
    connection_text: str
    evidence_text: str
    read_only: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.source_mode, ProductSourceMode):
            raise ProductRequestError("source_mode must be a ProductSourceMode")
        for name in (
            "source_name",
            "source_summary",
            "profile_name",
            "profile_version",
            "profile_display_name",
            "connection_text",
            "evidence_text",
        ):
            _text(name, getattr(self, name))
        if self.read_only is not True:
            raise ProductRequestError("the Phase 5 Dashboard must remain read-only")

    @property
    def profile_identity(self) -> str:
        """Return the exact displayed profile identity."""

        return f"{self.profile_name}/{self.profile_version}"


@dataclass(frozen=True, slots=True)
class DashboardConfigurationPanel:
    """Selected job plus the visible safe-review decision."""

    job_type: ProductJobType
    job_name: str
    summary: str
    safety_review: str
    can_run: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.job_type, ProductJobType):
            raise ProductRequestError("job_type must be a ProductJobType")
        for name in ("job_name", "summary", "safety_review"):
            _text(name, getattr(self, name))
        if not isinstance(self.can_run, bool):
            raise ProductRequestError("can_run must be boolean")


@dataclass(frozen=True, slots=True)
class DashboardProgressPanel:
    """Bounded worker progress rendered without relying on color."""

    worker_state: ProductWorkerState
    status_text: str
    completed: int | None = None
    total: int | None = None
    can_cancel: bool = False
    event_count: int = 0
    dropped_event_count: int = 0
    last_event_index: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.worker_state, ProductWorkerState):
            raise ProductRequestError("worker_state must be a ProductWorkerState")
        _text("status_text", self.status_text)
        if (self.completed is None) != (self.total is None):
            raise ProductRequestError("completed and total must be present together")
        if self.completed is not None and (
            isinstance(self.completed, bool)
            or not isinstance(self.completed, int)
            or isinstance(self.total, bool)
            or not isinstance(self.total, int)
            or self.total <= 0
            or self.completed < 0
            or self.completed > self.total
        ):
            raise ProductRequestError("progress must satisfy 0 <= completed <= total")
        for name in ("event_count", "dropped_event_count", "last_event_index"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ProductRequestError(f"{name} must be a non-negative integer")
        if not isinstance(self.can_cancel, bool):
            raise ProductRequestError("can_cancel must be boolean")
        if self.can_cancel and not self.worker_state.is_active:
            raise ProductRequestError("only an active worker can be cancellable")


@dataclass(frozen=True, slots=True)
class DashboardPlotPoint:
    """One copied report row; values are display strings, not calculations."""

    index: int
    label: str
    disposition: str
    values: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            isinstance(self.index, bool)
            or not isinstance(self.index, int)
            or self.index < 0
        ):
            raise ProductRequestError("plot point index must be non-negative")
        _text("plot point label", self.label)
        _text("plot point disposition", self.disposition)
        object.__setattr__(
            self,
            "values",
            _text_tuple("plot point values", self.values, maximum=32),
        )


@dataclass(frozen=True, slots=True)
class DashboardPlotPanel:
    """Presentation-only point table backing the Plot region."""

    title: str
    summary: str
    points: tuple[DashboardPlotPoint, ...] = ()
    total_points: int = 0

    def __post_init__(self) -> None:
        _text("plot title", self.title)
        _text("plot summary", self.summary)
        if not isinstance(self.points, tuple) or not all(
            isinstance(value, DashboardPlotPoint) for value in self.points
        ):
            raise ProductRequestError(
                "plot points must be a tuple of DashboardPlotPoint"
            )
        if len(self.points) > MAX_DASHBOARD_PLOT_POINTS:
            raise ProductRequestError(
                f"plot points exceeds {MAX_DASHBOARD_PLOT_POINTS} entries"
            )
        if (
            isinstance(self.total_points, bool)
            or not isinstance(self.total_points, int)
            or self.total_points < len(self.points)
            or self.total_points > MAX_DASHBOARD_PLOT_POINTS
        ):
            raise ProductRequestError("total_points is inconsistent with plot points")


@dataclass(frozen=True, slots=True)
class DashboardResultPanel:
    """Product result, engineering outcome, evidence, and limitations."""

    status: ProductResultStatus | None
    outcome: TestRunOutcome | None
    evidence_source: EvidenceSource | None
    summary: str
    limitations: tuple[str, ...]
    not_verified: tuple[str, ...]
    issue: UserIssue | None = None

    def __post_init__(self) -> None:
        if self.status is not None and not isinstance(self.status, ProductResultStatus):
            raise ProductRequestError(
                "result status must be ProductResultStatus or None"
            )
        if self.outcome is not None and not isinstance(self.outcome, TestRunOutcome):
            raise ProductRequestError("outcome must be TestRunOutcome or None")
        if self.evidence_source is not None and not isinstance(
            self.evidence_source, EvidenceSource
        ):
            raise ProductRequestError("evidence_source must be EvidenceSource or None")
        _text("result summary", self.summary)
        object.__setattr__(
            self,
            "limitations",
            _text_tuple("limitations", self.limitations, allow_empty=False),
        )
        object.__setattr__(
            self,
            "not_verified",
            _text_tuple("not_verified", self.not_verified, allow_empty=False),
        )
        if self.issue is not None and not isinstance(self.issue, UserIssue):
            raise ProductRequestError("issue must be a UserIssue or None")


@dataclass(frozen=True, slots=True)
class DashboardArtifactView:
    """Path-free artifact identity safe for default UI display."""

    name: str
    media_type: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        _text("artifact name", self.name)
        _text("artifact media_type", self.media_type)
        if (
            isinstance(self.size_bytes, bool)
            or not isinstance(self.size_bytes, int)
            or self.size_bytes < 0
        ):
            raise ProductRequestError("artifact size_bytes must be non-negative")
        if (
            not isinstance(self.sha256, str)
            or len(self.sha256) != 64
            or any(value not in "0123456789abcdef" for value in self.sha256)
        ):
            raise ProductRequestError("artifact sha256 must contain 64 hex digits")


@dataclass(frozen=True, slots=True)
class DashboardArtifactsPanel:
    """Bounded report artifact list without absolute local paths."""

    summary: str
    artifacts: tuple[DashboardArtifactView, ...] = ()

    def __post_init__(self) -> None:
        _text("artifact summary", self.summary)
        if not isinstance(self.artifacts, tuple) or not all(
            isinstance(value, DashboardArtifactView) for value in self.artifacts
        ):
            raise ProductRequestError(
                "artifacts must be a tuple of DashboardArtifactView"
            )
        if len(self.artifacts) > MAX_DASHBOARD_ARTIFACTS:
            raise ProductRequestError(
                f"artifacts exceeds {MAX_DASHBOARD_ARTIFACTS} entries"
            )


@dataclass(frozen=True, slots=True)
class DashboardState:
    """Complete immutable view rendered by widgets on their owner thread."""

    revision: int
    source: DashboardSourcePanel
    configuration: DashboardConfigurationPanel
    progress: DashboardProgressPanel
    plot: DashboardPlotPanel
    result: DashboardResultPanel
    artifacts: DashboardArtifactsPanel
    event_messages: tuple[str, ...]
    active_job_id: str | None = None
    close_requested: bool = False
    hardware_claim: str = DASHBOARD_HARDWARE_CLAIM
    schema_version: str = DASHBOARD_STATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if isinstance(self.revision, bool) or not isinstance(self.revision, int):
            raise ProductRequestError("revision must be an integer")
        if self.revision < 0:
            raise ProductRequestError("revision must be non-negative")
        for name, expected in (
            ("source", DashboardSourcePanel),
            ("configuration", DashboardConfigurationPanel),
            ("progress", DashboardProgressPanel),
            ("plot", DashboardPlotPanel),
            ("result", DashboardResultPanel),
            ("artifacts", DashboardArtifactsPanel),
        ):
            if not isinstance(getattr(self, name), expected):
                raise ProductRequestError(f"{name} must be a {expected.__name__}")
        object.__setattr__(
            self,
            "event_messages",
            _text_tuple("event_messages", self.event_messages),
        )
        if self.active_job_id is not None:
            _text("active_job_id", self.active_job_id)
        if not isinstance(self.close_requested, bool):
            raise ProductRequestError("close_requested must be boolean")
        if self.hardware_claim != DASHBOARD_HARDWARE_CLAIM:
            raise ProductRequestError(
                f"hardware_claim must remain {DASHBOARD_HARDWARE_CLAIM}"
            )
        if self.schema_version != DASHBOARD_STATE_SCHEMA_VERSION:
            raise ProductRequestError(
                f"unsupported Dashboard state schema: {self.schema_version}"
            )


__all__ = [
    "DASHBOARD_HARDWARE_CLAIM",
    "DASHBOARD_STATE_SCHEMA_VERSION",
    "MAX_DASHBOARD_ARTIFACTS",
    "MAX_DASHBOARD_EVENT_HISTORY",
    "MAX_DASHBOARD_PLOT_POINTS",
    "MAX_DASHBOARD_TEXT_CHARS",
    "DashboardAction",
    "DashboardActionType",
    "DashboardArtifactView",
    "DashboardArtifactsPanel",
    "DashboardConfigurationPanel",
    "DashboardPlotPanel",
    "DashboardPlotPoint",
    "DashboardProgressPanel",
    "DashboardResultPanel",
    "DashboardSourcePanel",
    "DashboardState",
]
