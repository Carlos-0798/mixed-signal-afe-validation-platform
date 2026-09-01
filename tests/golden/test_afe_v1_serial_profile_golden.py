"""Frozen AFE v1 records exercised through the new serial-profile boundary."""

from __future__ import annotations

import base64
import csv
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from analog_validation.domain import EvidenceSource
from analog_validation.profiles import AfeV1SerialProfile
from analog_validation.protocol import AfeTelemetry, encode_afe_message
from analog_validation.transport import (
    BoundedRawEventLog,
    RawRecordEvent,
    RawRecordStatus,
)

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "test-data" / "golden"
NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def read_rows(name: str) -> list[dict[str, str]]:
    with (GOLDEN_DIR / name).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


VALID_ROWS = read_rows("afe_v1_valid.csv")
INVALID_ROWS = read_rows("afe_v1_invalid.csv")


def append_record(log: BoundedRawEventLog, raw: bytes) -> RawRecordEvent:
    return log.append_received(
        received_at=NOW,
        port_id="MEMORY:GOLDEN-AFE",
        profile_name="afe",
        raw_bytes=raw,
    )


def test_all_twenty_valid_golden_records_cross_the_serial_profile_exactly() -> None:
    profile = AfeV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog(max_events=32, max_total_bytes=8192)
    results = []

    for row in VALID_ROWS:
        raw = (row["record"] + "\n").encode("ascii")
        result = profile.process_record(append_record(log, raw), log)
        results.append(result)
        assert result.accepted, row["name"]
        assert result.message is not None
        assert encode_afe_message(result.message).encode("ascii") == raw

    assert len(results) == 20
    assert all(
        event.status is RawRecordStatus.PARSED for event in log.snapshot().events
    )
    telemetry_results = [
        result for result in results if isinstance(result.message, AfeTelemetry)
    ]
    assert len(telemetry_results) == 2
    assert all(len(result.measurements) == 4 for result in telemetry_results)
    assert all(
        measurement.channel.startswith("afe.ch")
        and not measurement.channel.endswith("_mv")
        for result in telemetry_results
        for measurement in result.measurements
    )
    capability_results = [
        result for result in results if result.capabilities is not None
    ]
    assert len(capability_results) == 1
    capabilities = capability_results[0].capabilities
    assert capabilities is not None
    assert capabilities.device_id == "sim-afe-1"
    assert capabilities.automated_output_allowed


@pytest.mark.parametrize(
    "row",
    INVALID_ROWS,
    ids=[row["name"] for row in INVALID_ROWS],
)
def test_all_nine_invalid_golden_records_keep_their_error_contract(
    row: dict[str, str],
) -> None:
    profile = AfeV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog(max_events=4, max_total_bytes=8192)
    raw = base64.b64decode(row["record_base64"], validate=True)

    result = profile.process_record(append_record(log, raw), log)

    assert not result.accepted
    assert result.event.status is RawRecordStatus.REJECTED
    assert result.event.error_type == row["error_type"]
    assert result.event.error_message is not None
    assert re.search(row["error_match"], result.event.error_message)
    assert result.message is None
    assert result.measurements == ()
    assert result.capabilities is None
