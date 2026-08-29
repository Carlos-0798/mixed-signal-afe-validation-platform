"""Data models shared by protocol and measurement analysis."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Telemetry:
    seq: int
    time_ms: int
    channel: int
    input_mv: int
    output_mv: int
    gain_milli: int
    threshold: int
    fault_flags: int


@dataclass(frozen=True)
class Command:
    seq: int
    verb: str
    subject: str
    channel: int | None = None
    value: int | None = None


@dataclass(frozen=True)
class SweepPoint:
    input_mv: float
    output_mv: float


@dataclass(frozen=True)
class FitResult:
    gain: float
    offset_mv: float
    r_squared: float
    used_points: int
    excluded_points: int = 0


@dataclass(frozen=True)
class HysteresisResult:
    threshold_high_mv: float
    threshold_low_mv: float
    width_mv: float

