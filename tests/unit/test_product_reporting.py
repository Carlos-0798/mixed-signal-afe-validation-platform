from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import pytest

from analog_validation.exports import load_result_export_json
from analog_validation_app import (
    HUMAN_REPORT_MANIFEST_SCHEMA_VERSION,
    HumanReportPublication,
    ProductReportExistsError,
    ProductReportFormatError,
    ProductReportPathError,
    ReportArtifact,
    ReportChartKind,
    ReportPointView,
    ReportValueView,
    build_human_report_view,
    publish_human_report,
    render_human_report_html,
    render_human_report_markdown,
    render_human_report_svg,
    render_human_report_text,
    reporting,
)

ROOT = Path(__file__).resolve().parents[2]
DC_RESULT = ROOT / "test-data" / "golden" / "phase3_dc_sweep_result_v1.json"
HYSTERESIS_RESULT = ROOT / "test-data" / "golden" / "phase3_hysteresis_result_v1.json"


def dc_view():
    return build_human_report_view(load_result_export_json(DC_RESULT))


def hysteresis_view():
    return build_human_report_view(load_result_export_json(HYSTERESIS_RESULT))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_dc_renderers_copy_status_evidence_fit_and_exclusions() -> None:
    view = dc_view()

    text = render_human_report_text(view)
    markdown = render_human_report_markdown(view)
    svg = render_human_report_svg(view)
    html = render_human_report_html(view, svg)

    assert "OUTCOME: PASS" in text
    assert "EVIDENCE SOURCE: SYNTHETIC" in text
    assert "NO_NEW_HARDWARE_VALIDATION" in text
    assert "Canonical result SHA-256" in markdown
    assert "dc-point-2" in markdown
    assert r"HIGH\_SATURATION" in markdown
    assert "Included point" in svg
    assert "Excluded point" in svg
    assert "Frozen predicted values" in svg
    assert 'stroke-dasharray="7 5"' in svg
    assert "Outcome: PASS" in html
    assert "Not verified" in html
    assert svg in html


def test_dc_plot_uses_frozen_predicted_values_not_gain_metric() -> None:
    original = dc_view()
    changed_metrics = tuple(
        replace(value, value=999.0) if value.name == "gain" else value
        for value in original.metrics
    )
    changed = replace(original, metrics=changed_metrics)

    def predicted_line(svg: str) -> str:
        return next(
            line
            for line in svg.splitlines()
            if 'stroke="#111827"' in line and "polyline" in line
        )

    assert predicted_line(render_human_report_svg(original)) == predicted_line(
        render_human_report_svg(changed)
    )


def test_hysteresis_svg_shows_directions_brackets_and_final_metric_units() -> None:
    svg = render_human_report_svg(hysteresis_view())

    assert "Rising direction" in svg
    assert "Falling direction" in svg
    assert "Adjacent exported transition bracket" in svg
    assert "Final mean high threshold: 1750 mV" in svg
    assert "Final mean low threshold: 1550 mV" in svg
    assert 'data-direction="RISING"' in svg
    assert 'data-direction="FALLING"' in svg


def test_rendered_html_and_svg_are_structured_and_offline() -> None:
    view = hysteresis_view()
    svg = render_human_report_svg(view)
    html = render_human_report_html(view, svg)

    HTMLParser().feed(html)
    ElementTree.fromstring(svg)
    assert "<script" not in html.lower()
    assert "src=" not in html.lower()
    assert not re.search(r"href\s*=\s*['\"]https?://", html, re.IGNORECASE)
    assert "url(" not in html.lower()
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg


def test_hostile_text_is_escaped_in_markdown_and_html() -> None:
    view = replace(
        dc_view(),
        limitations=("<script>alert(1)</script> | [unsafe] *bold*",),
    )

    markdown = render_human_report_markdown(view)
    html = render_human_report_html(view)

    assert "\\<script\\>" in markdown
    assert "\\|" in markdown
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_generic_and_empty_chart_views_remain_explicit() -> None:
    generic = replace(dc_view(), chart_kind=ReportChartKind.NONE)
    empty_dc = replace(dc_view(), points=())
    empty_hysteresis = replace(hysteresis_view(), points=())

    assert "No supported chart" in render_human_report_svg(generic)
    assert "No finite plottable DC points" in render_human_report_svg(empty_dc)
    assert "No finite plottable hysteresis points" in render_human_report_svg(
        empty_hysteresis
    )


def test_reports_handle_no_points_criteria_or_missing_requirements() -> None:
    view = replace(
        dc_view(),
        points=(),
        criteria_id=None,
        criteria_version=None,
        criterion_results=(),
        missing_requirements=("measurement-count",),
    )

    text = render_human_report_text(view)
    markdown = render_human_report_markdown(view)
    html = render_human_report_html(view)

    assert "FINALIZED CRITERIA\n- none" in text
    assert "TRACEABLE POINTS\n- none" in text
    assert "measurement-count" in text
    assert "NOT EVALUATED" in markdown
    assert "not evaluated" in html


