"""Stable command-line workflows for Analog Validation Studio."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import traceback
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn, TextIO, cast
from uuid import uuid4

from analog_validation import (
    AnalogValidationError,
    EvidenceSource,
    Measurement,
    MeasurementUnit,
    ReadOperation,
    TestRunOutcome,
    __version__,
)
from analog_validation.exports import (
    CALIBRATION_COEFFICIENTS_SCHEMA_VERSION,
    ResultExportBundle,
    ResultExportExistsError,
    ResultExportPathError,
    calibration_coefficients_to_dict,
    load_calibration_coefficients_json,
    load_result_export_csv,
    load_result_export_json,
    result_export_to_dict,
    write_calibration_coefficients_json,
    write_result_export_csv,
    write_result_export_json,
)

from .catalog import PRODUCT_CATALOG_SCHEMA_VERSION, list_product_profiles
from .demo import PortfolioDemoPublication, publish_portfolio_demo
from .errors import (
    CliUsageError,
    ProductAppError,
    ProductRequestError,
    ProductServiceError,
)
from .factories import (
    SerialBackendFactory,
    SerialChannelAlias,
    SerialSourceConfig,
    default_serial_backend_factory,
    discover_serial_ports,
)
from .import_cli import (
    add_import_csv_parser,
    execute_import_csv,
    write_import_csv_document,
)
from .issues import UserIssue, UserIssueCode, issue_from_exception, user_issue_to_dict
from .models import (
    ProductJobType,
    ProductResultStatus,
    ProductSourceMode,
    ProductWorkerState,
)
from .presentation import (
    REPORT_HARDWARE_CLAIM,
    HumanReportView,
    build_human_report_view,
)
from .product_workflows import ProductWorkflowConfiguration, prepare_product_job
from .projects import (
    MAX_VALIDATION_HISTORY_INPUTS,
    VALIDATION_RUN_MANIFEST_FILENAME,
    ValidationBatchPhase,
    ValidationBatchProgress,
    ValidationBatchStatus,
    ValidationProject,
    ValidationRunManifest,
    build_default_validation_project,
    compare_validation_runs,
    load_validation_project,
    load_validation_run_manifest,
    publish_validation_project_run,
    validation_project_to_dict,
    validation_run_comparison_to_dict,
    validation_run_manifest_to_dict,
    write_validation_project,
)
from .reporting import HumanReportPublication, publish_human_report
from .services import (
    ProductJobExecution,
    execute_product_job,
)

if TYPE_CHECKING:
    from .dashboard.app import DashboardSessionResult

CLI_OUTPUT_SCHEMA_VERSION = "product-cli-output.v2"
CLI_USAGE_EXIT_CODE = 2
CLI_ENGINEERING_FAIL_EXIT_CODE = 1
CLI_INCOMPLETE_EXIT_CODE = 3
CLI_UNSUPPORTED_EXIT_CODE = 4
CLI_OPERATION_ERROR_EXIT_CODE = 5
CLI_INTERNAL_ERROR_EXIT_CODE = 70
CLI_CANCELLED_EXIT_CODE = 130
MAX_CLI_SAMPLES = 10_000
PRODUCT_DISPLAY_NAME = "Analog Validation Studio"

IdentifierFactory = Callable[[], str]
DashboardLauncher = Callable[[], "DashboardSessionResult"]


def _new_job_id() -> str:
    return f"cli-{uuid4()}"


def _new_event_id() -> str:
    return f"internal-{uuid4()}"


@dataclass(frozen=True, slots=True)
class CliDependencies:
    """Injectable resource factories keep CLI tests away from physical ports."""

    serial_backend_factory: SerialBackendFactory = default_serial_backend_factory
    job_id_factory: IdentifierFactory = _new_job_id
    event_id_factory: IdentifierFactory = _new_event_id
    dashboard_launcher: DashboardLauncher | None = None

    def __post_init__(self) -> None:
        for name in (
            "serial_backend_factory",
            "job_id_factory",
            "event_id_factory",
        ):
            if not callable(getattr(self, name)):
                raise CliUsageError(f"{name} must be callable")
        if self.dashboard_launcher is not None and not callable(
            self.dashboard_launcher
        ):
            raise CliUsageError("dashboard_launcher must be callable or None")


@dataclass(frozen=True, slots=True)
class _ParserExit(Exception):
    status: int
    message: str | None = None


class _CliParser(argparse.ArgumentParser):
    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        raise _ParserExit(status, message)

    def error(self, message: str) -> NoReturn:
        raise CliUsageError(message)


def _bounded_integer(name: str, minimum: int, maximum: int) -> Callable[[str], int]:
    def parse(value: str) -> int:
        try:
            checked = int(value)
        except ValueError as error:
            raise argparse.ArgumentTypeError(f"{name} must be an integer") from error
        if not minimum <= checked <= maximum:
            raise argparse.ArgumentTypeError(
                f"{name} must be between {minimum} and {maximum}"
            )
        return checked

    return parse


def _finite_number(name: str) -> Callable[[str], float]:
    def parse(value: str) -> float:
        try:
            checked = float(value)
        except ValueError as error:
            raise argparse.ArgumentTypeError(f"{name} must be numeric") from error
        if not math.isfinite(checked):
            raise argparse.ArgumentTypeError(f"{name} must be finite")
        return checked

    return parse


def _serial_channel_alias(value: str) -> SerialChannelAlias:
    try:
        return SerialChannelAlias.parse(value)
    except ProductRequestError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def _add_serial_device_contract(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--expected-device-id",
        help=(
            "require an exact capability device_id match before reading measurements"
        ),
    )
    parser.add_argument(
        "--afe-adc-alias",
        action="append",
        type=_serial_channel_alias,
        metavar="ADC=CANONICAL",
        help=(
            "explicit AFE v1 ADC observation mapping, for example "
            "adc1=afe.ch0.output; repeat for every advertised ADC channel"
        ),
    )


def _add_machine_view(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit versioned machine-readable JSON",
    )


def _add_profile(parser: argparse.ArgumentParser, *, required: bool = False) -> None:
    parser.add_argument(
        "--profile",
        required=required,
        default=None if required else "afe",
        help="exact reviewed profile name",
    )
    parser.add_argument(
        "--profile-version",
        default="1",
        help="exact reviewed profile version",
    )


def _add_export(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output",
        type=Path,
        help="write a finalized result export; existing files are rejected",
    )
    parser.add_argument(
        "--format",
        choices=("json", "csv"),
        default="json",
        dest="output_format",
        help="result-export file format used with --output",
    )


def _add_read_options(
    parser: argparse.ArgumentParser,
    *,
    default_channel: str = "afe.ch0.input",
) -> None:
    parser.add_argument("--channel", default=default_channel)
    parser.add_argument(
        "--operation",
        choices=("analog", "digital"),
        default="analog",
    )
    parser.add_argument(
        "--unit",
        choices=tuple(unit.value for unit in MeasurementUnit),
        default=MeasurementUnit.MILLIVOLT.value,
    )
    parser.add_argument(
        "--samples",
        type=_bounded_integer("samples", 1, MAX_CLI_SAMPLES),
        default=5,
    )
    _add_machine_view(parser)


def _add_live_monitor_options(
    parser: argparse.ArgumentParser,
    *,
    default_cycles: int = 50,
    default_sample_interval: float = 0.02,
    default_include_secondary: bool = True,
    default_include_state: bool = True,
    primary_channel_required: bool = False,
) -> None:
    parser.add_argument(
        "--primary-channel",
        default=None if primary_channel_required else "afe.ch0.input",
        required=primary_channel_required,
        help=(
            "exact readable channel advertised by the selected serial profile"
            if primary_channel_required
            else None
        ),
    )
    parser.add_argument("--secondary-channel", default="afe.ch0.output")
    parser.add_argument("--state-channel", default="afe.ch0.threshold")
    parser.add_argument(
        "--unit",
        choices=(MeasurementUnit.MILLIVOLT.value, MeasurementUnit.VOLT.value),
        default=MeasurementUnit.MILLIVOLT.value,
    )
    parser.add_argument(
        "--cycles",
        type=_bounded_integer("cycles", 1, MAX_CLI_SAMPLES),
        default=default_cycles,
        help="finite number of sample cycles; this command never runs forever",
    )
    parser.add_argument(
        "--sample-interval",
        type=_finite_number("sample-interval"),
        default=default_sample_interval,
        help="seconds between complete sample cycles",
    )
    parser.add_argument(
        "--time-window",
        type=_finite_number("time-window"),
        default=5.0,
        help="trailing seconds selected for presentation",
    )
    parser.add_argument(
        "--max-buffer-points",
        type=_bounded_integer("max-buffer-points", 1, MAX_CLI_SAMPLES),
        default=2048,
        help="hard upper bound for retained live-view points",
    )
    secondary = parser.add_mutually_exclusive_group()
    secondary.add_argument(
        "--secondary",
        action="store_true",
        dest="include_secondary",
        help=(
            "include the secondary analog channel (default)"
            if default_include_secondary
            else "include the secondary analog channel"
        ),
    )
    secondary.add_argument(
        "--no-secondary",
        action="store_false",
        dest="include_secondary",
        help=(
            "omit the secondary analog channel"
            if default_include_secondary
            else "omit the secondary analog channel (default)"
        ),
    )
    state = parser.add_mutually_exclusive_group()
    state.add_argument(
        "--state",
        action="store_true",
        dest="include_state",
        help=(
            "include the boolean state channel (default)"
            if default_include_state
            else "include the boolean state channel"
        ),
    )
    state.add_argument(
        "--no-state",
        action="store_false",
        dest="include_state",
        help=(
            "omit the boolean state channel"
            if default_include_state
            else "omit the boolean state channel (default)"
        ),
    )
    parser.set_defaults(
        include_secondary=default_include_secondary,
        include_state=default_include_state,
    )
    _add_machine_view(parser)


def _add_dc_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input-channel", default="afe.ch0.input")
    parser.add_argument("--output-channel", default="afe.ch0.output")
    parser.add_argument(
        "--unit",
        choices=(MeasurementUnit.MILLIVOLT.value, MeasurementUnit.VOLT.value),
        default=MeasurementUnit.MILLIVOLT.value,
    )
    parser.add_argument(
        "--points",
        type=_bounded_integer("points", 2, MAX_CLI_SAMPLES),
        default=24,
    )
    parser.add_argument(
        "--low-output-limit", type=_finite_number("low-output-limit"), default=25.0
    )
    parser.add_argument(
        "--high-output-limit",
        type=_finite_number("high-output-limit"),
        default=3275.0,
    )
    parser.add_argument(
        "--target-gain", type=_finite_number("target-gain"), default=2.0
    )
    parser.add_argument(
        "--gain-tolerance", type=_finite_number("gain-tolerance"), default=0.05
    )
    parser.add_argument(
        "--max-abs-offset", type=_finite_number("max-abs-offset"), default=25.0
    )
    parser.add_argument(
        "--min-r-squared", type=_finite_number("min-r-squared"), default=0.999
    )
    parser.add_argument("--max-rmse", type=_finite_number("max-rmse"), default=1.0)
    _add_machine_view(parser)
    _add_export(parser)


def _add_hysteresis_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input-channel", default="afe.ch0.input")
    parser.add_argument("--state-channel", default="afe.ch0.threshold")
    parser.add_argument(
        "--unit",
        choices=(MeasurementUnit.MILLIVOLT.value, MeasurementUnit.VOLT.value),
        default=MeasurementUnit.MILLIVOLT.value,
    )
    parser.add_argument(
        "--rising-count",
        type=_bounded_integer("rising-count", 2, MAX_CLI_SAMPLES),
        default=12,
    )
    parser.add_argument(
        "--falling-count",
        type=_bounded_integer("falling-count", 2, MAX_CLI_SAMPLES),
        default=22,
    )
    parser.add_argument(
        "--minimum-high-threshold",
        type=_finite_number("minimum-high-threshold"),
        default=900.0,
    )
    parser.add_argument(
        "--maximum-high-threshold",
        type=_finite_number("maximum-high-threshold"),
        default=1100.0,
    )
    parser.add_argument(
        "--minimum-low-threshold",
        type=_finite_number("minimum-low-threshold"),
        default=800.0,
    )
    parser.add_argument(
        "--maximum-low-threshold",
        type=_finite_number("maximum-low-threshold"),
        default=1000.0,
    )
    parser.add_argument(
        "--minimum-width", type=_finite_number("minimum-width"), default=20.0
    )
    parser.add_argument(
        "--maximum-width", type=_finite_number("maximum-width"), default=200.0
    )
    parser.add_argument(
        "--maximum-width-span",
        type=_finite_number("maximum-width-span"),
        default=0.0,
    )
    _add_machine_view(parser)
    _add_export(parser)


def _add_calibration_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--observed-channel", default="afe.ch0.input")
    parser.add_argument("--reference-channel", default="afe.ch0.output")
    parser.add_argument(
        "--unit",
        choices=(MeasurementUnit.MILLIVOLT.value, MeasurementUnit.VOLT.value),
        default=MeasurementUnit.MILLIVOLT.value,
    )
    parser.add_argument(
        "--points",
        type=_bounded_integer("points", 2, MAX_CLI_SAMPLES),
        default=8,
    )
    parser.add_argument("--coefficient-id", default="afe-linear-calibration")
    parser.add_argument("--coefficient-version", default="1")
    parser.add_argument(
        "--max-after-rmse",
        type=_finite_number("max-after-rmse"),
        default=1.0,
    )
    parser.add_argument(
        "--max-after-mean-absolute-error",
        type=_finite_number("max-after-mean-absolute-error"),
        default=1.0,
    )
    parser.add_argument(
        "--max-after-absolute-error",
        type=_finite_number("max-after-absolute-error"),
        default=2.0,
    )
    parser.add_argument(
        "--minimum-rmse-reduction",
        type=_finite_number("minimum-rmse-reduction"),
        default=0.0,
    )
    parser.add_argument(
        "--coefficients-output",
        type=Path,
        help="write versioned coefficient JSON; existing files are rejected",
    )
    _add_machine_view(parser)
    _add_export(parser)


def _add_frequency_response_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--frequency-channel", default="afe.ch0.frequency")
    parser.add_argument("--input-amplitude-channel", default="afe.ch0.input")
    parser.add_argument("--output-amplitude-channel", default="afe.ch0.output")
    parser.add_argument(
        "--unit",
        choices=(MeasurementUnit.MILLIVOLT.value, MeasurementUnit.VOLT.value),
        default=MeasurementUnit.MILLIVOLT.value,
    )
    parser.add_argument(
        "--points",
        type=_bounded_integer("points", 10, MAX_CLI_SAMPLES),
        default=21,
    )
    parser.add_argument(
        "--frequency-minimum-hz",
        type=_finite_number("frequency-minimum-hz"),
        default=10.0,
    )
    parser.add_argument(
        "--frequency-maximum-hz",
        type=_finite_number("frequency-maximum-hz"),
        default=100_000.0,
    )
    parser.add_argument(
        "--input-amplitude",
        type=_finite_number("input-amplitude"),
        default=1000.0,
        help="synthetic input amplitude; replay uses amplitudes from the CSV",
    )
    parser.add_argument(
        "--simulated-cutoff-hz",
        type=_finite_number("simulated-cutoff-hz"),
        default=1000.0,
        help="Simulator model cutoff; replay ignores this value",
    )
    parser.add_argument(
        "--target-cutoff-hz",
        type=_finite_number("target-cutoff-hz"),
        default=1000.0,
    )
    parser.add_argument(
        "--cutoff-relative-tolerance",
        type=_finite_number("cutoff-relative-tolerance"),
        default=0.15,
        help="fractional tolerance, for example 0.15 means +/-15 percent",
    )
    parser.add_argument(
        "--cutoff-drop-db",
        type=_finite_number("cutoff-drop-db"),
        default=3.010299956639812,
    )
    _add_machine_view(parser)
    _add_export(parser)


def _add_source_workflows(
    commands: argparse._SubParsersAction[_CliParser],
    source: str,
    help_text: str,
) -> None:
    source_parser = commands.add_parser(source, help=help_text)
    workflows = source_parser.add_subparsers(dest="workflow", metavar="WORKFLOW")

    read_parser = workflows.add_parser("read", help="run a bounded read-only workflow")
    _add_profile(read_parser)
    if source == "replay":
        read_parser.add_argument("--input", required=True, type=Path)
        read_parser.add_argument(
            "--minimum", type=_finite_number("minimum"), default=0.0
        )
        read_parser.add_argument(
            "--maximum", type=_finite_number("maximum"), default=3300.0
        )
    _add_read_options(read_parser)

    dc_parser = workflows.add_parser(
        "dc", help="acquire observations and run formal DC evaluation"
    )
    _add_profile(dc_parser)
    if source == "replay":
        dc_parser.add_argument("--input", required=True, type=Path)
        dc_parser.add_argument("--minimum", type=_finite_number("minimum"), default=0.0)
        dc_parser.add_argument(
            "--maximum", type=_finite_number("maximum"), default=3300.0
        )
    _add_dc_options(dc_parser)

    hysteresis_parser = workflows.add_parser(
        "hysteresis", help="run formal rising/falling hysteresis evaluation"
    )
    _add_profile(hysteresis_parser)
    if source == "replay":
        hysteresis_parser.add_argument("--input", required=True, type=Path)
        hysteresis_parser.add_argument(
            "--minimum", type=_finite_number("minimum"), default=0.0
        )
        hysteresis_parser.add_argument(
            "--maximum", type=_finite_number("maximum"), default=3300.0
        )
    _add_hysteresis_options(hysteresis_parser)

    calibration_parser = workflows.add_parser(
        "calibration",
        help="fit and evaluate versioned linear calibration coefficients",
    )
    _add_profile(calibration_parser)
    if source == "replay":
        calibration_parser.add_argument("--input", required=True, type=Path)
        calibration_parser.add_argument(
            "--minimum", type=_finite_number("minimum"), default=0.0
        )
        calibration_parser.add_argument(
            "--maximum", type=_finite_number("maximum"), default=3300.0
        )
    _add_calibration_options(calibration_parser)

    frequency_parser = workflows.add_parser(
        "frequency",
        help="evaluate an explicit amplitude response and -3 dB cutoff",
    )
    _add_profile(frequency_parser)
    if source == "replay":
        frequency_parser.add_argument("--input", required=True, type=Path)
        frequency_parser.add_argument(
            "--minimum", type=_finite_number("minimum"), default=0.0
        )
        frequency_parser.add_argument(
            "--maximum", type=_finite_number("maximum"), default=3300.0
        )
    _add_frequency_response_options(frequency_parser)

    monitor_parser = workflows.add_parser(
        "monitor",
        help="run a finite live-view session with a bounded in-memory trace",
    )
    _add_profile(monitor_parser)
    if source == "replay":
        monitor_parser.add_argument("--input", required=True, type=Path)
        monitor_parser.add_argument(
            "--minimum", type=_finite_number("minimum"), default=0.0
        )
        monitor_parser.add_argument(
            "--maximum", type=_finite_number("maximum"), default=3300.0
        )
    _add_live_monitor_options(monitor_parser)


def build_parser() -> argparse.ArgumentParser:
    """Build one CLI without importing pyserial or Tkinter at startup."""

    parser = _CliParser(
        prog="analog-validation",
        description=(
            "Controller-neutral analog validation software with deterministic "
            "simulation, CSV replay, and explicit receive-only serial access."
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="show developer traceback for an unexpected software defect",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")

    version_parser = commands.add_parser("version", help="show the installed version")
    _add_machine_view(version_parser)
    profiles_parser = commands.add_parser(
        "profiles", help="list exact reviewed profile identities"
    )
    _add_machine_view(profiles_parser)
    ports_parser = commands.add_parser(
        "ports", help="discover logical serial ports without opening them"
    )
    _add_machine_view(ports_parser)

    coefficients_parser = commands.add_parser(
        "coefficients",
        help="manage versioned calibration coefficient artifacts",
    )
    coefficient_commands = coefficients_parser.add_subparsers(
        dest="coefficient_command",
        metavar="ACTION",
    )
    inspect_coefficients_parser = coefficient_commands.add_parser(
        "inspect",
        help="strictly load and inspect a coefficient JSON without applying it",
    )
    inspect_coefficients_parser.add_argument("--input", required=True, type=Path)
    _add_machine_view(inspect_coefficients_parser)

    _add_source_workflows(
        commands, "simulate", "run deterministic software-only workflows"
    )
    _add_source_workflows(commands, "replay", "analyze an explicit local CSV replay")

    serial_parser = commands.add_parser(
        "serial",
        help="run explicit bounded receive-only serial workflows",
    )
    serial_workflows = serial_parser.add_subparsers(
        dest="serial_workflow",
        metavar="WORKFLOW",
    )
    serial_monitor_parser = serial_workflows.add_parser(
        "monitor",
        help="run a finite receive-only serial live-view session",
    )
    _add_profile(serial_monitor_parser, required=True)
    serial_monitor_parser.add_argument("--port", required=True)
    serial_monitor_parser.add_argument(
        "--baud-rate",
        type=_bounded_integer("baud-rate", 1, 4_000_000),
        default=115_200,
    )
    serial_monitor_parser.add_argument(
        "--read-timeout",
        type=_finite_number("read-timeout"),
        default=0.05,
    )
    serial_monitor_parser.add_argument(
        "--max-polls",
        type=_bounded_integer("max-polls", 1, 10_000),
        default=4,
    )
    serial_monitor_parser.add_argument(
        "--confirm-read-only",
        action="store_true",
        help="confirm that this command only receives and never sends bytes",
    )
    _add_serial_device_contract(serial_monitor_parser)
    _add_live_monitor_options(
        serial_monitor_parser,
        default_cycles=20,
        default_include_secondary=False,
        default_include_state=False,
        primary_channel_required=True,
    )

    observe_parser = commands.add_parser(
        "observe", help="run an explicit bounded receive-only serial read"
    )
    _add_profile(observe_parser, required=True)
    observe_parser.add_argument("--port", required=True)
    observe_parser.add_argument("--channel", required=True)
    observe_parser.add_argument(
        "--operation", choices=("analog", "digital"), required=True
    )
    observe_parser.add_argument(
        "--unit",
        choices=tuple(unit.value for unit in MeasurementUnit),
        required=True,
    )
    observe_parser.add_argument(
        "--max-records",
        type=_bounded_integer("max-records", 1, MAX_CLI_SAMPLES),
        default=10,
    )
    observe_parser.add_argument(
        "--baud-rate",
        type=_bounded_integer("baud-rate", 1, 4_000_000),
        default=115_200,
    )
    observe_parser.add_argument(
        "--read-timeout",
        type=_finite_number("read-timeout"),
        default=0.25,
    )
    observe_parser.add_argument(
        "--max-polls",
        type=_bounded_integer("max-polls", 1, 10_000),
        default=32,
    )
    observe_parser.add_argument(
        "--confirm-read-only",
        action="store_true",
        help="confirm that this command only receives and never sends bytes",
    )
    _add_serial_device_contract(observe_parser)
    _add_machine_view(observe_parser)

    project_parser = commands.add_parser(
        "project",
        help="create, run, inspect, and compare bounded local test projects",
    )
    project_actions = project_parser.add_subparsers(
        dest="project_action",
        metavar="ACTION",
    )
    create_project_parser = project_actions.add_parser(
        "create",
        help="create a six-preset software-only starter project",
    )
    create_project_parser.add_argument("--output", required=True, type=Path)
    create_project_parser.add_argument("--project-id", required=True)
    create_project_parser.add_argument("--name", required=True)
    create_project_parser.add_argument(
        "--description",
        default="Offline reusable AFE validation presets.",
    )
    _add_machine_view(create_project_parser)

    inspect_project_parser = project_actions.add_parser(
        "inspect",
        help="validate a project without opening its replay files or any device",
    )
    inspect_project_parser.add_argument("--input", required=True, type=Path)
    _add_machine_view(inspect_project_parser)

    run_project_parser = project_actions.add_parser(
        "run",
        help="run a bounded offline preset batch into a new history directory",
    )
    run_project_parser.add_argument("--input", required=True, type=Path)
    run_project_parser.add_argument("--output", required=True, type=Path)
    run_project_parser.add_argument("--run-id", required=True)
    run_project_parser.add_argument(
        "--preset",
        action="append",
        default=[],
        help="run one exact preset ID; repeat to select several; omit for all",
    )
    _add_machine_view(run_project_parser)

    history_project_parser = project_actions.add_parser(
        "history",
        help="verify and summarize explicit run manifests without directory scanning",
    )
    history_project_parser.add_argument(
        "--run",
        action="append",
        dest="run_files",
        required=True,
        type=Path,
        help=f"run manifest path (normally {VALIDATION_RUN_MANIFEST_FILENAME}); repeatable",
    )
    _add_machine_view(history_project_parser)

    compare_project_parser = project_actions.add_parser(
        "compare",
        help="compare copied outcomes and metrics from two verified runs",
    )
    compare_project_parser.add_argument("--left", required=True, type=Path)
    compare_project_parser.add_argument("--right", required=True, type=Path)
    _add_machine_view(compare_project_parser)

    report_parser = commands.add_parser(
        "report", help="build deterministic human reports from a result export"
    )
    report_parser.add_argument("--input", required=True, type=Path)
    report_parser.add_argument(
        "--input-format",
        choices=("auto", "json", "csv"),
        default="auto",
        help="result-export format; auto accepts .json or .csv",
    )
    report_parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="new report directory; an existing path is never overwritten",
    )
    _add_machine_view(report_parser)

    demo_parser = commands.add_parser(
        "demo", help="generate the reproducible software-only portfolio demo"
    )
    demo_parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="new demo directory; an existing path is never overwritten",
    )
    _add_machine_view(demo_parser)

    dashboard_parser = commands.add_parser(
        "dashboard", help="launch the local six-step validation dashboard"
    )
    _add_machine_view(dashboard_parser)
    add_import_csv_parser(commands)
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


def _coefficient_document(path: Path) -> dict[str, object]:
    coefficients = load_calibration_coefficients_json(path)
    return {
        "schema_version": CLI_OUTPUT_SCHEMA_VERSION,
        "command": "coefficients inspect",
        "product": PRODUCT_DISPLAY_NAME,
        "software_version": __version__,
        "coefficient_file": {
            "path": str(path.resolve()),
            "validated": True,
            "applied": False,
        },
        "coefficients": calibration_coefficients_to_dict(coefficients),
        "hardware_claim": "NO_PERFORMANCE_VALIDATION",
    }


def _write_coefficient_inspection(document: dict[str, object], stream: TextIO) -> None:
    coefficients = document["coefficients"]
    if not isinstance(coefficients, dict):  # pragma: no cover - internal invariant
        raise ProductServiceError("coefficient inspection document is malformed")
    stream.write(
        "Calibration coefficients: "
        f"{coefficients['coefficient_id']}/{coefficients['coefficient_version']}\n"
    )
    stream.write(
        "Mapping: reference = "
        f"{coefficients['scale']:g} * observed + {coefficients['offset']:g} "
        f"{coefficients['unit']}\n"
    )
    stream.write(
        f"Evidence: observed={coefficients['observed_source']}; "
        f"reference={coefficients['reference_source']}\n"
    )
    stream.write("Loaded and schema-validated: YES\n")
    stream.write("Applied to measurements: NO\n")
    stream.write("Hardware performance validation: NOT CLAIMED\n")


def _project_document(
    command: str,
    *,
    project: ValidationProject | None = None,
    project_path: Path | None = None,
    run: ValidationRunManifest | None = None,
    run_directory: Path | None = None,
    history: tuple[tuple[Path, ValidationRunManifest], ...] = (),
    comparison: dict[str, object] | None = None,
) -> dict[str, object]:
    document: dict[str, object] = {
        "schema_version": CLI_OUTPUT_SCHEMA_VERSION,
        "command": command,
        "product": PRODUCT_DISPLAY_NAME,
        "software_version": __version__,
        "hardware_claim": "NO_NEW_HARDWARE_VALIDATION",
        "resource_policy": (
            "OFFLINE_PROJECT_ONLY; no serial configuration is persisted or executed"
        ),
    }
    if project is not None:
        if project_path is None:
            raise ProductServiceError("project path is missing")
        document["project_file"] = {
            "path": str(project_path.resolve()),
            "overwrite": False,
        }
        document["project"] = validation_project_to_dict(
            project,
            project_directory=project_path.parent.resolve(),
        )
    if run is not None:
        if run_directory is None:
            raise ProductServiceError("run directory is missing")
        document["run_directory"] = str(run_directory.resolve())
        document["run_manifest"] = validation_run_manifest_to_dict(run)
    if history:
        document["runs"] = [
            {
                "path": str(path.resolve()),
                "manifest": validation_run_manifest_to_dict(manifest),
            }
            for path, manifest in history
        ]
    if comparison is not None:
        document["comparison"] = comparison
    return document


def _project_run_exit_code(manifest: ValidationRunManifest) -> int:
    if manifest.batch_status is ValidationBatchStatus.CANCELLED:
        return CLI_CANCELLED_EXIT_CODE
    if manifest.batch_status is ValidationBatchStatus.ERROR:
        return CLI_OPERATION_ERROR_EXIT_CODE
    if any(
        record.worker_state is ProductWorkerState.CANCELLED
        or record.product_status is ProductResultStatus.CANCELLED
        for record in manifest.records
    ):
        return CLI_CANCELLED_EXIT_CODE
    if any(
        record.worker_state is ProductWorkerState.FAILED
        or record.product_status is ProductResultStatus.ERROR
        for record in manifest.records
    ):
        return CLI_OPERATION_ERROR_EXIT_CODE
    if any(
        record.product_status is ProductResultStatus.UNSUPPORTED
        for record in manifest.records
    ):
        return CLI_UNSUPPORTED_EXIT_CODE
    if any(
        record.product_status is ProductResultStatus.INCOMPLETE
        for record in manifest.records
    ):
        return CLI_INCOMPLETE_EXIT_CODE
    if manifest.engineering_failures:
        return CLI_ENGINEERING_FAIL_EXIT_CODE
    return 0


def _execute_project_action(
    arguments: argparse.Namespace,
    *,
    progress_stream: TextIO | None = None,
) -> tuple[dict[str, object], int]:
    action = arguments.project_action
    if action == "create":
        project = build_default_validation_project(
            arguments.project_id,
            arguments.name,
            arguments.description,
        )
        written = write_validation_project(arguments.output, project)
        return (
            _project_document(
                "project create",
                project=project,
                project_path=written,
            ),
            0,
        )
    if action == "inspect":
        project = load_validation_project(arguments.input)
        return (
            _project_document(
                "project inspect",
                project=project,
                project_path=arguments.input,
            ),
            0,
        )
    if action == "run":
        project = load_validation_project(arguments.input)
        manifest = publish_validation_project_run(
            project,
            arguments.output,
            arguments.run_id,
            selected_preset_ids=tuple(arguments.preset),
            project_directory=arguments.input.parent.resolve(),
            report_progress=(
                None
                if progress_stream is None
                else lambda event: _write_project_progress(event, progress_stream)
            ),
        )
        return (
            _project_document(
                "project run",
                project=project,
                project_path=arguments.input,
                run=manifest,
                run_directory=arguments.output,
            ),
            _project_run_exit_code(manifest),
        )
    if action == "history":
        paths = tuple(arguments.run_files)
        if len(paths) > MAX_VALIDATION_HISTORY_INPUTS:
            raise CliUsageError(
                "project history exceeds the bounded run-manifest input limit"
            )
        resolved_paths = tuple(path.resolve() for path in paths)
        if len(resolved_paths) != len(set(resolved_paths)):
            raise CliUsageError("project history inputs cannot repeat")
        history = tuple(
            (path, load_validation_run_manifest(path)) for path in paths
        )
        project_ids = {manifest.project_id for _, manifest in history}
        if len(project_ids) != 1:
            raise CliUsageError(
                "project history inputs must belong to one project"
            )
        return _project_document("project history", history=history), 0
    if action == "compare":
        left = load_validation_run_manifest(arguments.left)
        right = load_validation_run_manifest(arguments.right)
        comparison = compare_validation_runs(left, right)
        return (
            _project_document(
                "project compare",
                comparison=validation_run_comparison_to_dict(comparison),
            ),
            0,
        )
    raise CliUsageError("project requires an ACTION")


def _write_project_progress(
    progress: ValidationBatchProgress, stream: TextIO
) -> None:
    prefix = f"[run {progress.run_id}] {progress.phase.value}"
    if progress.phase is ValidationBatchPhase.FINISHED:
        if progress.batch_status is None:  # pragma: no cover - progress invariant
            raise ProductServiceError("finished batch progress is missing status")
        stream.write(
            f"{prefix} status={progress.batch_status.value}; "
            f"completed={progress.completed_presets}/{progress.total_presets}\n"
        )
        return
    current = ""
    if progress.current_preset_id is not None:
        current = (
            f" preset {progress.current_preset_number}/{progress.total_presets} "
            f"{progress.current_preset_id}"
        )
    stream.write(
        f"{prefix}{current}; "
        f"completed={progress.completed_presets}/{progress.total_presets}\n"
    )


def _write_preparation_failure(manifest: dict[str, object], stream: TextIO) -> None:
    failure = manifest.get("preparation_failure")
    if failure is None:
        return
    if not isinstance(failure, dict):
        raise ProductServiceError("preparation failure presentation is malformed")
    stream.write(
        f"Preparation failed before worker start: {failure['preset_id']} "
        f"[{failure['issue_code']}]\n"
    )
    stream.write(f"Reason: {failure['message']}\n")
    stream.write(
        "No measurements were acquired for this preset; earlier completed results were retained.\n"
    )


def _write_project_document(document: dict[str, object], stream: TextIO) -> None:
    command = document["command"]
    stream.write(f"Command: {command}\n")
    project = document.get("project")
    if isinstance(project, dict):
        presets = project.get("presets")
        if not isinstance(presets, list):
            raise ProductServiceError("project presentation is malformed")
        stream.write(f"Project: {project['project_id']} - {project['name']}\n")
        stream.write(f"Presets: {len(presets)}\n")
        for preset in presets:
            if not isinstance(preset, dict):
                raise ProductServiceError("project preset presentation is malformed")
            configuration = preset.get("configuration")
            if not isinstance(configuration, dict):
                raise ProductServiceError(
                    "project configuration presentation is malformed"
                )
            stream.write(
                f"- {preset['preset_id']}: {configuration['source_mode']} / "
                f"{configuration['job_type']}\n"
            )
    run = document.get("run_manifest")
    if isinstance(run, dict):
        records = run.get("records")
        if not isinstance(records, list):
            raise ProductServiceError("run presentation is malformed")
        stream.write(f"Run: {run['run_id']}\n")
        if "batch_status" in run:
            stream.write(f"Batch status: {run['batch_status']}\n")
        stream.write(f"Records: {len(records)}\n")
        input_artifacts = run.get("input_artifacts")
        if input_artifacts is not None:
            if not isinstance(input_artifacts, list):
                raise ProductServiceError(
                    "run input-artifact presentation is malformed"
                )
            stream.write(f"Archived Replay inputs: {len(input_artifacts)}\n")
            for artifact in input_artifacts:
                if not isinstance(artifact, dict):
                    raise ProductServiceError(
                        "run input-artifact presentation is malformed"
                    )
                stream.write(
                    f"- Input for {artifact['preset_id']}: {artifact['artifact']}; "
                    f"{artifact['size_bytes']} bytes; SHA-256={artifact['sha256']}\n"
                )
        not_started = run.get("not_started_preset_ids", [])
        if not isinstance(not_started, list):
            raise ProductServiceError("run not-started presentation is malformed")
        if not_started:
            stream.write("Not started: " + ", ".join(map(str, not_started)) + "\n")
        _write_preparation_failure(run, stream)
        for record in records:
            if not isinstance(record, dict):
                raise ProductServiceError("run record presentation is malformed")
            outcome = record["engineering_outcome"] or "none"
            stream.write(
                f"- {record['preset_id']}: {record['worker_state']}; "
                f"outcome={outcome}; evidence={record['evidence_source']}\n"
            )
        manifest_path = (
            Path(str(document["run_directory"]))
            / VALIDATION_RUN_MANIFEST_FILENAME
        )
        stream.write(f"Run manifest: {manifest_path}\n")
    history = document.get("runs")
    if isinstance(history, list):
        stream.write(f"Verified history manifests: {len(history)}\n")
        for item in history:
            if not isinstance(item, dict) or not isinstance(
                item.get("manifest"), dict
            ):
                raise ProductServiceError("history presentation is malformed")
            manifest = cast(dict[str, object], item["manifest"])
            summary = manifest.get("summary")
            if not isinstance(summary, dict):
                raise ProductServiceError("history summary is malformed")
            stream.write(
                f"- {manifest['run_id']}: "
                f"status={manifest.get('batch_status', 'UNKNOWN_V1')}; "
                f"{summary['record_count']} records; "
                f"engineering failures={summary['engineering_failures']}; "
                f"operational failures={summary['operational_failures']}"
            )
            if "input_artifact_count" in summary:
                stream.write(
                    f"; archived Replay inputs={summary['input_artifact_count']}"
                )
            stream.write("\n")
            _write_preparation_failure(manifest, stream)
    comparison = document.get("comparison")
    if isinstance(comparison, dict):
        stream.write(
            f"Comparison: {comparison['left_run_id']} -> "
            f"{comparison['right_run_id']}\n"
        )
        stream.write(f"Changed presets: {comparison['changed_entries']}\n")
        entries = comparison.get("entries")
        if not isinstance(entries, list):
            raise ProductServiceError("comparison presentation is malformed")
        for entry in entries:
            if not isinstance(entry, dict):
                raise ProductServiceError("comparison entry is malformed")
            stream.write(
                f"- {entry['preset_id']}: "
                f"{'CHANGED' if entry['changed'] else 'UNCHANGED'}\n"
            )
    stream.write("Serial/device access: NONE\n")
    stream.write("Hardware performance validation: NOT CLAIMED\n")


def _launch_dashboard(dependencies: CliDependencies) -> DashboardSessionResult:
    from .dashboard.app import DashboardSessionResult, launch_dashboard

    launcher = dependencies.dashboard_launcher or launch_dashboard
    session = launcher()
    if not isinstance(session, DashboardSessionResult):
        raise ProductRequestError(
            "dashboard launcher must return a DashboardSessionResult"
        )
    return session


def _dashboard_document(session: DashboardSessionResult) -> dict[str, object]:
    from .dashboard.app import DashboardSessionResult

    if not isinstance(session, DashboardSessionResult):
        raise ProductRequestError("session must be a DashboardSessionResult")
    return {
        "schema_version": CLI_OUTPUT_SCHEMA_VERSION,
        "command": "dashboard",
        "product": PRODUCT_DISPLAY_NAME,
        "software_version": __version__,
        "dashboard_schema_version": session.schema_version,
        "source_mode": session.source_mode.value,
        "profile_identity": session.profile_identity,
        "worker_state": session.worker_state.value,
        "closed_safely": session.closed_safely,
        "hardware_claim": session.hardware_claim,
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


def _issue_document(issue: UserIssue) -> dict[str, object]:
    return {
        "schema_version": CLI_OUTPUT_SCHEMA_VERSION,
        "command": "error",
        "product": PRODUCT_DISPLAY_NAME,
        "software_version": __version__,
        "issue": user_issue_to_dict(issue),
        "hardware_claim": "NO_PERFORMANCE_VALIDATION",
    }


def _operation(value: str) -> ReadOperation:
    return ReadOperation.ANALOG if value == "analog" else ReadOperation.DIGITAL


def _unit(value: str) -> MeasurementUnit:
    return MeasurementUnit(value)


def _execute_workflow(
    arguments: argparse.Namespace,
    dependencies: CliDependencies,
) -> ProductJobExecution:
    source_mode = (
        ProductSourceMode.SIMULATOR
        if arguments.command == "simulate"
        else ProductSourceMode.CSV_REPLAY
    )
    if arguments.workflow == "read":
        job_type = ProductJobType.READ
        values = {
            "primary_channel": arguments.channel,
            "operation": _operation(arguments.operation),
            "unit": _unit(arguments.unit),
            "sample_count": arguments.samples,
        }
    elif arguments.workflow == "dc":
        job_type = ProductJobType.DC_ANALYSIS
        values = {
            "primary_channel": arguments.input_channel,
            "secondary_channel": arguments.output_channel,
            "unit": _unit(arguments.unit),
            "sample_count": arguments.points,
            "low_output_limit": arguments.low_output_limit,
            "high_output_limit": arguments.high_output_limit,
            "target_gain": arguments.target_gain,
            "gain_tolerance": arguments.gain_tolerance,
            "max_abs_offset": arguments.max_abs_offset,
            "min_r_squared": arguments.min_r_squared,
            "max_rmse": arguments.max_rmse,
        }
    elif arguments.workflow == "hysteresis":
        job_type = ProductJobType.HYSTERESIS_ANALYSIS
        values = {
            "primary_channel": arguments.input_channel,
            "state_channel": arguments.state_channel,
            "unit": _unit(arguments.unit),
            "rising_count": arguments.rising_count,
            "falling_count": arguments.falling_count,
            "minimum_high_threshold": arguments.minimum_high_threshold,
            "maximum_high_threshold": arguments.maximum_high_threshold,
            "minimum_low_threshold": arguments.minimum_low_threshold,
            "maximum_low_threshold": arguments.maximum_low_threshold,
            "minimum_width": arguments.minimum_width,
            "maximum_width": arguments.maximum_width,
            "maximum_width_span": arguments.maximum_width_span,
        }
    elif arguments.workflow == "calibration":
        job_type = ProductJobType.CALIBRATION_ANALYSIS
        values = {
            "primary_channel": arguments.observed_channel,
            "secondary_channel": arguments.reference_channel,
            "unit": _unit(arguments.unit),
            "sample_count": arguments.points,
            "coefficient_id": arguments.coefficient_id,
            "coefficient_version": arguments.coefficient_version,
            "max_calibration_rmse": arguments.max_after_rmse,
            "max_calibration_mean_absolute_error": (
                arguments.max_after_mean_absolute_error
            ),
            "max_calibration_absolute_error": arguments.max_after_absolute_error,
            "minimum_calibration_rmse_reduction": (arguments.minimum_rmse_reduction),
        }
    elif arguments.workflow == "frequency":
        job_type = ProductJobType.FREQUENCY_RESPONSE_ANALYSIS
        values = {
            "frequency_channel": arguments.frequency_channel,
            "primary_channel": arguments.input_amplitude_channel,
            "secondary_channel": arguments.output_amplitude_channel,
            "unit": _unit(arguments.unit),
            "frequency_point_count": arguments.points,
            "frequency_minimum_hz": arguments.frequency_minimum_hz,
            "frequency_maximum_hz": arguments.frequency_maximum_hz,
            "frequency_input_amplitude": arguments.input_amplitude,
            "simulated_cutoff_frequency_hz": arguments.simulated_cutoff_hz,
            "target_cutoff_frequency_hz": arguments.target_cutoff_hz,
            "cutoff_relative_tolerance": arguments.cutoff_relative_tolerance,
            "cutoff_drop_db": arguments.cutoff_drop_db,
        }
    elif arguments.workflow == "monitor":
        job_type = ProductJobType.LIVE_MONITOR
        values = {
            "primary_channel": arguments.primary_channel,
            "secondary_channel": arguments.secondary_channel,
            "state_channel": arguments.state_channel,
            "operation": ReadOperation.ANALOG,
            "unit": _unit(arguments.unit),
            "sample_count": arguments.cycles,
            "monitor_sample_interval_seconds": arguments.sample_interval,
            "monitor_time_window_seconds": arguments.time_window,
            "monitor_max_buffer_points": arguments.max_buffer_points,
            "monitor_include_secondary": arguments.include_secondary,
            "monitor_include_state": arguments.include_state,
        }
    else:
        raise CliUsageError(f"{arguments.command} requires a workflow")
    if source_mode is ProductSourceMode.CSV_REPLAY:
        values.update(
            {
                "replay_path": arguments.input,
                "replay_minimum": arguments.minimum,
                "replay_maximum": arguments.maximum,
            }
        )
    config = ProductWorkflowConfiguration(
        source_mode,
        job_type,
        arguments.profile,
        arguments.profile_version,
        **values,
    )
    prepared = prepare_product_job(
        config,
        dependencies.job_id_factory(),
        backend_factory=dependencies.serial_backend_factory,
        prevalidate_replay=False,
    )
    join_timeout_s = 5.0
    if job_type is ProductJobType.LIVE_MONITOR:
        join_timeout_s = min(
            60.0,
            max(5.0, config.live_monitor_runtime_bound_seconds() + 5.0),
        )
    return execute_product_job(
        prepared.request,
        prepared.service_factory,
        prepared.output_slot,
        join_timeout_s=join_timeout_s,
    )


def _execute_observe(
    arguments: argparse.Namespace,
    dependencies: CliDependencies,
) -> ProductJobExecution:
    if not arguments.confirm_read_only:
        raise CliUsageError("observe requires --confirm-read-only")
    serial_config = SerialSourceConfig(
        port_id=arguments.port,
        baud_rate=arguments.baud_rate,
        read_timeout_seconds=arguments.read_timeout,
        max_polls_per_operation=arguments.max_polls,
        max_buffered_measurements=max(128, arguments.max_records * 8),
        evidence_source=EvidenceSource.HOST_TEST,
        expected_device_id=arguments.expected_device_id,
        afe_adc_channel_aliases=tuple(arguments.afe_adc_alias or ()),
    )
    config = ProductWorkflowConfiguration(
        ProductSourceMode.SERIAL_READ_ONLY,
        ProductJobType.READ,
        arguments.profile,
        arguments.profile_version,
        primary_channel=arguments.channel,
        operation=_operation(arguments.operation),
        unit=_unit(arguments.unit),
        sample_count=arguments.max_records,
        serial_config=serial_config,
        confirm_read_only=True,
    )
    prepared = prepare_product_job(
        config,
        dependencies.job_id_factory(),
        backend_factory=dependencies.serial_backend_factory,
    )
    return execute_product_job(
        prepared.request, prepared.service_factory, prepared.output_slot
    )


def _execute_serial_monitor(
    arguments: argparse.Namespace,
    dependencies: CliDependencies,
) -> ProductJobExecution:
    if arguments.serial_workflow != "monitor":
        raise CliUsageError("serial requires a WORKFLOW")
    if not arguments.confirm_read_only:
        raise CliUsageError("serial monitor requires --confirm-read-only")
    enabled_channel_count = (
        1 + int(arguments.include_secondary) + int(arguments.include_state)
    )
    serial_config = SerialSourceConfig(
        port_id=arguments.port,
        baud_rate=arguments.baud_rate,
        read_timeout_seconds=arguments.read_timeout,
        max_polls_per_operation=arguments.max_polls,
        max_buffered_measurements=min(
            MAX_CLI_SAMPLES,
            max(128, arguments.cycles * enabled_channel_count * 8),
        ),
        evidence_source=EvidenceSource.HOST_TEST,
        expected_device_id=arguments.expected_device_id,
        afe_adc_channel_aliases=tuple(arguments.afe_adc_alias or ()),
    )
    config = ProductWorkflowConfiguration(
        ProductSourceMode.SERIAL_READ_ONLY,
        ProductJobType.LIVE_MONITOR,
        arguments.profile,
        arguments.profile_version,
        primary_channel=arguments.primary_channel,
        secondary_channel=arguments.secondary_channel,
        state_channel=arguments.state_channel,
        operation=ReadOperation.ANALOG,
        unit=_unit(arguments.unit),
        sample_count=arguments.cycles,
        serial_config=serial_config,
        confirm_read_only=True,
        monitor_sample_interval_seconds=arguments.sample_interval,
        monitor_time_window_seconds=arguments.time_window,
        monitor_max_buffer_points=arguments.max_buffer_points,
        monitor_include_secondary=arguments.include_secondary,
        monitor_include_state=arguments.include_state,
    )
    prepared = prepare_product_job(
        config,
        dependencies.job_id_factory(),
        backend_factory=dependencies.serial_backend_factory,
    )
    join_timeout_s = min(
        60.0,
        max(5.0, config.live_monitor_runtime_bound_seconds() + 5.0),
    )
    return execute_product_job(
        prepared.request,
        prepared.service_factory,
        prepared.output_slot,
        join_timeout_s=join_timeout_s,
    )


def _measurement_document(measurement: object) -> dict[str, object]:
    if not isinstance(measurement, Measurement):
        raise CliUsageError("service returned an invalid measurement")
    return {
        "record_id": measurement.record_id,
        "raw_record_id": measurement.raw_record_id,
        "timestamp": measurement.timestamp.isoformat(),
        "channel": measurement.channel,
        "value": measurement.value,
        "unit": measurement.unit.value,
        "status": measurement.status.value,
        "source": measurement.source.value,
        "quality_flags": sorted(flag.value for flag in measurement.quality_flags),
    }


def _execution_document(
    command: str,
    execution: ProductJobExecution,
    artifact: dict[str, object] | None,
    coefficient_artifact: dict[str, object] | None = None,
) -> dict[str, object]:
    request = execution.request
    result = execution.result
    output = execution.output
    return {
        "schema_version": CLI_OUTPUT_SCHEMA_VERSION,
        "command": command,
        "product": PRODUCT_DISPLAY_NAME,
        "software_version": __version__,
        "request": {
            "job_id": request.job_id,
            "source_mode": request.source_mode.value,
            "job_type": request.job_type.value,
            "profile_name": request.profile_name,
            "profile_version": request.profile_version,
            "read_only": not request.allow_output,
        },
        "worker": {
            "state": execution.worker_state.value,
            "interrupted": execution.interrupted,
            "dropped_event_count": execution.dropped_event_count,
            "events": [
                {
                    "index": event.index,
                    "state": event.state.value,
                    "message": event.message,
                    "completed": event.completed,
                    "total": event.total,
                }
                for event in execution.events
            ],
        },
        "result": None
        if result is None
        else {
            "status": result.status.value,
            "evidence_source": result.evidence_source.value,
            "test_run_outcome": None
            if result.test_run_outcome is None
            else result.test_run_outcome.value,
            "engineering_conclusion": result.is_engineering_conclusion,
            "limitations": list(result.limitations),
        },
        "issue": None
        if execution.issue is None
        else user_issue_to_dict(execution.issue),
        "read": None
        if output is None
        else {
            "status": output.read_result.status.value,
            "device_id": output.read_result.capabilities.device_id,
            "profile_name": output.read_result.capabilities.profile_name,
            "profile_version": output.read_result.capabilities.profile_version,
            "readable_analog_channels": list(
                output.read_result.capabilities.adc_channels
            ),
            "readable_digital_channels": list(
                output.read_result.capabilities.digital_input_channels
            ),
            "evidence_source": output.read_result.evidence_source.value,
            "missing_requirements": list(output.read_result.missing_requirements),
            "measurements": [
                _measurement_document(measurement)
                for measurement in output.read_result.measurements
            ],
        },
        "result_export": None
        if output is None or output.result_export is None
        else result_export_to_dict(output.result_export),
        "calibration_coefficients": None
        if output is None or output.calibration_coefficients is None
        else calibration_coefficients_to_dict(output.calibration_coefficients),
        "live_monitor": None
        if output is None or output.live_monitor is None
        else {
            "schema_version": output.live_monitor.schema_version,
            "total_points": output.live_monitor.total_points,
            "retained_points": len(output.live_monitor.points),
            "visible_points": len(output.live_monitor.visible_points),
            "evicted_points": output.live_monitor.evicted_points,
            "paused": output.live_monitor.paused,
            "pause_count": output.live_monitor.pause_count,
            "time_window_seconds": output.live_monitor.time_window_seconds,
            "valid_points": output.live_monitor.valid_points,
            "suspect_points": output.live_monitor.suspect_points,
            "invalid_points": output.live_monitor.invalid_points,
            "points": [
                {
                    "index": point.index,
                    "cycle_index": point.cycle_index,
                    "elapsed_seconds": point.elapsed_seconds,
                    "measurement": _measurement_document(point.measurement),
                }
                for point in output.live_monitor.points
            ],
        },
        "artifact": artifact,
        "coefficient_artifact": coefficient_artifact,
        "hardware_claim": "NO_PERFORMANCE_VALIDATION",
    }


def _write_execution(execution: ProductJobExecution, stream: TextIO) -> None:
    result = execution.result
    stream.write(f"Job: {execution.request.job_id}\n")
    stream.write(f"Worker state: {execution.worker_state.value}\n")
    if result is not None:
        stream.write(f"Product status: {result.status.value}\n")
        stream.write(f"Evidence source: {result.evidence_source.value}\n")
        outcome = (
            "none" if result.test_run_outcome is None else result.test_run_outcome.value
        )
        stream.write(f"Engineering outcome: {outcome}\n")
        stream.writelines(
            f"Limitation: {limitation}\n" for limitation in result.limitations
        )
    if execution.output is not None:
        read = execution.output.read_result
        stream.write(f"Read status: {read.status.value}\n")
        stream.write(
            "Capability identity: "
            f"{read.capabilities.device_id} "
            f"({read.capabilities.profile_name}/{read.capabilities.profile_version})\n"
        )
        stream.write(f"Measurements: {len(read.measurements)}\n")
        stream.writelines(
            f"Missing: {missing}\n" for missing in read.missing_requirements
        )
        coefficients = execution.output.calibration_coefficients
        if coefficients is not None:
            stream.write(
                "Calibration coefficients: "
                f"{coefficients.coefficient_id}/{coefficients.coefficient_version}\n"
            )
            stream.write(
                f"Calibration mapping: reference = {coefficients.scale:g} * "
                f"observed + {coefficients.offset:g} {coefficients.unit.value}\n"
            )
        live_monitor = execution.output.live_monitor
        if live_monitor is not None:
            stream.write(
                "Live monitor: "
                f"{live_monitor.total_points} acquired; "
                f"{len(live_monitor.points)} retained; "
                f"{live_monitor.evicted_points} oldest points evicted by the "
                "memory bound.\n"
            )
            stream.write(
                f"Live view window: {live_monitor.time_window_seconds:g} s; "
                f"pause actions: {live_monitor.pause_count}.\n"
            )
            stream.write(
                "Measurement status totals: "
                f"VALID={live_monitor.valid_points}; "
                f"SUSPECT={live_monitor.suspect_points}; "
                f"INVALID={live_monitor.invalid_points}.\n"
            )
        if (
            execution.request.job_type is ProductJobType.FREQUENCY_RESPONSE_ANALYSIS
            and execution.output.result_export is not None
        ):
            metrics = {
                value.name: value for value in execution.output.result_export.metrics
            }
            cutoff = metrics.get("cutoff_frequency")
            reference = metrics.get("reference_gain")
            if (
                cutoff is not None
                and isinstance(cutoff.value, (int, float))
                and not isinstance(cutoff.value, bool)
            ):
                stream.write(f"Estimated cutoff: {cutoff.value:g} {cutoff.unit}\n")
            if (
                reference is not None
                and isinstance(reference.value, (int, float))
                and not isinstance(reference.value, bool)
            ):
                stream.write(f"Reference gain: {reference.value:g} {reference.unit}\n")
    stream.write("Hardware performance validation: NOT CLAIMED\n")


def _write_artifact(
    arguments: argparse.Namespace,
    execution: ProductJobExecution,
) -> dict[str, object] | None:
    output_path = getattr(arguments, "output", None)
    if output_path is None:
        return None
    if execution.worker_state is not ProductWorkerState.SUCCEEDED:
        return None
    if execution.output is None or execution.output.result_export is None:
        if (
            execution.result is not None
            and execution.result.status is not ProductResultStatus.COMPLETED
        ):
            return None
        raise ProductServiceError(
            "a finalized analysis job did not publish its result export"
        )
    bundle = execution.output.result_export
    if arguments.output_format == "json":
        written = write_result_export_json(output_path, bundle)
    else:
        written = write_result_export_csv(output_path, bundle)
    payload = written.read_bytes()
    return {
        "path": str(written.resolve()),
        "format": arguments.output_format,
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "overwrite": False,
    }


def _preflight_artifact_paths(arguments: argparse.Namespace) -> None:
    paths = tuple(
        value
        for value in (
            getattr(arguments, "output", None),
            getattr(arguments, "coefficients_output", None),
        )
        if value is not None
    )
    if len(paths) == 2 and paths[0].resolve() == paths[1].resolve():
        raise CliUsageError(
            "--output and --coefficients-output must identify different files"
        )
    for path in paths:
        if path.exists():
            raise ResultExportExistsError("destination already exists")
        if not path.parent.exists() or not path.parent.is_dir():
            raise ResultExportPathError("destination parent directory must exist")


def _write_coefficient_artifact(
    arguments: argparse.Namespace,
    execution: ProductJobExecution,
) -> dict[str, object] | None:
    output_path = getattr(arguments, "coefficients_output", None)
    if output_path is None:
        return None
    if execution.worker_state is not ProductWorkerState.SUCCEEDED:
        return None
    output = execution.output
    if output is None or output.calibration_coefficients is None:
        if (
            execution.result is not None
            and execution.result.status is not ProductResultStatus.COMPLETED
        ):
            return None
        raise ProductServiceError(
            "a finalized calibration job did not publish coefficients"
        )
    written = write_calibration_coefficients_json(
        output_path, output.calibration_coefficients
    )
    payload = written.read_bytes()
    return {
        "path": str(written.resolve()),
        "format": "json",
        "schema_version": CALIBRATION_COEFFICIENTS_SCHEMA_VERSION,
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "overwrite": False,
    }


def _load_report_input(arguments: argparse.Namespace) -> ResultExportBundle:
    selected = arguments.input_format
    if selected == "auto":
        suffix = arguments.input.suffix.lower()
        if suffix == ".json":
            selected = "json"
        elif suffix == ".csv":
            selected = "csv"
        else:
            raise CliUsageError(
                "report --input-format auto requires a .json or .csv input suffix"
            )
    if selected == "json":
        return load_result_export_json(arguments.input)
    if selected == "csv":
        return load_result_export_csv(arguments.input)
    raise CliUsageError("report input format is unsupported")


def _report_document(
    view: HumanReportView,
    publication: HumanReportPublication,
) -> dict[str, object]:
    return {
        "schema_version": CLI_OUTPUT_SCHEMA_VERSION,
        "command": "report",
        "product": PRODUCT_DISPLAY_NAME,
        "software_version": __version__,
        "report_schema_version": view.schema_version,
        "canonical_result_sha256": view.canonical_result_sha256,
        "outcome": view.outcome.value,
        "evidence_source": view.evidence_source.value,
        "hardware_claim": REPORT_HARDWARE_CLAIM,
        "output_directory": str(publication.output_directory),
        "artifacts": [
            {
                "name": artifact.name,
                "media_type": artifact.media_type,
                "size_bytes": artifact.size_bytes,
                "sha256": artifact.sha256,
            }
            for artifact in publication.artifacts
        ],
    }


def _write_report_publication(
    view: HumanReportView,
    publication: HumanReportPublication,
    stream: TextIO,
) -> None:
    stream.write(f"Report outcome: {view.outcome.value}\n")
    stream.write(f"Evidence source: {view.evidence_source.value}\n")
    stream.write(f"Canonical result SHA-256: {view.canonical_result_sha256}\n")
    stream.write(f"Report directory: {publication.output_directory}\n")
    stream.writelines(
        f"Artifact: {artifact.name} | {artifact.size_bytes} bytes | SHA-256 {artifact.sha256}\n"
        for artifact in publication.artifacts
    )
    stream.write("New hardware performance validation: NOT CLAIMED\n")


def _demo_document(publication: PortfolioDemoPublication) -> dict[str, object]:
    return {
        "schema_version": CLI_OUTPUT_SCHEMA_VERSION,
        "command": "demo",
        "product": PRODUCT_DISPLAY_NAME,
        "software_version": __version__,
        "demo_schema_version": publication.schema_version,
        "outcome": publication.outcome.value,
        "evidence_source": publication.evidence_source.value,
        "hardware_claim": REPORT_HARDWARE_CLAIM,
        "output_directory": str(publication.output_directory),
        "canonical_result_sha256": publication.canonical_result_sha256,
        "artifacts": [
            {
                "relative_path": artifact.relative_path,
                "media_type": artifact.media_type,
                "size_bytes": artifact.size_bytes,
                "sha256": artifact.sha256,
            }
            for artifact in publication.artifacts
        ],
    }


def _write_demo_publication(
    publication: PortfolioDemoPublication,
    stream: TextIO,
) -> None:
    stream.write(f"Demo outcome: {publication.outcome.value}\n")
    stream.write(f"Evidence source: {publication.evidence_source.value}\n")
    stream.write(f"Canonical result SHA-256: {publication.canonical_result_sha256}\n")
    stream.write(f"Demo directory: {publication.output_directory}\n")
    stream.writelines(
        f"Artifact: {artifact.relative_path} | {artifact.size_bytes} bytes | SHA-256 {artifact.sha256}\n"
        for artifact in publication.artifacts
    )
    stream.write("Serial ports opened: 0\n")
    stream.write("Network access: NONE\n")
    stream.write("New hardware performance validation: NOT CLAIMED\n")


def _report_exit_code(outcome: TestRunOutcome) -> int:
    return {
        TestRunOutcome.PASS: 0,
        TestRunOutcome.FAIL: CLI_ENGINEERING_FAIL_EXIT_CODE,
        TestRunOutcome.INCOMPLETE: CLI_INCOMPLETE_EXIT_CODE,
        TestRunOutcome.UNSUPPORTED: CLI_UNSUPPORTED_EXIT_CODE,
        TestRunOutcome.ABORTED: CLI_CANCELLED_EXIT_CODE,
        TestRunOutcome.ERROR: CLI_OPERATION_ERROR_EXIT_CODE,
    }[outcome]


def _execution_exit_code(execution: ProductJobExecution) -> int:
    if execution.interrupted or execution.worker_state is ProductWorkerState.CANCELLED:
        return CLI_CANCELLED_EXIT_CODE
    if execution.worker_state is ProductWorkerState.FAILED:
        return CLI_OPERATION_ERROR_EXIT_CODE
    result = execution.result
    if result is None:
        return CLI_OPERATION_ERROR_EXIT_CODE
    if result.status is ProductResultStatus.COMPLETED:
        if (
            result.test_run_outcome is not None
            and result.test_run_outcome.value == "FAIL"
        ):
            return CLI_ENGINEERING_FAIL_EXIT_CODE
        return 0
    if result.status is ProductResultStatus.INCOMPLETE:
        return CLI_INCOMPLETE_EXIT_CODE
    if result.status is ProductResultStatus.UNSUPPORTED:
        return CLI_UNSUPPORTED_EXIT_CODE
    if result.status is ProductResultStatus.CANCELLED:
        return CLI_CANCELLED_EXIT_CODE
    return CLI_OPERATION_ERROR_EXIT_CODE


def _issue_exit_code(issue: UserIssue) -> int:
    if issue.code is UserIssueCode.INVALID_REQUEST:
        return CLI_USAGE_EXIT_CODE
    if issue.code in {
        UserIssueCode.CAPABILITY_UNAVAILABLE,
        UserIssueCode.OPTIONAL_DEPENDENCY,
    }:
        return CLI_UNSUPPORTED_EXIT_CODE
    return CLI_OPERATION_ERROR_EXIT_CODE


def _as_json_requested(arguments: object) -> bool:
    return bool(getattr(arguments, "as_json", False))


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    dependencies: CliDependencies | None = None,
) -> int:
    """Run the stable CLI and return a documented process exit code."""

    output = stdout or sys.stdout
    errors = stderr or sys.stderr
    injected = dependencies or CliDependencies()
    parser = build_parser()
    arguments: argparse.Namespace | None = None
    try:
        try:
            arguments = parser.parse_args(argv)
        except _ParserExit as exit_request:
            if exit_request.message:
                output.write(exit_request.message)
            return exit_request.status

        if arguments.command is None:
            parser.print_help(file=output)
            return 0
        if arguments.command == "version":
            if arguments.as_json:
                _write_json(_version_document(), output)
            else:
                output.write(f"{PRODUCT_DISPLAY_NAME} {__version__}\n")
            return 0
        if arguments.command == "import-csv":
            document = execute_import_csv(arguments, schema_version=CLI_OUTPUT_SCHEMA_VERSION)
            if arguments.as_json:
                _write_json(document, output)
            else:
                write_import_csv_document(document, output)
            return 0
        if arguments.command == "profiles":
            if arguments.as_json:
                _write_json(_profile_document(), output)
            else:
                _write_profiles(output)
            return 0
        if arguments.command == "ports":
            ports = discover_serial_ports(injected.serial_backend_factory)
            document = {
                "schema_version": CLI_OUTPUT_SCHEMA_VERSION,
                "command": "ports",
                "ports": [
                    {"port_id": port.port_id, "description": port.description}
                    for port in ports
                ],
                "opened_ports": 0,
            }
            if arguments.as_json:
                _write_json(document, output)
            else:
                output.write("Discovered logical ports (none were opened):\n")
                for port in ports:
                    description = f" - {port.description}" if port.description else ""
                    output.write(f"- {port.port_id}{description}\n")
                if not ports:
                    output.write("- none\n")
            return 0
        if arguments.command == "coefficients":
            if arguments.coefficient_command != "inspect":
                raise CliUsageError("coefficients requires an ACTION")
            document = _coefficient_document(arguments.input)
            if arguments.as_json:
                _write_json(document, output)
            else:
                _write_coefficient_inspection(document, output)
            return 0
        if arguments.command == "project":
            document, exit_code = _execute_project_action(
                arguments, progress_stream=errors
            )
            if arguments.as_json:
                _write_json(document, output)
            else:
                _write_project_document(document, output)
            return exit_code
        if arguments.command == "report":
            report_view = build_human_report_view(_load_report_input(arguments))
            publication = publish_human_report(arguments.output, report_view)
            if arguments.as_json:
                _write_json(_report_document(report_view, publication), output)
            else:
                _write_report_publication(report_view, publication, output)
            return _report_exit_code(report_view.outcome)
        if arguments.command == "demo":
            demo = publish_portfolio_demo(arguments.output)
            if arguments.as_json:
                _write_json(_demo_document(demo), output)
            else:
                _write_demo_publication(demo, output)
            return _report_exit_code(demo.outcome)
        if arguments.command == "dashboard":
            session = _launch_dashboard(injected)
            if arguments.as_json:
                _write_json(_dashboard_document(session), output)
            else:
                output.write("Dashboard closed safely.\n")
                output.write(f"Source: {session.source_mode.value}\n")
                output.write(f"Profile: {session.profile_identity}\n")
                output.write(f"Worker state: {session.worker_state.value}\n")
                output.write(f"Hardware claim: {session.hardware_claim}\n")
            return 0
        if arguments.command in {"simulate", "replay"}:
            _preflight_artifact_paths(arguments)
            execution = _execute_workflow(arguments, injected)
        elif arguments.command == "serial":
            execution = _execute_serial_monitor(arguments, injected)
        elif arguments.command == "observe":
            execution = _execute_observe(arguments, injected)
        else:
            raise CliUsageError("argparse returned an unknown command")

        artifact = _write_artifact(arguments, execution)
        coefficient_artifact = _write_coefficient_artifact(arguments, execution)
        if arguments.as_json:
            _write_json(
                _execution_document(
                    arguments.command,
                    execution,
                    artifact,
                    coefficient_artifact,
                ),
                output,
            )
        else:
            _write_execution(execution, output)
            if artifact is not None:
                output.write(f"Artifact: {artifact['path']}\n")
                output.write(f"SHA-256: {artifact['sha256']}\n")
            if coefficient_artifact is not None:
                output.write(f"Coefficient artifact: {coefficient_artifact['path']}\n")
                output.write(f"Coefficient SHA-256: {coefficient_artifact['sha256']}\n")
            if execution.issue is not None:
                _write_issue(execution.issue, errors)
        return _execution_exit_code(execution)
    except (ProductAppError, AnalogValidationError) as error:
        issue = issue_from_exception(error)
        if _as_json_requested(arguments):
            _write_json(_issue_document(issue), errors)
        else:
            _write_issue(issue, errors)
        return _issue_exit_code(issue)
    except BaseException as error:  # noqa: BLE001 - process boundary
        event_id = injected.event_id_factory()
        errors.write(
            f"ERROR [INTERNAL_ERROR] Unexpected software failure; event ID: {event_id}\n"
        )
        errors.write("No hardware validation result was produced.\n")
        if arguments is not None and arguments.debug:
            traceback.print_exception(error, file=errors)
        return CLI_INTERNAL_ERROR_EXIT_CODE


__all__ = [
    "CLI_CANCELLED_EXIT_CODE",
    "CLI_ENGINEERING_FAIL_EXIT_CODE",
    "CLI_INCOMPLETE_EXIT_CODE",
    "CLI_INTERNAL_ERROR_EXIT_CODE",
    "CLI_OPERATION_ERROR_EXIT_CODE",
    "CLI_OUTPUT_SCHEMA_VERSION",
    "CLI_UNSUPPORTED_EXIT_CODE",
    "CLI_USAGE_EXIT_CODE",
    "PRODUCT_DISPLAY_NAME",
    "CliDependencies",
    "DashboardLauncher",
    "build_parser",
    "main",
]
