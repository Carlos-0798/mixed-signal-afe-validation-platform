"""Repository-owned MSP430 Protocol v1 interoperability fixtures."""

from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from analog_validation.domain import EvidenceSource
from analog_validation.errors import ProtocolError
from analog_validation.profiles import Msp430HealthV1SerialProfile
from analog_validation.protocol.msp430_health_v1 import (
    MSP430_HEALTH_INTERFACE_COMMIT,
    Msp430LogRecord,
    encode_msp430_message,
    parse_msp430_message,
)
from analog_validation.transport import BoundedRawEventLog, RawRecordStatus

GOLDEN_PATH = (
    Path(__file__).resolve().parents[2]
    / "test-data"
    / "golden"
    / "msp430_equipment_health_v1.json"
)
MANIFEST: dict[str, Any] = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def test_manifest_declares_independent_host_only_scope_and_frozen_interface() -> None:
    assert set(MANIFEST) == {
        "schema_version",
        "evidence_source",
        "scope",
        "interface_reference",
        "valid_records",
        "invalid_records",
    }
    assert MANIFEST["schema_version"] == "msp430-equipment-health-interoperability.v1"
    assert MANIFEST["evidence_source"] == "HOST_TEST"
    assert "no peer runtime code" in MANIFEST["scope"]
    assert "serial I/O" in MANIFEST["scope"]
    assert "inherited MSP430 project evidence" in MANIFEST["scope"]
    assert MANIFEST["interface_reference"]["commit"] == MSP430_HEALTH_INTERFACE_COMMIT
    assert MANIFEST["interface_reference"]["document"] == "docs/protocol.md"
    valid_names = [item["name"] for item in MANIFEST["valid_records"]]
    invalid_names = [item["name"] for item in MANIFEST["invalid_records"]]
    assert len(valid_names) == len(set(valid_names)) == 10
    assert len(invalid_names) == len(set(invalid_names)) == 11


@pytest.mark.parametrize(
    "item",
    MANIFEST["valid_records"],
    ids=[item["name"] for item in MANIFEST["valid_records"]],
)
def test_valid_records_parse_to_expected_type_and_reencode_exactly(
    item: dict[str, str],
) -> None:
    message = parse_msp430_message(item["record"])

    assert type(message).__name__ == item["message_type"]
    assert encode_msp430_message(message) == item["record"]
    if item["name"] == "log_unknown_numeric_state_preserved":
        assert isinstance(message, Msp430LogRecord)
        assert message.state_code == 255


@pytest.mark.parametrize(
    "item",
    MANIFEST["invalid_records"],
    ids=[item["name"] for item in MANIFEST["invalid_records"]],
)
def test_invalid_records_keep_their_error_family_and_meaning(
    item: dict[str, str],
) -> None:
    raw = base64.b64decode(item["record_base64"], validate=True)

    with pytest.raises(ProtocolError) as caught:
        parse_msp430_message(raw)

    assert type(caught.value).__name__ == item["error_type"]
    assert re.search(item["error_match"], str(caught.value))


@pytest.mark.parametrize(
    "item",
    MANIFEST["valid_records"],
    ids=[item["name"] for item in MANIFEST["valid_records"]],
)
def test_valid_records_cross_the_independent_serial_profile(item: dict[str, str]) -> None:
    profile = Msp430HealthV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog(max_events=2, max_total_bytes=512)
    raw = item["record"].encode("ascii")
    event = log.append_received(
        received_at=NOW,
        port_id="MEMORY:MSP430-GOLDEN",
        profile_name=profile.identity.name,
        raw_bytes=raw,
    )

    result = profile.process_record(event, log)

    assert result.accepted
    assert result.event.status is RawRecordStatus.PARSED
    assert result.event.raw_bytes == raw
    assert result.message is not None
    assert encode_msp430_message(result.message).encode("ascii") == raw


@pytest.mark.parametrize(
    "item",
    MANIFEST["invalid_records"],
    ids=[item["name"] for item in MANIFEST["invalid_records"]],
)
def test_invalid_records_are_rejected_without_derived_data(item: dict[str, str]) -> None:
    profile = Msp430HealthV1SerialProfile(evidence_source=EvidenceSource.HOST_TEST)
    log = BoundedRawEventLog(max_events=2, max_total_bytes=512)
    raw = base64.b64decode(item["record_base64"], validate=True)
    event = log.append_received(
        received_at=NOW,
        port_id="MEMORY:MSP430-GOLDEN",
        profile_name=profile.identity.name,
        raw_bytes=raw,
    )

    result = profile.process_record(event, log)

    assert not result.accepted
    assert result.event.status is RawRecordStatus.REJECTED
    assert result.event.error_type == item["error_type"]
    assert result.message is None
    assert result.measurements == ()
    assert result.capabilities is None
