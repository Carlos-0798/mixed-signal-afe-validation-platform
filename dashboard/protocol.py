"""Strict encoder/parser for the Phase 0 AFE ASCII CSV protocol."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .models import Command, Telemetry

MAX_RECORD_BYTES = 128
_HEX4 = re.compile(r"^[0-9A-F]{4}$")


class ProtocolError(ValueError):
    """Base class for rejected AFE records."""


class FrameTooLong(ProtocolError):
    """The serialized record exceeds the transport limit."""


class CrcMismatch(ProtocolError):
    """The received CRC does not match the payload."""


@dataclass(frozen=True)
class Frame:
    fields: tuple[str, ...]


def crc16_ccitt_false(data: bytes) -> int:
    """Return CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _ascii(text: str) -> bytes:
    try:
        return text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ProtocolError("record must contain ASCII only") from exc


def encode_frame(fields: Iterable[object]) -> str:
    rendered = tuple(str(field) for field in fields)
    if len(rendered) < 3 or rendered[0] != "AFE":
        raise ProtocolError("frame must begin with AFE and contain type and sequence")
    if any(not field or "," in field or "\r" in field or "\n" in field or field.strip() != field for field in rendered):
        raise ProtocolError("fields must be non-empty unquoted CSV tokens without whitespace")
    payload = ",".join(rendered)
    crc = crc16_ccitt_false(_ascii(payload))
    record = f"{payload},{crc:04X}\n"
    if len(_ascii(record)) > MAX_RECORD_BYTES:
        raise FrameTooLong(f"record exceeds {MAX_RECORD_BYTES} bytes")
    return record


def decode_frame(record: str | bytes) -> Frame:
    if isinstance(record, bytes):
        raw = record
        try:
            text = raw.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ProtocolError("record must contain ASCII only") from exc
    else:
        text = record
        raw = _ascii(text)
    if len(raw) > MAX_RECORD_BYTES:
        raise FrameTooLong(f"record exceeds {MAX_RECORD_BYTES} bytes")
    text = text.removesuffix("\n").removesuffix("\r")
    if "\r" in text or "\n" in text:
        raise ProtocolError("record contains an embedded line ending")
    parts = text.split(",")
    if len(parts) < 4 or parts[0] != "AFE":
        raise ProtocolError("invalid namespace or missing fields")
    if any(not part or part.strip() != part for part in parts):
        raise ProtocolError("empty or whitespace-padded field")
    received = parts[-1]
    if not _HEX4.fullmatch(received):
        raise ProtocolError("CRC must be four uppercase hexadecimal digits")
    payload = ",".join(parts[:-1])
    expected = crc16_ccitt_false(_ascii(payload))
    if int(received, 16) != expected:
        raise CrcMismatch(f"CRC mismatch: expected {expected:04X}")
    return Frame(tuple(parts[:-1]))


def _int_field(value: str, name: str, minimum: int, maximum: int, *, base: int = 10) -> int:
    try:
        parsed = int(value, base)
    except ValueError as exc:
        raise ProtocolError(f"{name} is not a valid integer") from exc
    if not minimum <= parsed <= maximum:
        raise ProtocolError(f"{name} is outside {minimum}..{maximum}")
    return parsed


def build_telemetry(message: Telemetry) -> str:
    return encode_frame((
        "AFE", "TEL", message.seq, message.time_ms, message.channel,
        message.input_mv, message.output_mv, message.gain_milli,
        message.threshold, f"{message.fault_flags:04X}",
    ))


def parse_telemetry(record: str | bytes) -> Telemetry:
    fields = decode_frame(record).fields
    if len(fields) != 10 or fields[:2] != ("AFE", "TEL"):
        raise ProtocolError("telemetry frame must contain exactly ten payload fields")
    if not _HEX4.fullmatch(fields[9]):
        raise ProtocolError("fault flags must be four uppercase hexadecimal digits")
    return Telemetry(
        seq=_int_field(fields[2], "seq", 0, 0xFFFF),
        time_ms=_int_field(fields[3], "time_ms", 0, 0xFFFFFFFF),
        channel=_int_field(fields[4], "channel", 0, 0xFF),
        input_mv=_int_field(fields[5], "input_mv", -0x8000, 0x7FFF),
        output_mv=_int_field(fields[6], "output_mv", -0x8000, 0x7FFF),
        gain_milli=_int_field(fields[7], "gain_milli", 0, 0xFFFF),
        threshold=_int_field(fields[8], "threshold", 0, 1),
        fault_flags=int(fields[9], 16),
    )


def parse_command(record: str | bytes) -> Command:
    fields = decode_frame(record).fields
    if len(fields) < 5 or fields[:2] != ("AFE", "CMD"):
        raise ProtocolError("not an AFE command")
    seq = _int_field(fields[2], "seq", 0, 0xFFFF)
    tail = fields[3:]
    if len(tail) == 3 and tail[:2] == ("GET", "STATUS"):
        return Command(seq, "GET", "STATUS", _int_field(tail[2], "channel", 0, 0xFF))
    if len(tail) == 4 and tail[0] == "SET" and tail[1] in {"GAIN", "FILTER"}:
        return Command(
            seq, "SET", tail[1],
            _int_field(tail[2], "channel", 0, 0xFF),
            _int_field(tail[3], "value", 0, 0xFF),
        )
    if len(tail) == 3 and tail[0] == "RUN" and tail[1] in {"DC_SWEEP", "HYSTERESIS", "FREQUENCY_SWEEP"}:
        return Command(seq, "RUN", tail[1], _int_field(tail[2], "channel", 0, 0xFF))
    if tail == ("SAVE", "CALIBRATION"):
        return Command(seq, "SAVE", "CALIBRATION")
    raise ProtocolError("unsupported command shape")

