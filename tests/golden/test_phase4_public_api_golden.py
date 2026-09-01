"""Freeze Software Phase 4 public APIs, schemas, errors, and fixtures."""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any

import analog_validation
from analog_validation.profiles import (
    AFE_V1_SERIAL_IDENTITY,
    MSP430_HEALTH_V1_SERIAL_IDENTITY,
    SERIAL_PROFILE_SCHEMA_VERSION,
    AfeV1SerialProfile,
    Msp430HealthV1SerialProfile,
    SerialProfileError,
    SerialProfileIdentity,
    SerialProfileStateError,
)
from analog_validation.protocol.afe_channels import (
    AFE_CHANNEL_MAPPING_SCHEMA_VERSION,
    AfeChannelNaming,
    AfeChannelRole,
    convert_afe_channel,
    format_afe_channel,
    parse_afe_channel,
)
from analog_validation.protocol.envelope import (
    decode_crc_envelope,
    encode_crc_envelope,
)
from analog_validation.protocol.msp430_health_v1 import (
    MSP430_HEALTH_INTERFACE_COMMIT,
    Msp430ControlMode,
    Msp430DeviceState,
    Msp430Fault,
    encode_msp430_message,
    msp430_telemetry_to_measurements,
    parse_msp430_message,
)
from analog_validation.serial_adapters import (
    SERIAL_ADAPTER_CONFIG_SCHEMA_VERSION,
    SerialAdapter,
    SerialAdapterConfig,
    project_afe_v1_read_only_capabilities,
    project_identity_read_only_capabilities,
)
from analog_validation.transport import (
    RAW_EVENT_PRIVACY_NOTICE,
    BoundedLineFramer,
    BoundedRawEventLog,
    RawEventError,
    RawEventLimitError,
    RawEventNotFound,
    RawRecordStatus,
    SequenceDisposition,
    SequenceTracker,
    SerialBackendDisconnected,
    SerialBackendTimeout,
    SerialCloseError,
    SerialConnectionSettings,
    SerialDiscoveryError,
    SerialOpenError,
    SerialParity,
    SerialPollStatus,
    SerialReadError,
    SerialReconnectError,
    SerialSession,
    SerialSessionState,
    SerialStateError,
    SerialStopBits,
    SerialTransportError,
    StreamIssueKind,
)
from analog_validation_pyserial import (
    PySerialBackend,
    PySerialBackendError,
    PySerialBackendStateError,
    PySerialUnavailableError,
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = ROOT / "test-data" / "golden"
MANIFEST_PATH = GOLDEN_DIR / "phase4_public_api.json"

MODULE_NAMES = (
    "analog_validation.transport",
    "analog_validation.protocol.envelope",
    "analog_validation.protocol.afe_channels",
    "analog_validation.protocol.msp430_health_v1",
    "analog_validation.profiles",
    "analog_validation.serial_adapters",
    "analog_validation_pyserial",
)
MODULES = {name: importlib.import_module(name) for name in MODULE_NAMES}
SCHEMAS = {
    "AFE_CHANNEL_MAPPING_SCHEMA_VERSION": AFE_CHANNEL_MAPPING_SCHEMA_VERSION,
    "SERIAL_ADAPTER_CONFIG_SCHEMA_VERSION": SERIAL_ADAPTER_CONFIG_SCHEMA_VERSION,
    "SERIAL_PROFILE_SCHEMA_VERSION": SERIAL_PROFILE_SCHEMA_VERSION,
}
ENUMS: dict[str, type[Enum]] = {
    "AfeChannelNaming": AfeChannelNaming,
    "AfeChannelRole": AfeChannelRole,
    "Msp430ControlMode": Msp430ControlMode,
    "Msp430DeviceState": Msp430DeviceState,
    "Msp430Fault": Msp430Fault,
    "RawRecordStatus": RawRecordStatus,
    "SequenceDisposition": SequenceDisposition,
    "SerialParity": SerialParity,
    "SerialPollStatus": SerialPollStatus,
    "SerialSessionState": SerialSessionState,
    "SerialStopBits": SerialStopBits,
    "StreamIssueKind": StreamIssueKind,
}
SIGNATURES: dict[str, Callable[..., Any]] = {
    "AfeV1SerialProfile": AfeV1SerialProfile,
    "BoundedLineFramer": BoundedLineFramer,
    "BoundedRawEventLog": BoundedRawEventLog,
    "Msp430HealthV1SerialProfile": Msp430HealthV1SerialProfile,
    "PySerialBackend": PySerialBackend,
    "SequenceTracker": SequenceTracker,
    "SerialAdapter": SerialAdapter,
    "SerialAdapterConfig": SerialAdapterConfig,
    "SerialConnectionSettings": SerialConnectionSettings,
    "SerialProfileIdentity": SerialProfileIdentity,
    "SerialSession": SerialSession,
    "convert_afe_channel": convert_afe_channel,
    "decode_crc_envelope": decode_crc_envelope,
    "encode_crc_envelope": encode_crc_envelope,
    "encode_msp430_message": encode_msp430_message,
    "format_afe_channel": format_afe_channel,
    "msp430_telemetry_to_measurements": msp430_telemetry_to_measurements,
    "parse_afe_channel": parse_afe_channel,
    "parse_msp430_message": parse_msp430_message,
    "project_afe_v1_read_only_capabilities": (
        project_afe_v1_read_only_capabilities
    ),
    "project_identity_read_only_capabilities": (
        project_identity_read_only_capabilities
    ),
}
ERRORS: dict[str, type[Exception]] = {
    "PySerialBackendError": PySerialBackendError,
    "PySerialBackendStateError": PySerialBackendStateError,
    "PySerialUnavailableError": PySerialUnavailableError,
    "RawEventError": RawEventError,
    "RawEventLimitError": RawEventLimitError,
    "RawEventNotFound": RawEventNotFound,
    "SerialBackendDisconnected": SerialBackendDisconnected,
    "SerialBackendTimeout": SerialBackendTimeout,
    "SerialCloseError": SerialCloseError,
    "SerialDiscoveryError": SerialDiscoveryError,
    "SerialOpenError": SerialOpenError,
    "SerialProfileError": SerialProfileError,
    "SerialProfileStateError": SerialProfileStateError,
    "SerialReadError": SerialReadError,
    "SerialReconnectError": SerialReconnectError,
    "SerialStateError": SerialStateError,
    "SerialTransportError": SerialTransportError,
}
GOLDEN_FILES = (
    "afe_v1_invalid.csv",
    "afe_v1_valid.csv",
    "msp430_equipment_health_v1.json",
    "phase4_composite_v1.json",
    "profile_neutral_envelope_v1.json",
)


def _signature_parameters(value: Callable[..., Any]) -> list[list[object]]:
    return [
        [
            parameter.name,
            parameter.kind.name,
            parameter.default is inspect.Parameter.empty,
        ]
        for parameter in inspect.signature(value).parameters.values()
    ]


def _enum_members(enum_type: type[Enum]) -> list[list[object]]:
    return [[name, member.value] for name, member in enum_type.__members__.items()]


def _identity(value: SerialProfileIdentity) -> dict[str, object]:
    return {
        "name": value.name,
        "version": value.version,
        "sequence_bits": value.sequence_bits,
        "max_record_bytes": value.max_record_bytes,
        "schema_version": value.schema_version,
    }


def _actual_manifest() -> dict[str, object]:
    return {
        "schema_version": "phase4-public-api-golden.v1",
        "package_version": analog_validation.__version__,
        "evidence_source": "HOST_TEST",
        "module_exports": {
            name: sorted(MODULES[name].__all__) for name in MODULE_NAMES
        },
        "schema_versions": SCHEMAS,
        "stable_constants": {
            "AFE_V1_SERIAL_IDENTITY": _identity(AFE_V1_SERIAL_IDENTITY),
            "MSP430_HEALTH_V1_SERIAL_IDENTITY": _identity(
                MSP430_HEALTH_V1_SERIAL_IDENTITY
            ),
            "MSP430_HEALTH_INTERFACE_COMMIT": MSP430_HEALTH_INTERFACE_COMMIT,
            "RAW_EVENT_PRIVACY_NOTICE": RAW_EVENT_PRIVACY_NOTICE,
        },
        "enum_members": {
            name: _enum_members(enum_type) for name, enum_type in ENUMS.items()
        },
        "signature_parameters": {
            name: _signature_parameters(value) for name, value in SIGNATURES.items()
        },
        "error_bases": {
            name: error.__base__.__name__
            for name, error in ERRORS.items()
            if error.__base__ is not None
        },
        "golden_sha256": {
            name: hashlib.sha256((GOLDEN_DIR / name).read_bytes()).hexdigest()
            for name in GOLDEN_FILES
        },
    }


def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_phase4_manifest_identity_is_explicitly_host_only() -> None:
    manifest = _manifest()
    assert set(manifest) == set(_actual_manifest())
    assert manifest["schema_version"] == "phase4-public-api-golden.v1"
    assert manifest["package_version"] == analog_validation.__version__
    assert manifest["evidence_source"] == "HOST_TEST"


def test_phase4_public_module_exports_match_frozen_manifest() -> None:
    assert _manifest()["module_exports"] == _actual_manifest()["module_exports"]


def test_phase4_schemas_and_stable_constants_match_frozen_manifest() -> None:
    manifest = _manifest()
    actual = _actual_manifest()
    assert manifest["schema_versions"] == actual["schema_versions"]
    assert manifest["stable_constants"] == actual["stable_constants"]


def test_phase4_enum_members_match_frozen_manifest() -> None:
    assert _manifest()["enum_members"] == _actual_manifest()["enum_members"]


def test_phase4_signature_shapes_match_frozen_manifest() -> None:
    assert _manifest()["signature_parameters"] == _actual_manifest()[
        "signature_parameters"
    ]


def test_phase4_error_families_match_frozen_manifest() -> None:
    assert _manifest()["error_bases"] == _actual_manifest()["error_bases"]


def test_phase4_golden_files_match_frozen_hashes() -> None:
    assert _manifest()["golden_sha256"] == _actual_manifest()["golden_sha256"]


def test_phase4_public_implementation_stays_in_owned_packages() -> None:
    for module_name in MODULE_NAMES:
        module = MODULES[module_name]
        expected_prefix = (
            "analog_validation_pyserial"
            if module_name == "analog_validation_pyserial"
            else "analog_validation"
        )
        for name in module.__all__:
            value = getattr(module, name)
            if inspect.isfunction(value) or inspect.isclass(value):
                assert value.__module__.startswith(expected_prefix)


def test_optional_backend_public_surface_remains_receive_only() -> None:
    assert not hasattr(PySerialBackend, "write")
