"""Measure Phase 5 product-quality targets without hardware or network access."""

from __future__ import annotations

import argparse
import csv
import io
import json
import platform
import sys
import tempfile
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from analog_validation import (
    CSV_REPLAY_COLUMNS,
    CSV_REPLAY_SCHEMA_VERSION,
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
    TestRunOutcome,
    parse_csv_replay,
)
from analog_validation_app import (
    LiveMonitorSession,
    ProductCancellationToken,
    ProductJobRequest,
    ProductJobResult,
    ProductJobType,
    ProductJobWorker,
    ProductProgressReporter,
    ProductResultStatus,
    ProductSourceMode,
    ProductWorkerState,
    publish_portfolio_demo,
)

ACCEPTANCE_SCHEMA_VERSION = "phase5-product-quality-acceptance.v1"
REPLAY_COUNTS = (100, 1_000, 10_000)
EVENT_COUNT = 10_000
EVENT_QUEUE_LIMIT = 256
MAX_REPLAY_10K_SECONDS = 5.0
MAX_REPLAY_10K_PEAK_MIB = 128.0
MAX_EVENT_10K_SECONDS = 5.0
LIVE_MONITOR_POINT_COUNT = 10_000
LIVE_MONITOR_RETAINED_LIMIT = 2_048
MAX_LIVE_MONITOR_10K_SECONDS = 5.0
MAX_LIVE_MONITOR_10K_PEAK_MIB = 64.0
MAX_DEMO_SECONDS = 5.0


def _replay_payload(record_count: int) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CSV_REPLAY_COLUMNS)
    writer.writerow(
        (
            "META",
            CSV_REPLAY_SCHEMA_VERSION,
            f"quality-{record_count}",
            *("" for _ in range(10)),
        )
    )
    for index in range(record_count):
        writer.writerow(
            (
                "DATA",
                CSV_REPLAY_SCHEMA_VERSION,
                f"quality-{record_count}",
                f"record-{index:05d}",
                f"raw-{index:05d}",
                "2026-01-01T00:00:00.000000Z",
                "afe.ch0.input",
                str(index % 3301),
                "mV",
                "VALID",
                "SYNTHETIC",
                "",
                "",
            )
        )
    writer.writerow(
        (
            "END",
            CSV_REPLAY_SCHEMA_VERSION,
            f"quality-{record_count}",
            *("" for _ in range(9)),
            str(record_count),
        )
    )
    return stream.getvalue().encode()


def _measure_replay(record_count: int) -> dict[str, Any]:
    payload = _replay_payload(record_count)
    tracemalloc.start()
    started = perf_counter()
    dataset = parse_csv_replay(payload)
    elapsed = perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if len(dataset.records) != record_count:
        raise RuntimeError("replay parser returned an unexpected record count")
    return {
        "records": record_count,
        "input_bytes": len(payload),
        "elapsed_seconds": round(elapsed, 6),
        "peak_memory_mib": round(peak / (1024 * 1024), 3),
    }


class _BurstService:
    def __init__(self, event_count: int) -> None:
        self._event_count = event_count
        self.cleaned = False

    def run(
        self,
        request: ProductJobRequest,
        cancellation: ProductCancellationToken,
        report_progress: ProductProgressReporter,
    ) -> ProductJobResult:
        for index in range(1, self._event_count + 1):
            if index % 128 == 0:
                cancellation.raise_if_cancelled()
            report_progress(f"Acceptance event {index}.", index, self._event_count)
        return ProductJobResult(
            request,
            ProductResultStatus.COMPLETED,
            EvidenceSource.SYNTHETIC,
            ("Host-only event-volume acceptance; no hardware was accessed.",),
            TestRunOutcome.PASS,
        )

    def cleanup(self) -> None:
        self.cleaned = True


def _measure_event_volume() -> dict[str, Any]:
    request = ProductJobRequest(
        "quality-event-volume",
        ProductSourceMode.SIMULATOR,
        ProductJobType.READ,
        "afe",
        "1",
    )
    service = _BurstService(EVENT_COUNT)
    worker = ProductJobWorker(
        lambda _request: service,
        max_events=EVENT_QUEUE_LIMIT,
        join_timeout_s=10.0,
    )
    started = perf_counter()
    try:
        worker.start(request)
        if not worker.join(10.0):
            raise RuntimeError("event-volume worker did not finish")
        elapsed = perf_counter() - started
        retained = worker.events
        document: dict[str, Any] = {
            "requested_progress_events": EVENT_COUNT,
            "last_event_index": retained[-1].index,
            "retained_events": len(retained),
            "queue_limit": EVENT_QUEUE_LIMIT,
            "dropped_events": worker.dropped_event_count,
            "worker_state": worker.state.value,
            "cleanup_complete": service.cleaned,
            "elapsed_seconds": round(elapsed, 6),
        }
    finally:
        worker.close(10.0)
    return document


