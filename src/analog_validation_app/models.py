"""Immutable contracts shared by future CLI, worker, and Dashboard layers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from analog_validation import EvidenceSource, TestRunOutcome

from .errors import ProductRequestError
from .issues import UserIssue

PRODUCT_JOB_EVENT_SCHEMA_VERSION = "product-job-event.v1"
PRODUCT_JOB_SCHEMA_VERSION = "product-job.v1"
PRODUCT_RESULT_SCHEMA_VERSION = "product-result.v1"
MAX_PRODUCT_EVENT_TEXT_CHARS = 512
MAX_PRODUCT_IDENTIFIER_CHARS = 128
MAX_PRODUCT_LIMITATIONS = 64
MAX_PRODUCT_LIMITATION_CHARS = 1024


class ProductSourceMode(str, Enum):
    """Explicit source choices exposed by the product layer."""

    SIMULATOR = "SIMULATOR"
    CSV_REPLAY = "CSV_REPLAY"
    SERIAL_READ_ONLY = "SERIAL_READ_ONLY"


class ProductJobType(str, Enum):
    """High-level intent without embedding device-specific behavior."""

    READ = "READ"
    DC_ANALYSIS = "DC_ANALYSIS"
    HYSTERESIS_ANALYSIS = "HYSTERESIS_ANALYSIS"


class ProductResultStatus(str, Enum):
    """Product execution status kept separate from engineering conclusions."""

    COMPLETED = "COMPLETED"
    INCOMPLETE = "INCOMPLETE"
    UNSUPPORTED = "UNSUPPORTED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


class ProductWorkerState(str, Enum):
    """Stable lifecycle values shared by workers and future presenters."""

    IDLE = "IDLE"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    CANCELLING = "CANCELLING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def is_active(self) -> bool:
        """Return whether one worker still owns an active job."""

        return self in {
            ProductWorkerState.STARTING,
            ProductWorkerState.RUNNING,
            ProductWorkerState.CANCELLING,
        }

    @property
    def is_terminal(self) -> bool:
        """Return whether the worker published a terminal job state."""

        return self in {
            ProductWorkerState.SUCCEEDED,
            ProductWorkerState.FAILED,
            ProductWorkerState.CANCELLED,
        }


def _identifier(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProductRequestError(f"{name} must be a non-empty stripped string")
    if len(value) > MAX_PRODUCT_IDENTIFIER_CHARS:
        raise ProductRequestError(
            f"{name} exceeds {MAX_PRODUCT_IDENTIFIER_CHARS} characters"
        )
    if not value.isprintable():
        raise ProductRequestError(f"{name} must contain only printable characters")
    return value


def _limitations(values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ProductRequestError("limitations must be an iterable")
    frozen = tuple(values)
    if not frozen:
        raise ProductRequestError("at least one limitation is required")
    if len(frozen) > MAX_PRODUCT_LIMITATIONS:
        raise ProductRequestError(
            f"limitations exceeds {MAX_PRODUCT_LIMITATIONS} entries"
        )
    checked: list[str] = []
    for value in frozen:
        if not isinstance(value, str) or not value or value != value.strip():
            raise ProductRequestError(
                "each limitation must be a non-empty stripped string"
            )
        if len(value) > MAX_PRODUCT_LIMITATION_CHARS:
            raise ProductRequestError(
                f"limitation exceeds {MAX_PRODUCT_LIMITATION_CHARS} characters"
            )
        if not value.isprintable():
            raise ProductRequestError(
                "limitations must contain only printable characters"
            )
        checked.append(value)
    if len(checked) != len(set(checked)):
        raise ProductRequestError("limitations cannot contain duplicates")
    return tuple(checked)


def _event_text(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProductRequestError("event message must be a non-empty stripped string")
    if len(value) > MAX_PRODUCT_EVENT_TEXT_CHARS:
        raise ProductRequestError(
            f"event message exceeds {MAX_PRODUCT_EVENT_TEXT_CHARS} characters"
        )
    if not value.isprintable():
        raise ProductRequestError(
            "event message must contain only printable characters"
        )
    return value


def _event_time(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise ProductRequestError("event created_at must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ProductRequestError("event created_at must be timezone-aware")
    return value.astimezone(timezone.utc)


def _event_progress(
    completed: object,
    total: object,
) -> tuple[int | None, int | None]:
    if (completed is None) != (total is None):
        raise ProductRequestError("event completed and total must be provided together")
    if completed is None:
        return None, None
    if (
        isinstance(completed, bool)
        or not isinstance(completed, int)
        or isinstance(total, bool)
        or not isinstance(total, int)
    ):
        raise ProductRequestError("event completed and total must be integers")
    if total <= 0 or completed < 0 or completed > total:
        raise ProductRequestError("event progress must satisfy 0 <= completed <= total")
    return completed, total


@dataclass(frozen=True, slots=True)
class ProductJobEvent:
    """One immutable bounded worker event for future CLI/UI polling."""

    job_id: str
    index: int
    created_at: datetime
    state: ProductWorkerState
    message: str
    completed: int | None = None
    total: int | None = None
    issue: UserIssue | None = None
    schema_version: str = PRODUCT_JOB_EVENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _identifier("job_id", self.job_id)
        if isinstance(self.index, bool) or not isinstance(self.index, int):
            raise ProductRequestError("event index must be an integer")
        if self.index <= 0:
            raise ProductRequestError("event index must be positive")
        object.__setattr__(self, "created_at", _event_time(self.created_at))
        if not isinstance(self.state, ProductWorkerState):
            raise ProductRequestError("event state must be a ProductWorkerState")
        _event_text(self.message)
        completed, total = _event_progress(self.completed, self.total)
        if completed is not None and self.state is not ProductWorkerState.RUNNING:
            raise ProductRequestError("event progress is only valid in RUNNING state")
        object.__setattr__(self, "completed", completed)
        object.__setattr__(self, "total", total)
        if self.issue is not None and not isinstance(self.issue, UserIssue):
            raise ProductRequestError("event issue must be a UserIssue or None")
        if self.state is ProductWorkerState.FAILED and self.issue is None:
            raise ProductRequestError("FAILED events require a user issue")
        if self.state is not ProductWorkerState.FAILED and self.issue is not None:
            raise ProductRequestError("only FAILED events may carry a user issue")
        if self.schema_version != PRODUCT_JOB_EVENT_SCHEMA_VERSION:
            raise ProductRequestError(
                f"unsupported product job event schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class ProductJobRequest:
    """One reviewed product intent before any adapter or resource is created."""

    job_id: str
    source_mode: ProductSourceMode
    job_type: ProductJobType
    profile_name: str
    profile_version: str
    allow_output: bool = False
    schema_version: str = PRODUCT_JOB_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _identifier("job_id", self.job_id)
        if not isinstance(self.source_mode, ProductSourceMode):
            raise ProductRequestError("source_mode must be a ProductSourceMode")
        if not isinstance(self.job_type, ProductJobType):
            raise ProductRequestError("job_type must be a ProductJobType")
        _identifier("profile_name", self.profile_name)
        _identifier("profile_version", self.profile_version)
        if not isinstance(self.allow_output, bool):
            raise ProductRequestError("allow_output must be boolean")
        if self.allow_output:
            raise ProductRequestError(
                "the Phase 5 product contract is read-only; output is not available"
            )
        if self.schema_version != PRODUCT_JOB_SCHEMA_VERSION:
            raise ProductRequestError(
                f"unsupported product job schema: {self.schema_version}"
            )

    @property
    def profile_identity(self) -> str:
        """Return the explicit profile identity without inferring hardware."""

        return f"{self.profile_name}/{self.profile_version}"


_STATUS_OUTCOMES: dict[ProductResultStatus, frozenset[TestRunOutcome | None]] = {
    ProductResultStatus.COMPLETED: frozenset(
        {None, TestRunOutcome.PASS, TestRunOutcome.FAIL}
    ),
    ProductResultStatus.INCOMPLETE: frozenset({None, TestRunOutcome.INCOMPLETE}),
    ProductResultStatus.UNSUPPORTED: frozenset({None, TestRunOutcome.UNSUPPORTED}),
    ProductResultStatus.CANCELLED: frozenset({None, TestRunOutcome.ABORTED}),
    ProductResultStatus.ERROR: frozenset({None, TestRunOutcome.ERROR}),
}

_SOURCE_EVIDENCE: dict[ProductSourceMode, frozenset[EvidenceSource]] = {
    ProductSourceMode.SIMULATOR: frozenset({EvidenceSource.SYNTHETIC}),
    ProductSourceMode.CSV_REPLAY: frozenset({EvidenceSource.CSV_REPLAY}),
    ProductSourceMode.SERIAL_READ_ONLY: frozenset(
        {EvidenceSource.HOST_TEST, EvidenceSource.BENCH_CONTROLLER}
    ),
}


@dataclass(frozen=True, slots=True)
class ProductJobResult:
    """One terminal product result with explicit evidence and limitations."""

    request: ProductJobRequest
    status: ProductResultStatus
    evidence_source: EvidenceSource
    limitations: tuple[str, ...]
    test_run_outcome: TestRunOutcome | None = None
    schema_version: str = PRODUCT_RESULT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.request, ProductJobRequest):
            raise ProductRequestError("request must be a ProductJobRequest")
        if not isinstance(self.status, ProductResultStatus):
            raise ProductRequestError("status must be a ProductResultStatus")
        if not isinstance(self.evidence_source, EvidenceSource):
            raise ProductRequestError("evidence_source must be an EvidenceSource")
        if self.evidence_source not in _SOURCE_EVIDENCE[self.request.source_mode]:
            raise ProductRequestError(
                "evidence_source is inconsistent with the requested source_mode"
            )
        if self.test_run_outcome is not None and not isinstance(
            self.test_run_outcome, TestRunOutcome
        ):
            raise ProductRequestError(
                "test_run_outcome must be a TestRunOutcome or None"
            )
        if self.test_run_outcome not in _STATUS_OUTCOMES[self.status]:
            raise ProductRequestError(
                "test_run_outcome is inconsistent with the product result status"
            )
        object.__setattr__(self, "limitations", _limitations(self.limitations))
        if self.schema_version != PRODUCT_RESULT_SCHEMA_VERSION:
            raise ProductRequestError(
                f"unsupported product result schema: {self.schema_version}"
            )

    @property
    def is_engineering_conclusion(self) -> bool:
        """Return true only for a complete PASS or FAIL conclusion."""

        return self.test_run_outcome in {
            TestRunOutcome.PASS,
            TestRunOutcome.FAIL,
        }


__all__ = [
    "MAX_PRODUCT_EVENT_TEXT_CHARS",
    "MAX_PRODUCT_IDENTIFIER_CHARS",
    "MAX_PRODUCT_LIMITATIONS",
    "MAX_PRODUCT_LIMITATION_CHARS",
    "PRODUCT_JOB_EVENT_SCHEMA_VERSION",
    "PRODUCT_JOB_SCHEMA_VERSION",
    "PRODUCT_RESULT_SCHEMA_VERSION",
    "ProductJobEvent",
    "ProductJobRequest",
    "ProductJobResult",
    "ProductJobType",
    "ProductResultStatus",
    "ProductSourceMode",
    "ProductWorkerState",
]
