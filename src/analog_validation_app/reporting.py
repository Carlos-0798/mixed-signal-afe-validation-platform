"""Deterministic local human reports rendered from presentation-only views."""

from __future__ import annotations

import hashlib
import html
import json
import math
import os
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import pairwise
from os import PathLike
from pathlib import Path
from typing import cast

from .errors import (
    ProductReportExistsError,
    ProductReportFormatError,
    ProductReportPathError,
)
from .presentation import (
    HUMAN_REPORT_SCHEMA_VERSION,
    REPORT_HARDWARE_CLAIM,
    HumanReportView,
    ReportChartKind,
    ReportCriterionView,
    ReportPointView,
    ReportValueView,
)

HUMAN_REPORT_MANIFEST_SCHEMA_VERSION = "human-report-manifest.v1"
REPORT_TEXT_FILENAME = "report.txt"
REPORT_MARKDOWN_FILENAME = "report.md"
REPORT_HTML_FILENAME = "report.html"
REPORT_SVG_FILENAME = "chart.svg"
REPORT_MANIFEST_FILENAME = "manifest.json"

_WIDTH = 960.0
_HEIGHT = 540.0
_LEFT = 100.0
_RIGHT = 900.0
_TOP = 72.0
_BOTTOM = 430.0


def _clean(value: str) -> str:
    return " ".join(value.split())


def _format_scalar(value: object) -> str:
    if value is None:
        return "not available"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(value, ".12g")
    return str(value)


def _format_value(value: ReportValueView) -> str:
    return f"{_format_scalar(value.value)} {value.unit}"


def _format_limit(value: float | None) -> str:
    return "none" if value is None else format(value, ".12g")


def _criterion_range(value: ReportCriterionView) -> str:
    return f"{_format_limit(value.lower_limit)} to {_format_limit(value.upper_limit)}"


def _markdown(value: str) -> str:
    escaped = _clean(value).replace("\\", "\\\\")
    for character in ("`", "*", "_", "[", "]", "<", ">", "|", "#"):
        escaped = escaped.replace(character, f"\\{character}")
    return escaped


def _html(value: object) -> str:
    return html.escape(_clean(str(value)), quote=True)


def _numeric(point: ReportPointView, name: str) -> float | None:
    value = point.get_value(name)
    if value is None or isinstance(value.value, bool):
        return None
    if isinstance(value.value, (int, float)):
        checked = float(value.value)
        return checked if math.isfinite(checked) else None
    return None


def _text_value(point: ReportPointView, name: str) -> str | None:
    value = point.get_value(name)
    return value.value if value is not None and isinstance(value.value, str) else None


def _state(point: ReportPointView) -> float | None:
    value = point.get_value("state")
    if value is None:
        return None
    raw = value.value
    if isinstance(raw, bool):
        return 1.0 if raw else 0.0
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        number = float(raw)
        if number in {0.0, 1.0}:
            return number
    return None


def _metric(view: HumanReportView, name: str) -> float | None:
    value = next((item for item in view.metrics if item.name == name), None)
    if value is None or isinstance(value.value, bool):
        return None
    if isinstance(value.value, (int, float)):
        number = float(value.value)
        return number if math.isfinite(number) else None
    return None


def _unit(view: HumanReportView, value_name: str, *, metric: bool = False) -> str:
    values: Iterable[ReportValueView]
    if metric:
        values = (value for value in view.metrics if value.name == value_name)
    else:
        values = (
            value
            for point in view.points
            for value in point.values
            if value.name == value_name
        )
    selected = next(iter(values), None)
    return "unitless" if selected is None else selected.unit


def _bounds(values: Iterable[float]) -> tuple[float, float]:
    frozen = tuple(values)
    if not frozen:
        return 0.0, 1.0
    minimum = min(frozen)
    maximum = max(frozen)
    span = maximum - minimum
    padding = max(span * 0.08, abs(minimum) * 0.01, abs(maximum) * 0.01, 1.0)
    if span == 0.0:
        return minimum - padding, maximum + padding
    return minimum - padding, maximum + padding


def _map(
    value: float, minimum: float, maximum: float, low: float, high: float
) -> float:
    if maximum <= minimum:
        raise ProductReportFormatError("plot bounds must increase")
    return low + (value - minimum) * (high - low) / (maximum - minimum)


def _x(value: float, minimum: float, maximum: float) -> float:
    return _map(value, minimum, maximum, _LEFT, _RIGHT)


def _y(value: float, minimum: float, maximum: float) -> float:
    return _map(value, minimum, maximum, _BOTTOM, _TOP)


def _svg_text(x: float, y: float, text: str, **attributes: str) -> str:
    extra = "".join(f' {name}="{_html(value)}"' for name, value in attributes.items())
    return f'<text x="{x:.2f}" y="{y:.2f}"{extra}>{_html(text)}</text>'


