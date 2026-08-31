"""Headless Dashboard polling and close/cancel lifecycle controller."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..errors import ProductAppError, ProductRequestError
from ..issues import UserIssue, issue_from_exception
from ..models import (
    ProductJobEvent,
    ProductJobRequest,
    ProductJobResult,
    ProductWorkerState,
)
from .presenter import DashboardPresenter
from .state import DashboardAction, DashboardActionType, DashboardState


@runtime_checkable
class DashboardWorkerPort(Protocol):
    """Small worker surface polled by the UI owner thread."""

    @property
    def state(self) -> ProductWorkerState: ...

    @property
    def is_active(self) -> bool: ...

    @property
    def request(self) -> ProductJobRequest | None: ...

    @property
    def result(self) -> ProductJobResult | None: ...

    @property
    def issue(self) -> UserIssue | None: ...

    @property
    def dropped_event_count(self) -> int: ...

    def drain_events(self) -> tuple[ProductJobEvent, ...]: ...

    def request_cancel(self) -> bool: ...

    def close(self, timeout_s: float | None = None) -> None: ...


class DashboardController:
    """Move worker snapshots into a presenter; never create a job or adapter."""

    def __init__(
        self,
        presenter: DashboardPresenter,
        worker: DashboardWorkerPort,
    ) -> None:
        if not isinstance(presenter, DashboardPresenter):
            raise ProductRequestError("presenter must be a DashboardPresenter")
        if not isinstance(worker, DashboardWorkerPort):
            raise ProductRequestError("worker must satisfy DashboardWorkerPort")
        self._presenter = presenter
        self._worker = worker
        self._closed = False

    @property
    def state(self) -> DashboardState:
        """Return the latest immutable Dashboard state."""

        return self._presenter.state

    @property
    def is_closed(self) -> bool:
        """Return whether bounded worker shutdown completed."""

        return self._closed

    def poll(self) -> DashboardState:
        """Drain the bounded worker queue on the presenter's owner thread."""

        request = self._worker.request
        if request is not None and self.state.active_job_id != request.job_id:
            self._presenter.begin_job(request)
        for event in self._worker.drain_events():
            self._presenter.present_event(
                event,
                dropped_event_count=self._worker.dropped_event_count,
            )
        return self._presenter.present_worker_snapshot(
            self._worker.state,
            request=request,
            result=self._worker.result,
            issue=self._worker.issue,
            dropped_event_count=self._worker.dropped_event_count,
        )

    def request_cancel(self) -> bool:
        """Request cooperative cancellation and immediately refresh visible state."""

        if self._closed or not self._worker.is_active:
            return False
        try:
            changed = self._worker.request_cancel()
            self.poll()
            return changed
        except ProductAppError as error:
            self._presenter.present_issue(issue_from_exception(error))
            return False

    def request_close(self, timeout_s: float | None = None) -> bool:
        """Close only after the worker's cooperative cancel/join contract succeeds."""

        if self._closed:
            return True
        self._presenter.dispatch(DashboardAction(DashboardActionType.REQUEST_CLOSE))
        try:
            self._worker.close(timeout_s)
        except ProductAppError as error:
            self.poll()
            self._presenter.present_issue(issue_from_exception(error))
            return False
        self.poll()
        self._closed = True
        return True


__all__ = [
    "DashboardController",
    "DashboardWorkerPort",
]
