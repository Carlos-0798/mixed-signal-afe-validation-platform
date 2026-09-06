"""Explicit product adapter construction without device identity guessing."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from importlib.util import find_spec
from os import PathLike
from typing import Any

from analog_validation.adapters import (
    CsvReplayAdapter,
    CsvReplayAdapterConfig,
    DeviceAdapter,
    FrequencyResponseSimulatorAdapter,
    FrequencyResponseSimulatorConfig,
    SimulatorAdapter,
    SimulatorConfig,
)
from analog_validation.domain import EvidenceSource
from analog_validation.profiles import (
    AFE_V1_SERIAL_IDENTITY,
    MSP430_HEALTH_V1_SERIAL_IDENTITY,
    AfeV1SerialProfile,
    Msp430HealthV1SerialProfile,
    SerialProfile,
)
from analog_validation.replay import CsvReplayDataset, load_csv_replay
from analog_validation.serial_adapters import (
    SerialAdapter,
    SerialAdapterConfig,
    project_afe_v1_read_only_capabilities,
    project_identity_read_only_capabilities,
)
from analog_validation.transport import (
    DEFAULT_BAUD_RATE,
    DEFAULT_READ_TIMEOUT_SECONDS,
    MAX_BAUD_RATE,
    MAX_READ_TIMEOUT_SECONDS,
    SerialBackend,
    SerialConnectionSettings,
    SerialPortInfo,
    SerialSession,
)

from .catalog import get_product_profile, get_product_source
from .errors import ProductDependencyError, ProductRequestError
from .models import ProductJobRequest, ProductJobType, ProductSourceMode

AdapterFactory = Callable[[ProductJobRequest], DeviceAdapter]
SerialBackendFactory = Callable[[], SerialBackend]


def _validate_request(
    request: ProductJobRequest,
    source_mode: ProductSourceMode,
) -> None:
    if not isinstance(request, ProductJobRequest):
        raise ProductRequestError("request must be a ProductJobRequest")
    if request.source_mode is not source_mode:
        raise ProductRequestError(
            f"adapter factory requires {source_mode.value} source mode"
        )
    source = get_product_source(request.source_mode)
    profile = get_product_profile(request.profile_name, request.profile_version)
    if request.source_mode not in profile.source_modes:
        raise ProductRequestError(
            f"profile {profile.identity} does not support {request.source_mode.value}"
        )
    if request.job_type not in source.supported_jobs:
        raise ProductRequestError(
            f"source {source.mode.value} does not support {request.job_type.value}"
        )


def make_simulator_adapter_factory(config: SimulatorConfig) -> AdapterFactory:
    """Return a request-checked factory for one immutable simulator config."""

    if not isinstance(config, SimulatorConfig):
        raise ProductRequestError("config must be a SimulatorConfig")

    def create(request: ProductJobRequest) -> DeviceAdapter:
        _validate_request(request, ProductSourceMode.SIMULATOR)
        if (config.profile_name, config.profile_version) != (
            request.profile_name,
            request.profile_version,
        ):
            raise ProductRequestError(
                "simulator config does not match the requested profile identity"
            )
        return SimulatorAdapter(config)

    return create


def make_frequency_response_simulator_adapter_factory(
    config: FrequencyResponseSimulatorConfig,
) -> AdapterFactory:
    """Return a checked factory for one synthetic frequency-response sweep."""

    if not isinstance(config, FrequencyResponseSimulatorConfig):
        raise ProductRequestError("config must be a FrequencyResponseSimulatorConfig")

    def create(request: ProductJobRequest) -> DeviceAdapter:
        _validate_request(request, ProductSourceMode.SIMULATOR)
        if request.job_type is not ProductJobType.FREQUENCY_RESPONSE_ANALYSIS:
            raise ProductRequestError(
                "frequency-response simulator requires a FREQUENCY_RESPONSE_ANALYSIS job"
            )
        if (config.profile_name, config.profile_version) != (
            request.profile_name,
            request.profile_version,
        ):
            raise ProductRequestError(
                "frequency-response simulator config does not match the requested profile identity"
            )
        return FrequencyResponseSimulatorAdapter(config)

    return create


def make_csv_replay_adapter_factory(
    path: str | PathLike[str],
    config: CsvReplayAdapterConfig,
) -> AdapterFactory:
    """Load one bounded replay only when the worker constructs its service."""

    if not isinstance(path, (str, PathLike)):
        raise ProductRequestError("replay path must be path-like")
    if not isinstance(config, CsvReplayAdapterConfig):
        raise ProductRequestError("config must be a CsvReplayAdapterConfig")

    def create(request: ProductJobRequest) -> DeviceAdapter:
        dataset = load_csv_replay(path)
        return make_csv_replay_dataset_adapter_factory(dataset, config)(request)

    return create


def make_csv_replay_dataset_adapter_factory(
    dataset: CsvReplayDataset,
    config: CsvReplayAdapterConfig,
) -> AdapterFactory:
    """Bind an already-validated immutable replay snapshot to a worker factory."""

    if not isinstance(dataset, CsvReplayDataset):
        raise ProductRequestError("dataset must be a CsvReplayDataset")
    if not isinstance(config, CsvReplayAdapterConfig):
        raise ProductRequestError("config must be a CsvReplayAdapterConfig")

    def create(request: ProductJobRequest) -> DeviceAdapter:
        _validate_request(request, ProductSourceMode.CSV_REPLAY)
        if (config.profile_name, config.profile_version) != (
            request.profile_name,
            request.profile_version,
        ):
            raise ProductRequestError(
                "replay config does not match the requested profile identity"
            )
        selected_channels = {channel.name for channel in config.channels}
        selected_records = tuple(
            record for record in dataset.records if record.channel in selected_channels
        )
        projected = CsvReplayDataset(
            dataset.dataset_id,
            selected_records,
            len(selected_records),
        )
        return CsvReplayAdapter(projected, config)

    return create


def _finite_seconds(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProductRequestError(f"{name} must be numeric")
    checked = float(value)
    if not math.isfinite(checked) or not 0 < checked <= MAX_READ_TIMEOUT_SECONDS:
        raise ProductRequestError(
            f"{name} must be greater than zero up to {MAX_READ_TIMEOUT_SECONDS:g}"
        )
    return checked


@dataclass(frozen=True, slots=True)
class SerialSourceConfig:
    """Explicit bounded settings for one receive-only product job."""

    port_id: str
    baud_rate: int = DEFAULT_BAUD_RATE
    read_timeout_seconds: float = DEFAULT_READ_TIMEOUT_SECONDS
    max_polls_per_operation: int = 4
    max_buffered_measurements: int = 128
    evidence_source: EvidenceSource = EvidenceSource.BENCH_CONTROLLER

    def __post_init__(self) -> None:
        if (
            not isinstance(self.port_id, str)
            or not self.port_id
            or self.port_id != self.port_id.strip()
            or not self.port_id.isprintable()
        ):
            raise ProductRequestError(
                "port_id must be non-empty printable text without outer whitespace"
            )
        if (
            isinstance(self.baud_rate, bool)
            or not isinstance(self.baud_rate, int)
            or not 1 <= self.baud_rate <= MAX_BAUD_RATE
        ):
            raise ProductRequestError(
                f"baud_rate must be an integer between 1 and {MAX_BAUD_RATE}"
            )
        object.__setattr__(
            self,
            "read_timeout_seconds",
            _finite_seconds("read_timeout_seconds", self.read_timeout_seconds),
        )
        for name, maximum in (
            ("max_polls_per_operation", 10_000),
            ("max_buffered_measurements", 10_000),
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 1 <= value <= maximum
            ):
                raise ProductRequestError(
                    f"{name} must be an integer between 1 and {maximum}"
                )
        if self.evidence_source not in {
            EvidenceSource.HOST_TEST,
            EvidenceSource.BENCH_CONTROLLER,
        }:
            raise ProductRequestError(
                "serial evidence_source must be HOST_TEST or BENCH_CONTROLLER"
            )


def default_serial_backend_factory() -> SerialBackend:
    """Load the optional receive-only backend only after an explicit command."""

    if find_spec("serial") is None:
        raise ProductDependencyError(
            "optional serial support is unavailable; install the '[serial]' extra"
        )
    module = import_module("analog_validation_pyserial")
    backend_type = getattr(module, "PySerialBackend", None)
    if not callable(backend_type):
        raise ProductDependencyError(
            "optional serial backend entry point is unavailable"
        )
    return backend_type()  # type: ignore[no-any-return]


def discover_serial_ports(
    backend_factory: SerialBackendFactory = default_serial_backend_factory,
) -> tuple[SerialPortInfo, ...]:
    """Discover minimal logical port information without opening any port."""

    if not callable(backend_factory):
        raise ProductRequestError("backend_factory must be callable")
    backend = backend_factory()
    try:
        ports = backend.discover_ports()
        if not isinstance(ports, tuple) or not all(
            isinstance(port, SerialPortInfo) for port in ports
        ):
            raise ProductRequestError(
                "serial backend discovery must return SerialPortInfo values"
            )
        port_ids = tuple(port.port_id for port in ports)
        if len(port_ids) != len(set(port_ids)):
            raise ProductRequestError(
                "serial backend discovery returned duplicate port IDs"
            )
        return ports
    finally:
        backend.close()


def make_serial_adapter_factory(
    config: SerialSourceConfig,
    *,
    backend_factory: SerialBackendFactory = default_serial_backend_factory,
) -> AdapterFactory:
    """Construct one exact receive-only serial adapter inside the worker thread."""

    if not isinstance(config, SerialSourceConfig):
        raise ProductRequestError("config must be a SerialSourceConfig")
    if not callable(backend_factory):
        raise ProductRequestError("backend_factory must be callable")

    def create(request: ProductJobRequest) -> DeviceAdapter:
        _validate_request(request, ProductSourceMode.SERIAL_READ_ONLY)
        identity = (request.profile_name, request.profile_version)
        profile: SerialProfile[Any]
        if identity == (
            AFE_V1_SERIAL_IDENTITY.name,
            AFE_V1_SERIAL_IDENTITY.version,
        ):
            profile = AfeV1SerialProfile(evidence_source=config.evidence_source)
            serial_identity = AFE_V1_SERIAL_IDENTITY
            projector = project_afe_v1_read_only_capabilities
        elif identity == (
            MSP430_HEALTH_V1_SERIAL_IDENTITY.name,
            MSP430_HEALTH_V1_SERIAL_IDENTITY.version,
        ):
            profile = Msp430HealthV1SerialProfile(
                evidence_source=config.evidence_source
            )
            serial_identity = MSP430_HEALTH_V1_SERIAL_IDENTITY
            projector = project_identity_read_only_capabilities
        else:  # pragma: no cover - exact reviewed catalog preflight owns this invariant
            raise ProductRequestError("no serial adapter exists for this profile")
        settings = SerialConnectionSettings(
            port_id=config.port_id,
            profile_name=serial_identity.name,
            baud_rate=config.baud_rate,
            max_record_bytes=serial_identity.max_record_bytes,
            read_timeout_seconds=config.read_timeout_seconds,
            max_reconnect_attempts=0,
        )
        session = SerialSession(backend_factory(), settings)
        adapter_config = SerialAdapterConfig(
            serial_identity.name,
            serial_identity.version,
            max_polls_per_operation=config.max_polls_per_operation,
            max_buffered_measurements=config.max_buffered_measurements,
        )
        return SerialAdapter(
            session,
            profile,
            adapter_config,
            capability_projector=projector,
        )

    return create


__all__ = [
    "AdapterFactory",
    "SerialBackendFactory",
    "SerialSourceConfig",
    "default_serial_backend_factory",
    "discover_serial_ports",
    "make_csv_replay_adapter_factory",
    "make_csv_replay_dataset_adapter_factory",
    "make_frequency_response_simulator_adapter_factory",
    "make_serial_adapter_factory",
    "make_simulator_adapter_factory",
]
