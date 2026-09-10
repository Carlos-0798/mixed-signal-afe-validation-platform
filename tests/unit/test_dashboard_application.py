from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic, sleep
from typing import Any, cast

import pytest

import analog_validation_app.dashboard.application as application_module
from analog_validation.protocol.msp430_health_v1 import (
    MSP430_HEALTH_CHANNEL_BUS_VOLTAGE,
    Msp430DeviceState,
    Msp430Telemetry,
    encode_msp430_message,
)
from analog_validation.transport import SerialPortInfo
from analog_validation_app import (
    DashboardApplication,
    DashboardWizardDraft,
    DashboardWizardStep,
    PreparedProductJob,
    ProductAppError,
    ProductCancellationToken,
    ProductJobRequest,
    ProductJobResult,
    ProductJobType,
    ProductProgressReporter,
    ProductRequestError,
    ProductServiceOutputSlot,
    ProductSourceMode,
    ProductWorkerClosedError,
    ProductWorkerState,
    ProductWorkflowConfiguration,
    ReviewedServiceRouter,
    prepare_product_job,
)
from tests.support import MemorySerialBackend

ROOT = Path(__file__).resolve().parents[2]


class WriteTrapBackend(MemorySerialBackend):
    def __init__(self, record: bytes = b"") -> None:
        super().__init__(ports=(SerialPortInfo("MEMORY:1", "Memory port"),))
        if record:
            self.read_actions.append(record)
        self.write_calls: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.write_calls.append(data)
        raise AssertionError("Dashboard receive-only path attempted a write")


class IdleWorker:
    state = ProductWorkerState.IDLE
    request = None
    result = None
    issue = None
    dropped_event_count = 0

    @property
    def is_active(self) -> bool:
        return False

    def drain_events(self) -> tuple[object, ...]:
        return ()

    def request_cancel(self) -> bool:
        return False

    def close(self, timeout_s: float | None = None) -> None:
        return None


class FalsyIdleWorker(IdleWorker):
    def __bool__(self) -> bool:
        return False


class RejectingWorker(IdleWorker):
    def start(self, request: ProductJobRequest) -> None:
        raise ProductWorkerClosedError("worker is closed")


class BlockingService:
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
        report_progress("Waiting for cancellation.", 0, 1)
        while not cancellation.wait(0.01):
            pass
        cancellation.raise_if_cancelled()
        raise AssertionError("cancelled service cannot return")

    def cleanup(self) -> None:
        self.cleaned.set()


def advance_to_configuration(
    application: DashboardApplication,
    job_type: ProductJobType = ProductJobType.READ,
) -> DashboardWizardDraft:
    assert application.next()
    if job_type is not ProductJobType.READ:
        assert application.select_job(job_type)
    assert application.next()
    assert application.wizard_state.step is DashboardWizardStep.CONFIGURATION
    return application.wizard_state.draft


def wait_for_result(application: DashboardApplication) -> None:
    deadline = monotonic() + 5.0
    while monotonic() < deadline:
        application.poll()
        if application.wizard_state.step is DashboardWizardStep.RESULT:
            return
        sleep(0.001)
    raise AssertionError("Dashboard job did not reach RESULT")


def ready_dc_application() -> DashboardApplication:
    application = DashboardApplication(job_id_factory=lambda: "dashboard-dc")
    draft = advance_to_configuration(application, ProductJobType.DC_ANALYSIS)
    assert application.prepare_review(replace(draft, sample_count="24"))
    assert application.run()
    wait_for_result(application)
    return application


def test_live_monitor_dashboard_chain_copies_bounded_points_without_analysis() -> None:
    application = DashboardApplication(job_id_factory=lambda: "dashboard-live")
    draft = advance_to_configuration(application, ProductJobType.LIVE_MONITOR)
    configured = replace(
        draft,
        sample_count="4",
        monitor_sample_interval_seconds="0",
        monitor_time_window_seconds="5",
        monitor_max_buffer_points="5",
    )
    assert application.prepare_review(configured)
    assert application.dashboard_state.live.total_points == 0
    assert application.run()
    wait_for_result(application)

    state = application.dashboard_state
    assert state.progress.worker_state is ProductWorkerState.SUCCEEDED
    assert state.live.active is False
    assert state.live.total_points == 12
    assert state.live.retained_points == 5
    assert state.live.evicted_points == 7
    assert state.live.valid_points == 12
    assert len(state.live.points) <= 5
    assert state.plot.total_points == 12
    assert state.result.outcome is None
    assert state.result.evidence_source is not None
    assert state.result.evidence_source.value == "SYNTHETIC"
    assert application.set_live_time_window(0.5)
    assert application.dashboard_state.live.time_window_seconds == 0.5
    assert application.set_live_time_window(0.0) is False
    assert application.wizard_state.issue is not None
    assert application.request_close()


