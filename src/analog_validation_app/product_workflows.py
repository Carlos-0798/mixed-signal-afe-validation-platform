"""Shared reviewed workflow configuration for CLI and Dashboard consumers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from analog_validation import (
    ChannelReadRequest,
    CsvReplayAdapterConfig,
    MeasurementUnit,
    ReadOperation,
    ReadWorkflowRequest,
    ReplayChannelConfig,
    ReplayChannelKind,
    SafeRange,
    SimulatorConfig,
)
from analog_validation.analysis import (
    DCSweepAcceptanceCriteria,
    DCSweepAnalysisConfig,
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
    make_serial_adapter_factory,
    make_simulator_adapter_factory,
)
from .models import ProductJobRequest, ProductJobType, ProductSourceMode
from .services import (
    ProductServiceOutputSlot,
    make_dc_sweep_service_factory,
    make_hysteresis_service_factory,
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
    minimum_high_threshold: float = 900.0
    maximum_high_threshold: float = 1100.0
    minimum_low_threshold: float = 800.0
    maximum_low_threshold: float = 1000.0
    minimum_width: float = 20.0
    maximum_width: float = 200.0
    maximum_width_span: float = 0.0
    schema_version: str = PRODUCT_WORKFLOW_CONFIG_SCHEMA_VERSION

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
        ):
            _text(name, getattr(self, name))
        if not isinstance(self.operation, ReadOperation):
            raise ProductRequestError("operation must be a ReadOperation")
        if not isinstance(self.unit, MeasurementUnit):
            raise ProductRequestError("unit must be a MeasurementUnit")
        _sample_count("sample_count", self.sample_count)
        _sample_count("rising_count", self.rising_count, minimum=2)
        _sample_count("falling_count", self.falling_count, minimum=2)
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
            "minimum_high_threshold",
            "maximum_high_threshold",
            "minimum_low_threshold",
            "maximum_low_threshold",
            "minimum_width",
            "maximum_width",
            "maximum_width_span",
        ):
            _finite(name, getattr(self, name))
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
        if self.primary_channel == self.state_channel:
            raise ProductRequestError("hysteresis input and state channels must differ")


@dataclass(frozen=True, slots=True)
class PreparedProductJob:
    """A reviewed request and deferred worker service with an output handoff."""

    request: ProductJobRequest
    service_factory: ProductJobServiceFactory
    output_slot: ProductServiceOutputSlot
    review_lines: tuple[str, ...]

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
    elif config.job_type is ProductJobType.DC_ANALYSIS:
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
) -> PreparedProductJob:
    """Validate all user-controlled inputs before binding a deferred service."""

    if not isinstance(config, ProductWorkflowConfiguration):
        raise ProductRequestError("config must be a ProductWorkflowConfiguration")
    _text("job_id", job_id)
    if not callable(backend_factory):
        raise ProductRequestError("backend_factory must be callable")
    if not isinstance(prevalidate_replay, bool):
        raise ProductRequestError("prevalidate_replay must be boolean")
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
        service_factory = make_dc_sweep_service_factory(
            adapter_factory,
            dc_workflow,
            dc_analysis,
            dc_criteria,
            limitations,
            slot,
        )
        workflow_review = (
            f"Test: DC_ANALYSIS; {config.sample_count} paired points.",
            f"Channels: {config.primary_channel} -> {config.secondary_channel} ({config.unit.value}).",
            f"Unsaturated output window: {config.low_output_limit:g} to {config.high_output_limit:g} {config.unit.value}.",
            f"Reviewed target gain: {config.target_gain:g} +/- {config.gain_tolerance:g}.",
            f"Fit criteria: abs offset <= {config.max_abs_offset:g} {config.unit.value}; R^2 >= {config.min_r_squared:g}; RMSE <= {config.max_rmse:g} {config.unit.value}.",
        )
    else:
        hysteresis_workflow, hysteresis_analysis, hysteresis_criteria = (
            _hysteresis_parts(config)
        )
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
    return PreparedProductJob(request, service_factory, slot, review)


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
