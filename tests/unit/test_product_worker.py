from __future__ import annotations

from collections import deque
from collections.abc import Callable
from datetime import timezone
from threading import Event, Thread, current_thread
from typing import Any, cast

import pytest

import analog_validation_app.worker as worker_module
from analog_validation import EvidenceSource
from analog_validation import TestRunOutcome as RunOutcome
from analog_validation_app import (
    MAX_PRODUCT_CANCELLATION_WAIT_S,
    MAX_PRODUCT_EVENT_QUEUE_SIZE,
    MAX_PRODUCT_JOIN_TIMEOUT_S,
    ProductCancellationToken,
    ProductJobRequest,
    ProductJobResult,
    ProductJobType,
    ProductJobWorker,
    ProductRequestError,
    ProductResultStatus,
    ProductSourceMode,
    ProductWorkerBusyError,
    ProductWorkerClosedError,
    ProductWorkerContractError,
    ProductWorkerError,
    ProductWorkerState,
    ProductWorkerTimeoutError,
    UserIssueCode,
)


def make_request(
    job_id: str = "worker-job-001",
    *,
    source_mode: ProductSourceMode = ProductSourceMode.SIMULATOR,
) -> ProductJobRequest:
    return ProductJobRequest(
        job_id=job_id,
        source_mode=source_mode,
        job_type=ProductJobType.READ,
        profile_name="afe",
        profile_version="1",
    )


def make_result(
    request: ProductJobRequest,
    *,
    status: ProductResultStatus = ProductResultStatus.COMPLETED,
    outcome: RunOutcome | None = RunOutcome.PASS,
) -> ProductJobResult:
    evidence = {
        ProductSourceMode.SIMULATOR: EvidenceSource.SYNTHETIC,
        ProductSourceMode.CSV_REPLAY: EvidenceSource.CSV_REPLAY,
        ProductSourceMode.SERIAL_READ_ONLY: EvidenceSource.HOST_TEST,
    }[request.source_mode]
    return ProductJobResult(
        request=request,
        status=status,
        evidence_source=evidence,
        limitations=("Host-side worker test; no hardware was accessed.",),
        test_run_outcome=outcome,
    )


class RecordingService:
    def __init__(
        self,
        returned: object,
        *,
        progress: tuple[tuple[str, int | None, int | None], ...] = (),
        run_error: BaseException | None = None,
        cleanup_error: BaseException | None = None,
        on_run: Callable[[], None] | None = None,
    ) -> None:
        self.returned = returned
        self.progress = progress
        self.run_error = run_error
        self.cleanup_error_to_raise = cleanup_error
        self.on_run = on_run
        self.started = Event()
        self.cleaned = Event()
        self.run_count = 0
        self.cleanup_count = 0
        self.run_thread: Thread | None = None
        self.cleanup_thread: Thread | None = None

    def run(
        self,
        request: ProductJobRequest,
        cancellation: ProductCancellationToken,
        report_progress: Callable[[str, int | None, int | None], None],
    ) -> ProductJobResult:
        self.run_count += 1
        self.run_thread = current_thread()
        self.started.set()
        if self.on_run is not None:
            self.on_run()
        for message, completed, total in self.progress:
            report_progress(message, completed, total)
        if self.run_error is not None:
            raise self.run_error
        return cast(ProductJobResult, self.returned)

    def cleanup(self) -> None:
        self.cleanup_count += 1
        self.cleanup_thread = current_thread()
        self.cleaned.set()
        if self.cleanup_error_to_raise is not None:
            raise self.cleanup_error_to_raise


class BlockingService(RecordingService):
    def __init__(
        self,
        returned: ProductJobResult,
        *,
        cooperate: bool,
        cleanup_error: BaseException | None = None,
    ) -> None:
        super().__init__(returned, cleanup_error=cleanup_error)
        self.cooperate = cooperate
        self.release = Event()

    def run(
        self,
        request: ProductJobRequest,
        cancellation: ProductCancellationToken,
        report_progress: Callable[[str, int | None, int | None], None],
    ) -> ProductJobResult:
        self.run_count += 1
        self.run_thread = current_thread()
        self.started.set()
        while not self.release.wait(0.002):
            if self.cooperate:
                cancellation.raise_if_cancelled()
        if self.cooperate:
            cancellation.raise_if_cancelled()
        return cast(ProductJobResult, self.returned)


