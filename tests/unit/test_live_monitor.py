from __future__ import annotations

from datetime import datetime, timezone
from threading import Event, Thread
from typing import Any, cast

import pytest

from analog_validation import (
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
    QualityFlag,
)
from analog_validation_app import (
    ProductCancellationToken,
    ProductRequestError,
    ProductServiceError,
)
from analog_validation_app.errors import ProductJobCancelled
from analog_validation_app.live import (
    LIVE_MONITOR_SCHEMA_VERSION,
    MAX_LIVE_MONITOR_INTERVAL_SECONDS,
    MAX_LIVE_MONITOR_MAX_POINTS,
    MAX_LIVE_MONITOR_WINDOW_SECONDS,
    MIN_LIVE_MONITOR_WINDOW_SECONDS,
    LiveMonitorSession,
    LiveMonitorSnapshot,
    LiveTracePoint,
)

NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)


def measurement(
    index: int = 1,
    channel: str = "afe.ch0.input",
    *,
    status: MeasurementStatus = MeasurementStatus.VALID,
) -> Measurement:
    flags: frozenset[QualityFlag] = frozenset()
    if status is MeasurementStatus.SUSPECT:
        flags = frozenset({QualityFlag.TIME_ANOMALY})
    elif status is MeasurementStatus.INVALID:
        flags = frozenset({QualityFlag.DEVICE_FAULT})
    return Measurement(
        f"measurement-{index}",
        f"raw-{index}",
        NOW,
        channel,
        float(index),
        MeasurementUnit.MILLIVOLT,
        status,
        EvidenceSource.SYNTHETIC,
        flags,
    )


def point(index: int = 1, *, elapsed: float = 0.0) -> LiveTracePoint:
    return LiveTracePoint(index, index - 1, elapsed, measurement(index))


