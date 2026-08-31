from __future__ import annotations

import argparse
import io
import json
import runpy
import sys
from types import SimpleNamespace

import pytest

import analog_validation_app.cli as cli_module
from analog_validation import __version__
from analog_validation_app.cli import (
    CLI_OUTPUT_SCHEMA_VERSION,
    CLI_USAGE_EXIT_CODE,
    PRODUCT_DISPLAY_NAME,
    build_parser,
    main,
)


def test_cli_parser_has_one_product_name_and_two_step1_commands() -> None:
    parser = build_parser()

    assert parser.prog == "analog-validation"
    assert parser.description is not None
    assert "Step 1" in parser.description
    choices = next(
        action.choices
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    assert tuple(choices) == ("version", "profiles")


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
    with pytest.raises(AssertionError, match="unknown command"):
        main([])


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
