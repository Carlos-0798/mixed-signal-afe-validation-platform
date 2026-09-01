"""Tests for offline amplitude-ratio and cutoff-frequency analysis."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from analog_validation.analysis import (
    CUTOFF_INTERPOLATION_METHOD,
    FREQUENCY_RESPONSE_ANALYSIS_SCHEMA_VERSION,
    AnalysisQualityPolicy,
    FrequencyMeasurementDecision,
    FrequencyPointExclusionReason,
    FrequencyResponseAnalysisConfig,
    FrequencyResponseAnalysisResult,
    FrequencyResponsePointResult,
    FrequencyResponseSummary,
    MeasurementBatch,
    PointDisposition,
    PointExclusionReason,
    analyze_frequency_response,
    assess_frequency_measurement,
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
    unit: MeasurementUnit,
    *,
    source: EvidenceSource = EvidenceSource.SYNTHETIC,
    status: MeasurementStatus = MeasurementStatus.VALID,
    flags: frozenset[QualityFlag] = frozenset(),
    sequence: int = 0,
) -> Measurement:
    return Measurement(
        record_id,
        f"raw-{record_id}",
        NOW + timedelta(milliseconds=sequence),
        channel,
        value,
        unit,
        status,
        source,
        flags,
    )


def make_batch(
    prefix: str,
    channel: str,
    values: Sequence[float | None],
    unit: MeasurementUnit,
    *,
    units: list[MeasurementUnit] | None = None,
    source: EvidenceSource = EvidenceSource.SYNTHETIC,
) -> MeasurementBatch:
    actual_units = units or [unit] * len(values)
    return MeasurementBatch(
        tuple(
            measurement(
                f"{prefix}-{index}",
                channel,
                value,
                actual_unit,
                source=source,
                sequence=index,
            )
            for index, (value, actual_unit) in enumerate(
                zip(values, actual_units, strict=True)
            )
        )
    )


def config(**overrides: Any) -> FrequencyResponseAnalysisConfig:
    values: dict[str, Any] = {
        "frequency_channel": "frequency",
        "input_amplitude_channel": "vin",
        "output_amplitude_channel": "vout",
    }
    values.update(overrides)
    return FrequencyResponseAnalysisConfig(**values)


def unsafe_replace(instance: Any, **changes: Any) -> Any:
    """Exercise runtime dataclass guards with deliberately invalid types."""

    return replace(instance, **changes)


def analyze(
    frequencies: list[float],
    ratios: list[float],
    *,
    configuration: FrequencyResponseAnalysisConfig | None = None,
) -> FrequencyResponseAnalysisResult:
    return analyze_frequency_response(
        make_batch("f", "frequency", frequencies, MeasurementUnit.HERTZ),
        make_batch("i", "vin", [1000] * len(frequencies), MeasurementUnit.MILLIVOLT),
        make_batch(
            "o",
            "vout",
            [1000 * ratio for ratio in ratios],
            MeasurementUnit.MILLIVOLT,
        ),
        configuration or config(),
    )


def test_nominal_response_calculates_ratio_db_and_log_frequency_cutoff() -> None:
    result = analyze([10, 100, 1000], [1, 0.8, 0.5])
    assert result.schema_version == FREQUENCY_RESPONSE_ANALYSIS_SCHEMA_VERSION
    assert result.is_complete
    assert result.included_points == 3
    assert [point.amplitude_ratio for point in result.points] == pytest.approx(
        [1, 0.8, 0.5]
    )
    assert [point.gain_db for point in result.points] == pytest.approx(
        [0, 20 * math.log10(0.8), 20 * math.log10(0.5)]
    )
    summary = result.summary
    assert summary is not None
    expected = 10 ** (
        2
        + (summary.cutoff_target_db - 20 * math.log10(0.8))
        / (20 * math.log10(0.5) - 20 * math.log10(0.8))
    )
    assert summary.cutoff_frequency_hz == pytest.approx(expected)
    assert summary.reference_gain_db == pytest.approx(0)
    assert summary.interpolation_method == CUTOFF_INTERPOLATION_METHOD
    assert result.evidence_source is EvidenceSource.SYNTHETIC
    assert result.points[0].frequency_hz == 10
    with pytest.raises(FrozenInstanceError):
        result.summary.cutoff_frequency_hz = 1  # type: ignore[misc,union-attr]


def test_exact_target_endpoint_is_deduplicated_across_adjacent_segments() -> None:
    target_ratio = 10 ** (-3.010299956639812 / 20)
    result = analyze([10, 100, 1000], [1, target_ratio, 0.4])
    assert result.summary is not None
    assert result.summary.cutoff_frequency_hz == pytest.approx(100)


def test_v_and_mv_amplitudes_are_normalized_before_ratio() -> None:
    result = analyze_frequency_response(
        make_batch("f", "frequency", [10, 100], MeasurementUnit.HERTZ),
        make_batch(
            "i",
            "vin",
            [1, 1000],
            MeasurementUnit.MILLIVOLT,
            units=[MeasurementUnit.VOLT, MeasurementUnit.MILLIVOLT],
        ),
        make_batch(
            "o",
            "vout",
            [1, 0.5],
            MeasurementUnit.VOLT,
        ),
        config(),
    )
    assert result.summary is not None
    assert [point.amplitude_ratio for point in result.points] == pytest.approx([1, 0.5])
    assert result.summary.cutoff_frequency_hz == pytest.approx(math.sqrt(10 * 100))


def test_no_crossing_is_incomplete_and_multiple_crossings_are_rejected() -> None:
    no_crossing = analyze([10, 100, 1000], [1, 0.95, 0.9])
    assert not no_crossing.is_complete
    assert no_crossing.missing_requirements == ("cutoff-crossing",)
    with pytest.raises(ValidationError, match="multiple cutoff"):
        analyze([10, 100, 1000, 10000], [1, 0.5, 0.9, 0.4])


def test_quality_exclusion_retains_decisions_but_suppresses_summary() -> None:
    frequencies = list(
        make_batch(
            "f", "frequency", [10, 100, 1000], MeasurementUnit.HERTZ
        ).measurements
    )
    frequencies[1] = replace(
        frequencies[1],
        status=MeasurementStatus.SUSPECT,
        quality_flags=frozenset({QualityFlag.TIME_ANOMALY}),
    )
    result = analyze_frequency_response(
        MeasurementBatch(tuple(frequencies)),
        make_batch("i", "vin", [1000, 1000, 1000], MeasurementUnit.MILLIVOLT),
        make_batch("o", "vout", [1000, 800, 500], MeasurementUnit.MILLIVOLT),
        config(),
    )
    assert result.missing_requirements == ("usable-points:2/3",)
    assert result.points[1].disposition is PointDisposition.EXCLUDED
    assert result.points[1].exclusion_reasons == (
        FrequencyPointExclusionReason.FREQUENCY_NOT_INCLUDED,
    )
    assert result.points[1].amplitude_ratio is None


def test_allowed_suspect_frequency_can_be_used() -> None:
    policy = AnalysisQualityPolicy(frozenset({QualityFlag.TIME_ANOMALY}))
    frequencies = list(
        make_batch("f", "frequency", [10, 100], MeasurementUnit.HERTZ).measurements
    )
    frequencies[0] = replace(
        frequencies[0],
        status=MeasurementStatus.SUSPECT,
        quality_flags=frozenset({QualityFlag.TIME_ANOMALY}),
    )
    result = analyze_frequency_response(
        MeasurementBatch(tuple(frequencies)),
        make_batch("i", "vin", [1000, 1000], MeasurementUnit.MILLIVOLT),
        make_batch("o", "vout", [1000, 500], MeasurementUnit.MILLIVOLT),
        config(quality_policy=policy),
    )
    assert result.is_complete


@pytest.mark.parametrize(
    ("input_values", "output_values", "message"),
    [
        ([0, 1000], [1000, 500], "input amplitude"),
        ([-1, 1000], [1000, 500], "input amplitude"),
        ([1000, 1000], [0, 500], "amplitude ratio"),
        ([1000, 1000], [-1, 500], "amplitude ratio"),
    ],
)
def test_nonpositive_amplitudes_are_rejected(
    input_values: list[float],
    output_values: list[float],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        analyze_frequency_response(
            make_batch("f", "frequency", [10, 100], MeasurementUnit.HERTZ),
            make_batch("i", "vin", input_values, MeasurementUnit.MILLIVOLT),
            make_batch("o", "vout", output_values, MeasurementUnit.MILLIVOLT),
            config(),
        )


@pytest.mark.parametrize("frequencies", [[0, 10], [-1, 10], [100, 10], [10, 10]])
def test_frequency_must_be_positive_and_strictly_increasing(
    frequencies: list[float],
) -> None:
    with pytest.raises(ValidationError):
        analyze(frequencies, [1, 0.5])


def test_batch_and_channel_boundaries_are_rejected() -> None:
    frequencies = make_batch("f", "frequency", [10, 100], MeasurementUnit.HERTZ)
    inputs = make_batch("i", "vin", [1000, 1000], MeasurementUnit.MILLIVOLT)
    outputs = make_batch("o", "vout", [1000, 500], MeasurementUnit.MILLIVOLT)
    for arguments in (
        ("bad", inputs, outputs, config()),
        (frequencies, inputs, outputs, "bad"),
        (
            frequencies,
            make_batch("i", "vin", [1], MeasurementUnit.VOLT),
            outputs,
            config(),
        ),
        (
            frequencies,
            inputs,
            make_batch(
                "o",
                "vout",
                [1000, 500],
                MeasurementUnit.MILLIVOLT,
                source=EvidenceSource.HOST_TEST,
            ),
            config(),
        ),
        (frequencies, inputs, outputs, config(frequency_channel="wrong")),
        (frequencies, inputs, outputs, config(input_amplitude_channel="wrong")),
        (frequencies, inputs, outputs, config(output_amplitude_channel="wrong")),
    ):
        with pytest.raises(ValidationError):
            analyze_frequency_response(*arguments)  # type: ignore[arg-type]
    duplicate = MeasurementBatch(
        tuple(
            replace(item, record_id=f"f-{index}")
            for index, item in enumerate(inputs.measurements)
        )
    )
    with pytest.raises(ValidationError, match="record IDs"):
        analyze_frequency_response(frequencies, duplicate, outputs, config())


@pytest.mark.parametrize(
    "overrides",
    [
        {"frequency_channel": ""},
        {"input_amplitude_channel": " vin"},
        {"output_amplitude_channel": "vin"},
        {"normalized_amplitude_unit": MeasurementUnit.HERTZ},
        {"cutoff_drop_db": True},
        {"cutoff_drop_db": math.inf},
        {"cutoff_drop_db": 0},
        {"minimum_included_points": True},
        {"minimum_included_points": 1},
        {"quality_policy": "bad"},
        {"schema_version": "bad"},
    ],
)
def test_config_validation(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        config(**overrides)


def test_frequency_measurement_assessment_validation() -> None:
    valid = measurement("f", "frequency", 10, MeasurementUnit.HERTZ)
    decision = assess_frequency_measurement(valid)
    assert decision.frequency_hz == 10
    assert decision.disposition is PointDisposition.INCLUDED
    for item, policy in (
        ("bad", AnalysisQualityPolicy()),
        (valid, "bad"),
        (replace(valid, unit=MeasurementUnit.VOLT), AnalysisQualityPolicy()),
        (replace(valid, value=0), AnalysisQualityPolicy()),
    ):
        with pytest.raises(ValidationError):
            assess_frequency_measurement(item, policy)  # type: ignore[arg-type]


def test_frequency_decision_point_summary_and_result_model_guards() -> None:
    result = analyze([10, 100], [1, 0.5])
    point = result.points[0]
    decision = point.frequency_decision
    summary = result.summary
    assert summary is not None
    invalid_measurement = measurement(
        "invalid-frequency",
        "frequency",
        None,
        MeasurementUnit.HERTZ,
        status=MeasurementStatus.INVALID,
        flags=frozenset({QualityFlag.MISSING}),
    )
    invalid_decision = assess_frequency_measurement(invalid_measurement)
    assert invalid_decision.disposition is PointDisposition.INVALID
    for decision_changes in (
        {"reference": "bad"},
        {"frequency_hz": True},
        {"frequency_hz": 0},
        {"status": "bad"},
        {"observed_quality_flags": 1},
        {"observed_quality_flags": frozenset({"bad"})},
        {"disposition": "bad"},
        {"quality_policy": "bad"},
        {"exclusion_reasons": ("bad",)},
        {"exclusion_reasons": (PointDisposition.INVALID,)},
        {
            "exclusion_reasons": (
                PointExclusionReason.SUSPECT_STATUS,
                PointExclusionReason.SUSPECT_STATUS,
            )
        },
        {"disposition": PointDisposition.EXCLUDED},
        {"frequency_hz": None},
        {"schema_version": "bad"},
    ):
        with pytest.raises((ValidationError, TypeError)):
            unsafe_replace(decision, **decision_changes)

    different_unit_output = replace(
        point.output_decision,
        normalized_unit=MeasurementUnit.VOLT,
        normalized_value=1,
    )
    excluded_point = replace(
        point,
        frequency_decision=invalid_decision,
        disposition=PointDisposition.INVALID,
        exclusion_reasons=(FrequencyPointExclusionReason.FREQUENCY_NOT_INCLUDED,),
        amplitude_ratio=None,
        gain_db=None,
    )

    for point_changes in (
        {"sequence": True},
        {"frequency_decision": "bad"},
        {"input_decision": "bad"},
        {"disposition": "bad"},
        {"exclusion_reasons": ("bad",)},
        {
            "exclusion_reasons": (
                FrequencyPointExclusionReason.INPUT_NOT_INCLUDED,
                FrequencyPointExclusionReason.INPUT_NOT_INCLUDED,
            )
        },
        {"exclusion_reasons": (FrequencyPointExclusionReason.INPUT_NOT_INCLUDED,)},
        {"amplitude_ratio": None},
        {"amplitude_ratio": 0},
        {"gain_db": 1},
        {"schema_version": "bad"},
        {"output_decision": different_unit_output},
        {"disposition": PointDisposition.EXCLUDED},
    ):
        with pytest.raises(ValidationError):
            unsafe_replace(point, **point_changes)
    with pytest.raises(ValidationError, match="cannot contain"):
        replace(excluded_point, amplitude_ratio=1, gain_db=0)

    for summary_changes in (
        {"reference_gain_db": math.inf},
        {"cutoff_frequency_hz": 0},
        {"included_points": True},
        {"included_points": 1},
        {"interpolation_method": "bad"},
        {"schema_version": "bad"},
    ):
        with pytest.raises(ValidationError):
            unsafe_replace(summary, **summary_changes)

    for result_changes in (
        {"config": "bad"},
        {"evidence_source": "bad"},
        {"points": ()},
        {"points": ("bad",)},
        {"points": (replace(point, sequence=2),)},
        {"evidence_source": EvidenceSource.HOST_TEST},
        {"missing_requirements": ("x", "x")},
        {"missing_requirements": ("x",)},
        {"summary": None},
        {"summary": "bad"},
        {"summary": replace(summary, included_points=3)},
        {"schema_version": "bad"},
    ):
        with pytest.raises(ValidationError):
            unsafe_replace(result, **result_changes)
    assert isinstance(decision, FrequencyMeasurementDecision)
    assert isinstance(point, FrequencyResponsePointResult)
    assert isinstance(summary, FrequencyResponseSummary)
    assert isinstance(result, FrequencyResponseAnalysisResult)


def test_invalid_or_missing_points_can_report_both_minimum_and_usable_requirements() -> (
    None
):
    inputs = list(
        make_batch("i", "vin", [1000, 1000], MeasurementUnit.MILLIVOLT).measurements
    )
    inputs[0] = replace(
        inputs[0],
        value=None,
        status=MeasurementStatus.INVALID,
        quality_flags=frozenset({QualityFlag.MISSING}),
    )
    result = analyze_frequency_response(
        make_batch("f", "frequency", [10, 100], MeasurementUnit.HERTZ),
        MeasurementBatch(tuple(inputs)),
        make_batch("o", "vout", [1000, 500], MeasurementUnit.MILLIVOLT),
        config(),
    )
    assert result.missing_requirements == (
        "included-points:1/2",
        "usable-points:1/2",
    )
    assert result.points[0].disposition is PointDisposition.INVALID
    assert result.points[0].exclusion_reasons == (
        FrequencyPointExclusionReason.INPUT_NOT_INCLUDED,
    )
