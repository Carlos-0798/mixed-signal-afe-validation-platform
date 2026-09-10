from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from analog_validation import EvidenceSource
from analog_validation import TestRunOutcome as RunOutcome
from analog_validation.exports import (
    ExportSchemaReference,
    ResultExportBundle,
    load_result_export_json,
)
from analog_validation_app import (
    HUMAN_REPORT_SCHEMA_VERSION,
    MAX_REPORT_POINTS,
    REPORT_HARDWARE_CLAIM,
    HumanReportView,
    ProductReportFormatError,
    ProductReportLimitError,
    ProductRequestError,
    ReportChartKind,
    ReportCriterionView,
    ReportPointView,
    ReportReferenceView,
    ReportSchemaView,
    ReportValueView,
    build_human_report_view,
    presentation,
)

ROOT = Path(__file__).resolve().parents[2]
DC_RESULT = ROOT / "test-data" / "golden" / "phase3_dc_sweep_result_v1.json"
HYSTERESIS_RESULT = ROOT / "test-data" / "golden" / "phase3_hysteresis_result_v1.json"


def bundle(path: Path = DC_RESULT) -> ResultExportBundle:
    return load_result_export_json(path)


def view(path: Path = DC_RESULT) -> HumanReportView:
    return build_human_report_view(bundle(path))


def test_dc_view_copies_finalized_identity_outcome_and_points() -> None:
    selected = view()

    assert HUMAN_REPORT_SCHEMA_VERSION == "human-report.v1"
    assert REPORT_HARDWARE_CLAIM == "NO_NEW_HARDWARE_VALIDATION"
    assert MAX_REPORT_POINTS == 10_000
    assert selected.title == "DC Sweep Validation Report"
    assert selected.chart_kind is ReportChartKind.DC_SWEEP
    assert selected.outcome is RunOutcome.PASS
    assert selected.evidence_source is EvidenceSource.SYNTHETIC
    assert selected.is_bench_evidence is False
    assert selected.run_id == "phase3-golden-dc"
    assert selected.canonical_result_sha256 == (
        "a137b527303a7a8938b4bba7f74d28f35e9a9ca013474cd5946f4d6da9591547"
    )
    assert selected.points[2].disposition == "EXCLUDED"
    assert selected.points[2].get_value("output") is not None
    assert selected.points[2].get_value("absent") is None
    assert selected.criterion_results[0].passed is True
    assert "no declared physical bench evidence" in selected.not_verified[-1]


def test_hysteresis_view_selects_only_hysteresis_presentation() -> None:
    selected = view(HYSTERESIS_RESULT)

    assert selected.title == "Hysteresis Validation Report"
    assert selected.chart_kind is ReportChartKind.HYSTERESIS
    assert selected.points[0].get_value("direction") == ReportValueView(
        "direction", "RISING", "enum"
    )
    metrics = {value.name: value.value for value in selected.metrics}
    assert metrics["mean_high_threshold"] == 1750.0
    assert metrics["mean_low_threshold"] == 1550.0


def test_generic_and_conflicting_source_schema_detection() -> None:
    selected = bundle()
    generic_bundle = replace(
        selected,
        source_schemas=(ExportSchemaReference("test-run", "test-run.v1"),),
    )
    generic = build_human_report_view(generic_bundle)
    assert generic.chart_kind is ReportChartKind.NONE
    assert generic.title == "Analog Validation Report"

    conflicting = replace(
        selected,
        source_schemas=(
            *selected.source_schemas,
            ExportSchemaReference("hysteresis-analysis", "hysteresis-analysis.v1"),
        ),
    )
    with pytest.raises(ProductReportFormatError, match="multiple analysis schemas"):
        build_human_report_view(conflicting)


def test_view_sanitizes_hostile_display_text_without_changing_bundle_hash() -> None:
    selected = bundle()
    hostile = replace(
        selected,
        limitations=("<script>alert(1)</script> | line\nbreak",),
    )

    report = build_human_report_view(hostile)

    assert report.limitations == ("<script>alert(1)</script> | line break",)
    assert len(report.canonical_result_sha256) == 64


