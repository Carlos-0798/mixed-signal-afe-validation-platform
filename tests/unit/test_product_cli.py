from __future__ import annotations

import argparse
import io
import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import analog_validation_app.cli as cli_module
from analog_validation import EvidenceSource, __version__
from analog_validation import TestRunOutcome as RunOutcome
from analog_validation.protocol.msp430_health_v1 import (
    MSP430_HEALTH_CHANNEL_TEMPERATURE_DS,
    Msp430DeviceState,
    Msp430Telemetry,
    encode_msp430_message,
)
from analog_validation.transport import SerialPortInfo
from analog_validation_app import (
    ProductDependencyError,
    ProductJobExecution,
    ProductJobRequest,
    ProductJobResult,
    ProductJobType,
    ProductResultStatus,
    ProductServiceError,
    ProductSourceMode,
    ProductWorkerState,
)
from analog_validation_app.cli import (
    CLI_ENGINEERING_FAIL_EXIT_CODE,
    CLI_INCOMPLETE_EXIT_CODE,
    CLI_INTERNAL_ERROR_EXIT_CODE,
    CLI_OUTPUT_SCHEMA_VERSION,
    CLI_UNSUPPORTED_EXIT_CODE,
    CLI_USAGE_EXIT_CODE,
    PRODUCT_DISPLAY_NAME,
    CliDependencies,
    build_parser,
    main,
)
from tests.support import MemorySerialBackend

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_REPLAY = ROOT / "test-data" / "golden" / "csv_replay_v1_valid.csv"


def dependencies(
    backend: MemorySerialBackend | None = None,
) -> CliDependencies:
    selected = backend or MemorySerialBackend()
    return CliDependencies(
        serial_backend_factory=lambda: selected,
        job_id_factory=lambda: "cli-test-job",
        event_id_factory=lambda: "internal-test-event",
    )


