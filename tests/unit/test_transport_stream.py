"""Tests for the profile-neutral bounded line stream state machine."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from analog_validation.errors import ValidationError
from analog_validation.transport import (
    BoundedLineFramer,
    StreamIssueKind,
)


def test_fragmented_and_coalesced_records_preserve_raw_bytes() -> None:
    framer = BoundedLineFramer(128)

    first = framer.feed(b"AFE,1,T")
    second = framer.feed(b"EL,1\r\nTEL,2\npartial")

    assert first.records == ()
    assert first.issues == ()
    assert second.records == (b"AFE,1,TEL,1\r\n", b"TEL,2\n")
    assert second.issues == ()
    assert framer.pending_bytes == len(b"partial")


def test_transport_does_not_assume_ascii_csv_namespace_or_nonempty_lines() -> None:
    framer = BoundedLineFramer(8)

    result = framer.feed(b"\xff\x00\n\n")

    assert result.records == (b"\xff\x00\n", b"\n")
    assert result.issues == ()


def test_exact_limit_is_accepted_and_next_byte_is_rejected_then_recovers() -> None:
    framer = BoundedLineFramer(4)

    result = framer.feed(b"abc\nabcd\nok\n")

    assert result.records == (b"abc\n", b"ok\n")
    assert len(result.issues) == 1
    assert result.issues[0].kind is StreamIssueKind.OVERLONG_RECORD
    assert result.issues[0].discarded_bytes == 5
    assert framer.pending_bytes == 0
    assert framer.discarding_overlong is False


def test_overlong_record_across_chunks_stays_bounded_and_recovers_on_lf() -> None:
    framer = BoundedLineFramer(4)

    first = framer.feed(b"abcde")
    second = framer.feed(b"fg\nZ\n")

    assert first.records == ()
    assert first.issues == ()
    assert framer.discarding_overlong is False
    assert second.records == (b"Z\n",)
    assert second.issues[0].discarded_bytes == 8


def test_overlong_state_is_visible_before_recovery() -> None:
    framer = BoundedLineFramer(4)

    result = framer.feed(b"abcde")

    assert result.records == ()
    assert framer.discarding_overlong is True
    assert framer.pending_bytes == 5


def test_empty_and_all_supported_bytes_like_chunks_are_accepted() -> None:
    framer = BoundedLineFramer(8)

    assert framer.feed(b"").records == ()
    assert framer.feed(bytearray(b"A")).records == ()
    result = framer.feed(memoryview(b"\n"))

    assert result.records == (b"A\n",)
    assert framer.max_record_bytes == 8


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "128"])
def test_limit_validation_is_strict(limit: object) -> None:
    with pytest.raises(ValidationError, match="max_record_bytes"):
        BoundedLineFramer(cast(Any, limit))


def test_feed_rejects_non_bytes_like_data() -> None:
    framer = BoundedLineFramer(8)

    with pytest.raises(ValidationError, match="bytes-like"):
        framer.feed(cast(Any, "text"))


def test_reset_reports_and_clears_normal_partial_state() -> None:
    framer = BoundedLineFramer(8)
    framer.feed(b"part")

    reset = framer.reset()

    assert reset.discarded_bytes == 4
    assert reset.was_discarding_overlong is False
    assert framer.pending_bytes == 0
    assert framer.feed(b"new\n").records == (b"new\n",)


def test_reset_reports_and_clears_overlong_state() -> None:
    framer = BoundedLineFramer(3)
    framer.feed(b"toolong")

    reset = framer.reset()

    assert reset.discarded_bytes == 7
    assert reset.was_discarding_overlong is True
    assert framer.discarding_overlong is False


def test_feed_result_and_issue_are_immutable() -> None:
    result = BoundedLineFramer(1).feed(b"xx\n")

    with pytest.raises(FrozenInstanceError):
        result.records = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.issues[0].discarded_bytes = 0  # type: ignore[misc]
