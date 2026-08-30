"""Tests for the compatible strict, bounded AFE ASCII CSV envelope."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from analog_validation import (
    MAX_RECORD_BYTES,
    CrcMismatch,
    FrameTooLong,
    FramingError,
    decode_frame,
    encode_frame,
)


def test_encode_decode_round_trip_for_text_and_bytes() -> None:
    record = encode_frame(("AFE", "TEST", 7, -125, "OK"))

    assert record.endswith("\n")
    assert record[-6] == ","
    assert decode_frame(record).fields == ("AFE", "TEST", "7", "-125", "OK")
    assert decode_frame(record.encode("ascii")).fields == (
        "AFE",
        "TEST",
        "7",
        "-125",
        "OK",
    )


def test_lf_crlf_and_already_delimited_records_are_accepted() -> None:
    lf_record = encode_frame(("AFE", "TEST", 1))
    body = lf_record.removesuffix("\n")

    assert decode_frame(lf_record).fields == ("AFE", "TEST", "1")
    assert decode_frame(body + "\r\n").fields == ("AFE", "TEST", "1")
    assert decode_frame(body).fields == ("AFE", "TEST", "1")


def test_frame_result_is_immutable() -> None:
    frame = decode_frame(encode_frame(("AFE", "TEST", 1)))

    with pytest.raises(FrozenInstanceError):
        frame.fields = ("changed",)  # type: ignore[misc]


def test_exact_length_limit_is_accepted_and_next_byte_is_rejected() -> None:
    exact = encode_frame(("AFE", "X", 0, "A" * 114))

    assert len(exact.encode("ascii")) == MAX_RECORD_BYTES
    assert decode_frame(exact).fields[-1] == "A" * 114
    with pytest.raises(FrameTooLong, match="128"):
        encode_frame(("AFE", "X", 0, "A" * 115))


def test_overlong_text_and_bytes_are_rejected_before_parsing() -> None:
    with pytest.raises(FrameTooLong, match="128"):
        decode_frame("A" * 129)
    with pytest.raises(FrameTooLong, match="128"):
        decode_frame(b"A" * 129)


def test_non_ascii_text_and_bytes_are_rejected() -> None:
    with pytest.raises(FramingError, match="ASCII"):
        encode_frame(("AFE", "TEST", "\u6e29\u5ea6"))

    with pytest.raises(FramingError, match="ASCII") as text_error:
        decode_frame("AFE,TEST,\u6e29\u5ea6,0000\n")
    assert isinstance(text_error.value.__cause__, UnicodeEncodeError)

    with pytest.raises(FramingError, match="ASCII") as bytes_error:
        decode_frame(b"AFE,TEST,\xff,0000\n")
    assert isinstance(bytes_error.value.__cause__, UnicodeDecodeError)


def test_decode_requires_text_or_bytes() -> None:
    with pytest.raises(FramingError, match="str or bytes"):
        decode_frame(cast(Any, 123))


def test_encode_requires_iterable_fields() -> None:
    with pytest.raises(FramingError, match="iterable") as captured:
        encode_frame(cast(Any, None))
    assert isinstance(captured.value.__cause__, TypeError)


@pytest.mark.parametrize(
    "fields",
    [
        (),
        ("AFE",),
        ("AFE", "TEST"),
        ("OTHER", "TEST", 1),
    ],
)
def test_encode_requires_namespace_type_and_sequence(
    fields: tuple[object, ...],
) -> None:
    with pytest.raises(FramingError, match="begin with AFE"):
        encode_frame(fields)


@pytest.mark.parametrize(
    "invalid_token",
    ["", " leading", "trailing ", "internal space", "tab\tvalue", "comma,value", "\x1f", "\x7f"],
)
def test_encode_rejects_empty_whitespace_comma_and_nonprintable_tokens(
    invalid_token: str,
) -> None:
    with pytest.raises(FramingError, match="fields must"):
        encode_frame(("AFE", "TEST", 1, invalid_token))


@pytest.mark.parametrize(
    "record",
    [
        "AFE,TEST,1,0000\r",
        "AFE,TEST,1,0000\nEXTRA",
        "AFE,TEST,1\r,0000\n",
    ],
)
def test_bare_or_embedded_line_endings_are_rejected(record: str) -> None:
    with pytest.raises(FramingError, match="CR|embedded"):
        decode_frame(record)


@pytest.mark.parametrize(
    "record",
    [
        "",
        "AFE,TEST,0000",
        "OTHER,TEST,1,0000",
    ],
)
def test_decode_rejects_bad_namespace_or_missing_fields(record: str) -> None:
    with pytest.raises(FramingError, match="namespace or missing"):
        decode_frame(record)


@pytest.mark.parametrize(
    "record",
    [
        "AFE,,1,0000\n",
        "AFE,TEST, 1,0000\n",
        "AFE,TEST,\t,0000\n",
    ],
)
def test_decode_rejects_invalid_payload_tokens_before_crc(record: str) -> None:
    with pytest.raises(FramingError, match="fields must"):
        decode_frame(record)


@pytest.mark.parametrize(
    "crc_text",
    ["", "ABC", "29b1", "GGGG", "12345"],
)
def test_decode_requires_exact_uppercase_crc(crc_text: str) -> None:
    with pytest.raises(FramingError, match="four uppercase"):
        decode_frame(f"AFE,TEST,1,{crc_text}\n")


def test_crc_corruption_has_specific_error_and_expected_value() -> None:
    record = encode_frame(("AFE", "TEST", 1, 100)).replace(",100,", ",101,")

    with pytest.raises(CrcMismatch, match=r"expected [0-9A-F]{4}"):
        decode_frame(record)
