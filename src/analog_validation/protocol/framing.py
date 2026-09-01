"""Backward-compatible AFE wrapper over the profile-neutral CRC envelope."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from analog_validation.errors import FramingError

from .envelope import (
    DEFAULT_MAX_RECORD_BYTES,
    _decode_crc_envelope,
    _encode_crc_envelope,
)

MAX_RECORD_BYTES = DEFAULT_MAX_RECORD_BYTES


@dataclass(frozen=True, slots=True)
class Frame:
    """Validated payload fields with namespace but without CRC or terminator."""

    fields: tuple[str, ...]


def _require_afe_encode_shape(fields: tuple[str, ...]) -> None:
    if len(fields) < 3 or fields[0] != "AFE":
        raise FramingError("frame must begin with AFE and contain type and sequence")


def _require_afe_decode_shape(fields: tuple[str, ...]) -> None:
    if len(fields) < 3 or fields[0] != "AFE":
        raise FramingError("invalid namespace or missing fields")


def encode_frame(fields: Iterable[object]) -> str:
    """Encode payload fields as one LF-terminated record with uppercase CRC."""

    return _encode_crc_envelope(
        fields,
        max_record_bytes=MAX_RECORD_BYTES,
        field_validator=_require_afe_encode_shape,
    )


def decode_frame(record: str | bytes) -> Frame:
    """Validate one complete or already-delimited record and return its payload."""

    envelope = _decode_crc_envelope(
        record,
        max_record_bytes=MAX_RECORD_BYTES,
        field_validator=_require_afe_decode_shape,
    )
    return Frame(envelope.fields)


__all__ = ["MAX_RECORD_BYTES", "Frame", "decode_frame", "encode_frame"]
