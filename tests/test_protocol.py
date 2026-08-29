import pytest

from dashboard.models import Telemetry
from dashboard.protocol import (
    CrcMismatch,
    FrameTooLong,
    ProtocolError,
    build_telemetry,
    decode_frame,
    encode_frame,
    parse_command,
    parse_telemetry,
)


def sample() -> Telemetry:
    return Telemetry(120, 45120, 0, 500, 2487, 4974, 1, 0)


def test_telemetry_round_trip() -> None:
    assert parse_telemetry(build_telemetry(sample())) == sample()


def test_crlf_is_accepted() -> None:
    record = build_telemetry(sample()).removesuffix("\n") + "\r\n"
    assert parse_telemetry(record) == sample()


def test_crc_corruption_is_rejected() -> None:
    record = build_telemetry(sample()).replace(",500,", ",501,")
    with pytest.raises(CrcMismatch):
        parse_telemetry(record)


def test_missing_field_with_recomputed_crc_is_rejected() -> None:
    short = encode_frame(("AFE", "TEL", 1, 2, 0, 10, 20, 1000, "0000"))
    with pytest.raises(ProtocolError, match="exactly ten"):
        parse_telemetry(short)


def test_overlong_input_is_rejected_before_crc() -> None:
    with pytest.raises(FrameTooLong):
        decode_frame("A" * 129)


def test_non_ascii_is_rejected() -> None:
    with pytest.raises(ProtocolError, match="ASCII"):
        decode_frame("AFE,TEL,温度,0000\n")


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        (("AFE", "CMD", 1, "GET", "STATUS", 0), ("GET", "STATUS", 0, None)),
        (("AFE", "CMD", 2, "SET", "GAIN", 0, 3), ("SET", "GAIN", 0, 3)),
        (("AFE", "CMD", 3, "RUN", "DC_SWEEP", 1), ("RUN", "DC_SWEEP", 1, None)),
        (("AFE", "CMD", 4, "SAVE", "CALIBRATION"), ("SAVE", "CALIBRATION", None, None)),
    ],
)
def test_supported_commands(fields, expected) -> None:
    command = parse_command(encode_frame(fields))
    assert (command.verb, command.subject, command.channel, command.value) == expected


def test_unsupported_command_is_rejected() -> None:
    with pytest.raises(ProtocolError, match="unsupported"):
        parse_command(encode_frame(("AFE", "CMD", 1, "ERASE", "ALL")))


def test_out_of_range_threshold_is_rejected() -> None:
    record = encode_frame(("AFE", "TEL", 1, 2, 0, 10, 20, 1000, 2, "0000"))
    with pytest.raises(ProtocolError, match="threshold"):
        parse_telemetry(record)

