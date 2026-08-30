"""Tests for Phase 3 common analysis semantics."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError
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
    ANALYSIS_COMMON_SCHEMA_VERSION,
    DEFAULT_ANALYSIS_QUALITY_POLICY,
    AnalysisQualityPolicy,
    AnalysisRecordReference,
    MeasurementBatch,
    MeasurementDecision,
    PointDisposition,
    PointExclusionReason,
    assess_voltage_measurement,
    normalize_voltage,
)

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def make_measurement(
    *,
    record_id: str = "measurement-1",
    raw_record_id: str = "measurement-1",
    timestamp: datetime = NOW,
    channel: str = "afe.ch0.output",
    value: float | None = 1250.0,
    unit: MeasurementUnit = MeasurementUnit.MILLIVOLT,
    status: MeasurementStatus = MeasurementStatus.VALID,
    source: EvidenceSource = EvidenceSource.SYNTHETIC,
    quality_flags: frozenset[QualityFlag] = frozenset(),
) -> Measurement:
    return Measurement(
        record_id=record_id,
        raw_record_id=raw_record_id,
        timestamp=timestamp,
        channel=channel,
        value=value,
        unit=unit,
        status=status,
        source=source,
        quality_flags=quality_flags,
    )


def make_reference(**overrides: Any) -> AnalysisRecordReference:
    values: dict[str, Any] = {
        "record_id": "measurement-1",
        "raw_record_id": "raw-1",
        "timestamp": NOW,
        "channel": "afe.ch0.output",
        "source": EvidenceSource.SYNTHETIC,
    }
    values.update(overrides)
    return AnalysisRecordReference(**values)


def make_decision(**overrides: Any) -> MeasurementDecision:
    values: dict[str, Any] = {
        "reference": make_reference(),
        "original_unit": MeasurementUnit.MILLIVOLT,
        "normalized_value": 1250.0,
        "normalized_unit": MeasurementUnit.MILLIVOLT,
        "status": MeasurementStatus.VALID,
        "observed_quality_flags": frozenset(),
        "disposition": PointDisposition.INCLUDED,
        "exclusion_reasons": (),
    }
    values.update(overrides)
    return MeasurementDecision(**values)


def test_public_schema_enums_and_default_policy_are_stable() -> None:
    assert ANALYSIS_COMMON_SCHEMA_VERSION == "analysis-common.v1"
    assert [value.value for value in PointDisposition] == [
        "INCLUDED",
        "EXCLUDED",
        "INVALID",
    ]
    assert [value.value for value in PointExclusionReason] == [
        "MISSING_VALUE",
        "NON_FINITE_VALUE",
        "INVALID_STATUS",
        "SUSPECT_STATUS",
        "SATURATED",
        "OUT_OF_RANGE",
        "TIME_ANOMALY",
        "COMMUNICATION_ERROR",
        "DEVICE_FAULT",
    ]
    assert DEFAULT_ANALYSIS_QUALITY_POLICY.allowed_suspect_flags == frozenset()


def test_quality_policy_freezes_an_explicit_allowlist() -> None:
    mutable = {QualityFlag.SATURATED, QualityFlag.TIME_ANOMALY}
    policy = AnalysisQualityPolicy(cast(frozenset[QualityFlag], mutable))
    mutable.clear()

    assert policy.allowed_suspect_flags == frozenset(
        {QualityFlag.SATURATED, QualityFlag.TIME_ANOMALY}
    )
    with pytest.raises(FrozenInstanceError):
        policy.schema_version = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "flags",
    [
        None,
        "SATURATED",
        [[QualityFlag.SATURATED]],
        {"SATURATED"},
    ],
)
def test_quality_policy_rejects_invalid_allowlists(flags: object) -> None:
    with pytest.raises(ValidationError, match="allowed_suspect_flags"):
        AnalysisQualityPolicy(cast(frozenset[QualityFlag], flags))


@pytest.mark.parametrize("flag", [QualityFlag.MISSING, QualityFlag.NON_FINITE])
def test_quality_policy_never_allows_unavailable_values(flag: QualityFlag) -> None:
    with pytest.raises(ValidationError, match="never be allowed"):
        AnalysisQualityPolicy(frozenset({flag}))


def test_quality_policy_rejects_unknown_schema() -> None:
    with pytest.raises(ValidationError, match="unsupported analysis common"):
        AnalysisQualityPolicy(schema_version="analysis-common.v2")


def test_record_reference_copies_lineage_normalizes_utc_and_preserves_source() -> None:
    eastern = timezone(timedelta(hours=-4))
    measurement = make_measurement(
        record_id="derived-1",
        raw_record_id="raw-1",
        timestamp=datetime(2026, 8, 30, 8, 0, tzinfo=eastern),
        source=EvidenceSource.BENCH_DMM,
    )
    reference = AnalysisRecordReference.from_measurement(measurement)

    assert reference.record_id == "derived-1"
    assert reference.raw_record_id == "raw-1"
    assert reference.timestamp == NOW
    assert reference.channel == measurement.channel
    assert reference.source is EvidenceSource.BENCH_DMM
    assert reference.is_derived
    assert reference.is_bench_evidence


def test_record_reference_can_identify_non_derived_non_bench_data() -> None:
    reference = AnalysisRecordReference.from_measurement(make_measurement())

    assert not reference.is_derived
    assert not reference.is_bench_evidence


@pytest.mark.parametrize("field", ["record_id", "raw_record_id", "channel"])
@pytest.mark.parametrize("value", ["", " bad", "bad "])
def test_record_reference_rejects_bad_identifiers(field: str, value: str) -> None:
    with pytest.raises(ValidationError, match=field):
        make_reference(**{field: value})


def test_record_reference_rejects_bad_timestamp_source_schema_and_input() -> None:
    with pytest.raises(ValidationError, match="datetime"):
        make_reference(timestamp=cast(datetime, "2026-08-30"))
    with pytest.raises(ValidationError, match="timezone"):
        make_reference(timestamp=datetime(2026, 8, 30))  # noqa: DTZ001
    with pytest.raises(ValidationError, match="EvidenceSource"):
        make_reference(source=cast(EvidenceSource, "SYNTHETIC"))
    with pytest.raises(ValidationError, match="unsupported analysis common"):
        make_reference(schema_version="analysis-common.v2")
    with pytest.raises(ValidationError, match="must be a Measurement"):
        AnalysisRecordReference.from_measurement(cast(Measurement, object()))


def test_measurement_batch_freezes_order_and_exposes_lineage() -> None:
    values = [
        make_measurement(record_id="derived-1", raw_record_id="raw-1"),
        make_measurement(record_id="derived-2", raw_record_id="raw-1"),
    ]
    batch = MeasurementBatch(cast(tuple[Measurement, ...], values))
    values.clear()

    assert len(batch.measurements) == 2
    assert batch.evidence_source is EvidenceSource.SYNTHETIC
    assert batch.record_ids == ("derived-1", "derived-2")
    assert batch.raw_record_ids == ("raw-1", "raw-1")
    assert tuple(item.record_id for item in batch.references) == batch.record_ids
    assert not batch.is_bench_evidence


def test_measurement_batch_preserves_bench_classification() -> None:
    batch = MeasurementBatch(
        (make_measurement(source=EvidenceSource.BENCH_CONTROLLER),)
    )

    assert batch.is_bench_evidence


@pytest.mark.parametrize("values", [None, "measurement", b"measurement"])
def test_measurement_batch_rejects_non_iterables_and_text(values: object) -> None:
    with pytest.raises(ValidationError, match="iterable"):
        MeasurementBatch(cast(tuple[Measurement, ...], values))


def test_measurement_batch_rejects_empty_wrong_duplicate_or_mixed_records() -> None:
    with pytest.raises(ValidationError, match="cannot be empty"):
        MeasurementBatch(())
    with pytest.raises(ValidationError, match="Measurement values"):
        MeasurementBatch(cast(tuple[Measurement, ...], (object(),)))

    first = make_measurement()
    with pytest.raises(ValidationError, match="record IDs must be unique"):
        MeasurementBatch((first, first))
    with pytest.raises(ValidationError, match="one evidence source"):
        MeasurementBatch(
            (
                first,
                make_measurement(
                    record_id="measurement-2",
                    source=EvidenceSource.CSV_REPLAY,
                ),
            )
        )
    with pytest.raises(ValidationError, match="unsupported analysis common"):
        MeasurementBatch((first,), schema_version="analysis-common.v2")


@pytest.mark.parametrize(
    ("value", "unit", "target", "expected"),
    [
        (1.25, MeasurementUnit.VOLT, MeasurementUnit.MILLIVOLT, 1250.0),
        (1250, MeasurementUnit.MILLIVOLT, MeasurementUnit.VOLT, 1.25),
        (1250, MeasurementUnit.MILLIVOLT, MeasurementUnit.MILLIVOLT, 1250.0),
        (1, MeasurementUnit.VOLT, MeasurementUnit.VOLT, 1.0),
    ],
)
def test_normalize_voltage_is_explicit_and_reversible(
    value: float,
    unit: MeasurementUnit,
    target: MeasurementUnit,
    expected: float,
) -> None:
    assert normalize_voltage(value, unit, target) == pytest.approx(expected)


@pytest.mark.parametrize("value", [True, "1.25", object()])
def test_normalize_voltage_rejects_non_numeric_values(value: object) -> None:
    with pytest.raises(ValidationError, match="numeric"):
        normalize_voltage(cast(float, value), MeasurementUnit.VOLT)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_normalize_voltage_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(ValidationError, match="finite"):
        normalize_voltage(value, MeasurementUnit.VOLT)


def test_normalize_voltage_rejects_unknown_and_non_voltage_units() -> None:
    with pytest.raises(ValidationError, match="unit must be V or mV"):
        normalize_voltage(1.0, MeasurementUnit.AMPERE)
    with pytest.raises(ValidationError, match="unit must be V or mV"):
        normalize_voltage(1.0, cast(MeasurementUnit, "VOLT"))
    with pytest.raises(ValidationError, match="target_unit must be V or mV"):
        normalize_voltage(1.0, MeasurementUnit.VOLT, MeasurementUnit.ADC_COUNT)


def test_assess_valid_voltage_includes_and_normalizes_without_relabeling() -> None:
    measurement = make_measurement(
        value=1.25,
        unit=MeasurementUnit.VOLT,
        source=EvidenceSource.CSV_REPLAY,
    )
    decision = assess_voltage_measurement(measurement)

    assert decision.reference.record_id == measurement.record_id
    assert decision.reference.source is EvidenceSource.CSV_REPLAY
    assert decision.original_unit is MeasurementUnit.VOLT
    assert decision.normalized_value == pytest.approx(1250.0)
    assert decision.normalized_unit is MeasurementUnit.MILLIVOLT
    assert decision.disposition is PointDisposition.INCLUDED
    assert decision.exclusion_reasons == ()


def test_default_policy_excludes_suspect_measurement_with_exact_reasons() -> None:
    measurement = make_measurement(
        status=MeasurementStatus.SUSPECT,
        quality_flags=frozenset(
            {QualityFlag.SATURATED, QualityFlag.TIME_ANOMALY}
        ),
    )
    decision = assess_voltage_measurement(measurement)

    assert decision.normalized_value == 1250.0
    assert decision.disposition is PointDisposition.EXCLUDED
    assert decision.exclusion_reasons == (
        PointExclusionReason.SUSPECT_STATUS,
        PointExclusionReason.SATURATED,
        PointExclusionReason.TIME_ANOMALY,
    )


@pytest.mark.parametrize(
    ("value", "flag", "reason"),
    [
        (None, QualityFlag.MISSING, PointExclusionReason.MISSING_VALUE),
        (math.nan, QualityFlag.NON_FINITE, PointExclusionReason.NON_FINITE_VALUE),
    ],
)
def test_invalid_unavailable_measurement_has_no_normalized_value(
    value: float | None,
    flag: QualityFlag,
    reason: PointExclusionReason,
) -> None:
    decision = assess_voltage_measurement(
        make_measurement(
            value=value,
            status=MeasurementStatus.INVALID,
            quality_flags=frozenset({flag}),
        )
    )

    assert decision.normalized_value is None
    assert decision.disposition is PointDisposition.INVALID
    assert decision.exclusion_reasons == (
        PointExclusionReason.INVALID_STATUS,
        reason,
    )


def test_invalid_finite_measurement_preserves_value_and_all_quality_reasons() -> None:
    decision = assess_voltage_measurement(
        make_measurement(
            status=MeasurementStatus.INVALID,
            quality_flags=frozenset(
                {
                    QualityFlag.OUT_OF_RANGE,
                    QualityFlag.COMMUNICATION_ERROR,
                    QualityFlag.DEVICE_FAULT,
                }
            ),
        )
    )

    assert decision.normalized_value == 1250.0
    assert decision.exclusion_reasons == (
        PointExclusionReason.INVALID_STATUS,
        PointExclusionReason.OUT_OF_RANGE,
        PointExclusionReason.COMMUNICATION_ERROR,
        PointExclusionReason.DEVICE_FAULT,
    )


def test_explicit_policy_can_include_only_allowlisted_suspect_flags() -> None:
    measurement = make_measurement(
        status=MeasurementStatus.SUSPECT,
        quality_flags=frozenset(
            {QualityFlag.SATURATED, QualityFlag.TIME_ANOMALY}
        ),
    )
    all_allowed = AnalysisQualityPolicy(
        frozenset({QualityFlag.SATURATED, QualityFlag.TIME_ANOMALY})
    )
    partially_allowed = AnalysisQualityPolicy(
        frozenset({QualityFlag.SATURATED})
    )

    included = assess_voltage_measurement(measurement, all_allowed)
    excluded = assess_voltage_measurement(measurement, partially_allowed)

    assert included.disposition is PointDisposition.INCLUDED
    assert included.observed_quality_flags == measurement.quality_flags
    assert included.exclusion_reasons == ()
    assert excluded.disposition is PointDisposition.EXCLUDED
    assert excluded.exclusion_reasons == (
        PointExclusionReason.SUSPECT_STATUS,
        PointExclusionReason.TIME_ANOMALY,
    )


def test_assess_voltage_measurement_validates_inputs_and_target_unit() -> None:
    with pytest.raises(ValidationError, match="must be a Measurement"):
        assess_voltage_measurement(cast(Measurement, object()))
    with pytest.raises(ValidationError, match="must be an AnalysisQualityPolicy"):
        assess_voltage_measurement(
            make_measurement(),
            cast(AnalysisQualityPolicy, object()),
        )
    with pytest.raises(ValidationError, match="measurement unit must be V or mV"):
        assess_voltage_measurement(
            make_measurement(unit=MeasurementUnit.AMPERE)
        )
    with pytest.raises(ValidationError, match="target_unit must be V or mV"):
        assess_voltage_measurement(
            make_measurement(),
            target_unit=MeasurementUnit.ADC_COUNT,
        )


def test_measurement_decision_is_frozen_and_accepts_valid_constructed_data() -> None:
    decision = make_decision()

    assert decision.schema_version == ANALYSIS_COMMON_SCHEMA_VERSION
    with pytest.raises(FrozenInstanceError):
        decision.normalized_value = 0.0  # type: ignore[misc]


def test_measurement_decision_validates_reference_units_value_and_status() -> None:
    with pytest.raises(ValidationError, match="reference"):
        make_decision(reference=object())
    with pytest.raises(ValidationError, match="original_unit"):
        make_decision(original_unit=MeasurementUnit.AMPERE)
    with pytest.raises(ValidationError, match="normalized_unit"):
        make_decision(normalized_unit=MeasurementUnit.AMPERE)
    with pytest.raises(ValidationError, match="numeric or missing"):
        make_decision(normalized_value=True)
    with pytest.raises(ValidationError, match="finite"):
        make_decision(normalized_value=math.inf)
    with pytest.raises(ValidationError, match="MeasurementStatus"):
        make_decision(status="VALID")
    with pytest.raises(ValidationError, match="PointDisposition"):
        make_decision(disposition="INCLUDED")
    with pytest.raises(ValidationError, match="quality_policy"):
        make_decision(quality_policy=object())


@pytest.mark.parametrize(
    "flags",
    [None, "SATURATED", [[QualityFlag.SATURATED]], {"SATURATED"}],
)
def test_measurement_decision_rejects_invalid_quality_collections(
    flags: object,
) -> None:
    with pytest.raises(ValidationError, match="observed_quality_flags"):
        make_decision(observed_quality_flags=flags)


def test_measurement_decision_rejects_invalid_reason_collections() -> None:
    with pytest.raises(ValidationError, match="iterable"):
        make_decision(exclusion_reasons=None)
    with pytest.raises(ValidationError, match="unknown PointExclusionReason"):
        make_decision(exclusion_reasons=("SATURATED",))
    with pytest.raises(ValidationError, match="duplicates"):
        make_decision(
            status=MeasurementStatus.SUSPECT,
            observed_quality_flags=frozenset({QualityFlag.SATURATED}),
            disposition=PointDisposition.EXCLUDED,
            exclusion_reasons=(
                PointExclusionReason.SATURATED,
                PointExclusionReason.SATURATED,
            ),
        )


def test_measurement_decision_enforces_status_and_disposition_consistency() -> None:
    with pytest.raises(ValidationError, match="VALID decision"):
        make_decision(observed_quality_flags=frozenset({QualityFlag.SATURATED}))
    with pytest.raises(ValidationError, match="requires quality flags"):
        make_decision(
            status=MeasurementStatus.SUSPECT,
            disposition=PointDisposition.EXCLUDED,
            exclusion_reasons=(PointExclusionReason.SUSPECT_STATUS,),
        )
    with pytest.raises(ValidationError, match="INVALID disposition"):
        make_decision(
            disposition=PointDisposition.INVALID,
            exclusion_reasons=(PointExclusionReason.INVALID_STATUS,),
        )
    with pytest.raises(ValidationError, match="INVALID status"):
        make_decision(
            status=MeasurementStatus.INVALID,
            observed_quality_flags=frozenset({QualityFlag.OUT_OF_RANGE}),
        )
    with pytest.raises(ValidationError, match="EXCLUDED disposition"):
        make_decision(
            disposition=PointDisposition.EXCLUDED,
            exclusion_reasons=(PointExclusionReason.SUSPECT_STATUS,),
        )


def test_measurement_decision_enforces_reason_and_value_consistency() -> None:
    with pytest.raises(ValidationError, match="cannot have exclusion reasons"):
        make_decision(exclusion_reasons=(PointExclusionReason.SATURATED,))
    with pytest.raises(ValidationError, match="requires a finite value"):
        make_decision(normalized_value=None)
    with pytest.raises(ValidationError, match="requires reasons"):
        make_decision(
            status=MeasurementStatus.SUSPECT,
            observed_quality_flags=frozenset({QualityFlag.SATURATED}),
            disposition=PointDisposition.EXCLUDED,
        )
    with pytest.raises(ValidationError, match="must agree"):
        make_decision(
            normalized_value=None,
            status=MeasurementStatus.INVALID,
            observed_quality_flags=frozenset({QualityFlag.OUT_OF_RANGE}),
            disposition=PointDisposition.INVALID,
            exclusion_reasons=(
                PointExclusionReason.INVALID_STATUS,
                PointExclusionReason.OUT_OF_RANGE,
            ),
        )


def test_measurement_decision_requires_reasons_to_match_quality_flags() -> None:
    with pytest.raises(ValidationError, match="every quality flag"):
        make_decision(
            status=MeasurementStatus.INVALID,
            observed_quality_flags=frozenset({QualityFlag.OUT_OF_RANGE}),
            disposition=PointDisposition.INVALID,
            exclusion_reasons=(
                PointExclusionReason.INVALID_STATUS,
                PointExclusionReason.DEVICE_FAULT,
            ),
        )
    with pytest.raises(ValidationError, match="explicit quality policy"):
        make_decision(
            status=MeasurementStatus.SUSPECT,
            observed_quality_flags=frozenset({QualityFlag.SATURATED}),
        )
    included = make_decision(
        status=MeasurementStatus.SUSPECT,
        observed_quality_flags=frozenset({QualityFlag.SATURATED}),
        quality_policy=AnalysisQualityPolicy(
            frozenset({QualityFlag.SATURATED})
        ),
    )
    assert included.disposition is PointDisposition.INCLUDED
    with pytest.raises(ValidationError, match="disallowed quality flags"):
        make_decision(
            status=MeasurementStatus.SUSPECT,
            observed_quality_flags=frozenset({QualityFlag.SATURATED}),
            disposition=PointDisposition.EXCLUDED,
            exclusion_reasons=(PointExclusionReason.SUSPECT_STATUS,),
        )
    with pytest.raises(ValidationError, match="disallowed quality flags"):
        make_decision(
            status=MeasurementStatus.SUSPECT,
            observed_quality_flags=frozenset({QualityFlag.SATURATED}),
            disposition=PointDisposition.EXCLUDED,
            exclusion_reasons=(
                PointExclusionReason.SUSPECT_STATUS,
                PointExclusionReason.TIME_ANOMALY,
            ),
        )
    with pytest.raises(ValidationError, match="must agree"):
        make_decision(
            status=MeasurementStatus.INVALID,
            observed_quality_flags=frozenset({QualityFlag.MISSING}),
            disposition=PointDisposition.INVALID,
            exclusion_reasons=(
                PointExclusionReason.INVALID_STATUS,
                PointExclusionReason.MISSING_VALUE,
            ),
        )


def test_measurement_decision_rejects_unknown_schema() -> None:
    with pytest.raises(ValidationError, match="unsupported analysis common"):
        make_decision(schema_version="analysis-common.v2")
