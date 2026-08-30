"""Freeze Software Phase 2 public imports, versions, enums, and signatures."""

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
from analog_validation import (
    CAPABILITY_SCHEMA_VERSION,
    CSV_REPLAY_ADAPTER_CONFIG_SCHEMA_VERSION,
    CSV_REPLAY_SCHEMA_VERSION,
    MEASUREMENT_SCHEMA_VERSION,
    READ_WORKFLOW_SCHEMA_VERSION,
    SIMULATOR_CONFIG_SCHEMA_VERSION,
    TEST_RUN_SCHEMA_VERSION,
    VALIDATION_CONFIG_SCHEMA_VERSION,
    AdapterConnectionError,
    AdapterDataError,
    AdapterError,
    AdapterState,
    AdapterStateError,
    ChannelReadRequest,
    CsvReplayAdapter,
    CsvReplayAdapterConfig,
    DeviceAdapter,
    ReadOperation,
    ReadWorkflowRequest,
    ReadWorkflowStatus,
    ReplayChannelKind,
    ReplayEndOfData,
    ReplayError,
    ReplayFormatError,
    ReplayLimitError,
    ReplayTimingMode,
    SimulatorAdapter,
    SimulatorFaultMode,
    run_read_workflow,
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = ROOT / "test-data" / "golden"
MANIFEST: dict[str, Any] = json.loads(
    (GOLDEN_DIR / "phase2_public_api.json").read_text(encoding="utf-8")
)

MODULES = {
    name: importlib.import_module(name)
    for name in (
        "analog_validation",
        "analog_validation.adapters",
        "analog_validation.replay",
        "analog_validation.workflows",
    )
}
SCHEMAS = {
    "CAPABILITY_SCHEMA_VERSION": CAPABILITY_SCHEMA_VERSION,
    "CSV_REPLAY_ADAPTER_CONFIG_SCHEMA_VERSION": (
        CSV_REPLAY_ADAPTER_CONFIG_SCHEMA_VERSION
    ),
    "CSV_REPLAY_SCHEMA_VERSION": CSV_REPLAY_SCHEMA_VERSION,
    "MEASUREMENT_SCHEMA_VERSION": MEASUREMENT_SCHEMA_VERSION,
    "READ_WORKFLOW_SCHEMA_VERSION": READ_WORKFLOW_SCHEMA_VERSION,
    "SIMULATOR_CONFIG_SCHEMA_VERSION": SIMULATOR_CONFIG_SCHEMA_VERSION,
    "TEST_RUN_SCHEMA_VERSION": TEST_RUN_SCHEMA_VERSION,
    "VALIDATION_CONFIG_SCHEMA_VERSION": VALIDATION_CONFIG_SCHEMA_VERSION,
}
ENUMS: dict[str, type[Enum]] = {
    "AdapterState": AdapterState,
    "ReadOperation": ReadOperation,
    "ReadWorkflowStatus": ReadWorkflowStatus,
    "ReplayChannelKind": ReplayChannelKind,
    "ReplayTimingMode": ReplayTimingMode,
    "SimulatorFaultMode": SimulatorFaultMode,
}
SIGNATURES: dict[str, Callable[..., Any]] = {
    "ChannelReadRequest": ChannelReadRequest,
    "CsvReplayAdapter": CsvReplayAdapter,
    "CsvReplayAdapterConfig": CsvReplayAdapterConfig,
    "DeviceAdapter.connect": DeviceAdapter.connect,
    "DeviceAdapter.disconnect": DeviceAdapter.disconnect,
    "DeviceAdapter.get_capabilities": DeviceAdapter.get_capabilities,
    "DeviceAdapter.read_digital_state": DeviceAdapter.read_digital_state,
    "DeviceAdapter.read_measurement": DeviceAdapter.read_measurement,
    "DeviceAdapter.safe_shutdown": DeviceAdapter.safe_shutdown,
    "ReadWorkflowRequest": ReadWorkflowRequest,
    "SimulatorAdapter": SimulatorAdapter,
    "run_read_workflow": run_read_workflow,
}
ERRORS: dict[str, type[Exception]] = {
    "AdapterConnectionError": AdapterConnectionError,
    "AdapterDataError": AdapterDataError,
    "AdapterStateError": AdapterStateError,
    "ReplayEndOfData": ReplayEndOfData,
    "ReplayFormatError": ReplayFormatError,
    "ReplayLimitError": ReplayLimitError,
}


def _signature_parameters(value: Callable[..., Any]) -> list[list[object]]:
    return [
        [
            parameter.name,
            parameter.kind.name,
            parameter.default is inspect.Parameter.empty,
        ]
        for parameter in inspect.signature(value).parameters.values()
    ]


def test_phase2_api_manifest_identity_is_explicitly_host_only() -> None:
    assert set(MANIFEST) == {
        "schema_version",
        "package_version",
        "evidence_source",
        "module_exports",
        "schema_versions",
        "enum_values",
        "signature_parameters",
        "error_bases",
        "replay_sha256",
    }
    assert MANIFEST["schema_version"] == "phase2-public-api-golden.v1"
    assert MANIFEST["package_version"] == analog_validation.__version__
    assert MANIFEST["evidence_source"] == "HOST_TEST"


def test_phase2_public_module_exports_match_frozen_manifest() -> None:
    for name, module in MODULES.items():
        expected = MANIFEST["module_exports"][name]
        assert sorted(module.__all__) == expected
        assert all(hasattr(module, symbol) for symbol in expected)


def test_phase2_schema_versions_match_frozen_manifest() -> None:
    assert SCHEMAS == MANIFEST["schema_versions"]


def test_phase2_enum_values_match_frozen_manifest() -> None:
    actual = {
        name: [member.value for member in enum_type]
        for name, enum_type in ENUMS.items()
    }
    assert actual == MANIFEST["enum_values"]


def test_phase2_signature_shapes_match_frozen_manifest() -> None:
    actual = {
        name: _signature_parameters(value)
        for name, value in SIGNATURES.items()
    }
    assert actual == MANIFEST["signature_parameters"]


def test_phase2_error_families_match_frozen_manifest() -> None:
    assert issubclass(AdapterConnectionError, AdapterError)
    assert issubclass(ReplayEndOfData, ReplayError)
    actual: dict[str, str] = {}
    for name, error in ERRORS.items():
        base = error.__base__
        assert base is not None
        actual[name] = base.__name__
    assert actual == MANIFEST["error_bases"]


def test_phase2_replay_compatibility_files_match_frozen_hashes() -> None:
    actual = {
        name: hashlib.sha256((GOLDEN_DIR / name).read_bytes()).hexdigest()
        for name in MANIFEST["replay_sha256"]
    }
    assert actual == MANIFEST["replay_sha256"]
