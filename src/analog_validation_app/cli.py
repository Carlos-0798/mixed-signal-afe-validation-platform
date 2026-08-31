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
from typing import TYPE_CHECKING, NoReturn, TextIO
from uuid import uuid4

from analog_validation import (
    AnalogValidationError,
    ChannelReadRequest,
    CsvReplayAdapterConfig,
    EvidenceSource,
    Measurement,
    MeasurementUnit,
    ReadOperation,
    ReadWorkflowRequest,
    ReplayChannelConfig,
    ReplayChannelKind,
    SafeRange,
    SimulatorConfig,
    TestRunOutcome,
    __version__,
)
from analog_validation.analysis import (
    DCSweepAcceptanceCriteria,
    DCSweepAnalysisConfig,
    HysteresisAcceptanceCriteria,
    HysteresisAnalysisConfig,
)
from analog_validation.exports import (
    ResultExportBundle,
    load_result_export_csv,
    load_result_export_json,
    result_export_to_dict,
    write_result_export_csv,
    write_result_export_json,
)

from .catalog import PRODUCT_CATALOG_SCHEMA_VERSION, list_product_profiles
from .errors import (
    CliUsageError,
    ProductAppError,
    ProductFeatureUnavailableError,
    ProductRequestError,
    ProductServiceError,
)
from .factories import (
    AdapterFactory,
    SerialBackendFactory,
    SerialSourceConfig,
    default_serial_backend_factory,
    discover_serial_ports,
    make_csv_replay_adapter_factory,
    make_serial_adapter_factory,
    make_simulator_adapter_factory,
)
from .issues import UserIssue, UserIssueCode, issue_from_exception, user_issue_to_dict
from .models import (
    ProductJobRequest,
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
from .reporting import HumanReportPublication, publish_human_report
from .services import (
    ProductJobExecution,
    ProductServiceOutputSlot,
    execute_product_job,
    make_dc_sweep_service_factory,
    make_hysteresis_service_factory,
    make_read_service_factory,
)

if TYPE_CHECKING:
    from .dashboard.app import DashboardSessionResult

CLI_OUTPUT_SCHEMA_VERSION = "product-cli-output.v1"
CLI_USAGE_EXIT_CODE = 2
CLI_ENGINEERING_FAIL_EXIT_CODE = 1
CLI_INCOMPLETE_EXIT_CODE = 3
CLI_UNSUPPORTED_EXIT_CODE = 4
CLI_OPERATION_ERROR_EXIT_CODE = 5
CLI_INTERNAL_ERROR_EXIT_CODE = 70
CLI_CANCELLED_EXIT_CODE = 130
MAX_CLI_SAMPLES = 10_000
PRODUCT_DISPLAY_NAME = "Analog Validation Studio"

SIMULATOR_LIMITATIONS = (
    "Synthetic software observations only; no physical hardware was measured.",
    "A software PASS or FAIL does not validate an assembled analog front end.",
)
REPLAY_LIMITATIONS = (
    "Results describe a local CSV replay under the declared channel mapping.",
    "Replay analysis does not prove current hardware wiring or performance.",
)
SERIAL_LIMITATIONS = (
    "Receive-only host integration; no command or serial write was issued.",
    "Received records alone do not prove calibrated AFE performance or safe wiring.",
)

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

    _add_source_workflows(
        commands, "simulate", "run deterministic software-only workflows"
    )
    _add_source_workflows(commands, "replay", "analyze an explicit local CSV replay")

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
    _add_machine_view(observe_parser)

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

    for name, help_text in (
        ("demo", "generate the reproducible portfolio demo (Step 7)"),
        ("dashboard", "launch the local desktop dashboard (Step 5)"),
    ):
        future = commands.add_parser(name, help=help_text)
        _add_machine_view(future)
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
    }


def _operation(value: str) -> ReadOperation:
    return ReadOperation.ANALOG if value == "analog" else ReadOperation.DIGITAL


def _unit(value: str) -> MeasurementUnit:
    return MeasurementUnit(value)


def _profile_request(
    arguments: argparse.Namespace,
    dependencies: CliDependencies,
    source_mode: ProductSourceMode,
    job_type: ProductJobType,
) -> ProductJobRequest:
    return ProductJobRequest(
        dependencies.job_id_factory(),
        source_mode,
        job_type,
        arguments.profile,
        arguments.profile_version,
    )


def _read_workflow(arguments: argparse.Namespace) -> ReadWorkflowRequest:
    sample_count = (
        arguments.samples if hasattr(arguments, "samples") else arguments.max_records
    )
    return ReadWorkflowRequest(
        (
            ChannelReadRequest(
                arguments.channel,
                _operation(arguments.operation),
                _unit(arguments.unit),
                sample_count,
            ),
        ),
        request_id="product-read",
    )


def _analog_channel(
    name: str,
    unit: MeasurementUnit,
    minimum: float,
    maximum: float,
) -> ReplayChannelConfig:
    return ReplayChannelConfig(
        name,
        ReplayChannelKind.ANALOG,
        unit,
        SafeRange(minimum, maximum, unit),
    )


