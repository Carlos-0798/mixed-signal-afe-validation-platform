from __future__ import annotations

import io
from dataclasses import replace
from pathlib import Path
from time import monotonic, sleep
from typing import cast

from analog_validation.exports import load_result_export_json, result_export_to_dict
from analog_validation_app import (
    DashboardApplication,
    DashboardWizardStep,
    ProductJobType,
)
from analog_validation_app.cli import CliDependencies, main
from tests.support import MemorySerialBackend


def _wait_for_result(application: DashboardApplication) -> None:
    deadline = monotonic() + 5.0
    while monotonic() < deadline:
        application.poll()
        if application.wizard_state.step is DashboardWizardStep.RESULT:
            return
        sleep(0.001)
    raise AssertionError("Dashboard job did not reach RESULT")


def _stable_document(path: Path) -> dict[str, object]:
    document = result_export_to_dict(load_result_export_json(path))
    test_run = cast(dict[str, object], document["test_run"])
    metadata = cast(dict[str, object], test_run["metadata"])
    metadata.pop("started_at")
    metadata.pop("ended_at")
    return document


def test_cli_and_dashboard_compile_the_same_simulator_dc_product_result(
    tmp_path: Path,
) -> None:
    cli_path = tmp_path / "cli-result.json"
    dashboard_path = tmp_path / "dashboard-result.json"
    dependencies = CliDependencies(
        serial_backend_factory=MemorySerialBackend,
        job_id_factory=lambda: "equivalent-product-job",
        event_id_factory=lambda: "unused",
    )
    assert (
        main(
            [
                "simulate",
                "dc",
                "--points",
                "24",
                "--output",
                str(cli_path),
                "--json",
            ],
            stdout=io.StringIO(),
            dependencies=dependencies,
        )
        == 0
    )

    application = DashboardApplication(
        serial_backend_factory=MemorySerialBackend,
        job_id_factory=lambda: "equivalent-product-job",
    )
    assert application.next()
    assert application.select_job(ProductJobType.DC_ANALYSIS)
    assert application.next()
    draft = replace(application.wizard_state.draft, sample_count="24")
    assert application.prepare_review(draft)
    assert application.run()
    _wait_for_result(application)
    assert application.export_result(str(dashboard_path), "json")
    assert application.request_close()

    assert _stable_document(cli_path) == _stable_document(dashboard_path)
