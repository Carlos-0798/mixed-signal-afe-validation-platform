"""Shared reviewed workflow configuration for CLI and Dashboard consumers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from analog_validation import (
    ChannelReadRequest,
    CsvReplayAdapterConfig,
    FrequencyResponseSimulatorConfig,
    MeasurementUnit,
    ReadOperation,
    ReadWorkflowRequest,
    ReplayChannelConfig,
    ReplayChannelKind,
    SafeRange,
    SimulatorConfig,
)
from analog_validation.analysis import (
    CalibrationAcceptanceCriteria,
    CalibrationFitConfig,
    DCSweepAcceptanceCriteria,
    DCSweepAnalysisConfig,
    FrequencyResponseAcceptanceCriteria,
    FrequencyResponseAnalysisConfig,
    HysteresisAcceptanceCriteria,
    HysteresisAnalysisConfig,
)
from analog_validation.replay import load_csv_replay

from .catalog import get_product_profile, get_product_source
from .errors import ProductRequestError
from .factories import (
    AdapterFactory,
    SerialBackendFactory,
    SerialSourceConfig,
    default_serial_backend_factory,
    make_csv_replay_adapter_factory,
    make_csv_replay_dataset_adapter_factory,
    make_frequency_response_simulator_adapter_factory,
    make_serial_adapter_factory,
    make_simulator_adapter_factory,
)
from .live import (
    DEFAULT_LIVE_MONITOR_MAX_POINTS,
    MAX_LIVE_MONITOR_DURATION_SECONDS,
    MAX_LIVE_MONITOR_INTERVAL_SECONDS,
    MAX_LIVE_MONITOR_WINDOW_SECONDS,
    MIN_LIVE_MONITOR_WINDOW_SECONDS,
    LiveMonitorSession,
)
from .models import ProductJobRequest, ProductJobType, ProductSourceMode
from .services import (
    Clock,
    ProductServiceOutputSlot,
    make_calibration_service_factory,
    make_dc_sweep_service_factory,
    make_frequency_response_service_factory,
    make_hysteresis_service_factory,
    make_live_monitor_service_factory,
    make_read_service_factory,
)
from .worker import ProductJobServiceFactory

PRODUCT_WORKFLOW_CONFIG_SCHEMA_VERSION = "product-workflow-config.v1"
MAX_PRODUCT_WORKFLOW_SAMPLES = 10_000
MAX_PRODUCT_WORKFLOW_TEXT_CHARS = 1_024

SIMULATOR_LIMITATIONS = (
    "Synthetic software observations only; no physical hardware was measured.",
    "A software PASS or FAIL does not validate an assembled analog front end.",
)
REPLAY_LIMITATIONS = (
    "Results describe a local CSV replay under the declared channel mapping.",
    "Replay analysis does not prove current hardware wiring or performance.",
)
SERIAL_LIMITATIONS = (
    "Receive-only host integration; no command or serial write was issued.",
    "Received records alone do not prove calibrated AFE performance or safe wiring.",
)


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ProductRequestError(f"{name} must be non-empty stripped text")
    if len(value) > MAX_PRODUCT_WORKFLOW_TEXT_CHARS:
        raise ProductRequestError(
            f"{name} exceeds {MAX_PRODUCT_WORKFLOW_TEXT_CHARS} characters"
        )
    if not value.isprintable():
        raise ProductRequestError(f"{name} must contain only printable characters")
    return value


def _sample_count(name: str, value: object, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProductRequestError(f"{name} must be an integer")
    if not minimum <= value <= MAX_PRODUCT_WORKFLOW_SAMPLES:
        raise ProductRequestError(
            f"{name} must be between {minimum} and {MAX_PRODUCT_WORKFLOW_SAMPLES}"
        )
    return value


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProductRequestError(f"{name} must be numeric")
    checked = float(value)
    if not math.isfinite(checked):
        raise ProductRequestError(f"{name} must be finite")
    return checked


@dataclass(frozen=True, slots=True)
class ProductWorkflowConfiguration:
    """One typed, read-only configuration shared by product presentation layers."""

    source_mode: ProductSourceMode
    job_type: ProductJobType
    profile_name: str = "afe"
    profile_version: str = "1"
    primary_channel: str = "afe.ch0.input"
    secondary_channel: str = "afe.ch0.output"
    state_channel: str = "afe.ch0.threshold"
    operation: ReadOperation = ReadOperation.ANALOG
    unit: MeasurementUnit = MeasurementUnit.MILLIVOLT
    sample_count: int = 5
    rising_count: int = 12
    falling_count: int = 22
    replay_path: Path | None = None
    replay_minimum: float = 0.0
    replay_maximum: float = 3300.0
    serial_config: SerialSourceConfig | None = None
    confirm_read_only: bool = False
    low_output_limit: float = 25.0
    high_output_limit: float = 3275.0
    target_gain: float = 2.0
    gain_tolerance: float = 0.05
    max_abs_offset: float = 25.0
    min_r_squared: float = 0.999
    max_rmse: float = 1.0
    coefficient_id: str = "afe-linear-calibration"
    coefficient_version: str = "1"
    max_calibration_rmse: float = 1.0
    max_calibration_mean_absolute_error: float = 1.0
    max_calibration_absolute_error: float = 2.0
    minimum_calibration_rmse_reduction: float = 0.0
    minimum_high_threshold: float = 900.0
    maximum_high_threshold: float = 1100.0
    minimum_low_threshold: float = 800.0
    maximum_low_threshold: float = 1000.0
    minimum_width: float = 20.0
    maximum_width: float = 200.0
    maximum_width_span: float = 0.0
    schema_version: str = PRODUCT_WORKFLOW_CONFIG_SCHEMA_VERSION
    frequency_channel: str = "afe.ch0.frequency"
    frequency_point_count: int = 21
    frequency_minimum_hz: float = 10.0
    frequency_maximum_hz: float = 100_000.0
    frequency_input_amplitude: float = 1_000.0
    simulated_cutoff_frequency_hz: float = 1_000.0
    target_cutoff_frequency_hz: float = 1_000.0
    cutoff_relative_tolerance: float = 0.15
    cutoff_drop_db: float = 3.010299956639812
    monitor_sample_interval_seconds: float = 0.05
    monitor_time_window_seconds: float = 5.0
    monitor_max_buffer_points: int = DEFAULT_LIVE_MONITOR_MAX_POINTS
    monitor_include_secondary: bool = True
    monitor_include_state: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.source_mode, ProductSourceMode):
            raise ProductRequestError("source_mode must be a ProductSourceMode")
        if not isinstance(self.job_type, ProductJobType):
            raise ProductRequestError("job_type must be a ProductJobType")
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
        if not isinstance(self.operation, ReadOperation):
            raise ProductRequestError("operation must be a ReadOperation")
        if not isinstance(self.unit, MeasurementUnit):
            raise ProductRequestError("unit must be a MeasurementUnit")
        _sample_count("sample_count", self.sample_count)
        _sample_count("rising_count", self.rising_count, minimum=2)
        _sample_count("falling_count", self.falling_count, minimum=2)
        _sample_count("frequency_point_count", self.frequency_point_count, minimum=10)
        if self.rising_count + self.falling_count > MAX_PRODUCT_WORKFLOW_SAMPLES:
            raise ProductRequestError(
                "rising_count plus falling_count exceeds the workflow sample limit"
            )
        minimum = _finite("replay_minimum", self.replay_minimum)
        maximum = _finite("replay_maximum", self.replay_maximum)
        if minimum >= maximum:
            raise ProductRequestError("replay_minimum must be below replay_maximum")
        if not isinstance(self.confirm_read_only, bool):
            raise ProductRequestError("confirm_read_only must be boolean")
        for name in (
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
            "frequency_minimum_hz",
            "frequency_maximum_hz",
            "frequency_input_amplitude",
            "simulated_cutoff_frequency_hz",
            "target_cutoff_frequency_hz",
            "cutoff_relative_tolerance",
            "cutoff_drop_db",
            "monitor_sample_interval_seconds",
            "monitor_time_window_seconds",
        ):
            _finite(name, getattr(self, name))
        _sample_count("monitor_max_buffer_points", self.monitor_max_buffer_points)
        for name in ("monitor_include_secondary", "monitor_include_state"):
            if not isinstance(getattr(self, name), bool):
                raise ProductRequestError(f"{name} must be boolean")
        source = get_product_source(self.source_mode)
        profile = get_product_profile(self.profile_name, self.profile_version)
        if self.source_mode not in profile.source_modes:
            raise ProductRequestError(
                f"profile {profile.identity} does not support {self.source_mode.value}"
            )
        if self.job_type not in source.supported_jobs:
            raise ProductRequestError(
                f"source {source.mode.value} does not support {self.job_type.value}"
            )
        self._validate_source_fields()
        self._validate_job_fields()
        if self.schema_version != PRODUCT_WORKFLOW_CONFIG_SCHEMA_VERSION:
            raise ProductRequestError(
                f"unsupported product workflow config schema: {self.schema_version}"
            )

    def _validate_source_fields(self) -> None:
        if self.source_mode is ProductSourceMode.SIMULATOR:
            if self.replay_path is not None or self.serial_config is not None:
                raise ProductRequestError(
                    "Simulator configuration cannot include replay or serial resources"
                )
            if self.confirm_read_only:
                raise ProductRequestError(
                    "Simulator configuration does not use a serial confirmation"
                )
            return
        if self.source_mode is ProductSourceMode.CSV_REPLAY:
            if not isinstance(self.replay_path, Path):
                raise ProductRequestError("CSV Replay requires a local replay_path")
            if self.serial_config is not None or self.confirm_read_only:
                raise ProductRequestError(
                    "CSV Replay configuration cannot include serial settings"
                )
            return
        if self.replay_path is not None:
            raise ProductRequestError("Serial configuration cannot include replay_path")
        if not isinstance(self.serial_config, SerialSourceConfig):
            raise ProductRequestError("Serial source requires SerialSourceConfig")
        if not self.confirm_read_only:
            raise ProductRequestError(
                "Serial source requires explicit receive-only confirmation"
            )

    def _validate_job_fields(self) -> None:
        if self.job_type is ProductJobType.READ:
            if self.operation is ReadOperation.DIGITAL:
                if self.unit is not MeasurementUnit.BOOLEAN:
                    raise ProductRequestError("digital reads require boolean units")
            elif self.unit is MeasurementUnit.BOOLEAN:
                raise ProductRequestError("analog reads cannot use boolean units")
            return
        if self.unit not in {MeasurementUnit.MILLIVOLT, MeasurementUnit.VOLT}:
            raise ProductRequestError("analysis workflows require V or mV units")
        if self.job_type is ProductJobType.DC_ANALYSIS:
            if self.primary_channel == self.secondary_channel:
                raise ProductRequestError("DC input and output channels must differ")
            return
        if self.job_type is ProductJobType.CALIBRATION_ANALYSIS:
            if self.primary_channel == self.secondary_channel:
                raise ProductRequestError(
                    "calibration observed and reference channels must differ"
                )
            if any(
                value < 0.0
                for value in (
                    self.max_calibration_rmse,
                    self.max_calibration_mean_absolute_error,
                    self.max_calibration_absolute_error,
                    self.minimum_calibration_rmse_reduction,
                )
            ):
                raise ProductRequestError(
                    "calibration error limits and reduction cannot be negative"
                )
            return
        if self.job_type is ProductJobType.FREQUENCY_RESPONSE_ANALYSIS:
            channels = (
                self.frequency_channel,
                self.primary_channel,
                self.secondary_channel,
            )
            if len(set(channels)) != 3:
                raise ProductRequestError(
                    "frequency, input-amplitude, and output-amplitude channels must differ"
                )
            if not (
                0.0
                < self.frequency_minimum_hz
                < self.target_cutoff_frequency_hz
                < self.frequency_maximum_hz
            ):
                raise ProductRequestError(
                    "frequency bounds must satisfy 0 < minimum < target cutoff < maximum"
                )
            if not (
                self.frequency_minimum_hz
                < self.simulated_cutoff_frequency_hz
                < self.frequency_maximum_hz
            ):
                raise ProductRequestError(
                    "frequency bounds must contain the simulated cutoff"
                )
            if not 0.0 <= self.cutoff_relative_tolerance < 1.0:
                raise ProductRequestError(
                    "cutoff_relative_tolerance must be at least zero and below one"
                )
            if self.cutoff_drop_db <= 0.0:
                raise ProductRequestError("cutoff_drop_db must be positive")
            amplitude_maximum = 3.3 if self.unit is MeasurementUnit.VOLT else 3300.0
            if not 0.0 < self.frequency_input_amplitude <= amplitude_maximum:
                raise ProductRequestError(
                    "frequency_input_amplitude must be positive and within 3.3 V"
                )
            return
        if self.job_type is ProductJobType.LIVE_MONITOR:
            if self.operation is not ReadOperation.ANALOG:
                raise ProductRequestError(
                    "live monitor primary channel must use analog operation"
                )
            if (
                not 0.0
                <= self.monitor_sample_interval_seconds
                <= (MAX_LIVE_MONITOR_INTERVAL_SECONDS)
            ):
                raise ProductRequestError(
                    "monitor_sample_interval_seconds must be between 0 and "
                    f"{MAX_LIVE_MONITOR_INTERVAL_SECONDS:g}"
                )
            if (
                not MIN_LIVE_MONITOR_WINDOW_SECONDS
                <= (self.monitor_time_window_seconds)
                <= MAX_LIVE_MONITOR_WINDOW_SECONDS
            ):
                raise ProductRequestError(
                    "monitor_time_window_seconds must be between "
                    f"{MIN_LIVE_MONITOR_WINDOW_SECONDS:g} and "
                    f"{MAX_LIVE_MONITOR_WINDOW_SECONDS:g}"
                )
            duration_seconds = (
                max(0, self.sample_count - 1) * self.monitor_sample_interval_seconds
            )
            if duration_seconds > MAX_LIVE_MONITOR_DURATION_SECONDS:
                raise ProductRequestError(
                    "live monitor requested duration exceeds the interactive "
                    f"limit of {MAX_LIVE_MONITOR_DURATION_SECONDS:g} seconds"
                )
            channel_identities = (
                self.primary_channel,
                self.secondary_channel,
                self.state_channel,
            )
            if len(channel_identities) != len(set(channel_identities)):
                raise ProductRequestError(
                    "live monitor channel identities must be distinct"
                )
            enabled_channel_count = (
                1
                + int(self.monitor_include_secondary)
                + int(self.monitor_include_state)
            )
            total_measurements = self.sample_count * enabled_channel_count
            if total_measurements > MAX_PRODUCT_WORKFLOW_SAMPLES:
                raise ProductRequestError(
                    "live monitor cycles multiplied by enabled channels exceeds "
                    "the workflow sample limit"
                )
            return
        if self.primary_channel == self.state_channel:
            raise ProductRequestError("hysteresis input and state channels must differ")


@dataclass(frozen=True, slots=True)
class PreparedProductJob:
    """A reviewed request and deferred worker service with an output handoff."""

    request: ProductJobRequest
    service_factory: ProductJobServiceFactory
    output_slot: ProductServiceOutputSlot
    review_lines: tuple[str, ...]
    live_monitor_session: LiveMonitorSession | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request, ProductJobRequest):
            raise ProductRequestError("request must be a ProductJobRequest")
        if not callable(self.service_factory):
            raise ProductRequestError("service_factory must be callable")
        if not isinstance(self.output_slot, ProductServiceOutputSlot):
            raise ProductRequestError("output_slot must be ProductServiceOutputSlot")
        if not isinstance(self.review_lines, tuple) or not self.review_lines:
            raise ProductRequestError("review_lines must be a non-empty tuple")
        for line in self.review_lines:
            _text("review line", line)
        if self.live_monitor_session is not None and not isinstance(
            self.live_monitor_session, LiveMonitorSession
        ):
            raise ProductRequestError(
                "live_monitor_session must be a LiveMonitorSession or None"
            )
        if (self.request.job_type is ProductJobType.LIVE_MONITOR) != (
            self.live_monitor_session is not None
        ):
            raise ProductRequestError(
                "only LIVE_MONITOR jobs require a live_monitor_session"
            )


def _replay_channel(
    name: str,
    kind: ReplayChannelKind,
    unit: MeasurementUnit,
    minimum: float,
    maximum: float,
) -> ReplayChannelConfig:
    if kind is ReplayChannelKind.DIGITAL:
        return ReplayChannelConfig(name, kind, MeasurementUnit.BOOLEAN)
    return ReplayChannelConfig(name, kind, unit, SafeRange(minimum, maximum, unit))


def _adapter_factory(
    config: ProductWorkflowConfiguration,
    *,
    backend_factory: SerialBackendFactory,
    prevalidate_replay: bool,
) -> tuple[AdapterFactory, tuple[str, ...]]:
    if config.source_mode is ProductSourceMode.SIMULATOR:
        if config.job_type is ProductJobType.FREQUENCY_RESPONSE_ANALYSIS:
            frequency_simulator = FrequencyResponseSimulatorConfig(
                point_count=config.frequency_point_count,
                frequency_minimum_hz=config.frequency_minimum_hz,
                frequency_maximum_hz=config.frequency_maximum_hz,
                cutoff_frequency_hz=config.simulated_cutoff_frequency_hz,
                input_amplitude=config.frequency_input_amplitude,
                amplitude_unit=config.unit,
                profile_name=config.profile_name,
                profile_version=config.profile_version,
                frequency_channel=config.frequency_channel,
                input_amplitude_channel=config.primary_channel,
                output_amplitude_channel=config.secondary_channel,
            )
            return make_frequency_response_simulator_adapter_factory(
                frequency_simulator
            ), (
                "Source: deterministic frequency-response Simulator; evidence remains SYNTHETIC.",
                (
                    "Simulator model: reference-normalized single-pole low-pass; "
                    f"modeled cutoff {config.simulated_cutoff_frequency_hz:g} Hz; "
                    "no stimulus was driven."
                ),
            )
        if config.job_type is ProductJobType.LIVE_MONITOR:
            simulator = SimulatorConfig(
                profile_name=config.profile_name,
                profile_version=config.profile_version,
                analog_channel=config.primary_channel,
                output_channel=config.secondary_channel,
                threshold_channel=config.state_channel,
            )
        else:
            simulator = SimulatorConfig(
                profile_name=config.profile_name,
                profile_version=config.profile_version,
            )
        return make_simulator_adapter_factory(simulator), (
            "Source: deterministic Simulator; evidence remains SYNTHETIC.",
        )
    if config.source_mode is ProductSourceMode.SERIAL_READ_ONLY:
        serial = config.serial_config
        if serial is None:  # pragma: no cover - guarded by the configuration
            raise ProductRequestError("SerialSourceConfig is missing")
        return make_serial_adapter_factory(serial, backend_factory=backend_factory), (
            f"Serial port: {serial.port_id}; it opens only after Run.",
            f"Serial bounds: {serial.read_timeout_seconds:g} s/read, {serial.max_polls_per_operation} polls.",
            "Receive-only confirmation: YES; the product exposes no write command.",
        )

    replay_path = config.replay_path
    if replay_path is None:  # pragma: no cover - guarded by the configuration
        raise ProductRequestError("replay_path is missing")
    channels: tuple[ReplayChannelConfig, ...]
    if config.job_type is ProductJobType.READ:
        channels = (
            _replay_channel(
                config.primary_channel,
                ReplayChannelKind.ANALOG
                if config.operation is ReadOperation.ANALOG
                else ReplayChannelKind.DIGITAL,
                config.unit,
                config.replay_minimum,
                config.replay_maximum,
            ),
        )
    elif config.job_type is ProductJobType.LIVE_MONITOR:
        live_channels = [
            _replay_channel(
                config.primary_channel,
                ReplayChannelKind.ANALOG,
                config.unit,
                config.replay_minimum,
                config.replay_maximum,
            )
        ]
        if config.monitor_include_secondary:
            live_channels.append(
                _replay_channel(
                    config.secondary_channel,
                    ReplayChannelKind.ANALOG,
                    config.unit,
                    config.replay_minimum,
                    config.replay_maximum,
                )
            )
        if config.monitor_include_state:
            live_channels.append(
                _replay_channel(
                    config.state_channel,
                    ReplayChannelKind.DIGITAL,
                    MeasurementUnit.BOOLEAN,
                    config.replay_minimum,
                    config.replay_maximum,
                )
            )
        channels = tuple(live_channels)
    elif config.job_type in {
        ProductJobType.DC_ANALYSIS,
        ProductJobType.CALIBRATION_ANALYSIS,
    }:
        channels = (
            _replay_channel(
                config.primary_channel,
                ReplayChannelKind.ANALOG,
                config.unit,
                config.replay_minimum,
                config.replay_maximum,
            ),
            _replay_channel(
                config.secondary_channel,
                ReplayChannelKind.ANALOG,
                config.unit,
                config.replay_minimum,
                config.replay_maximum,
            ),
        )
    elif config.job_type is ProductJobType.FREQUENCY_RESPONSE_ANALYSIS:
        channels = (
            _replay_channel(
                config.frequency_channel,
                ReplayChannelKind.ANALOG,
                MeasurementUnit.HERTZ,
                config.frequency_minimum_hz,
                config.frequency_maximum_hz,
            ),
            _replay_channel(
                config.primary_channel,
                ReplayChannelKind.ANALOG,
                config.unit,
                config.replay_minimum,
                config.replay_maximum,
            ),
            _replay_channel(
                config.secondary_channel,
                ReplayChannelKind.ANALOG,
                config.unit,
                config.replay_minimum,
                config.replay_maximum,
            ),
        )
    else:
        channels = (
            _replay_channel(
                config.primary_channel,
                ReplayChannelKind.ANALOG,
                config.unit,
                config.replay_minimum,
                config.replay_maximum,
            ),
            _replay_channel(
                config.state_channel,
                ReplayChannelKind.DIGITAL,
                MeasurementUnit.BOOLEAN,
                config.replay_minimum,
                config.replay_maximum,
            ),
        )
    replay_config = CsvReplayAdapterConfig(
        channels,
        profile_name=config.profile_name,
        profile_version=config.profile_version,
    )
    if not prevalidate_replay:
        return make_csv_replay_adapter_factory(replay_path, replay_config), (
            f"Replay file selected: {replay_path.name}; validation occurs in the bounded worker.",
        )
    dataset = load_csv_replay(replay_path)
    return make_csv_replay_dataset_adapter_factory(dataset, replay_config), (
        f"Replay file validated before Run: {replay_path.name}.",
        f"Replay dataset: {dataset.dataset_id}; {len(dataset)} bounded records.",
    )


def _read_workflow(config: ProductWorkflowConfiguration) -> ReadWorkflowRequest:
    return ReadWorkflowRequest(
        (
            ChannelReadRequest(
                config.primary_channel,
                config.operation,
                config.unit,
                config.sample_count,
            ),
        ),
        request_id="product-read",
    )


def _live_monitor_workflow(
    config: ProductWorkflowConfiguration,
) -> ReadWorkflowRequest:
    requirements = [
        ChannelReadRequest(
            config.primary_channel,
            ReadOperation.ANALOG,
            config.unit,
            config.sample_count,
        )
    ]
    if config.monitor_include_secondary:
        requirements.append(
            ChannelReadRequest(
                config.secondary_channel,
                ReadOperation.ANALOG,
                config.unit,
                config.sample_count,
            )
        )
    if config.monitor_include_state:
        requirements.append(
            ChannelReadRequest(
                config.state_channel,
                ReadOperation.DIGITAL,
                MeasurementUnit.BOOLEAN,
                config.sample_count,
            )
        )
    return ReadWorkflowRequest(
        tuple(requirements),
        request_id="product-live-monitor",
    )


def _dc_parts(
    config: ProductWorkflowConfiguration,
) -> tuple[ReadWorkflowRequest, DCSweepAnalysisConfig, DCSweepAcceptanceCriteria]:
    workflow = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                config.primary_channel,
                ReadOperation.ANALOG,
                config.unit,
                config.sample_count,
            ),
            ChannelReadRequest(
                config.secondary_channel,
                ReadOperation.ANALOG,
                config.unit,
                config.sample_count,
            ),
        ),
        request_id="product-dc-sweep",
    )
    analysis = DCSweepAnalysisConfig(
        config.primary_channel,
        config.secondary_channel,
        config.low_output_limit,
        config.high_output_limit,
        config.unit,
    )
    criteria = DCSweepAcceptanceCriteria(
        "product-dc-default",
        "1",
        config.target_gain,
        config.gain_tolerance,
        config.max_abs_offset,
        config.min_r_squared,
        config.max_rmse,
        3,
        config.unit,
    )
    return workflow, analysis, criteria


def _calibration_parts(
    config: ProductWorkflowConfiguration,
) -> tuple[
    ReadWorkflowRequest,
    CalibrationFitConfig,
    CalibrationAcceptanceCriteria,
]:
    workflow = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                config.primary_channel,
                ReadOperation.ANALOG,
                config.unit,
                config.sample_count,
            ),
            ChannelReadRequest(
                config.secondary_channel,
                ReadOperation.ANALOG,
                config.unit,
                config.sample_count,
            ),
        ),
        request_id="product-calibration",
    )
    analysis = CalibrationFitConfig(
        config.primary_channel,
        config.secondary_channel,
        config.coefficient_id,
        config.coefficient_version,
        config.unit,
        3,
    )
    criteria = CalibrationAcceptanceCriteria(
        "product-calibration-default",
        "1",
        config.max_calibration_rmse,
        config.max_calibration_mean_absolute_error,
        config.max_calibration_absolute_error,
        config.minimum_calibration_rmse_reduction,
        3,
        config.unit,
    )
    return workflow, analysis, criteria


def _frequency_response_parts(
    config: ProductWorkflowConfiguration,
) -> tuple[
    ReadWorkflowRequest,
    FrequencyResponseAnalysisConfig,
    FrequencyResponseAcceptanceCriteria,
]:
    workflow = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                config.frequency_channel,
                ReadOperation.ANALOG,
                MeasurementUnit.HERTZ,
                config.frequency_point_count,
            ),
            ChannelReadRequest(
                config.primary_channel,
                ReadOperation.ANALOG,
                config.unit,
                config.frequency_point_count,
            ),
            ChannelReadRequest(
                config.secondary_channel,
                ReadOperation.ANALOG,
                config.unit,
                config.frequency_point_count,
            ),
        ),
        request_id="product-frequency-response",
    )
    analysis = FrequencyResponseAnalysisConfig(
        config.frequency_channel,
        config.primary_channel,
        config.secondary_channel,
        config.unit,
        config.cutoff_drop_db,
        10,
    )
    criteria = FrequencyResponseAcceptanceCriteria(
        "product-frequency-response-default",
        "1",
        config.target_cutoff_frequency_hz,
        config.cutoff_relative_tolerance,
        10,
    )
    return workflow, analysis, criteria


def _hysteresis_parts(
    config: ProductWorkflowConfiguration,
) -> tuple[
    ReadWorkflowRequest,
    HysteresisAnalysisConfig,
    HysteresisAcceptanceCriteria,
]:
    count = config.rising_count + config.falling_count
    workflow = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                config.primary_channel,
                ReadOperation.ANALOG,
                config.unit,
                count,
            ),
            ChannelReadRequest(
                config.state_channel,
                ReadOperation.DIGITAL,
                MeasurementUnit.BOOLEAN,
                count,
            ),
        ),
        request_id="product-hysteresis",
    )
    analysis = HysteresisAnalysisConfig(
        config.primary_channel,
        config.state_channel,
        config.unit,
    )
    criteria = HysteresisAcceptanceCriteria(
        "product-hysteresis-default",
        "1",
        config.minimum_high_threshold,
        config.maximum_high_threshold,
        config.minimum_low_threshold,
        config.maximum_low_threshold,
        config.minimum_width,
        config.maximum_width,
        config.maximum_width_span,
        1,
        config.unit,
    )
    return workflow, analysis, criteria


def prepare_product_job(
    config: ProductWorkflowConfiguration,
    job_id: str,
    *,
    backend_factory: SerialBackendFactory = default_serial_backend_factory,
    prevalidate_replay: bool = True,
    service_clock: Clock | None = None,
) -> PreparedProductJob:
    """Validate all user-controlled inputs before binding a deferred service."""

    if not isinstance(config, ProductWorkflowConfiguration):
        raise ProductRequestError("config must be a ProductWorkflowConfiguration")
    _text("job_id", job_id)
    if not callable(backend_factory):
        raise ProductRequestError("backend_factory must be callable")
    if not isinstance(prevalidate_replay, bool):
        raise ProductRequestError("prevalidate_replay must be boolean")
    if service_clock is not None and not callable(service_clock):
        raise ProductRequestError("service_clock must be callable or None")
    request = ProductJobRequest(
        job_id,
        config.source_mode,
        config.job_type,
        config.profile_name,
        config.profile_version,
    )
    adapter_factory, source_review = _adapter_factory(
        config,
        backend_factory=backend_factory,
        prevalidate_replay=prevalidate_replay,
    )
    slot = ProductServiceOutputSlot()
    live_session: LiveMonitorSession | None = None
    limitations = {
        ProductSourceMode.SIMULATOR: SIMULATOR_LIMITATIONS,
        ProductSourceMode.CSV_REPLAY: REPLAY_LIMITATIONS,
        ProductSourceMode.SERIAL_READ_ONLY: SERIAL_LIMITATIONS,
    }[config.source_mode]
    workflow_review: tuple[str, ...]
    if config.job_type is ProductJobType.READ:
        service_factory = make_read_service_factory(
            adapter_factory, _read_workflow(config), limitations, slot
        )
        workflow_review = (
            f"Test: READ; {config.sample_count} samples from {config.primary_channel}.",
            f"Operation/unit: {config.operation.value}/{config.unit.value}.",
        )
    elif config.job_type is ProductJobType.DC_ANALYSIS:
        dc_workflow, dc_analysis, dc_criteria = _dc_parts(config)
        if service_clock is None:
            service_factory = make_dc_sweep_service_factory(
                adapter_factory,
                dc_workflow,
                dc_analysis,
                dc_criteria,
                limitations,
                slot,
            )
        else:
            service_factory = make_dc_sweep_service_factory(
                adapter_factory,
                dc_workflow,
                dc_analysis,
                dc_criteria,
                limitations,
                slot,
                clock=service_clock,
            )
        workflow_review = (
            f"Test: DC_ANALYSIS; {config.sample_count} paired points.",
            f"Channels: {config.primary_channel} -> {config.secondary_channel} ({config.unit.value}).",
            f"Unsaturated output window: {config.low_output_limit:g} to {config.high_output_limit:g} {config.unit.value}.",
            f"Reviewed target gain: {config.target_gain:g} +/- {config.gain_tolerance:g}.",
            f"Fit criteria: abs offset <= {config.max_abs_offset:g} {config.unit.value}; R^2 >= {config.min_r_squared:g}; RMSE <= {config.max_rmse:g} {config.unit.value}.",
        )
    elif config.job_type is ProductJobType.CALIBRATION_ANALYSIS:
        calibration_workflow, calibration_analysis, calibration_criteria = (
            _calibration_parts(config)
        )
        if service_clock is None:
            service_factory = make_calibration_service_factory(
                adapter_factory,
                calibration_workflow,
                calibration_analysis,
                calibration_criteria,
                limitations,
                slot,
            )
        else:
            service_factory = make_calibration_service_factory(
                adapter_factory,
                calibration_workflow,
                calibration_analysis,
                calibration_criteria,
                limitations,
                slot,
                clock=service_clock,
            )
        workflow_review = (
            f"Test: CALIBRATION_ANALYSIS; {config.sample_count} observed/reference pairs.",
            f"Channels: observed {config.primary_channel}; reference {config.secondary_channel} ({config.unit.value}).",
            f"Coefficient: {config.coefficient_id}/{config.coefficient_version}; linear reference fit.",
            f"After-error limits: RMSE <= {config.max_calibration_rmse:g}, mean absolute <= {config.max_calibration_mean_absolute_error:g}, max absolute <= {config.max_calibration_absolute_error:g} {config.unit.value}.",
            f"Required RMSE reduction: >= {config.minimum_calibration_rmse_reduction:g} {config.unit.value}.",
        )
    elif config.job_type is ProductJobType.FREQUENCY_RESPONSE_ANALYSIS:
        frequency_workflow, frequency_analysis, frequency_criteria = (
            _frequency_response_parts(config)
        )
        if service_clock is None:
            service_factory = make_frequency_response_service_factory(
                adapter_factory,
                frequency_workflow,
                frequency_analysis,
                frequency_criteria,
                limitations,
                slot,
            )
        else:
            service_factory = make_frequency_response_service_factory(
                adapter_factory,
                frequency_workflow,
                frequency_analysis,
                frequency_criteria,
                limitations,
                slot,
                clock=service_clock,
            )
        workflow_review = (
            f"Test: FREQUENCY_RESPONSE_ANALYSIS; {config.frequency_point_count} logarithmic points.",
            f"Channels: frequency {config.frequency_channel}; input {config.primary_channel}; output {config.secondary_channel} (Hz/{config.unit.value}).",
            f"Frequency window: {config.frequency_minimum_hz:g} to {config.frequency_maximum_hz:g} Hz.",
            f"Cutoff definition: reference gain minus {config.cutoff_drop_db:g} dB.",
            f"Reviewed cutoff target: {config.target_cutoff_frequency_hz:g} Hz +/- {config.cutoff_relative_tolerance * 100:g}%.",
            (
                "At least 10 frequency points are required; every requested point "
                "must be usable and strictly increasing for v1 cutoff publication."
            ),
        )
    elif config.job_type is ProductJobType.LIVE_MONITOR:
        live_session = LiveMonitorSession(
            max_points=config.monitor_max_buffer_points,
            time_window_seconds=config.monitor_time_window_seconds,
        )
        service_factory = make_live_monitor_service_factory(
            adapter_factory,
            _live_monitor_workflow(config),
            limitations,
            slot,
            live_session,
            sample_interval_seconds=config.monitor_sample_interval_seconds,
        )
        enabled_channels = [config.primary_channel]
        if config.monitor_include_secondary:
            enabled_channels.append(config.secondary_channel)
        if config.monitor_include_state:
            enabled_channels.append(config.state_channel)
        workflow_review = (
            f"Test: LIVE_MONITOR; {config.sample_count} finite sample cycles.",
            f"Enabled channels: {', '.join(enabled_channels)}.",
            f"Cadence: {config.monitor_sample_interval_seconds:g} s between cycles.",
            f"Requested duration: {max(0, config.sample_count - 1) * config.monitor_sample_interval_seconds:g} s (finite interactive session).",
            f"Presentation window: {config.monitor_time_window_seconds:g} s; retained-point limit: {config.monitor_max_buffer_points}.",
            "Pause/resume controls acquisition checkpoints; no background acquisition survives completion.",
        )
    else:
        hysteresis_workflow, hysteresis_analysis, hysteresis_criteria = (
            _hysteresis_parts(config)
        )
        if service_clock is None:
            service_factory = make_hysteresis_service_factory(
                adapter_factory,
                hysteresis_workflow,
                hysteresis_analysis,
                hysteresis_criteria,
                config.rising_count,
                config.falling_count,
                limitations,
                slot,
            )
        else:
            service_factory = make_hysteresis_service_factory(
                adapter_factory,
                hysteresis_workflow,
                hysteresis_analysis,
                hysteresis_criteria,
                config.rising_count,
                config.falling_count,
                limitations,
                slot,
                clock=service_clock,
            )
        workflow_review = (
            f"Test: HYSTERESIS_ANALYSIS; {config.rising_count} rising + {config.falling_count} falling points.",
            f"Channels: {config.primary_channel} + {config.state_channel} ({config.unit.value}/boolean).",
            f"High threshold window: {config.minimum_high_threshold:g} to {config.maximum_high_threshold:g} {config.unit.value}.",
            f"Low threshold window: {config.minimum_low_threshold:g} to {config.maximum_low_threshold:g} {config.unit.value}.",
            f"Width window: {config.minimum_width:g} to {config.maximum_width:g} {config.unit.value}; max span {config.maximum_width_span:g} {config.unit.value}.",
        )
    review = (
        f"Profile: {request.profile_identity}.",
        *source_review,
        *workflow_review,
        "Output permission: DENIED; this product workflow is read-only.",
        "Hardware performance validation: NOT CLAIMED.",
    )
    return PreparedProductJob(request, service_factory, slot, review, live_session)


__all__ = [
    "MAX_PRODUCT_WORKFLOW_SAMPLES",
    "MAX_PRODUCT_WORKFLOW_TEXT_CHARS",
    "PRODUCT_WORKFLOW_CONFIG_SCHEMA_VERSION",
    "REPLAY_LIMITATIONS",
    "SERIAL_LIMITATIONS",
    "SIMULATOR_LIMITATIONS",
    "PreparedProductJob",
    "ProductWorkflowConfiguration",
    "prepare_product_job",
]