def test_cli_parser_has_one_product_name_and_stable_step3_commands() -> None:
    parser = build_parser()

    assert parser.prog == "analog-validation"
    assert parser.description is not None
    assert "receive-only" in parser.description
    choices = next(
        action.choices
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    assert tuple(choices) == (
        "version",
        "profiles",
        "ports",
        "simulate",
        "replay",
        "observe",
        "report",
        "demo",
        "dashboard",
    )


def test_cli_without_a_command_is_beginner_friendly_help() -> None:
    output = io.StringIO()
    errors = io.StringIO()

    assert main([], stdout=output, stderr=errors) == 0
    assert "usage: analog-validation" in output.getvalue()
    assert "version" in output.getvalue()
    assert "profiles" in output.getvalue()
    assert errors.getvalue() == ""


def test_cli_help_and_global_version_exit_cleanly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--help"]) == 0
    help_capture = capsys.readouterr()
    assert "Controller-neutral analog validation software" in help_capture.out
    assert help_capture.err == ""

    assert main(["--version"]) == 0
    version_capture = capsys.readouterr()
    assert version_capture.out == f"analog-validation {__version__}\n"
    assert version_capture.err == ""


def test_version_command_has_human_and_machine_views() -> None:
    human = io.StringIO()
    machine = io.StringIO()

    assert main(["version"], stdout=human) == 0
    assert human.getvalue() == f"{PRODUCT_DISPLAY_NAME} {__version__}\n"

    assert main(["version", "--json"], stdout=machine) == 0
    assert json.loads(machine.getvalue()) == {
        "schema_version": CLI_OUTPUT_SCHEMA_VERSION,
        "command": "version",
        "product": PRODUCT_DISPLAY_NAME,
        "software_version": __version__,
    }


def test_profiles_command_is_read_only_and_hardware_honest() -> None:
    output = io.StringIO()

    assert main(["profiles"], stdout=output) == 0
    text = output.getvalue()
    assert "Phase 5 product access is read-only" in text
    assert "afe/1" in text
    assert "msp430-equipment-health/1" in text
    assert "does not validate hardware" in text
    assert "write" not in text.lower()


def test_profiles_json_is_deterministic_and_explicit() -> None:
    first = io.StringIO()
    second = io.StringIO()

    assert main(["profiles", "--json"], stdout=first) == 0
    assert main(["profiles", "--json"], stdout=second) == 0
    assert first.getvalue() == second.getvalue()
    document = json.loads(first.getvalue())
    assert document["schema_version"] == CLI_OUTPUT_SCHEMA_VERSION
    assert document["catalog_schema_version"] == "product-catalog.v1"
    assert document["hardware_claim"] == "NONE"
    assert document["profiles"] == [
        {
            "name": "afe",
            "version": "1",
            "display_name": "Configurable AFE v1",
            "summary": (
                "Controller-neutral AFE records; Phase 5 product access "
                "remains receive-only."
            ),
            "source_modes": ["SIMULATOR", "CSV_REPLAY", "SERIAL_READ_ONLY"],
            "product_read_only": True,
        },
        {
            "name": "msp430-equipment-health",
            "version": "1",
            "display_name": "MSP430 Equipment Health v1",
            "summary": (
                "Independent peer telemetry profile with unavailable-safe mapping."
            ),
            "source_modes": ["SERIAL_READ_ONLY"],
            "product_read_only": True,
        },
    ]


def test_invalid_command_returns_structured_beginner_guidance() -> None:
    output = io.StringIO()
    errors = io.StringIO()

    assert main(["unknown"], stdout=output, stderr=errors) == CLI_USAGE_EXIT_CODE
    assert output.getvalue() == ""
    assert "ERROR [INVALID_REQUEST]" in errors.getvalue()
    assert "What happened:" in errors.getvalue()
    assert "Possible cause:" in errors.getvalue()
    assert "Safe next step:" in errors.getvalue()
    assert "Traceback" not in errors.getvalue()


def test_main_rejects_an_impossible_parser_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ImpossibleParser:
        def parse_args(self, _argv: object) -> SimpleNamespace:
            return SimpleNamespace(command="future")

    monkeypatch.setattr(cli_module, "build_parser", ImpossibleParser)
    errors = io.StringIO()
    assert main([], stderr=errors) == CLI_USAGE_EXIT_CODE
    assert "argparse returned an unknown command" in errors.getvalue()


def test_parser_exit_message_is_routed_to_selected_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StoppingParser:
        def parse_args(self, _argv: object) -> SimpleNamespace:
            raise cli_module._ParserExit(7, "stopped cleanly\n")

    output = io.StringIO()
    monkeypatch.setattr(cli_module, "build_parser", StoppingParser)

    assert main([], stdout=output) == 7
    assert output.getvalue() == "stopped cleanly\n"


def test_module_entrypoint_returns_the_cli_status(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["analog_validation_app", "version"])

    with pytest.raises(SystemExit) as stopped:
        runpy.run_module("analog_validation_app.__main__", run_name="__main__")

    assert stopped.value.code == 0
    assert capsys.readouterr().out == f"{PRODUCT_DISPLAY_NAME} {__version__}\n"


def test_ports_only_discovers_and_closes_without_opening() -> None:
    backend = MemorySerialBackend(
        ports=(SerialPortInfo("MEMORY:1", "In-memory test port"),)
    )
    output = io.StringIO()

    assert (
        main(
            ["ports", "--json"],
            stdout=output,
            dependencies=dependencies(backend),
        )
        == 0
    )

    document = json.loads(output.getvalue())
    assert document["opened_ports"] == 0
    assert document["ports"] == [
        {"port_id": "MEMORY:1", "description": "In-memory test port"}
    ]
    assert backend.discover_calls == 1
    assert backend.open_calls == []
    assert backend.close_calls == 1


def test_ports_human_empty_and_optional_dependency_guidance() -> None:
    output = io.StringIO()
    assert main(["ports"], stdout=output, dependencies=dependencies()) == 0
    assert "none were opened" in output.getvalue()
    assert "- none" in output.getvalue()

    errors = io.StringIO()
    unavailable = CliDependencies(
        serial_backend_factory=lambda: (_ for _ in ()).throw(
            ProductDependencyError("install serial extra")
        ),
        job_id_factory=lambda: "unused",
        event_id_factory=lambda: "unused",
    )
    assert (
        main(["ports"], stderr=errors, dependencies=unavailable)
        == CLI_UNSUPPORTED_EXIT_CODE
    )
    assert "OPTIONAL_DEPENDENCY" in errors.getvalue()
    assert "[serial]" in errors.getvalue()


def test_simulator_read_json_runs_the_real_worker_and_core_workflow() -> None:
    output = io.StringIO()
    errors = io.StringIO()

    assert (
        main(
            ["simulate", "read", "--samples", "3", "--json"],
            stdout=output,
            stderr=errors,
            dependencies=dependencies(),
        )
        == 0
    )

    document = json.loads(output.getvalue())
    assert document["request"] == {
        "job_id": "cli-test-job",
        "source_mode": "SIMULATOR",
        "job_type": "READ",
        "profile_name": "afe",
        "profile_version": "1",
        "read_only": True,
    }
    assert document["worker"]["state"] == "SUCCEEDED"
    assert document["result"]["status"] == "COMPLETED"
    assert document["result"]["engineering_conclusion"] is False
    assert len(document["read"]["measurements"]) == 3
    assert document["hardware_claim"] == "NO_PERFORMANCE_VALIDATION"
    assert errors.getvalue() == ""


def test_simulator_digital_read_and_human_evidence_boundary() -> None:
    output = io.StringIO()
    status = main(
        [
            "simulate",
            "read",
            "--operation",
            "digital",
            "--channel",
            "afe.ch0.threshold",
            "--unit",
            "bool",
            "--samples",
            "2",
        ],
        stdout=output,
        dependencies=dependencies(),
    )
    assert status == 0
    assert "Evidence source: SYNTHETIC" in output.getvalue()
    assert "Measurements: 2" in output.getvalue()
    assert "Hardware performance validation: NOT CLAIMED" in output.getvalue()


def test_simulator_dc_pass_fail_and_default_no_overwrite(tmp_path: Path) -> None:
    destination = tmp_path / "dc-result.json"
    machine = io.StringIO()
    assert (
        main(
            [
                "simulate",
                "dc",
                "--points",
                "6",
                "--output",
                str(destination),
                "--json",
            ],
            stdout=machine,
            dependencies=dependencies(),
        )
        == 0
    )
    document = json.loads(machine.getvalue())
    assert document["result"]["test_run_outcome"] == "PASS"
    assert document["result_export"]["test_run"]["outcome"] == "PASS"
    assert document["artifact"]["format"] == "json"
    assert len(document["artifact"]["sha256"]) == 64
    original = destination.read_bytes()

    errors = io.StringIO()
    assert (
        main(
            ["simulate", "dc", "--points", "6", "--output", str(destination)],
            stderr=errors,
            dependencies=dependencies(),
        )
        == 5
    )
    assert "OUTPUT_EXISTS" in errors.getvalue()
    assert destination.read_bytes() == original

    failed = io.StringIO()
    assert (
        main(
            [
                "simulate",
                "dc",
                "--points",
                "6",
                "--target-gain",
                "99",
                "--gain-tolerance",
                "0",
            ],
            stdout=failed,
            dependencies=dependencies(),
        )
        == CLI_ENGINEERING_FAIL_EXIT_CODE
    )
    assert "Engineering outcome: FAIL" in failed.getvalue()


def test_simulator_hysteresis_pass_and_csv_export(tmp_path: Path) -> None:
    destination = tmp_path / "hysteresis.csv"
    output = io.StringIO()

    assert (
        main(
            [
                "simulate",
                "hysteresis",
                "--output",
                str(destination),
                "--format",
                "csv",
                "--json",
            ],
            stdout=output,
            dependencies=dependencies(),
        )
        == 0
    )

    document = json.loads(output.getvalue())
    assert document["result"]["test_run_outcome"] == "PASS"
    assert document["artifact"]["format"] == "csv"
    assert destination.read_text(encoding="utf-8").startswith(
        "format_version,row_type,row_index,payload"
    )


def test_replay_read_and_incomplete_analysis_keep_replay_evidence() -> None:
    read_output = io.StringIO()
    assert (
        main(
            [
                "replay",
                "read",
                "--input",
                str(GOLDEN_REPLAY),
                "--samples",
                "2",
                "--json",
            ],
            stdout=read_output,
            dependencies=dependencies(),
        )
        == 0
    )
    assert json.loads(read_output.getvalue())["result"]["evidence_source"] == (
        "CSV_REPLAY"
    )

    dc_output = io.StringIO()
    assert (
        main(
            [
                "replay",
                "dc",
                "--input",
                str(GOLDEN_REPLAY),
                "--points",
                "2",
                "--json",
            ],
            stdout=dc_output,
            dependencies=dependencies(),
        )
        == CLI_INCOMPLETE_EXIT_CODE
    )
    document = json.loads(dc_output.getvalue())
    assert document["result"]["status"] == "INCOMPLETE"
    assert document["result"]["test_run_outcome"] == "INCOMPLETE"
    assert document["hardware_claim"] == "NO_PERFORMANCE_VALIDATION"


def test_observe_requires_confirmation_before_backend_construction() -> None:
    backend = MemorySerialBackend()
    errors = io.StringIO()
    assert (
        main(
            [
                "observe",
                "--port",
                "MEMORY:MSP",
                "--profile",
                "msp430-equipment-health",
                "--channel",
                MSP430_HEALTH_CHANNEL_TEMPERATURE_DS,
                "--operation",
                "analog",
                "--unit",
                "degC",
            ],
            stderr=errors,
            dependencies=dependencies(backend),
        )
        == CLI_USAGE_EXIT_CODE
    )
    assert "confirm-read-only" in errors.getvalue()
    assert backend.open_calls == []
    assert backend.read_calls == []


def test_observe_msp430_memory_stream_is_bounded_receive_only() -> None:
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
    backend = MemorySerialBackend.scripted(reads=(record,))
    output = io.StringIO()

    assert (
        main(
            [
                "observe",
                "--port",
                "MEMORY:MSP",
                "--profile",
                "msp430-equipment-health",
                "--channel",
                MSP430_HEALTH_CHANNEL_TEMPERATURE_DS,
                "--operation",
                "analog",
                "--unit",
                "degC",
                "--max-records",
                "1",
                "--confirm-read-only",
                "--json",
            ],
            stdout=output,
            dependencies=dependencies(backend),
        )
        == 0
    )

    document = json.loads(output.getvalue())
    assert document["request"]["source_mode"] == "SERIAL_READ_ONLY"
    assert document["result"]["evidence_source"] == "HOST_TEST"
    assert document["read"]["measurements"][0]["value"] == 42.1
    assert backend.open_calls[0].port_id == "MEMORY:MSP"
    assert len(backend.read_calls) == 1
    assert backend.close_calls == 1
    assert not hasattr(backend, "write_calls")


@pytest.mark.parametrize("command", ["demo", "dashboard"])
def test_reserved_commands_are_stable_but_honestly_unavailable(command: str) -> None:
    errors = io.StringIO()
    assert (
        main([command, "--json"], stderr=errors, dependencies=dependencies())
        == CLI_UNSUPPORTED_EXIT_CODE
    )
    document = json.loads(errors.getvalue())
    assert document["issue"]["code"] == "CAPABILITY_UNAVAILABLE"
    assert "later reviewed" in document["issue"]["what_happened"]


@pytest.mark.parametrize(
    "argv",
    [
        ["simulate"],
        ["replay"],
        ["simulate", "read", "--samples", "0"],
        ["simulate", "read", "--operation", "digital", "--unit", "mV"],
        [
            "simulate",
            "hysteresis",
            "--rising-count",
            "6000",
            "--falling-count",
            "6000",
        ],
    ],
)
def test_invalid_workflow_requests_return_usage_without_traceback(
    argv: list[str],
) -> None:
    errors = io.StringIO()
    assert main(argv, stderr=errors, dependencies=dependencies()) == CLI_USAGE_EXIT_CODE
    assert "INVALID_REQUEST" in errors.getvalue()
    assert "Traceback" not in errors.getvalue()


def test_unexpected_error_is_redacted_unless_debug_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("developer-only-secret")

    monkeypatch.setattr(cli_module, "_execute_workflow", fail)
    errors = io.StringIO()
    assert (
        main(
            ["simulate", "read"],
            stderr=errors,
            dependencies=dependencies(),
        )
        == CLI_INTERNAL_ERROR_EXIT_CODE
    )
    assert "internal-test-event" in errors.getvalue()
    assert "developer-only-secret" not in errors.getvalue()
    assert "Traceback" not in errors.getvalue()

    debug_errors = io.StringIO()
    assert (
        main(
            ["--debug", "simulate", "read"],
            stderr=debug_errors,
            dependencies=dependencies(),
        )
        == CLI_INTERNAL_ERROR_EXIT_CODE
    )
    assert "Traceback" in debug_errors.getvalue()
    assert "developer-only-secret" in debug_errors.getvalue()


def test_default_identifier_factories_produce_bounded_prefixed_ids() -> None:
    assert cli_module._new_job_id().startswith("cli-")
    assert cli_module._new_event_id().startswith("internal-")


@pytest.mark.parametrize(
    "field",
    ["serial_backend_factory", "job_id_factory", "event_id_factory"],
)
def test_cli_dependencies_reject_noncallable_factories(field: str) -> None:
    values: dict[str, object] = {
        "serial_backend_factory": MemorySerialBackend,
        "job_id_factory": lambda: "job",
        "event_id_factory": lambda: "event",
    }
    values[field] = object()
    with pytest.raises(cli_module.CliUsageError, match=field):
        CliDependencies(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "argv",
    [
        ["simulate", "read", "--samples", "not-an-integer"],
        ["simulate", "dc", "--target-gain", "not-a-number"],
        ["simulate", "dc", "--target-gain", "nan"],
    ],
)
def test_cli_numeric_parsers_reject_non_numeric_and_non_finite(argv: list[str]) -> None:
    errors = io.StringIO()
    assert main(argv, stderr=errors, dependencies=dependencies()) == CLI_USAGE_EXIT_CODE
    assert "INVALID_REQUEST" in errors.getvalue()


def test_replay_hysteresis_uses_explicit_analog_and_digital_projection() -> None:
    output = io.StringIO()
    assert (
        main(
            [
                "replay",
                "hysteresis",
                "--input",
                str(GOLDEN_REPLAY),
                "--rising-count",
                "2",
                "--falling-count",
                "2",
                "--json",
            ],
            stdout=output,
            dependencies=dependencies(),
        )
        == CLI_INCOMPLETE_EXIT_CODE
    )
    document = json.loads(output.getvalue())
    assert document["request"]["job_type"] == "HYSTERESIS_ANALYSIS"
    assert document["result"]["evidence_source"] == "CSV_REPLAY"
    assert document["read"]["status"] == "INCOMPLETE"


def test_ports_human_view_lists_description_without_opening() -> None:
    backend = MemorySerialBackend(ports=(SerialPortInfo("MEMORY:2", "Readable name"),))
    output = io.StringIO()
    assert main(["ports"], stdout=output, dependencies=dependencies(backend)) == 0
    assert "MEMORY:2 - Readable name" in output.getvalue()
    assert backend.open_calls == []


def test_human_analysis_output_prints_artifact_identity(tmp_path: Path) -> None:
    output = io.StringIO()
    destination = tmp_path / "human-result.json"
    assert (
        main(
            ["simulate", "dc", "--points", "4", "--output", str(destination)],
            stdout=output,
            dependencies=dependencies(),
        )
        == 0
    )
    assert f"Artifact: {destination.resolve()}" in output.getvalue()
    assert "SHA-256:" in output.getvalue()


def test_worker_side_expected_failure_prints_issue_without_traceback(
    tmp_path: Path,
) -> None:
    output = io.StringIO()
    errors = io.StringIO()
    assert (
        main(
            ["replay", "read", "--input", str(tmp_path / "missing.csv")],
            stdout=output,
            stderr=errors,
            dependencies=dependencies(),
        )
        == 5
    )
    assert "Worker state: FAILED" in output.getvalue()
    assert "INPUT_DATA" in errors.getvalue()
    assert "Traceback" not in errors.getvalue()


def _execution_for_status(
    status: ProductResultStatus | None,
    *,
    worker_state: ProductWorkerState = ProductWorkerState.SUCCEEDED,
    interrupted: bool = False,
) -> ProductJobExecution:
    request = ProductJobRequest(
        "exit-code",
        ProductSourceMode.SIMULATOR,
        ProductJobType.READ,
        "afe",
        "1",
    )
    outcomes = {
        ProductResultStatus.COMPLETED: None,
        ProductResultStatus.INCOMPLETE: RunOutcome.INCOMPLETE,
        ProductResultStatus.UNSUPPORTED: RunOutcome.UNSUPPORTED,
        ProductResultStatus.CANCELLED: RunOutcome.ABORTED,
        ProductResultStatus.ERROR: RunOutcome.ERROR,
    }
    result = (
        None
        if status is None
        else ProductJobResult(
            request,
            status,
            EvidenceSource.SYNTHETIC,
            ("Exit-code unit test; no hardware.",),
            outcomes[status],
        )
    )
    return ProductJobExecution(
        request,
        worker_state,
        result,
        None,
        (),
        None,
        0,
        interrupted,
    )


@pytest.mark.parametrize(
    ("execution", "expected"),
    [
        (_execution_for_status(None, interrupted=True), 130),
        (
            _execution_for_status(
                ProductResultStatus.CANCELLED,
                worker_state=ProductWorkerState.CANCELLED,
            ),
            130,
        ),
        (_execution_for_status(None, worker_state=ProductWorkerState.FAILED), 5),
        (_execution_for_status(None), 5),
        (_execution_for_status(ProductResultStatus.UNSUPPORTED), 4),
        (_execution_for_status(ProductResultStatus.CANCELLED), 130),
        (_execution_for_status(ProductResultStatus.ERROR), 5),
    ],
)
def test_execution_exit_code_covers_every_non_pass_terminal(
    execution: ProductJobExecution, expected: int
) -> None:
    assert cli_module._execution_exit_code(execution) == expected


def test_presentation_helpers_reject_impossible_internal_values(tmp_path: Path) -> None:
    with pytest.raises(cli_module.CliUsageError, match="measurement"):
        cli_module._measurement_document(object())
    with pytest.raises(ProductServiceError, match="result export"):
        cli_module._write_artifact(
            argparse.Namespace(output=tmp_path / "unused.json", output_format="json"),
            _execution_for_status(ProductResultStatus.COMPLETED),
        )


def test_output_request_never_masks_failed_or_incomplete_execution(
    tmp_path: Path,
) -> None:
    arguments = argparse.Namespace(
        output=tmp_path / "must-not-exist.json", output_format="json"
    )

    assert (
        cli_module._write_artifact(
            arguments,
            _execution_for_status(None, worker_state=ProductWorkerState.FAILED),
        )
        is None
    )
    assert (
        cli_module._write_artifact(
            arguments,
            _execution_for_status(ProductResultStatus.INCOMPLETE),
        )
        is None
    )
    assert not arguments.output.exists()
