"""Exercise the Step 1 byte stream through the Step 2 neutral envelope."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from analog_validation.protocol.envelope import decode_crc_envelope
from analog_validation.transport import BoundedLineFramer, StreamIssue

GOLDEN_PATH = (
    Path(__file__).resolve().parents[2]
    / "test-data"
    / "golden"
    / "profile_neutral_envelope_v1.json"
)


def test_fragmented_mixed_profile_shapes_reach_neutral_decoder_in_order() -> None:
    manifest: dict[str, Any] = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    expected_records = tuple(
        item["record"].encode("ascii") for item in manifest["records"]
    )
    stream = b"".join(expected_records)
    framer = BoundedLineFramer(128)
    received: list[bytes] = []
    issues: list[StreamIssue] = []

    for start, stop in ((0, 7), (7, 53), (53, 91), (91, len(stream))):
        result = framer.feed(stream[start:stop])
        received.extend(result.records)
        issues.extend(result.issues)

    assert tuple(received) == expected_records
    assert issues == []
    assert framer.pending_bytes == 0
    assert [decode_crc_envelope(record).fields for record in received] == [
        tuple(item["fields"]) for item in manifest["records"]
    ]
