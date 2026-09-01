"""Tests for provenance-aware measurements."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from typing import cast

import pytest

from analog_validation import (
    MEASUREMENT_SCHEMA_VERSION,
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
    QualityFlag,
    ValidationError,
)


def make_measurement(
    *,
    record_id: str = "record-001",
    raw_record_id: str = "record-001",
    timestamp: datetime = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
    channel: str = "afe.ch0.output",
    value: float | None = 1250.0,
    unit: MeasurementUnit = MeasurementUnit.MILLIVOLT,
    status: MeasurementStatus = MeasurementStatus.VALID,
    source: EvidenceSource = EvidenceSource.SYNTHETIC,
    quality_flags: frozenset[QualityFlag] = frozenset(),
    schema_version: str = MEASUREMENT_SCHEMA_VERSION,
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
        schema_version=schema_version,
    )


def test_evidence_source_values_are_stable() -> None:
    assert [source.value for source in EvidenceSource] == [
        "THEORY",
        "SYNTHETIC",
        "CSV_REPLAY",
        "SPICE_IDEAL",
        "SPICE_MODEL",
        "HOST_TEST",
        "BENCH_DMM",
        "BENCH_CONTROLLER",
        "BENCH_SCOPE",
    ]


@pytest.mark.parametrize(
    "source",
    [
        EvidenceSource.BENCH_DMM,
        EvidenceSource.BENCH_CONTROLLER,
        EvidenceSource.BENCH_SCOPE,
    ],
)
def test_only_bench_sources_are_marked_as_bench_evidence(
    source: EvidenceSource,
) -> None:
    assert source.is_bench_evidence
    assert make_measurement(source=source).is_bench_evidence


@pytest.mark.parametrize(
    "source",
    [
        EvidenceSource.THEORY,
        EvidenceSource.SYNTHETIC,
        EvidenceSource.CSV_REPLAY,
        EvidenceSource.SPICE_IDEAL,
        EvidenceSource.SPICE_MODEL,
        EvidenceSource.HOST_TEST,
    ],
)
def test_non_bench_sources_cannot_become_bench_evidence(
    source: EvidenceSource,
) -> None:
    assert not source.is_bench_evidence
    assert not make_measurement(source=source).is_bench_evidence


def test_valid_measurement_is_immutable_and_has_explicit_provenance() -> None:
    measurement = make_measurement()

    assert measurement.value == 1250.0
    assert measurement.source is EvidenceSource.SYNTHETIC
    assert measurement.status is MeasurementStatus.VALID
    assert measurement.quality_flags == frozenset()
    assert measurement.schema_version == "measurement.v1"
    assert not measurement.is_derived

    with pytest.raises(FrozenInstanceError):
        measurement.value = 1300.0  # type: ignore[misc]


def test_derived_measurement_preserves_raw_record_reference() -> None:
    measurement = make_measurement(
        record_id="calibrated-001",
        raw_record_id="raw-001",
    )

    assert measurement.is_derived
    assert measurement.raw_record_id == "raw-001"


def test_timestamp_is_normalized_to_utc() -> None:
    eastern = timezone(timedelta(hours=-4))
    measurement = make_measurement(
        timestamp=datetime(2026, 8, 29, 8, 0, tzinfo=eastern)
    )

    assert measurement.timestamp == datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    assert measurement.timestamp.tzinfo is timezone.utc


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        make_measurement(timestamp=datetime(2026, 8, 29, 12, 0))  # noqa: DTZ001


def test_non_datetime_timestamp_is_rejected() -> None:
    invalid = cast(datetime, "2026-08-29T12:00:00Z")

    with pytest.raises(ValidationError, match="datetime"):
        make_measurement(timestamp=invalid)


@pytest.mark.parametrize("record_id", ["", " record-001", "record-001 "])
def test_record_id_must_be_nonempty_and_trimmed(record_id: str) -> None:
    with pytest.raises(ValidationError, match="record_id"):
        make_measurement(record_id=record_id)


@pytest.mark.parametrize("raw_record_id", ["", " raw-001", "raw-001 "])
def test_raw_record_id_must_be_nonempty_and_trimmed(raw_record_id: str) -> None:
    with pytest.raises(ValidationError, match="raw_record_id"):
        make_measurement(raw_record_id=raw_record_id)


@pytest.mark.parametrize("channel", ["", " afe.ch0", "afe.ch0 "])
def test_channel_must_be_nonempty_and_trimmed(channel: str) -> None:
    with pytest.raises(ValidationError, match="channel"):
        make_measurement(channel=channel)


def test_unknown_unit_is_rejected() -> None:
    unknown = cast(MeasurementUnit, "millivolts")

    with pytest.raises(ValidationError, match="unit"):
        make_measurement(unit=unknown)


def test_missing_or_unknown_source_is_rejected() -> None:
    missing = cast(EvidenceSource, None)

    with pytest.raises(ValidationError, match="source"):
        make_measurement(source=missing)


def test_unknown_status_is_rejected() -> None:
    unknown = cast(MeasurementStatus, "GOOD")

    with pytest.raises(ValidationError, match="status"):
        make_measurement(status=unknown)


def test_quality_flags_are_frozen_on_construction() -> None:
    mutable_input = {QualityFlag.SATURATED}
    measurement = make_measurement(
        status=MeasurementStatus.SUSPECT,
        quality_flags=cast(frozenset[QualityFlag], mutable_input),
    )
    mutable_input.clear()

    assert measurement.quality_flags == frozenset({QualityFlag.SATURATED})


def test_unknown_quality_flag_is_rejected() -> None:
    flags = cast(frozenset[QualityFlag], frozenset({"CLIPPED"}))

    with pytest.raises(ValidationError, match="unknown flag"):
        make_measurement(
            status=MeasurementStatus.SUSPECT,
            quality_flags=flags,
        )


def test_non_iterable_quality_flags_are_rejected() -> None:
    invalid = cast(frozenset[QualityFlag], None)

    with pytest.raises(ValidationError, match="iterable"):
        make_measurement(quality_flags=invalid)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_value_requires_explicit_invalid_marking(value: float) -> None:
    with pytest.raises(ValidationError, match="NON_FINITE"):
        make_measurement(value=value)

    measurement = make_measurement(
        value=value,
        status=MeasurementStatus.INVALID,
        quality_flags=frozenset({QualityFlag.NON_FINITE}),
    )

    assert measurement.status is MeasurementStatus.INVALID
    assert QualityFlag.NON_FINITE in measurement.quality_flags


def test_missing_value_requires_explicit_invalid_marking() -> None:
    with pytest.raises(ValidationError, match="MISSING"):
        make_measurement(value=None)

    measurement = make_measurement(
        value=None,
        status=MeasurementStatus.INVALID,
        quality_flags=frozenset({QualityFlag.MISSING}),
    )

    assert measurement.value is None
    assert measurement.status is MeasurementStatus.INVALID


@pytest.mark.parametrize(
    ("value", "flag"),
    [
        (None, QualityFlag.MISSING),
        (math.nan, QualityFlag.NON_FINITE),
    ],
)
def test_missing_or_non_finite_value_cannot_be_suspect(
    value: float | None,
    flag: QualityFlag,
) -> None:
    with pytest.raises(ValidationError, match="must be INVALID"):
        make_measurement(
            value=value,
            status=MeasurementStatus.SUSPECT,
            quality_flags=frozenset({flag}),
        )


def test_missing_flag_cannot_be_attached_to_numeric_value() -> None:
    with pytest.raises(ValidationError, match="MISSING"):
        make_measurement(
            status=MeasurementStatus.INVALID,
            quality_flags=frozenset({QualityFlag.MISSING}),
        )


def test_non_finite_flag_cannot_be_attached_to_finite_value() -> None:
    with pytest.raises(ValidationError, match="NON_FINITE"):
        make_measurement(
            status=MeasurementStatus.INVALID,
            quality_flags=frozenset({QualityFlag.NON_FINITE}),
        )


def test_valid_status_rejects_quality_flags() -> None:
    with pytest.raises(ValidationError, match="VALID"):
        make_measurement(quality_flags=frozenset({QualityFlag.SATURATED}))


def test_suspect_status_requires_quality_flag() -> None:
    with pytest.raises(ValidationError, match="SUSPECT"):
        make_measurement(status=MeasurementStatus.SUSPECT)


def test_invalid_status_requires_quality_flag() -> None:
    with pytest.raises(ValidationError, match="INVALID"):
        make_measurement(status=MeasurementStatus.INVALID)


def test_suspect_and_invalid_finite_measurements_are_supported() -> None:
    suspect = make_measurement(
        status=MeasurementStatus.SUSPECT,
        quality_flags=frozenset({QualityFlag.TIME_ANOMALY}),
    )
    invalid = make_measurement(
        status=MeasurementStatus.INVALID,
        quality_flags=frozenset({QualityFlag.OUT_OF_RANGE}),
    )

    assert suspect.status is MeasurementStatus.SUSPECT
    assert invalid.status is MeasurementStatus.INVALID


@pytest.mark.parametrize("value", [True, "1250", object()])
def test_value_must_be_numeric_or_missing(value: object) -> None:
    with pytest.raises(ValidationError, match="numeric"):
        make_measurement(value=cast(float, value))


def test_unknown_schema_version_is_rejected() -> None:
    with pytest.raises(ValidationError, match="schema version"):
        make_measurement(schema_version="measurement.v2")
