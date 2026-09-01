"""Profile-neutral bounded ASCII token and CRC record envelope."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from analog_validation.errors import CrcMismatch, FrameTooLong, FramingError

from .crc import crc16_ccitt_false

DEFAULT_MAX_RECORD_BYTES = 128
_CRC_HEX = re.compile(r"^[0-9A-F]{4}$")
_FieldValidator = Callable[[tuple[str, ...]], None]


@dataclass(frozen=True, slots=True)
class CrcEnvelope:
    """Validated payload tokens without their CRC or line terminator."""

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


def _require_positive_limit(max_record_bytes: int) -> int:
    if isinstance(max_record_bytes, bool) or not isinstance(max_record_bytes, int):
        raise FramingError("max_record_bytes must be an integer")
    if max_record_bytes < 1:
        raise FramingError("max_record_bytes must be positive")
    return max_record_bytes


def _require_payload(fields: tuple[str, ...]) -> None:
    if not fields:
        raise FramingError("envelope must contain at least one payload field")


def _render_fields(
    fields: Iterable[object],
    *,
    field_validator: _FieldValidator,
) -> tuple[str, ...]:
    try:
        rendered = tuple(str(field) for field in fields)
    except TypeError as error:
        raise FramingError("fields must be an iterable") from error
    field_validator(rendered)
    for field in rendered:
        _validate_token(field)
    return rendered


def _encode_crc_envelope(
    fields: Iterable[object],
    *,
    max_record_bytes: int,
    field_validator: _FieldValidator,
) -> str:
    limit = _require_positive_limit(max_record_bytes)
    rendered = _render_fields(fields, field_validator=field_validator)
    payload = ",".join(rendered)
    crc = crc16_ccitt_false(_ascii_bytes(payload))
    record = f"{payload},{crc:04X}\n"
    if len(_ascii_bytes(record)) > limit:
        raise FrameTooLong(f"record exceeds {limit} bytes")
    return record


def encode_crc_envelope(
    fields: Iterable[object],
    *,
    max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES,
) -> str:
    """Encode profile-neutral payload tokens with uppercase CRC and LF."""

    return _encode_crc_envelope(
        fields,
        max_record_bytes=max_record_bytes,
        field_validator=_require_payload,
    )


def _decode_ascii(record: str | bytes, *, max_record_bytes: int) -> str:
    limit = _require_positive_limit(max_record_bytes)
    if isinstance(record, bytes):
        if len(record) > limit:
            raise FrameTooLong(f"record exceeds {limit} bytes")
        try:
            return record.decode("ascii")
        except UnicodeDecodeError as error:
            raise FramingError("record must contain ASCII only") from error
    if isinstance(record, str):
        raw = _ascii_bytes(record)
        if len(raw) > limit:
            raise FrameTooLong(f"record exceeds {limit} bytes")
        return record
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


def _decode_crc_envelope(
    record: str | bytes,
    *,
    max_record_bytes: int,
    field_validator: _FieldValidator,
) -> CrcEnvelope:
    text = _decode_ascii(record, max_record_bytes=max_record_bytes)
    parts = _remove_terminator(text).split(",")
    payload_fields = tuple(parts[:-1])
    field_validator(payload_fields)
    for field in payload_fields:
        _validate_token(field)

    received = parts[-1]
    if not _CRC_HEX.fullmatch(received):
        raise FramingError("CRC must be four uppercase hexadecimal digits")
    payload = ",".join(payload_fields)
    expected = crc16_ccitt_false(_ascii_bytes(payload))
    if int(received, 16) != expected:
        raise CrcMismatch(f"CRC mismatch: expected {expected:04X}")
    return CrcEnvelope(payload_fields)


def decode_crc_envelope(
    record: str | bytes,
    *,
    max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES,
) -> CrcEnvelope:
    """Validate one complete profile-neutral CRC record."""

    return _decode_crc_envelope(
        record,
        max_record_bytes=max_record_bytes,
        field_validator=_require_payload,
    )


__all__ = [
    "DEFAULT_MAX_RECORD_BYTES",
    "CrcEnvelope",
    "decode_crc_envelope",
    "encode_crc_envelope",
]
