"""Bounded single-owner worker for future product services."""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Callable
from datetime import datetime, timezone
from threading import Event, RLock, Thread, current_thread
from time import monotonic
from typing import Protocol, Self, runtime_checkable

from analog_validation import TestRunOutcome

from .errors import (
    ProductJobCancelled,
    ProductRequestError,
    ProductWorkerBusyError,
    ProductWorkerClosedError,
    ProductWorkerContractError,
    ProductWorkerError,
    ProductWorkerTimeoutError,
)
from .issues import UserIssue, issue_from_exception
from .models import (
    ProductJobEvent,
    ProductJobRequest,
    ProductJobResult,
    ProductResultStatus,
    ProductWorkerState,
)

DEFAULT_PRODUCT_EVENT_QUEUE_SIZE = 256
MAX_PRODUCT_EVENT_QUEUE_SIZE = 4096
DEFAULT_PRODUCT_JOIN_TIMEOUT_S = 5.0
MAX_PRODUCT_JOIN_TIMEOUT_S = 60.0
MAX_PRODUCT_CANCELLATION_WAIT_S = 60.0
_PRODUCT_JOIN_POLL_S = 0.05

ProductProgressReporter = Callable[[str, int | None, int | None], None]


class ProductCancellationToken:
    """Read-only cancellation view supplied to one running job service."""

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = Event()

    @property
    def is_cancellation_requested(self) -> bool:
        """Return whether the worker owner requested cooperative cancellation."""

        return self._event.is_set()

    def wait(self, timeout_s: float) -> bool:
        """Wait for cancellation for a finite, validated duration."""

        timeout = _bounded_seconds(
            "cancellation wait",
            timeout_s,
            minimum=0.0,
            maximum=MAX_PRODUCT_CANCELLATION_WAIT_S,
        )
        return self._event.wait(timeout)

    def raise_if_cancelled(self) -> None:
        """Stop a cooperative service at its next safe checkpoint."""

        if self.is_cancellation_requested:
            raise ProductJobCancelled("job cancellation was requested")

    def _request(self) -> None:
        self._event.set()


@runtime_checkable
class ProductJobService(Protocol):
    """Injected resource-owning operation used by the generic worker."""

    def run(
        self,
        request: ProductJobRequest,
        cancellation: ProductCancellationToken,
        report_progress: ProductProgressReporter,
    ) -> ProductJobResult:
        """Run one bounded job and return one validated terminal result."""

    def cleanup(self) -> None:
        """Release every resource owned by this service instance."""


ProductJobServiceFactory = Callable[[ProductJobRequest], ProductJobService]


