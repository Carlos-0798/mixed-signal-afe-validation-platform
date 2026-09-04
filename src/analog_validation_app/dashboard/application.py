"""Headless application coordinator for the reviewed Dashboard workflow."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path
from threading import RLock
from uuid import uuid4

from analog_validation.exports import (
    ResultExportBundle,
    write_result_export_csv,
    write_result_export_json,
)

from ..errors import ProductRequestError, ProductServiceError
from ..factories import (
    SerialBackendFactory,
    default_serial_backend_factory,
    discover_serial_ports,
)
from ..issues import UserIssue, issue_from_exception
from ..models import ProductJobRequest, ProductJobType, ProductSourceMode
from ..presentation import HumanReportView, build_human_report_view
from ..product_workflows import PreparedProductJob, prepare_product_job
from ..reporting import HumanReportPublication, ReportArtifact
from ..worker import ProductJobService, ProductJobWorker
from .controller import DashboardController, DashboardWorkerPort
from .presenter import DashboardPresenter
from .state import DashboardAction, DashboardActionType, DashboardState
from .wizard import (
    DashboardExportFormat,
    DashboardWizardDraft,
    DashboardWizardPresenter,
    DashboardWizardState,
    DashboardWizardStep,
)

DashboardJobIdFactory = Callable[[], str]


def _new_dashboard_job_id() -> str:
    return f"dashboard-{uuid4()}"


class ReviewedServiceRouter:
    """Thread-safe handoff from one reviewed UI job to the generic worker."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._prepared: PreparedProductJob | None = None

    @property
    def prepared(self) -> PreparedProductJob | None:
        with self._lock:
            return self._prepared

    def register(self, prepared: PreparedProductJob) -> None:
        if not isinstance(prepared, PreparedProductJob):
            raise ProductRequestError("prepared must be a PreparedProductJob")
        with self._lock:
            self._prepared = prepared

    def clear(self) -> None:
        with self._lock:
            self._prepared = None

    def __call__(self, request: ProductJobRequest) -> ProductJobService:
        if not isinstance(request, ProductJobRequest):
            raise ProductRequestError("request must be a ProductJobRequest")
        with self._lock:
            prepared = self._prepared
        if prepared is None:
            raise ProductServiceError("no reviewed Dashboard job is registered")
        if prepared.request != request:
            raise ProductServiceError(
                "worker request does not match the reviewed Dashboard job"
            )
        return prepared.service_factory(request)