def test_live_trace_models_are_versioned_frozen_and_windowed() -> None:
    points = (point(1, elapsed=0.0), point(2, elapsed=0.4), point(3, elapsed=1.0))
    snapshot = LiveMonitorSnapshot(points, 3, 0, False, 1, 0.5, 3, 0, 0)

    assert snapshot.schema_version == LIVE_MONITOR_SCHEMA_VERSION
    assert snapshot.visible_points == points[2:]
    assert LiveMonitorSnapshot((), 0, 0, False, 0, 1.0, 0, 0, 0).visible_points == ()


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"index": 0}, "index"),
        ({"cycle_index": -1}, "cycle_index"),
        ({"elapsed_seconds": float("nan")}, "elapsed_seconds"),
        ({"measurement": object()}, "Measurement"),
        ({"schema_version": "live-monitor.v2"}, "schema"),
    ],
)
def test_live_trace_point_rejects_invalid_fields(
    changes: dict[str, object], message: str
) -> None:
    values: dict[str, object] = {
        "index": 1,
        "cycle_index": 0,
        "elapsed_seconds": 0.0,
        "measurement": measurement(),
    }
    values.update(changes)
    with pytest.raises(ProductRequestError, match=message):
        LiveTracePoint(**cast(Any, values))


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"points": cast(Any, "points")}, "tuple"),
        ({"points": (object(),)}, "LiveTracePoint"),
        ({"total_points": True}, "integer"),
        ({"evicted_points": -1}, "between"),
        ({"total_points": 2}, "retained plus evicted"),
        (
            {
                "points": (point(2),),
                "total_points": 1,
            },
            "indexes",
        ),
        (
            {
                "points": (point(1, elapsed=1.0), point(2, elapsed=0.0)),
                "total_points": 2,
            },
            "elapsed times",
        ),
        ({"paused": cast(Any, 1)}, "paused"),
        ({"pause_count": cast(Any, True)}, "integer"),
        ({"time_window_seconds": 0.0}, "time_window_seconds"),
        ({"valid_points": 0}, "status counts"),
        ({"invalid_points": True}, "integer"),
        ({"schema_version": "live-monitor.v2"}, "schema"),
    ],
)
def test_live_monitor_snapshot_rejects_inconsistent_fields(
    values: dict[str, object], message: str
) -> None:
    defaults: dict[str, object] = {
        "points": (point(),),
        "total_points": 1,
        "evicted_points": 0,
        "paused": False,
        "pause_count": 0,
        "time_window_seconds": 1.0,
        "valid_points": 1,
        "suspect_points": 0,
        "invalid_points": 0,
    }
    defaults.update(values)
    with pytest.raises(ProductRequestError, match=message):
        LiveMonitorSnapshot(**cast(Any, defaults))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_points": 0}, "max_points"),
        ({"max_points": MAX_LIVE_MONITOR_MAX_POINTS + 1}, "max_points"),
        (
            {"time_window_seconds": MIN_LIVE_MONITOR_WINDOW_SECONDS - 0.01},
            "time_window_seconds",
        ),
        (
            {"time_window_seconds": MAX_LIVE_MONITOR_WINDOW_SECONDS + 1},
            "time_window_seconds",
        ),
        ({"clock": object()}, "clock"),
    ],
)
def test_live_monitor_session_rejects_invalid_configuration(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(ProductRequestError, match=message):
        LiveMonitorSession(**cast(Any, kwargs))


def test_live_monitor_session_bounds_points_and_tracks_presentation_window() -> None:
    times = iter((10.0, 10.25, 11.0))
    session = LiveMonitorSession(
        max_points=2,
        time_window_seconds=0.5,
        clock=lambda: next(times),
    )

    assert session.max_points == 2
    assert session.is_paused is False
    session.publish(0, measurement(1))
    session.publish(1, measurement(2))
    retained = session.publish(2, measurement(3))
    snapshot = session.snapshot()

    assert retained.index == 3
    assert tuple(value.index for value in snapshot.points) == (2, 3)
    assert snapshot.total_points == 3
    assert snapshot.evicted_points == 1
    assert snapshot.visible_points == (retained,)
    updated = session.set_time_window(2.0)
    assert updated.visible_points == updated.points


def test_live_monitor_session_tracks_all_measurement_statuses() -> None:
    session = LiveMonitorSession()

    session.publish(0, measurement(1))
    session.publish(1, measurement(2, status=MeasurementStatus.SUSPECT))
    session.publish(2, measurement(3, status=MeasurementStatus.INVALID))

    snapshot = session.snapshot()
    assert snapshot.valid_points == 1
    assert snapshot.suspect_points == 1
    assert snapshot.invalid_points == 1


@pytest.mark.parametrize("value", [True, "0", float("nan"), float("inf")])
def test_live_monitor_clock_requires_finite_numeric_values(value: object) -> None:
    session = LiveMonitorSession(clock=lambda: cast(Any, value))
    with pytest.raises(ProductServiceError, match="finite"):
        session.publish(0, measurement())


def test_live_monitor_rejects_bad_publish_values_and_backward_clock() -> None:
    session = LiveMonitorSession()
    with pytest.raises(ProductRequestError, match="cycle_index"):
        session.publish(cast(Any, True), measurement())
    with pytest.raises(ProductRequestError, match="Measurement"):
        session.publish(0, cast(Any, object()))

    times = iter((2.0, 1.0))
    regressing = LiveMonitorSession(clock=lambda: next(times))
    regressing.publish(0, measurement())
    with pytest.raises(ProductServiceError, match="backwards"):
        regressing.publish(1, measurement(2))


def test_pause_resume_are_idempotent_and_checkpoint_wakes_on_resume() -> None:
    session = LiveMonitorSession()
    token = ProductCancellationToken()
    assert session.pause() is True
    assert session.pause() is False
    assert session.is_paused is True
    started = Event()
    finished = Event()

    def check() -> None:
        started.set()
        session.checkpoint(token)
        finished.set()

    thread = Thread(target=check)
    thread.start()
    assert started.wait(1.0)
    assert finished.wait(0.02) is False
    assert session.resume() is True
    assert session.resume() is False
    assert finished.wait(1.0)
    thread.join(1.0)
    assert session.snapshot().pause_count == 1


def test_checkpoint_and_interval_wait_validate_token_and_honor_cancellation() -> None:
    session = LiveMonitorSession()
    with pytest.raises(ProductRequestError, match="cancellation"):
        session.checkpoint(cast(Any, object()))
    with pytest.raises(ProductRequestError, match="cancellation"):
        session.wait_interval(0.0, cast(Any, object()))
    token = ProductCancellationToken()
    session.wait_interval(0.0, token)
    token._request()
    with pytest.raises(ProductJobCancelled):
        session.checkpoint(token)
    with pytest.raises(ProductJobCancelled):
        session.wait_interval(0.01, token)


@pytest.mark.parametrize(
    "value",
    [True, "1", -1.0, float("nan"), MAX_LIVE_MONITOR_INTERVAL_SECONDS + 1],
)
def test_interval_wait_rejects_invalid_bounds(value: object) -> None:
    with pytest.raises(ProductRequestError, match="sample_interval_seconds"):
        LiveMonitorSession().wait_interval(cast(Any, value), ProductCancellationToken())


def test_interval_wait_completes_without_cancellation() -> None:
    session = LiveMonitorSession()
    session.wait_interval(0.001, ProductCancellationToken())


def test_interval_wait_rechecks_cancellation_after_a_signalled_wait() -> None:
    class SignalledToken(ProductCancellationToken):
        def __init__(self) -> None:
            super().__init__()
            self.checks = 0

        def wait(self, timeout_s: float) -> bool:
            return True

        def raise_if_cancelled(self) -> None:
            self.checks += 1
            if self.checks > 1:
                raise ProductJobCancelled("cancelled during interval")

    with pytest.raises(ProductJobCancelled, match="during interval"):
        LiveMonitorSession().wait_interval(0.01, SignalledToken())
