"""Headless application coordinator for the reviewed Dashboard workflow."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path
from threading import RLock
from uuid import uuid4

from analog_validation.analysis import LinearCalibrationCoefficients
from analog_validation.exports import (
    ResultExportBundle,
    load_calibration_coefficients_json,
    write_calibration_coefficients_json,
    write_result_export_csv,
    write_result_export_json,
)

from ..catalog import get_product_profile, get_product_source
from ..errors import ProductRequestError, ProductServiceError
from ..factories import (
    SerialBackendFactory,
    default_serial_backend_factory,
    discover_serial_ports,
)
from ..issues import UserIssue, issue_from_exception
from ..live import LiveMonitorSession
from ..models import ProductJobRequest, ProductJobType, ProductSourceMode
from ..presentation import HumanReportView, build_human_report_view
from ..product_workflows import (
    PreparedProductJob,
    ProductWorkflowConfiguration,
    prepare_product_job,
)
from ..reporting import HumanReportPublication, ReportArtifact, publish_human_report
from ..worker import ProductJobService, ProductJobWorker
from .controller import DashboardController, DashboardWorkerPort
from .presenter import DashboardPresenter
from .presets import draft_from_configuration
from .state import (
    DashboardAction,
    DashboardActionType,
    DashboardArtifactView,
    DashboardState,
)
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
        self._calibration_coefficients: LinearCalibrationCoefficients | None = None
        self._loaded_calibration_coefficients: LinearCalibrationCoefficients | None = (
            None
        )
        self._report_view: HumanReportView | None = None
        self._report_publication: HumanReportPublication | None = None
        self._terminal_presented = False
        self._result_exported = False
        self._coefficient_exported = False
        self._issue_field_id: str | None = None

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
    def report_publication(self) -> HumanReportPublication | None:
        return self._report_publication

    def load_preset_configuration(
        self,
        configuration: ProductWorkflowConfiguration,
        *,
        discard_unsaved: bool = False,
    ) -> bool:
        """Load a copy into Configure without opening input files or starting work."""
        try:
            if self.is_closed or self.dashboard_state.progress.worker_state.is_active:
                raise ProductRequestError(
                    "Preset loading requires an idle, open Dashboard"
                )
            if not isinstance(discard_unsaved, bool):
                raise ProductRequestError("discard_unsaved must be boolean")
            if self.has_unsaved_result and not discard_unsaved:
                raise ProductRequestError(
                    "Save the current result before loading a preset"
                )
            draft = draft_from_configuration(configuration)
            profile = get_product_profile(draft.profile_name, draft.profile_version)
            source = get_product_source(draft.source_mode)
            if (
                draft.source_mode not in profile.source_modes
                or draft.job_type not in source.supported_jobs
            ):
                raise ProductRequestError(
                    "Preset source, profile and test are incompatible"
                )
            self._wizard.load_preset_draft(draft)
            self._reset_prepared()
            self._issue_field_id = None
            for action in (
                DashboardAction(
                    DashboardActionType.SELECT_SOURCE, source_mode=draft.source_mode
                ),
                DashboardAction(
                    DashboardActionType.SELECT_PROFILE,
                    profile_name=draft.profile_name,
                    profile_version=draft.profile_version,
                ),
                DashboardAction(
                    DashboardActionType.SELECT_JOB, job_type=draft.job_type
                ),
            ):
                self._dashboard.dispatch(action)
            return True
        except BaseException as error:  # noqa: BLE001 - UI boundary
            self._present_exception(error)
            return False

    @property
    def has_unsaved_result(self) -> bool:
        """Report whether a finalized result artifact still lacks a saved copy."""

        unsaved_analysis = (
            self._wizard.state.can_export
            and self._bundle is not None
            and not self._result_exported
        )
        unsaved_coefficients = (
            self._wizard.state.can_save_coefficients
            and self._calibration_coefficients is not None
            and not self._coefficient_exported
        )
        return unsaved_analysis or unsaved_coefficients

    @property
    def loaded_calibration_coefficients(self) -> LinearCalibrationCoefficients | None:
        """Return the strictly validated coefficient artifact loaded for inspection."""

        return self._loaded_calibration_coefficients

    @property
    def issue_field_id(self) -> str | None:
        """Return the optional Dashboard-only field hint for the visible issue."""

        return self._issue_field_id if self._wizard.state.issue is not None else None

    def _present_exception(
        self,
        error: BaseException,
        *,
        fallback_field_id: str | None = None,
    ) -> UserIssue:
        field_id = getattr(error, "field_id", fallback_field_id)
        self._issue_field_id = field_id if isinstance(field_id, str) else None
        issue = issue_from_exception(error)
        self._wizard.present_issue(issue)
        self._dashboard.present_issue(issue)
        return issue

    def present_input_error(self, error: BaseException) -> bool:
        """Present a form-construction failure through the normal issue boundary."""

        if not isinstance(error, BaseException):
            raise ProductRequestError("error must be a BaseException")
        self._present_exception(error)
        return False

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
            self._calibration_coefficients = None
            self._report_view = None
            self._terminal_presented = False
            self._result_exported = False
            self._coefficient_exported = False
            self._wizard.present_review(draft, prepared.review_lines)
            self._dashboard.present_review(prepared.request, prepared.review_lines)
            return True
        except BaseException as error:  # noqa: BLE001 - UI boundary
            self._reset_prepared()
            self._present_exception(
                error,
                fallback_field_id=(
                    "replay_path"
                    if draft.source_mode is ProductSourceMode.CSV_REPLAY
                    else None
                ),
            )
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
                self._issue_field_id = None
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
        prepared = self._prepared
        live_session = None if prepared is None else prepared.live_monitor_session
        if live_session is not None:
            state = self._dashboard.present_live_monitor(
                live_session.snapshot(),
                active=state.progress.worker_state.is_active,
            )
        if state.progress.worker_state.is_terminal and not self._terminal_presented:
            self._terminal_presented = True
            output = None if prepared is None else prepared.output_slot.value
            self._bundle = None if output is None else output.result_export
            self._calibration_coefficients = (
                None if output is None else output.calibration_coefficients
            )
            self._report_view = (
                None if self._bundle is None else build_human_report_view(self._bundle)
            )
            if self._report_view is not None:
                self._dashboard.present_report(self._report_view)
            elif (
                output is not None
                and prepared is not None
                and prepared.request.job_type
                in {ProductJobType.READ, ProductJobType.LIVE_MONITOR}
            ):
                self._dashboard.present_read_observations(output.read_result)
            self._wizard.finish_run(
                export_available=self._bundle is not None,
                coefficient_available=self._calibration_coefficients is not None,
            )
        return self._controller.state

    def pause_live_monitor(self) -> bool:
        """Pause only an active reviewed live monitor at a safe checkpoint."""

        try:
            session = self._require_live_session(active=True)
            changed = session.pause()
            self._dashboard.present_live_monitor(session.snapshot(), active=True)
            return changed
        except BaseException as error:  # noqa: BLE001 - UI boundary
            self._present_exception(error)
            return False

    def resume_live_monitor(self) -> bool:
        """Resume only an active reviewed live monitor."""

        try:
            session = self._require_live_session(active=True)
            changed = session.resume()
            self._dashboard.present_live_monitor(session.snapshot(), active=True)
            return changed
        except BaseException as error:  # noqa: BLE001 - UI boundary
            self._present_exception(error)
            return False

    def set_live_time_window(self, seconds: float) -> bool:
        """Change presentation range without altering acquisition or evidence."""

        try:
            session = self._require_live_session(active=False)
            snapshot = session.set_time_window(seconds)
            self._dashboard.present_live_monitor(
                snapshot,
                active=self._controller.state.progress.worker_state.is_active,
            )
            return True
        except BaseException as error:  # noqa: BLE001 - UI boundary
            self._present_exception(error)
            return False

    def _require_live_session(self, *, active: bool) -> LiveMonitorSession:
        prepared = self._prepared
        session = None if prepared is None else prepared.live_monitor_session
        if session is None:
            raise ProductRequestError("no reviewed live monitor session is available")
        if active and (
            self._wizard.state.step is not DashboardWizardStep.RUN
            or not self._controller.state.progress.worker_state.is_active
        ):
            raise ProductRequestError("live monitor control requires an active run")
        return session

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
            existing_artifacts = self._dashboard.state.artifacts.artifacts
            self._dashboard.present_report(
                self._report_view,
                HumanReportPublication(written.parent, (artifact,)),
            )
            for existing_artifact in existing_artifacts:
                self._dashboard.present_artifact(existing_artifact)
            self._wizard.present_export(written.name)
            self._result_exported = True
            return True
        except BaseException as error:  # noqa: BLE001 - UI boundary
            self._present_exception(error)
            return False

    def save_report_bundle(self, path_text: str) -> bool:
        """Save a readable report and its exact analysis JSON in one new directory."""
        try:
            if (
                not self._wizard.state.can_export
                or self._bundle is None
                or self._report_view is None
            ):
                raise ProductRequestError(
                    "A finalized analysis is required to save a report"
                )
            publication = publish_human_report(
                path_text, self._report_view, result_bundle=self._bundle
            )
            previous = self._dashboard.state.artifacts.artifacts
            self._dashboard.present_report(self._report_view, publication)
            names = {artifact.name for artifact in publication.artifacts}
            for artifact in previous:
                if artifact.name not in names:
                    self._dashboard.present_artifact(artifact)
            self._report_publication = publication
            self._wizard.present_export("report package (includes result.json)")
            self._result_exported = True
            return True
        except BaseException as error:  # noqa: BLE001 - UI boundary
            self._present_exception(error)
            return False

    def save_calibration_coefficients(self, path_text: str) -> bool:
        """Save fitted coefficients to a new JSON file without overwriting."""

        try:
            coefficients = self._calibration_coefficients
            if not self._wizard.state.can_save_coefficients or coefficients is None:
                raise ProductRequestError(
                    "no finalized calibration coefficient artifact is available"
                )
            path = self._coefficient_path(path_text)
            written = write_calibration_coefficients_json(path, coefficients)
            payload = written.read_bytes()
            self._dashboard.present_artifact(
                DashboardArtifactView(
                    written.name,
                    "application/json",
                    len(payload),
                    hashlib.sha256(payload).hexdigest(),
                )
            )
            self._wizard.present_coefficient_artifact(
                f"Calibration coefficients saved safely: {written.name}"
            )
            self._coefficient_exported = True
            return True
        except BaseException as error:  # noqa: BLE001 - UI boundary
            self._present_exception(error)
            return False

    def load_calibration_coefficients(self, path_text: str) -> bool:
        """Strictly validate one coefficient file; loading does not apply it to a run."""

        try:
            if not self._wizard.state.can_load_coefficients:
                raise ProductRequestError(
                    "coefficient inspection is available only on the Result step"
                )
            coefficients = load_calibration_coefficients_json(
                self._coefficient_path(path_text)
            )
            self._loaded_calibration_coefficients = coefficients
            self._wizard.present_coefficient_artifact(
                "Loaded and validated coefficients "
                f"{coefficients.coefficient_id}/{coefficients.coefficient_version}: "
                f"reference = {coefficients.scale:g} * observed + "
                f"{coefficients.offset:g} {coefficients.unit.value}. "
                "Inspection only; this did not change or rerun the test."
            )
            return True
        except BaseException as error:  # noqa: BLE001 - UI boundary
            self._present_exception(error)
            return False

    @staticmethod
    def _coefficient_path(path_text: str) -> Path:
        if not isinstance(path_text, str) or not path_text.strip():
            raise ProductRequestError("coefficient path cannot be empty")
        if path_text != path_text.strip() or not path_text.isprintable():
            raise ProductRequestError(
                "coefficient path must be printable stripped text"
            )
        path = Path(path_text)
        if path.suffix.lower() != ".json":
            raise ProductRequestError(
                "calibration coefficient path must end with .json"
            )
        return path

    def request_close(self, timeout_s: float | None = None) -> bool:
        return self._controller.request_close(timeout_s)

    def _reset_prepared(self) -> None:
        if (
            self._prepared is not None
            and self._prepared.live_monitor_session is not None
        ):
            self._prepared.live_monitor_session.resume()
        self._router.clear()
        self._prepared = None
        self._bundle = None
        self._calibration_coefficients = None
        self._loaded_calibration_coefficients = None
        self._report_view = None
        self._report_publication = None
        self._terminal_presented = False
        self._result_exported = False
        self._coefficient_exported = False


__all__ = [
    "DashboardApplication",
    "DashboardJobIdFactory",
    "ReviewedServiceRouter",
]
