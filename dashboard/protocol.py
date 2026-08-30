"""Strict encoder/parser for the Phase 0 AFE ASCII CSV protocol."""

from __future__ import annotations

import re

from analog_validation.errors import (
    CrcMismatch,
    FrameTooLong,
    FramingError,
    ProtocolError,
)
from analog_validation.protocol import (
    MAX_RECORD_BYTES,
    Frame,
    crc16_ccitt_false,
    decode_frame,
    encode_frame,
)

from .models import Command, Telemetry

_HEX4 = re.compile(r"^[0-9A-F]{4}$")

__all__ = [
    "MAX_RECORD_BYTES",
    "CrcMismatch",
    "Frame",
    "FrameTooLong",
    "FramingError",
    "ProtocolError",
    "build_telemetry",
    "crc16_ccitt_false",
    "decode_frame",
    "encode_frame",
    "parse_command",
    "parse_telemetry",
]


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