def _measure_live_monitor() -> dict[str, Any]:
    clock_value = [0.0]
    session = LiveMonitorSession(
        max_points=LIVE_MONITOR_RETAINED_LIMIT,
        time_window_seconds=1.0,
        clock=lambda: clock_value[0],
    )
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    tracemalloc.start()
    started = perf_counter()
    for index in range(LIVE_MONITOR_POINT_COUNT):
        clock_value[0] = index / 1_000
        session.publish(
            index,
            Measurement(
                f"live-{index:05d}",
                f"raw-live-{index:05d}",
                timestamp,
                "afe.ch0.input",
                float(index % 3_301),
                MeasurementUnit.MILLIVOLT,
                MeasurementStatus.VALID,
                EvidenceSource.SYNTHETIC,
            ),
        )
    snapshot = session.snapshot()
    elapsed = perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "requested_points": LIVE_MONITOR_POINT_COUNT,
        "total_points": snapshot.total_points,
        "retained_points": len(snapshot.points),
        "retained_limit": LIVE_MONITOR_RETAINED_LIMIT,
        "evicted_points": snapshot.evicted_points,
        "valid_points": snapshot.valid_points,
        "suspect_points": snapshot.suspect_points,
        "invalid_points": snapshot.invalid_points,
        "visible_points": len(snapshot.visible_points),
        "elapsed_seconds": round(elapsed, 6),
        "peak_memory_mib": round(peak / (1024 * 1024), 3),
    }


def _measure_demo() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="analog-validation-quality-") as directory:
        output = Path(directory) / "demo"
        started = perf_counter()
        publication = publish_portfolio_demo(output)
        elapsed = perf_counter() - started
        return {
            "elapsed_seconds": round(elapsed, 6),
            "artifact_count": len(publication.artifacts),
            "outcome": publication.outcome.value,
            "evidence_source": publication.evidence_source.value,
            "manifest_present": (output / "manifest.json").is_file(),
        }


def run_acceptance() -> dict[str, Any]:
    """Return measured host evidence and explicit pass/fail targets."""

    replay = [_measure_replay(count) for count in REPLAY_COUNTS]
    event_volume = _measure_event_volume()
    live_monitor = _measure_live_monitor()
    demo = _measure_demo()
    replay_10k = replay[-1]
    checks = {
        "replay_10k_time": replay_10k["elapsed_seconds"] <= MAX_REPLAY_10K_SECONDS,
        "replay_10k_peak_memory": replay_10k["peak_memory_mib"]
        <= MAX_REPLAY_10K_PEAK_MIB,
        "event_10k_time": event_volume["elapsed_seconds"] <= MAX_EVENT_10K_SECONDS,
        "event_queue_bounded": event_volume["retained_events"] <= EVENT_QUEUE_LIMIT,
        "event_cleanup": event_volume["cleanup_complete"] is True,
        "event_terminal_state": event_volume["worker_state"]
        == ProductWorkerState.SUCCEEDED.value,
        "live_10k_time": live_monitor["elapsed_seconds"]
        <= MAX_LIVE_MONITOR_10K_SECONDS,
        "live_10k_peak_memory": live_monitor["peak_memory_mib"]
        <= MAX_LIVE_MONITOR_10K_PEAK_MIB,
        "live_ring_bounded": live_monitor["retained_points"]
        <= live_monitor["retained_limit"] == LIVE_MONITOR_RETAINED_LIMIT,
        "live_eviction_accounted": live_monitor["total_points"]
        == live_monitor["retained_points"] + live_monitor["evicted_points"]
        == LIVE_MONITOR_POINT_COUNT,
        "live_status_accounted": live_monitor["valid_points"]
        + live_monitor["suspect_points"]
        + live_monitor["invalid_points"]
        == LIVE_MONITOR_POINT_COUNT,
        "demo_time": demo["elapsed_seconds"] <= MAX_DEMO_SECONDS,
        "demo_pass": demo["outcome"] == TestRunOutcome.PASS.value,
        "demo_synthetic": demo["evidence_source"] == EvidenceSource.SYNTHETIC.value,
        "demo_manifest": demo["manifest_present"] is True,
    }
    return {
        "schema_version": ACCEPTANCE_SCHEMA_VERSION,
        "scope": "HOST_SOFTWARE_ONLY",
        "hardware_validation": False,
        "platform": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "targets": {
            "replay_10k_max_seconds": MAX_REPLAY_10K_SECONDS,
            "replay_10k_max_peak_mib": MAX_REPLAY_10K_PEAK_MIB,
            "event_10k_max_seconds": MAX_EVENT_10K_SECONDS,
            "event_queue_limit": EVENT_QUEUE_LIMIT,
            "live_monitor_10k_max_seconds": MAX_LIVE_MONITOR_10K_SECONDS,
            "live_monitor_10k_max_peak_mib": MAX_LIVE_MONITOR_10K_PEAK_MIB,
            "live_monitor_retained_limit": LIVE_MONITOR_RETAINED_LIMIT,
            "demo_max_seconds": MAX_DEMO_SECONDS,
        },
        "measurements": {
            "replay": replay,
            "event_volume": event_volume,
            "live_monitor": live_monitor,
            "demo": demo,
        },
        "checks": checks,
        "passed": all(checks.values()),
        "limitations": [
            "Wall-clock timings describe this host run and are not real-time guarantees.",
            "The live-monitor stress uses deterministic in-process synthetic observations, not a physical sample clock.",
            "The acceptance opened no serial port, sent no device command, and measured no hardware.",
            "Network absence is enforced by source/runtime tests; this tool itself performs no network operation.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run bounded Phase 5 host product-quality acceptance."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional new JSON file; existing files are never replaced",
    )
    arguments = parser.parse_args(argv)
    document = run_acceptance()
    rendered = json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if arguments.output is None:
        sys.stdout.write(rendered)
    else:
        try:
            with arguments.output.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(rendered)
        except FileExistsError:
            sys.stderr.write("Acceptance output already exists; choose a new path.\n")
            return 2
    return 0 if document["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
