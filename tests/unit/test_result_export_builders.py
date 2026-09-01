"""Tests for typed result-export builders from finalized evaluations."""

from __future__ import annotations

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
from analog_validation import TestRunMetadata as RunMetadata
from analog_validation.analysis import (
    DC_SWEEP_TEST_TYPE,
    HYSTERESIS_TEST_TYPE,
    DCSweepAcceptanceCriteria,
    DCSweepAnalysisConfig,
    DCSweepAnalysisResult,
    DCSweepEvaluationResult,
    HysteresisAcceptanceCriteria,
    HysteresisAnalysisConfig,
    HysteresisCycleInput,
    HysteresisEvaluationResult,
    MeasurementBatch,
    PointDisposition,
    analyze_dc_sweep,
    analyze_hysteresis,
    evaluate_dc_sweep,
    evaluate_hysteresis,
)
from analog_validation.exports import (
    ResultExportBundle,
    build_dc_sweep_export,
    build_hysteresis_export,
    dump_result_export_csv,
    dump_result_export_json,
    parse_result_export_csv,
    parse_result_export_json,
)

NOW = datetime(2026, 8, 30, 22, 0, tzinfo=timezone.utc)


def measurement(
    record_id: str,
    channel: str,
    value: float | None,
    unit: MeasurementUnit,
    *,
    sequence: int,
    status: MeasurementStatus = MeasurementStatus.VALID,
    flags: frozenset[QualityFlag] = frozenset(),
) -> Measurement:
    return Measurement(
        record_id=record_id,
        raw_record_id=f"raw-{record_id}",
        timestamp=NOW + timedelta(milliseconds=sequence),
        channel=channel,
        value=value,
        unit=unit,
        status=status,
        source=EvidenceSource.HOST_TEST,
        quality_flags=flags,
    )


def metadata(
    test_type: str,
    raw_ids: tuple[str, ...],
    **overrides: Any,
) -> RunMetadata:
    values: dict[str, Any] = {
        "run_id": f"{test_type}-export-run",
        "test_type": test_type,
        "configuration_id": "export-fixture",
        "configuration_version": "1",
        "started_at": NOW,
        "ended_at": NOW + timedelta(seconds=1),
        "software_version": "0.1.0.dev0",
        "device_id": "host-fixture",
        "profile_name": "reference-output",
        "profile_version": "1",
        "evidence_source": EvidenceSource.HOST_TEST,
        "input_record_ids": raw_ids,
    }
    values.update(overrides)
    return RunMetadata(**values)


def raw_ids_from_dc(analysis: DCSweepAnalysisResult) -> tuple[str, ...]:
    values = (
        reference.raw_record_id
        for point in analysis.points
        for reference in (
            point.input_decision.reference,
            point.output_decision.reference,
        )
    )
    return tuple(dict.fromkeys(values))


def dc_evaluation(*, complete: bool = True) -> DCSweepEvaluationResult:
    records: list[Measurement] = []
    inputs = [100.0, 200.0, 300.0, 400.0] if complete else [100.0, 200.0]
    outputs = [212.0, 412.0, 5000.0, 812.0] if complete else [212.0, 412.0]
    for index, (input_value, output_value) in enumerate(zip(inputs, outputs, strict=True)):
        records.extend(
            (
                measurement(
                    f"dc-in-{index}",
                    "vin",
                    input_value,
                    MeasurementUnit.MILLIVOLT,
                    sequence=index * 2,
                ),
                measurement(
                    f"dc-out-{index}",
                    "vout",
                    output_value,
                    MeasurementUnit.MILLIVOLT,
                    sequence=index * 2 + 1,
                ),
            )
        )
    analysis = analyze_dc_sweep(
        MeasurementBatch(tuple(records)),
        DCSweepAnalysisConfig("vin", "vout", -1000, 1000),
    )
    criteria = (
        DCSweepAcceptanceCriteria(
            "dc-export", "1", 2.0, 0.05, 20, 0.99, 5, 3
        )
        if complete
        else None
    )
    return evaluate_dc_sweep(
        analysis,
        criteria,
        metadata(DC_SWEEP_TEST_TYPE, raw_ids_from_dc(analysis)),
    )


def directional_batch(
    prefix: str,
    values: tuple[float, ...],
    states: tuple[int, ...],
    *,
    suspect_input: int | None = None,
    invalid_state: int | None = None,
) -> MeasurementBatch:
    records: list[Measurement] = []
    for index, (value, state) in enumerate(zip(values, states, strict=True)):
        input_status = (
            MeasurementStatus.SUSPECT
            if index == suspect_input
            else MeasurementStatus.VALID
        )
        input_flags = (
            frozenset({QualityFlag.TIME_ANOMALY})
            if index == suspect_input
            else frozenset()
        )
        state_status = (
            MeasurementStatus.INVALID
            if index == invalid_state
            else MeasurementStatus.VALID
        )
        state_flags = (
            frozenset({QualityFlag.MISSING})
            if index == invalid_state
            else frozenset()
        )
        records.extend(
            (
                measurement(
                    f"{prefix}-in-{index}",
                    "vin",
                    value,
                    MeasurementUnit.MILLIVOLT,
                    sequence=index * 2,
                    status=input_status,
                    flags=input_flags,
                ),
                measurement(
                    f"{prefix}-state-{index}",
                    "state",
                    None if index == invalid_state else float(state),
                    MeasurementUnit.BOOLEAN,
                    sequence=index * 2 + 1,
                    status=state_status,
                    flags=state_flags,
                ),
            )
        )
    return MeasurementBatch(tuple(records))


