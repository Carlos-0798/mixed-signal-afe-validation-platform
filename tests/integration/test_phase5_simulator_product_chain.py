from __future__ import annotations

import io
import json
from pathlib import Path

from analog_validation.exports import load_result_export_json
from analog_validation_app.cli import CliDependencies, main
from tests.support import MemorySerialBackend


def dependencies() -> CliDependencies:
    return CliDependencies(
        serial_backend_factory=MemorySerialBackend,
        job_id_factory=lambda: "phase5-simulator-chain",
        event_id_factory=lambda: "unused",
    )


def test_simulator_cli_worker_analysis_export_and_reload_chain(tmp_path: Path) -> None:
    output = io.StringIO()
    destination = tmp_path / "dc-result.json"

    status = main(
        [
            "simulate",
            "dc",
            "--points",
            "12",
            "--output",
            str(destination),
            "--json",
        ],
        stdout=output,
        dependencies=dependencies(),
    )

    assert status == 0
    document = json.loads(output.getvalue())
    reloaded = load_result_export_json(destination)
    assert document["worker"]["state"] == "SUCCEEDED"
    assert document["result"]["test_run_outcome"] == "PASS"
    assert document["result"]["evidence_source"] == "SYNTHETIC"
    assert reloaded.test_run_result.outcome.value == "PASS"
    assert reloaded.test_run_result.metadata.run_id == "phase5-simulator-chain"
    assert len(reloaded.points) == 12
    assert document["hardware_claim"] == "NO_PERFORMANCE_VALIDATION"


def test_simulator_hysteresis_chain_uses_formal_threshold_result() -> None:
    output = io.StringIO()

    status = main(
        ["simulate", "hysteresis", "--json"],
        stdout=output,
        dependencies=dependencies(),
    )

    assert status == 0
    document = json.loads(output.getvalue())
    metrics = {
        metric["name"]: metric["value"]
        for metric in document["result_export"]["metrics"]
    }
    assert document["result"]["test_run_outcome"] == "PASS"
    assert metrics["complete_cycles"] == 1
    assert metrics["mean_high_threshold"] == 991.5
    assert metrics["mean_low_threshold"] == 916.0
    assert metrics["mean_width"] == 75.5