def _svg_header(view: HumanReportView, description: str) -> list[str]:
    return [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH:.0f}" '
            f'height="{_HEIGHT:.0f}" viewBox="0 0 {_WIDTH:.0f} {_HEIGHT:.0f}" '
            'role="img" aria-labelledby="chart-title chart-description">'
        ),
        f'<title id="chart-title">{_html(view.title)}</title>',
        f'<desc id="chart-description">{_html(description)}</desc>',
        '<rect width="960" height="540" fill="#ffffff"/>',
        _svg_text(
            40,
            34,
            view.title,
            id="chart-title-visible",
            fill="#172554",
            **{"font-size": "22", "font-weight": "700"},
        ),
        _svg_text(
            40,
            58,
            f"Outcome: {view.outcome.value} | Evidence: {view.evidence_source.value}",
            fill="#334155",
            **{"font-size": "14", "font-weight": "600"},
        ),
        '<rect x="100" y="72" width="800" height="358" fill="#f8fafc" stroke="#94a3b8"/>',
    ]


def _svg_footer(view: HumanReportView) -> list[str]:
    return [
        _svg_text(
            40,
            518,
            f"Canonical result SHA-256: {view.canonical_result_sha256}",
            fill="#475569",
            **{"font-size": "11"},
        ),
        _svg_text(
            40,
            500,
            "Presentation only; report generation performed no new hardware validation.",
            fill="#7c2d12",
            **{"font-size": "12", "font-weight": "600"},
        ),
        "</svg>",
    ]


def _axes(
    x_minimum: float,
    x_maximum: float,
    y_minimum: float,
    y_maximum: float,
    x_label: str,
    y_label: str,
) -> list[str]:
    lines = [
        f'<line x1="{_LEFT:.2f}" y1="{_BOTTOM:.2f}" x2="{_RIGHT:.2f}" y2="{_BOTTOM:.2f}" stroke="#334155"/>',
        f'<line x1="{_LEFT:.2f}" y1="{_TOP:.2f}" x2="{_LEFT:.2f}" y2="{_BOTTOM:.2f}" stroke="#334155"/>',
    ]
    for index in range(5):
        fraction = index / 4
        x_value = x_minimum + (x_maximum - x_minimum) * fraction
        y_value = y_minimum + (y_maximum - y_minimum) * fraction
        x_coord = _LEFT + (_RIGHT - _LEFT) * fraction
        y_coord = _BOTTOM - (_BOTTOM - _TOP) * fraction
        lines.extend(
            (
                f'<line x1="{x_coord:.2f}" y1="{_TOP:.2f}" x2="{x_coord:.2f}" y2="{_BOTTOM:.2f}" stroke="#e2e8f0"/>',
                f'<line x1="{_LEFT:.2f}" y1="{y_coord:.2f}" x2="{_RIGHT:.2f}" y2="{y_coord:.2f}" stroke="#e2e8f0"/>',
                _svg_text(
                    x_coord,
                    _BOTTOM + 20,
                    format(x_value, ".6g"),
                    fill="#475569",
                    **{"font-size": "11", "text-anchor": "middle"},
                ),
                _svg_text(
                    _LEFT - 10,
                    y_coord + 4,
                    format(y_value, ".6g"),
                    fill="#475569",
                    **{"font-size": "11", "text-anchor": "end"},
                ),
            )
        )
    lines.extend(
        (
            _svg_text(
                (_LEFT + _RIGHT) / 2,
                480,
                x_label,
                fill="#0f172a",
                **{"font-size": "13", "text-anchor": "middle"},
            ),
            (
                f'<text x="24" y="{(_TOP + _BOTTOM) / 2:.2f}" fill="#0f172a" '
                'font-size="13" text-anchor="middle" '
                f'transform="rotate(-90 24 {(_TOP + _BOTTOM) / 2:.2f})">{_html(y_label)}</text>'
            ),
        )
    )
    return lines


def _point_marker(point: ReportPointView, x_coord: float, y_coord: float) -> str:
    if point.disposition == "INCLUDED":
        return f'<circle cx="{x_coord:.2f}" cy="{y_coord:.2f}" r="4" fill="#2563eb" stroke="#1e3a8a"/>'
    if point.disposition == "EXCLUDED":
        return (
            f'<path d="M {x_coord - 5:.2f} {y_coord - 5:.2f} L {x_coord + 5:.2f} {y_coord + 5:.2f} '
            f'M {x_coord - 5:.2f} {y_coord + 5:.2f} L {x_coord + 5:.2f} {y_coord - 5:.2f}" '
            'stroke="#c2410c" stroke-width="2" fill="none"/>'
        )
    return (
        f'<rect x="{x_coord - 4:.2f}" y="{y_coord - 4:.2f}" width="8" height="8" '
        f'fill="#dc2626" stroke="#7f1d1d" transform="rotate(45 {x_coord:.2f} {y_coord:.2f})"/>'
    )


