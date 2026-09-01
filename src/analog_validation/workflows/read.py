"""Shared read-only acquisition workflow for every DeviceAdapter."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import cast

from analog_validation.adapters import AdapterState, DeviceAdapter
from analog_validation.domain import (
    DeviceCapabilities,
    DeviceCommand,
    EvidenceSource,
    Measurement,
    MeasurementUnit,
)
from analog_validation.errors import (
    AdapterStateError,
    ReplayEndOfData,
    ValidationError,
)

READ_WORKFLOW_SCHEMA_VERSION = "read-workflow.v1"


class ReadOperation(str, Enum):
    """Controller-neutral kind of read requested from an adapter."""

    ANALOG = "ANALOG"
    DIGITAL = "DIGITAL"


class ReadWorkflowStatus(str, Enum):
    """Acquisition status that never implies an engineering PASS/FAIL."""

    COMPLETED = "COMPLETED"
    UNSUPPORTED = "UNSUPPORTED"
    INCOMPLETE = "INCOMPLETE"


def _require_identifier(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValidationError(f"{name} must be a non-empty stripped string")
    return value


def _freeze_typed_tuple(
    name: str,
    values: object,
    expected_type: type[object],
) -> tuple[object, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ValidationError(f"{name} must be an iterable")
    frozen: tuple[object, ...] = tuple(values)
    if not all(isinstance(value, expected_type) for value in frozen):
        raise ValidationError(
            f"{name} must contain {expected_type.__name__} values"
        )
    return frozen


def _freeze_missing_requirements(values: object) -> tuple[str, ...]:
    frozen = _freeze_typed_tuple("missing_requirements", values, str)
    typed = cast(tuple[str, ...], frozen)
    for value in typed:
        _require_identifier("missing requirement", value)
    if len(typed) != len(set(typed)):
        raise ValidationError("missing_requirements cannot contain duplicates")
    return typed


@dataclass(frozen=True, slots=True)
class ChannelReadRequest:
    """One explicit channel, operation, unit, and sample count."""

    channel: str
    operation: ReadOperation
    unit: MeasurementUnit
    sample_count: int = 1

    def __post_init__(self) -> None:
        _require_identifier("channel", self.channel)
        if not isinstance(self.operation, ReadOperation):
            raise ValidationError("operation must be a ReadOperation")
        if not isinstance(self.unit, MeasurementUnit):
            raise ValidationError("unit must be a MeasurementUnit")
        if self.operation is ReadOperation.ANALOG:
            if self.unit is MeasurementUnit.BOOLEAN:
                raise ValidationError("analog reads cannot use bool units")
        elif self.unit is not MeasurementUnit.BOOLEAN:
            raise ValidationError("digital reads must use bool units")
        if (
            isinstance(self.sample_count, bool)
            or not isinstance(self.sample_count, int)
            or self.sample_count < 1
        ):
            raise ValidationError("sample_count must be an integer of at least one")


@dataclass(frozen=True, slots=True)
class ReadWorkflowRequest:
    """Versioned atomic preflight and acquisition request."""

    requirements: tuple[ChannelReadRequest, ...]
    request_id: str = "read-workflow"
    schema_version: str = READ_WORKFLOW_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_identifier("request_id", self.request_id)
        frozen = _freeze_typed_tuple(
            "requirements", self.requirements, ChannelReadRequest
        )
        requirements = cast(tuple[ChannelReadRequest, ...], frozen)
        if not requirements:
            raise ValidationError("requirements cannot be empty")
        channels = [requirement.channel for requirement in requirements]
        if len(channels) != len(set(channels)):
            raise ValidationError("read workflow channels must be unique")
        object.__setattr__(self, "requirements", requirements)
        if self.schema_version != READ_WORKFLOW_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported read workflow version: {self.schema_version}"
            )

    @property
    def requested_sample_count(self) -> int:
        """Return the total number of Measurements requested."""

        return sum(requirement.sample_count for requirement in self.requirements)


@dataclass(frozen=True, slots=True)
class ReadWorkflowResult:
    """Immutable acquisition result with explicit degradation semantics."""

    request: ReadWorkflowRequest
    capabilities: DeviceCapabilities
    evidence_source: EvidenceSource
    status: ReadWorkflowStatus
    measurements: tuple[Measurement, ...] = ()
    missing_requirements: tuple[str, ...] = ()
    schema_version: str = READ_WORKFLOW_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.request, ReadWorkflowRequest):
            raise ValidationError("request must be a ReadWorkflowRequest")
        if not isinstance(self.capabilities, DeviceCapabilities):
            raise ValidationError("capabilities must be DeviceCapabilities")
        if not isinstance(self.evidence_source, EvidenceSource):
            raise ValidationError("evidence_source must be an EvidenceSource")
        if not isinstance(self.status, ReadWorkflowStatus):
            raise ValidationError("status must be a ReadWorkflowStatus")

        frozen_measurements = _freeze_typed_tuple(
            "measurements", self.measurements, Measurement
        )
        measurements = cast(tuple[Measurement, ...], frozen_measurements)
        missing = _freeze_missing_requirements(self.missing_requirements)
        object.__setattr__(self, "measurements", measurements)
        object.__setattr__(self, "missing_requirements", missing)

        requirements = {
            requirement.channel: requirement
            for requirement in self.request.requirements
        }
        counts = dict.fromkeys(requirements, 0)
        for measurement in measurements:
            requirement = requirements.get(measurement.channel)
            if requirement is None:
                raise ValidationError(
                    "measurement channel was not requested by the workflow"
                )
            if measurement.unit is not requirement.unit:
                raise ValidationError(
                    "measurement unit does not match the workflow request"
                )
            if measurement.source is not self.evidence_source:
                raise ValidationError(
                    "measurement source does not match workflow evidence source"
                )
            counts[measurement.channel] += 1
            if counts[measurement.channel] > requirement.sample_count:
                raise ValidationError(
                    "workflow result contains more samples than requested"
                )

        collected = len(measurements)
        requested = self.request.requested_sample_count
        capability_missing = _missing_capabilities(
            self.capabilities,
            self.request,
        )
        if self.status is ReadWorkflowStatus.COMPLETED:
            if capability_missing:
                raise ValidationError(
                    "COMPLETED workflow requires all requested capabilities"
                )
            if missing:
                raise ValidationError(
                    "COMPLETED workflow cannot have missing requirements"
                )
            if collected != requested:
                raise ValidationError(
                    "COMPLETED workflow requires every requested sample"
                )
        elif self.status is ReadWorkflowStatus.UNSUPPORTED:
            if not missing:
                raise ValidationError(
                    "UNSUPPORTED workflow must identify missing requirements"
                )
            if missing != capability_missing:
                raise ValidationError(
                    "UNSUPPORTED workflow must list the exact capability gaps"
                )
            if measurements:
                raise ValidationError(
                    "UNSUPPORTED workflow cannot contain partial measurements"
                )
        else:
            if capability_missing:
                raise ValidationError(
                    "INCOMPLETE workflow requires all requested capabilities"
                )
            if not missing:
                raise ValidationError(
                    "INCOMPLETE workflow must identify missing requirements"
                )
            if collected >= requested:
                raise ValidationError(
                    "INCOMPLETE workflow must be missing requested samples"
                )

        if self.schema_version != READ_WORKFLOW_SCHEMA_VERSION:
            raise ValidationError(
                f"unsupported read workflow version: {self.schema_version}"
            )

    @property
    def is_completed(self) -> bool:
        """Return true only when every requested sample was acquired."""

        return self.status is ReadWorkflowStatus.COMPLETED

    @property
    def is_unsupported(self) -> bool:
        """Return true when preflight found missing device capabilities."""

        return self.status is ReadWorkflowStatus.UNSUPPORTED

    @property
    def is_incomplete(self) -> bool:
        """Return true when an available source ended before acquisition."""

        return self.status is ReadWorkflowStatus.INCOMPLETE


def _append_once(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _missing_capabilities(
    capabilities: DeviceCapabilities,
    request: ReadWorkflowRequest,
) -> tuple[str, ...]:
    missing: list[str] = []
    for requirement in request.requirements:
        if requirement.operation is ReadOperation.ANALOG:
            command = DeviceCommand.READ_MEASUREMENT
            if not capabilities.supports(command):
                _append_once(missing, f"command:{command.value}")
            if requirement.channel not in capabilities.adc_channels:
                _append_once(missing, f"analog-channel:{requirement.channel}")
            else:
                actual_unit = capabilities.get_input_range(requirement.channel).unit
                if actual_unit is not requirement.unit:
                    _append_once(
                        missing,
                        f"analog-unit:{requirement.channel}:{requirement.unit.value}",
                    )
        else:
            command = DeviceCommand.READ_DIGITAL_STATE
            if not capabilities.supports(command):
                _append_once(missing, f"command:{command.value}")
            if requirement.channel not in capabilities.digital_input_channels:
                _append_once(missing, f"digital-channel:{requirement.channel}")
    return tuple(missing)


def _uncollected_sample_requirements(
    request: ReadWorkflowRequest,
    requirement_index: int,
    collected_for_current: int,
) -> tuple[str, ...]:
    missing: list[str] = []
    for index, requirement in enumerate(request.requirements[requirement_index:]):
        collected = collected_for_current if index == 0 else 0
        remaining = requirement.sample_count - collected
        if remaining:
            missing.append(
                f"samples:{requirement.operation.value}:"
                f"{requirement.channel}:{remaining}"
            )
    return tuple(missing)


def run_read_workflow(
    adapter: DeviceAdapter,
    request: ReadWorkflowRequest,
) -> ReadWorkflowResult:
    """Acquire requested channels through one adapter-neutral workflow.

    Capability preflight is atomic: if any requirement is unavailable, no read
    is attempted. The workflow owns a disconnected adapter for this call and
    always disconnects it before returning or re-raising an execution error.
    """

    if not isinstance(adapter, DeviceAdapter):
        raise ValidationError("adapter must be a DeviceAdapter")
    if not isinstance(request, ReadWorkflowRequest):
        raise ValidationError("request must be a ReadWorkflowRequest")
    if adapter.state is not AdapterState.DISCONNECTED:
        raise AdapterStateError(
            "read workflow requires a disconnected adapter it can own"
        )

    adapter.connect()
    try:
        capabilities = adapter.get_capabilities()
        missing = _missing_capabilities(capabilities, request)
        if missing:
            return ReadWorkflowResult(
                request,
                capabilities,
                adapter.evidence_source,
                ReadWorkflowStatus.UNSUPPORTED,
                missing_requirements=missing,
            )

        measurements: list[Measurement] = []
        for requirement_index, requirement in enumerate(request.requirements):
            for sample_index in range(requirement.sample_count):
                try:
                    if requirement.operation is ReadOperation.ANALOG:
                        measurement = adapter.read_measurement(requirement.channel)
                    else:
                        measurement = adapter.read_digital_state(requirement.channel)
                except ReplayEndOfData:
                    return ReadWorkflowResult(
                        request,
                        capabilities,
                        adapter.evidence_source,
                        ReadWorkflowStatus.INCOMPLETE,
                        tuple(measurements),
                        _uncollected_sample_requirements(
                            request,
                            requirement_index,
                            sample_index,
                        ),
                    )
                measurements.append(measurement)

        return ReadWorkflowResult(
            request,
            capabilities,
            adapter.evidence_source,
            ReadWorkflowStatus.COMPLETED,
            tuple(measurements),
        )
    finally:
        adapter.disconnect()


__all__ = [
    "READ_WORKFLOW_SCHEMA_VERSION",
    "ChannelReadRequest",
    "ReadOperation",
    "ReadWorkflowRequest",
    "ReadWorkflowResult",
    "ReadWorkflowStatus",
    "run_read_workflow",
]
