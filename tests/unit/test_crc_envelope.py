"""Tests for the profile-neutral bounded ASCII CRC envelope."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from analog_validation.errors import CrcMismatch, FrameTooLong, FramingError
from analog_validation.protocol.envelope import (
    DEFAULT_MAX_RECORD_BYTES,
    CrcEnvelope,
    decode_crc_envelope,
    encode_crc_envelope,
)


def test_round_trip_does_not_require_a_namespace() -> None:
    record = encode_crc_envelope(("TEL", 7, -125, "FAULT", "0015"))

    assert record == "TEL,7,-125,FAULT,0015,146F\n"
    assert decode_crc_envelope(record).fields == (
        "TEL",
        "7",
        "-125",
        "FAULT",
        "0015",
    )
    assert decode_crc_envelope(record.encode("ascii")).fields[0] == "TEL"


def test_lf_crlf_and_already_delimited_records_are_accepted() -> None:
    lf_record = encode_crc_envelope(("ACK", 1, "OK"))
    body = lf_record.removesuffix("\n")

    assert decode_crc_envelope(lf_record).fields == ("ACK", "1", "OK")
    assert decode_crc_envelope(body + "\r\n").fields == ("ACK", "1", "OK")
    assert decode_crc_envelope(body).fields == ("ACK", "1", "OK")


def test_envelope_result_is_immutable() -> None:
    envelope = decode_crc_envelope(encode_crc_envelope(("TEL",)))

    assert isinstance(envelope, CrcEnvelope)
    with pytest.raises(FrozenInstanceError):
        envelope.fields = ("changed",)  # type: ignore[misc]


def test_default_and_custom_exact_length_limits() -> None:
    assert DEFAULT_MAX_RECORD_BYTES == 128
    exact = encode_crc_envelope(("X", "A" * 4), max_record_bytes=12)

    assert len(exact.encode("ascii")) == 12
    assert decode_crc_envelope(exact, max_record_bytes=12).fields[-1] == "A" * 4
    with pytest.raises(FrameTooLong, match="12"):
        encode_crc_envelope(("X", "A" * 5), max_record_bytes=12)


def test_overlong_text_and_bytes_are_rejected_before_parsing() -> None:
    with pytest.raises(FrameTooLong, match="8"):
        decode_crc_envelope("A" * 9, max_record_bytes=8)
    with pytest.raises(FrameTooLong, match="8"):
        decode_crc_envelope(b"A" * 9, max_record_bytes=8)


def test_non_ascii_text_and_bytes_are_rejected_with_causes() -> None:
    with pytest.raises(FramingError, match="ASCII"):
        encode_crc_envelope(("TEL", "temperature-\u6e29"))

    with pytest.raises(FramingError, match="ASCII") as text_error:
        decode_crc_envelope("TEL,\u6e29,0000\n")
    assert isinstance(text_error.value.__cause__, UnicodeEncodeError)

    with pytest.raises(FramingError, match="ASCII") as bytes_error:
        decode_crc_envelope(b"TEL,\xff,0000\n")
    assert isinstance(bytes_error.value.__cause__, UnicodeDecodeError)


def test_input_types_and_empty_payload_are_rejected() -> None:
    with pytest.raises(FramingError, match="str or bytes"):
        decode_crc_envelope(cast(Any, 123))
    with pytest.raises(FramingError, match="iterable") as captured:
        encode_crc_envelope(cast(Any, None))
    assert isinstance(captured.value.__cause__, TypeError)
    with pytest.raises(FramingError, match="at least one"):
        encode_crc_envelope(())
    with pytest.raises(FramingError, match="at least one"):
        decode_crc_envelope("0000\n")


@pytest.mark.parametrize(
    "invalid_token",
    [
        "",
        " leading",
        "trailing ",
        "internal space",
        "tab\tvalue",
        "comma,value",
        "\x1f",
        "\x7f",
    ],
)
def test_invalid_payload_tokens_are_rejected(invalid_token: str) -> None:
    with pytest.raises(FramingError, match="fields must"):
        encode_crc_envelope(("TEL", invalid_token))


@pytest.mark.parametrize(
    "record",
    [
        "TEL,1,0000\r",
        "TEL,1,0000\nEXTRA",
        "TEL,1\r,0000\n",
    ],
)
def test_bare_or_embedded_line_endings_are_rejected(record: str) -> None:
    with pytest.raises(FramingError, match="CR|embedded"):
        decode_crc_envelope(record)


@pytest.mark.parametrize("crc_text", ["", "ABC", "29b1", "GGGG", "12345"])
def test_crc_requires_exact_uppercase_hex(crc_text: str) -> None:
    with pytest.raises(FramingError, match="four uppercase"):
        decode_crc_envelope(f"TEL,1,{crc_text}\n")


def test_crc_corruption_has_specific_error() -> None:
    record = encode_crc_envelope(("TEL", 1, 100)).replace(",100,", ",101,")

    with pytest.raises(CrcMismatch, match=r"expected [0-9A-F]{4}"):
        decode_crc_envelope(record)


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "128"])
def test_record_limit_validation_is_strict(limit: object) -> None:
    with pytest.raises(FramingError, match="max_record_bytes"):
        encode_crc_envelope(("TEL",), max_record_bytes=cast(Any, limit))