class DashboardApplication:
    """Coordinate wizard, presenter, and worker without importing Tk."""

    def __init__(
        self,
        *,
        worker: DashboardWorkerPort | None = None,
        serial_backend_factory: SerialBackendFactory = default_serial_backend_factory,
        job_id_factory: DashboardJobIdFactory = _new_dashboard_job_id,
    ) -> None:
        if not callable(serial_backend_factory):
            raise ProductRequestError("serial_backend_factory must be callable")
        if not callable(job_id_factory):
            raise ProductRequestError("job_id_factory must be callable")
        self._router = ReviewedServiceRouter()
        selected_worker = ProductJobWorker(self._router) if worker is None else worker
        self._dashboard = DashboardPresenter()
        self._controller = DashboardController(self._dashboard, selected_worker)
        self._wizard = DashboardWizardPresenter()
        self._serial_backend_factory = serial_backend_factory
        self._job_id_factory = job_id_factory
        self._prepared: PreparedProductJob | None = None
        self._bundle: ResultExportBundle | None = None
        self._report_view: HumanReportView | None = None
        self._terminal_presented = False
        self._result_exported = False

    @property
    def dashboard_state(self) -> DashboardState:
        return self._controller.state

    @property
    def wizard_state(self) -> DashboardWizardState:
        return self._wizard.state

    @property
    def is_closed(self) -> bool:
        return self._controller.is_closed

    @property
    def has_unsaved_result(self) -> bool:
        """Report whether the current finalized analysis has no saved copy yet."""

        return (
            self._wizard.state.can_export
            and self._bundle is not None
            and not self._result_exported
        )

    def _present_exception(self, error: BaseException) -> UserIssue:
        issue = issue_from_exception(error)
        self._wizard.present_issue(issue)
        self._dashboard.present_issue(issue)
        return issue

    def select_source(self, mode: ProductSourceMode) -> bool:
        try:
            state = self._wizard.select_source(mode)
            self._dashboard.dispatch(
                DashboardAction(
                    DashboardActionType.SELECT_SOURCE,
                    source_mode=state.draft.source_mode,
                )
            )
            self._dashboard.dispatch(
                DashboardAction(
                    DashboardActionType.SELECT_PROFILE,
                    profile_name=state.draft.profile_name,
                    profile_version=state.draft.profile_version,
                )
            )
            self._reset_prepared()
            return True
        except BaseException as error:  # noqa: BLE001 - UI boundary
            self._present_exception(error)
            return False

    def select_profile(self, name: str, version: str) -> bool:
        try:
            self._wizard.select_profile(name, version)
            self._dashboard.dispatch(
                DashboardAction(
                    DashboardActionType.SELECT_PROFILE,
                    profile_name=name,
                    profile_version=version,
                )
            )
            self._reset_prepared()
            return True
        except BaseException as error:  # noqa: BLE001 - UI boundary
            self._present_exception(error)
            return False

    def select_job(self, job_type: ProductJobType) -> bool:
        try:
            self._wizard.select_job(job_type)
            self._dashboard.dispatch(
                DashboardAction(
                    DashboardActionType.SELECT_JOB,
                    job_type=job_type,
                )
            )
            self._reset_prepared()
            return True
        except BaseException as error:  # noqa: BLE001 - UI boundary
            self._present_exception(error)
            return False

    def next(self) -> bool:
        try:
            self._wizard.next()
            return True
        except BaseException as error:  # noqa: BLE001 - UI boundary
            self._present_exception(error)
            return False

    def back(self) -> bool:
        try:
            leaving = self._wizard.state.step
            if leaving is DashboardWizardStep.RESULT:
                self._wizard.modify_setup()
            else:
                self._wizard.back()
            if leaving is DashboardWizardStep.REVIEW:
                self._reset_prepared()
                self._dashboard.dispatch(
                    DashboardAction(DashboardActionType.CLEAR_RESULT)
                )
            elif leaving is DashboardWizardStep.RESULT:
                self._reset_prepared()
                self._dashboard.detach_result()
            return True
        except BaseException as error:  # noqa: BLE001 - UI boundary
            self._present_exception(error)
            return False

    def modify_setup(self) -> bool:
        """Leave Result for editable configuration without erasing its display."""

        return self.back()

    def review_same_setup(self) -> bool:
        """Compile a fresh immutable job from the last finalized setup."""

        try:
            if not self._wizard.state.can_review_same_setup:
                raise ProductRequestError(
                    "Review same setup requires a finalized result"
                )
            draft = self._wizard.state.draft
            self._wizard.modify_setup()
            self._reset_prepared()
            self._dashboard.detach_result()
        except BaseException as error:  # noqa: BLE001 - UI boundary
            self._present_exception(error)
            return False
        return self.prepare_review(draft)

    def start_new_test(self) -> bool:
        """Reset the wizard only after an explicit Result-page action."""

        try:
            state = self._wizard.start_new_test()
            self._reset_prepared()
            self._dashboard.dispatch(
                DashboardAction(
                    DashboardActionType.SELECT_SOURCE,
                    source_mode=state.draft.source_mode,
                )
            )
            self._dashboard.dispatch(
                DashboardAction(
                    DashboardActionType.SELECT_PROFILE,
                    profile_name=state.draft.profile_name,
                    profile_version=state.draft.profile_version,
                )
            )
            self._dashboard.dispatch(
                DashboardAction(
                    DashboardActionType.SELECT_JOB,
                    job_type=state.draft.job_type,
                )
            )
            return True
        except BaseException as error:  # noqa: BLE001 - UI boundary
            self._present_exception(error)
            return False

    def prepare_review(self, draft: DashboardWizardDraft) -> bool:
        """Validate form and CSV content while every external resource is closed."""

        try:
            self._wizard.submit_configuration(draft)
            configuration = draft.to_product_configuration()
            prepared = prepare_product_job(
                configuration,
                self._job_id_factory(),
                backend_factory=self._serial_backend_factory,
            )
            self._router.register(prepared)
            self._prepared = prepared
            self._bundle = None
            self._report_view = None
            self._terminal_presented = False
            self._result_exported = False
            self._wizard.present_review(draft, prepared.review_lines)
            self._dashboard.present_review(prepared.request, prepared.review_lines)
            return True
        except BaseException as error:  # noqa: BLE001 - UI boundary
            self._reset_prepared()
            self._present_exception(error)
            return False

    def run(self) -> bool:
        prepared = self._prepared
        if prepared is None:
            self._present_exception(
                ProductRequestError("Run requires a reviewed configuration")
            )
            return False
        try:
            if not self._controller.start_job(prepared.request):
                issue = self._controller.state.result.issue or issue_from_exception(
                    ProductServiceError("the reviewed Dashboard job could not start")
                )
                self._wizard.present_issue(issue)
                return False
            self._wizard.begin_run()
            return True
        except BaseException as error:  # noqa: BLE001 - UI boundary
            self._present_exception(error)
            return False

    def poll(self) -> DashboardState:
        if self._wizard.state.step is not DashboardWizardStep.RUN:
            return self._controller.state
        state = self._controller.poll()
        if (
            state.progress.worker_state.is_terminal
            and not self._terminal_presented
        ):
            self._terminal_presented = True
            prepared = self._prepared
            output = None if prepared is None else prepared.output_slot.value
            self._bundle = None if output is None else output.result_export
            self._report_view = (
                None if self._bundle is None else build_human_report_view(self._bundle)
            )
            if self._report_view is not None:
                self._dashboard.present_report(self._report_view)
            elif (
                output is not None
                and prepared is not None
                and prepared.request.job_type is ProductJobType.READ
            ):
                self._dashboard.present_read_observations(output.read_result)
            self._wizard.finish_run(export_available=self._bundle is not None)
        return self._controller.state

    def request_cancel(self) -> bool:
        return self._controller.request_cancel()

    def discover_ports(self) -> bool:
        """Enumerate logical IDs only after the user presses Discover."""

        try:
            if (
                self._wizard.state.draft.source_mode
                is not ProductSourceMode.SERIAL_READ_ONLY
            ):
                raise ProductRequestError(
                    "select Serial (read-only) before discovering ports"
                )
            ports = discover_serial_ports(self._serial_backend_factory)
            self._wizard.present_ports(ports)
            return True
        except BaseException as error:  # noqa: BLE001 - UI boundary
            self._present_exception(error)
            return False

    def export_result(self, path_text: str, format_name: str) -> bool:
        """Write one finalized analysis bundle without replacing an existing file."""

        try:
            if not self._wizard.state.can_export or self._bundle is None:
                raise ProductRequestError("no finalized analysis export is available")
            if not isinstance(path_text, str) or not path_text.strip():
                raise ProductRequestError("export path cannot be empty")
            if path_text != path_text.strip() or not path_text.isprintable():
                raise ProductRequestError("export path must be printable stripped text")
            selected_format = DashboardExportFormat(format_name)
            path = Path(path_text)
            required_suffix = f".{selected_format.value}"
            if path.suffix.lower() != required_suffix:
                raise ProductRequestError(
                    f"{selected_format.value.upper()} export path must end with "
                    f"{required_suffix}"
                )
            if selected_format is DashboardExportFormat.JSON:
                written = write_result_export_json(path, self._bundle)
                media_type = "application/json"
            else:
                written = write_result_export_csv(path, self._bundle)
                media_type = "text/csv"
            payload = written.read_bytes()
            artifact = ReportArtifact(
                written.name,
                media_type,
                len(payload),
                hashlib.sha256(payload).hexdigest(),
            )
            if (
                self._report_view is None
            ):  # pragma: no cover - bundle owns this invariant
                self._report_view = build_human_report_view(self._bundle)
            self._dashboard.present_report(
                self._report_view,
                HumanReportPublication(written.parent, (artifact,)),
            )
            self._wizard.present_export(written.name)
            self._result_exported = True
            return True
        except BaseException as error:  # noqa: BLE001 - UI boundary
            self._present_exception(error)
            return False

    def request_close(self, timeout_s: float | None = None) -> bool:
        return self._controller.request_close(timeout_s)

    def _reset_prepared(self) -> None:
        self._router.clear()
        self._prepared = None
        self._bundle = None
        self._report_view = None
        self._terminal_presented = False
        self._result_exported = False


__all__ = [
    "DashboardApplication",
    "DashboardJobIdFactory",
    "ReviewedServiceRouter",
]
