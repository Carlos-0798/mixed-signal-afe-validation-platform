"""Tests for profile-configurable modular sequence tracking."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest

from analog_validation.errors import ValidationError
from analog_validation.transport import (
    MAX_SEQUENCE_BITS,
    MIN_SEQUENCE_BITS,
    SequenceDisposition,
    SequenceTracker,
)


def test_first_in_order_gap_and_properties() -> None:
    tracker = SequenceTracker(16)

    first = tracker.observe(10)
    ordered = tracker.observe(11)
    gap = tracker.observe(15)

    assert tracker.bits == 16
    assert tracker.modulus == 65536
    assert first.previous_sequence is None
    assert first.disposition is SequenceDisposition.FIRST
    assert ordered.previous_sequence == 10
    assert ordered.disposition is SequenceDisposition.IN_ORDER
    assert gap.previous_sequence == 11
    assert gap.disposition is SequenceDisposition.GAP
    assert gap.missing_count == 3
    assert tracker.last_sequence == 15


@pytest.mark.parametrize(
    ("bits", "values", "expected_missing"),
    [
        (16, (65534, 65535, 0, 2), 1),
        (32, (4294967294, 4294967295, 0, 3), 2),
    ],
)
def test_wrap_is_in_order_and_wrap_gap_uses_profile_width(
    bits: int,
    values: tuple[int, int, int, int],
    expected_missing: int,
) -> None:
    tracker = SequenceTracker(bits)

    assert tracker.observe(values[0]).disposition is SequenceDisposition.FIRST
    assert tracker.observe(values[1]).disposition is SequenceDisposition.IN_ORDER
    assert tracker.observe(values[2]).disposition is SequenceDisposition.IN_ORDER
    wrapped_gap = tracker.observe(values[3])

    assert wrapped_gap.disposition is SequenceDisposition.GAP
    assert wrapped_gap.missing_count == expected_missing


def test_duplicate_and_out_of_order_do_not_move_high_water_mark() -> None:
    tracker = SequenceTracker(8)
    tracker.observe(100)

    duplicate = tracker.observe(100)
    old = tracker.observe(99)
    next_value = tracker.observe(101)

    assert duplicate.disposition is SequenceDisposition.DUPLICATE
    assert old.disposition is SequenceDisposition.OUT_OF_ORDER
    assert tracker.last_sequence == 101
    assert next_value.previous_sequence == 100
    assert next_value.disposition is SequenceDisposition.IN_ORDER


def test_exact_half_range_is_conservatively_out_of_order() -> None:
    tracker = SequenceTracker(8)
    tracker.observe(0)

    observation = tracker.observe(128)

    assert observation.disposition is SequenceDisposition.OUT_OF_ORDER
    assert tracker.last_sequence == 0


@pytest.mark.parametrize(
    "bits",
    [MIN_SEQUENCE_BITS - 1, MAX_SEQUENCE_BITS + 1, True, 16.0, "16"],
)
def test_sequence_width_validation_is_strict(bits: object) -> None:
    with pytest.raises(ValidationError, match="sequence bits"):
        SequenceTracker(cast(Any, bits))


@pytest.mark.parametrize("sequence", [-1, 256, True, 1.5, "1"])
def test_sequence_value_validation_is_strict(sequence: object) -> None:
    tracker = SequenceTracker(8)

    with pytest.raises(ValidationError, match="sequence"):
        tracker.observe(cast(Any, sequence))


def test_reset_returns_high_water_mark_and_next_value_is_first() -> None:
    tracker = SequenceTracker(16)
    tracker.observe(7)

    assert tracker.reset() == 7
    assert tracker.last_sequence is None
    assert tracker.reset() is None
    assert tracker.observe(3).disposition is SequenceDisposition.FIRST


def test_observation_is_immutable() -> None:
    observation = SequenceTracker(16).observe(1)

    with pytest.raises(FrozenInstanceError):
        observation.sequence = 2  # type: ignore[misc]