def _render_dc_svg(view: HumanReportView) -> str:
    plotted = tuple(
        (point, x_value, y_value, _numeric(point, "predicted_output"))
        for point in view.points
        for x_value in [_numeric(point, "input")]
        for y_value in [_numeric(point, "output")]
        if x_value is not None and y_value is not None
    )
    x_minimum, x_maximum = _bounds(value[1] for value in plotted)
    y_values = [value[2] for value in plotted]
    y_values.extend(value[3] for value in plotted if value[3] is not None)
    y_minimum, y_maximum = _bounds(cast(Iterable[float], y_values))
    lines = _svg_header(
        view,
        "DC points and frozen predicted outputs copied from the finalized result bundle.",
    )
    lines.extend(
        _axes(
            x_minimum,
            x_maximum,
            y_minimum,
            y_maximum,
            f"Input ({_unit(view, 'input')})",
            f"Output ({_unit(view, 'output')})",
        )
    )
    predicted = [
        f"{_x(x_value, x_minimum, x_maximum):.2f},{_y(predicted_value, y_minimum, y_maximum):.2f}"
        for point, x_value, _, predicted_value in plotted
        if point.disposition == "INCLUDED" and predicted_value is not None
    ]
    if predicted:
        lines.append(
            f'<polyline points="{" ".join(predicted)}" fill="none" stroke="#111827" '
            'stroke-width="2" stroke-dasharray="7 5"/>'
        )
    if not plotted:
        lines.append(
            _svg_text(
                500,
                250,
                "No finite plottable DC points are present in this finalized result.",
                fill="#7c2d12",
                **{"font-size": "15", "text-anchor": "middle"},
            )
        )
    for point, x_value, y_value, _ in plotted:
        lines.append(
            _point_marker(
                point,
                _x(x_value, x_minimum, x_maximum),
                _y(y_value, y_minimum, y_maximum),
            )
        )
    lines.extend(
        (
            '<circle cx="650" cy="92" r="4" fill="#2563eb" stroke="#1e3a8a"/>',
            _svg_text(662, 96, "Included point", fill="#0f172a", **{"font-size": "11"}),
            '<path d="M 748 87 L 758 97 M 748 97 L 758 87" stroke="#c2410c" stroke-width="2"/>',
            _svg_text(764, 96, "Excluded point", fill="#0f172a", **{"font-size": "11"}),
            '<rect x="650" y="107" width="8" height="8" fill="#dc2626" transform="rotate(45 654 111)"/>',
            _svg_text(662, 115, "Invalid point", fill="#0f172a", **{"font-size": "11"}),
            '<line x1="748" y1="111" x2="758" y2="111" stroke="#111827" stroke-width="2" stroke-dasharray="5 3"/>',
            _svg_text(
                764,
                115,
                "Frozen predicted values",
                fill="#0f172a",
                **{"font-size": "11"},
            ),
        )
    )
    lines.extend(_svg_footer(view))
    return "\n".join(lines) + "\n"


def _cycle_index(point: ReportPointView) -> int | None:
    value = point.get_value("cycle_index")
    if (
        value is None
        or isinstance(value.value, bool)
        or not isinstance(value.value, int)
    ):
        return None
    return value.value