def test_live_monitor_dashboard_pause_resume_stops_at_safe_checkpoint() -> None:
    application = DashboardApplication(job_id_factory=lambda: "dashboard-live-pause")
    draft = advance_to_configuration(application, ProductJobType.LIVE_MONITOR)
    configured = replace(
        draft,
        sample_count="40",
        monitor_sample_interval_seconds="0.01",
        monitor_time_window_seconds="5",
        monitor_max_buffer_points="200",
    )
    assert application.prepare_review(configured)
    assert application.run()

    deadline = monotonic() + 2.0
    while monotonic() < deadline:
        application.poll()
        if application.dashboard_state.live.total_points >= 3:
            break
        sleep(0.001)
    else:
        raise AssertionError("live monitor did not publish an initial cycle")
    assert application.pause_live_monitor()
    assert application.dashboard_state.live.paused is True
    assert application.set_live_time_window(1.0)
    sleep(0.08)
    application.poll()
    stable_total = application.dashboard_state.live.total_points
    sleep(0.08)
    application.poll()
    assert application.dashboard_state.live.total_points == stable_total
    assert application.dashboard_state.live.pause_count == 1
    assert application.resume_live_monitor()
    wait_for_result(application)
    assert application.dashboard_state.live.total_points == 120
    assert application.dashboard_state.live.paused is False
    assert application.dashboard_state.live.pause_count == 1
    assert application.request_close()


def test_live_controls_fail_closed_without_an_active_review_and_reset_resumes() -> None:
    application = DashboardApplication(job_id_factory=lambda: "dashboard-live-guard")

    assert application.pause_live_monitor() is False
    assert application.wizard_state.issue is not None

    draft = advance_to_configuration(application, ProductJobType.LIVE_MONITOR)
    assert application.prepare_review(
        replace(
            draft,
            sample_count="2",
            monitor_sample_interval_seconds="0",
        )
    )
    assert application.resume_live_monitor() is False
    assert application.wizard_state.issue is not None

    prepared = cast(PreparedProductJob, application._prepared)
    session = prepared.live_monitor_session
    assert session is not None
    assert session.pause()
    assert application.back()
    assert session.is_paused is False
    assert application.request_close()


def test_reviewed_service_router_accepts_only_one_exact_prepared_request() -> None:
    router = ReviewedServiceRouter()
    assert router.prepared is None
    with pytest.raises(ProductRequestError, match="ProductJobRequest"):
        router(cast(Any, object()))
    with pytest.raises(ProductRequestError, match="PreparedProductJob"):
        router.register(cast(Any, object()))

    config = ProductWorkflowConfiguration(
        ProductSourceMode.SIMULATOR, ProductJobType.READ
    )
    prepared = prepare_product_job(config, "router-job")
    router.register(prepared)
    assert router.prepared is prepared
    assert router(prepared.request) is not None
    mismatch = replace(prepared.request, job_id="other-job")
    with pytest.raises(ProductAppError, match="does not match"):
        router(mismatch)
    router.clear()
    with pytest.raises(ProductAppError, match="no reviewed"):
        router(prepared.request)


def test_application_validates_dependencies_and_exposes_initial_state() -> None:
    assert application_module._new_dashboard_job_id().startswith("dashboard-")
    with pytest.raises(ProductRequestError, match="serial_backend_factory"):
        DashboardApplication(serial_backend_factory=cast(Any, object()))
    with pytest.raises(ProductRequestError, match="job_id_factory"):
        DashboardApplication(job_id_factory=cast(Any, object()))

    application = DashboardApplication()
    assert application.dashboard_state.source.source_mode is ProductSourceMode.SIMULATOR
    assert application.wizard_state.step is DashboardWizardStep.SOURCE
    assert application.has_unsaved_result is False
    assert application.is_closed is False
    assert application.request_cancel() is False
    with pytest.raises(ProductRequestError, match="BaseException"):
        application.present_input_error(cast(Any, object()))
    assert application.present_input_error(ProductRequestError("bad form")) is False
    assert application.wizard_state.issue is not None
    assert application.request_close() is True
    assert application.is_closed is True


