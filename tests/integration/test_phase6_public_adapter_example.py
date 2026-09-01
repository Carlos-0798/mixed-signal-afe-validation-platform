"""Execute the third-party-style adapter through the public shared workflow."""

from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any, cast

from analog_validation import (
    AdapterState,
    DeviceAdapter,
    DeviceCommand,
    EvidenceSource,
    MeasurementUnit,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "public_adapter" / "read_only_voltage_adapter.py"


def _namespace() -> dict[str, Any]:
    return runpy.run_path(str(EXAMPLE))


def test_public_adapter_runs_complete_read_only_workflow_and_cleanup() -> None:
    namespace = _namespace()
    run_example = cast(Any, namespace["run_example"])

    assert run_example() == {
        "schema_version": "public-read-only-adapter-example.v1",
        "status": "COMPLETED",
        "evidence_source": "SYNTHETIC",
        "capabilities_read_only": True,
        "output_command_count": 0,
        "measurement_count": 3,
        "values_mv": [825.0, 830.0, 835.0],
        "connect_count": 1,
        "disconnect_count": 1,
        "connected_after_run": False,
        "application_bytes_written": 0,
    }


def test_public_adapter_exposes_only_declared_read_capability() -> None:
    namespace = _namespace()
    adapter_type = cast(Any, namespace["ReadOnlyVoltageAdapter"])
    adapter = cast(DeviceAdapter, adapter_type())

    assert adapter.state is AdapterState.DISCONNECTED
    assert adapter.evidence_source is EvidenceSource.SYNTHETIC
    adapter.connect()
    capabilities = adapter.get_capabilities()
    measurement = adapter.read_measurement("example.voltage")
    adapter.disconnect()

    assert capabilities.is_read_only
    assert capabilities.supported_commands == frozenset(
        {DeviceCommand.READ_MEASUREMENT}
    )
    assert not capabilities.supports_safe_shutdown
    assert measurement.value == 825.0
    assert measurement.unit is MeasurementUnit.MILLIVOLT
    assert measurement.source is EvidenceSource.SYNTHETIC
    assert adapter.state is AdapterState.DISCONNECTED
    assert cast(Any, adapter).application_bytes_written == 0
