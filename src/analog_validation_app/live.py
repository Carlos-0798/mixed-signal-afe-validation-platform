"""Bounded in-memory state for presentation-only live monitoring."""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from threading import Condition
from time import monotonic

from analog_validation import Measurement, MeasurementStatus

from .errors import ProductRequestError, ProductServiceError
from .worker import ProductCancellationToken

LIVE_MONITOR_SCHEMA_VERSION = "live-monitor.v1"
DEFAULT_LIVE_MONITOR_MAX_POINTS = 2_048
MAX_LIVE_MONITOR_MAX_POINTS = 10_000
MIN_LIVE_MONITOR_WINDOW_SECONDS = 0.1
MAX_LIVE_MONITOR_WINDOW_SECONDS = 3_600.0
MAX_LIVE_MONITOR_INTERVAL_SECONDS = 60.0
MAX_LIVE_MONITOR_DURATION_SECONDS = 55.0
LIVE_MONITOR_CONTROL_POLL_SECONDS = 0.05

MonotonicClock = Callable[[], float]


def _integer(name: str, value: object, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProductRequestError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise ProductRequestError(f"{name} must be between {minimum} and {maximum}")
    return value


def _seconds(
    name: str,
    value: object,
    *,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProductRequestError(f"{name} must be a finite number")
    checked = float(value)
    if not math.isfinite(checked):
        raise ProductRequestError(f"{name} must be a finite number")
    if not minimum <= checked <= maximum:
        raise ProductRequestError(
            f"{name} must be between {minimum:g} and {maximum:g} seconds"
        )
    return checked


@dataclass(frozen=True, slots=True)
class LiveTracePoint:
    """One measurement copied into a bounded live-view sequence."""

    index: int
    cycle_index: int
    elapsed_seconds: float
    measurement: Measurement
    schema_version: str = LIVE_MONITOR_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _integer("live point index", self.index, minimum=1, maximum=2**63 - 1)
        _integer(
            "live point cycle_index",
            self.cycle_index,
            minimum=0,
            maximum=2**63 - 1,
        )
        _seconds(
            "live point elapsed_seconds",
            self.elapsed_seconds,
            minimum=0.0,
            maximum=float(2**31),
        )
        if not isinstance(self.measurement, Measurement):
            raise ProductRequestError("live point measurement must be a Measurement")
        if self.schema_version != LIVE_MONITOR_SCHEMA_VERSION:
            raise ProductRequestError(
                f"unsupported live monitor schema: {self.schema_version}"
            )


@dataclass(frozen=True, slots=True)
class LiveMonitorSnapshot:
    """Immutable trace/control snapshot safe to move onto the UI thread."""

    points: tuple[LiveTracePoint, ...]
    total_points: int
    evicted_points: int
    paused: bool
    pause_count: int
    time_window_seconds: float
    valid_points: int
    suspect_points: int
    invalid_points: int
    schema_version: str = LIVE_MONITOR_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.points, tuple) or not all(
            isinstance(point, LiveTracePoint) for point in self.points
        ):
            raise ProductRequestError(
                "live monitor points must be a tuple of LiveTracePoint values"
            )
        total = _integer(
            "live monitor total_points",
            self.total_points,
            minimum=0,
            maximum=2**63 - 1,
        )
        evicted = _integer(
            "live monitor evicted_points",
            self.evicted_points,
            minimum=0,
            maximum=2**63 - 1,
        )
        if total != len(self.points) + evicted:
            raise ProductRequestError(
                "live monitor total_points must equal retained plus evicted points"
            )
        if self.points:
            indexes = tuple(point.index for point in self.points)
            if indexes != tuple(range(evicted + 1, total + 1)):
                raise ProductRequestError(
                    "retained live point indexes must be contiguous after eviction"
                )
            elapsed = tuple(point.elapsed_seconds for point in self.points)
            if elapsed != tuple(sorted(elapsed)):
                raise ProductRequestError(
                    "retained live point elapsed times must be non-decreasing"
                )
        if not isinstance(self.paused, bool):
            raise ProductRequestError("live monitor paused must be boolean")
        _integer(
            "live monitor pause_count",
            self.pause_count,
            minimum=0,
            maximum=2**63 - 1,
        )
        _seconds(
            "live monitor time_window_seconds",
            self.time_window_seconds,
            minimum=MIN_LIVE_MONITOR_WINDOW_SECONDS,
            maximum=MAX_LIVE_MONITOR_WINDOW_SECONDS,
        )
        status_total = 0
        for name in ("valid_points", "suspect_points", "invalid_points"):
            status_total += _integer(
                f"live monitor {name}",
                getattr(self, name),
                minimum=0,
                maximum=2**63 - 1,
            )
        if status_total != total:
            raise ProductRequestError(
                "live monitor status counts must equal total_points"
            )
        if self.schema_version != LIVE_MONITOR_SCHEMA_VERSION:
            raise ProductRequestError(
                f"unsupported live monitor schema: {self.schema_version}"
            )

    @property
    def visible_points(self) -> tuple[LiveTracePoint, ...]:
        """Return retained points inside the configured trailing time window."""

        if not self.points:
            return ()
        cutoff = self.points[-1].elapsed_seconds - self.time_window_seconds
        return tuple(point for point in self.points if point.elapsed_seconds >= cutoff)


class LiveMonitorSession:
    """Thread-safe bounded trace plus cooperative pause/resume control."""

    def __init__(
        self,
        *,
        max_points: int = DEFAULT_LIVE_MONITOR_MAX_POINTS,
        time_window_seconds: float = 5.0,
        clock: MonotonicClock = monotonic,
    ) -> None:
        self._max_points = _integer(
            "max_points",
            max_points,
            minimum=1,
            maximum=MAX_LIVE_MONITOR_MAX_POINTS,
        )
        self._time_window_seconds = _seconds(
            "time_window_seconds",
            time_window_seconds,
            minimum=MIN_LIVE_MONITOR_WINDOW_SECONDS,
            maximum=MAX_LIVE_MONITOR_WINDOW_SECONDS,
        )
        if not callable(clock):
            raise ProductRequestError("clock must be callable")
        self._clock = clock
        self._condition = Condition()
        self._points: deque[LiveTracePoint] = deque()
        self._total_points = 0
        self._evicted_points = 0
        self._started_at: float | None = None
        self._last_elapsed_seconds = 0.0
        self._paused = False
        self._pause_count = 0
        self._valid_points = 0
        self._suspect_points = 0
        self._invalid_points = 0

    @property
    def max_points(self) -> int:
        return self._max_points

    @property
    def is_paused(self) -> bool:
        with self._condition:
            return self._paused

    def publish(self, cycle_index: int, measurement: Measurement) -> LiveTracePoint:
        """Append one immutable point, evicting only the oldest retained point."""

        checked_cycle = _integer(
            "cycle_index", cycle_index, minimum=0, maximum=2**63 - 1
        )
        if not isinstance(measurement, Measurement):
            raise ProductRequestError("measurement must be a Measurement")
        current = self._clock()
        if isinstance(current, bool) or not isinstance(current, (int, float)):
            raise ProductServiceError("live monitor clock must return a finite number")
        now = float(current)
        if not math.isfinite(now):
            raise ProductServiceError("live monitor clock must return a finite number")
        with self._condition:
            if self._started_at is None:
                self._started_at = now
            elapsed = now - self._started_at
            if elapsed < self._last_elapsed_seconds:
                raise ProductServiceError("live monitor clock moved backwards")
            self._last_elapsed_seconds = elapsed
            self._total_points += 1
            point = LiveTracePoint(
                self._total_points,
                checked_cycle,
                elapsed,
                measurement,
            )
            self._points.append(point)
            if measurement.status is MeasurementStatus.VALID:
                self._valid_points += 1
            elif measurement.status is MeasurementStatus.SUSPECT:
                self._suspect_points += 1
            else:
                self._invalid_points += 1
            if len(self._points) > self._max_points:
                self._points.popleft()
                self._evicted_points += 1
            return point

    def snapshot(self) -> LiveMonitorSnapshot:
        """Return one internally consistent point/control snapshot."""

        with self._condition:
            return LiveMonitorSnapshot(
                tuple(self._points),
                self._total_points,
                self._evicted_points,
                self._paused,
                self._pause_count,
                self._time_window_seconds,
                self._valid_points,
                self._suspect_points,
                self._invalid_points,
            )

    def set_time_window(self, seconds: float) -> LiveMonitorSnapshot:
        """Change only the presentation window; acquisition is unaffected."""

        checked = _seconds(
            "time_window_seconds",
            seconds,
            minimum=MIN_LIVE_MONITOR_WINDOW_SECONDS,
            maximum=MAX_LIVE_MONITOR_WINDOW_SECONDS,
        )
        with self._condition:
            self._time_window_seconds = checked
        return self.snapshot()

    def pause(self) -> bool:
        """Pause at the next worker checkpoint; return whether state changed."""

        with self._condition:
            if self._paused:
                return False
            self._paused = True
            self._pause_count += 1
            return True

    def resume(self) -> bool:
        """Resume a paused worker and wake every bounded checkpoint waiter."""

        with self._condition:
            if not self._paused:
                return False
            self._paused = False
            self._condition.notify_all()
            return True

    def checkpoint(self, cancellation: ProductCancellationToken) -> None:
        """Block while paused but remain responsive to cooperative cancellation."""

        if not isinstance(cancellation, ProductCancellationToken):
            raise ProductRequestError("cancellation must be a ProductCancellationToken")
        while True:
            cancellation.raise_if_cancelled()
            with self._condition:
                if not self._paused:
                    return
                self._condition.wait(LIVE_MONITOR_CONTROL_POLL_SECONDS)

    def wait_interval(
        self,
        seconds: float,
        cancellation: ProductCancellationToken,
    ) -> None:
        """Wait in short slices so pause and cancellation remain responsive."""

        remaining = _seconds(
            "sample_interval_seconds",
            seconds,
            minimum=0.0,
            maximum=MAX_LIVE_MONITOR_INTERVAL_SECONDS,
        )
        if not isinstance(cancellation, ProductCancellationToken):
            raise ProductRequestError("cancellation must be a ProductCancellationToken")
        while remaining > 0.0:
            self.checkpoint(cancellation)
            wait_for = min(remaining, LIVE_MONITOR_CONTROL_POLL_SECONDS)
            started = monotonic()
            if cancellation.wait(wait_for):
                cancellation.raise_if_cancelled()
            remaining -= monotonic() - started


__all__ = [
    "DEFAULT_LIVE_MONITOR_MAX_POINTS",
    "LIVE_MONITOR_CONTROL_POLL_SECONDS",
    "LIVE_MONITOR_SCHEMA_VERSION",
    "MAX_LIVE_MONITOR_DURATION_SECONDS",
    "MAX_LIVE_MONITOR_INTERVAL_SECONDS",
    "MAX_LIVE_MONITOR_MAX_POINTS",
    "MAX_LIVE_MONITOR_WINDOW_SECONDS",
    "MIN_LIVE_MONITOR_WINDOW_SECONDS",
    "LiveMonitorSession",
    "LiveMonitorSnapshot",
    "LiveTracePoint",
    "MonotonicClock",
]
