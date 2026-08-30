"""Profile-configurable modular sequence continuity tracking."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from analog_validation.errors import ValidationError

MIN_SEQUENCE_BITS = 2
MAX_SEQUENCE_BITS = 64


class SequenceDisposition(str, Enum):
    """Relationship between one sequence value and the accepted high-water mark."""

    FIRST = "FIRST"
    IN_ORDER = "IN_ORDER"
    GAP = "GAP"
    DUPLICATE = "DUPLICATE"
    OUT_OF_ORDER = "OUT_OF_ORDER"


@dataclass(frozen=True, slots=True)
class SequenceObservation:
    """Explainable result from observing one modular sequence value."""

    sequence: int
    previous_sequence: int | None
    disposition: SequenceDisposition
    missing_count: int = 0


def _require_bits(bits: int) -> int:
    if isinstance(bits, bool) or not isinstance(bits, int):
        raise ValidationError("sequence bits must be an integer")
    if not MIN_SEQUENCE_BITS <= bits <= MAX_SEQUENCE_BITS:
        raise ValidationError(
            f"sequence bits must be between {MIN_SEQUENCE_BITS} and "
            f"{MAX_SEQUENCE_BITS}"
        )
    return bits


class SequenceTracker:
    """Track gaps and reordering with a profile-supplied sequence width.

    Values less than half a modular range ahead advance the high-water mark.
    Duplicate and out-of-order values are reported but do not move it backward.
    """

    def __init__(self, bits: int) -> None:
        self._bits = _require_bits(bits)
        self._modulus = 1 << self._bits
        self._half_range = self._modulus >> 1
        self._last_sequence: int | None = None

    @property
    def bits(self) -> int:
        """Configured sequence field width."""

        return self._bits

    @property
    def modulus(self) -> int:
        """First invalid value and wrap modulus for this profile."""

        return self._modulus

    @property
    def last_sequence(self) -> int | None:
        """Most recent accepted high-water sequence value."""

        return self._last_sequence

    def _require_sequence(self, sequence: int) -> int:
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            raise ValidationError("sequence must be an integer")
        if not 0 <= sequence < self._modulus:
            raise ValidationError(
                f"sequence must be between 0 and {self._modulus - 1}"
            )
        return sequence

    def observe(self, sequence: int) -> SequenceObservation:
        """Classify one sequence and advance only for new forward progress."""

        current = self._require_sequence(sequence)
        previous = self._last_sequence
        if previous is None:
            disposition = SequenceDisposition.FIRST
            missing_count = 0
            self._last_sequence = current
        else:
            delta = (current - previous) % self._modulus
            if delta == 0:
                disposition = SequenceDisposition.DUPLICATE
                missing_count = 0
            elif delta == 1:
                disposition = SequenceDisposition.IN_ORDER
                missing_count = 0
                self._last_sequence = current
            elif delta < self._half_range:
                disposition = SequenceDisposition.GAP
                missing_count = delta - 1
                self._last_sequence = current
            else:
                disposition = SequenceDisposition.OUT_OF_ORDER
                missing_count = 0

        return SequenceObservation(current, previous, disposition, missing_count)

    def reset(self) -> int | None:
        """Clear continuity state and return the previous high-water mark."""

        previous = self._last_sequence
        self._last_sequence = None
        return previous


__all__ = [
    "MAX_SEQUENCE_BITS",
    "MIN_SEQUENCE_BITS",
    "SequenceDisposition",
    "SequenceObservation",
    "SequenceTracker",
]