def wait_started(service: RecordingService) -> None:
    assert service.started.wait(2.0), "test service did not start"


def join_worker(worker: ProductJobWorker) -> None:
    assert worker.join(2.0), "worker did not stop"


@pytest.mark.parametrize("value", [None, object(), 1])
def test_worker_requires_a_callable_service_factory(value: object) -> None:
    with pytest.raises(ProductRequestError, match="service_factory"):
        ProductJobWorker(cast(Any, value))


@pytest.mark.parametrize("value", [True, "1", 0, MAX_PRODUCT_EVENT_QUEUE_SIZE + 1])
def test_worker_rejects_invalid_event_queue_bounds(value: object) -> None:
    with pytest.raises(ProductRequestError, match="max_events"):
        ProductJobWorker(
            lambda request: RecordingService(make_result(request)),
            max_events=cast(Any, value),
        )


@pytest.mark.parametrize(
    "value",
    [True, "1", 0, float("nan"), float("inf"), MAX_PRODUCT_JOIN_TIMEOUT_S + 1],
)
def test_worker_rejects_invalid_join_bounds(value: object) -> None:
    with pytest.raises(ProductRequestError, match="join timeout"):
        ProductJobWorker(
            lambda request: RecordingService(make_result(request)),
            join_timeout_s=cast(Any, value),
        )


def test_cancellation_token_exposes_only_bounded_cooperative_checks() -> None:
    token = ProductCancellationToken()

    assert token.is_cancellation_requested is False
    assert token.wait(0.0) is False
    token.raise_if_cancelled()
    for value in (
        True,
        "1",
        -0.1,
        float("nan"),
        MAX_PRODUCT_CANCELLATION_WAIT_S + 1,
    ):
        with pytest.raises(ProductRequestError, match="cancellation wait"):
            token.wait(cast(Any, value))


def test_idle_worker_snapshot_drain_join_and_close_are_safe() -> None:
    worker = ProductJobWorker(lambda request: RecordingService(make_result(request)))

    assert worker.state is ProductWorkerState.IDLE
    assert worker.is_active is False
    assert worker.is_closed is False
    assert worker.request is None
    assert worker.result is None
    assert worker.issue is None
    assert worker.last_error is None
    assert worker.cleanup_error is None
    assert worker.events == ()
    assert worker.drain_events() == ()
    assert worker.join() is True

    worker.close()
    worker.close()
    assert worker.is_closed is True
    with pytest.raises(ProductWorkerClosedError):
        worker.start(make_request())
    with pytest.raises(ProductWorkerClosedError), worker:
        pass


def test_start_requires_a_typed_product_request() -> None:
    worker = ProductJobWorker(lambda request: RecordingService(make_result(request)))

    with pytest.raises(ProductRequestError, match="ProductJobRequest"):
        worker.start(cast(Any, object()))


def test_normal_job_owns_one_thread_reports_progress_and_cleans_up() -> None:
    request = make_request()
    expected = make_result(request)
    service = RecordingService(
        expected,
        progress=(
            ("Read first bounded record.", 1, 2),
            ("Read second bounded record.", 2, 2),
        ),
    )
    worker = ProductJobWorker(lambda _request: service)

    worker.start(request)
    join_worker(worker)

    assert worker.state is ProductWorkerState.SUCCEEDED
    assert worker.is_active is False
    assert worker.request is request
    assert worker.result is expected
    assert worker.result.is_engineering_conclusion is True
    assert worker.issue is None
    assert worker.last_error is None
    assert worker.cleanup_error is None
    assert service.run_count == 1
    assert service.cleanup_count == 1
    assert service.cleaned.is_set()
    assert service.run_thread is service.cleanup_thread
    assert service.run_thread is not current_thread()
    assert service.run_thread is not None
    assert service.run_thread.name == "analog-validation-worker-job-001"
    assert service.run_thread.daemon is False
    assert service.run_thread.is_alive() is False

    events = worker.events
    assert [event.index for event in events] == [1, 2, 3, 4, 5]
    assert [event.state for event in events] == [
        ProductWorkerState.STARTING,
        ProductWorkerState.RUNNING,
        ProductWorkerState.RUNNING,
        ProductWorkerState.RUNNING,
        ProductWorkerState.SUCCEEDED,
    ]
    assert [(event.completed, event.total) for event in events[2:4]] == [
        (1, 2),
        (2, 2),
    ]
    assert all(event.job_id == request.job_id for event in events)
    assert all(event.created_at.tzinfo is timezone.utc for event in events)
    assert worker.drain_events() == events
    assert worker.events == ()


