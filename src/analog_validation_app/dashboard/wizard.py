"""Headless six-step beginner workflow for the local Dashboard."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from threading import get_ident
from typing import Any

from analog_validation import EvidenceSource, MeasurementUnit, ReadOperation
from analog_validation.protocol.msp430_health_v1 import (
    MSP430_HEALTH_CHANNEL_BUS_VOLTAGE,
    MSP430_HEALTH_PROFILE_NAME,
    MSP430_HEALTH_PROFILE_VERSION,
)
from analog_validation.transport import SerialPortInfo

from ..catalog import get_product_profile, get_product_source, list_product_profiles
from ..errors import ProductCatalogError, ProductFieldError, ProductRequestError
from ..factories import SerialChannelAlias, SerialSourceConfig
from ..issues import UserIssue
from ..models import ProductJobType, ProductSourceMode
from ..product_workflows import ProductWorkflowConfiguration

DASHBOARD_WIZARD_SCHEMA_VERSION = "dashboard-wizard.v1"
MAX_DASHBOARD_WIZARD_PORTS = 256
MAX_DASHBOARD_WIZARD_REVIEW_LINES = 64
MAX_DASHBOARD_WIZARD_TEXT_CHARS = 1_024


class DashboardWizardStep(str, Enum):
    """The fixed beginner journey; order is part of the product contract."""

    SOURCE = "SOURCE"
    TEST = "TEST"
    CONFIGURATION = "CONFIGURATION"
    REVIEW = "REVIEW"
    RUN = "RUN"
    RESULT = "RESULT"


class DashboardExportFormat(str, Enum):
    """Explicit finalized analysis export formats supported by the core."""

    JSON = "json"
    CSV = "csv"


def _text(name: str, value: object, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise ProductFieldError(f"{name} must be stripped text", name)
    if not value and not allow_empty:
        raise ProductFieldError(f"{name} cannot be empty", name)
    if len(value) > MAX_DASHBOARD_WIZARD_TEXT_CHARS:
        raise ProductFieldError(
            f"{name} exceeds {MAX_DASHBOARD_WIZARD_TEXT_CHARS} characters", name
        )
    if value and not value.isprintable():
        raise ProductFieldError(f"{name} must contain only printable characters", name)
    return value


def _integer(name: str, value: str) -> int:
    checked = _text(name, value)
    try:
        return int(checked)
    except ValueError as error:
        raise ProductFieldError(f"{name} must be an integer", name) from error


def _number(name: str, value: str) -> float:
    checked = _text(name, value)
    try:
        parsed = float(checked)
    except ValueError as error:
        raise ProductFieldError(f"{name} must be numeric", name) from error
    if not math.isfinite(parsed):
        raise ProductFieldError(f"{name} must be finite", name)
    return parsed


def _serial_aliases(value: str) -> tuple[SerialChannelAlias, ...]:
    checked = _text("serial_afe_adc_aliases", value, allow_empty=True)
    if not checked:
        return ()
    entries = tuple(part.strip() for part in checked.split(","))
    if any(not entry for entry in entries):
        raise ProductFieldError(
            "serial_afe_adc_aliases contains an empty comma-separated entry",
            "serial_afe_adc_aliases",
        )
    try:
        return tuple(SerialChannelAlias.parse(entry) for entry in entries)
    except ProductRequestError as error:
        raise ProductFieldError(str(error), "serial_afe_adc_aliases") from error


def _dashboard_serial_field(field_id: str) -> str:
    return {
        "port_id": "serial_port",
        "baud_rate": "serial_baud_rate",
        "read_timeout_seconds": "serial_read_timeout",
        "max_polls_per_operation": "serial_max_polls",
        "expected_device_id": "serial_expected_device_id",
        "afe_adc_channel_aliases": "serial_afe_adc_aliases",
        "native_channel": "serial_afe_adc_aliases",
        "canonical_channel": "serial_afe_adc_aliases",
    }.get(field_id, field_id)


@dataclass(frozen=True, slots=True)
class DashboardWizardGuidance:
    """Beginner explanation shown for one workflow step."""

    number: int
    title: str
    what: str
    why: str
    confirm: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.number, bool)
            or not isinstance(self.number, int)
            or not 1 <= self.number <= 6
        ):
            raise ProductRequestError("guidance number must be between 1 and 6")
        for name in ("title", "what", "why", "confirm"):
            _text(name, getattr(self, name))


_GUIDANCE = {
    DashboardWizardStep.SOURCE: DashboardWizardGuidance(
        1,
        "Choose the evidence source",
        "We select where observations will come from; Simulator is the safe default.",
        "Evidence labels and available tests depend on the source, so it must be explicit.",
        "Confirm the source and exact profile. This selection opens no file or port.",
    ),
    DashboardWizardStep.TEST: DashboardWizardGuidance(
        2,
        "Choose the test",
        "We choose a bounded read, live monitor, DC, hysteresis, calibration, or frequency-response analysis.",
        "A test defines required channels and calculations, independent of the device brand.",
        "Confirm that the selected source declares support for this test.",
    ),
    DashboardWizardStep.CONFIGURATION: DashboardWizardGuidance(
        3,
        "Enter bounded configuration",
        "We enter channels, units, counts, and only the settings needed by the source.",
        "Typed limits prevent accidental unbounded reads and ambiguous unit conversions.",
        "Confirm channel names, units, counts, replay path, or receive-only serial bounds.",
    ),
    DashboardWizardStep.REVIEW: DashboardWizardGuidance(
        4,
        "Review evidence and safety",
        "We compile the form into one immutable job and display its exact boundaries.",
        "The resource stays closed until Run, while invalid CSV data is rejected now.",
        "Confirm the evidence class, profile, limits, and explicit no-hardware-validation claim.",
    ),
    DashboardWizardStep.RUN: DashboardWizardGuidance(
        5,
        "Run with bounded ownership",
        "One worker owns the selected source and reports progress to the UI thread.",
        "Single ownership plus cooperative cancellation prevents orphaned resources.",
        "Wait for completion or use Cancel safely; do not disconnect an active serial source.",
    ),
    DashboardWizardStep.RESULT: DashboardWizardGuidance(
        6,
        "View and export finalized evidence",
        "We show the finalized result, evidence source, limitations, and copied report points.",
        "Presentation never recalculates PASS/FAIL, and export never overwrites by default.",
        "Confirm the outcome and limitations before using an analysis export elsewhere.",
    ),
}


@dataclass(frozen=True, slots=True)
class DashboardWizardDraft:
    """Editable form snapshot; strict conversion happens before the review step."""

    source_mode: ProductSourceMode = ProductSourceMode.SIMULATOR
    job_type: ProductJobType = ProductJobType.READ
    profile_name: str = "afe"
    profile_version: str = "1"
    primary_channel: str = "afe.ch0.input"
    secondary_channel: str = "afe.ch0.output"
    state_channel: str = "afe.ch0.threshold"
    operation: ReadOperation = ReadOperation.ANALOG
    unit: MeasurementUnit = MeasurementUnit.MILLIVOLT
    sample_count: str = "5"
    rising_count: str = "12"
    falling_count: str = "22"
    replay_path: str = ""
    replay_minimum: str = "0"
    replay_maximum: str = "3300"
    serial_port: str = ""
    serial_baud_rate: str = "115200"
    serial_read_timeout: str = "0.25"
    serial_max_polls: str = "32"
    serial_expected_device_id: str = ""
    serial_afe_adc_aliases: str = ""
    serial_confirm_read_only: bool = False
    low_output_limit: str = "25"
    high_output_limit: str = "3275"
    target_gain: str = "2"
    gain_tolerance: str = "0.05"
    max_abs_offset: str = "25"
    min_r_squared: str = "0.999"
    max_rmse: str = "1"
    coefficient_id: str = "afe-linear-calibration"
    coefficient_version: str = "1"
    max_calibration_rmse: str = "1"
    max_calibration_mean_absolute_error: str = "1"
    max_calibration_absolute_error: str = "2"
    minimum_calibration_rmse_reduction: str = "0"
    minimum_high_threshold: str = "900"
    maximum_high_threshold: str = "1100"
    minimum_low_threshold: str = "800"
    maximum_low_threshold: str = "1000"
    minimum_width: str = "20"
    maximum_width: str = "200"
    maximum_width_span: str = "0"
    export_path: str = ""
    export_format: DashboardExportFormat = DashboardExportFormat.JSON
    frequency_channel: str = "afe.ch0.frequency"
    frequency_point_count: str = "21"
    frequency_minimum_hz: str = "10"
    frequency_maximum_hz: str = "100000"
    frequency_input_amplitude: str = "1000"
    simulated_cutoff_frequency_hz: str = "1000"
    target_cutoff_frequency_hz: str = "1000"
    cutoff_relative_tolerance: str = "0.15"
    cutoff_drop_db: str = "3.010299956639812"
    monitor_sample_interval_seconds: str = "0.05"
    monitor_time_window_seconds: str = "5"
    monitor_max_buffer_points: str = "2048"
    monitor_include_secondary: bool = True
    monitor_include_state: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.source_mode, ProductSourceMode):
            raise ProductRequestError("source_mode must be a ProductSourceMode")
        if not isinstance(self.job_type, ProductJobType):
            raise ProductRequestError("job_type must be a ProductJobType")
        if not isinstance(self.operation, ReadOperation):
            raise ProductRequestError("operation must be a ReadOperation")
        if not isinstance(self.unit, MeasurementUnit):
            raise ProductRequestError("unit must be a MeasurementUnit")
        if not isinstance(self.export_format, DashboardExportFormat):
            raise ProductRequestError("export_format must be a DashboardExportFormat")
        for name in (
            "profile_name",
            "profile_version",
            "primary_channel",
            "secondary_channel",
            "state_channel",
            "frequency_channel",
            "coefficient_id",
            "coefficient_version",
        ):
            _text(name, getattr(self, name))
        for name in (
            "sample_count",
            "rising_count",
            "falling_count",
            "frequency_point_count",
            "frequency_minimum_hz",
            "frequency_maximum_hz",
            "frequency_input_amplitude",
            "simulated_cutoff_frequency_hz",
            "target_cutoff_frequency_hz",
            "cutoff_relative_tolerance",
            "cutoff_drop_db",
            "monitor_sample_interval_seconds",
            "monitor_time_window_seconds",
            "monitor_max_buffer_points",
            "replay_path",
            "replay_minimum",
            "replay_maximum",
            "serial_port",
            "serial_baud_rate",
            "serial_read_timeout",
            "serial_max_polls",
            "serial_expected_device_id",
            "serial_afe_adc_aliases",
            "low_output_limit",
            "high_output_limit",
            "target_gain",
            "gain_tolerance",
            "max_abs_offset",
            "min_r_squared",
            "max_rmse",
            "max_calibration_rmse",
            "max_calibration_mean_absolute_error",
            "max_calibration_absolute_error",
            "minimum_calibration_rmse_reduction",
            "minimum_high_threshold",
            "maximum_high_threshold",
            "minimum_low_threshold",
            "maximum_low_threshold",
            "minimum_width",
            "maximum_width",
            "maximum_width_span",
            "export_path",
        ):
            _text(name, getattr(self, name), allow_empty=True)
        if not isinstance(self.serial_confirm_read_only, bool):
            raise ProductRequestError("serial_confirm_read_only must be boolean")
        for name in ("monitor_include_secondary", "monitor_include_state"):
            if not isinstance(getattr(self, name), bool):
                raise ProductRequestError(f"{name} must be boolean")
        source = get_product_source(self.source_mode)
        profile = get_product_profile(self.profile_name, self.profile_version)
        if self.job_type not in source.supported_jobs:
            raise ProductCatalogError(
                f"{self.source_mode.value} does not support {self.job_type.value}"
            )
        if self.source_mode not in profile.source_modes:
            raise ProductCatalogError(
                f"profile {profile.identity} does not support {self.source_mode.value}"
            )

    def to_product_configuration(self) -> ProductWorkflowConfiguration:
        """Parse the form once, before any worker or serial resource starts."""

        replay_bounds: dict[str, float] = {}
        try:
            minimum = _number("replay_minimum", self.replay_minimum)
            maximum = _number("replay_maximum", self.replay_maximum)
            if minimum >= maximum:
                raise ProductFieldError(
                    "replay_minimum must be below replay_maximum", "replay_maximum"
                )
            replay_bounds = {"replay_minimum": minimum, "replay_maximum": maximum}
        except ProductFieldError:
            if self.source_mode is ProductSourceMode.CSV_REPLAY:
                raise
            # Hidden invalid Replay scratch must not block another source. Omit
            # both fields to use the typed configuration's own default bounds.
        values: dict[str, Any] = {
            **replay_bounds,
            "primary_channel": self.primary_channel,
            "secondary_channel": self.secondary_channel,
            "state_channel": self.state_channel,
            "operation": self.operation,
            "unit": self.unit,
            "sample_count": _integer("sample_count", self.sample_count),
            "rising_count": _integer("rising_count", self.rising_count),
            "falling_count": _integer("falling_count", self.falling_count),
            "frequency_channel": self.frequency_channel,
            "frequency_point_count": _integer(
                "frequency_point_count", self.frequency_point_count
            ),
            "frequency_minimum_hz": _number(
                "frequency_minimum_hz", self.frequency_minimum_hz
            ),
            "frequency_maximum_hz": _number(
                "frequency_maximum_hz", self.frequency_maximum_hz
            ),
            "frequency_input_amplitude": _number(
                "frequency_input_amplitude", self.frequency_input_amplitude
            ),
            "simulated_cutoff_frequency_hz": _number(
                "simulated_cutoff_frequency_hz",
                self.simulated_cutoff_frequency_hz,
            ),
            "target_cutoff_frequency_hz": _number(
                "target_cutoff_frequency_hz", self.target_cutoff_frequency_hz
            ),
            "cutoff_relative_tolerance": _number(
                "cutoff_relative_tolerance", self.cutoff_relative_tolerance
            ),
            "cutoff_drop_db": _number("cutoff_drop_db", self.cutoff_drop_db),
            "monitor_sample_interval_seconds": _number(
                "monitor_sample_interval_seconds",
                self.monitor_sample_interval_seconds,
            ),
            "monitor_time_window_seconds": _number(
                "monitor_time_window_seconds", self.monitor_time_window_seconds
            ),
            "monitor_max_buffer_points": _integer(
                "monitor_max_buffer_points", self.monitor_max_buffer_points
            ),
            "monitor_include_secondary": self.monitor_include_secondary,
            "monitor_include_state": self.monitor_include_state,
            "low_output_limit": _number("low_output_limit", self.low_output_limit),
            "high_output_limit": _number("high_output_limit", self.high_output_limit),
            "target_gain": _number("target_gain", self.target_gain),
            "gain_tolerance": _number("gain_tolerance", self.gain_tolerance),
            "max_abs_offset": _number("max_abs_offset", self.max_abs_offset),
            "min_r_squared": _number("min_r_squared", self.min_r_squared),
            "max_rmse": _number("max_rmse", self.max_rmse),
            "coefficient_id": self.coefficient_id,
            "coefficient_version": self.coefficient_version,
            "max_calibration_rmse": _number(
                "max_calibration_rmse", self.max_calibration_rmse
            ),
            "max_calibration_mean_absolute_error": _number(
                "max_calibration_mean_absolute_error",
                self.max_calibration_mean_absolute_error,
            ),
            "max_calibration_absolute_error": _number(
                "max_calibration_absolute_error",
                self.max_calibration_absolute_error,
            ),
            "minimum_calibration_rmse_reduction": _number(
                "minimum_calibration_rmse_reduction",
                self.minimum_calibration_rmse_reduction,
            ),
            "minimum_high_threshold": _number(
                "minimum_high_threshold", self.minimum_high_threshold
            ),
            "maximum_high_threshold": _number(
                "maximum_high_threshold", self.maximum_high_threshold
            ),
            "minimum_low_threshold": _number(
                "minimum_low_threshold", self.minimum_low_threshold
            ),
            "maximum_low_threshold": _number(
                "maximum_low_threshold", self.maximum_low_threshold
            ),
            "minimum_width": _number("minimum_width", self.minimum_width),
            "maximum_width": _number("maximum_width", self.maximum_width),
            "maximum_width_span": _number(
                "maximum_width_span", self.maximum_width_span
            ),
        }
        if self.source_mode is ProductSourceMode.CSV_REPLAY:
            values.update(
                {
                    "replay_path": Path(_text("replay_path", self.replay_path)),
                }
            )
        elif self.source_mode is ProductSourceMode.SERIAL_READ_ONLY:
            sample_count = _integer("sample_count", self.sample_count)
            try:
                serial_config = SerialSourceConfig(
                    port_id=_text("serial_port", self.serial_port),
                    baud_rate=_integer("serial_baud_rate", self.serial_baud_rate),
                    read_timeout_seconds=_number(
                        "serial_read_timeout", self.serial_read_timeout
                    ),
                    max_polls_per_operation=_integer(
                        "serial_max_polls", self.serial_max_polls
                    ),
                    max_buffered_measurements=max(128, sample_count * 8),
                    evidence_source=EvidenceSource.HOST_TEST,
                    expected_device_id=(
                        _text(
                            "serial_expected_device_id",
                            self.serial_expected_device_id,
                            allow_empty=True,
                        )
                        or None
                    ),
                    afe_adc_channel_aliases=_serial_aliases(
                        self.serial_afe_adc_aliases
                    ),
                )
            except ProductRequestError as error:
                field_id = _dashboard_serial_field(
                    str(getattr(error, "field_id", "serial_afe_adc_aliases"))
                )
                if isinstance(error, ProductFieldError) and error.field_id == field_id:
                    raise
                raise ProductFieldError(str(error), field_id) from error
            values.update(
                {
                    "serial_config": serial_config,
                    "confirm_read_only": self.serial_confirm_read_only,
                }
            )
        return ProductWorkflowConfiguration(
            self.source_mode,
            self.job_type,
            self.profile_name,
            self.profile_version,
            **values,
        )


def _compatible_profile_identities(mode: ProductSourceMode) -> tuple[str, ...]:
    values = tuple(
        profile.identity
        for profile in list_product_profiles()
        if mode in profile.source_modes
    )
    if not values:
        raise ProductCatalogError(f"no profile supports {mode.value}")
    return values


def _normalize_live_monitor_draft(
    draft: DashboardWizardDraft,
) -> DashboardWizardDraft:
    """Apply safe, finite defaults when a source enters live-monitor mode."""

    unit = (
        MeasurementUnit.MILLIVOLT
        if draft.unit is MeasurementUnit.BOOLEAN
        else draft.unit
    )
    if draft.source_mode is ProductSourceMode.SERIAL_READ_ONLY:
        return replace(
            draft,
            operation=ReadOperation.ANALOG,
            unit=unit,
            sample_count="20",
            monitor_sample_interval_seconds="0.02",
            monitor_include_secondary=False,
            monitor_include_state=False,
            serial_read_timeout="0.05",
            serial_max_polls="4",
        )
    return replace(draft, operation=ReadOperation.ANALOG, unit=unit)


@dataclass(frozen=True, slots=True)
class DashboardWizardState:
    """Complete immutable wizard view owned by the UI thread."""

    revision: int
    step: DashboardWizardStep
    draft: DashboardWizardDraft
    review_lines: tuple[str, ...] = ()
    discovered_ports: tuple[SerialPortInfo, ...] = ()
    issue: UserIssue | None = None
    export_available: bool = False
    export_message: str = "No finalized analysis export is available."
    coefficient_available: bool = False
    coefficient_message: str = "No calibration coefficient artifact is available."
    schema_version: str = DASHBOARD_WIZARD_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or self.revision < 0
        ):
            raise ProductRequestError("wizard revision must be non-negative")
        if not isinstance(self.step, DashboardWizardStep):
            raise ProductRequestError("step must be a DashboardWizardStep")
        if not isinstance(self.draft, DashboardWizardDraft):
            raise ProductRequestError("draft must be a DashboardWizardDraft")
        if (
            not isinstance(self.review_lines, tuple)
            or len(self.review_lines) > MAX_DASHBOARD_WIZARD_REVIEW_LINES
        ):
            raise ProductRequestError("review_lines must be a bounded tuple")
        for line in self.review_lines:
            _text("review line", line)
        if (
            not isinstance(self.discovered_ports, tuple)
            or len(self.discovered_ports) > MAX_DASHBOARD_WIZARD_PORTS
        ):
            raise ProductRequestError("discovered_ports must be a bounded tuple")
        if not all(isinstance(port, SerialPortInfo) for port in self.discovered_ports):
            raise ProductRequestError(
                "discovered_ports must contain SerialPortInfo values"
            )
        if self.issue is not None and not isinstance(self.issue, UserIssue):
            raise ProductRequestError("issue must be a UserIssue or None")
        if not isinstance(self.export_available, bool):
            raise ProductRequestError("export_available must be boolean")
        _text("export_message", self.export_message)
        if not isinstance(self.coefficient_available, bool):
            raise ProductRequestError("coefficient_available must be boolean")
        _text("coefficient_message", self.coefficient_message)
        if self.schema_version != DASHBOARD_WIZARD_SCHEMA_VERSION:
            raise ProductRequestError(
                f"unsupported Dashboard wizard schema: {self.schema_version}"
            )

    @property
    def guidance(self) -> DashboardWizardGuidance:
        return _GUIDANCE[self.step]

    @property
    def source_modes(self) -> tuple[ProductSourceMode, ...]:
        return tuple(ProductSourceMode)

    @property
    def job_types(self) -> tuple[ProductJobType, ...]:
        return get_product_source(self.draft.source_mode).supported_jobs

    @property
    def profile_identities(self) -> tuple[str, ...]:
        return _compatible_profile_identities(self.draft.source_mode)

    @property
    def can_back(self) -> bool:
        return self.step not in {DashboardWizardStep.SOURCE, DashboardWizardStep.RUN}

    @property
    def can_next(self) -> bool:
        return self.step in {DashboardWizardStep.SOURCE, DashboardWizardStep.TEST}

    @property
    def can_prepare_review(self) -> bool:
        return self.step is DashboardWizardStep.CONFIGURATION

    @property
    def can_run(self) -> bool:
        return (
            self.step is DashboardWizardStep.REVIEW
            and bool(self.review_lines)
            and self.issue is None
        )

    @property
    def can_cancel(self) -> bool:
        return self.step is DashboardWizardStep.RUN

    @property
    def can_export(self) -> bool:
        return self.step is DashboardWizardStep.RESULT and self.export_available

    @property
    def can_save_coefficients(self) -> bool:
        return self.step is DashboardWizardStep.RESULT and self.coefficient_available

    @property
    def can_load_coefficients(self) -> bool:
        return self.step is DashboardWizardStep.RESULT

    @property
    def can_modify_setup(self) -> bool:
        return self.step is DashboardWizardStep.RESULT

    @property
    def can_review_same_setup(self) -> bool:
        return self.step is DashboardWizardStep.RESULT

    @property
    def can_start_new_test(self) -> bool:
        return self.step is DashboardWizardStep.RESULT


class DashboardWizardPresenter:
    """Apply wizard transitions only on the creating UI/main thread."""

    def __init__(self, state: DashboardWizardState | None = None) -> None:
        if state is not None and not isinstance(state, DashboardWizardState):
            raise ProductRequestError("state must be DashboardWizardState or None")
        self._owner_thread_id = get_ident()
        self._state = state or DashboardWizardState(
            0, DashboardWizardStep.SOURCE, DashboardWizardDraft()
        )

    @property
    def state(self) -> DashboardWizardState:
        return self._state

    def _replace(self, **changes: Any) -> DashboardWizardState:
        if get_ident() != self._owner_thread_id:
            raise ProductRequestError(
                "Dashboard wizard updates must run on the creating UI thread"
            )
        candidate = replace(self._state, **changes)
        if candidate == self._state:
            return self._state
        self._state = replace(candidate, revision=self._state.revision + 1)
        return self._state

    def select_source(self, mode: ProductSourceMode) -> DashboardWizardState:
        if self._state.step is not DashboardWizardStep.SOURCE:
            raise ProductRequestError("source can only change in step 1")
        source = get_product_source(mode)
        profiles = _compatible_profile_identities(mode)
        profile_name, profile_version = profiles[0].split("/", maxsplit=1)
        job = (
            self._state.draft.job_type
            if self._state.draft.job_type in source.supported_jobs
            else source.supported_jobs[0]
        )
        draft = replace(
            self._state.draft,
            source_mode=mode,
            job_type=job,
            profile_name=profile_name,
            profile_version=profile_version,
            serial_confirm_read_only=False,
        )
        if job is ProductJobType.LIVE_MONITOR:
            draft = _normalize_live_monitor_draft(draft)
        return self._replace(
            draft=draft,
            review_lines=(),
            discovered_ports=(),
            issue=None,
            export_available=False,
            coefficient_available=False,
            coefficient_message="No calibration coefficient artifact is available.",
        )

    def select_profile(self, name: str, version: str) -> DashboardWizardState:
        if self._state.step is not DashboardWizardStep.SOURCE:
            raise ProductRequestError("profile can only change in step 1")
        profile = get_product_profile(name, version)
        if self._state.draft.source_mode not in profile.source_modes:
            raise ProductCatalogError(
                f"profile {profile.identity} does not support "
                f"{self._state.draft.source_mode.value}"
            )
        primary_channel = (
            MSP430_HEALTH_CHANNEL_BUS_VOLTAGE
            if (name, version)
            == (MSP430_HEALTH_PROFILE_NAME, MSP430_HEALTH_PROFILE_VERSION)
            else "afe.ch0.input"
        )
        return self._replace(
            draft=replace(
                self._state.draft,
                profile_name=name,
                profile_version=version,
                primary_channel=primary_channel,
                operation=ReadOperation.ANALOG,
                unit=MeasurementUnit.MILLIVOLT,
            ),
            issue=None,
        )

    def select_job(self, job_type: ProductJobType) -> DashboardWizardState:
        if self._state.step is not DashboardWizardStep.TEST:
            raise ProductRequestError("test can only change in step 2")
        source = get_product_source(self._state.draft.source_mode)
        if job_type not in source.supported_jobs:
            raise ProductCatalogError(
                f"{source.mode.value} does not support {job_type.value}"
            )
        draft = replace(self._state.draft, job_type=job_type)
        if job_type is ProductJobType.LIVE_MONITOR:
            draft = _normalize_live_monitor_draft(draft)
        return self._replace(
            draft=draft,
            issue=None,
        )

    def submit_configuration(self, draft: DashboardWizardDraft) -> DashboardWizardState:
        if self._state.step is not DashboardWizardStep.CONFIGURATION:
            raise ProductRequestError("configuration can only change in step 3")
        if not isinstance(draft, DashboardWizardDraft):
            raise ProductRequestError("draft must be a DashboardWizardDraft")
        if (
            draft.source_mode,
            draft.job_type,
            draft.profile_name,
            draft.profile_version,
        ) != (
            self._state.draft.source_mode,
            self._state.draft.job_type,
            self._state.draft.profile_name,
            self._state.draft.profile_version,
        ):
            raise ProductRequestError(
                "configuration cannot silently change source, test, or profile"
            )
        return self._replace(draft=draft, issue=None)

    def load_preset_draft(self, draft: DashboardWizardDraft) -> DashboardWizardState:
        """Replace an idle setup with an offline preset, requiring a fresh review."""
        if self._state.step is DashboardWizardStep.RUN:
            raise ProductRequestError(
                "Wait for the current run before loading a preset"
            )
        if not isinstance(draft, DashboardWizardDraft) or draft.source_mode not in {
            ProductSourceMode.SIMULATOR,
            ProductSourceMode.CSV_REPLAY,
        }:
            raise ProductRequestError("Preset loading requires an offline wizard draft")
        return self._replace(
            step=DashboardWizardStep.CONFIGURATION,
            draft=draft,
            review_lines=(),
            discovered_ports=(),
            issue=None,
            export_available=False,
            coefficient_available=False,
            export_message="Preset loaded. Validate this setup before running.",
            coefficient_message="No calibration coefficient artifact is available.",
        )

    def next(self) -> DashboardWizardState:
        target = {
            DashboardWizardStep.SOURCE: DashboardWizardStep.TEST,
            DashboardWizardStep.TEST: DashboardWizardStep.CONFIGURATION,
        }.get(self._state.step)
        if target is None:
            raise ProductRequestError("Next is unavailable for the current step")
        return self._replace(step=target, issue=None)

    def back(self) -> DashboardWizardState:
        target = {
            DashboardWizardStep.TEST: DashboardWizardStep.SOURCE,
            DashboardWizardStep.CONFIGURATION: DashboardWizardStep.TEST,
            DashboardWizardStep.REVIEW: DashboardWizardStep.CONFIGURATION,
            DashboardWizardStep.RESULT: DashboardWizardStep.CONFIGURATION,
        }.get(self._state.step)
        if target is None:
            raise ProductRequestError("Back is unavailable for the current step")
        return self._replace(
            step=target,
            review_lines=(),
            issue=None,
            export_available=False,
            export_message="No finalized analysis export is available.",
            coefficient_available=False,
            coefficient_message="No calibration coefficient artifact is available.",
        )

    def modify_setup(self) -> DashboardWizardState:
        """Return from Result to Configuration while preserving reviewed values."""

        if not self._state.can_modify_setup:
            raise ProductRequestError("Modify setup requires a finalized result")
        return self._replace(
            step=DashboardWizardStep.CONFIGURATION,
            review_lines=(),
            issue=None,
            export_available=False,
            export_message=(
                "The previous result remains visible for reference. "
                "Validate the edited setup before running again."
            ),
            coefficient_available=False,
            coefficient_message="No calibration coefficient artifact is available.",
        )

    def start_new_test(self) -> DashboardWizardState:
        """Start a fresh workflow only after the current run has finalized."""

        if not self._state.can_start_new_test:
            raise ProductRequestError("New test requires a finalized result")
        return self._replace(
            step=DashboardWizardStep.SOURCE,
            draft=DashboardWizardDraft(),
            review_lines=(),
            discovered_ports=(),
            issue=None,
            export_available=False,
            export_message="No finalized analysis export is available.",
            coefficient_available=False,
            coefficient_message="No calibration coefficient artifact is available.",
        )

    def present_review(
        self,
        draft: DashboardWizardDraft,
        review_lines: tuple[str, ...],
    ) -> DashboardWizardState:
        if self._state.step is not DashboardWizardStep.CONFIGURATION:
            raise ProductRequestError("review requires step 3 configuration")
        if not isinstance(draft, DashboardWizardDraft):
            raise ProductRequestError("draft must be a DashboardWizardDraft")
        if not isinstance(review_lines, tuple) or not review_lines:
            raise ProductRequestError("review_lines must be a non-empty tuple")
        return self._replace(
            step=DashboardWizardStep.REVIEW,
            draft=draft,
            review_lines=review_lines,
            issue=None,
        )

    def begin_run(self) -> DashboardWizardState:
        if not self._state.can_run:
            raise ProductRequestError(
                "Run requires a successful reviewed configuration"
            )
        return self._replace(
            step=DashboardWizardStep.RUN,
            issue=None,
            export_available=False,
            export_message="The worker is running; no export is finalized yet.",
            coefficient_available=False,
            coefficient_message="The worker is running; no coefficient artifact is finalized yet.",
        )

    def finish_run(
        self,
        *,
        export_available: bool,
        coefficient_available: bool = False,
    ) -> DashboardWizardState:
        if self._state.step is not DashboardWizardStep.RUN:
            raise ProductRequestError("only a running workflow can finish")
        if not isinstance(export_available, bool):
            raise ProductRequestError("export_available must be boolean")
        if not isinstance(coefficient_available, bool):
            raise ProductRequestError("coefficient_available must be boolean")
        message = (
            "A finalized analysis export is available; choose a new JSON or CSV path."
            if export_available
            else "This result has no analysis bundle to export; the visible result remains available."
        )
        return self._replace(
            step=DashboardWizardStep.RESULT,
            export_available=export_available,
            export_message=message,
            coefficient_available=coefficient_available,
            coefficient_message=(
                "Calibration coefficients are ready to save as a new JSON file."
                if coefficient_available
                else "No calibration coefficient artifact is available for this result."
            ),
        )

    def present_ports(self, ports: tuple[SerialPortInfo, ...]) -> DashboardWizardState:
        if self._state.draft.source_mode is not ProductSourceMode.SERIAL_READ_ONLY:
            raise ProductRequestError("port discovery requires the Serial source")
        if not isinstance(ports, tuple):
            raise ProductRequestError("ports must be a tuple")
        return self._replace(discovered_ports=ports, issue=None)

    def present_issue(self, issue: UserIssue) -> DashboardWizardState:
        if not isinstance(issue, UserIssue):
            raise ProductRequestError("issue must be a UserIssue")
        return self._replace(issue=issue)

    def present_export(self, filename: str) -> DashboardWizardState:
        if not self._state.can_export:
            raise ProductRequestError("no finalized analysis export is available")
        checked = _text("filename", filename)
        return self._replace(export_message=f"Exported safely: {checked}", issue=None)

    def present_coefficient_artifact(self, message: str) -> DashboardWizardState:
        if self._state.step is not DashboardWizardStep.RESULT:
            raise ProductRequestError(
                "calibration coefficient files can only be managed on the Result step"
            )
        return self._replace(
            coefficient_message=_text("coefficient message", message),
            issue=None,
        )


__all__ = [
    "DASHBOARD_WIZARD_SCHEMA_VERSION",
    "MAX_DASHBOARD_WIZARD_PORTS",
    "MAX_DASHBOARD_WIZARD_REVIEW_LINES",
    "MAX_DASHBOARD_WIZARD_TEXT_CHARS",
    "DashboardExportFormat",
    "DashboardWizardDraft",
    "DashboardWizardGuidance",
    "DashboardWizardPresenter",
    "DashboardWizardState",
    "DashboardWizardStep",
]