def _simulator_factory(
    arguments: argparse.Namespace,
) -> tuple[AdapterFactory, SimulatorConfig]:
    config = SimulatorConfig(
        profile_name=arguments.profile,
        profile_version=arguments.profile_version,
    )
    return make_simulator_adapter_factory(config), config


def _replay_read_factory(arguments: argparse.Namespace) -> AdapterFactory:
    unit = _unit(arguments.unit)
    kind = (
        ReplayChannelKind.ANALOG
        if arguments.operation == "analog"
        else ReplayChannelKind.DIGITAL
    )
    channel = (
        _analog_channel(arguments.channel, unit, arguments.minimum, arguments.maximum)
        if kind is ReplayChannelKind.ANALOG
        else ReplayChannelConfig(
            arguments.channel,
            ReplayChannelKind.DIGITAL,
            MeasurementUnit.BOOLEAN,
        )
    )
    config = CsvReplayAdapterConfig(
        (channel,),
        profile_name=arguments.profile,
        profile_version=arguments.profile_version,
    )
    return make_csv_replay_adapter_factory(arguments.input, config)


def _dc_parts(
    arguments: argparse.Namespace,
) -> tuple[ReadWorkflowRequest, DCSweepAnalysisConfig, DCSweepAcceptanceCriteria]:
    unit = _unit(arguments.unit)
    workflow = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                arguments.input_channel, ReadOperation.ANALOG, unit, arguments.points
            ),
            ChannelReadRequest(
                arguments.output_channel, ReadOperation.ANALOG, unit, arguments.points
            ),
        ),
        request_id="product-dc-sweep",
    )
    analysis = DCSweepAnalysisConfig(
        arguments.input_channel,
        arguments.output_channel,
        arguments.low_output_limit,
        arguments.high_output_limit,
        unit,
    )
    criteria = DCSweepAcceptanceCriteria(
        "product-dc-default",
        "1",
        arguments.target_gain,
        arguments.gain_tolerance,
        arguments.max_abs_offset,
        arguments.min_r_squared,
        arguments.max_rmse,
        3,
        unit,
    )
    return workflow, analysis, criteria


def _hysteresis_parts(
    arguments: argparse.Namespace,
) -> tuple[
    ReadWorkflowRequest,
    HysteresisAnalysisConfig,
    HysteresisAcceptanceCriteria,
]:
    unit = _unit(arguments.unit)
    count = arguments.rising_count + arguments.falling_count
    if count > MAX_CLI_SAMPLES:
        raise CliUsageError(
            f"rising-count plus falling-count cannot exceed {MAX_CLI_SAMPLES}"
        )
    workflow = ReadWorkflowRequest(
        (
            ChannelReadRequest(
                arguments.input_channel, ReadOperation.ANALOG, unit, count
            ),
            ChannelReadRequest(
                arguments.state_channel,
                ReadOperation.DIGITAL,
                MeasurementUnit.BOOLEAN,
                count,
            ),
        ),
        request_id="product-hysteresis",
    )
    analysis = HysteresisAnalysisConfig(
        arguments.input_channel, arguments.state_channel, unit
    )
    criteria = HysteresisAcceptanceCriteria(
        "product-hysteresis-default",
        "1",
        arguments.minimum_high_threshold,
        arguments.maximum_high_threshold,
        arguments.minimum_low_threshold,
        arguments.maximum_low_threshold,
        arguments.minimum_width,
        arguments.maximum_width,
        arguments.maximum_width_span,
        1,
        unit,
    )
    return workflow, analysis, criteria


def _replay_analysis_factory(
    arguments: argparse.Namespace,
    *,
    hysteresis: bool,
) -> AdapterFactory:
    unit = _unit(arguments.unit)
    channels = [
        _analog_channel(
            arguments.input_channel, unit, arguments.minimum, arguments.maximum
        )
    ]
    if hysteresis:
        channels.append(
            ReplayChannelConfig(
                arguments.state_channel,
                ReplayChannelKind.DIGITAL,
                MeasurementUnit.BOOLEAN,
            )
        )
    else:
        channels.append(
            _analog_channel(
                arguments.output_channel, unit, arguments.minimum, arguments.maximum
            )
        )
    config = CsvReplayAdapterConfig(
        tuple(channels),
        profile_name=arguments.profile,
        profile_version=arguments.profile_version,
    )
    return make_csv_replay_adapter_factory(arguments.input, config)


