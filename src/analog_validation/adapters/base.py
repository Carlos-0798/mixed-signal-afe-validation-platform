"""Lifecycle and safety contract shared by every device adapter."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from enum import Enum
from typing import TypeVar

from analog_validation.config import (
    ChannelRole,
    ValidationConfig,
    validate_config_capabilities,
)
from analog_validation.domain import (
    DeviceCapabilities,
    DeviceCommand,
    EvidenceSource,
    Measurement,
    MeasurementUnit,
)
from analog_validation.errors import (
    AdapterConnectionError,
    AdapterDataError,
    AdapterError,
    AdapterStateError,
    AnalogValidationError,
    CapabilityError,
    ConfigurationError,
    ValidationError,
)

T = TypeVar("T")


class AdapterState(str, Enum):
    """Safety-relevant lifecycle state exposed to application services."""

    DISCONNECTED = "DISCONNECTED"
    CONNECTED_READ_ONLY = "CONNECTED_READ_ONLY"
    CAPABILITIES_CONFIRMED = "CAPABILITIES_CONFIRMED"
    ARMED = "ARMED"
    RUNNING = "RUNNING"
    SAFE_SHUTDOWN = "SAFE_SHUTDOWN"


class DeviceAdapter(ABC):
    """Template-method contract for simulator, replay, and physical adapters.

    Public methods own lifecycle and host-side safety checks. Subclasses only
    implement the protected I/O hooks appropriate for their data source.
    """

    def __init__(self, evidence_source: EvidenceSource) -> None:
        if not isinstance(evidence_source, EvidenceSource):
            raise ValidationError("evidence_source must be an EvidenceSource")
        self._evidence_source = evidence_source
        self._state = AdapterState.DISCONNECTED
        self._capabilities: DeviceCapabilities | None = None
        self._configuration: ValidationConfig | None = None

    @property
    def evidence_source(self) -> EvidenceSource:
        """Return the provenance every measurement from this adapter must use."""

        return self._evidence_source

    @property
    def state(self) -> AdapterState:
        """Return the current lifecycle state without performing I/O."""

        return self._state

    @property
    def is_connected(self) -> bool:
        """Return whether the adapter owns an active logical connection."""

        return self._state is not AdapterState.DISCONNECTED

    @property
    def capabilities(self) -> DeviceCapabilities:
        """Return confirmed capabilities or reject premature access."""

        if self._capabilities is None:
            raise AdapterStateError("device capabilities have not been confirmed")
        return self._capabilities

    def connect(self) -> None:
        """Open the data source in a read-only state.

        Connection deliberately does not authorize output. Capability
        negotiation is a separate, visible step.
        """

        self._require_state("connect", AdapterState.DISCONNECTED)
        try:
            self._invoke("connect", self._connect, AdapterConnectionError)
        except AnalogValidationError:
            self._reset_state()
            raise
        self._state = AdapterState.CONNECTED_READ_ONLY

    def get_capabilities(self) -> DeviceCapabilities:
        """Negotiate and cache explicit device capabilities."""

        self._require_state(
            "get capabilities",
            AdapterState.CONNECTED_READ_ONLY,
            AdapterState.CAPABILITIES_CONFIRMED,
            AdapterState.ARMED,
            AdapterState.RUNNING,
            AdapterState.SAFE_SHUTDOWN,
        )
        if self._capabilities is not None:
            return self._capabilities
        capabilities = self._invoke("get capabilities", self._get_capabilities)
        if not isinstance(capabilities, DeviceCapabilities):
            raise AdapterDataError(
                "adapter get_capabilities hook must return DeviceCapabilities"
            )
        self._capabilities = capabilities
        self._state = AdapterState.CAPABILITIES_CONFIRMED
        return capabilities

    def arm(self, config: ValidationConfig) -> None:
        """Authorize configured automatic output after all host-side gates."""

        self._require_state("arm", AdapterState.CAPABILITIES_CONFIRMED)
        if not isinstance(config, ValidationConfig):
            raise ConfigurationError("config must be a ValidationConfig")
        if not config.allow_output:
            raise ConfigurationError("arming requires allow_output=true")
        if config.evidence_source is not self.evidence_source:
            raise ConfigurationError(
                "configuration evidence source does not match the adapter"
            )
        validate_config_capabilities(config, self.capabilities)
        self._configuration = config
        self._state = AdapterState.ARMED

    def read_measurement(self, channel: str) -> Measurement:
        """Read one analog measurement after explicit capability confirmation."""

        self._require_operational_state("read measurement")
        self._require_identifier("channel", channel)
        capabilities = self.capabilities
        capabilities.require_command(DeviceCommand.READ_MEASUREMENT)
        if channel not in capabilities.adc_channels:
            raise CapabilityError(f"ADC channel {channel} is not available")
        measurement = self._invoke(
            "read measurement", lambda: self._read_measurement(channel)
        )
        self._validate_measurement(
            measurement,
            channel,
            capabilities.get_input_range(channel).unit,
        )
        return measurement

    def read_digital_state(self, channel: str) -> Measurement:
        """Read one digital-input state as a boolean-unit Measurement."""

        self._require_operational_state("read digital state")
        self._require_identifier("channel", channel)
        capabilities = self.capabilities
        capabilities.require_command(DeviceCommand.READ_DIGITAL_STATE)
        if channel not in capabilities.digital_input_channels:
            raise CapabilityError(f"digital input channel {channel} is not available")
        measurement = self._invoke(
            "read digital state", lambda: self._read_digital_state(channel)
        )
        self._validate_measurement(measurement, channel, MeasurementUnit.BOOLEAN)
        return measurement

    def set_stimulus(
        self,
        channel: str,
        value: float,
        unit: MeasurementUnit,
    ) -> None:
        """Apply one bounded output only from ARMED or RUNNING."""

        self._require_state("set stimulus", AdapterState.ARMED, AdapterState.RUNNING)
        if self._configuration is None:  # pragma: no cover - state invariant
            raise AdapterStateError("adapter has no armed configuration")
        configured_channel = self._configuration.require_output(channel, value, unit)
        command = (
            DeviceCommand.SET_ANALOG_STIMULUS
            if configured_channel.role is ChannelRole.ANALOG_OUTPUT
            else DeviceCommand.SET_PWM_STIMULUS
        )
        self.capabilities.require_automated_output(command, channel, value, unit)
        self._invoke(
            "set stimulus", lambda: self._set_stimulus(channel, float(value), unit)
        )
        self._state = AdapterState.RUNNING

    def run_command(self, command: str) -> None:
        """Run an advertised non-stimulus profile command.

        Concrete adapters must route every output-affecting operation through
        ``set_stimulus`` instead of using this generic escape hatch.
        """

        self._require_operational_state("run command")
        self._require_identifier("command", command)
        self.capabilities.require_command(DeviceCommand.RUN_DEVICE_COMMAND)
        self._invoke("run command", lambda: self._run_command(command))

    def safe_shutdown(self) -> None:
        """Request an idempotent safe state without claiming physical proof."""

        if self._state in {AdapterState.DISCONNECTED, AdapterState.SAFE_SHUTDOWN}:
            return
        if self._capabilities is not None and self._capabilities.supports_safe_shutdown:
            self._invoke("safe shutdown", self._safe_shutdown)
        self._configuration = None
        self._state = AdapterState.SAFE_SHUTDOWN

    def disconnect(self) -> None:
        """Release the source and reset state, attempting shutdown first."""

        if self._state is AdapterState.DISCONNECTED:
            return

        shutdown_error: AnalogValidationError | None = None
        disconnect_error: AnalogValidationError | None = None
        try:
            if self._state in {AdapterState.ARMED, AdapterState.RUNNING}:
                try:
                    self.safe_shutdown()
                except AnalogValidationError as error:
                    shutdown_error = error
            try:
                self._invoke("disconnect", self._disconnect, AdapterConnectionError)
            except AnalogValidationError as error:
                disconnect_error = error
        finally:
            self._reset_state()

        if disconnect_error is not None:
            raise disconnect_error
        if shutdown_error is not None:
            raise shutdown_error

    def _require_operational_state(self, operation: str) -> None:
        self._require_state(
            operation,
            AdapterState.CAPABILITIES_CONFIRMED,
            AdapterState.ARMED,
            AdapterState.RUNNING,
        )

    def _require_state(
        self,
        operation: str,
        *allowed_states: AdapterState,
    ) -> None:
        if self._state not in allowed_states:
            allowed = ", ".join(state.value for state in allowed_states)
            raise AdapterStateError(
                f"cannot {operation} while adapter state is {self._state.value}; "
                f"expected {allowed}"
            )

    def _validate_measurement(
        self,
        measurement: object,
        channel: str,
        unit: MeasurementUnit,
    ) -> None:
        if not isinstance(measurement, Measurement):
            raise AdapterDataError("adapter read hook must return a Measurement")
        if measurement.channel != channel:
            raise AdapterDataError("adapter returned a different measurement channel")
        if measurement.unit is not unit:
            raise AdapterDataError("adapter returned an incompatible measurement unit")
        if measurement.source is not self.evidence_source:
            raise AdapterDataError("adapter returned an incompatible evidence source")

    @staticmethod
    def _require_identifier(name: str, value: object) -> None:
        if not isinstance(value, str) or not value or value != value.strip():
            raise ValidationError(f"{name} must be a non-empty stripped string")

    @staticmethod
    def _invoke(
        action: str,
        operation: Callable[[], T],
        error_type: type[AdapterError] = AdapterError,
    ) -> T:
        try:
            return operation()
        except AnalogValidationError:
            raise
        except Exception as error:
            raise error_type(f"adapter {action} failed: {error}") from error

    def _reset_state(self) -> None:
        self._configuration = None
        self._capabilities = None
        self._state = AdapterState.DISCONNECTED

    @abstractmethod
    def _connect(self) -> None:
        """Open adapter-specific resources without enabling output."""

    @abstractmethod
    def _disconnect(self) -> None:
        """Release adapter-specific resources."""

    @abstractmethod
    def _get_capabilities(self) -> DeviceCapabilities:
        """Return explicit adapter capabilities."""

    @abstractmethod
    def _read_measurement(self, channel: str) -> Measurement:
        """Return one analog Measurement for a validated channel."""

    def _read_digital_state(self, channel: str) -> Measurement:
        raise CapabilityError("adapter does not implement digital input")

    def _set_stimulus(
        self,
        channel: str,
        value: float,
        unit: MeasurementUnit,
    ) -> None:
        raise CapabilityError("adapter does not implement stimulus output")

    def _run_command(self, command: str) -> None:
        """Run a non-stimulus command after the public capability gate."""

        raise CapabilityError("adapter does not implement device commands")

    def _safe_shutdown(self) -> None:
        raise CapabilityError("adapter does not implement safe shutdown")


__all__ = ["AdapterState", "DeviceAdapter"]
