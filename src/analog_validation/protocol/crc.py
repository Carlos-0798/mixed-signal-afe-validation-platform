"""Single implementation of CRC-16/CCITT-FALSE."""

from __future__ import annotations

CRC16_CCITT_FALSE_POLYNOMIAL = 0x1021
CRC16_CCITT_FALSE_INITIAL = 0xFFFF
CRC16_CCITT_FALSE_XOR_OUT = 0x0000


def crc16_ccitt_false(data: bytes | bytearray | memoryview) -> int:
    """Return CRC-16/CCITT-FALSE for a bytes-like payload.

    Parameters are poly=0x1021, init=0xFFFF, refin=false, refout=false, and
    xorout=0x0000. Text callers must choose an encoding before this layer.
    """

    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("data must be bytes-like")

    crc = CRC16_CCITT_FALSE_INITIAL
    for byte in bytes(data):
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ CRC16_CCITT_FALSE_POLYNOMIAL) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc ^ CRC16_CCITT_FALSE_XOR_OUT


__all__ = [
    "CRC16_CCITT_FALSE_INITIAL",
    "CRC16_CCITT_FALSE_POLYNOMIAL",
    "CRC16_CCITT_FALSE_XOR_OUT",
    "crc16_ccitt_false",
]
