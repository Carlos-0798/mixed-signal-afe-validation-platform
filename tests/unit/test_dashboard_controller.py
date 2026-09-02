from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

import pytest

from analog_validation import EvidenceSource
from analog_validation import TestRunOutcome as RunOutcome
from analog_validation_app import (
    ProductJobEvent,
    ProductJobRequest,
    ProductJobResult,
    ProductJobType,
    ProductRequestError,
    ProductResultStatus,
    ProductSourceMode,
    ProductWorkerContractError,
    ProductWorkerState,
    ProductWorkerTimeoutError,
    UserIssue,
)
from analog_validation_app.dashboard import DashboardController, DashboardPresenter


def request() -> ProductJobRequest:
    return ProductJobRequest(
        "controller-job",
        ProductSourceMode.SIMULATOR,
        ProductJobType.READ,
        "afe",
        "1",
    )


def result(selected: ProductJobRequest) -> ProductJobResult:
    return ProductJobResult(
        selected,
        ProductResultStatus.COMPLETED,
        EvidenceSource.SYNTHETIC,
        ("Controller test uses synthetic software evidence.",),
        RunOutcome.PASS,
    )


class FakeWorker:
    def __init__(self) -> None:
        self.state = ProductWorkerState.IDLE
        self.request: ProductJobRequest | None = None
        self.result: ProductJobResult | None = None
        self.issue: UserIssue | None = None
        self.dropped_event_count = 0
        self.events: list[ProductJobEvent] = []
        self.cancel_calls = 0
        self.close_calls: list[float | None] = []
        self.cancel_error: ProductWorkerContractError | None = None
        self.close_error: ProductWorkerTimeoutError | None = None

    @property
    def is_active(self) -> bool:
        return self.state.is_active

    def drain_events(self) -> tuple[ProductJobEvent, ...]:
        selected = tuple(self.events)
        self.events.clear()
        return selected

    def request_cancel(self) -> bool:
        self.cancel_calls += 1
        if self.cancel_error is not None:
            raise self.cancel_error
        if not self.is_active or self.state is ProductWorkerState.CANCELLING:
            return False
        self.state = ProductWorkerState.CANCELLING
        self.events.append(
            ProductJobEvent(
                "controller-job",
                2,
                datetime(2026, 8, 31, tzinfo=timezone.utc),
                ProductWorkerState.CANCELLING,
                "Cancellation requested.",
            )
        )
        return True

    def close(self, timeout_s: float | None = None) -> None:
        self.close_calls.append(timeout_s)
        if self.close_error is not None:
            raise self.close_error
        if self.is_active:
            self.state = ProductWorkerState.CANCELLED


def worker_event(
    index: int,
    state: ProductWorkerState,
    *,
    completed: int | None = None,
    total: int | None = None,
) -> ProductJobEvent:
    return ProductJobEvent(
        "controller-job",
        index,
        datetime(2026, 8, 31, tzinfo=timezone.utc),
        state,
        f"Worker event {index}.",
        completed,
        total,
    )


class ReusableFakeWorker(FakeWorker):
    """Keep unread prior events to reproduce the immediate-rerun boundary."""

    def start(self, selected: ProductJobRequest) -> None:
        self.request = selected
        self.result = None
        self.issue = None
        self.state = ProductWorkerState.STARTING
        self.events.append(
            ProductJobEvent(
                selected.job_id,
                3,
                datetime(2026, 8, 31, tzinfo=timezone.utc),
                ProductWorkerState.STARTING,
                "Replacement job accepted.",
            )
        )


def test_controller_requires_headless_presenter_and_worker_port() -> None:
    presenter = DashboardPresenter()
    worker = FakeWorker()
    assert DashboardController(presenter, worker).state == presenter.state

    with pytest.raises(ProductRequestError, match="presenter"):
        DashboardController(cast(Any, object()), worker)
    with pytest.raises(ProductRequestError, match="DashboardWorkerPort"):
        DashboardController(presenter, cast(Any, object()))


def test_start_job_rejects_invalid_request_and_is_noop_after_close() -> None:
    controller = DashboardController(DashboardPresenter(), FakeWorker())
    with pytest.raises(ProductRequestError, match="ProductJobRequest"):
        controller.start_job(cast(Any, object()))
    assert controller.request_close()
    assert controller.start_job(request()) is False


