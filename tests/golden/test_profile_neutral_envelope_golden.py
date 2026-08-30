"""Frozen profile-neutral CRC-envelope interoperability shapes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from analog_validation import FramingError, decode_frame
from analog_validation.protocol.envelope import (
    decode_crc_envelope,
    encode_crc_envelope,
)

GOLDEN_PATH = (
    Path(__file__).resolve().parents[2]
    / "test-data"
    / "golden"
    / "profile_neutral_envelope_v1.json"
)
MANIFEST: dict[str, Any] = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def test_manifest_scope_is_explicit_and_records_are_unique() -> None:
    assert set(MANIFEST) == {
        "schema_version",
        "evidence_source",
        "scope",
        "interface_references",
        "records",
    }
    assert MANIFEST["schema_version"] == "profile-neutral-envelope-golden.v1"
    assert MANIFEST["evidence_source"] == "HOST_TEST"
    assert "no business-field parsing" in MANIFEST["scope"]
    assert "hardware validation" in MANIFEST["scope"]
    assert set(MANIFEST["interface_references"]) == {"afe", "msp430"}
    names = [item["name"] for item in MANIFEST["records"]]
    assert len(names) == len(set(names)) == 3


@pytest.mark.parametrize(
    "item",
    MANIFEST["records"],
    ids=[item["name"] for item in MANIFEST["records"]],
)
def test_profile_neutral_records_decode_and_reencode_exactly(
    item: dict[str, Any],
) -> None:
    fields = tuple(item["fields"])

    assert decode_crc_envelope(item["record"]).fields == fields
    assert encode_crc_envelope(fields) == item["record"]


def test_msp430_shape_is_accepted_only_by_neutral_envelope() -> None:
    item = next(
        value
        for value in MANIFEST["records"]
        if value["name"] == "msp430_unavailable_telemetry_shape"
    )

    assert decode_crc_envelope(item["record"]).fields[0] == "TEL"
    with pytest.raises(FramingError, match="namespace"):
        decode_frame(item["record"])
