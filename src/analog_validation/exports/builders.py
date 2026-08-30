"""Typed builders from finalized analyses to controller-neutral export bundles."""

from __future__ import annotations

from collections.abc import Iterable

from analog_validation.analysis import (
    ANALYSIS_COMMON_SCHEMA_VERSION,
    DC_SWEEP_ANALYSIS_SCHEMA_VERSION,
    DC_SWEEP_CRITERIA_SCHEMA_VERSION,
    DC_SWEEP_EVALUATION_SCHEMA_VERSION,
    HYSTERESIS_ANALYSIS_SCHEMA_VERSION,
    HYSTERESIS_CRITERIA_SCHEMA_VERSION,
    HYSTERESIS_EVALUATION_SCHEMA_VERSION,
    DCSweepCriterionResult,
    DCSweepEvaluationResult,
    HysteresisCriterionResult,
    HysteresisEvaluationResult,
    HysteresisPointResult,
    MeasurementDecision,
    PointDisposition,
)
from analog_validation.domain import (
    TEST_RUN_SCHEMA_VERSION,
    MeasurementStatus,
)
from analog_validation.errors import ValidationError

from .models import (
    ExportCriterion,
    ExportPoint,
    ExportSchemaReference,
    ExportValue,
    ResultExportBundle,
)


