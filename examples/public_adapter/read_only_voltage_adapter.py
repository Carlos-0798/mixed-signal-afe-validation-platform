"""Third-party-style read-only adapter using only the installed public API."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from analog_validation import (
    AdapterState,
    ChannelRange,
    ChannelReadRequest,
    DeviceAdapter,
    DeviceCapabilities,
    DeviceCommand,
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
    ReadOperation,
    ReadWorkflowRequest,
    ReadWorkflowStatus,
    ReplayEndOfData,
    SafeRange,
    run_read_workflow,
)

EXAMPLE_SCHEMA_VERSION = "public-read-only-adapter-example.v1"
CHANNEL = "example.voltage"
VALUES_MV = (825.0, 830.0, 835.0)
START_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


class ReadOnlyVoltageAdapter(DeviceAdapter):
    """Small deterministic source that advertises no output capability."""

    def __init__(self) -> None:
        super().__init__(EvidenceSource.SYNTHETIC)
        self.connect_count = 0
        self.disconnect_count = 0
        self.read_count = 0
        self.application_bytes_written = 0
        self._cursor = 0

    def _connect(self) -> None:
        self.connect_count += 1
        self._cursor = 0

    def _disconnect(self) -> None:
        self.disconnect_count += 1

    def _get_capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities(
            device_id="public-example-source",
            profile_name="public-read-only-example",
            profile_version="1",
            adc_channels=(CHANNEL,),
            safe_input_ranges=(
                ChannelRange(
                    CHANNEL,
                    SafeRange(0.0, 3_300.0, MeasurementUnit.MILLIVOLT),
                ),
            ),
            supported_commands=frozenset({DeviceCommand.READ_MEASUREMENT}),
        )

    def _read_measurement(self, channel: str) -> Measurement:
        if self._cursor >= len(VALUES_MV):
            raise ReplayEndOfData("the public example dataset is complete")
        index = self._cursor
        self._cursor += 1
        self.read_count += 1
        record_id = f"public-example-{index:03d}"
        return Measurement(
            record_id=record_id,
            raw_record_id=record_id,
            timestamp=START_TIME + timedelta(milliseconds=100 * index),
            channel=channel,
            value=VALUES_MV[index],
            unit=MeasurementUnit.MILLIVOLT,
            status=MeasurementStatus.VALID,
            source=EvidenceSource.SYNTHETIC,
        )


def run_example() -> dict[str, object]:
    """Run the external adapter through the shared installed workflow."""

    adapter = ReadOnlyVoltageAdapter()
    request = ReadWorkflowRequest(
        requirements=(
            ChannelReadRequest(
                channel=CHANNEL,
                operation=ReadOperation.ANALOG,
                unit=MeasurementUnit.MILLIVOLT,
                sample_count=len(VALUES_MV),
            ),
        ),
        request_id="public-adapter-example",
    )
    result = run_read_workflow(adapter, request)
    document: dict[str, object] = {
        "schema_version": EXAMPLE_SCHEMA_VERSION,
        "status": result.status.value,
        "evidence_source": result.evidence_source.value,
        "capabilities_read_only": result.capabilities.is_read_only,
        "output_command_count": sum(
            result.capabilities.supports(command)
            for command in (
                DeviceCommand.SET_ANALOG_STIMULUS,
                DeviceCommand.SET_PWM_STIMULUS,
                DeviceCommand.RUN_DEVICE_COMMAND,
            )
        ),
        "measurement_count": len(result.measurements),
        "values_mv": [measurement.value for measurement in result.measurements],
        "connect_count": adapter.connect_count,
        "disconnect_count": adapter.disconnect_count,
        "connected_after_run": adapter.state is not AdapterState.DISCONNECTED,
        "application_bytes_written": adapter.application_bytes_written,
    }
    if result.status is not ReadWorkflowStatus.COMPLETED:
        raise RuntimeError("public adapter example did not complete")
    return document


def main() -> int:
    print(json.dumps(run_example(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