def test_duplicate_start_does_not_disturb_the_owned_job() -> None:
    first = make_request("first-job")
    second = make_request("second-job")
    service = BlockingService(make_result(first), cooperate=True)
    worker = ProductJobWorker(lambda _request: service)

    worker.start(first)
    wait_started(service)
    with pytest.raises(ProductWorkerBusyError, match="first-job"):
        worker.start(second)

    assert worker.request is first
    assert worker.request_cancel() is True
    assert worker.request_cancel() is False
    join_worker(worker)
    assert worker.state is ProductWorkerState.CANCELLED
    assert service.cleanup_count == 1


def test_cancel_during_factory_startup_skips_run_but_still_cleans_service() -> None:
    request = make_request()
    service = RecordingService(make_result(request))
    factory_entered = Event()
    factory_release = Event()

    def factory(_request: ProductJobRequest) -> RecordingService:
        factory_entered.set()
        assert factory_release.wait(2.0)
        return service

    worker = ProductJobWorker(factory)
    worker.start(request)
    assert factory_entered.wait(2.0)
    assert worker.state is ProductWorkerState.STARTING
    assert worker.request_cancel() is True
    factory_release.set()
    join_worker(worker)

    assert worker.state is ProductWorkerState.CANCELLED
    assert worker.result is None
    assert worker.issue is None
    assert service.run_count == 0
    assert service.cleanup_count == 1
    assert [event.state for event in worker.events] == [
        ProductWorkerState.STARTING,
        ProductWorkerState.CANCELLING,
        ProductWorkerState.CANCELLED,
    ]


def test_cooperative_cancel_during_run_releases_service_without_pass() -> None:
    request = make_request()
    service = BlockingService(make_result(request), cooperate=True)
    worker = ProductJobWorker(lambda _request: service)

    worker.start(request)
    wait_started(service)
    assert worker.request_cancel() is True
    join_worker(worker)

    assert worker.state is ProductWorkerState.CANCELLED
    assert worker.result is None
    assert service.cleanup_count == 1
    assert worker.events[-1].state is ProductWorkerState.CANCELLED


def test_service_can_wait_for_the_workers_cancellation_signal() -> None:
    request = make_request()
    observed: list[bool] = []

    class WaitingService(RecordingService):
        def run(
            self,
            request: ProductJobRequest,
            cancellation: ProductCancellationToken,
            report_progress: Callable[[str, int | None, int | None], None],
        ) -> ProductJobResult:
            self.started.set()
            observed.append(cancellation.wait(2.0))
            cancellation.raise_if_cancelled()
            return make_result(request)

    service = WaitingService(make_result(request))
    worker = ProductJobWorker(lambda _request: service)

    worker.start(request)
    wait_started(service)
    assert worker.request_cancel() is True
    join_worker(worker)

    assert observed == [True]
    assert worker.state is ProductWorkerState.CANCELLED
    assert service.cleanup_count == 1


def test_cancel_wins_completion_race_and_downgrades_a_pass_result() -> None:
    request = make_request()
    service = BlockingService(make_result(request), cooperate=False)
    worker = ProductJobWorker(lambda _request: service)

    worker.start(request)
    wait_started(service)
    assert worker.request_cancel() is True
    service.release.set()
    join_worker(worker)

    assert worker.state is ProductWorkerState.CANCELLED
    assert worker.result is not None
    assert worker.result.status is ProductResultStatus.CANCELLED
    assert worker.result.test_run_outcome is RunOutcome.ABORTED
    assert worker.result.is_engineering_conclusion is False
    assert service.cleanup_count == 1


def test_cancel_after_terminal_result_is_a_noop() -> None:
    request = make_request()
    service = RecordingService(make_result(request))
    worker = ProductJobWorker(lambda _request: service)

    worker.start(request)
    join_worker(worker)

    assert worker.request_cancel() is False
    assert worker.state is ProductWorkerState.SUCCEEDED
    assert worker.result is not None
    assert worker.result.test_run_outcome is RunOutcome.PASS


