from __future__ import annotations

import subprocess
import sys
from threading import Event

from analog_validation_app import (
    ProductCancellationToken,
    ProductJobRequest,
    ProductJobResult,
    ProductJobType,
    ProductJobWorker,
    ProductProgressReporter,
    ProductSourceMode,
    ProductWorkerState,
)
from analog_validation_app.dashboard import (
    DASHBOARD_HARDWARE_CLAIM,
    DashboardController,
    DashboardPresenter,
)


class CooperativeService:
    def __init__(self) -> None:
        self.started = Event()
        self.cleaned = Event()

    def run(
        self,
        request: ProductJobRequest,
        cancellation: ProductCancellationToken,
        report_progress: ProductProgressReporter,
    ) -> ProductJobResult:
        self.started.set()
        report_progress("Waiting for a bounded cancellation test.", 0, 1)
        while not cancellation.wait(0.01):
            pass
        cancellation.raise_if_cancelled()
        raise AssertionError("cancelled service cannot return a result")

    def cleanup(self) -> None:
        self.cleaned.set()


def test_headless_dashboard_import_does_not_load_tk_or_serial() -> None:
    code = """
import sys
import analog_validation_app
import analog_validation_app.dashboard
assert 'tkinter' not in sys.modules
assert 'serial' not in sys.modules
print('headless-dashboard-import=PASS')
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "headless-dashboard-import=PASS"


def test_window_close_controller_cancels_joins_and_cleans_actual_worker() -> None:
    service = CooperativeService()
    selected = ProductJobRequest(
        "dashboard-close-job",
        ProductSourceMode.SIMULATOR,
        ProductJobType.READ,
        "afe",
        "1",
    )
    worker = ProductJobWorker(lambda request: service, join_timeout_s=2.0)
    worker.start(selected)
    assert service.started.wait(2.0)
    controller = DashboardController(DashboardPresenter(), worker)

    controller.poll()
    assert controller.state.progress.worker_state is ProductWorkerState.RUNNING
    assert controller.request_close(2.0) is True

    assert service.cleaned.wait(2.0)
    assert worker.state is ProductWorkerState.CANCELLED
    assert worker.is_closed is True
    assert controller.is_closed is True
    assert controller.state.progress.worker_state is ProductWorkerState.CANCELLED
    assert controller.state.close_requested is True
    assert controller.state.hardware_claim == DASHBOARD_HARDWARE_CLAIM