def _execute_workflow(
    arguments: argparse.Namespace,
    dependencies: CliDependencies,
) -> ProductJobExecution:
    source_mode = (
        ProductSourceMode.SIMULATOR
        if arguments.command == "simulate"
        else ProductSourceMode.CSV_REPLAY
    )
    limitations = (
        SIMULATOR_LIMITATIONS
        if source_mode is ProductSourceMode.SIMULATOR
        else REPLAY_LIMITATIONS
    )
    slot = ProductServiceOutputSlot()
    if arguments.workflow == "read":
        request = _profile_request(
            arguments, dependencies, source_mode, ProductJobType.READ
        )
        if source_mode is ProductSourceMode.SIMULATOR:
            adapter_factory, _ = _simulator_factory(arguments)
        else:
            adapter_factory = _replay_read_factory(arguments)
        service_factory = make_read_service_factory(
            adapter_factory, _read_workflow(arguments), limitations, slot
        )
    elif arguments.workflow == "dc":
        request = _profile_request(
            arguments, dependencies, source_mode, ProductJobType.DC_ANALYSIS
        )
        if source_mode is ProductSourceMode.SIMULATOR:
            adapter_factory, _ = _simulator_factory(arguments)
        else:
            adapter_factory = _replay_analysis_factory(arguments, hysteresis=False)
        dc_workflow, dc_analysis, dc_criteria = _dc_parts(arguments)
        service_factory = make_dc_sweep_service_factory(
            adapter_factory,
            dc_workflow,
            dc_analysis,
            dc_criteria,
            limitations,
            slot,
        )
    elif arguments.workflow == "hysteresis":
        request = _profile_request(
            arguments,
            dependencies,
            source_mode,
            ProductJobType.HYSTERESIS_ANALYSIS,
        )
        if source_mode is ProductSourceMode.SIMULATOR:
            adapter_factory, _ = _simulator_factory(arguments)
        else:
            adapter_factory = _replay_analysis_factory(arguments, hysteresis=True)
        hysteresis_workflow, hysteresis_analysis, hysteresis_criteria = (
            _hysteresis_parts(arguments)
        )
        service_factory = make_hysteresis_service_factory(
            adapter_factory,
            hysteresis_workflow,
            hysteresis_analysis,
            hysteresis_criteria,
            arguments.rising_count,
            arguments.falling_count,
            limitations,
            slot,
        )
    else:
        raise CliUsageError(f"{arguments.command} requires a workflow")
    return execute_product_job(request, service_factory, slot)


def _execute_observe(
    arguments: argparse.Namespace,
    dependencies: CliDependencies,
) -> ProductJobExecution:
    if not arguments.confirm_read_only:
        raise CliUsageError("observe requires --confirm-read-only")
    request = _profile_request(
        arguments,
        dependencies,
        ProductSourceMode.SERIAL_READ_ONLY,
        ProductJobType.READ,
    )
    slot = ProductServiceOutputSlot()
    config = SerialSourceConfig(
        arguments.port,
        arguments.baud_rate,
        arguments.read_timeout,
        arguments.max_polls,
        max(128, arguments.max_records * 8),
        EvidenceSource.HOST_TEST,
    )
    adapter_factory = make_serial_adapter_factory(
        config, backend_factory=dependencies.serial_backend_factory
    )
    service_factory = make_read_service_factory(
        adapter_factory,
        _read_workflow(arguments),
        SERIAL_LIMITATIONS,
        slot,
    )
    return execute_product_job(request, service_factory, slot)


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
        "artifact": artifact,
        "hardware_claim": "NO_PERFORMANCE_VALIDATION",
    }


def _write_execution(execution: ProductJobExecution, stream: TextIO) -> None:
    result = execution.result
    stream.write(f"Job: {execution.request.job_id}\n")
    stream.write(f"Worker state: {execution.worker_state.value}\n")
    if result is not None:
        stream.write(f"Product status: {result.status.value}\n")
        stream.write(f"Evidence source: {result.evidence_source.value}\n")
        if result.test_run_outcome is not None:
            stream.write(f"Engineering outcome: {result.test_run_outcome.value}\n")
        stream.writelines(
            f"Limitation: {limitation}\n" for limitation in result.limitations
        )
    if execution.output is not None:
        read = execution.output.read_result
        stream.write(f"Read status: {read.status.value}\n")
        stream.write(f"Measurements: {len(read.measurements)}\n")
        stream.writelines(
            f"Missing: {missing}\n" for missing in read.missing_requirements
        )
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
            "a finalized DC or hysteresis job did not publish its result export"
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
        if arguments.command == "report":
            report_view = build_human_report_view(_load_report_input(arguments))
            publication = publish_human_report(arguments.output, report_view)
            if arguments.as_json:
                _write_json(_report_document(report_view, publication), output)
            else:
                _write_report_publication(report_view, publication, output)
            return _report_exit_code(report_view.outcome)
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
        if arguments.command == "demo":
            raise ProductFeatureUnavailableError(
                f"{arguments.command} is reserved for a later reviewed Phase 5 step"
            )
        if arguments.command in {"simulate", "replay"}:
            execution = _execute_workflow(arguments, injected)
        elif arguments.command == "observe":
            execution = _execute_observe(arguments, injected)
        else:
            raise CliUsageError("argparse returned an unknown command")

        artifact = _write_artifact(arguments, execution)
        if arguments.as_json:
            _write_json(
                _execution_document(arguments.command, execution, artifact), output
            )
        else:
            _write_execution(execution, output)
            if artifact is not None:
                output.write(f"Artifact: {artifact['path']}\n")
                output.write(f"SHA-256: {artifact['sha256']}\n")
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