def _render_hysteresis_svg(view: HumanReportView) -> str:
    plotted = tuple(
        (point, cycle, direction, input_value, state_value)
        for point in view.points
        for cycle in [_cycle_index(point)]
        for direction in [_text_value(point, "direction")]
        for input_value in [_numeric(point, "input")]
        for state_value in [_state(point)]
        if cycle is not None
        and direction in {"RISING", "FALLING"}
        and input_value is not None
        and state_value is not None
    )
    high_threshold = _metric(view, "mean_high_threshold")
    low_threshold = _metric(view, "mean_low_threshold")
    x_values = [value[3] for value in plotted]
    x_values.extend(
        value for value in (high_threshold, low_threshold) if value is not None
    )
    x_minimum, x_maximum = _bounds(x_values)
    y_minimum, y_maximum = -0.1, 1.1
    lines = _svg_header(
        view,
        "Rising and falling state observations, adjacent exported transition brackets, and finalized threshold metrics.",
    )
    lines.extend(
        _axes(
            x_minimum,
            x_maximum,
            y_minimum,
            y_maximum,
            f"Input ({_unit(view, 'input')})",
            "State (0 or 1)",
        )
    )
    groups: dict[tuple[int, str], list[tuple[ReportPointView, float, float]]] = {}
    for point, cycle, direction, input_value, state_value in plotted:
        groups.setdefault((cycle, direction), []).append(
            (point, input_value, state_value)
        )
    for values in groups.values():
        for previous, current in pairwise(values):
            if previous[2] == current[2]:
                continue
            start = _x(previous[1], x_minimum, x_maximum)
            end = _x(current[1], x_minimum, x_maximum)
            left = min(start, end)
            width = max(abs(end - start), 1.0)
            lines.append(
                f'<rect x="{left:.2f}" y="{_TOP:.2f}" width="{width:.2f}" '
                f'height="{_BOTTOM - _TOP:.2f}" fill="#fef3c7" opacity="0.55"/>'
            )
    for threshold, label, color, metric_name, label_y in (
        (
            high_threshold,
            "Final mean high threshold",
            "#047857",
            "mean_high_threshold",
            _TOP + 48,
        ),
        (
            low_threshold,
            "Final mean low threshold",
            "#9f1239",
            "mean_low_threshold",
            _TOP + 66,
        ),
    ):
        if threshold is None:
            continue
        x_coord = _x(threshold, x_minimum, x_maximum)
        lines.append(
            f'<line x1="{x_coord:.2f}" y1="{_TOP:.2f}" x2="{x_coord:.2f}" '
            f'y2="{_BOTTOM:.2f}" stroke="{color}" stroke-width="2" stroke-dasharray="6 4"/>'
        )
        lines.append(
            _svg_text(
                x_coord + 5,
                label_y,
                f"{label}: {format(threshold, '.6g')} {_unit(view, metric_name, metric=True)}",
                fill=color,
                **{"font-size": "11"},
            )
        )
    for (cycle, direction), values in groups.items():
        color = "#2563eb" if direction == "RISING" else "#7c3aed"
        coordinates = " ".join(
            f"{_x(input_value, x_minimum, x_maximum):.2f},{_y(state_value, y_minimum, y_maximum):.2f}"
            for _, input_value, state_value in values
        )
        if coordinates:
            lines.append(
                f'<polyline points="{coordinates}" fill="none" stroke="{color}" '
                f'stroke-width="2" data-cycle="{cycle}" data-direction="{direction}"/>'
            )
        for point, input_value, state_value in values:
            x_coord = _x(input_value, x_minimum, x_maximum)
            y_coord = _y(state_value, y_minimum, y_maximum)
            if point.disposition == "INCLUDED":
                lines.append(
                    f'<circle cx="{x_coord:.2f}" cy="{y_coord:.2f}" r="4" fill="{color}"/>'
                )
            else:
                lines.append(_point_marker(point, x_coord, y_coord))
    if not plotted:
        lines.append(
            _svg_text(
                500,
                250,
                "No finite plottable hysteresis points are present in this result.",
                fill="#7c2d12",
                **{"font-size": "15", "text-anchor": "middle"},
            )
        )
    lines.extend(
        (
            '<line x1="650" y1="92" x2="670" y2="92" stroke="#2563eb" stroke-width="3"/>',
            _svg_text(
                676, 96, "Rising direction", fill="#0f172a", **{"font-size": "11"}
            ),
            '<line x1="780" y1="92" x2="800" y2="92" stroke="#7c3aed" stroke-width="3"/>',
            _svg_text(
                806, 96, "Falling direction", fill="#0f172a", **{"font-size": "11"}
            ),
            '<rect x="650" y="104" width="20" height="10" fill="#fef3c7" stroke="#d97706"/>',
            _svg_text(
                676,
                113,
                "Adjacent exported transition bracket",
                fill="#0f172a",
                **{"font-size": "11"},
            ),
        )
    )
    lines.extend(_svg_footer(view))
    return "\n".join(lines) + "\n"


def _render_empty_svg(view: HumanReportView) -> str:
    lines = _svg_header(
        view,
        "No chart contract exists for the source schemas in this finalized result.",
    )
    lines.append(
        _svg_text(
            500,
            250,
            "No supported chart is defined for this result type.",
            fill="#475569",
            **{"font-size": "16", "text-anchor": "middle"},
        )
    )
    lines.extend(_svg_footer(view))
    return "\n".join(lines) + "\n"


def render_human_report_svg(view: HumanReportView) -> str:
    """Render one deterministic SVG without remote resources or scripts."""

    if not isinstance(view, HumanReportView):
        raise ProductReportFormatError("view must be a HumanReportView")
    if view.chart_kind is ReportChartKind.DC_SWEEP:
        return _render_dc_svg(view)
    if view.chart_kind is ReportChartKind.HYSTERESIS:
        return _render_hysteresis_svg(view)
    return _render_empty_svg(view)


def _point_values(point: ReportPointView) -> str:
    return "; ".join(f"{value.name}={_format_value(value)}" for value in point.values)


def _point_records(point: ReportPointView) -> str:
    return ", ".join(reference.record_id for reference in point.references)