def test_builder_rejects_wrong_type_and_bounded_point_overflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ProductReportFormatError, match="ResultExportBundle"):
        build_human_report_view(object())  # type: ignore[arg-type]

    monkeypatch.setattr(presentation, "MAX_REPORT_POINTS", 1)
    with pytest.raises(ProductReportLimitError, match="point limit"):
        build_human_report_view(bundle())


def test_not_verified_wording_preserves_each_bench_boundary() -> None:
    controller = presentation._not_verified(EvidenceSource.BENCH_CONTROLLER)
    dmm = presentation._not_verified(EvidenceSource.BENCH_DMM)

    assert "controller evidence" in controller[-1]
    assert "not independently repeated" in dmm[-1]


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: ReportSchemaView(1, "1"), "string"),  # type: ignore[arg-type]
        (lambda: ReportSchemaView("x" * 1025, "1"), "1024"),
        (lambda: ReportValueView("gain", float("inf"), "ratio"), "finite"),
        (
            lambda: ReportCriterionView("gain", float("nan"), "ratio", True, 1, 2),
            "finite",
        ),
        (
            lambda: ReportCriterionView(
                "gain",
                1,
                "ratio",
                "yes",  # type: ignore[arg-type]
                1,
                2,
            ),
            "boolean",
        ),
        (
            lambda: ReportCriterionView("gain", 1, "ratio", True, True, 2),
            "numeric",
        ),
        (
            lambda: ReportReferenceView(
                "id",
                "raw",
                "time",
                object(),  # type: ignore[arg-type]
                "source",
            ),
            "string",
        ),
        (
            lambda: ReportPointView(-1, "point", "INCLUDED", (), (), (), ()),
            "non-negative",
        ),
        (
            lambda: ReportPointView(
                0,
                "point",
                "INCLUDED",
                "bad",  # type: ignore[arg-type]
                (),
                (),
                (),
            ),
            "iterable",
        ),
        (
            lambda: ReportPointView(
                0,
                "point",
                "INCLUDED",
                (),
                (ReportValueView("x", 1, "mV"), ReportValueView("x", 2, "mV")),
                (),
                (),
            ),
            "cannot repeat",
        ),
    ],
)
def test_presentation_value_models_reject_invalid_inputs(
    factory: Any,
    message: str,
) -> None:
    with pytest.raises(
        (ProductReportFormatError, ProductReportLimitError), match=message
    ):
        factory()


def test_point_get_value_rejects_non_text_name() -> None:
    point = view().points[0]
    with pytest.raises(ProductRequestError, match="must be a string"):
        point.get_value(1)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"title": 1}, "string"),
        ({"canonical_result_sha256": "short"}, "64"),
        ({"canonical_result_sha256": "z" * 64}, "hexadecimal"),
        ({"evidence_source": "SYNTHETIC"}, "EvidenceSource"),
        ({"outcome": "PASS"}, "TestRunOutcome"),
        ({"chart_kind": "DC_SWEEP"}, "ReportChartKind"),
        ({"source_schemas": ()}, "cannot be empty"),
        ({"source_schemas": (object(),)}, "invalid value"),
        ({"metrics": "bad"}, "iterable"),
        ({"points": (object(),)}, "invalid value"),
        ({"points": (view().points[1],)}, "contiguous"),
        ({"criterion_results": (object(),)}, "invalid value"),
        ({"limitations": ()}, "cannot be empty"),
        ({"missing_requirements": (1,)}, "invalid value"),
        ({"not_verified": ()}, "cannot be empty"),
        ({"criteria_id": None}, "present together"),
        (
            {
                "criteria_id": None,
                "criteria_version": None,
                "criterion_results": view().criterion_results,
            },
            "require criteria identity",
        ),
        ({"schema_version": "human-report.v2"}, "unsupported"),
    ],
)
def test_human_report_view_rejects_invalid_contracts(
    changes: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ProductReportFormatError, match=message):
        replace(view(), **changes)


def test_view_point_limit_is_enforced_on_direct_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = view()
    monkeypatch.setattr(presentation, "MAX_REPORT_POINTS", 1)
    with pytest.raises(ProductReportLimitError, match="point limit"):
        replace(selected, points=selected.points[:2])


def test_control_only_text_uses_explicit_fallback() -> None:
    assert presentation._display_text("\n\t") == "[not printable]"