def test_application_selection_navigation_and_error_mapping_are_headless() -> None:
    application = DashboardApplication(job_id_factory=lambda: "selection-job")
    assert application.select_source(ProductSourceMode.CSV_REPLAY)
    assert application.select_profile("afe", "1")
    assert application.next()
    assert application.select_job(ProductJobType.HYSTERESIS_ANALYSIS)
    assert application.next()
    assert application.select_source(ProductSourceMode.SIMULATOR) is False
    assert application.select_profile("afe", "1") is False
    assert application.select_job(ProductJobType.READ) is False
    assert application.next() is False
    assert application.wizard_state.issue is not None
    assert application.back()
    assert application.wizard_state.step is DashboardWizardStep.TEST
    assert application.back()
    assert application.wizard_state.step is DashboardWizardStep.SOURCE
    assert application.back() is False
    assert application.request_close()


def test_back_from_review_discards_only_the_prepared_run() -> None:
    application = DashboardApplication(job_id_factory=lambda: "review-back")
    draft = advance_to_configuration(application)
    assert application.prepare_review(draft)
    assert application.wizard_state.step is DashboardWizardStep.REVIEW
    assert application.dashboard_state.configuration.can_run is True

    assert application.back()

    assert application.wizard_state.step is DashboardWizardStep.CONFIGURATION
    assert application.dashboard_state.configuration.can_run is False
    assert application.dashboard_state.active_job_id is None
    assert application.request_close()


def test_simulator_read_runs_to_result_without_inventing_an_analysis_export() -> None:
    application = DashboardApplication(job_id_factory=lambda: "dashboard-read")
    draft = advance_to_configuration(application)
    assert application.prepare_review(draft)
    assert application.dashboard_state.configuration.can_run is True
    assert "NOT CLAIMED" in application.dashboard_state.configuration.safety_review
    assert application.run()
    wait_for_result(application)
    application.poll()

    assert (
        application.dashboard_state.progress.worker_state
        is ProductWorkerState.SUCCEEDED
    )
    assert application.wizard_state.export_available is False
    assert application.dashboard_state.plot.title == "Read observations"
    assert len(application.dashboard_state.plot.points) == 5
    assert application.dashboard_state.plot.points[0].values[0] == "value=800 mV"
    assert "PASS or FAIL" in application.dashboard_state.plot.summary
    assert "Capability identity: simulator-afe-1 (afe/1)" in (
        application.dashboard_state.plot.summary
    )
    assert "not a physical serial-number claim" in (
        application.dashboard_state.plot.summary
    )
    assert application.export_result("result.json", "json") is False
    assert application.back()
    assert application.dashboard_state.active_job_id is None
    assert application.request_close()


def test_result_navigation_preserves_reference_but_never_resurrects_worker_state() -> (
    None
):
    application = DashboardApplication(job_id_factory=lambda: "dashboard-reference")
    draft = advance_to_configuration(application)
    assert application.prepare_review(draft)
    assert application.run()
    wait_for_result(application)
    completed_plot = application.dashboard_state.plot
    completed_result = application.dashboard_state.result

    assert application.modify_setup()
    assert application.wizard_state.step is DashboardWizardStep.CONFIGURATION
    assert application.dashboard_state.active_job_id is None
    assert application.dashboard_state.plot == completed_plot
    assert application.dashboard_state.result == completed_result
    assert application.dashboard_state.progress.worker_state is ProductWorkerState.IDLE

    for _ in range(3):
        application.poll()
    assert application.dashboard_state.active_job_id is None
    assert application.dashboard_state.plot == completed_plot
    assert application.dashboard_state.result == completed_result
    assert application.request_close()


def test_result_actions_review_same_setup_and_start_a_clean_new_test() -> None:
    job_ids = iter(("dashboard-first", "dashboard-repeat"))
    application = DashboardApplication(job_id_factory=lambda: next(job_ids))
    draft = advance_to_configuration(application)
    assert application.prepare_review(draft)
    assert application.run()
    wait_for_result(application)

    assert application.review_same_setup()
    assert application.wizard_state.step is DashboardWizardStep.REVIEW
    assert application.wizard_state.can_run is True
    assert application.dashboard_state.plot.points == ()
    assert application.run()
    wait_for_result(application)

    assert application.start_new_test()
    assert application.wizard_state.step is DashboardWizardStep.SOURCE
    assert application.wizard_state.draft == DashboardWizardDraft()
    assert application.dashboard_state.result.status is None
    assert application.dashboard_state.plot.points == ()
    assert application.modify_setup() is False
    assert application.review_same_setup() is False
    assert application.start_new_test() is False
    assert application.request_close()


