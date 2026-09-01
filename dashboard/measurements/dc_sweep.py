"""Least-squares analysis for DC sweep points."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SweepPoint:
    """One legacy Phase 0 DC sweep point in millivolts."""

    input_mv: float
    output_mv: float


@dataclass(frozen=True, slots=True)
class FitResult:
    """Legacy Phase 0 linear-fit result awaiting Phase 3 migration."""

    gain: float
    offset_mv: float
    r_squared: float
    used_points: int
    excluded_points: int = 0


def exclude_saturated(
    points: Iterable[SweepPoint],
    *,
    low_output_mv: float = 25.0,
    high_output_mv: float = 3275.0,
) -> tuple[list[SweepPoint], list[SweepPoint]]:
    """Split points into an open output interval and excluded saturation bands."""
    if low_output_mv >= high_output_mv:
        raise ValueError("low saturation limit must be below high limit")
    kept: list[SweepPoint] = []
    excluded: list[SweepPoint] = []
    for point in points:
        (kept if low_output_mv < point.output_mv < high_output_mv else excluded).append(point)
    return kept, excluded


def linear_fit(points: Sequence[SweepPoint]) -> FitResult:
    """Fit y = gain*x + offset by ordinary least squares."""
    if len(points) < 2:
        raise ValueError("at least two points are required")
    mean_x = sum(point.input_mv for point in points) / len(points)
    mean_y = sum(point.output_mv for point in points) / len(points)
    sxx = sum((point.input_mv - mean_x) ** 2 for point in points)
    if sxx == 0:
        raise ValueError("input values must not all be equal")
    sxy = sum((point.input_mv - mean_x) * (point.output_mv - mean_y) for point in points)
    gain = sxy / sxx
    offset = mean_y - gain * mean_x
    residual = sum((point.output_mv - (gain * point.input_mv + offset)) ** 2 for point in points)
    total = sum((point.output_mv - mean_y) ** 2 for point in points)
    r_squared = 1.0 if total == 0 and residual == 0 else (0.0 if total == 0 else 1.0 - residual / total)
    return FitResult(gain, offset, r_squared, len(points))


def analyze_dc_sweep(
    points: Sequence[SweepPoint],
    *,
    low_output_mv: float = 25.0,
    high_output_mv: float = 3275.0,
) -> FitResult:
    kept, excluded = exclude_saturated(
        points, low_output_mv=low_output_mv, high_output_mv=high_output_mv
    )
    result = linear_fit(kept)
    return FitResult(
        result.gain,
        result.offset_mv,
        result.r_squared,
        result.used_points,
        len(excluded),
    )