@pytest.mark.parametrize(
    ("status", "outcome", "worker_state", "has_issue"),
    [
        (
            ProductResultStatus.COMPLETED,
            RunOutcome.FAIL,
            ProductWorkerState.SUCCEEDED,
            False,
        ),
        (
            ProductResultStatus.INCOMPLETE,
            RunOutcome.INCOMPLETE,
            ProductWorkerState.SUCCEEDED,
            False,
        ),
        (
            ProductResultStatus.UNSUPPORTED,
            RunOutcome.UNSUPPORTED,
            ProductWorkerState.SUCCEEDED,
            False,
        ),
        (
            ProductResultStatus.CANCELLED,
            RunOutcome.ABORTED,
            ProductWorkerState.CANCELLED,
            False,
        ),
        (
            ProductResultStatus.ERROR,
            RunOutcome.ERROR,
            ProductWorkerState.FAILED,
            True,
        ),
    ],
)
def test_worker_state_remains_separate_from_product_result_meaning(
    status: ProductResultStatus,
    outcome: RunOutcome,
    worker_state: ProductWorkerState,
    has_issue: bool,
) -> None:
    request = make_request()
    result = make_result(request, status=status, outcome=outcome)
    worker = ProductJobWorker(lambda _request: RecordingService(result))

    worker.start(request)
    join_worker(worker)

    assert worker.state is worker_state
    assert worker.result is result
    assert (worker.issue is not None) is has_issue
    if has_issue:
        assert worker.issue is not None
        assert worker.issue.code is UserIssueCode.OPERATION_FAILED
        assert isinstance(worker.last_error, ProductWorkerError)


def test_factory_exception_is_captured_as_a_safe_failed_event() -> None:
    expected = ProductWorkerError("reviewed factory failed")

    def factory(_request: ProductJobRequest) -> RecordingService:
        raise expected

    worker = ProductJobWorker(factory)
    worker.start(make_request())
    join_worker(worker)

    assert worker.state is ProductWorkerState.FAILED
    assert worker.result is None
    assert worker.last_error is expected
    assert worker.cleanup_error is None
    assert worker.issue is not None
    assert worker.issue.code is UserIssueCode.OPERATION_FAILED
    assert worker.events[-1].issue is worker.issue


def test_factory_returning_a_nonservice_is_a_contract_failure() -> None:
    worker = ProductJobWorker(cast(Any, lambda _request: object()))

    worker.start(make_request())
    join_worker(worker)

    assert worker.state is ProductWorkerState.FAILED
    assert isinstance(worker.last_error, ProductWorkerContractError)
    assert worker.issue is not None
    assert worker.issue.code is UserIssueCode.OPERATION_FAILED


@pytest.mark.parametrize(
    ("error", "issue_code"),
    [
        (
            ProductWorkerError("expected execution failure"),
            UserIssueCode.OPERATION_FAILED,
        ),
        (RuntimeError("secret internal detail"), UserIssueCode.INTERNAL_ERROR),
    ],
)
def test_run_exception_is_captured_and_cleanup_always_runs(
    error: BaseException,
    issue_code: UserIssueCode,
) -> None:
    request = make_request()
    service = RecordingService(make_result(request), run_error=error)
    worker = ProductJobWorker(lambda _request: service)

    worker.start(request)
    join_worker(worker)

    assert worker.state is ProductWorkerState.FAILED
    assert worker.result is None
    assert worker.last_error is error
    assert worker.issue is not None
    assert worker.issue.code is issue_code
    if issue_code is UserIssueCode.INTERNAL_ERROR:
        assert "secret internal detail" not in worker.issue.what_happened
    assert service.cleanup_count == 1


@pytest.mark.parametrize("invalid_return", [None, object(), "result"])
def test_invalid_service_result_is_a_contract_failure(invalid_return: object) -> None:
    request = make_request()
    service = RecordingService(invalid_return)
    worker = ProductJobWorker(lambda _request: service)

    worker.start(request)
    join_worker(worker)

    assert worker.state is ProductWorkerState.FAILED
    assert worker.result is None
    assert isinstance(worker.last_error, ProductWorkerContractError)
    assert worker.issue is not None
    assert worker.issue.code is UserIssueCode.OPERATION_FAILED
    assert service.cleanup_count == 1


