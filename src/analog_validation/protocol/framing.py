"""Strict bounded ASCII CSV framing independent of any controller profile."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from analog_validation.errors import CrcMismatch, FrameTooLong, FramingError

from .crc import crc16_ccitt_false

MAX_RECORD_BYTES = 128
_CRC_HEX = re.compile(r"^[0-9A-F]{4}$")


@dataclass(frozen=True, slots=True)
class Frame:
    """Validated payload fields with namespace but without CRC or terminator."""

    fields: tuple[str, ...]


def _ascii_bytes(text: str) -> bytes:
    try:
        return text.encode("ascii")
    except UnicodeEncodeError as error:
        raise FramingError("record must contain ASCII only") from error


def _validate_token(field: str) -> None:
    if not field:
        raise FramingError("fields must be non-empty")
    if any(character == "," or not 0x21 <= ord(character) <= 0x7E for character in field):
        raise FramingError(
            "fields must be printable unquoted ASCII tokens without commas or whitespace"
        )


def _render_fields(fields: Iterable[object]) -> tuple[str, ...]:
    try:
        rendered = tuple(str(field) for field in fields)
    except TypeError as error:
        raise FramingError("fields must be an iterable") from error
    if len(rendered) < 3 or rendered[0] != "AFE":
        raise FramingError("frame must begin with AFE and contain type and sequence")
    for field in rendered:
        _validate_token(field)
    return rendered


def encode_frame(fields: Iterable[object]) -> str:
    """Encode payload fields as one LF-terminated record with uppercase CRC."""

    rendered = _render_fields(fields)
    payload = ",".join(rendered)
    crc = crc16_ccitt_false(_ascii_bytes(payload))
    record = f"{payload},{crc:04X}\n"
    if len(_ascii_bytes(record)) > MAX_RECORD_BYTES:
        raise FrameTooLong(f"record exceeds {MAX_RECORD_BYTES} bytes")
    return record


def _decode_ascii(record: str | bytes) -> tuple[str, bytes]:
    if isinstance(record, bytes):
        raw = record
        if len(raw) > MAX_RECORD_BYTES:
            raise FrameTooLong(f"record exceeds {MAX_RECORD_BYTES} bytes")
        try:
            return raw.decode("ascii"), raw
        except UnicodeDecodeError as error:
            raise FramingError("record must contain ASCII only") from error
    if isinstance(record, str):
        raw = _ascii_bytes(record)
        if len(raw) > MAX_RECORD_BYTES:
            raise FrameTooLong(f"record exceeds {MAX_RECORD_BYTES} bytes")
        return record, raw
    raise FramingError("record must be str or bytes")


def _remove_terminator(text: str) -> str:
    if text.endswith("\r\n"):
        text = text[:-2]
    elif text.endswith("\n"):
        text = text[:-1]
    elif text.endswith("\r"):
        raise FramingError("bare CR is not a valid record terminator")
    if "\r" in text or "\n" in text:
        raise FramingError("record contains an embedded line ending")
    return text


def decode_frame(record: str | bytes) -> Frame:
    """Validate one complete or already-delimited record and return its payload."""

    text, _raw = _decode_ascii(record)
    text = _remove_terminator(text)
    parts = text.split(",")
    if len(parts) < 4 or parts[0] != "AFE":
        raise FramingError("invalid namespace or missing fields")

    payload_fields = parts[:-1]
    for field in payload_fields:
        _validate_token(field)

    received = parts[-1]
    if not _CRC_HEX.fullmatch(received):
        raise FramingError("CRC must be four uppercase hexadecimal digits")
    payload = ",".join(payload_fields)
    expected = crc16_ccitt_false(_ascii_bytes(payload))
    if int(received, 16) != expected:
        raise CrcMismatch(f"CRC mismatch: expected {expected:04X}")
    return Frame(tuple(payload_fields))


__all__ = ["MAX_RECORD_BYTES", "Frame", "decode_frame", "encode_frame"]