def _point_notes(point: ReportPointView) -> str:
    values = (*point.quality_flags, *point.exclusion_reasons)
    return "none" if not values else "; ".join(values)


def render_human_report_text(view: HumanReportView) -> str:
    """Render a plain-text report with textual status independent of color."""

    if not isinstance(view, HumanReportView):
        raise ProductReportFormatError("view must be a HumanReportView")
    lines = [
        "ANALOG VALIDATION STUDIO",
        view.title.upper(),
        "=" * 72,
        f"OUTCOME: {view.outcome.value}",
        f"EVIDENCE SOURCE: {view.evidence_source.value}",
        f"HARDWARE CLAIM: {REPORT_HARDWARE_CLAIM}",
        f"SUMMARY: {view.summary}",
        "",
        "IDENTITY AND REPRODUCIBILITY",
        f"Report schema: {view.schema_version}",
        f"Generator version: {view.generator_version}",
        f"Input result schema: {view.input_schema_version}",
        f"Canonical result SHA-256: {view.canonical_result_sha256}",
        f"Run ID: {view.run_id}",
        f"Test type: {view.test_type}",
        f"Configuration: {view.configuration_id}/{view.configuration_version}",
        f"Input software version: {view.input_software_version}",
        f"Device ID: {view.device_id}",
        f"Profile: {view.profile_name}/{view.profile_version}",
        f"Started UTC: {view.started_at}",
        f"Ended UTC: {view.ended_at}",
        "",
        "SOURCE SCHEMAS",
        *(f"- {schema.name}: {schema.version}" for schema in view.source_schemas),
        "",
        "FINALIZED METRICS",
        *(f"- {value.name}: {_format_value(value)}" for value in view.metrics),
        "",
        "FINALIZED CRITERIA",
    ]
    if view.criterion_results:
        lines.extend(
            f"- {criterion.name}: {_format_scalar(criterion.actual_value)} {criterion.unit}; limits {_criterion_range(criterion)}; {'PASS' if criterion.passed else 'FAIL'}"
            for criterion in view.criterion_results
        )
    else:
        lines.append("- none")
    lines.extend(("", "LIMITATIONS"))
    lines.extend(f"- {value}" for value in view.limitations)
    lines.extend(("", "NOT VERIFIED"))
    lines.extend(f"- {value}" for value in view.not_verified)
    lines.extend(("", "MISSING REQUIREMENTS"))
    lines.extend(
        (f"- {value}" for value in view.missing_requirements)
        if view.missing_requirements
        else ("- none",)
    )
    lines.extend(("", "TRACEABLE POINTS"))
    if view.points:
        lines.extend(
            f"- [{point.index}] {point.label} | {point.disposition} | {_point_values(point)} | records={_point_records(point)} | notes={_point_notes(point)}"
            for point in view.points
        )
    else:
        lines.append("- none")
    lines.extend(
        (
            "",
            "Generated artifact hashes are recorded in manifest.json.",
            "This presentation copied finalized values and did not recompute the engineering outcome.",
        )
    )
    return "\n".join(lines) + "\n"


