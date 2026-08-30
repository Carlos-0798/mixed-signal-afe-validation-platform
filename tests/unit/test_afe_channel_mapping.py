"""Tests for explicit legacy-to-canonical AFE channel-name mapping."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import Any, cast

import pytest

from analog_validation import EvidenceSource, ValidationError
from analog_validation.protocol.afe_channels import (
    AFE_CHANNEL_MAPPING_SCHEMA_VERSION,
    AfeChannelNaming,
    AfeChannelReference,
    AfeChannelRole,
    convert_afe_channel,
    format_afe_channel,
    parse_afe_channel,
)
from analog_validation.protocol.afe_v1 import AfeTelemetry, telemetry_to_measurements

EXPECTED_SUFFIXES = {
    AfeChannelNaming.CANONICAL: {
        AfeChannelRole.INPUT: "input",
        AfeChannelRole.OUTPUT: "output",
        AfeChannelRole.GAIN: "gain",
        AfeChannelRole.THRESHOLD: "threshold",
    },
    AfeChannelNaming.LEGACY_TELEMETRY_V1: {
        AfeChannelRole.INPUT: "input_mv",
        AfeChannelRole.OUTPUT: "output_mv",
        AfeChannelRole.GAIN: "gain",
        AfeChannelRole.THRESHOLD: "threshold",
    },
}


def test_schema_and_all_mapping_pairs_are_frozen() -> None:
    assert AFE_CHANNEL_MAPPING_SCHEMA_VERSION == "afe-channel-map.v1"

    for naming, suffixes in EXPECTED_SUFFIXES.items():
        for role, suffix in suffixes.items():
            name = format_afe_channel(7, role, naming=naming)
            assert name == f"afe.ch7.{suffix}"
            assert parse_afe_channel(name, naming=naming) == AfeChannelReference(7, role)


def test_reference_is_immutable_and_channel_boundaries_are_supported() -> None:
    reference = AfeChannelReference(255, AfeChannelRole.OUTPUT)

    assert format_afe_channel(
        0, AfeChannelRole.INPUT, naming=AfeChannelNaming.CANONICAL
    ) == "afe.ch0.input"
    assert reference.channel == 255
    with pytest.raises(FrozenInstanceError):
        reference.channel = 0  # type: ignore[misc]


def test_conversion_requires_declared_source_and_target_vocabularies() -> None:
    assert convert_afe_channel(
        "afe.ch2.input_mv",
        source=AfeChannelNaming.LEGACY_TELEMETRY_V1,
        target=AfeChannelNaming.CANONICAL,
    ) == "afe.ch2.input"
    assert convert_afe_channel(
        "afe.ch2.output",
        source=AfeChannelNaming.CANONICAL,
        target=AfeChannelNaming.LEGACY_TELEMETRY_V1,
    ) == "afe.ch2.output_mv"


def test_existing_telemetry_mapping_stays_legacy_and_converts_explicitly() -> None:
    message = AfeTelemetry(1, 1000, 0, 100, 200, 2000, 1, 0)
    measurements = telemetry_to_measurements(
        message,
        received_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
        raw_record_id="step2-fixture",
        source=EvidenceSource.HOST_TEST,
    )
    legacy_names = [item.channel for item in measurements]

    assert legacy_names == [
        "afe.ch0.input_mv",
        "afe.ch0.output_mv",
        "afe.ch0.gain",
        "afe.ch0.threshold",
    ]
    assert [
        convert_afe_channel(
            name,
            source=AfeChannelNaming.LEGACY_TELEMETRY_V1,
            target=AfeChannelNaming.CANONICAL,
        )
        for name in legacy_names
    ] == [
        "afe.ch0.input",
        "afe.ch0.output",
        "afe.ch0.gain",
        "afe.ch0.threshold",
    ]


@pytest.mark.parametrize("channel", [-1, 256, True, 1.5, "1"])
def test_channel_index_validation_is_strict(channel: object) -> None:
    with pytest.raises(ValidationError, match="channel index"):
        format_afe_channel(
            cast(Any, channel),
            AfeChannelRole.INPUT,
            naming=AfeChannelNaming.CANONICAL,
        )


def test_reference_and_formatter_require_typed_roles() -> None:
    with pytest.raises(ValidationError, match="AfeChannelRole"):
        AfeChannelReference(0, cast(Any, "INPUT"))
    with pytest.raises(ValidationError, match="AfeChannelRole"):
        format_afe_channel(
            0, cast(Any, "INPUT"), naming=AfeChannelNaming.CANONICAL
        )


def test_mapping_requires_typed_naming() -> None:
    with pytest.raises(ValidationError, match="AfeChannelNaming"):
        format_afe_channel(
            0, AfeChannelRole.INPUT, naming=cast(Any, "CANONICAL")
        )
    with pytest.raises(ValidationError, match="AfeChannelNaming"):
        parse_afe_channel("afe.ch0.input", naming=cast(Any, "CANONICAL"))


@pytest.mark.parametrize(
    "channel_name",
    [
        "afe.ch00.input",
        "afe.ch0.INPUT",
        "afe.ch0.input.extra",
        "other.ch0.input",
    ],
)
def test_parser_rejects_noncanonical_shapes(channel_name: str) -> None:
    with pytest.raises(ValidationError, match="afe.ch"):
        parse_afe_channel(channel_name, naming=AfeChannelNaming.CANONICAL)


def test_parser_rejects_nonstring_out_of_range_and_wrong_vocabulary() -> None:
    with pytest.raises(ValidationError, match="string"):
        parse_afe_channel(cast(Any, 1), naming=AfeChannelNaming.CANONICAL)
    with pytest.raises(ValidationError, match="between 0 and 255"):
        parse_afe_channel("afe.ch256.input", naming=AfeChannelNaming.CANONICAL)
    with pytest.raises(ValidationError, match="LEGACY_TELEMETRY_V1") as captured:
        parse_afe_channel(
            "afe.ch0.input",
            naming=AfeChannelNaming.LEGACY_TELEMETRY_V1,
        )
    assert isinstance(captured.value.__cause__, KeyError)
