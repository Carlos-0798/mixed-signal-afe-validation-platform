"""Freeze accepted CSV Replay v1 meaning and rejected error families."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict, cast

import pytest

from analog_validation import (
    CsvReplayDataset,
    ReplayFormatError,
    UnsupportedReplayVersion,
    load_csv_replay,
    parse_csv_replay,
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = ROOT / "test-data" / "golden"
VALID_FILE = GOLDEN_DIR / "csv_replay_v1_valid.csv"
INVALID_FILE = GOLDEN_DIR / "csv_replay_v1_invalid.json"


class InvalidCase(TypedDict):
    name: str
    find: str
    replace: str
    error_type: str
    message: str


ERROR_TYPES = {
    "ReplayFormatError": ReplayFormatError,
    "UnsupportedReplayVersion": UnsupportedReplayVersion,
}


def invalid_cases() -> list[InvalidCase]:
    raw = json.loads(INVALID_FILE.read_text(encoding="utf-8"))
    return cast(list[InvalidCase], raw)


def test_valid_golden_file_has_frozen_model_meaning() -> None:
    dataset = load_csv_replay(VALID_FILE)

    assert isinstance(dataset, CsvReplayDataset)
    assert dataset.dataset_id == "afe-demo-001"
    assert dataset.declared_record_count == 5
    assert [record.record_id for record in dataset.records] == [
        "input-000",
        "output-001",
        "input-002",
        "output-003",
        "bool-004",
    ]


@pytest.mark.parametrize("case", invalid_cases(), ids=lambda case: case["name"])
def test_invalid_golden_mutations_freeze_error_families(case: InvalidCase) -> None:
    valid = VALID_FILE.read_text(encoding="utf-8")
    assert case["find"] in valid
    invalid = valid.replace(case["find"], case["replace"], 1)
    error_type = ERROR_TYPES[case["error_type"]]

    with pytest.raises(error_type, match=case["message"]):
        parse_csv_replay(invalid)