def render_human_report_markdown(view: HumanReportView) -> str:
    """Render deterministic Markdown with escaped untrusted result text."""

    if not isinstance(view, HumanReportView):
        raise ProductReportFormatError("view must be a HumanReportView")
    lines = [
        f"# {_markdown(view.title)}",
        "",
        f"> **Outcome: {_markdown(view.outcome.value)}**  ",
        f"> **Evidence source: {_markdown(view.evidence_source.value)}**  ",
        f"> **Hardware claim: {REPORT_HARDWARE_CLAIM}**",
        "",
        _markdown(view.summary),
        "",
        "## Identity and reproducibility",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Report schema | `{_markdown(view.schema_version)}` |",
        f"| Generator version | `{_markdown(view.generator_version)}` |",
        f"| Input result schema | `{_markdown(view.input_schema_version)}` |",
        f"| Canonical result SHA-256 | `{view.canonical_result_sha256}` |",
        f"| Run ID | `{_markdown(view.run_id)}` |",
        f"| Test type | {_markdown(view.test_type)} |",
        f"| Configuration | `{_markdown(view.configuration_id)}/{_markdown(view.configuration_version)}` |",
        f"| Input software version | `{_markdown(view.input_software_version)}` |",
        f"| Device ID | `{_markdown(view.device_id)}` |",
        f"| Profile | `{_markdown(view.profile_name)}/{_markdown(view.profile_version)}` |",
        f"| Started UTC | `{_markdown(view.started_at)}` |",
        f"| Ended UTC | `{_markdown(view.ended_at)}` |",
        "",
        "## Source schemas",
        "",
        *(
            f"- `{_markdown(schema.name)}`: `{_markdown(schema.version)}`"
            for schema in view.source_schemas
        ),
        "",
        "## Finalized metrics",
        "",
        "| Metric | Value | Unit |",
        "|---|---:|---|",
        *(
            f"| {_markdown(value.name)} | {_markdown(_format_scalar(value.value))} | {_markdown(value.unit)} |"
            for value in view.metrics
        ),
        "",
        "## Finalized criteria",
        "",
        "| Criterion | Actual | Limits | Status |",
        "|---|---:|---|---|",
    ]
    if view.criterion_results:
        lines.extend(
            f"| {_markdown(criterion.name)} | {_markdown(_format_scalar(criterion.actual_value))} {_markdown(criterion.unit)} | {_markdown(_criterion_range(criterion))} | {'PASS' if criterion.passed else 'FAIL'} |"
            for criterion in view.criterion_results
        )
    else:
        lines.append("| none | — | — | NOT EVALUATED |")
    lines.extend(("", "## Evidence boundary", "", "### Limitations", ""))
    lines.extend(f"- {_markdown(value)}" for value in view.limitations)
    lines.extend(("", "### Not verified", ""))
    lines.extend(f"- {_markdown(value)}" for value in view.not_verified)
    lines.extend(("", "### Missing requirements", ""))
    lines.extend(
        (f"- {_markdown(value)}" for value in view.missing_requirements)
        if view.missing_requirements
        else ("- none",)
    )
    lines.extend(
        (
            "",
            "## Chart",
            "",
            "The self-contained HTML embeds the same deterministic SVG stored as `chart.svg`.",
            "",
            "## Traceable points",
            "",
            "| Index | Label | Disposition | Finalized values | Record IDs | Quality / exclusion |",
            "|---:|---|---|---|---|---|",
        )
    )
    if view.points:
        lines.extend(
            f"| {point.index} | {_markdown(point.label)} | {_markdown(point.disposition)} | {_markdown(_point_values(point))} | {_markdown(_point_records(point))} | {_markdown(_point_notes(point))} |"
            for point in view.points
        )
    else:
        lines.append("| — | none | — | — | — | — |")
    lines.extend(
        (
            "",
            "Generated artifact hashes are recorded in `manifest.json`.",
            "",
            "This presentation copied finalized values and did not recompute the engineering outcome.",
        )
    )
    return "\n".join(lines) + "\n"