def hysteresis_evaluation(
    *, complete: bool = True, with_quality_issues: bool = False
) -> HysteresisEvaluationResult:
    if complete:
        rising = directional_batch(
            "rise",
            (1600, 1700, 1790, 1810, 1900),
            (0, 0, 0, 1, 1),
            suspect_input=1 if with_quality_issues else None,
        )
        falling = directional_batch(
            "fall",
            (1900, 1600, 1550, 1490, 1400),
            (1, 1, 1, 0, 0),
            invalid_state=2 if with_quality_issues else None,
        )
    else:
        rising = directional_batch("rise", (1600, 1800, 1900), (0, 0, 0))
        falling = directional_batch("fall", (1900, 1500, 1400), (1, 0, 0))
    analysis = analyze_hysteresis(
        (HysteresisCycleInput(0, rising, falling),),
        HysteresisAnalysisConfig("vin", "state"),
    )
    raw_ids = tuple(
        dict.fromkeys(
            reference.raw_record_id
            for cycle in analysis.cycles
            for point in cycle.rising_points + cycle.falling_points
            for reference in (point.input_decision.reference, point.state_reference)
        )
    )
    criteria = (
        HysteresisAcceptanceCriteria(
            "hysteresis-export", "1", 1750, 1850, 1450, 1600, 200, 400, 100, 1
        )
        if complete
        else None
    )
    return evaluate_hysteresis(
        analysis,
        criteria,
        metadata(HYSTERESIS_TEST_TYPE, raw_ids),
    )


def value_map(bundle: ResultExportBundle) -> dict[str, object]:
    return {value.name: value.value for value in bundle.metrics}


def test_dc_builder_preserves_fit_criteria_exclusion_and_round_trips() -> None:
    evaluation = dc_evaluation()
    bundle = build_dc_sweep_export(
        evaluation,
        ("HOST_TEST fixture only; no physical AFE was measured.",),
    )
    assert bundle.test_run_result is evaluation.test_run_result
    assert bundle.criteria_id == "dc-export"
    assert value_map(bundle)["gain"] == pytest.approx(2.0)
    assert value_map(bundle)["excluded_points"] == 1
    assert bundle.points[2].disposition is PointDisposition.EXCLUDED
    assert "point:HIGH_SATURATION" in bundle.points[2].exclusion_reasons
    assert bundle.points[0].values[2].name == "predicted_output"
    assert parse_result_export_json(dump_result_export_json(bundle)) == bundle
    assert parse_result_export_csv(dump_result_export_csv(bundle)) == bundle


def test_dc_builder_preserves_incomplete_result_without_inventing_fit() -> None:
    bundle = build_dc_sweep_export(
        dc_evaluation(complete=False),
        ("Insufficient points and no acceptance criteria.",),
    )
    assert bundle.criteria_id is None
    assert not bundle.criterion_results
    assert set(value_map(bundle)) == {
        "included_points",
        "excluded_points",
        "invalid_points",
    }
    assert all(len(point.values) == 2 for point in bundle.points)


def test_hysteresis_builder_preserves_quality_state_metrics_and_round_trips() -> None:
    evaluation = hysteresis_evaluation()
    bundle = build_hysteresis_export(
        evaluation,
        ("HOST_TEST fixture thresholds are not bench measurements.",),
    )
    assert bundle.test_run_result is evaluation.test_run_result
    assert bundle.criteria_id == "hysteresis-export"
    assert value_map(bundle)["complete_cycles"] == 1
    assert value_map(bundle)["excluded_points"] == 0
    assert value_map(bundle)["invalid_points"] == 0
    assert parse_result_export_json(dump_result_export_json(bundle)) == bundle
    assert parse_result_export_csv(dump_result_export_csv(bundle)) == bundle


def test_hysteresis_builder_preserves_excluded_and_invalid_point_reasons() -> None:
    bundle = build_hysteresis_export(
        hysteresis_evaluation(with_quality_issues=True),
        ("Quality issues make threshold calculation incomplete.",),
    )
    assert "complete_cycles" not in value_map(bundle)
    assert value_map(bundle)["excluded_points"] == 1
    assert value_map(bundle)["invalid_points"] == 1
    assert bundle.points[1].disposition is PointDisposition.EXCLUDED
    assert "input:TIME_ANOMALY" in bundle.points[1].quality_flags
    assert bundle.points[7].disposition is PointDisposition.INVALID
    assert "state:MISSING" in bundle.points[7].quality_flags


def test_hysteresis_builder_preserves_incomplete_result_without_summary() -> None:
    bundle = build_hysteresis_export(
        hysteresis_evaluation(complete=False),
        ("Rising transition is missing.",),
    )
    assert bundle.criteria_id is None
    assert not bundle.criterion_results
    assert "complete_cycles" not in value_map(bundle)


@pytest.mark.parametrize(
    ("builder", "message"),
    (
        (build_dc_sweep_export, "DCSweepEvaluationResult"),
        (build_hysteresis_export, "HysteresisEvaluationResult"),
    ),
)
def test_builders_reject_the_wrong_evaluation_type(builder: object, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        cast(Any, builder)(object(), ("limitation",))


def test_builder_rejects_a_string_as_the_limitations_collection() -> None:
    with pytest.raises(ValidationError, match="limitations must be an iterable"):
        build_dc_sweep_export(
            dc_evaluation(), cast(Any, "not-a-collection")
        )