def test_result_for_a_different_request_is_rejected() -> None:
    owned = make_request("owned")
    other = make_request("other")
    service = RecordingService(make_result(other))
    worker = ProductJobWorker(lambda _request: service)

    worker.start(owned)
    join_worker(worker)

    assert worker.state is ProductWorkerState.FAILED
    assert worker.result is None
    assert isinstance(worker.last_error, ProductWorkerContractError)
    assert service.cleanup_count == 1


@pytest.mark.parametrize(
    "progress",
    [
        (("", None, None),),
        ((" padded ", None, None),),
        (("invalid counts", 2, 1),),
        (("missing total", 1, None),),
    ],
)
def test_invalid_progress_fails_the_job_and_cleans_up(
    progress: tuple[tuple[str, int | None, int | None], ...],
) -> None:
    request = make_request()
    service = RecordingService(make_result(request), progress=progress)
    worker = ProductJobWorker(lambda _request: service)

    worker.start(request)
    join_worker(worker)

    assert worker.state is ProductWorkerState.FAILED
    assert worker.result is None
    assert isinstance(worker.last_error, ProductRequestError)
    assert worker.issue is not None
    assert worker.issue.code is UserIssueCode.INVALID_REQUEST
    assert service.cleanup_count == 1


def test_foreign_thread_cannot_publish_progress_for_the_owned_job() -> None:
    request = make_request()
    captured: list[BaseException] = []

    class ForeignProgressService(RecordingService):
        def run(
            self,
            request: ProductJobRequest,
            cancellation: ProductCancellationToken,
            report_progress: Callable[[str, int | None, int | None], None],
        ) -> ProductJobResult:
            self.started.set()

            def publish() -> None:
                try:
                    report_progress("foreign progress", 1, 1)
                except BaseException as error:  # noqa: BLE001 - test captures boundary
                    captured.append(error)

            thread = Thread(target=publish)
            thread.start()
            thread.join(1.0)
            assert not thread.is_alive()
            raise captured[0]

    service = ForeignProgressService(make_result(request))
    worker = ProductJobWorker(lambda _request: service)

    worker.start(request)
    join_worker(worker)

    assert len(captured) == 1
    assert isinstance(captured[0], ProductWorkerContractError)
    assert worker.state is ProductWorkerState.FAILED
    assert service.cleanup_count == 1


@pytest.mark.parametrize("violation", ["identity", "state"])
def test_owned_thread_cannot_publish_progress_for_the_wrong_job_state(
    violation: str,
) -> None:
    request = make_request()
    holder: dict[str, ProductJobWorker] = {}

    class InvalidOwnershipService(RecordingService):
        def run(
            self,
            request: ProductJobRequest,
            cancellation: ProductCancellationToken,
            report_progress: Callable[[str, int | None, int | None], None],
        ) -> ProductJobResult:
            self.started.set()
            worker = holder["worker"]
            if violation == "identity":
                cast(Any, worker)._report_progress(
                    make_request("wrong-job"),
                    cancellation,
                    "Wrong identity.",
                    None,
                    None,
                )
            else:
                cast(Any, worker)._state = ProductWorkerState.CANCELLING
                cast(Any, worker)._report_progress(
                    request,
                    cancellation,
                    "Wrong state.",
                    None,
                    None,
                )
            return make_result(request)

    service = InvalidOwnershipService(make_result(request))
    worker = ProductJobWorker(lambda _request: service)
    holder["worker"] = worker

    worker.start(request)
    join_worker(worker)

    assert worker.state is ProductWorkerState.FAILED
    assert isinstance(worker.last_error, ProductWorkerContractError)
    assert service.cleanup_count == 1