def _html_table(headers: tuple[str, ...], rows: Iterable[tuple[str, ...]]) -> str:
    head = "".join(f'<th scope="col">{_html(value)}</th>' for value in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{_html(value)}</td>" for value in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_human_report_html(view: HumanReportView, svg: str | None = None) -> str:
    """Render self-contained UTF-8 HTML with inline CSS and embedded SVG."""

    if not isinstance(view, HumanReportView):
        raise ProductReportFormatError("view must be a HumanReportView")
    expected_svg = render_human_report_svg(view)
    if svg is not None and (not isinstance(svg, str) or svg != expected_svg):
        raise ProductReportFormatError("svg must be a rendered SVG document")
    selected_svg = expected_svg
    status_class = f"status-{view.outcome.value.lower()}"
    metadata = _html_table(
        ("Field", "Value"),
        (
            ("Report schema", view.schema_version),
            ("Generator version", view.generator_version),
            ("Input result schema", view.input_schema_version),
            ("Canonical result SHA-256", view.canonical_result_sha256),
            ("Run ID", view.run_id),
            ("Test type", view.test_type),
            ("Configuration", f"{view.configuration_id}/{view.configuration_version}"),
            ("Input software version", view.input_software_version),
            ("Device ID", view.device_id),
            ("Profile", f"{view.profile_name}/{view.profile_version}"),
            ("Started UTC", view.started_at),
            ("Ended UTC", view.ended_at),
        ),
    )
    schemas = _html_table(
        ("Schema", "Version"),
        ((value.name, value.version) for value in view.source_schemas),
    )
    metrics = _html_table(
        ("Metric", "Value", "Unit"),
        (
            (value.name, _format_scalar(value.value), value.unit)
            for value in view.metrics
        ),
    )
    criteria = _html_table(
        ("Criterion", "Actual", "Limits", "Status"),
        (
            (
                value.name,
                f"{_format_scalar(value.actual_value)} {value.unit}",
                _criterion_range(value),
                "PASS" if value.passed else "FAIL",
            )
            for value in view.criterion_results
        )
        if view.criterion_results
        else (("none", "not evaluated", "none", "NOT EVALUATED"),),
    )
    points = _html_table(
        (
            "Index",
            "Label",
            "Disposition",
            "Finalized values",
            "Record IDs",
            "Quality / exclusion",
        ),
        (
            (
                str(point.index),
                point.label,
                point.disposition,
                _point_values(point),
                _point_records(point),
                _point_notes(point),
            )
            for point in view.points
        )
        if view.points
        else (("—", "none", "—", "—", "—", "—"),),
    )
    limitations = "".join(f"<li>{_html(value)}</li>" for value in view.limitations)
    not_verified = "".join(f"<li>{_html(value)}</li>" for value in view.not_verified)
    missing = (
        "".join(f"<li>{_html(value)}</li>" for value in view.missing_requirements)
        if view.missing_requirements
        else "<li>none</li>"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html(view.title)}</title>
<style>
:root {{ color-scheme: light; font-family: system-ui, sans-serif; color: #0f172a; background: #f8fafc; }}
body {{ margin: 0; }} main {{ max-width: 1100px; margin: 0 auto; padding: 2rem; }}
.card {{ background: white; border: 1px solid #cbd5e1; border-radius: .75rem; padding: 1.25rem; margin: 1rem 0; overflow-x: auto; }}
.status {{ display: inline-block; padding: .35rem .7rem; border: 2px solid currentColor; border-radius: .4rem; font-weight: 800; }}
.status-pass {{ color: #166534; }} .status-fail, .status-error {{ color: #991b1b; }}
.status-incomplete, .status-unsupported, .status-aborted {{ color: #92400e; }}
table {{ border-collapse: collapse; width: 100%; }} th, td {{ border: 1px solid #cbd5e1; padding: .5rem; text-align: left; vertical-align: top; }}
th {{ background: #e2e8f0; }} code {{ overflow-wrap: anywhere; }} svg {{ width: 100%; height: auto; }}
.boundary {{ border-left: .4rem solid #b45309; }}
</style>
</head>
<body>
<main>
<header class="card">
<p>Analog Validation Studio</p>
<h1>{_html(view.title)}</h1>
<p class="status {_html(status_class)}">Outcome: {_html(view.outcome.value)}</p>
<p><strong>Evidence source:</strong> {_html(view.evidence_source.value)}</p>
<p><strong>Hardware claim:</strong> {REPORT_HARDWARE_CLAIM}</p>
<p>{_html(view.summary)}</p>
</header>
<section class="card"><h2>Identity and reproducibility</h2>{metadata}</section>
<section class="card"><h2>Source schemas</h2>{schemas}</section>
<section class="card"><h2>Finalized metrics</h2>{metrics}</section>
<section class="card"><h2>Finalized criteria</h2>{criteria}</section>
<section class="card boundary">
<h2>Evidence boundary</h2>
<h3>Limitations</h3><ul>{limitations}</ul>
<h3>Not verified</h3><ul>{not_verified}</ul>
<h3>Missing requirements</h3><ul>{missing}</ul>
</section>
<section class="card"><h2>Deterministic chart</h2>{selected_svg}</section>
<section class="card"><h2>Traceable points</h2>{points}</section>
<footer class="card">
<p>Generated artifact hashes are recorded in <code>manifest.json</code>.</p>
<p>This presentation copied finalized values and did not recompute the engineering outcome.</p>
</footer>
</main>
</body>
</html>
"""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@dataclass(frozen=True, slots=True)
class ReportArtifact:
    """One fixed-name local report artifact with content identity."""

    name: str
    media_type: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or Path(self.name).name != self.name:
            raise ProductReportFormatError("artifact name must be one local filename")
        if not isinstance(self.media_type, str) or not self.media_type:
            raise ProductReportFormatError("artifact media_type cannot be empty")
        if (
            isinstance(self.size_bytes, bool)
            or not isinstance(self.size_bytes, int)
            or self.size_bytes < 0
        ):
            raise ProductReportFormatError("artifact size_bytes must be non-negative")
        if (
            not isinstance(self.sha256, str)
            or len(self.sha256) != 64
            or any(value not in "0123456789abcdef" for value in self.sha256)
        ):
            raise ProductReportFormatError("artifact sha256 must have 64 hex digits")


@dataclass(frozen=True, slots=True)
class HumanReportPublication:
    """Atomically published report directory and its exact artifacts."""

    output_directory: Path
    artifacts: tuple[ReportArtifact, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.output_directory, Path):
            raise ProductReportFormatError("output_directory must be a Path")
        if not isinstance(self.artifacts, tuple) or not self.artifacts:
            raise ProductReportFormatError("artifacts must be a non-empty tuple")
        if not all(isinstance(value, ReportArtifact) for value in self.artifacts):
            raise ProductReportFormatError("artifacts contains an invalid value")
        if len({value.name for value in self.artifacts}) != len(self.artifacts):
            raise ProductReportFormatError("artifact names cannot repeat")

    def artifact(self, name: str) -> ReportArtifact:
        """Return one exact artifact descriptor."""

        selected = next((value for value in self.artifacts if value.name == name), None)
        if selected is None:
            raise ProductReportFormatError(f"report artifact is absent: {name}")
        return selected


def _artifact(name: str, media_type: str, payload: bytes) -> ReportArtifact:
    return ReportArtifact(name, media_type, len(payload), _sha256_bytes(payload))


def _manifest(view: HumanReportView, artifacts: tuple[ReportArtifact, ...]) -> str:
    document = {
        "schema_version": HUMAN_REPORT_MANIFEST_SCHEMA_VERSION,
        "report_schema_version": HUMAN_REPORT_SCHEMA_VERSION,
        "canonical_result_sha256": view.canonical_result_sha256,
        "run_id": view.run_id,
        "outcome": view.outcome.value,
        "evidence_source": view.evidence_source.value,
        "hardware_claim": REPORT_HARDWARE_CLAIM,
        "artifacts": [
            {
                "name": artifact.name,
                "media_type": artifact.media_type,
                "size_bytes": artifact.size_bytes,
                "sha256": artifact.sha256,
            }
            for artifact in artifacts
        ],
    }
    return json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _output_path(value: str | PathLike[str]) -> Path:
    if not isinstance(value, (str, PathLike)):
        raise ProductReportPathError(
            "report output must be a string or path-like value"
        )
    try:
        path = Path(value)
    except (TypeError, ValueError, OSError) as error:
        raise ProductReportPathError("report output path is invalid") from error
    if not path.name:
        raise ProductReportPathError("report output must identify a new directory")
    return path


def _write_staging_file(path: Path, payload: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _cleanup_staging(path: Path) -> None:
    try:
        if path.exists():
            for child in path.iterdir():
                if child.is_file() or child.is_symlink():
                    child.unlink(missing_ok=True)
            path.rmdir()
    except OSError:
        pass


def publish_human_report(
    output_directory: str | PathLike[str],
    view: HumanReportView,
) -> HumanReportPublication:
    """Render in memory and atomically publish one create-new report directory."""

    if not isinstance(view, HumanReportView):
        raise ProductReportFormatError("view must be a HumanReportView")
    destination = _output_path(output_directory)
    parent = destination.parent
    try:
        if not parent.exists() or not parent.is_dir():
            raise ProductReportPathError(
                "report output parent must be an existing directory"
            )
        if destination.exists() or destination.is_symlink():
            raise ProductReportExistsError("report output already exists")
    except (ProductReportPathError, ProductReportExistsError):
        raise
    except OSError as error:
        raise ProductReportPathError("report output cannot be prepared") from error

    svg = render_human_report_svg(view)
    rendered = (
        (
            REPORT_TEXT_FILENAME,
            "text/plain; charset=utf-8",
            render_human_report_text(view),
        ),
        (
            REPORT_MARKDOWN_FILENAME,
            "text/markdown; charset=utf-8",
            render_human_report_markdown(view),
        ),
        (
            REPORT_HTML_FILENAME,
            "text/html; charset=utf-8",
            render_human_report_html(view, svg),
        ),
        (REPORT_SVG_FILENAME, "image/svg+xml; charset=utf-8", svg),
    )
    payloads = tuple(
        (name, media_type, content.encode("utf-8"))
        for name, media_type, content in rendered
    )
    artifacts = tuple(
        _artifact(name, media_type, payload) for name, media_type, payload in payloads
    )
    manifest_payload = _manifest(view, artifacts).encode("utf-8")
    manifest_artifact = _artifact(
        REPORT_MANIFEST_FILENAME,
        "application/json; charset=utf-8",
        manifest_payload,
    )

    staging: Path | None = None
    try:
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{destination.name}.",
                suffix=".tmp",
                dir=parent,
            )
        )
        for name, _, payload in payloads:
            _write_staging_file(staging / name, payload)
        _write_staging_file(staging / REPORT_MANIFEST_FILENAME, manifest_payload)
        os.rename(staging, destination)
        staging = None
    except FileExistsError as error:
        raise ProductReportExistsError("report output already exists") from error
    except OSError as error:
        raise ProductReportPathError("report output could not be published") from error
    finally:
        if staging is not None:
            _cleanup_staging(staging)
    return HumanReportPublication(
        destination.resolve(),
        (*artifacts, manifest_artifact),
    )


__all__ = [
    "HUMAN_REPORT_MANIFEST_SCHEMA_VERSION",
    "REPORT_HTML_FILENAME",
    "REPORT_MANIFEST_FILENAME",
    "REPORT_MARKDOWN_FILENAME",
    "REPORT_SVG_FILENAME",
    "REPORT_TEXT_FILENAME",
    "HumanReportPublication",
    "ReportArtifact",
    "publish_human_report",
    "render_human_report_html",
    "render_human_report_markdown",
    "render_human_report_svg",
    "render_human_report_text",
]