def test_simulator_dc_runs_shared_analysis_and_exports_json_csv_without_overwrite(
    tmp_path: Path,
) -> None:
    application = ready_dc_application()
    assert application.dashboard_state.result.outcome is not None
    assert application.dashboard_state.plot.points
    assert application.has_unsaved_result is True

    json_path = tmp_path / "dc-result.json"
    csv_path = tmp_path / "dc-result.csv"
    assert application.export_result(str(json_path), "json")
    assert application.has_unsaved_result is False
    assert json_path.is_file()
    assert application.dashboard_state.artifacts.artifacts[0].name == json_path.name
    assert application.export_result(str(csv_path), "csv")
    assert csv_path.is_file()
    assert application.export_result(str(json_path), "json") is False
    assert application.wizard_state.issue is not None
    assert application.request_close()


@pytest.mark.parametrize(
    ("path_text", "format_name"),
    [
        ("", "json"),
        (" result.json", "json"),
        ("result.json", "yaml"),
        ("result.csv", "json"),
        ("result.json", "csv"),
        ("result", "json"),
    ],
)
def test_export_rejects_missing_ambiguous_or_unknown_destination(
    tmp_path: Path,
    path_text: str,
    format_name: str,
) -> None:
    application = ready_dc_application()
    selected = path_text if not path_text else str(tmp_path / path_text)
    if path_text.startswith(" "):
        selected = f" {tmp_path / path_text.strip()}"
    assert application.export_result(selected, format_name) is False
    assert application.wizard_state.issue is not None
    assert application.request_close()


def test_replay_is_rejected_during_review_before_worker_start(tmp_path: Path) -> None:
    application = DashboardApplication(job_id_factory=lambda: "missing-replay")
    assert application.select_source(ProductSourceMode.CSV_REPLAY)
    draft = advance_to_configuration(application)
    missing = replace(draft, replay_path=str(tmp_path / "missing.csv"))

    assert application.prepare_review(missing) is False
    assert application.dashboard_state.progress.worker_state is ProductWorkerState.IDLE
    assert application.wizard_state.step is DashboardWizardStep.CONFIGURATION
    assert application.issue_field_id == "replay_path"
    assert application.run() is False
    assert application.issue_field_id is None
    assert application.request_close()


def test_review_error_exposes_and_then_clears_an_internal_field_hint() -> None:
    application = DashboardApplication(job_id_factory=lambda: "field-hint")
    draft = advance_to_configuration(application)

    assert application.prepare_review(replace(draft, sample_count="many")) is False
    assert application.wizard_state.issue is not None
    assert application.issue_field_id == "sample_count"

    assert application.prepare_review(replace(draft, sample_count="2"))
    assert application.wizard_state.issue is None
    assert application.issue_field_id is None
    assert application.request_close()


def test_explicit_serial_discovery_closes_backend_without_opening_port() -> None:
    backend = WriteTrapBackend()
    application = DashboardApplication(
        serial_backend_factory=lambda: backend,
        job_id_factory=lambda: "serial-discovery",
    )
    assert application.discover_ports() is False
    assert backend.discover_calls == 0
    assert application.select_source(ProductSourceMode.SERIAL_READ_ONLY)
    assert application.discover_ports()
    assert application.wizard_state.discovered_ports[0].port_id == "MEMORY:1"
    assert backend.discover_calls == 1
    assert backend.open_calls == []
    assert backend.close_calls == 1
    assert backend.write_calls == []
    assert application.request_close()


