"""Freeze Software Phase 5 product APIs, CLI, schemas, and artifact fields."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import inspect
import io
import json
from collections.abc import Callable, Iterable
from dataclasses import MISSING, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import pytest

import analog_validation_app
import analog_validation_app.cli as product_cli
import analog_validation_app.errors as product_errors
from analog_validation_app import (
    DASHBOARD_HARDWARE_CLAIM,
    DASHBOARD_STATE_SCHEMA_VERSION,
    DASHBOARD_WIZARD_SCHEMA_VERSION,
    DEFAULT_PRODUCT_EVENT_QUEUE_SIZE,
    DEFAULT_PRODUCT_JOIN_TIMEOUT_S,
    HUMAN_REPORT_MANIFEST_SCHEMA_VERSION,
    HUMAN_REPORT_SCHEMA_VERSION,
    PORTFOLIO_DEMO_CONFIG_SCHEMA_VERSION,
    PORTFOLIO_DEMO_EPOCH,
    PORTFOLIO_DEMO_JOB_ID,
    PORTFOLIO_DEMO_MANIFEST_FILENAME,
    PORTFOLIO_DEMO_POINT_COUNT,
    PORTFOLIO_DEMO_SCHEMA_VERSION,
    PRODUCT_CATALOG_SCHEMA_VERSION,
    PRODUCT_JOB_EVENT_SCHEMA_VERSION,
    PRODUCT_JOB_SCHEMA_VERSION,
    PRODUCT_PROFILES,
    PRODUCT_RESULT_SCHEMA_VERSION,
    PRODUCT_SOURCES,
    PRODUCT_WORKFLOW_CONFIG_SCHEMA_VERSION,
    REPLAY_LIMITATIONS,
    REPORT_HARDWARE_CLAIM,
    REPORT_HTML_FILENAME,
    REPORT_MANIFEST_FILENAME,
    REPORT_MARKDOWN_FILENAME,
    REPORT_SVG_FILENAME,
    REPORT_TEXT_FILENAME,
    SERIAL_LIMITATIONS,
    SIMULATOR_LIMITATIONS,
    USER_ISSUE_SCHEMA_VERSION,
    issue_from_exception,
)
from analog_validation_app.dashboard.app import (
    DASHBOARD_SESSION_SCHEMA_VERSION,
    DashboardSessionResult,
    launch_dashboard,
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = ROOT / "test-data" / "golden"
MANIFEST_PATH = GOLDEN_DIR / "phase5_public_api.json"

MODULE_NAMES = (
    "analog_validation_app",
    "analog_validation_app.cli",
    "analog_validation_app.dashboard",
    "analog_validation_app.dashboard.app",
)
MODULES = {name: importlib.import_module(name) for name in MODULE_NAMES}

SCHEMAS = {
    "CLI_OUTPUT_SCHEMA_VERSION": product_cli.CLI_OUTPUT_SCHEMA_VERSION,
    "DASHBOARD_SESSION_SCHEMA_VERSION": DASHBOARD_SESSION_SCHEMA_VERSION,
    "DASHBOARD_STATE_SCHEMA_VERSION": DASHBOARD_STATE_SCHEMA_VERSION,
    "DASHBOARD_WIZARD_SCHEMA_VERSION": DASHBOARD_WIZARD_SCHEMA_VERSION,
    "HUMAN_REPORT_MANIFEST_SCHEMA_VERSION": HUMAN_REPORT_MANIFEST_SCHEMA_VERSION,
    "HUMAN_REPORT_SCHEMA_VERSION": HUMAN_REPORT_SCHEMA_VERSION,
    "PORTFOLIO_DEMO_CONFIG_SCHEMA_VERSION": PORTFOLIO_DEMO_CONFIG_SCHEMA_VERSION,
    "PORTFOLIO_DEMO_SCHEMA_VERSION": PORTFOLIO_DEMO_SCHEMA_VERSION,
    "PRODUCT_CATALOG_SCHEMA_VERSION": PRODUCT_CATALOG_SCHEMA_VERSION,
    "PRODUCT_JOB_EVENT_SCHEMA_VERSION": PRODUCT_JOB_EVENT_SCHEMA_VERSION,
    "PRODUCT_JOB_SCHEMA_VERSION": PRODUCT_JOB_SCHEMA_VERSION,
    "PRODUCT_RESULT_SCHEMA_VERSION": PRODUCT_RESULT_SCHEMA_VERSION,
    "PRODUCT_WORKFLOW_CONFIG_SCHEMA_VERSION": PRODUCT_WORKFLOW_CONFIG_SCHEMA_VERSION,
    "USER_ISSUE_SCHEMA_VERSION": USER_ISSUE_SCHEMA_VERSION,
}

ENUM_NAMES = (
    "DashboardActionType",
    "DashboardExportFormat",
    "DashboardWizardStep",
    "ProductJobType",
    "ProductResultStatus",
    "ProductSourceMode",
    "ProductWorkerState",
    "ReportChartKind",
    "UserIssueCode",
    "UserIssueSeverity",
)
ENUMS: dict[str, type[Enum]] = {
    name: getattr(analog_validation_app, name) for name in ENUM_NAMES
}

DATACLASS_NAMES = (
    "DashboardAction",
    "DashboardArtifactView",
    "DashboardArtifactsPanel",
    "DashboardConfigurationPanel",
    "DashboardPlotPanel",
    "DashboardPlotPoint",
    "DashboardProgressPanel",
    "DashboardResultPanel",
    "DashboardSourcePanel",
    "DashboardState",
    "DashboardWizardDraft",
    "DashboardWizardGuidance",
    "DashboardWizardState",
    "DemoArtifact",
    "HumanReportPublication",
    "HumanReportView",
    "PortfolioDemoPublication",
    "PreparedProductJob",
    "ProductJobEvent",
    "ProductJobExecution",
    "ProductJobRequest",
    "ProductJobResult",
    "ProductProfileDescriptor",
    "ProductServiceOutput",
    "ProductSourceDescriptor",
    "ProductWorkflowConfiguration",
    "ReportArtifact",
    "ReportCriterionView",
    "ReportPointView",
    "ReportReferenceView",
    "ReportSchemaView",
    "ReportValueView",
    "SerialSourceConfig",
    "UserIssue",
)
DATACLASSES: dict[str, type[object]] = {
    name: getattr(analog_validation_app, name) for name in DATACLASS_NAMES
}
DATACLASSES["CliDependencies"] = product_cli.CliDependencies
DATACLASSES["DashboardSessionResult"] = DashboardSessionResult

SIGNATURE_NAMES = (
    "DashboardApplication",
    "DashboardController",
    "DashboardPresenter",
    "DashboardWizardPresenter",
    "DemoArtifact",
    "HumanReportPublication",
    "HumanReportView",
    "PortfolioDemoPublication",
    "PreparedProductJob",
    "ProductJobEvent",
    "ProductJobRequest",
    "ProductJobResult",
    "ProductJobWorker",
    "ProductProfileDescriptor",
    "ProductServiceOutputSlot",
    "ProductSourceDescriptor",
    "ProductWorkflowConfiguration",
    "ReportArtifact",
    "SerialSourceConfig",
    "UserIssue",
    "build_human_report_view",
    "execute_product_job",
    "initial_dashboard_state",
    "issue_from_exception",
    "make_dc_sweep_service_factory",
    "make_hysteresis_service_factory",
    "make_read_service_factory",
    "prepare_product_job",
    "publish_human_report",
    "publish_portfolio_demo",
)
SIGNATURES: dict[str, Callable[..., Any]] = {
    name: getattr(analog_validation_app, name) for name in SIGNATURE_NAMES
}
SIGNATURES.update(
    {
        "CliDependencies": product_cli.CliDependencies,
        "DashboardSessionResult": DashboardSessionResult,
        "build_parser": product_cli.build_parser,
        "launch_dashboard": launch_dashboard,
        "main": product_cli.main,
    }
)

ERRORS: dict[str, type[Exception]] = {
    name: getattr(product_errors, name) for name in product_errors.__all__
}

GOLDEN_FILES = (
    "phase2_public_api.json",
    "phase3_public_api.json",
    "phase4_composite_v1.json",
    "phase4_public_api.json",
    "phase5_demo_v1.json",
    "phase5_human_reports_v1.json",
)


def _signature_parameters(value: Callable[..., Any]) -> list[list[object]]:
    return [
        [
            parameter.name,
            parameter.kind.name,
            parameter.default is inspect.Parameter.empty,
        ]
        for parameter in inspect.signature(value).parameters.values()
    ]


def _enum_members(enum_type: type[Enum]) -> list[list[object]]:
    return [[name, member.value] for name, member in enum_type.__members__.items()]


def _dataclass_fields(value: type[object]) -> list[list[object]]:
    assert is_dataclass(value)
    return [
        [
            field.name,
            field.default is MISSING and field.default_factory is MISSING,
            field.kw_only,
        ]
        for field in fields(value)
    ]


def _source_catalog() -> list[dict[str, object]]:
    return [
        {
            "mode": source.mode.value,
            "display_name": source.display_name,
            "summary": source.summary,
            "evidence_sources": [value.value for value in source.evidence_sources],
            "supported_jobs": [value.value for value in source.supported_jobs],
            "requires_serial_extra": source.requires_serial_extra,
            "is_default": source.is_default,
            "schema_version": source.schema_version,
        }
        for source in PRODUCT_SOURCES
    ]


def _profile_catalog() -> list[dict[str, object]]:
    return [
        {
            "name": profile.name,
            "version": profile.version,
            "display_name": profile.display_name,
            "summary": profile.summary,
            "source_modes": [value.value for value in profile.source_modes],
            "product_read_only": profile.product_read_only,
            "schema_version": profile.schema_version,
        }
        for profile in PRODUCT_PROFILES
    ]


def _choice_values(value: object) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return None
    if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        return [str(value)]
    return [str(item) for item in value]


def _nargs(value: object) -> int | str | None:
    if value is None or isinstance(value, (int, str)):
        return value
    return str(value)


def _cli_contract() -> dict[str, object]:
    parser = product_cli.build_parser()
    commands: dict[str, list[dict[str, object]]] = {}

    def walk(current: argparse.ArgumentParser, path: str) -> None:
        options: list[dict[str, object]] = []
        for action in current._actions:
            choices = getattr(action, "choices", None)
            if not action.option_strings and isinstance(choices, dict):
                for name, child in sorted(choices.items()):
                    child_path = f"{path} {name}".strip()
                    walk(child, child_path)
                continue
            if action.option_strings:
                options.append(
                    {
                        "flags": list(action.option_strings),
                        "dest": action.dest,
                        "required": action.required,
                        "nargs": _nargs(action.nargs),
                        "choices": _choice_values(choices),
                    }
                )
        commands[path or "<root>"] = sorted(
            options, key=lambda item: str(item["flags"])
        )

    walk(parser, "")
    return {"program": parser.prog, "commands": dict(sorted(commands.items()))}


def _run_json(argv: list[str]) -> dict[str, Any]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    status = product_cli.main(argv, stdout=stdout, stderr=stderr)
    if status != 0:
        raise AssertionError(f"CLI contract command failed ({status}): {stderr.getvalue()}")
    return json.loads(stdout.getvalue())


def _serialized_fields(output_parent: Path) -> dict[str, list[str]]:
    version = _run_json(["version", "--json"])
    profiles = _run_json(["profiles", "--json"])
    demo_directory = output_parent / "demo"
    demo_cli = _run_json(
        ["demo", "--output", str(demo_directory), "--json"]
    )
    demo_manifest = json.loads(
        (demo_directory / "manifest.json").read_text(encoding="utf-8")
    )
    report_manifest = json.loads(
        (demo_directory / "report" / "manifest.json").read_text(encoding="utf-8")
    )
    return {
        "cli_demo": sorted(demo_cli),
        "cli_demo_artifact": sorted(demo_cli["artifacts"][0]),
        "cli_profile_entry": sorted(profiles["profiles"][0]),
        "cli_profiles": sorted(profiles),
        "cli_version": sorted(version),
        "demo_artifact": sorted(demo_manifest["artifacts"][0]),
        "demo_examples": sorted(demo_manifest["examples"]),
        "demo_manifest": sorted(demo_manifest),
        "demo_result": sorted(demo_manifest["result"]),
        "demo_safety_and_privacy": sorted(demo_manifest["safety_and_privacy"]),
        "demo_workflow": sorted(demo_manifest["workflow"]),
        "human_report_artifact": sorted(report_manifest["artifacts"][0]),
        "human_report_manifest": sorted(report_manifest),
    }


def _issue_families() -> dict[str, list[str]]:
    samples: dict[str, BaseException] = {
        name: error_type("phase5 compatibility sample")
        for name, error_type in ERRORS.items()
    }
    samples["RuntimeError"] = RuntimeError("unexpected compatibility sample")
    return {
        name: [
            issue_from_exception(error).code.value,
            issue_from_exception(error).severity.value,
            issue_from_exception(error).technical_type,
        ]
        for name, error in sorted(samples.items())
    }


def _actual_manifest(output_parent: Path) -> dict[str, object]:
    return {
        "schema_version": "phase5-public-api-golden.v1",
        "package_version": analog_validation_app.__version__,
        "evidence_source": "HOST_TEST",
        "new_hardware_validation": False,
        "module_exports": {
            name: sorted(MODULES[name].__all__) for name in MODULE_NAMES
        },
        "schema_versions": SCHEMAS,
        "stable_constants": {
            "product_display_name": product_cli.PRODUCT_DISPLAY_NAME,
            "hardware_claims": {
                "dashboard": DASHBOARD_HARDWARE_CLAIM,
                "report": REPORT_HARDWARE_CLAIM,
            },
            "worker_defaults": {
                "event_queue_size": DEFAULT_PRODUCT_EVENT_QUEUE_SIZE,
                "join_timeout_seconds": DEFAULT_PRODUCT_JOIN_TIMEOUT_S,
            },
            "report_filenames": [
                REPORT_TEXT_FILENAME,
                REPORT_MARKDOWN_FILENAME,
                REPORT_HTML_FILENAME,
                REPORT_SVG_FILENAME,
                REPORT_MANIFEST_FILENAME,
            ],
            "demo_identity": {
                "epoch_utc": PORTFOLIO_DEMO_EPOCH.strftime(
                    "%Y-%m-%dT%H:%M:%S.%fZ"
                ),
                "job_id": PORTFOLIO_DEMO_JOB_ID,
                "manifest_filename": PORTFOLIO_DEMO_MANIFEST_FILENAME,
                "point_count": PORTFOLIO_DEMO_POINT_COUNT,
            },
            "limitations": {
                "simulator": list(SIMULATOR_LIMITATIONS),
                "replay": list(REPLAY_LIMITATIONS),
                "serial": list(SERIAL_LIMITATIONS),
            },
            "sources": _source_catalog(),
            "profiles": _profile_catalog(),
        },
        "enum_members": {
            name: _enum_members(enum_type) for name, enum_type in ENUMS.items()
        },
        "dataclass_fields": {
            name: _dataclass_fields(value)
            for name, value in sorted(DATACLASSES.items())
        },
        "signature_parameters": {
            name: _signature_parameters(value)
            for name, value in sorted(SIGNATURES.items())
        },
        "error_bases": {
            name: error.__base__.__name__
            for name, error in sorted(ERRORS.items())
            if error.__base__ is not None
        },
        "issue_families": _issue_families(),
        "cli_contract": _cli_contract(),
        "exit_codes": {
            "success": 0,
            "engineering_fail": product_cli.CLI_ENGINEERING_FAIL_EXIT_CODE,
            "usage": product_cli.CLI_USAGE_EXIT_CODE,
            "incomplete": product_cli.CLI_INCOMPLETE_EXIT_CODE,
            "unsupported": product_cli.CLI_UNSUPPORTED_EXIT_CODE,
            "operation_error": product_cli.CLI_OPERATION_ERROR_EXIT_CODE,
            "internal_error": product_cli.CLI_INTERNAL_ERROR_EXIT_CODE,
            "cancelled": product_cli.CLI_CANCELLED_EXIT_CODE,
        },
        "serialized_fields": _serialized_fields(output_parent),
        "golden_sha256": {
            name: hashlib.sha256((GOLDEN_DIR / name).read_bytes()).hexdigest()
            for name in GOLDEN_FILES
        },
    }


def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def actual_manifest(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    return _actual_manifest(tmp_path_factory.mktemp("phase5-public-api"))


def test_phase5_manifest_identity_is_explicitly_host_only(
    actual_manifest: dict[str, object],
) -> None:
    manifest = _manifest()
    assert set(manifest) == set(actual_manifest)
    assert manifest["schema_version"] == "phase5-public-api-golden.v1"
    assert manifest["package_version"] == analog_validation_app.__version__
    assert manifest["evidence_source"] == "HOST_TEST"
    assert manifest["new_hardware_validation"] is False


@pytest.mark.parametrize(
    "section",
    (
        "module_exports",
        "schema_versions",
        "stable_constants",
        "enum_members",
        "dataclass_fields",
        "signature_parameters",
        "error_bases",
        "issue_families",
        "cli_contract",
        "exit_codes",
        "serialized_fields",
        "golden_sha256",
    ),
)
def test_phase5_public_contract_matches_frozen_manifest(
    section: str,
    actual_manifest: dict[str, object],
) -> None:
    assert _manifest()[section] == actual_manifest[section]


def test_phase5_public_implementation_stays_in_product_package() -> None:
    for module_name in MODULE_NAMES:
        module = MODULES[module_name]
        for name in module.__all__:
            value = getattr(module, name)
            # Python 3.10 reports parameterized collections.abc.Callable aliases
            # as classes.  Their public names are frozen above, but they are type
            # aliases rather than package-owned implementations.
            if (inspect.isfunction(value) or inspect.isclass(value)) and not hasattr(
                value, "__origin__"
            ):
                assert value.__module__.startswith("analog_validation_app")


def test_phase5_freeze_keeps_receive_only_and_hardware_claim_boundaries() -> None:
    manifest = _manifest()
    constants = manifest["stable_constants"]
    assert manifest["new_hardware_validation"] is False
    assert constants["hardware_claims"] == {
        "dashboard": "NO_NEW_HARDWARE_VALIDATION",
        "report": "NO_NEW_HARDWARE_VALIDATION",
    }
    assert all(profile["product_read_only"] for profile in constants["profiles"])
    serial_source = next(
        value
        for value in constants["sources"]
        if value["mode"] == "SERIAL_READ_ONLY"
    )
    assert serial_source["supported_jobs"] == ["READ"]
