from __future__ import annotations

import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from analog_validation_app.cli import CliDependencies, main
from tests.support import MemorySerialBackend

HEADER = (
    "row_type,schema_version,dataset_id,record_id,raw_record_id,timestamp_utc,"
    "channel,value,unit,status,source,quality_flags,record_count"
)


def dependencies() -> CliDependencies:
    return CliDependencies(
        serial_backend_factory=MemorySerialBackend,
        job_id_factory=lambda: "phase5-replay-chain",
        event_id_factory=lambda: "unused",
    )


def replay_text(dataset_id: str, rows: list[tuple[str, float, str]]) -> str:
    started = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
    lines = [HEADER, ",".join(("META", "csv-replay.v1", dataset_id, *("",) * 10))]
    for index, (channel, value, unit) in enumerate(rows):
        timestamp = (
            (started + timedelta(milliseconds=index * 10))
            .isoformat()
            .replace("+00:00", "Z")
        )
        lines.append(
            ",".join(
                (
                    "DATA",
                    "csv-replay.v1",
                    dataset_id,
                    f"record-{index}",
                    f"raw-{index}",
                    timestamp,
                    channel,
                    str(value),
                    unit,
                    "VALID",
                    "SYNTHETIC",
                    "",
                    "",
                )
            )
        )
    lines.append(
        ",".join(("END", "csv-replay.v1", dataset_id, *("",) * 9, str(len(rows))))
    )
    return "\n".join(lines) + "\n"


def test_replay_dc_chain_preserves_replay_provenance_and_lineage(
    tmp_path: Path,
) -> None:
    rows: list[tuple[str, float, str]] = []
    for input_value in (100.0, 200.0, 300.0, 400.0):
        rows.extend(
            (
                ("afe.ch0.input", input_value, "mV"),
                ("afe.ch0.output", 2 * input_value + 12, "mV"),
            )
        )
    source = tmp_path / "dc.csv"
    source.write_text(replay_text("phase5-dc", rows), encoding="utf-8")
    output = io.StringIO()

    status = main(
        ["replay", "dc", "--input", str(source), "--points", "4", "--json"],
        stdout=output,
        dependencies=dependencies(),
    )

    assert status == 0
    document = json.loads(output.getvalue())
    assert document["result"]["test_run_outcome"] == "PASS"
    assert document["result"]["evidence_source"] == "CSV_REPLAY"
    assert (
        document["result_export"]["test_run"]["metadata"]["input_record_ids"][0]
        == "record-0"
    )
    assert document["result_export"]["points"][0]["references"][0][
        "record_id"
    ].startswith("csv-replay:phase5-dc:")


def test_replay_hysteresis_chain_uses_explicit_direction_counts(
    tmp_path: Path,
) -> None:
    samples = (
        (800.0, 0.0),
        (950.0, 0.0),
        (1050.0, 1.0),
        (1200.0, 1.0),
        (1200.0, 1.0),
        (950.0, 1.0),
        (850.0, 0.0),
        (700.0, 0.0),
    )
    rows = [
        row
        for input_value, state in samples
        for row in (
            ("afe.ch0.input", input_value, "mV"),
            ("afe.ch0.threshold", state, "bool"),
        )
    ]
    source = tmp_path / "hysteresis.csv"
    source.write_text(replay_text("phase5-hysteresis", rows), encoding="utf-8")
    output = io.StringIO()

    status = main(
        [
            "replay",
            "hysteresis",
            "--input",
            str(source),
            "--rising-count",
            "4",
            "--falling-count",
            "4",
            "--json",
        ],
        stdout=output,
        dependencies=dependencies(),
    )

    assert status == 0
    document = json.loads(output.getvalue())
    metrics = {
        item["name"]: item["value"] for item in document["result_export"]["metrics"]
    }
    assert document["result"]["test_run_outcome"] == "PASS"
    assert metrics["mean_high_threshold"] == 1000.0
    assert metrics["mean_low_threshold"] == 900.0
    assert metrics["mean_width"] == 100.0
