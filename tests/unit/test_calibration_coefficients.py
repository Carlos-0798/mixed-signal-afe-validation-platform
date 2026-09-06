"""Tests for strict versioned calibration-coefficient persistence."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from analog_validation.analysis import (
    CalibrationFitConfig,
    MeasurementBatch,
    fit_linear_calibration,
)
from analog_validation.domain import (
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
)
from analog_validation.errors import ValidationError
from analog_validation.exports import (
    CALIBRATION_COEFFICIENTS_SCHEMA_VERSION,
    MAX_CALIBRATION_COEFFICIENT_BYTES,
    ResultExportExistsError,
    ResultExportFormatError,
    ResultExportLimitError,
    UnsupportedResultExportVersion,
    calibration_coefficients_from_dict,
    calibration_coefficients_to_dict,
    dump_calibration_coefficients_json,
    load_calibration_coefficients_json,
    parse_calibration_coefficients_json,
    write_calibration_coefficients_json,
)

NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)


def _coefficients():
    def batch(prefix: str, channel: str, values: tuple[float, ...]) -> MeasurementBatch:
        return MeasurementBatch(
            tuple(
                Measurement(
                    f"{prefix}-{index}",
                    f"raw-{prefix}-{index}",
                    NOW + timedelta(seconds=index),
                    channel,
                    value,
                    MeasurementUnit.MILLIVOLT,
                    MeasurementStatus.VALID,
                    EvidenceSource.CSV_REPLAY,
                )
                for index, value in enumerate(values)
            )
        )

    result = fit_linear_calibration(
        batch("observed", "adc.raw", (0.0, 50.0, 100.0)),
        batch("reference", "dmm.reference", (10.0, 110.0, 210.0)),
        CalibrationFitConfig("adc.raw", "dmm.reference", "adc-linear", "2026.09"),
    )
    assert result.coefficients is not None
    return result.coefficients


def test_coefficient_json_round_trip_is_deterministic_and_complete() -> None:
    coefficients = _coefficients()
    document = calibration_coefficients_to_dict(coefficients)
    assert document["schema_version"] == CALIBRATION_COEFFICIENTS_SCHEMA_VERSION
    assert document["scale"] == pytest.approx(2.0)
    assert document["offset"] == pytest.approx(10.0)
    text = dump_calibration_coefficients_json(coefficients)
    assert parse_calibration_coefficients_json(text) == coefficients
    assert calibration_coefficients_from_dict(json.loads(text)) == coefficients
    assert dump_calibration_coefficients_json(coefficients) == text


def test_coefficient_file_write_load_and_no_overwrite(tmp_path: Path) -> None:
    coefficients = _coefficients()
    path = tmp_path / "adc-linear.json"
    assert write_calibration_coefficients_json(path, coefficients) == path
    assert load_calibration_coefficients_json(path) == coefficients
    with pytest.raises(ResultExportExistsError):
        write_calibration_coefficients_json(path, coefficients)
    write_calibration_coefficients_json(path, coefficients, overwrite=True)
    assert load_calibration_coefficients_json(path) == coefficients


@pytest.mark.parametrize(
    ("mutate", "error_type"),
    [
        (
            lambda value: value.update(schema_version="future"),
            UnsupportedResultExportVersion,
        ),
        (
            lambda value: value.update(analysis_schema_version="future"),
            ResultExportFormatError,
        ),
        (lambda value: value.update(method="unknown"), ResultExportFormatError),
        (lambda value: value.update(scale=True), ResultExportFormatError),
        (lambda value: value.update(unit="Hz"), ResultExportFormatError),
        (lambda value: value.pop("offset"), ResultExportFormatError),
        (
            lambda value: value["lineage"].update(observed_record_ids=[]),
            ResultExportFormatError,
        ),
    ],
)
def test_coefficient_document_rejects_schema_and_domain_tampering(
    mutate, error_type: type[Exception]
) -> None:
    document = calibration_coefficients_to_dict(_coefficients())
    mutate(document)
    with pytest.raises(error_type):
        calibration_coefficients_from_dict(document)


def test_coefficient_document_rejects_wrong_json_field_types_and_enum_values() -> None:
    with pytest.raises(ResultExportFormatError, match="must be an object"):
        calibration_coefficients_from_dict([])

    document = calibration_coefficients_to_dict(_coefficients())
    document["unexpected"] = "field"
    with pytest.raises(ResultExportFormatError, match="fields"):
        calibration_coefficients_from_dict(document)

    document = calibration_coefficients_to_dict(_coefficients())
    document["schema_version"] = 1
    with pytest.raises(ResultExportFormatError, match="must be a string"):
        calibration_coefficients_from_dict(document)

    document = calibration_coefficients_to_dict(_coefficients())
    lineage = document["lineage"]
    assert isinstance(lineage, dict)
    lineage["reference_record_ids"] = "not-an-array"
    with pytest.raises(ResultExportFormatError, match="array of strings"):
        calibration_coefficients_from_dict(document)

    document = calibration_coefficients_to_dict(_coefficients())
    document["observed_source"] = "NOT_A_SOURCE"
    with pytest.raises(ResultExportFormatError, match="unsupported value"):
        calibration_coefficients_from_dict(document)


def test_coefficient_parser_rejects_unsafe_or_unbounded_content() -> None:
    with pytest.raises(ResultExportFormatError, match="duplicate"):
        parse_calibration_coefficients_json(
            '{"schema_version":"calibration-coefficients.v1",'
            '"schema_version":"calibration-coefficients.v1"}'
        )
    with pytest.raises(ResultExportFormatError, match="non-finite"):
        parse_calibration_coefficients_json('{"scale":NaN}')
    with pytest.raises(ResultExportFormatError, match="NUL"):
        parse_calibration_coefficients_json("{}\x00")
    with pytest.raises(ResultExportLimitError):
        parse_calibration_coefficients_json(
            " " * (MAX_CALIBRATION_COEFFICIENT_BYTES + 1)
        )
    with pytest.raises(ResultExportFormatError, match="string"):
        parse_calibration_coefficients_json(1)  # type: ignore[arg-type]
    with pytest.raises(ResultExportFormatError, match="UTF-8"):
        parse_calibration_coefficients_json("\ud800")
    with pytest.raises(ValidationError, match="LinearCalibrationCoefficients"):
        calibration_coefficients_to_dict(object())  # type: ignore[arg-type]