@pytest.mark.parametrize(
    "renderer",
    [
        render_human_report_text,
        render_human_report_markdown,
        render_human_report_svg,
        render_human_report_html,
    ],
)
def test_renderers_reject_wrong_view_type(renderer: Any) -> None:
    with pytest.raises(ProductReportFormatError, match="HumanReportView"):
        renderer(object())


@pytest.mark.parametrize(
    "svg",
    [1, "not-svg", "<svg></svg><script>alert('unsafe')</script>"],
)
def test_html_rejects_invalid_injected_svg(svg: Any) -> None:
    with pytest.raises(ProductReportFormatError, match="rendered SVG"):
        render_human_report_html(dc_view(), svg)


def test_low_level_plot_helpers_cover_defensive_display_paths() -> None:
    point = ReportPointView(
        0,
        "point",
        "INVALID",
        (),
        (
            ReportValueView("input", "not numeric", "mV"),
            ReportValueView("state", 2, "bool"),
            ReportValueView("cycle_index", True, "index"),
        ),
        (),
        ("bad",),
    )

    assert reporting._numeric(point, "input") is None
    assert reporting._numeric(point, "absent") is None
    assert reporting._text_value(point, "state") is None
    assert reporting._state(point) is None
    assert reporting._state(replace(point, values=())) is None
    assert (
        reporting._state(
            replace(point, values=(ReportValueView("state", True, "bool"),))
        )
        == 1.0
    )
    assert reporting._format_scalar(None) == "not available"
    assert reporting._format_scalar(True) == "true"
    assert reporting._format_scalar(False) == "false"
    view = dc_view()
    assert reporting._metric(view, "absent") is None
    assert (
        reporting._metric(
            replace(view, metrics=(ReportValueView("bad", True, "bool"),)),
            "bad",
        )
        is None
    )
    assert (
        reporting._metric(
            replace(view, metrics=(ReportValueView("bad", "text", "unit"),)),
            "bad",
        )
        is None
    )
    assert reporting._cycle_index(point) is None
    assert reporting._bounds(()) == (0.0, 1.0)
    assert reporting._bounds((5.0,)) == (4.0, 6.0)
    with pytest.raises(ProductReportFormatError, match="bounds"):
        reporting._map(1, 1, 1, 0, 10)
    assert "rect" in reporting._point_marker(point, 10, 10)
    excluded = replace(point, disposition="EXCLUDED")
    included = replace(point, disposition="INCLUDED")
    assert "path" in reporting._point_marker(excluded, 10, 10)
    assert "circle" in reporting._point_marker(included, 10, 10)


def test_hysteresis_chart_handles_missing_threshold_and_nonincluded_point() -> None:
    original = hysteresis_view()
    metrics = tuple(
        metric for metric in original.metrics if metric.name != "mean_high_threshold"
    )
    points = (replace(original.points[0], disposition="EXCLUDED"), *original.points[1:])

    svg = render_human_report_svg(replace(original, metrics=metrics, points=points))

    assert "Final mean high threshold" not in svg
    assert "Final mean low threshold: 1550 mV" in svg
    assert 'stroke="#c2410c"' in svg


def test_publish_creates_fixed_files_manifest_and_exact_hashes(tmp_path: Path) -> None:
    destination = tmp_path / "dc-report"
    publication = publish_human_report(destination, dc_view())

    assert publication.output_directory == destination.resolve()
    assert tuple(value.name for value in publication.artifacts) == (
        "report.txt",
        "report.md",
        "report.html",
        "chart.svg",
        "manifest.json",
    )
    for artifact in publication.artifacts:
        path = destination / artifact.name
        assert path.stat().st_size == artifact.size_bytes
        assert sha256(path) == artifact.sha256
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == HUMAN_REPORT_MANIFEST_SCHEMA_VERSION
    assert manifest["hardware_claim"] == "NO_NEW_HARDWARE_VALIDATION"
    assert manifest["canonical_result_sha256"] == dc_view().canonical_result_sha256
    assert len(manifest["artifacts"]) == 4
    assert str(tmp_path.resolve()) not in "".join(
        path.read_text(encoding="utf-8") for path in destination.iterdir()
    )
    assert publication.artifact("report.html").media_type.startswith("text/html")
    with pytest.raises(ProductReportFormatError, match="absent"):
        publication.artifact("missing")


