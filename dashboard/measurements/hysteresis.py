"""Threshold and hysteresis calculations from ordered samples."""

from __future__ import annotations

from collections.abc import Sequence

from ..models import HysteresisResult

Sample = tuple[float, int]


def _transition_midpoint(samples: Sequence[Sample], before: int, after: int) -> float:
    if len(samples) < 2:
        raise ValueError("at least two ordered samples are required")
    for (previous_mv, previous_state), (current_mv, current_state) in zip(samples, samples[1:]):
        if previous_state == before and current_state == after:
            return (previous_mv + current_mv) / 2.0
    raise ValueError(f"no {before}->{after} transition found")


def calculate_hysteresis(rising_samples: Sequence[Sample], falling_samples: Sequence[Sample]) -> HysteresisResult:
    """Interpolate rising 0->1 and falling 1->0 trips at sample midpoints."""
    high = _transition_midpoint(rising_samples, 0, 1)
    low = _transition_midpoint(falling_samples, 1, 0)
    if high < low:
        raise ValueError("high threshold is below low threshold")
    return HysteresisResult(high, low, high - low)

