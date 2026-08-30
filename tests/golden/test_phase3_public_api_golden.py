"""Freeze Software Phase 3 public APIs, versions, enums, and golden files."""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any

import analog_validation
from analog_validation.analysis import (
    ANALYSIS_COMMON_SCHEMA_VERSION,
    CALIBRATION_ANALYSIS_SCHEMA_VERSION,
    CALIBRATION_METHOD,
    CUTOFF_INTERPOLATION_METHOD,
    DC_SWEEP_ANALYSIS_SCHEMA_VERSION,
    DC_SWEEP_CRITERIA_SCHEMA_VERSION,
    DC_SWEEP_EVALUATION_SCHEMA_VERSION,
    FREQUENCY_RESPONSE_ANALYSIS_SCHEMA_VERSION,
    HYSTERESIS_ANALYSIS_SCHEMA_VERSION,
    HYSTERESIS_CRITERIA_SCHEMA_VERSION,
    HYSTERESIS_EVALUATION_SCHEMA_VERSION,
    AnalysisQualityPolicy,
    AnalysisRecordReference,
    CalibrationApplicationConfig,
    CalibrationFitConfig,
    CalibrationPointExclusionReason,
    DCSweepAcceptanceCriteria,
    DCSweepAnalysisConfig,
    DCSweepCriterionName,
    DCSweepPointExclusionReason,
    FrequencyPointExclusionReason,
    FrequencyResponseAnalysisConfig,
    HysteresisAcceptanceCriteria,
    HysteresisAnalysisConfig,
    HysteresisCriterionName,
    MeasurementBatch,
    PointDisposition,
    PointExclusionReason,
    SweepDirection,
    analyze_dc_sweep,
    analyze_frequency_response,
    analyze_hysteresis,
    apply_linear_calibration,
    evaluate_dc_sweep,
    evaluate_hysteresis,
    fit_linear_calibration,
)
from analog_validation.exports import (
    CSV_RESULT_EXPORT_COLUMNS,
    MAX_RESULT_EXPORT_BYTES,
    MAX_RESULT_EXPORT_ROWS,
    RESULT_EXPORT_SCHEMA_VERSION,
    ResultExportBundle,
    ResultExportError,
    ResultExportExistsError,
    ResultExportFormatError,
    ResultExportLimitError,
    ResultExportPathError,
    UnsupportedResultExportVersion,
    build_dc_sweep_export,
    build_hysteresis_export,
    dump_result_export_csv,
    dump_result_export_json,
    load_result_export_csv,
    load_result_export_json,
    parse_result_export_csv,
    parse_result_export_json,
    result_export_from_dict,
    result_export_to_dict,
    write_result_export_csv,
    write_result_export_json,
)
from analog_validation.runners import (
    DC_SWEEP_RUNNER_SCHEMA_VERSION,
    HYSTERESIS_RUNNER_SCHEMA_VERSION,
    DCSweepPlan,
    HysteresisPlan,
    run_dc_sweep,
    run_hysteresis,
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = ROOT / "test-data" / "golden"
MANIFEST_PATH = GOLDEN_DIR / "phase3_public_api.json"

MODULE_NAMES = (
    "analog_validation",
    "analog_validation.analysis",
    "analog_validation.runners",
    "analog_validation.exports",
)
MODULES = {name: importlib.import_module(name) for name in MODULE_NAMES}
SCHEMAS = {
    "ANALYSIS_COMMON_SCHEMA_VERSION": ANALYSIS_COMMON_SCHEMA_VERSION,
    "CALIBRATION_ANALYSIS_SCHEMA_VERSION": CALIBRATION_ANALYSIS_SCHEMA_VERSION,
    "DC_SWEEP_ANALYSIS_SCHEMA_VERSION": DC_SWEEP_ANALYSIS_SCHEMA_VERSION,
    "DC_SWEEP_CRITERIA_SCHEMA_VERSION": DC_SWEEP_CRITERIA_SCHEMA_VERSION,
    "DC_SWEEP_EVALUATION_SCHEMA_VERSION": DC_SWEEP_EVALUATION_SCHEMA_VERSION,
    "DC_SWEEP_RUNNER_SCHEMA_VERSION": DC_SWEEP_RUNNER_SCHEMA_VERSION,
    "FREQUENCY_RESPONSE_ANALYSIS_SCHEMA_VERSION": (
        FREQUENCY_RESPONSE_ANALYSIS_SCHEMA_VERSION
    ),
    "HYSTERESIS_ANALYSIS_SCHEMA_VERSION": HYSTERESIS_ANALYSIS_SCHEMA_VERSION,
    "HYSTERESIS_CRITERIA_SCHEMA_VERSION": HYSTERESIS_CRITERIA_SCHEMA_VERSION,
    "HYSTERESIS_EVALUATION_SCHEMA_VERSION": HYSTERESIS_EVALUATION_SCHEMA_VERSION,
    "HYSTERESIS_RUNNER_SCHEMA_VERSION": HYSTERESIS_RUNNER_SCHEMA_VERSION,
    "RESULT_EXPORT_SCHEMA_VERSION": RESULT_EXPORT_SCHEMA_VERSION,
}
ENUMS: dict[str, type[Enum]] = {
    "CalibrationPointExclusionReason": CalibrationPointExclusionReason,
    "DCSweepCriterionName": DCSweepCriterionName,
    "DCSweepPointExclusionReason": DCSweepPointExclusionReason,
    "FrequencyPointExclusionReason": FrequencyPointExclusionReason,
    "HysteresisCriterionName": HysteresisCriterionName,
    "PointDisposition": PointDisposition,
    "PointExclusionReason": PointExclusionReason,
    "SweepDirection": SweepDirection,
}
SIGNATURES: dict[str, Callable[..., Any]] = {
    "AnalysisQualityPolicy": AnalysisQualityPolicy,
    "AnalysisRecordReference": AnalysisRecordReference,
    "CalibrationApplicationConfig": CalibrationApplicationConfig,
    "CalibrationFitConfig": CalibrationFitConfig,
    "DCSweepAcceptanceCriteria": DCSweepAcceptanceCriteria,
    "DCSweepAnalysisConfig": DCSweepAnalysisConfig,
    "DCSweepPlan": DCSweepPlan,
    "FrequencyResponseAnalysisConfig": FrequencyResponseAnalysisConfig,
    "HysteresisAcceptanceCriteria": HysteresisAcceptanceCriteria,
    "HysteresisAnalysisConfig": HysteresisAnalysisConfig,
    "HysteresisPlan": HysteresisPlan,
    "MeasurementBatch": MeasurementBatch,
    "ResultExportBundle": ResultExportBundle,
    "analyze_dc_sweep": analyze_dc_sweep,
    "analyze_frequency_response": analyze_frequency_response,
    "analyze_hysteresis": analyze_hysteresis,
    "apply_linear_calibration": apply_linear_calibration,
    "build_dc_sweep_export": build_dc_sweep_export,
    "build_hysteresis_export": build_hysteresis_export,
    "dump_result_export_csv": dump_result_export_csv,
    "dump_result_export_json": dump_result_export_json,
    "evaluate_dc_sweep": evaluate_dc_sweep,
    "evaluate_hysteresis": evaluate_hysteresis,
    "fit_linear_calibration": fit_linear_calibration,
    "load_result_export_csv": load_result_export_csv,
    "load_result_export_json": load_result_export_json,
    "parse_result_export_csv": parse_result_export_csv,
    "parse_result_export_json": parse_result_export_json,
    "result_export_from_dict": result_export_from_dict,
    "result_export_to_dict": result_export_to_dict,
    "run_dc_sweep": run_dc_sweep,
    "run_hysteresis": run_hysteresis,
    "write_result_export_csv": write_result_export_csv,
    "write_result_export_json": write_result_export_json,
}
ERRORS: dict[str, type[Exception]] = {
    "ResultExportError": ResultExportError,
    "ResultExportExistsError": ResultExportExistsError,
    "ResultExportFormatError": ResultExportFormatError,
    "ResultExportLimitError": ResultExportLimitError,
    "ResultExportPathError": ResultExportPathError,
    "UnsupportedResultExportVersion": UnsupportedResultExportVersion,
}
GOLDEN_FILES = (
    "phase3_dc_sweep_input_v1.json",
    "phase3_dc_sweep_result_v1.json",
    "phase3_hysteresis_result_v1.json",
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


def _actual_manifest() -> dict[str, object]:
    return {
        "schema_version": "phase3-public-api-golden.v1",
        "package_version": analog_validation.__version__,
        "evidence_source": "HOST_TEST",
        "module_exports": {
            name: sorted(module.__all__) for name, module in MODULES.items()
        },
        "schema_versions": SCHEMAS,
        "stable_constants": {
            "CALIBRATION_METHOD": CALIBRATION_METHOD,
            "CUTOFF_INTERPOLATION_METHOD": CUTOFF_INTERPOLATION_METHOD,
            "CSV_RESULT_EXPORT_COLUMNS": list(CSV_RESULT_EXPORT_COLUMNS),
            "MAX_RESULT_EXPORT_BYTES": MAX_RESULT_EXPORT_BYTES,
            "MAX_RESULT_EXPORT_ROWS": MAX_RESULT_EXPORT_ROWS,
        },
        "enum_values": {
            name: [member.value for member in enum_type]
            for name, enum_type in ENUMS.items()
        },
        "signature_parameters": {
            name: _signature_parameters(value) for name, value in SIGNATURES.items()
        },
        "error_bases": {
            name: error.__base__.__name__
            for name, error in ERRORS.items()
            if error.__base__ is not None
        },
        "golden_sha256": {
            name: hashlib.sha256((GOLDEN_DIR / name).read_bytes()).hexdigest()
            for name in GOLDEN_FILES
        },
    }


def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_phase3_manifest_identity_is_explicitly_host_only() -> None:
    manifest = _manifest()
    assert set(manifest) == set(_actual_manifest())
    assert manifest["schema_version"] == "phase3-public-api-golden.v1"
    assert manifest["package_version"] == analog_validation.__version__
    assert manifest["evidence_source"] == "HOST_TEST"


def test_phase3_public_module_exports_match_frozen_manifest() -> None:
    assert _manifest()["module_exports"] == _actual_manifest()["module_exports"]


def test_phase3_versions_and_stable_constants_match_frozen_manifest() -> None:
    manifest = _manifest()
    actual = _actual_manifest()
    assert manifest["schema_versions"] == actual["schema_versions"]
    assert manifest["stable_constants"] == actual["stable_constants"]


def test_phase3_enum_values_match_frozen_manifest() -> None:
    assert _manifest()["enum_values"] == _actual_manifest()["enum_values"]


def test_phase3_signature_shapes_match_frozen_manifest() -> None:
    assert _manifest()["signature_parameters"] == _actual_manifest()[
        "signature_parameters"
    ]


def test_phase3_error_families_match_frozen_manifest() -> None:
    assert _manifest()["error_bases"] == _actual_manifest()["error_bases"]


def test_phase3_golden_files_match_frozen_hashes() -> None:
    assert _manifest()["golden_sha256"] == _actual_manifest()["golden_sha256"]


def test_phase3_public_implementation_stays_in_formal_package() -> None:
    for module_name in MODULE_NAMES[1:]:
        module = MODULES[module_name]
        for name in module.__all__:
            value = getattr(module, name)
            if inspect.isfunction(value) or inspect.isclass(value):
                implementation = value.__module__
                assert implementation.startswith("analog_validation.")
                assert not implementation.startswith("dashboard.")
