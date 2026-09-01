"""Frozen AFE v1 compatibility records and expected rejection behavior."""

from __future__ import annotations

import base64
import csv
import dataclasses
import json
from enum import Enum
from pathlib import Path
from typing import Any

import pytest

from analog_validation import (
    CrcMismatch,
    FrameTooLong,
    FramingError,
    ProtocolError,
    UnsupportedProtocolVersion,
)
from analog_validation.protocol import (
    AFE_PROFILE_NAME,
    AFE_PROFILE_VERSION,
    encode_afe_message,
    parse_afe_message,
)

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "test-data" / "golden"


def _normalize(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _normalize(getattr(value, item.name))
            for item in dataclasses.fields(value)
        }
    if isinstance(value, (set, frozenset)):
        return sorted((_normalize(item) for item in value), key=repr)
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    return value


def _read_csv(name: str) -> tuple[list[str], list[dict[str, str]]]:
    with (GOLDEN_DIR / name).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        return list(reader.fieldnames or ()), rows


EXPECTED: dict[str, Any] = json.loads(
    (GOLDEN_DIR / "expected_frames.json").read_text(encoding="utf-8")
)
EXPECTED_BY_NAME = {item["name"]: item for item in EXPECTED["records"]}
VALID_FIELDS, VALID_ROWS = _read_csv("afe_v1_valid.csv")
INVALID_FIELDS, INVALID_ROWS = _read_csv("afe_v1_invalid.csv")
ERROR_TYPES: dict[str, type[Exception]] = {
    "CrcMismatch": CrcMismatch,
    "FrameTooLong": FrameTooLong,
    "FramingError": FramingError,
    "ProtocolError": ProtocolError,
    "UnsupportedProtocolVersion": UnsupportedProtocolVersion,
}


def test_golden_manifest_is_complete_and_explicitly_host_only() -> None:
    assert set(EXPECTED) == {
        "schema_version",
        "profile",
        "evidence_source",
        "records",
    }
    assert EXPECTED["schema_version"] == "afe-golden.v1"
    assert EXPECTED["profile"] == {
        "name": AFE_PROFILE_NAME,
        "version": AFE_PROFILE_VERSION,
    }
    assert EXPECTED["evidence_source"] == "HOST_TEST"
    assert VALID_FIELDS == ["name", "record"]
    assert INVALID_FIELDS == ["name", "record_base64", "error_type", "error_match"]
    assert len(VALID_ROWS) == len(EXPECTED_BY_NAME) == 20
    assert len(INVALID_ROWS) == 9
    assert len({row["name"] for row in VALID_ROWS}) == len(VALID_ROWS)
    assert len({row["name"] for row in INVALID_ROWS}) == len(INVALID_ROWS)
    assert {row["name"] for row in VALID_ROWS} == set(EXPECTED_BY_NAME)


@pytest.mark.parametrize("row", VALID_ROWS, ids=[row["name"] for row in VALID_ROWS])
def test_valid_golden_record_parses_and_reencodes_exactly(
    row: dict[str, str],
) -> None:
    record = row["record"] + "\n"
    message = parse_afe_message(record)
    expected_item = EXPECTED_BY_NAME[row["name"]]
    assert type(message).__name__ == expected_item["model_type"]
    assert _normalize(message) == expected_item["fields"]
    assert encode_afe_message(message) == record


@pytest.mark.parametrize(
    "row", INVALID_ROWS, ids=[row["name"] for row in INVALID_ROWS]
)
def test_invalid_golden_record_fails_with_frozen_error_family(
    row: dict[str, str],
) -> None:
    record = base64.b64decode(row["record_base64"], validate=True)
    expected_error = ERROR_TYPES[row["error_type"]]
    with pytest.raises(expected_error, match=row["error_match"]):
        parse_afe_message(record)
