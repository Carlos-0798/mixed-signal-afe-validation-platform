"""Public bounded ASCII framing and CRC primitives."""

from .crc import (
    CRC16_CCITT_FALSE_INITIAL,
    CRC16_CCITT_FALSE_POLYNOMIAL,
    CRC16_CCITT_FALSE_XOR_OUT,
    crc16_ccitt_false,
)
from .framing import MAX_RECORD_BYTES, Frame, decode_frame, encode_frame

__all__ = [
    "CRC16_CCITT_FALSE_INITIAL",
    "CRC16_CCITT_FALSE_POLYNOMIAL",
    "CRC16_CCITT_FALSE_XOR_OUT",
    "MAX_RECORD_BYTES",
    "Frame",
    "crc16_ccitt_false",
    "decode_frame",
    "encode_frame",
]