def test_cleanup_failure_overrides_pass_and_preserves_developer_details() -> None:
    request = make_request()
    cleanup_error = RuntimeError("resource did not close")
    service = RecordingService(
        make_result(request),
        cleanup_error=cleanup_error,
    )
    worker = ProductJobWorker(lambda _request: service)

    worker.start(request)
    join_worker(worker)

    assert worker.state is ProductWorkerState.FAILED
    assert worker.result is not None
    assert worker.result.status is ProductResultStatus.ERROR
    assert worker.result.test_run_outcome is RunOutcome.ERROR
    assert worker.result.is_engineering_conclusion is False
    assert worker.cleanup_error is cleanup_error
    assert worker.issue is not None
    assert worker.issue.code is UserIssueCode.INTERNAL_ERROR
    assert worker.events[-1].state is ProductWorkerState.FAILED


def test_cleanup_failure_overrides_cancellation_and_primary_run_error() -> None:
    request = make_request()
    run_error = ProductWorkerError("primary run failure")
    cleanup_error = ProductWorkerError("cleanup failure")
    service = RecordingService(
        make_result(request),
        run_error=run_error,
        cleanup_error=cleanup_error,
    )
    worker = ProductJobWorker(lambda _request: service)

    worker.start(request)
    wait_started(service)
    worker.request_cancel()
    join_worker(worker)

    assert worker.state is ProductWorkerState.FAILED
    assert worker.last_error is run_error
    assert worker.cleanup_error is cleanup_error
    assert worker.issue is not None
    assert worker.issue.what_happened == "cleanup failure"
    assert service.cleanup_count == 1


def test_bounded_queue_drops_oldest_events_but_keeps_global_monotonic_ids() -> None:
    first_request = make_request("first")
    first_service = RecordingService(
        make_result(first_request),
        progress=tuple((f"Progress {index}.", index, 10) for index in range(1, 11)),
    )
    second_request = make_request("second")
    second_service = RecordingService(make_result(second_request))
    services = deque([first_service, second_service])
    worker = ProductJobWorker(lambda _request: services.popleft(), max_events=3)

    worker.start(first_request)
    join_worker(worker)

    assert [event.index for event in worker.events] == [11, 12, 13]
    assert worker.events[-1].state is ProductWorkerState.SUCCEEDED
    assert worker.dropped_event_count == 10
    assert len(worker.drain_events()) == 3

    worker.start(second_request)
    join_worker(worker)

    assert [event.index for event in worker.events] == [14, 15, 16]
    assert worker.dropped_event_count == 10


def test_bounded_join_timeout_reports_failure_then_allows_safe_recovery() -> None:
    request = make_request()
    service = BlockingService(make_result(request), cooperate=False)
    worker = ProductJobWorker(lambda _request: service, join_timeout_s=0.01)

    worker.start(request)
    wait_started(service)
    assert worker.join() is False
    with pytest.raises(ProductWorkerTimeoutError, match="join timeout"):
        worker.cancel_and_join()
    assert worker.state is ProductWorkerState.CANCELLING
    assert worker.is_active is True

    service.release.set()
    join_worker(worker)
    assert worker.state is ProductWorkerState.CANCELLED
    assert service.cleanup_count == 1
    worker.close()


def test_join_fails_closed_when_its_deadline_is_already_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = make_request()
    service = BlockingService(make_result(request), cooperate=False)
    worker = ProductJobWorker(lambda _request: service)

    worker.start(request)
    wait_started(service)
    original_monotonic = worker_module.monotonic
    values = iter((0.0, 1.0))
    monkeypatch.setattr(worker_module, "monotonic", lambda: next(values))
    assert worker.join(0.1) is False
    monkeypatch.setattr(worker_module, "monotonic", original_monotonic)

    worker.request_cancel()
    service.release.set()
    join_worker(worker)
    assert service.cleanup_count == 1


def test_close_timeout_prevents_reuse_and_can_be_completed_later() -> None:
    request = make_request()
    service = BlockingService(make_result(request), cooperate=False)
    worker = ProductJobWorker(lambda _request: service)

    worker.start(request)
    wait_started(service)
    with pytest.raises(ProductWorkerTimeoutError):
        worker.close(0.01)

    assert worker.is_closed is True
    with pytest.raises(ProductWorkerClosedError):
        worker.start(make_request("new"))
    service.release.set()
    join_worker(worker)
    worker.close()
    assert worker.state is ProductWorkerState.CANCELLED