def test_poll_drains_events_and_copies_terminal_snapshot() -> None:
    selected = request()
    worker = FakeWorker()
    worker.request = selected
    worker.state = ProductWorkerState.SUCCEEDED
    worker.result = result(selected)
    worker.dropped_event_count = 3
    worker.events.extend(
        (
            worker_event(1, ProductWorkerState.STARTING),
            worker_event(2, ProductWorkerState.RUNNING, completed=1, total=1),
        )
    )
    controller = DashboardController(DashboardPresenter(), worker)

    state = controller.poll()

    assert worker.events == []
    assert state.active_job_id == selected.job_id
    assert state.progress.worker_state is ProductWorkerState.SUCCEEDED
    assert state.progress.dropped_event_count == 3
    assert state.result.outcome is RunOutcome.PASS
    assert len(state.event_messages) == 2


def test_start_job_reconciles_unread_terminal_event_before_immediate_rerun() -> None:
    previous = request()
    replacement = ProductJobRequest(
        "controller-rerun",
        ProductSourceMode.SIMULATOR,
        ProductJobType.READ,
        "afe",
        "1",
    )
    worker = ReusableFakeWorker()
    worker.request = previous
    worker.result = result(previous)
    worker.state = ProductWorkerState.SUCCEEDED
    worker.events.append(
        ProductJobEvent(
            previous.job_id,
            2,
            datetime(2026, 8, 31, tzinfo=timezone.utc),
            ProductWorkerState.SUCCEEDED,
            "Previous job finished.",
        )
    )
    controller = DashboardController(DashboardPresenter(), worker)

    assert controller.start_job(replacement) is True
    assert controller.state.active_job_id == replacement.job_id
    assert controller.state.progress.worker_state is ProductWorkerState.STARTING
    assert controller.state.event_messages == (
        "#3 [STARTING] Replacement job accepted.",
    )
    assert controller.state.result.issue is None


def test_cancel_is_cooperative_visible_and_noop_when_idle_or_closed() -> None:
    worker = FakeWorker()
    controller = DashboardController(DashboardPresenter(), worker)
    assert controller.request_cancel() is False

    worker.request = request()
    worker.state = ProductWorkerState.RUNNING
    worker.events.append(worker_event(1, ProductWorkerState.RUNNING))
    assert controller.request_cancel() is True
    assert worker.cancel_calls == 1
    assert controller.state.progress.worker_state is ProductWorkerState.CANCELLING
    assert controller.state.progress.can_cancel is False

    worker.state = ProductWorkerState.CANCELLED
    assert controller.request_close() is True
    assert controller.is_closed is True
    assert controller.request_cancel() is False


def test_cancel_expected_failure_becomes_structured_issue() -> None:
    worker = FakeWorker()
    worker.request = request()
    worker.state = ProductWorkerState.RUNNING
    worker.cancel_error = ProductWorkerContractError("missing cancellation token")
    controller = DashboardController(DashboardPresenter(), worker)

    assert controller.request_cancel() is False
    assert controller.state.result.issue is not None
    assert controller.state.result.issue.technical_type == "ProductWorkerContractError"


def test_close_calls_bounded_worker_close_and_is_idempotent() -> None:
    worker = FakeWorker()
    controller = DashboardController(DashboardPresenter(), worker)

    assert controller.request_close(0.25) is True
    assert worker.close_calls == [0.25]
    assert controller.state.close_requested is True
    assert controller.is_closed is True
    assert controller.request_close(0.5) is True
    assert worker.close_calls == [0.25]


def test_close_timeout_keeps_controller_open_and_explains_safe_next_step() -> None:
    worker = FakeWorker()
    worker.request = request()
    worker.state = ProductWorkerState.RUNNING
    worker.close_error = ProductWorkerTimeoutError("bounded close expired")
    controller = DashboardController(DashboardPresenter(), worker)

    assert controller.request_close(0.1) is False
    assert controller.is_closed is False
    assert controller.state.close_requested is True
    assert controller.state.result.issue is not None
    assert controller.state.result.issue.technical_type == "ProductWorkerTimeoutError"
