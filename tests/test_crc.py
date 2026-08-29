from dashboard.protocol import crc16_ccitt_false


def test_ccitt_false_known_vector() -> None:
    assert crc16_ccitt_false(b"123456789") == 0x29B1


def test_ccitt_false_empty_payload() -> None:
    assert crc16_ccitt_false(b"") == 0xFFFF


def test_crc_is_byte_sensitive() -> None:
    assert crc16_ccitt_false(b"AFE") != crc16_ccitt_false(b"afe")

