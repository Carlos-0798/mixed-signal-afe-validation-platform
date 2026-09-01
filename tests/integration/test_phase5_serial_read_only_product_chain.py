from __future__ import annotations

import io
import json

from analog_validation.protocol.msp430_health_v1 import (
    MSP430_HEALTH_CHANNEL_BUS_VOLTAGE,
    Msp430DeviceState,
    Msp430Telemetry,
    encode_msp430_message,
)
from analog_validation_app.cli import CliDependencies, main
from tests.support import MemorySerialBackend


class WriteTrapBackend(MemorySerialBackend):
    def __init__(self, record: bytes) -> None:
        super().__init__()
        self.read_actions.append(record)
        self.write_calls: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.write_calls.append(data)
        raise AssertionError("product receive-only chain attempted a serial write")


def test_explicit_msp430_observe_chain_never_calls_write() -> None:
    record = encode_msp430_message(
        Msp430Telemetry(
            0,
            1000,
            421,
            418,
            5012,
            186,
            932,
            650,
            Msp430DeviceState.COOLING_HIGH,
            0,
        )
    ).encode("ascii")
    backend = WriteTrapBackend(record)
    dependencies = CliDependencies(
        serial_backend_factory=lambda: backend,
        job_id_factory=lambda: "phase5-msp430-observe",
        event_id_factory=lambda: "unused",
    )
    output = io.StringIO()

    status = main(
        [
            "observe",
            "--port",
            "MEMORY:MSP430",
            "--profile",
            "msp430-equipment-health",
            "--channel",
            MSP430_HEALTH_CHANNEL_BUS_VOLTAGE,
            "--operation",
            "analog",
            "--unit",
            "mV",
            "--max-records",
            "1",
            "--confirm-read-only",
            "--json",
        ],
        stdout=output,
        dependencies=dependencies,
    )

    assert status == 0
    document = json.loads(output.getvalue())
    assert document["result"]["evidence_source"] == "HOST_TEST"
    assert document["read"]["measurements"][0]["value"] == 5012.0
    assert document["hardware_claim"] == "NO_PERFORMANCE_VALIDATION"
    assert len(backend.open_calls) == 1
    assert len(backend.read_calls) == 1
    assert backend.close_calls == 1
    assert backend.write_calls == []