def _limitations(values: Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ValidationError("limitations must be an iterable")
    return tuple(values)


def _schemas(*values: tuple[str, str]) -> tuple[ExportSchemaReference, ...]:
    return tuple(ExportSchemaReference(name, version) for name, version in values)


def _quality_flags(prefix: str, decision: MeasurementDecision) -> tuple[str, ...]:
    return tuple(
        f"{prefix}:{flag.value}"
        for flag in sorted(decision.observed_quality_flags, key=lambda item: item.value)
    )


def _decision_reasons(
    prefix: str, decision: MeasurementDecision
) -> tuple[str, ...]:
    return tuple(f"{prefix}:{reason.value}" for reason in decision.exclusion_reasons)


def _criterion(
    value: DCSweepCriterionResult | HysteresisCriterionResult,
) -> ExportCriterion:
    return ExportCriterion(
        name=value.criterion.value,
        actual_value=value.actual_value,
        unit=value.unit,
        passed=value.passed,
        lower_limit=value.lower_limit,
        upper_limit=value.upper_limit,
    )


def build_dc_sweep_export(
    evaluation: DCSweepEvaluationResult,
    limitations: Iterable[str],
) -> ResultExportBundle:
    """Freeze one evaluated DC sweep without recalculating its fit or criteria."""

    if not isinstance(evaluation, DCSweepEvaluationResult):
        raise ValidationError("evaluation must be a DCSweepEvaluationResult")
    analysis = evaluation.analysis
    unit = analysis.config.normalized_unit.value
    metrics = [
        ExportValue("included_points", analysis.included_points, "points"),
        ExportValue("excluded_points", analysis.excluded_points, "points"),
        ExportValue("invalid_points", analysis.invalid_points, "points"),
    ]
    if analysis.fit is not None:
        metrics.extend(
            (
                ExportValue("gain", analysis.fit.gain, "ratio"),
                ExportValue("offset", analysis.fit.offset, unit),
                ExportValue("r_squared", analysis.fit.r_squared, "ratio"),
                ExportValue("rmse", analysis.fit.rmse, unit),
                ExportValue(
                    "max_abs_residual", analysis.fit.max_abs_residual, unit
                ),
                ExportValue("fit_used_points", analysis.fit.used_points, "points"),
            )
        )

    points: list[ExportPoint] = []
    for point in analysis.points:
        values = [
            ExportValue("input", point.input_decision.normalized_value, unit),
            ExportValue("output", point.output_decision.normalized_value, unit),
        ]
        if point.predicted_output is not None:
            values.extend(
                (
                    ExportValue("predicted_output", point.predicted_output, unit),
                    ExportValue("residual", point.residual, unit),
                )
            )
        reasons = (
            *(f"point:{reason.value}" for reason in point.exclusion_reasons),
            *_decision_reasons("input", point.input_decision),
            *_decision_reasons("output", point.output_decision),
        )
        points.append(
            ExportPoint(
                index=point.sequence,
                label=f"dc-point-{point.sequence}",
                disposition=point.disposition,
                references=(
                    point.input_decision.reference,
                    point.output_decision.reference,
                ),
                values=tuple(values),
                quality_flags=(
                    *_quality_flags("input", point.input_decision),
                    *_quality_flags("output", point.output_decision),
                ),
                exclusion_reasons=tuple(dict.fromkeys(reasons)),
            )
        )

    schema_values = [
        ("analysis-common", ANALYSIS_COMMON_SCHEMA_VERSION),
        ("test-run", TEST_RUN_SCHEMA_VERSION),
        ("dc-sweep-analysis", DC_SWEEP_ANALYSIS_SCHEMA_VERSION),
        ("dc-sweep-evaluation", DC_SWEEP_EVALUATION_SCHEMA_VERSION),
    ]
    criteria_id = None
    criteria_version = None
    if evaluation.criteria is not None:
        schema_values.append(
            ("dc-sweep-criteria", DC_SWEEP_CRITERIA_SCHEMA_VERSION)
        )
        criteria_id = evaluation.criteria.criteria_id
        criteria_version = evaluation.criteria.criteria_version
    return ResultExportBundle(
        test_run_result=evaluation.test_run_result,
        source_schemas=_schemas(*schema_values),
        metrics=tuple(metrics),
        points=tuple(points),
        limitations=_limitations(limitations),
        criteria_id=criteria_id,
        criteria_version=criteria_version,
        criterion_results=tuple(_criterion(value) for value in evaluation.criterion_results),
    )


def _hysteresis_disposition(point: HysteresisPointResult) -> PointDisposition:
    if point.included:
        return PointDisposition.INCLUDED
    if (
        point.input_decision.disposition is PointDisposition.INVALID
        or point.state_status is MeasurementStatus.INVALID
    ):
        return PointDisposition.INVALID
    return PointDisposition.EXCLUDED


def build_hysteresis_export(
    evaluation: HysteresisEvaluationResult,
    limitations: Iterable[str],
) -> ResultExportBundle:
    """Freeze one evaluated hysteresis run without recomputing transitions."""

    if not isinstance(evaluation, HysteresisEvaluationResult):
        raise ValidationError("evaluation must be a HysteresisEvaluationResult")
    analysis = evaluation.analysis
    unit = analysis.config.normalized_unit.value
    points: list[ExportPoint] = []
    for cycle in analysis.cycles:
        for point in cycle.rising_points + cycle.falling_points:
            reasons = (
                *point.exclusion_reasons,
                *_decision_reasons("input", point.input_decision),
            )
            points.append(
                ExportPoint(
                    index=len(points),
                    label=(
                        f"cycle-{cycle.cycle_index}-{point.direction.value.lower()}-"
                        f"point-{point.sequence}"
                    ),
                    disposition=_hysteresis_disposition(point),
                    references=(
                        point.input_decision.reference,
                        point.state_reference,
                    ),
                    values=(
                        ExportValue("cycle_index", cycle.cycle_index, "index"),
                        ExportValue("direction", point.direction.value, "enum"),
                        ExportValue(
                            "input", point.input_decision.normalized_value, unit
                        ),
                        ExportValue("state", point.state_value, "bool"),
                    ),
                    quality_flags=(
                        *_quality_flags("input", point.input_decision),
                        *(
                            f"state:{flag.value}"
                            for flag in sorted(
                                point.state_quality_flags,
                                key=lambda item: item.value,
                            )
                        ),
                    ),
                    exclusion_reasons=tuple(dict.fromkeys(reasons)),
                )
            )

    counts = {
        disposition: sum(point.disposition is disposition for point in points)
        for disposition in PointDisposition
    }
    metrics = [
        ExportValue("included_points", counts[PointDisposition.INCLUDED], "points"),
        ExportValue("excluded_points", counts[PointDisposition.EXCLUDED], "points"),
        ExportValue("invalid_points", counts[PointDisposition.INVALID], "points"),
    ]
    if analysis.summary is not None:
        metrics.extend(
            (
                ExportValue("complete_cycles", analysis.summary.cycle_count, "cycles"),
                ExportValue(
                    "mean_high_threshold", analysis.summary.mean_high_threshold, unit
                ),
                ExportValue(
                    "mean_low_threshold", analysis.summary.mean_low_threshold, unit
                ),
                ExportValue("mean_width", analysis.summary.mean_width, unit),
                ExportValue("minimum_width", analysis.summary.minimum_width, unit),
                ExportValue("maximum_width", analysis.summary.maximum_width, unit),
                ExportValue("width_span", analysis.summary.width_span, unit),
            )
        )

    schema_values = [
        ("analysis-common", ANALYSIS_COMMON_SCHEMA_VERSION),
        ("test-run", TEST_RUN_SCHEMA_VERSION),
        ("hysteresis-analysis", HYSTERESIS_ANALYSIS_SCHEMA_VERSION),
        ("hysteresis-evaluation", HYSTERESIS_EVALUATION_SCHEMA_VERSION),
    ]
    criteria_id = None
    criteria_version = None
    if evaluation.criteria is not None:
        schema_values.append(
            ("hysteresis-criteria", HYSTERESIS_CRITERIA_SCHEMA_VERSION)
        )
        criteria_id = evaluation.criteria.criteria_id
        criteria_version = evaluation.criteria.criteria_version
    return ResultExportBundle(
        test_run_result=evaluation.test_run_result,
        source_schemas=_schemas(*schema_values),
        metrics=tuple(metrics),
        points=tuple(points),
        limitations=_limitations(limitations),
        criteria_id=criteria_id,
        criteria_version=criteria_version,
        criterion_results=tuple(_criterion(value) for value in evaluation.criterion_results),
    )


__all__ = ["build_dc_sweep_export", "build_hysteresis_export"]