def test_publish_is_deterministic_across_new_directories(tmp_path: Path) -> None:
    first = publish_human_report(tmp_path / "first", hysteresis_view())
    second = publish_human_report(tmp_path / "second", hysteresis_view())

    assert first.artifacts == second.artifacts
    assert all(
        (first.output_directory / artifact.name).read_bytes()
        == (second.output_directory / artifact.name).read_bytes()
        for artifact in first.artifacts
    )


def test_publish_rejects_existing_or_invalid_destinations(tmp_path: Path) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(ProductReportExistsError, match="already exists"):
        publish_human_report(existing, dc_view())
    with pytest.raises(ProductReportPathError, match="existing directory"):
        publish_human_report(tmp_path / "missing" / "report", dc_view())
    with pytest.raises(ProductReportPathError, match="string or path-like"):
        publish_human_report(object(), dc_view())  # type: ignore[arg-type]
    with pytest.raises(ProductReportPathError, match="new directory"):
        publish_human_report(Path("."), dc_view())
    with pytest.raises(ProductReportFormatError, match="HumanReportView"):
        publish_human_report(tmp_path / "wrong-view", object())  # type: ignore[arg-type]

    class BrokenPath(os.PathLike[str]):
        def __fspath__(self) -> str:
            raise OSError("broken path")

    with pytest.raises(ProductReportPathError, match="path is invalid"):
        publish_human_report(BrokenPath(), dc_view())


def test_publish_cleans_staging_after_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = reporting._write_staging_file
    calls = 0

    def fail_second(path: Path, payload: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("disk fault")
        original(path, payload)

    monkeypatch.setattr(reporting, "_write_staging_file", fail_second)
    destination = tmp_path / "write-failure"
    with pytest.raises(ProductReportPathError, match="could not be published"):
        publish_human_report(destination, dc_view())
    assert not destination.exists()
    assert not tuple(tmp_path.glob(".write-failure.*.tmp"))


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (FileExistsError("race"), ProductReportExistsError),
        (OSError("rename fault"), ProductReportPathError),
    ],
)
def test_publish_maps_atomic_rename_failures_and_cleans_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: OSError,
    expected: type[Exception],
) -> None:
    monkeypatch.setattr(os, "rename", lambda *_: (_ for _ in ()).throw(error))
    destination = tmp_path / "rename-failure"
    with pytest.raises(expected):
        publish_human_report(destination, dc_view())
    assert not destination.exists()
    assert not tuple(tmp_path.glob(".rename-failure.*.tmp"))


def test_publish_maps_parent_probe_and_staging_creation_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_exists = Path.exists

    def broken_exists(path: Path) -> bool:
        if path == tmp_path:
            raise OSError("probe fault")
        return original_exists(path)

    monkeypatch.setattr(Path, "exists", broken_exists)
    with pytest.raises(ProductReportPathError, match="cannot be prepared"):
        publish_human_report(tmp_path / "probe-failure", dc_view())

    monkeypatch.setattr(Path, "exists", original_exists)
    monkeypatch.setattr(
        reporting.tempfile,
        "mkdtemp",
        lambda **_: (_ for _ in ()).throw(OSError("temp fault")),
    )
    with pytest.raises(ProductReportPathError, match="could not be published"):
        publish_human_report(tmp_path / "temp-failure", dc_view())


def test_cleanup_staging_ignores_cleanup_os_error(tmp_path: Path) -> None:
    file_path = tmp_path / "not-a-directory"
    file_path.write_text("x", encoding="utf-8")
    reporting._cleanup_staging(file_path)
    assert file_path.exists()


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (
            lambda: ReportArtifact("../bad", "text/plain", 1, "0" * 64),
            "one local filename",
        ),
        (lambda: ReportArtifact("x", "", 1, "0" * 64), "media_type"),
        (lambda: ReportArtifact("x", "text/plain", -1, "0" * 64), "non-negative"),
        (lambda: ReportArtifact("x", "text/plain", 1, "bad"), "64 hex"),
        (
            lambda: HumanReportPublication("bad", ()),  # type: ignore[arg-type]
            "must be a Path",
        ),
        (lambda: HumanReportPublication(Path("x"), ()), "non-empty tuple"),
        (
            lambda: HumanReportPublication(
                Path("x"),
                (object(),),  # type: ignore[arg-type]
            ),
            "invalid value",
        ),
        (
            lambda: HumanReportPublication(
                Path("x"),
                (
                    ReportArtifact("a", "text/plain", 1, "0" * 64),
                    ReportArtifact("a", "text/plain", 1, "0" * 64),
                ),
            ),
            "cannot repeat",
        ),
    ],
)
def test_publication_models_reject_invalid_contracts(
    factory: Any,
    message: str,
) -> None:
    with pytest.raises(ProductReportFormatError, match=message):
        factory()
