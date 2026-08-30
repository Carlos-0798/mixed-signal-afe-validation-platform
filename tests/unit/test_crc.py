"""Golden and boundary tests for the single public CRC implementation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from analog_validation import (
    CRC16_CCITT_FALSE_INITIAL,
    CRC16_CCITT_FALSE_POLYNOMIAL,
    CRC16_CCITT_FALSE_XOR_OUT,
    crc16_ccitt_false,
)

GOLDEN_FILE = (
    Path(__file__).resolve().parents[2]
    / "test-data"
    / "golden"
    / "crc16_ccitt_false.json"
)


def test_ccitt_false_parameters_are_explicit_and_stable() -> None:
    assert CRC16_CCITT_FALSE_POLYNOMIAL == 0x1021
    assert CRC16_CCITT_FALSE_INITIAL == 0xFFFF
    assert CRC16_CCITT_FALSE_XOR_OUT == 0x0000


def test_ccitt_false_golden_vectors() -> None:
    document = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))

    assert document["algorithm"] == "CRC-16/CCITT-FALSE"
    assert document["parameters"] == {
        "width": 16,
        "polynomial": "1021",
        "initial": "FFFF",
        "reflect_input": False,
        "reflect_output": False,
        "xor_out": "0000",
    }
    for vector in document["vectors"]:
        payload = bytes.fromhex(vector["input_hex"])
        assert f"{crc16_ccitt_false(payload):04X}" == vector["expected_hex"], vector[
            "name"
        ]


def test_crc_accepts_common_bytes_like_inputs() -> None:
    expected = crc16_ccitt_false(b"123456789")

    assert crc16_ccitt_false(bytearray(b"123456789")) == expected
    assert crc16_ccitt_false(memoryview(b"123456789")) == expected


def test_crc_is_byte_sensitive() -> None:
    assert crc16_ccitt_false(b"AFE") != crc16_ccitt_false(b"afe")


@pytest.mark.parametrize("value", ["123456789", None, [1, 2, 3]])
def test_crc_rejects_non_bytes_inputs(value: object) -> None:
    with pytest.raises(TypeError, match="bytes-like"):
        crc16_ccitt_false(cast(Any, value))
