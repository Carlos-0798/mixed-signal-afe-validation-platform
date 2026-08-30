"""Tests for the public product exception hierarchy."""

from __future__ import annotations

import pytest

from analog_validation import (
    AnalogValidationError,
    CapabilityError,
    ConfigurationError,
    CrcMismatch,
    FrameTooLong,
    FramingError,
    ProtocolError,
    ReplayError,
    ReplayFormatError,
    ReplayLimitError,
    UnsupportedProtocolVersion,
    UnsupportedReplayVersion,
    ValidationError,
)


@pytest.mark.parametrize(
    "error_type",
    [
        ValidationError,
        ProtocolError,
        FramingError,
        FrameTooLong,
        CrcMismatch,
        UnsupportedProtocolVersion,
        CapabilityError,
        ConfigurationError,
        ReplayError,
        ReplayFormatError,
        ReplayLimitError,
        UnsupportedReplayVersion,
    ],
)
def test_every_product_error_is_caught_by_root(
    error_type: type[AnalogValidationError],
) -> None:
    with pytest.raises(AnalogValidationError, match="readable message"):
        raise error_type("readable message")


@pytest.mark.parametrize(
    "error_type",
    [FramingError, FrameTooLong, CrcMismatch, UnsupportedProtocolVersion],
)
def test_protocol_specializations_are_caught_as_protocol_errors(
    error_type: type[ProtocolError],
) -> None:
    with pytest.raises(ProtocolError):
        raise error_type("bad protocol record")


def test_non_protocol_families_remain_distinct() -> None:
    assert not issubclass(ValidationError, ProtocolError)
    assert not issubclass(CapabilityError, ProtocolError)
    assert not issubclass(ConfigurationError, ProtocolError)
    assert not issubclass(ReplayError, ProtocolError)


@pytest.mark.parametrize(
    "error_type",
    [ReplayFormatError, ReplayLimitError, UnsupportedReplayVersion],
)
def test_replay_specializations_are_caught_as_replay_errors(
    error_type: type[ReplayError],
) -> None:
    with pytest.raises(ReplayError):
        raise error_type("bad replay dataset")


def test_exception_chaining_preserves_low_level_cause() -> None:
    low_level = UnicodeDecodeError("ascii", b"\xff", 0, 1, "not ASCII")

    with pytest.raises(FramingError, match="ASCII") as captured:
        raise FramingError("record must contain ASCII only") from low_level

    assert captured.value.__cause__ is low_level
