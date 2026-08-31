"""Minimal installed CLI for product identity and reviewed profile discovery."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import NoReturn, TextIO

from analog_validation import __version__

from .catalog import PRODUCT_CATALOG_SCHEMA_VERSION, list_product_profiles
from .errors import CliUsageError, ProductAppError
from .issues import UserIssue, issue_from_exception

CLI_OUTPUT_SCHEMA_VERSION = "product-cli-output.v1"
CLI_USAGE_EXIT_CODE = 2
PRODUCT_DISPLAY_NAME = "Analog Validation Studio"


@dataclass(frozen=True, slots=True)
class _ParserExit(Exception):
    status: int
    message: str | None = None


class _CliParser(argparse.ArgumentParser):
    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        raise _ParserExit(status, message)

    def error(self, message: str) -> NoReturn:
        raise CliUsageError(message)


def build_parser() -> argparse.ArgumentParser:
    """Build the Step 1 parser without importing serial or GUI packages."""

    parser = _CliParser(
        prog="analog-validation",
        description=(
            "Controller-neutral analog validation software. "
            "Step 1 provides product identity and reviewed profiles only."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")

    version_parser = commands.add_parser(
        "version",
        help="show the installed product version",
    )
    version_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit versioned machine-readable JSON",
    )

    profiles_parser = commands.add_parser(
        "profiles",
        help="list exact reviewed profile identities and read-only product access",
    )
    profiles_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit versioned machine-readable JSON",
    )
    return parser


def _version_document() -> dict[str, object]:
    return {
        "schema_version": CLI_OUTPUT_SCHEMA_VERSION,
        "command": "version",
        "product": PRODUCT_DISPLAY_NAME,
        "software_version": __version__,
    }


def _profile_document() -> dict[str, object]:
    profiles = [
        {
            "name": profile.name,
            "version": profile.version,
            "display_name": profile.display_name,
            "summary": profile.summary,
            "source_modes": [mode.value for mode in profile.source_modes],
            "product_read_only": profile.product_read_only,
        }
        for profile in list_product_profiles()
    ]
    return {
        "schema_version": CLI_OUTPUT_SCHEMA_VERSION,
        "catalog_schema_version": PRODUCT_CATALOG_SCHEMA_VERSION,
        "command": "profiles",
        "product": PRODUCT_DISPLAY_NAME,
        "software_version": __version__,
        "profiles": profiles,
        "hardware_claim": "NONE",
    }


def _write_json(document: dict[str, object], stream: TextIO) -> None:
    stream.write(json.dumps(document, ensure_ascii=True, sort_keys=True))
    stream.write("\n")


def _write_profiles(stream: TextIO) -> None:
    stream.write("Reviewed profiles (Phase 5 product access is read-only):\n")
    for profile in list_product_profiles():
        sources = ", ".join(mode.value for mode in profile.source_modes)
        stream.write(f"- {profile.identity}: {profile.display_name}\n")
        stream.write(f"  {profile.summary}\n")
        stream.write(f"  Sources: {sources}\n")
    stream.write(
        "Listing a profile proves software support only; it does not validate hardware.\n"
    )


def _write_issue(issue: UserIssue, stream: TextIO) -> None:
    stream.write(f"{issue.severity.value} [{issue.code.value}]\n")
    stream.write(f"What happened: {issue.what_happened}\n")
    stream.write(f"Possible cause: {issue.possible_cause}\n")
    stream.write(f"Safe next step: {issue.safe_next_step}\n")


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the Step 1 CLI and return a stable process exit code."""

    output = stdout or sys.stdout
    errors = stderr or sys.stderr
    parser = build_parser()
    try:
        arguments = parser.parse_args(argv)
    except _ParserExit as exit_request:
        if exit_request.message:
            output.write(exit_request.message)
        return exit_request.status
    except ProductAppError as error:
        _write_issue(issue_from_exception(error), errors)
        return CLI_USAGE_EXIT_CODE

    if arguments.command is None:
        parser.print_help(file=output)
        return 0
    if arguments.command == "version":
        if arguments.as_json:
            _write_json(_version_document(), output)
        else:
            output.write(f"{PRODUCT_DISPLAY_NAME} {__version__}\n")
        return 0
    if arguments.command == "profiles":
        if arguments.as_json:
            _write_json(_profile_document(), output)
        else:
            _write_profiles(output)
        return 0
    raise AssertionError("argparse returned an unknown command")


__all__ = [
    "CLI_OUTPUT_SCHEMA_VERSION",
    "CLI_USAGE_EXIT_CODE",
    "PRODUCT_DISPLAY_NAME",
    "build_parser",
    "main",
]