def _bounded_seconds(
    name: str,
    value: object,
    *,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProductRequestError(f"{name} must be a finite number")
    checked = float(value)
    if not math.isfinite(checked):
        raise ProductRequestError(f"{name} must be a finite number")
    if checked < minimum or checked > maximum:
        raise ProductRequestError(
            f"{name} must be between {minimum:g} and {maximum:g} seconds"
        )
    return checked


def _event_queue_size(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProductRequestError("max_events must be an integer")
    if value <= 0 or value > MAX_PRODUCT_EVENT_QUEUE_SIZE:
        raise ProductRequestError(
            f"max_events must be between 1 and {MAX_PRODUCT_EVENT_QUEUE_SIZE}"
        )
    return value


class ProductJobWorker:
    """Run at most one injected service at a time and own its lifecycle."""

    def __init__(
        self,
        service_factory: ProductJobServiceFactory,
        *,
        max_events: int = DEFAULT_PRODUCT_EVENT_QUEUE_SIZE,
        join_timeout_s: float = DEFAULT_PRODUCT_JOIN_TIMEOUT_S,
    ) -> None:
        if not callable(service_factory):
            raise ProductRequestError("service_factory must be callable")
        self._service_factory = service_factory
        self._max_events = _event_queue_size(max_events)
        self._join_timeout_s = _bounded_seconds(
            "join timeout",
            join_timeout_s,
            minimum=0.001,
            maximum=MAX_PRODUCT_JOIN_TIMEOUT_S,
        )
        self._lock = RLock()
        self._events: deque[ProductJobEvent] = deque(maxlen=self._max_events)
        self._next_event_index = 1
        self._dropped_event_count = 0
        self._state = ProductWorkerState.IDLE
        self._request: ProductJobRequest | None = None
        self._result: ProductJobResult | None = None
        self._issue: UserIssue | None = None
        self._last_error: BaseException | None = None
        self._cleanup_error: BaseException | None = None
        self._cancellation: ProductCancellationToken | None = None
        self._thread: Thread | None = None
        self._completion: Event | None = None
        self._closed = False

    @property
    def state(self) -> ProductWorkerState:
        with self._lock:
            return self._state

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._state.is_active

    @property
    def is_closed(self) -> bool:
        with self._lock:
            return self._closed

    @property
    def request(self) -> ProductJobRequest | None:
        with self._lock:
            return self._request

    @property
    def result(self) -> ProductJobResult | None:
        with self._lock:
            return self._result

    @property
    def issue(self) -> UserIssue | None:
        with self._lock:
            return self._issue

    @property
    def last_error(self) -> BaseException | None:
        """Return developer-only captured execution detail."""

        with self._lock:
            return self._last_error

    @property
    def cleanup_error(self) -> BaseException | None:
        """Return developer-only cleanup detail when cleanup failed."""

        with self._lock:
            return self._cleanup_error

    @property
    def dropped_event_count(self) -> int:
        with self._lock:
            return self._dropped_event_count

    @property
    def events(self) -> tuple[ProductJobEvent, ...]:
        """Return a stable snapshot without consuming queued events."""

        with self._lock:
            return tuple(self._events)

    def drain_events(self) -> tuple[ProductJobEvent, ...]:
        """Atomically return and remove every currently retained event."""

        with self._lock:
            events = tuple(self._events)
            self._events.clear()
            return events

    def start(self, request: ProductJobRequest) -> None:
        """Start one job or fail without disturbing an already owned job."""

        if not isinstance(request, ProductJobRequest):
            raise ProductRequestError("request must be a ProductJobRequest")
        with self._lock:
            if self._closed:
                raise ProductWorkerClosedError("the product worker is closed")
            if self._state.is_active:
                owned_job_id = (
                    self._request.job_id if self._request is not None else "unknown"
                )
                raise ProductWorkerBusyError(
                    f"worker already owns active job {owned_job_id}"
                )
            self._request = request
            self._result = None
            self._issue = None
            self._last_error = None
            self._cleanup_error = None
            cancellation = ProductCancellationToken()
            completion = Event()
            self._cancellation = cancellation
            self._completion = completion
            self._state = ProductWorkerState.STARTING
            self._publish_locked("Job accepted by the worker.")
            try:
                thread = Thread(
                    target=self._run_job_with_completion,
                    args=(request, cancellation, completion),
                    name=f"analog-validation-{request.job_id}",
                    daemon=False,
                )
                self._thread = thread
                thread.start()
            except BaseException as error:
                failure = ProductWorkerError(
                    "the product worker thread could not start"
                )
                self._last_error = error
                self._issue = issue_from_exception(failure)
                self._state = ProductWorkerState.FAILED
                self._thread = None
                self._publish_locked(
                    "Job failed; review the attached issue.", issue=self._issue
                )
                raise failure from error

    def request_cancel(self) -> bool:
        """Request cancellation once; return whether this call changed state."""

        with self._lock:
            if self._state is ProductWorkerState.CANCELLING:
                return False
            if self._state not in {
                ProductWorkerState.STARTING,
                ProductWorkerState.RUNNING,
            }:
                return False
            if self._cancellation is None:
                raise ProductWorkerContractError(
                    "active worker is missing its cancellation token"
                )
            self._cancellation._request()
            self._state = ProductWorkerState.CANCELLING
            self._publish_locked("Cancellation requested; waiting for bounded cleanup.")
            return True

    def join(self, timeout_s: float | None = None) -> bool:
        """Wait for the current worker thread using only a bounded timeout."""

        timeout = (
            self._join_timeout_s
            if timeout_s is None
            else _bounded_seconds(
                "join timeout",
                timeout_s,
                minimum=0.001,
                maximum=MAX_PRODUCT_JOIN_TIMEOUT_S,
            )
        )
        deadline = monotonic() + timeout
        while True:
            with self._lock:
                thread = self._thread
                completion = self._completion
            if thread is None:
                return True
            if thread is current_thread():
                raise ProductWorkerContractError(
                    "a product worker thread cannot join itself"
                )
            if completion is None:
                raise ProductWorkerContractError(
                    "active worker is missing its completion event"
                )
            remaining = deadline - monotonic()
            if remaining <= 0:
                return False
            if completion.wait(min(remaining, _PRODUCT_JOIN_POLL_S)):
                thread.join(max(0.0, deadline - monotonic()))
                return True

    def cancel_and_join(self, timeout_s: float | None = None) -> None:
        """Request cooperative cancellation and require bounded termination."""

        self.request_cancel()
        if not self.join(timeout_s):
            raise ProductWorkerTimeoutError(
                "the product worker did not stop before the join timeout"
            )

    def close(self, timeout_s: float | None = None) -> None:
        """Permanently close this owner after cancelling and joining its job."""

        with self._lock:
            if self._thread is current_thread():
                raise ProductWorkerContractError(
                    "a product worker thread cannot close its own owner"
                )
            self._closed = True
        self.cancel_and_join(timeout_s)

    def __enter__(self) -> Self:
        with self._lock:
            if self._closed:
                raise ProductWorkerClosedError("the product worker is closed")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> None:
        self.close()

    def _run_job(
        self,
        request: ProductJobRequest,
        cancellation: ProductCancellationToken,
    ) -> None:
        service: ProductJobService | None = None
        result: ProductJobResult | None = None
        error: BaseException | None = None
        cleanup_error: BaseException | None = None

        try:
            candidate = self._service_factory(request)
            if not isinstance(candidate, ProductJobService):
                raise ProductWorkerContractError(
                    "service_factory must return a ProductJobService"
                )
            service = candidate
            with self._lock:
                cancellation.raise_if_cancelled()
                self._state = ProductWorkerState.RUNNING
                self._publish_locked("Job service started.")

            def report_progress(
                message: str,
                completed: int | None = None,
                total: int | None = None,
            ) -> None:
                self._report_progress(
                    request,
                    cancellation,
                    message,
                    completed,
                    total,
                )

            candidate_result = service.run(request, cancellation, report_progress)
            if not isinstance(candidate_result, ProductJobResult):
                raise ProductWorkerContractError(
                    "job service must return a ProductJobResult"
                )
            if candidate_result.request != request:
                raise ProductWorkerContractError(
                    "job service result does not match the owned request"
                )
            result = candidate_result
        except BaseException as caught:  # noqa: BLE001 - worker must capture failures
            error = caught
        finally:
            if service is not None:
                try:
                    service.cleanup()
                except BaseException as caught_cleanup:  # noqa: BLE001 - cleanup boundary
                    cleanup_error = caught_cleanup
            self._finish_job(
                request,
                cancellation,
                result,
                error,
                cleanup_error,
            )

    def _run_job_with_completion(
        self,
        request: ProductJobRequest,
        cancellation: ProductCancellationToken,
        completion: Event,
    ) -> None:
        """Set completion only after service cleanup and terminal publication."""

        try:
            self._run_job(request, cancellation)
        finally:
            completion.set()

    def _report_progress(
        self,
        request: ProductJobRequest,
        cancellation: ProductCancellationToken,
        message: str,
        completed: int | None,
        total: int | None,
    ) -> None:
        with self._lock:
            if current_thread() is not self._thread:
                raise ProductWorkerContractError(
                    "progress must be reported by the owned worker thread"
                )
            if self._request != request or self._cancellation is not cancellation:
                raise ProductWorkerContractError(
                    "progress does not belong to the active product job"
                )
            cancellation.raise_if_cancelled()
            if self._state is not ProductWorkerState.RUNNING:
                raise ProductWorkerContractError(
                    "progress is only valid while the job is running"
                )
            self._publish_locked(
                message,
                completed=completed,
                total=total,
            )

    def _finish_job(
        self,
        request: ProductJobRequest,
        cancellation: ProductCancellationToken,
        result: ProductJobResult | None,
        error: BaseException | None,
        cleanup_error: BaseException | None,
    ) -> None:
        with self._lock:
            if self._request != request or self._cancellation is not cancellation:
                return
            self._last_error = error
            self._cleanup_error = cleanup_error
            issue: UserIssue | None = None
            terminal_message: str

            if cleanup_error is not None:
                issue = issue_from_exception(cleanup_error)
                result = self._as_error_result(result)
                state = ProductWorkerState.FAILED
                terminal_message = "Job cleanup failed; review the attached issue."
            elif error is not None:
                if (
                    isinstance(error, ProductJobCancelled)
                    and cancellation.is_cancellation_requested
                ):
                    result = self._as_cancelled_result(result)
                    state = ProductWorkerState.CANCELLED
                    terminal_message = "Job cancelled and cleanup finished."
                else:
                    issue = issue_from_exception(error)
                    result = self._as_error_result(result)
                    state = ProductWorkerState.FAILED
                    terminal_message = "Job failed; review the attached issue."
            elif result is None:
                missing = ProductWorkerContractError(
                    "job service ended without a ProductJobResult"
                )
                self._last_error = missing
                issue = issue_from_exception(missing)
                state = ProductWorkerState.FAILED
                terminal_message = "Job failed; review the attached issue."
            elif result.status is ProductResultStatus.ERROR:
                returned_error = ProductWorkerError(
                    "job service returned an ERROR product result"
                )
                self._last_error = returned_error
                issue = issue_from_exception(returned_error)
                state = ProductWorkerState.FAILED
                terminal_message = "Job failed; review the attached issue."
            elif result.status is ProductResultStatus.CANCELLED:
                state = ProductWorkerState.CANCELLED
                terminal_message = "Job cancelled and cleanup finished."
            elif cancellation.is_cancellation_requested:
                result = self._as_cancelled_result(result)
                state = ProductWorkerState.CANCELLED
                terminal_message = "Job cancelled and cleanup finished."
            else:
                state = ProductWorkerState.SUCCEEDED
                terminal_message = "Job service completed and cleanup finished."

            self._result = result
            self._issue = issue
            self._state = state
            self._publish_locked(terminal_message, issue=issue)

    @staticmethod
    def _as_cancelled_result(
        result: ProductJobResult | None,
    ) -> ProductJobResult | None:
        if result is None:
            return None
        return ProductJobResult(
            request=result.request,
            status=ProductResultStatus.CANCELLED,
            evidence_source=result.evidence_source,
            limitations=result.limitations,
            test_run_outcome=TestRunOutcome.ABORTED,
        )

    @staticmethod
    def _as_error_result(
        result: ProductJobResult | None,
    ) -> ProductJobResult | None:
        if result is None:
            return None
        return ProductJobResult(
            request=result.request,
            status=ProductResultStatus.ERROR,
            evidence_source=result.evidence_source,
            limitations=result.limitations,
            test_run_outcome=TestRunOutcome.ERROR,
        )

    def _publish_locked(
        self,
        message: str,
        *,
        completed: int | None = None,
        total: int | None = None,
        issue: UserIssue | None = None,
    ) -> None:
        if self._request is None:
            raise ProductWorkerContractError(
                "worker cannot publish an event without an owned request"
            )
        event = ProductJobEvent(
            job_id=self._request.job_id,
            index=self._next_event_index,
            created_at=datetime.now(timezone.utc),
            state=self._state,
            message=message,
            completed=completed,
            total=total,
            issue=issue,
        )
        self._next_event_index += 1
        if len(self._events) == self._max_events:
            self._dropped_event_count += 1
        self._events.append(event)


__all__ = [
    "DEFAULT_PRODUCT_EVENT_QUEUE_SIZE",
    "DEFAULT_PRODUCT_JOIN_TIMEOUT_S",
    "MAX_PRODUCT_CANCELLATION_WAIT_S",
    "MAX_PRODUCT_EVENT_QUEUE_SIZE",
    "MAX_PRODUCT_JOIN_TIMEOUT_S",
    "ProductCancellationToken",
    "ProductJobService",
    "ProductJobServiceFactory",
    "ProductJobWorker",
    "ProductProgressReporter",
]
