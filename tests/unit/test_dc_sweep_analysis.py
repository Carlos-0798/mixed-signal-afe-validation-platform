"""Tests for provenance-aware Software Phase 3 DC sweep analysis."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest

from analog_validation import (
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
    QualityFlag,
    ValidationError,
)
from analog_validation.analysis import (
    DC_SWEEP_ANALYSIS_SCHEMA_VERSION,
    AnalysisQualityPolicy,
    DCSweepAnalysisConfig,
    DCSweepAnalysisResult,
    DCSweepFitResult,
    DCSweepPointExclusionReason,
    DCSweepPointPair,
    DCSweepPointResult,
    MeasurementBatch,
    PointDisposition,
    analyze_dc_sweep,
    assess_voltage_measurement,
    pair_dc_sweep_measurements,
)

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
INPUT_CHANNEL = "afe.ch0.input"
OUTPUT_CHANNEL = "afe.ch0.output"


def make_measurement(
    record_id: str,
    channel: str,
    value: float | None,
    *,
    unit: MeasurementUnit = MeasurementUnit.MILLIVOLT,
    status: MeasurementStatus = MeasurementStatus.VALID,
    source: EvidenceSource = EvidenceSource.SYNTHETIC,
    quality_flags: frozenset[QualityFlag] = frozenset(),
    sequence: int = 0,
) -> Measurement:
    return Measurement(
        record_id=record_id,
        raw_record_id=f"raw-{record_id}",
        timestamp=NOW + timedelta(milliseconds=sequence),
        channel=channel,
        value=value,
        unit=unit,
        status=status,
        source=source,
        quality_flags=quality_flags,
    )


def make_config(**overrides: Any) -> DCSweepAnalysisConfig:
    values: dict[str, Any] = {
        "input_channel": INPUT_CHANNEL,
        "output_channel": OUTPUT_CHANNEL,
        "low_output_limit": 100.0,
        "high_output_limit": 900.0,
    }
    values.update(overrides)
    return DCSweepAnalysisConfig(**values)


def make_batch(
    inputs: list[float | None],
    outputs: list[float | None],
    *,
    input_units: list[MeasurementUnit] | None = None,
    output_units: list[MeasurementUnit] | None = None,
    source: EvidenceSource = EvidenceSource.SYNTHETIC,
) -> MeasurementBatch:
    input_units = input_units or [MeasurementUnit.MILLIVOLT] * len(inputs)
    output_units = output_units or [MeasurementUnit.MILLIVOLT] * len(outputs)
    records: list[Measurement] = []
    for index, (input_value, output_value) in enumerate(zip(inputs, outputs)):
        records.extend(
            (
                make_measurement(
                    f"input-{index}",
                    INPUT_CHANNEL,
                    input_value,
                    unit=input_units[index],
                    source=source,
                    sequence=index * 2,
                ),
                make_measurement(
                    f"output-{index}",
                    OUTPUT_CHANNEL,
                    output_value,
                    unit=output_units[index],
                    source=source,
                    sequence=index * 2 + 1,
                ),
            )
        )
    return MeasurementBatch(tuple(records))


def make_pair(
    *,
    sequence: int = 0,
    input_measurement: Measurement | None = None,
    output_measurement: Measurement | None = None,
    schema_version: str = DC_SWEEP_ANALYSIS_SCHEMA_VERSION,
) -> DCSweepPointPair:
    return DCSweepPointPair(
        sequence=sequence,
        input_measurement=input_measurement
        or make_measurement("input-0", INPUT_CHANNEL, 200.0),
        output_measurement=output_measurement
        or make_measurement("output-0", OUTPUT_CHANNEL, 400.0),
        schema_version=schema_version,
    )


def make_included_point(
    *,
    sequence: int = 0,
    input_value: float = 200.0,
    output_value: float = 400.0,
    unit: MeasurementUnit = MeasurementUnit.MILLIVOLT,
    source: EvidenceSource = EvidenceSource.SYNTHETIC,
    predicted_output: float | None = None,
    residual: float | None = None,
) -> DCSweepPointResult:
    input_decision = assess_voltage_measurement(
        make_measurement(
            f"input-{sequence}",
            INPUT_CHANNEL,
            input_value,
            unit=unit,
            source=source,
        ),
        target_unit=unit,
    )
    output_decision = assess_voltage_measurement(
        make_measurement(
            f"output-{sequence}",
            OUTPUT_CHANNEL,
            output_value,
            unit=unit,
            source=source,
        ),
        target_unit=unit,
    )
    return DCSweepPointResult(
        sequence,
        input_decision,
        output_decision,
        PointDisposition.INCLUDED,
        predicted_output=predicted_output,
        residual=residual,
    )


def exact_analysis() -> DCSweepAnalysisResult:
    return analyze_dc_sweep(
        make_batch(
            [100.0, 200.0, 300.0, 400.0],
            [212.0, 412.0, 612.0, 812.0],
        ),
        make_config(low_output_limit=0.0, high_output_limit=1000.0),
    )


def test_public_dc_sweep_schema_and_exports_are_stable() -> None:
    import analog_validation.analysis.dc_sweep as module
    from analog_validation import analysis

    expected = {
        "DC_SWEEP_ANALYSIS_SCHEMA_VERSION",
        "DCSweepAnalysisConfig",
        "DCSweepAnalysisResult",
        "DCSweepFitResult",
        "DCSweepPointExclusionReason",
        "DCSweepPointPair",
        "DCSweepPointResult",
        "analyze_dc_sweep",
        "pair_dc_sweep_measurements",
    }

    assert DC_SWEEP_ANALYSIS_SCHEMA_VERSION == "dc-sweep-analysis.v1"
    assert set(module.__all__) == expected
    assert expected.issubset(set(analysis.__all__))
    assert tuple(reason.value for reason in DCSweepPointExclusionReason) == (
        "INPUT_NOT_INCLUDED",
        "OUTPUT_NOT_INCLUDED",
        "LOW_SATURATION",
        "HIGH_SATURATION",
    )


def test_config_freezes_normalized_numeric_limits_and_defaults() -> None:
    config = make_config(low_output_limit=0, high_output_limit=1000)

    assert config.low_output_limit == 0.0
    assert config.high_output_limit == 1000.0
    assert config.normalized_unit is MeasurementUnit.MILLIVOLT
    assert config.minimum_included_points == 3
    assert config.quality_policy.allowed_suspect_flags == frozenset()
    with pytest.raises(FrozenInstanceError):
        config.minimum_included_points = 4  # type: ignore[misc]


@pytest.mark.parametrize("field", ["input_channel", "output_channel"])
@pytest.mark.parametrize("value", [None, "", " bad", "bad "])
def test_config_rejects_bad_channel_identifiers(field: str, value: object) -> None:
    with pytest.raises(ValidationError, match=field):
        make_config(**{field: value})


def test_config_requires_distinct_channels() -> None:
    with pytest.raises(ValidationError, match="distinct"):
        make_config(output_channel=INPUT_CHANNEL)


@pytest.mark.parametrize("field", ["low_output_limit", "high_output_limit"])
@pytest.mark.parametrize("value", [True, "1", None])
def test_config_rejects_non_numeric_limits(field: str, value: object) -> None:
    with pytest.raises(ValidationError, match="numeric"):
        make_config(**{field: value})


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_config_rejects_non_finite_limits(value: float) -> None:
    with pytest.raises(ValidationError, match="finite"):
        make_config(high_output_limit=value)


@pytest.mark.parametrize(("low", "high"), [(1.0, 1.0), (2.0, 1.0)])
def test_config_requires_ordered_limits(low: float, high: float) -> None:
    with pytest.raises(ValidationError, match="must be below"):
        make_config(low_output_limit=low, high_output_limit=high)


@pytest.mark.parametrize(
    "unit",
    [MeasurementUnit.AMPERE, MeasurementUnit.ADC_COUNT, "mV"],
)
def test_config_rejects_unknown_or_non_voltage_unit(unit: object) -> None:
    with pytest.raises(ValidationError, match="normalized_unit must be V or mV"):
        make_config(normalized_unit=unit)


@pytest.mark.parametrize("minimum", [True, 1, 2.5, "3"])
def test_config_rejects_bad_minimum_point_count(minimum: object) -> None:
    with pytest.raises(ValidationError, match="integer of at least two"):
        make_config(minimum_included_points=minimum)


def test_config_rejects_bad_policy_and_schema() -> None:
    with pytest.raises(ValidationError, match="AnalysisQualityPolicy"):
        make_config(quality_policy=object())
    with pytest.raises(ValidationError, match="unsupported DC sweep"):
        make_config(schema_version="dc-sweep-analysis.v2")


def test_point_pair_preserves_order_source_and_is_frozen() -> None:
    pair = make_pair(sequence=7)

    assert pair.sequence == 7
    assert pair.evidence_source is EvidenceSource.SYNTHETIC
    with pytest.raises(FrozenInstanceError):
        pair.sequence = 8  # type: ignore[misc]


@pytest.mark.parametrize("sequence", [True, -1, 1.5, "0"])
def test_point_pair_rejects_bad_sequence(sequence: object) -> None:
    with pytest.raises(ValidationError, match="non-negative integer"):
        make_pair(sequence=cast(int, sequence))


def test_point_pair_rejects_wrong_measurements_identity_channel_and_source() -> None:
    with pytest.raises(ValidationError, match="input_measurement"):
        make_pair(input_measurement=cast(Measurement, object()))
    with pytest.raises(ValidationError, match="output_measurement"):
        make_pair(output_measurement=cast(Measurement, object()))

    input_measurement = make_measurement("same", INPUT_CHANNEL, 1.0)
    with pytest.raises(ValidationError, match="distinct record IDs"):
        make_pair(
            input_measurement=input_measurement,
            output_measurement=make_measurement("same", OUTPUT_CHANNEL, 2.0),
        )
    with pytest.raises(ValidationError, match="distinct channels"):
        make_pair(
            output_measurement=make_measurement("output-0", INPUT_CHANNEL, 2.0)
        )
    with pytest.raises(ValidationError, match="one evidence source"):
        make_pair(
            output_measurement=make_measurement(
                "output-0",
                OUTPUT_CHANNEL,
                2.0,
                source=EvidenceSource.CSV_REPLAY,
            )
        )
    with pytest.raises(ValidationError, match="unsupported DC sweep"):
        make_pair(schema_version="dc-sweep-analysis.v2")


def test_pairing_uses_within_channel_order_without_mutating_batch() -> None:
    original = make_batch([1.0, 2.0, 3.0], [11.0, 12.0, 13.0])
    reordered = MeasurementBatch(
        (
            original.measurements[1],
            original.measurements[3],
            original.measurements[0],
            original.measurements[5],
            original.measurements[2],
            original.measurements[4],
        )
    )
    before = reordered.measurements

    pairs = pair_dc_sweep_measurements(reordered, make_config())

    assert tuple(pair.sequence for pair in pairs) == (0, 1, 2)
    assert tuple(pair.input_measurement.value for pair in pairs) == (1.0, 2.0, 3.0)
    assert tuple(pair.output_measurement.value for pair in pairs) == (
        11.0,
        12.0,
        13.0,
    )
    assert reordered.measurements == before


def test_pairing_validates_types_channels_presence_and_equal_counts() -> None:
    config = make_config()
    batch = make_batch([1.0], [2.0])
    with pytest.raises(ValidationError, match="batch must"):
        pair_dc_sweep_measurements(cast(MeasurementBatch, object()), config)
    with pytest.raises(ValidationError, match="config must"):
        pair_dc_sweep_measurements(batch, cast(DCSweepAnalysisConfig, object()))

    extra = make_measurement("extra", "afe.other", 3.0)
    with pytest.raises(ValidationError, match="unexpected channels: afe.other"):
        pair_dc_sweep_measurements(
            MeasurementBatch((*batch.measurements, extra)),
            config,
        )
    with pytest.raises(ValidationError, match="at least one input and output"):
        pair_dc_sweep_measurements(
            MeasurementBatch((batch.measurements[0],)),
            config,
        )
    with pytest.raises(ValidationError, match="counts must match"):
        pair_dc_sweep_measurements(
            MeasurementBatch(
                (
                    *batch.measurements,
                    make_measurement("input-1", INPUT_CHANNEL, 3.0),
                )
            ),
            config,
        )


def test_point_result_accepts_fitted_included_point_and_exposes_source_unit() -> None:
    point = make_included_point(predicted_output=399.5, residual=0.5)

    assert point.evidence_source is EvidenceSource.SYNTHETIC
    assert point.normalized_unit is MeasurementUnit.MILLIVOLT
    assert point.predicted_output == 399.5
    assert point.residual == 0.5
    with pytest.raises(FrozenInstanceError):
        point.residual = 0.0  # type: ignore[misc]


@pytest.mark.parametrize("sequence", [True, -1, 0.5, "0"])
def test_point_result_rejects_bad_sequence(sequence: object) -> None:
    point = make_included_point()
    with pytest.raises(ValidationError, match="non-negative integer"):
        replace(point, sequence=sequence)  # type: ignore[arg-type]


def test_point_result_rejects_wrong_decisions_identity_source_unit_and_disposition() -> None:
    point = make_included_point()
    with pytest.raises(ValidationError, match="input_decision"):
        replace(point, input_decision=object())  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="output_decision"):
        replace(point, output_decision=object())  # type: ignore[arg-type]

    same_reference = replace(
        point.output_decision,
        reference=point.input_decision.reference,
    )
    with pytest.raises(ValidationError, match="distinct record IDs"):
        replace(point, output_decision=same_reference)

    csv_point = make_included_point(source=EvidenceSource.CSV_REPLAY)
    with pytest.raises(ValidationError, match="one evidence source"):
        replace(point, output_decision=csv_point.output_decision)

    volt_point = make_included_point(unit=MeasurementUnit.VOLT)
    with pytest.raises(ValidationError, match="one normalized unit"):
        replace(point, output_decision=volt_point.output_decision)
    with pytest.raises(ValidationError, match="PointDisposition"):
        replace(point, disposition="INCLUDED")  # type: ignore[arg-type]


def test_point_result_validates_reason_collections_and_optional_numbers() -> None:
    point = make_included_point()
    with pytest.raises(ValidationError, match="iterable"):
        replace(point, exclusion_reasons=None)  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="unknown"):
        replace(point, exclusion_reasons=("LOW_SATURATION",))  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="duplicates"):
        replace(
            point,
            exclusion_reasons=(
                DCSweepPointExclusionReason.LOW_SATURATION,
                DCSweepPointExclusionReason.LOW_SATURATION,
            ),
        )
    with pytest.raises(ValidationError, match="numeric"):
        replace(point, predicted_output=True, residual=0.0)
    with pytest.raises(ValidationError, match="finite"):
        replace(point, predicted_output=math.inf, residual=0.0)
    with pytest.raises(ValidationError, match="both be present"):
        replace(point, predicted_output=1.0)


def test_point_result_requires_component_reasons_to_agree() -> None:
    included = make_included_point()
    with pytest.raises(ValidationError, match="INPUT_NOT_INCLUDED"):
        replace(
            included,
            exclusion_reasons=(
                DCSweepPointExclusionReason.INPUT_NOT_INCLUDED,
            ),
        )
    with pytest.raises(ValidationError, match="OUTPUT_NOT_INCLUDED"):
        replace(
            included,
            exclusion_reasons=(
                DCSweepPointExclusionReason.OUTPUT_NOT_INCLUDED,
            ),
        )

    suspect = assess_voltage_measurement(
        make_measurement(
            "input-suspect",
            INPUT_CHANNEL,
            1.0,
            status=MeasurementStatus.SUSPECT,
            quality_flags=frozenset({QualityFlag.OUT_OF_RANGE}),
        )
    )
    with pytest.raises(ValidationError, match="INPUT_NOT_INCLUDED"):
        replace(included, input_decision=suspect)


def test_point_result_requires_overall_disposition_to_agree() -> None:
    included = make_included_point()
    invalid = assess_voltage_measurement(
        make_measurement(
            "bad-input",
            INPUT_CHANNEL,
            None,
            status=MeasurementStatus.INVALID,
            quality_flags=frozenset({QualityFlag.MISSING}),
        )
    )
    reasons = (DCSweepPointExclusionReason.INPUT_NOT_INCLUDED,)
    with pytest.raises(ValidationError, match="INVALID disposition"):
        replace(included, input_decision=invalid, exclusion_reasons=reasons)

    invalid_point = replace(
        included,
        input_decision=invalid,
        disposition=PointDisposition.INVALID,
        exclusion_reasons=reasons,
    )
    assert invalid_point.disposition is PointDisposition.INVALID
    with pytest.raises(ValidationError, match="INVALID disposition"):
        replace(included, disposition=PointDisposition.INVALID)
    with pytest.raises(ValidationError, match="requires reasons"):
        replace(included, disposition=PointDisposition.EXCLUDED)
    with pytest.raises(ValidationError, match="two included decisions"):
        replace(
            included,
            exclusion_reasons=(
                DCSweepPointExclusionReason.LOW_SATURATION,
            ),
        )


def test_point_result_enforces_fitted_and_saturation_consistency() -> None:
    point = make_included_point()
    saturated = replace(
        point,
        disposition=PointDisposition.EXCLUDED,
        exclusion_reasons=(DCSweepPointExclusionReason.LOW_SATURATION,),
    )
    assert saturated.predicted_output is None
    with pytest.raises(ValidationError, match="cannot contain fitted values"):
        replace(saturated, predicted_output=1.0, residual=0.0)
    with pytest.raises(ValidationError, match="both low- and high"):
        replace(
            saturated,
            exclusion_reasons=(
                DCSweepPointExclusionReason.LOW_SATURATION,
                DCSweepPointExclusionReason.HIGH_SATURATION,
            ),
        )

    missing_output = assess_voltage_measurement(
        make_measurement(
            "missing-output",
            OUTPUT_CHANNEL,
            None,
            status=MeasurementStatus.INVALID,
            quality_flags=frozenset({QualityFlag.MISSING}),
        )
    )
    with pytest.raises(ValidationError, match="finite output value"):
        DCSweepPointResult(
            0,
            point.input_decision,
            missing_output,
            PointDisposition.INVALID,
            (
                DCSweepPointExclusionReason.OUTPUT_NOT_INCLUDED,
                DCSweepPointExclusionReason.LOW_SATURATION,
            ),
        )
    with pytest.raises(ValidationError, match="unsupported DC sweep"):
        replace(point, schema_version="dc-sweep-analysis.v2")


def test_fit_result_normalizes_numbers_and_is_frozen() -> None:
    fit = DCSweepFitResult(2, 12, 1, 0, 0, 3, MeasurementUnit.MILLIVOLT)

    assert fit.gain == 2.0
    assert fit.offset == 12.0
    assert fit.used_points == 3
    with pytest.raises(FrozenInstanceError):
        fit.gain = 3.0  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("gain", True, "numeric"),
        ("offset", "0", "numeric"),
        ("r_squared", math.nan, "finite"),
        ("rmse", math.inf, "finite"),
        ("max_abs_residual", -math.inf, "finite"),
        ("r_squared", -0.1, "between zero and one"),
        ("r_squared", 1.1, "between zero and one"),
        ("rmse", -0.1, "cannot be negative"),
        ("max_abs_residual", -0.1, "cannot be negative"),
    ],
)
def test_fit_result_rejects_bad_metrics(
    field: str,
    value: object,
    message: str,
) -> None:
    fit = DCSweepFitResult(2, 12, 1, 0, 0, 3, MeasurementUnit.MILLIVOLT)
    with pytest.raises(ValidationError, match=message):
        replace(fit, **{field: value})  # type: ignore[arg-type]


@pytest.mark.parametrize("used_points", [True, 1, 2.5, "3"])
def test_fit_result_rejects_bad_count(used_points: object) -> None:
    with pytest.raises(ValidationError, match="integer of at least two"):
        DCSweepFitResult(
            2,
            12,
            1,
            0,
            0,
            cast(int, used_points),
            MeasurementUnit.MILLIVOLT,
        )


def test_fit_result_rejects_bad_unit_and_schema() -> None:
    with pytest.raises(ValidationError, match="normalized_unit must be V or mV"):
        DCSweepFitResult(2, 12, 1, 0, 0, 3, MeasurementUnit.AMPERE)
    with pytest.raises(ValidationError, match="unsupported DC sweep"):
        DCSweepFitResult(
            2,
            12,
            1,
            0,
            0,
            3,
            MeasurementUnit.MILLIVOLT,
            "dc-sweep-analysis.v2",
        )


def test_exact_line_returns_complete_traceable_metrics() -> None:
    result = exact_analysis()

    assert result.is_complete
    assert result.evidence_source is EvidenceSource.SYNTHETIC
    assert result.fit is not None
    assert result.fit.gain == pytest.approx(2.0)
    assert result.fit.offset == pytest.approx(12.0)
    assert result.fit.r_squared == pytest.approx(1.0)
    assert result.fit.rmse == pytest.approx(0.0)
    assert result.fit.max_abs_residual == pytest.approx(0.0)
    assert result.fit.used_points == 4
    assert result.included_points == 4
    assert result.excluded_points == 0
    assert result.invalid_points == 0
    assert result.missing_requirements == ()
    assert tuple(point.input_decision.reference.record_id for point in result.points) == (
        "input-0",
        "input-1",
        "input-2",
        "input-3",
    )
    assert all(point.predicted_output is not None for point in result.points)
    assert all(point.residual == pytest.approx(0.0) for point in result.points)


def test_noisy_line_reports_predictions_residuals_and_quality_metrics() -> None:
    result = analyze_dc_sweep(
        make_batch(
            [100.0, 200.0, 300.0, 400.0, 500.0],
            [211.0, 415.0, 608.0, 818.0, 1005.0],
        ),
        make_config(low_output_limit=0.0, high_output_limit=1100.0),
    )

    assert result.fit is not None
    assert result.fit.gain == pytest.approx(1.991)
    assert result.fit.offset == pytest.approx(14.1)
    assert 0.99 < result.fit.r_squared < 1.0
    assert result.fit.rmse > 0.0
    assert result.fit.max_abs_residual >= result.fit.rmse
    for point in result.points:
        assert point.predicted_output is not None
        assert point.residual is not None
        assert (
            point.output_decision.normalized_value
            == pytest.approx(point.predicted_output + point.residual)
        )


def test_saturation_boundaries_are_inclusive_and_all_points_are_retained() -> None:
    result = analyze_dc_sweep(
        make_batch(
            [0.0, 100.0, 200.0, 300.0, 400.0],
            [100.0, 200.0, 400.0, 600.0, 900.0],
        ),
        make_config(),
    )

    assert result.fit is not None
    assert len(result.points) == 5
    assert result.included_points == 3
    assert result.excluded_points == 2
    assert result.points[0].exclusion_reasons == (
        DCSweepPointExclusionReason.LOW_SATURATION,
    )
    assert result.points[-1].exclusion_reasons == (
        DCSweepPointExclusionReason.HIGH_SATURATION,
    )
    assert result.points[0].predicted_output is None
    assert result.points[-1].residual is None
    assert result.fit.gain == pytest.approx(2.0)


def test_quality_anomalies_are_explained_as_excluded_or_invalid() -> None:
    batch = make_batch(
        [100.0, 200.0, 300.0, 400.0, 500.0],
        [200.0, 400.0, 600.0, 800.0, 1000.0],
    )
    records = list(batch.measurements)
    records[2] = make_measurement(
        "input-1",
        INPUT_CHANNEL,
        200.0,
        status=MeasurementStatus.SUSPECT,
        quality_flags=frozenset({QualityFlag.TIME_ANOMALY}),
    )
    records[5] = make_measurement(
        "output-2",
        OUTPUT_CHANNEL,
        None,
        status=MeasurementStatus.INVALID,
        quality_flags=frozenset({QualityFlag.MISSING}),
    )

    result = analyze_dc_sweep(
        MeasurementBatch(tuple(records)),
        make_config(low_output_limit=0.0, high_output_limit=1100.0),
    )

    assert result.is_complete
    assert result.included_points == 3
    assert result.excluded_points == 1
    assert result.invalid_points == 1
    assert result.points[1].exclusion_reasons == (
        DCSweepPointExclusionReason.INPUT_NOT_INCLUDED,
    )
    assert result.points[2].exclusion_reasons == (
        DCSweepPointExclusionReason.OUTPUT_NOT_INCLUDED,
    )
    assert result.points[1].input_decision.exclusion_reasons
    assert result.points[2].output_decision.exclusion_reasons


def test_explicit_quality_policy_does_not_override_numeric_saturation() -> None:
    policy = AnalysisQualityPolicy(frozenset({QualityFlag.SATURATED}))
    config = make_config(
        low_output_limit=100.0,
        high_output_limit=900.0,
        minimum_included_points=2,
        quality_policy=policy,
    )
    batch = make_batch([100.0, 200.0, 300.0], [200.0, 400.0, 900.0])
    records = list(batch.measurements)
    records[3] = make_measurement(
        "output-1",
        OUTPUT_CHANNEL,
        400.0,
        status=MeasurementStatus.SUSPECT,
        quality_flags=frozenset({QualityFlag.SATURATED}),
    )

    result = analyze_dc_sweep(MeasurementBatch(tuple(records)), config)

    assert result.fit is not None
    assert result.points[1].disposition is PointDisposition.INCLUDED
    assert result.points[2].disposition is PointDisposition.EXCLUDED
    assert result.points[2].exclusion_reasons == (
        DCSweepPointExclusionReason.HIGH_SATURATION,
    )


def test_mixed_v_and_mv_inputs_are_explicitly_normalized() -> None:
    result = analyze_dc_sweep(
        make_batch(
            [0.1, 200.0, 0.3],
            [0.2, 400.0, 0.6],
            input_units=[
                MeasurementUnit.VOLT,
                MeasurementUnit.MILLIVOLT,
                MeasurementUnit.VOLT,
            ],
            output_units=[
                MeasurementUnit.VOLT,
                MeasurementUnit.MILLIVOLT,
                MeasurementUnit.VOLT,
            ],
        ),
        make_config(low_output_limit=0.0, high_output_limit=1000.0),
    )

    assert result.fit is not None
    assert result.fit.gain == pytest.approx(2.0)
    assert result.fit.offset == pytest.approx(0.0)
    assert all(
        point.normalized_unit is MeasurementUnit.MILLIVOLT
        for point in result.points
    )


def test_incomplete_analysis_preserves_points_and_lists_exact_gaps() -> None:
    result = analyze_dc_sweep(
        make_batch([100.0, 100.0], [200.0, 200.0]),
        make_config(),
    )

    assert not result.is_complete
    assert result.fit is None
    assert result.missing_requirements == (
        "included-points:2/3",
        "distinct-input-values:1/2",
    )
    assert len(result.points) == 2
    assert all(point.predicted_output is None for point in result.points)
    assert all(point.residual is None for point in result.points)


def test_constant_input_with_enough_points_reports_only_distinct_input_gap() -> None:
    result = analyze_dc_sweep(
        make_batch([100.0, 100.0, 100.0], [200.0, 201.0, 202.0]),
        make_config(),
    )

    assert result.missing_requirements == ("distinct-input-values:1/2",)


def test_configurable_two_point_minimum_can_complete_a_fit() -> None:
    result = analyze_dc_sweep(
        make_batch([100.0, 200.0], [212.0, 412.0]),
        make_config(
            low_output_limit=0.0,
            high_output_limit=1000.0,
            minimum_included_points=2,
        ),
    )

    assert result.fit is not None
    assert result.fit.used_points == 2
    assert result.fit.gain == pytest.approx(2.0)


def test_constant_output_uses_defined_r_squared_branch() -> None:
    result = analyze_dc_sweep(
        make_batch([100.0, 200.0, 300.0], [500.0, 500.0, 500.0]),
        make_config(low_output_limit=0.0, high_output_limit=1000.0),
    )

    assert result.fit is not None
    assert result.fit.gain == pytest.approx(0.0)
    assert result.fit.r_squared == pytest.approx(1.0)


def test_non_voltage_measurement_is_rejected_without_guessing() -> None:
    batch = make_batch([1.0, 2.0, 3.0], [2.0, 4.0, 6.0])
    records = list(batch.measurements)
    records[0] = make_measurement(
        "input-0",
        INPUT_CHANNEL,
        1.0,
        unit=MeasurementUnit.ADC_COUNT,
    )
    with pytest.raises(ValidationError, match="measurement unit must be V or mV"):
        analyze_dc_sweep(MeasurementBatch(tuple(records)), make_config())


def test_analysis_result_is_frozen_and_exposes_counts() -> None:
    result = exact_analysis()

    assert result.included_points == 4
    with pytest.raises(FrozenInstanceError):
        result.fit = None  # type: ignore[misc]


def test_analysis_result_validates_config_source_and_point_collection() -> None:
    result = exact_analysis()
    with pytest.raises(ValidationError, match="config must"):
        replace(result, config=object())  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="EvidenceSource"):
        replace(result, evidence_source="SYNTHETIC")  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="points must be an iterable"):
        replace(result, points=None)  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="cannot be empty"):
        replace(result, points=())
    with pytest.raises(ValidationError, match="DCSweepPointResult"):
        replace(result, points=(object(),))  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="contiguous"):
        replace(result, points=(replace(result.points[0], sequence=1),))


def test_analysis_result_requires_matching_point_source_and_unit() -> None:
    result = exact_analysis()
    csv_point = make_included_point(
        source=EvidenceSource.CSV_REPLAY,
        predicted_output=400.0,
        residual=0.0,
    )
    with pytest.raises(ValidationError, match="sources must match"):
        replace(
            result,
            points=(csv_point,),
        )

    volt_point = make_included_point(
        unit=MeasurementUnit.VOLT,
        predicted_output=0.4,
        residual=0.0,
    )
    with pytest.raises(ValidationError, match="point units must match"):
        replace(
            result,
            points=(volt_point,),
        )


def test_analysis_result_validates_missing_requirement_collection() -> None:
    result = analyze_dc_sweep(
        make_batch([1.0], [2.0]),
        make_config(low_output_limit=0.0, high_output_limit=10.0),
    )
    with pytest.raises(ValidationError, match="must be an iterable"):
        replace(result, missing_requirements=None)  # type: ignore[arg-type]
    for value in ("", " bad", "bad ", 3):
        with pytest.raises(ValidationError, match="missing requirement"):
            replace(result, missing_requirements=(value,))  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="duplicates"):
        replace(result, missing_requirements=("gap", "gap"))


def test_analysis_result_enforces_complete_and_incomplete_consistency() -> None:
    complete = exact_analysis()
    incomplete = analyze_dc_sweep(
        make_batch([1.0], [2.0]),
        make_config(low_output_limit=0.0, high_output_limit=10.0),
    )
    with pytest.raises(ValidationError, match="fit must"):
        replace(complete, fit=object())  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="complete result requires a fit"):
        replace(complete, fit=None)
    with pytest.raises(ValidationError, match="complete result requires a fit"):
        replace(complete, missing_requirements=("gap",))
    with pytest.raises(ValidationError, match="complete result requires a fit"):
        replace(incomplete, missing_requirements=())


def test_analysis_result_enforces_fit_count_minimum_unit_and_predictions() -> None:
    result = exact_analysis()
    assert result.fit is not None
    with pytest.raises(ValidationError, match="match included points"):
        replace(result, fit=replace(result.fit, used_points=3))

    config = replace(result.config, minimum_included_points=5)
    with pytest.raises(ValidationError, match="configured minimum"):
        replace(result, config=config)

    volt_fit = replace(result.fit, normalized_unit=MeasurementUnit.VOLT)
    with pytest.raises(ValidationError, match="fit unit must match"):
        replace(result, fit=volt_fit)

    unfitted = replace(
        result.points[0],
        predicted_output=None,
        residual=None,
    )
    with pytest.raises(ValidationError, match="require fitted values"):
        replace(result, points=(unfitted, *result.points[1:]))

    with pytest.raises(ValidationError, match="incomplete analysis"):
        DCSweepAnalysisResult(
            result.config,
            result.evidence_source,
            result.points,
            missing_requirements=("forced-gap",),
        )


def test_analysis_result_rejects_unknown_schema() -> None:
    with pytest.raises(ValidationError, match="unsupported DC sweep"):
        replace(exact_analysis(), schema_version="dc-sweep-analysis.v2")
