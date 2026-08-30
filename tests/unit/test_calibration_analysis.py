"""Tests for versioned linear calibration and immutable derived records."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from analog_validation.analysis import (
    CALIBRATION_ANALYSIS_SCHEMA_VERSION,
    CALIBRATION_METHOD,
    AnalysisQualityPolicy,
    CalibrationApplicationConfig,
    CalibrationApplicationResult,
    CalibrationAppliedPoint,
    CalibrationErrorMetrics,
    CalibrationFitConfig,
    CalibrationFitResult,
    CalibrationPointExclusionReason,
    CalibrationPointResult,
    MeasurementBatch,
    PointDisposition,
    apply_linear_calibration,
    assess_voltage_measurement,
    fit_linear_calibration,
)
from analog_validation.domain import (
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
    QualityFlag,
)
from analog_validation.errors import ValidationError

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def measurement(
    record_id: str,
    channel: str,
    value: float | None,
    *,
    unit: MeasurementUnit = MeasurementUnit.MILLIVOLT,
    source: EvidenceSource = EvidenceSource.SYNTHETIC,
    status: MeasurementStatus = MeasurementStatus.VALID,
    flags: frozenset[QualityFlag] = frozenset(),
    raw_record_id: str | None = None,
    sequence: int = 0,
) -> Measurement:
    return Measurement(
        record_id,
        raw_record_id or f"raw-{record_id}",
        NOW + timedelta(milliseconds=sequence),
        channel,
        value,
        unit,
        status,
        source,
        flags,
    )


def batch(
    prefix: str,
    channel: str,
    values: list[float | None],
    *,
    units: list[MeasurementUnit] | None = None,
    source: EvidenceSource = EvidenceSource.SYNTHETIC,
) -> MeasurementBatch:
    units = units or [MeasurementUnit.MILLIVOLT] * len(values)
    return MeasurementBatch(
        tuple(
            measurement(
                f"{prefix}-{index}",
                channel,
                value,
                unit=unit,
                source=source,
                sequence=index,
            )
            for index, (value, unit) in enumerate(zip(values, units, strict=True))
        )
    )


def fit_config(**overrides: Any) -> CalibrationFitConfig:
    values: dict[str, Any] = {
        "observed_channel": "observed",
        "reference_channel": "reference",
        "coefficient_id": "adc-linear",
        "coefficient_version": "1",
    }
    values.update(overrides)
    return CalibrationFitConfig(**values)


def unsafe_replace(instance: Any, **changes: Any) -> Any:
    """Exercise runtime dataclass guards with deliberately invalid types."""

    return replace(instance, **changes)


def complete_fit() -> CalibrationFitResult:
    return fit_linear_calibration(
        batch("o", "observed", [0, 50, 100]),
        batch(
            "r",
            "reference",
            [10, 110, 210],
            source=EvidenceSource.HOST_TEST,
        ),
        fit_config(),
    )


def test_fit_recovers_linear_coefficients_metrics_and_lineage() -> None:
    result = complete_fit()
    assert result.schema_version == CALIBRATION_ANALYSIS_SCHEMA_VERSION
    assert result.is_complete
    assert result.included_points == 3
    assert result.observed_source is EvidenceSource.SYNTHETIC
    assert result.reference_source is EvidenceSource.HOST_TEST
    coefficients = result.coefficients
    assert coefficients is not None
    assert coefficients.method == CALIBRATION_METHOD
    assert coefficients.scale == pytest.approx(2)
    assert coefficients.offset == pytest.approx(10)
    assert coefficients.apply(25) == pytest.approx(60)
    assert coefficients.observed_record_ids == ("o-0", "o-1", "o-2")
    assert coefficients.reference_raw_record_ids == (
        "raw-r-0",
        "raw-r-1",
        "raw-r-2",
    )
    assert result.metrics is not None
    assert result.metrics.before_rmse == pytest.approx(
        math.sqrt((10**2 + 60**2 + 110**2) / 3)
    )
    assert result.metrics.after_rmse == pytest.approx(0)
    assert result.metrics.after_mean_absolute_error == pytest.approx(0)
    assert result.metrics.after_max_absolute_error == pytest.approx(0)
    assert [point.calibrated_value for point in result.points] == pytest.approx(
        [10, 110, 210]
    )
    assert [point.before_error for point in result.points] == pytest.approx(
        [-10, -60, -110]
    )
    assert [point.after_error for point in result.points] == pytest.approx([0, 0, 0])


def test_fit_normalizes_v_and_mv_before_fitting() -> None:
    observed = batch(
        "o",
        "observed",
        [0.0, 0.05, 100],
        units=[MeasurementUnit.VOLT, MeasurementUnit.VOLT, MeasurementUnit.MILLIVOLT],
    )
    result = fit_linear_calibration(
        observed,
        batch("r", "reference", [10, 110, 210]),
        fit_config(),
    )
    assert result.coefficients is not None
    assert result.coefficients.scale == pytest.approx(2)


def test_application_creates_new_records_and_preserves_original_evidence() -> None:
    coefficients = complete_fit().coefficients
    assert coefficients is not None
    original = batch("apply", "adc", [25, 50])
    snapshot = original.measurements
    result = apply_linear_calibration(
        original,
        coefficients,
        CalibrationApplicationConfig("adc", "adc.calibrated", "cal-v1"),
    )
    assert result.is_complete
    assert result.calibrated_points == 2
    assert original.measurements == snapshot
    derived = tuple(point.calibrated_measurement for point in result.points)
    assert [item.value for item in derived if item is not None] == pytest.approx(
        [60, 110]
    )
    assert [item.record_id for item in derived if item is not None] == [
        "cal-v1:0:apply-0",
        "cal-v1:1:apply-1",
    ]
    assert [item.raw_record_id for item in derived if item is not None] == [
        "raw-apply-0",
        "raw-apply-1",
    ]
    assert all(item.is_derived for item in derived if item is not None)
    assert all(item.source is EvidenceSource.SYNTHETIC for item in derived if item)
    assert [point.correction for point in result.points] == pytest.approx([35, 60])
    with pytest.raises(FrozenInstanceError):
        result.points[0].correction = 0  # type: ignore[misc]


def test_quality_exclusions_make_fit_and_application_explicitly_incomplete() -> None:
    observed = list(batch("o", "observed", [0, 50, 100]).measurements)
    observed[1] = measurement(
        "o-bad",
        "observed",
        50,
        status=MeasurementStatus.SUSPECT,
        flags=frozenset({QualityFlag.OUT_OF_RANGE}),
    )
    result = fit_linear_calibration(
        MeasurementBatch(tuple(observed)),
        batch("r", "reference", [10, 110, 210]),
        fit_config(),
    )
    assert not result.is_complete
    assert result.missing_requirements == ("included-points:2/3",)
    assert result.points[1].disposition is PointDisposition.EXCLUDED
    assert result.points[1].exclusion_reasons == (
        CalibrationPointExclusionReason.OBSERVED_NOT_INCLUDED,
    )

    coefficients = complete_fit().coefficients
    assert coefficients is not None
    applied = apply_linear_calibration(
        MeasurementBatch(tuple(observed)),
        coefficients,
        CalibrationApplicationConfig("observed", "calibrated", "cal"),
    )
    assert not applied.is_complete
    assert applied.missing_requirements == ("calibrated-points:2/3",)
    assert applied.points[1].calibrated_measurement is None


def test_fit_reports_insufficient_and_non_distinct_inputs_without_coefficients() -> (
    None
):
    too_few = fit_linear_calibration(
        batch("o", "observed", [0, 10]),
        batch("r", "reference", [0, 20]),
        fit_config(minimum_included_points=3),
    )
    assert too_few.missing_requirements == ("included-points:2/3",)
    constant = fit_linear_calibration(
        batch("o", "observed", [10, 10, 10]),
        batch("r", "reference", [1, 2, 3]),
        fit_config(),
    )
    assert constant.missing_requirements == ("distinct-observed-values:1/2",)


def test_fit_rejects_structural_mismatches_and_zero_derived_scale() -> None:
    observed = batch("o", "observed", [0, 1, 2])
    reference = batch("r", "reference", [0, 2, 4])
    with pytest.raises(ValidationError, match="equal lengths"):
        fit_linear_calibration(observed, batch("r", "reference", [0, 2]), fit_config())
    with pytest.raises(ValidationError, match="observed channel"):
        fit_linear_calibration(
            observed, reference, fit_config(observed_channel="wrong")
        )
    with pytest.raises(ValidationError, match="reference channel"):
        fit_linear_calibration(
            observed, reference, fit_config(reference_channel="wrong")
        )
    duplicate_cross_batch = MeasurementBatch(
        tuple(
            replace(item, record_id=f"o-{index}")
            for index, item in enumerate(reference.measurements)
        )
    )
    with pytest.raises(ValidationError, match="record IDs"):
        fit_linear_calibration(observed, duplicate_cross_batch, fit_config())
    with pytest.raises(ValidationError, match="scale"):
        fit_linear_calibration(
            observed,
            batch("r", "reference", [5, 5, 5]),
            fit_config(),
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"observed_channel": ""}, "non-empty"),
        ({"reference_channel": " reference"}, "non-empty"),
        ({"reference_channel": "observed"}, "distinct"),
        ({"normalized_unit": MeasurementUnit.HERTZ}, "V or mV"),
        ({"minimum_included_points": True}, "at least two"),
        ({"minimum_included_points": 1}, "at least two"),
        ({"quality_policy": "bad"}, "AnalysisQualityPolicy"),
        ({"schema_version": "bad"}, "unsupported"),
    ],
)
def test_fit_config_validation(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        fit_config(**overrides)


def test_coefficients_and_metrics_validation() -> None:
    coefficients = complete_fit().coefficients
    metrics = complete_fit().metrics
    assert coefficients is not None and metrics is not None
    invalid_coefficient_changes = (
        ("coefficient_id", ""),
        ("coefficient_version", " 1"),
        ("scale", True),
        ("scale", 0),
        ("offset", math.inf),
        ("unit", MeasurementUnit.HERTZ),
        ("observed_source", "bad"),
        ("observed_record_ids", "bad"),
        ("observed_record_ids", ("same", "same", "third")),
        ("observed_record_ids", ("only-one",)),
        ("method", "bad"),
        ("schema_version", "bad"),
    )
    for name, value in invalid_coefficient_changes:
        with pytest.raises(ValidationError):
            unsafe_replace(coefficients, **{name: value})
    with pytest.raises(ValidationError, match="numeric"):
        coefficients.apply(True)
    with pytest.raises(ValidationError, match="finite"):
        replace(coefficients, scale=1e308, offset=1e308).apply(2)

    invalid_metric_changes = (
        ("included_points", True),
        ("included_points", 1),
        ("before_rmse", "bad"),
        ("after_rmse", math.inf),
        ("before_mean_absolute_error", -1),
        ("unit", MeasurementUnit.HERTZ),
        ("schema_version", "bad"),
    )
    for name, value in invalid_metric_changes:
        with pytest.raises(ValidationError):
            unsafe_replace(metrics, **{name: value})


def test_point_and_result_models_reject_inconsistent_states() -> None:
    complete = complete_fit()
    point = complete.points[0]
    excluded_decision = assess_voltage_measurement(
        measurement(
            "suspect",
            "observed",
            1,
            status=MeasurementStatus.SUSPECT,
            flags=frozenset({QualityFlag.OUT_OF_RANGE}),
        )
    )
    volt_decision = assess_voltage_measurement(
        measurement("volt", "reference", 1, unit=MeasurementUnit.VOLT),
        target_unit=MeasurementUnit.VOLT,
    )
    for point_changes in (
        {"sequence": True},
        {"observed_decision": "bad"},
        {"reference_decision": "bad"},
        {"disposition": "bad"},
        {"exclusion_reasons": "bad"},
        {"exclusion_reasons": ("bad",)},
        {
            "exclusion_reasons": (
                CalibrationPointExclusionReason.OBSERVED_NOT_INCLUDED,
                CalibrationPointExclusionReason.OBSERVED_NOT_INCLUDED,
            )
        },
        {"exclusion_reasons": (CalibrationPointExclusionReason.OBSERVED_NOT_INCLUDED,)},
        {"calibrated_value": None},
        {"calibrated_value": math.inf},
        {"schema_version": "bad"},
        {"reference_decision": volt_decision},
        {"disposition": PointDisposition.EXCLUDED},
    ):
        with pytest.raises(ValidationError):
            unsafe_replace(point, **point_changes)
    excluded = CalibrationPointResult(
        0,
        excluded_decision,
        point.reference_decision,
        PointDisposition.EXCLUDED,
        (CalibrationPointExclusionReason.OBSERVED_NOT_INCLUDED,),
    )
    with pytest.raises(ValidationError, match="cannot have fitted"):
        replace(excluded, calibrated_value=1, before_error=1, after_error=1)

    assert complete.metrics is not None
    for result_changes in (
        {"config": "bad"},
        {"observed_source": "bad"},
        {"points": ()},
        {"points": ("bad",)},
        {"points": (replace(complete.points[0], sequence=2),)},
        {"missing_requirements": ("x", "x")},
        {"missing_requirements": ("x",)},
        {"coefficients": None},
        {"metrics": None},
        {"schema_version": "bad"},
        {"coefficients": "bad"},
        {"config": replace(complete.config, normalized_unit=MeasurementUnit.VOLT)},
        {"observed_source": EvidenceSource.HOST_TEST},
        {"metrics": replace(complete.metrics, included_points=2)},
    ):
        with pytest.raises(ValidationError):
            unsafe_replace(complete, **result_changes)
    with pytest.raises(ValidationError, match="partial outputs"):
        unsafe_replace(complete, metrics=None, missing_requirements=("missing",))


def test_application_models_and_function_validate_boundaries() -> None:
    fit = complete_fit()
    coefficients = fit.coefficients
    assert coefficients is not None
    config = CalibrationApplicationConfig("adc", "cal", "prefix")
    original = batch("a", "adc", [1, 2])
    result = apply_linear_calibration(original, coefficients, config)
    point = result.points[0]

    for config_changes in (
        {"input_channel": ""},
        {"output_channel": " cal"},
        {"output_channel": "adc"},
        {"quality_policy": "bad"},
        {"schema_version": "bad"},
    ):
        with pytest.raises(ValidationError):
            unsafe_replace(config, **config_changes)
    for point_changes in (
        {"sequence": True},
        {"original_decision": "bad"},
        {"coefficient_id": ""},
        {"coefficient_version": " 1"},
        {"calibrated_measurement": None},
        {"correction": None},
        {"correction": math.inf},
        {"schema_version": "bad"},
    ):
        with pytest.raises(ValidationError):
            unsafe_replace(point, **point_changes)
    assert point.calibrated_measurement is not None
    wrong_raw = replace(point.calibrated_measurement, raw_record_id="other")
    wrong_source = replace(
        point.calibrated_measurement, source=EvidenceSource.HOST_TEST
    )
    with pytest.raises(ValidationError, match="raw_record_id"):
        replace(point, calibrated_measurement=wrong_raw)
    with pytest.raises(ValidationError, match="evidence source"):
        replace(point, calibrated_measurement=wrong_source)

    for result_changes in (
        {"config": "bad"},
        {"coefficients": "bad"},
        {"evidence_source": "bad"},
        {"points": ()},
        {"points": ("bad",)},
        {"points": (replace(result.points[0], sequence=2),)},
        {"evidence_source": EvidenceSource.HOST_TEST},
        {"missing_requirements": ("bad",)},
        {"missing_requirements": ("bad", "bad")},
        {"schema_version": "bad"},
    ):
        with pytest.raises(ValidationError):
            unsafe_replace(result, **result_changes)

    for arguments in (
        ("bad", coefficients, config),
        (original, "bad", config),
        (original, coefficients, "bad"),
    ):
        with pytest.raises(ValidationError):
            apply_linear_calibration(*arguments)  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="channel"):
        apply_linear_calibration(
            original,
            coefficients,
            replace(config, input_channel="wrong"),
        )

    assert isinstance(result, CalibrationApplicationResult)
    assert isinstance(point, CalibrationAppliedPoint)
    assert isinstance(fit.metrics, CalibrationErrorMetrics)


def test_fit_function_argument_validation() -> None:
    observed = batch("o", "observed", [0, 1, 2])
    reference = batch("r", "reference", [0, 1, 2])
    config = fit_config()
    for arguments in (
        ("bad", reference, config),
        (observed, "bad", config),
        (observed, reference, "bad"),
    ):
        with pytest.raises(ValidationError):
            fit_linear_calibration(*arguments)  # type: ignore[arg-type]


def test_allowed_suspect_quality_can_be_calibrated() -> None:
    policy = AnalysisQualityPolicy(frozenset({QualityFlag.OUT_OF_RANGE}))
    records = list(batch("o", "observed", [0, 50, 100]).measurements)
    records[1] = replace(
        records[1],
        status=MeasurementStatus.SUSPECT,
        quality_flags=frozenset({QualityFlag.OUT_OF_RANGE}),
    )
    result = fit_linear_calibration(
        MeasurementBatch(tuple(records)),
        batch("r", "reference", [10, 110, 210]),
        fit_config(quality_policy=policy),
    )
    assert result.is_complete