def test_context_manager_cancels_joins_and_cleans_before_scope_exit() -> None:
    request = make_request()
    service = BlockingService(make_result(request), cooperate=True)
    worker = ProductJobWorker(lambda _request: service)

    with worker as owned:
        assert owned is worker
        worker.start(request)
        wait_started(service)

    assert worker.is_closed is True
    assert worker.state is ProductWorkerState.CANCELLED
    assert worker.is_active is False
    assert service.cleanup_count == 1
    assert not cast(Thread, service.run_thread).is_alive()


@pytest.mark.parametrize("operation", ["join", "close"])
def test_worker_thread_cannot_join_or_close_its_own_owner(operation: str) -> None:
    request = make_request()
    holder: dict[str, ProductJobWorker] = {}

    def action() -> None:
        worker = holder["worker"]
        if operation == "join":
            worker.join()
        else:
            worker.close()

    service = RecordingService(make_result(request), on_run=action)
    worker = ProductJobWorker(lambda _request: service)
    holder["worker"] = worker

    worker.start(request)
    join_worker(worker)

    assert worker.state is ProductWorkerState.FAILED
    assert isinstance(worker.last_error, ProductWorkerContractError)
    assert service.cleanup_count == 1


def test_thread_start_failure_is_terminal_visible_and_does_not_own_a_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_thread(*args: object, **kwargs: object) -> Thread:
        raise RuntimeError("thread unavailable")

    monkeypatch.setattr(worker_module, "Thread", fail_thread)
    worker = ProductJobWorker(lambda request: RecordingService(make_result(request)))

    with pytest.raises(ProductWorkerError, match="could not start"):
        worker.start(make_request())

    assert worker.state is ProductWorkerState.FAILED
    assert worker.is_active is False
    assert isinstance(worker.last_error, RuntimeError)
    assert worker.issue is not None
    assert worker.issue.code is UserIssueCode.OPERATION_FAILED
    assert [event.state for event in worker.events] == [
        ProductWorkerState.STARTING,
        ProductWorkerState.FAILED,
    ]
    assert worker.join() is True


def test_defensive_missing_token_is_a_contract_failure() -> None:
    request = make_request()
    service = BlockingService(make_result(request), cooperate=False)
    worker = ProductJobWorker(lambda _request: service)

    worker.start(request)
    wait_started(service)
    owned_token = cast(ProductCancellationToken, cast(Any, worker)._cancellation)
    cast(Any, worker)._cancellation = None
    with pytest.raises(ProductWorkerContractError, match="missing"):
        worker.request_cancel()
    cast(Any, worker)._cancellation = owned_token
    owned_token._request()
    service.release.set()
    join_worker(worker)


def test_defensive_missing_completion_event_is_a_contract_failure() -> None:
    request = make_request()
    service = BlockingService(make_result(request), cooperate=True)
    worker = ProductJobWorker(lambda _request: service)

    worker.start(request)
    wait_started(service)
    owned_completion = cast(Event, cast(Any, worker)._completion)
    cast(Any, worker)._completion = None
    with pytest.raises(ProductWorkerContractError, match="completion event"):
        worker.join()
    cast(Any, worker)._completion = owned_completion
    worker.request_cancel()
    join_worker(worker)


def test_defensive_event_and_stale_completion_guards_are_fail_closed() -> None:
    worker = ProductJobWorker(lambda request: RecordingService(make_result(request)))
    with pytest.raises(ProductWorkerContractError, match="owned request"):
        cast(Any, worker)._publish_locked("No request exists.")

    stale_request = make_request("stale")
    stale_token = ProductCancellationToken()
    cast(Any, worker)._finish_job(
        stale_request,
        stale_token,
        None,
        None,
        None,
    )
    assert worker.state is ProductWorkerState.IDLE


def test_defensive_missing_result_is_published_as_a_failed_contract() -> None:
    worker = ProductJobWorker(lambda request: RecordingService(make_result(request)))
    request = make_request()
    token = ProductCancellationToken()
    cast(Any, worker)._request = request
    cast(Any, worker)._cancellation = token
    cast(Any, worker)._state = ProductWorkerState.RUNNING

    cast(Any, worker)._finish_job(request, token, None, None, None)

    assert worker.state is ProductWorkerState.FAILED
    assert isinstance(worker.last_error, ProductWorkerContractError)
    assert worker.issue is not None
    assert worker.events[-1].state is ProductWorkerState.FAILED
