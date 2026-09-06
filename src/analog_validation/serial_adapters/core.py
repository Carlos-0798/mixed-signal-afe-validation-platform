"""Read-only DeviceAdapter composition for one explicit serial profile."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from analog_validation.adapters.base import AdapterState, DeviceAdapter
from analog_validation.domain import (
    DeviceCapabilities,
    DeviceCommand,
    EvidenceSource,
    Measurement,
)
from analog_validation.errors import (
    AdapterConnectionError,
    AdapterDataError,
    ConfigurationError,
)
from analog_validation.profiles import SerialProfile, SerialProfileIdentity
from analog_validation.transport import (
    RawEventSnapshot,
    SerialPollStatus,
    SerialSession,
    SerialSessionState,
    SerialTransportError,
)

SERIAL_ADAPTER_CONFIG_SCHEMA_VERSION = "serial-adapter-config.v1"
DEFAULT_MAX_POLLS_PER_OPERATION = 32
DEFAULT_MAX_BUFFERED_MEASUREMENTS = 1024
MAX_POLLS_PER_OPERATION = 10_000
MAX_BUFFERED_MEASUREMENTS = 10_000

CapabilityProjector = Callable[[DeviceCapabilities], DeviceCapabilities]

_READ_ONLY_COMMANDS = frozenset(
    {
        DeviceCommand.READ_MEASUREMENT,
        DeviceCommand.READ_DIGITAL_STATE,
    }
)
_FORBIDDEN_SERIAL_ADAPTER_COMMANDS = frozenset(DeviceCommand) - _READ_ONLY_COMMANDS


def _identifier(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ConfigurationError(f"{name} must be a non-empty stripped string")
    if any(not character.isprintable() or character in "\r\n" for character in value):
        raise ConfigurationError(f"{name} must contain printable single-line text")
    return value


def _bounded_integer(
    name: str,
    value: object,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class SerialAdapterConfig:
    """Explicit profile selection and bounded synchronous polling policy."""

    profile_name: str
    profile_version: str
    max_polls_per_operation: int = DEFAULT_MAX_POLLS_PER_OPERATION
    max_buffered_measurements: int = DEFAULT_MAX_BUFFERED_MEASUREMENTS
    schema_version: str = SERIAL_ADAPTER_CONFIG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "profile_name",
            _identifier("profile_name", self.profile_name),
        )
        object.__setattr__(
            self,
            "profile_version",
            _identifier("profile_version", self.profile_version),
        )
        object.__setattr__(
            self,
            "max_polls_per_operation",
            _bounded_integer(
                "max_polls_per_operation",
                self.max_polls_per_operation,
                minimum=1,
                maximum=MAX_POLLS_PER_OPERATION,
            ),
        )
        object.__setattr__(
            self,
            "max_buffered_measurements",
            _bounded_integer(
                "max_buffered_measurements",
                self.max_buffered_measurements,
                minimum=1,
                maximum=MAX_BUFFERED_MEASUREMENTS,
            ),
        )
        if self.schema_version != SERIAL_ADAPTER_CONFIG_SCHEMA_VERSION:
            raise ConfigurationError(
                f"unsupported serial adapter config version: {self.schema_version}"
            )


def project_identity_read_only_capabilities(
    capabilities: DeviceCapabilities,
) -> DeviceCapabilities:
    """Keep channel vocabulary while removing operations this adapter cannot send."""

    if not isinstance(capabilities, DeviceCapabilities):
        raise ConfigurationError("capabilities must be DeviceCapabilities")
    return replace(
        capabilities,
        supported_commands=capabilities.supported_commands & _READ_ONLY_COMMANDS,
        supports_safe_shutdown=False,
    )


def _range_signature(
    capabilities: DeviceCapabilities,
    *,
    output: bool,
) -> tuple[tuple[float, float, str], ...]:
    ranges = (
        capabilities.safe_output_ranges if output else capabilities.safe_input_ranges
    )
    return tuple(
        sorted(
            (
                item.safe_range.minimum,
                item.safe_range.maximum,
                item.safe_range.unit.value,
            )
            for item in ranges
        )
    )


class SerialAdapter(DeviceAdapter):
    """Compose SerialSession and one profile behind the frozen adapter contract.

    This first serial adapter is deliberately receive-only. It consumes an
    already-selected profile and never exposes a backend write or device-command
    escape hatch. AFE capability records may describe physical outputs, but the
    adapter-facing command set remains read-only until a later write design is
    separately safety-reviewed.
    """

    def __init__(
        self,
        session: SerialSession,
        profile: SerialProfile[Any],
        config: SerialAdapterConfig,
        *,
        capability_projector: CapabilityProjector,
    ) -> None:
        if not isinstance(session, SerialSession):
            raise ConfigurationError("session must be a SerialSession")
        if not isinstance(profile, SerialProfile):
            raise ConfigurationError("profile must implement SerialProfile")
        if not isinstance(config, SerialAdapterConfig):
            raise ConfigurationError("config must be a SerialAdapterConfig")
        if not callable(capability_projector):
            raise ConfigurationError("capability_projector must be callable")

        identity = profile.identity
        if (config.profile_name, config.profile_version) != (
            identity.name,
            identity.version,
        ):
            raise ConfigurationError(
                "serial adapter config does not match the selected profile identity"
            )
        if session.settings.profile_name != identity.name:
            raise ConfigurationError(
                "serial session profile_name does not match the selected profile"
            )
        if session.settings.max_record_bytes != identity.max_record_bytes:
            raise ConfigurationError(
                "serial session max_record_bytes does not match the selected profile"
            )
        if session.state is not SerialSessionState.CLOSED:
            raise ConfigurationError("serial session must be closed at construction")

        evidence_source = profile.evidence_source
        if evidence_source not in {
            EvidenceSource.HOST_TEST,
            EvidenceSource.BENCH_CONTROLLER,
        }:
            raise ConfigurationError(
                "serial adapter evidence must be HOST_TEST or BENCH_CONTROLLER"
            )
        super().__init__(evidence_source)
        self._session = session
        self._profile = profile
        self._serial_config = config
        self._capability_projector = capability_projector
        self._measurements: deque[Measurement] = deque()
        self._native_capabilities: DeviceCapabilities | None = None
        self._projected_capabilities: DeviceCapabilities | None = None
        self._rejected_records = 0
        self._stream_issues = 0
        self._reconnects = 0

    @property
    def serial_config(self) -> SerialAdapterConfig:
        """Return immutable profile selection and polling limits."""

        return self._serial_config

    @property
    def profile_identity(self) -> SerialProfileIdentity:
        """Return the exact selected profile rather than inferring it from a port."""

        return self._profile.identity

    @property
    def raw_events(self) -> RawEventSnapshot:
        """Return the bounded memory-only receive provenance snapshot."""

        return self._session.event_log.snapshot()

    @property
    def native_capabilities(self) -> DeviceCapabilities | None:
        """Return the unmodified profile snapshot retained for audit."""

        return self._native_capabilities

    @property
    def buffered_measurement_count(self) -> int:
        """Return unread derived Measurements currently retained in memory."""

        return len(self._measurements)

    @property
    def rejected_record_count(self) -> int:
        """Return rejected complete records observed during this connection."""

        return self._rejected_records

    @property
    def stream_issue_count(self) -> int:
        """Return overlong/framing issues observed below complete records."""

        return self._stream_issues

    @property
    def reconnect_count(self) -> int:
        """Return reconnect boundaries observed during this connection."""

        return self._reconnects

    def _connect(self) -> None:
        self._clear_connection_state()
        self._profile.reset()
        try:
            self._session.open()
        except SerialTransportError as error:
            self._profile.reset()
            raise AdapterConnectionError("serial session open failed") from error

    def _disconnect(self) -> None:
        close_error: SerialTransportError | None = None
        try:
            self._session.close()
        except SerialTransportError as error:
            close_error = error
        finally:
            self._profile.reset()
            self._clear_connection_state()
        if close_error is not None:
            raise AdapterConnectionError("serial session close failed") from close_error

    def _get_capabilities(self) -> DeviceCapabilities:
        initial = self._profile.initial_capabilities
        if initial is not None:
            return self._register_capabilities(initial)

        for _ in range(self._serial_config.max_polls_per_operation):
            self._poll_once()
            if self._projected_capabilities is not None:
                return self._projected_capabilities
        raise AdapterDataError(
            "serial capability negotiation exhausted the bounded poll budget"
        )

    def _read_measurement(self, channel: str) -> Measurement:
        return self._read_channel(channel)

    def _read_digital_state(self, channel: str) -> Measurement:
        return self._read_channel(channel)

    def _read_channel(self, channel: str) -> Measurement:
        buffered = self._take_buffered(channel)
        if buffered is not None:
            return buffered
        for _ in range(self._serial_config.max_polls_per_operation):
            self._poll_once()
            buffered = self._take_buffered(channel)
            if buffered is not None:
                return buffered
        raise AdapterDataError(
            f"serial read for {channel} exhausted the bounded poll budget"
        )

    def _poll_once(self) -> None:
        try:
            poll = self._session.poll()
        except SerialTransportError as error:
            self._mark_session_lost()
            raise AdapterConnectionError("serial session poll failed") from error

        self._stream_issues += len(poll.issues)
        if poll.status is SerialPollStatus.RECONNECTED:
            self._reconnects += 1
            self._profile.reset()
            self._measurements.clear()
            self._native_capabilities = None
            self._projected_capabilities = None
            self._capabilities = None
            self._configuration = None
            self._state = AdapterState.CONNECTED_READ_ONLY
            raise AdapterConnectionError(
                "serial session reconnected; capabilities must be confirmed again"
            )
        if poll.status is SerialPollStatus.TIMEOUT:
            return

        for event in poll.records:
            try:
                result = self._profile.process_record(event, self._session.event_log)
            except Exception as error:
                raise AdapterDataError("serial profile processing failed") from error
            if not result.accepted:
                self._rejected_records += 1
                continue
            if result.capabilities is not None:
                self._register_capabilities(result.capabilities)
            self._buffer_measurements(result.measurements)

    def _register_capabilities(
        self,
        native: DeviceCapabilities,
    ) -> DeviceCapabilities:
        if not isinstance(native, DeviceCapabilities):
            raise AdapterDataError("serial profile returned invalid capabilities")
        if (
            self._native_capabilities is not None
            and native != self._native_capabilities
        ):
            raise AdapterDataError("serial profile capabilities changed in-session")
        try:
            projected = self._capability_projector(native)
        except Exception as error:
            raise AdapterDataError("serial capability projection failed") from error
        self._validate_projection(native, projected)
        if (
            self._projected_capabilities is not None
            and projected != self._projected_capabilities
        ):
            raise AdapterDataError("serial projected capabilities changed in-session")
        self._native_capabilities = native
        self._projected_capabilities = projected
        return projected

    def _validate_projection(
        self,
        native: DeviceCapabilities,
        projected: object,
    ) -> None:
        if not isinstance(projected, DeviceCapabilities):
            raise AdapterDataError(
                "serial capability projector must return DeviceCapabilities"
            )
        identity = self._profile.identity
        if (
            projected.device_id != native.device_id
            or projected.profile_name != native.profile_name
            or projected.profile_version != native.profile_version
            or (projected.profile_name, projected.profile_version)
            != (identity.name, identity.version)
        ):
            raise AdapterDataError(
                "serial capability projection changed device/profile identity"
            )
        channel_counts = (
            (len(native.adc_channels), len(projected.adc_channels)),
            (len(native.dac_channels), len(projected.dac_channels)),
            (len(native.pwm_channels), len(projected.pwm_channels)),
            (
                len(native.digital_input_channels),
                len(projected.digital_input_channels),
            ),
        )
        if any(before != after for before, after in channel_counts):
            raise AdapterDataError(
                "serial capability projection must alias every declared channel"
            )
        if _range_signature(native, output=False) != _range_signature(
            projected, output=False
        ) or _range_signature(native, output=True) != _range_signature(
            projected, output=True
        ):
            raise AdapterDataError(
                "serial capability projection changed a declared numeric range"
            )
        if not projected.supported_commands <= native.supported_commands:
            raise AdapterDataError("serial capability projection added a command")
        if projected.supported_commands & _FORBIDDEN_SERIAL_ADAPTER_COMMANDS:
            raise AdapterDataError(
                "SerialAdapter v1 capabilities must remain receive-only"
            )

    def _buffer_measurements(self, values: tuple[Measurement, ...]) -> None:
        if any(not isinstance(value, Measurement) for value in values):
            raise AdapterDataError("serial profile returned invalid measurements")
        if any(value.source is not self.evidence_source for value in values):
            raise AdapterDataError("serial profile changed measurement evidence")
        if (
            len(self._measurements) + len(values)
            > self._serial_config.max_buffered_measurements
        ):
            raise AdapterDataError("serial measurement buffer limit exceeded")
        self._measurements.extend(values)

    def _take_buffered(self, channel: str) -> Measurement | None:
        selected: Measurement | None = None
        count = len(self._measurements)
        for _ in range(count):
            measurement = self._measurements.popleft()
            if selected is None and measurement.channel == channel:
                selected = measurement
            else:
                self._measurements.append(measurement)
        return selected

    def _mark_session_lost(self) -> None:
        self._profile.reset()
        self._measurements.clear()
        self._native_capabilities = None
        self._projected_capabilities = None
        self._capabilities = None
        self._configuration = None
        self._state = AdapterState.DISCONNECTED

    def _clear_connection_state(self) -> None:
        self._measurements.clear()
        self._native_capabilities = None
        self._projected_capabilities = None
        self._rejected_records = 0
        self._stream_issues = 0
        self._reconnects = 0


__all__ = [
    "DEFAULT_MAX_BUFFERED_MEASUREMENTS",
    "DEFAULT_MAX_POLLS_PER_OPERATION",
    "MAX_BUFFERED_MEASUREMENTS",
    "MAX_POLLS_PER_OPERATION",
    "SERIAL_ADAPTER_CONFIG_SCHEMA_VERSION",
    "CapabilityProjector",
    "SerialAdapter",
    "SerialAdapterConfig",
    "project_identity_read_only_capabilities",
]