def test_dashboard_msp430_receive_only_chain_has_zero_write_surface() -> None:
    record = encode_msp430_message(
        Msp430Telemetry(
            0,
            1000,
            421,
            418,
            5012,
            186,
            932,
            650,
            Msp430DeviceState.COOLING_HIGH,
            0,
        )
    ).encode("ascii")
    backend = WriteTrapBackend(record)
    application = DashboardApplication(
        serial_backend_factory=lambda: backend,
        job_id_factory=lambda: "dashboard-msp430",
    )
    assert application.select_source(ProductSourceMode.SERIAL_READ_ONLY)
    assert application.select_profile("msp430-equipment-health", "1")
    draft = advance_to_configuration(application)
    configured = replace(
        draft,
        primary_channel=MSP430_HEALTH_CHANNEL_BUS_VOLTAGE,
        sample_count="1",
        serial_port="MEMORY:1",
        serial_confirm_read_only=True,
    )
    assert application.prepare_review(configured)
    assert backend.open_calls == []
    assert application.run()
    wait_for_result(application)

    assert application.dashboard_state.result.evidence_source is not None
    assert len(backend.open_calls) == 1
    assert backend.close_calls == 1
    assert backend.write_calls == []
    assert application.request_close()


def test_dashboard_serial_live_monitor_chain_is_finite_and_receive_only() -> None:
    backend = WriteTrapBackend()
    for sequence, bus_mv in ((0, 5012), (1, 5024)):
        backend.read_actions.append(
            encode_msp430_message(
                Msp430Telemetry(
                    sequence,
                    sequence * 1000,
                    421,
                    418,
                    bus_mv,
                    186,
                    932,
                    650,
                    Msp430DeviceState.COOLING_HIGH,
                    0,
                )
            ).encode("ascii")
        )
    application = DashboardApplication(
        serial_backend_factory=lambda: backend,
        job_id_factory=lambda: "dashboard-serial-live",
    )
    assert application.select_source(ProductSourceMode.SERIAL_READ_ONLY)
    assert application.select_profile("msp430-equipment-health", "1")
    draft = advance_to_configuration(application, ProductJobType.LIVE_MONITOR)
    configured = replace(
        draft,
        primary_channel=MSP430_HEALTH_CHANNEL_BUS_VOLTAGE,
        sample_count="2",
        monitor_sample_interval_seconds="0",
        serial_port="MEMORY:1",
        serial_confirm_read_only=True,
    )

    assert application.prepare_review(configured)
    assert any(
        "Worst-case serial receive wait budget" in line
        for line in application.wizard_state.review_lines
    )
    assert backend.open_calls == []
    assert application.run()
    wait_for_result(application)

    state = application.dashboard_state
    assert state.progress.worker_state is ProductWorkerState.SUCCEEDED
    assert state.live.total_points == 2
    assert [point.value for point in state.live.points] == [5012.0, 5024.0]
    assert state.result.evidence_source is not None
    assert state.result.evidence_source.value == "HOST_TEST"
    assert len(backend.open_calls) == 1
    assert backend.close_calls == 1
    assert backend.write_calls == []
    assert application.request_close()


def test_cancelled_dashboard_job_cleans_worker_and_never_creates_export(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = BlockingService()

    def prepare(
        config: ProductWorkflowConfiguration,
        job_id: str,
        **_kwargs: object,
    ) -> PreparedProductJob:
        request = ProductJobRequest(
            job_id,
            config.source_mode,
            config.job_type,
            config.profile_name,
            config.profile_version,
        )
        return PreparedProductJob(
            request,
            lambda _request: service,
            ProductServiceOutputSlot(),
            ("Synthetic cancellation test.",),
        )

    monkeypatch.setattr(application_module, "prepare_product_job", prepare)
    application = DashboardApplication(job_id_factory=lambda: "cancel-job")
    draft = advance_to_configuration(application)
    assert application.prepare_review(draft)
    assert application.run()
    assert service.started.wait(2.0)
    assert application.request_cancel()
    wait_for_result(application)

    assert service.cleaned.wait(2.0)
    assert (
        application.dashboard_state.progress.worker_state
        is ProductWorkerState.CANCELLED
    )
    assert application.wizard_state.export_available is False
    assert application.request_close()


def test_unstartable_and_rejecting_workers_become_structured_issues() -> None:
    unstartable = DashboardApplication(
        worker=cast(Any, FalsyIdleWorker()), job_id_factory=lambda: "unstartable"
    )
    draft = advance_to_configuration(unstartable)
    assert unstartable.prepare_review(draft)
    assert unstartable.run() is False
    assert unstartable.wizard_state.issue is not None
    assert unstartable.request_close()

    rejecting = DashboardApplication(
        worker=cast(Any, RejectingWorker()), job_id_factory=lambda: "rejecting"
    )
    draft = advance_to_configuration(rejecting)
    assert rejecting.prepare_review(draft)
    assert rejecting.run() is False
    assert rejecting.wizard_state.issue is not None
    assert rejecting.request_close()
