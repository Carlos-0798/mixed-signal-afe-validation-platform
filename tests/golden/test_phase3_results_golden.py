"""Freeze representative Phase 3 analysis, decision, and export meaning."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

from analog_validation import (
    EvidenceSource,
    Measurement,
    MeasurementStatus,
    MeasurementUnit,
    QualityFlag,
)
from analog_validation import TestRunMetadata as RunMetadata
from analog_validation import TestRunOutcome as RunOutcome
from analog_validation.analysis import (
    DCSweepAcceptanceCriteria,
    DCSweepAnalysisConfig,
    HysteresisAcceptanceCriteria,
    HysteresisAnalysisConfig,
    HysteresisCycleInput,
    MeasurementBatch,
    PointDisposition,
    analyze_dc_sweep,
    analyze_hysteresis,
    evaluate_dc_sweep,
    evaluate_hysteresis,
)
from analog_validation.exports import (
    ResultExportBundle,
    build_dc_sweep_export,
    build_hysteresis_export,
    dump_result_export_json,
)

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = ROOT / "test-data" / "golden"
DC_INPUT_PATH = GOLDEN_DIR / "phase3_dc_sweep_input_v1.json"
DC_RESULT_PATH = GOLDEN_DIR / "phase3_dc_sweep_result_v1.json"
HYSTERESIS_RESULT_PATH = GOLDEN_DIR / "phase3_hysteresis_result_v1.json"
HYSTERESIS_NOW = datetime(2026, 8, 30, 13, 0, tzinfo=timezone.utc)


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _measurement(value: dict[str, Any]) -> Measurement:
    return Measurement(
        record_id=value["record_id"],
        raw_record_id=value["raw_record_id"],
        timestamp=_utc(value["timestamp"]),
        channel=value["channel"],
        value=value["value"],
        unit=MeasurementUnit(value["unit"]),
        status=MeasurementStatus(value["status"]),
        source=EvidenceSource(value["source"]),
        quality_flags=frozenset(QualityFlag(item) for item in value["quality_flags"]),
    )


def dc_bundle() -> ResultExportBundle:
    """Rebuild the frozen synthetic DC result only from its input fixture."""

    fixture = _load(DC_INPUT_PATH)
    config = fixture["analysis_config"]
    criteria = fixture["criteria"]
    metadata = fixture["metadata"]
    batch = MeasurementBatch(
        tuple(_measurement(value) for value in fixture["measurements"])
    )
    analysis = analyze_dc_sweep(
        batch,
        DCSweepAnalysisConfig(
            input_channel=config["input_channel"],
            output_channel=config["output_channel"],
            low_output_limit=config["low_output_limit"],
            high_output_limit=config["high_output_limit"],
            normalized_unit=MeasurementUnit(config["normalized_unit"]),
            minimum_included_points=config["minimum_included_points"],
        ),
    )
    acceptance = DCSweepAcceptanceCriteria(
        criteria_id=criteria["criteria_id"],
        criteria_version=criteria["criteria_version"],
        target_gain=criteria["target_gain"],
        gain_absolute_tolerance=criteria["gain_absolute_tolerance"],
        max_abs_offset=criteria["max_abs_offset"],
        min_r_squared=criteria["min_r_squared"],
        max_rmse=criteria["max_rmse"],
        minimum_included_points=criteria["minimum_included_points"],
        normalized_unit=MeasurementUnit(criteria["normalized_unit"]),
    )
    evaluation = evaluate_dc_sweep(
        analysis,
        acceptance,
        RunMetadata(
            run_id=metadata["run_id"],
            test_type=metadata["test_type"],
            configuration_id=metadata["configuration_id"],
            configuration_version=metadata["configuration_version"],
            started_at=_utc(metadata["started_at"]),
            ended_at=_utc(metadata["ended_at"]),
            software_version=metadata["software_version"],
            device_id=metadata["device_id"],
            profile_name=metadata["profile_name"],
            profile_version=metadata["profile_version"],
            evidence_source=EvidenceSource(fixture["evidence_source"]),
            input_record_ids=tuple(value.raw_record_id for value in batch.measurements),
        ),
    )
    return build_dc_sweep_export(evaluation, tuple(fixture["limitations"]))


def _hysteresis_batch(
    prefix: str,
    values: tuple[float, ...],
    states: tuple[int, ...],
    *,
    start_sequence: int,
) -> MeasurementBatch:
    records: list[Measurement] = []
    for index, (input_value, state) in enumerate(zip(values, states, strict=True)):
        sequence = start_sequence + index * 2
        records.extend(
            (
                Measurement(
                    record_id=f"golden-{prefix}-input-{index}",
                    raw_record_id=f"golden-{prefix}-raw-input-{index}",
                    timestamp=HYSTERESIS_NOW + timedelta(milliseconds=sequence),
                    channel="afe.ch0.input",
                    value=input_value,
                    unit=MeasurementUnit.MILLIVOLT,
                    status=MeasurementStatus.VALID,
                    source=EvidenceSource.SYNTHETIC,
                ),
                Measurement(
                    record_id=f"golden-{prefix}-state-{index}",
                    raw_record_id=f"golden-{prefix}-raw-state-{index}",
                    timestamp=HYSTERESIS_NOW
                    + timedelta(milliseconds=sequence + 1),
                    channel="afe.ch0.threshold",
                    value=float(state),
                    unit=MeasurementUnit.BOOLEAN,
                    status=MeasurementStatus.VALID,
                    source=EvidenceSource.SYNTHETIC,
                ),
            )
        )
    return MeasurementBatch(tuple(records))


def hysteresis_bundle() -> ResultExportBundle:
    """Rebuild the frozen one-cycle synthetic hysteresis result."""

    rising = _hysteresis_batch(
        "hysteresis-rising",
        (1400.0, 1700.0, 1800.0, 1900.0),
        (0, 0, 1, 1),
        start_sequence=0,
    )
    falling = _hysteresis_batch(
        "hysteresis-falling",
        (1900.0, 1600.0, 1500.0, 1400.0),
        (1, 1, 0, 0),
        start_sequence=8,
    )
    analysis = analyze_hysteresis(
        (HysteresisCycleInput(0, rising, falling),),
        HysteresisAnalysisConfig("afe.ch0.input", "afe.ch0.threshold"),
    )
    raw_ids = tuple(
        reference.raw_record_id
        for cycle in analysis.cycles
        for point in cycle.rising_points + cycle.falling_points
        for reference in (point.input_decision.reference, point.state_reference)
    )
    evaluation = evaluate_hysteresis(
        analysis,
        HysteresisAcceptanceCriteria(
            "phase3-golden-hysteresis-criteria",
            "1",
            1700.0,
            1800.0,
            1500.0,
            1600.0,
            150.0,
            250.0,
            0.0,
            1,
        ),
        RunMetadata(
            "phase3-golden-hysteresis",
            "hysteresis",
            "phase3-golden-hysteresis-config",
            "1",
            HYSTERESIS_NOW,
            HYSTERESIS_NOW + timedelta(seconds=1),
            "0.1.0.dev0",
            "phase3-golden-simulator",
            "afe-synthetic",
            "1",
            EvidenceSource.SYNTHETIC,
            raw_ids,
        ),
    )
    return build_hysteresis_export(
        evaluation,
        ("SYNTHETIC golden compatibility fixture; no comparator was measured.",),
    )


def test_phase3_dc_input_fixture_is_versioned_and_synthetic() -> None:
    fixture = _load(DC_INPUT_PATH)
    assert set(fixture) == {
        "schema_version",
        "evidence_source",
        "metadata",
        "analysis_config",
        "criteria",
        "limitations",
        "measurements",
    }
    assert fixture["schema_version"] == "phase3-dc-sweep-input-golden.v1"
    assert fixture["evidence_source"] == "SYNTHETIC"
    assert all(value["source"] == "SYNTHETIC" for value in fixture["measurements"])


def test_phase3_dc_result_matches_frozen_json_exactly() -> None:
    bundle = dc_bundle()
    assert dump_result_export_json(bundle) == DC_RESULT_PATH.read_text(encoding="utf-8")
    assert bundle.test_run_result.outcome is RunOutcome.PASS
    assert bundle.test_run_result.metadata.evidence_source is EvidenceSource.SYNTHETIC
    assert bundle.points[2].disposition is PointDisposition.EXCLUDED
    assert bundle.points[2].exclusion_reasons == ("point:HIGH_SATURATION",)


def test_phase3_hysteresis_result_matches_frozen_json_exactly() -> None:
    bundle = hysteresis_bundle()
    assert dump_result_export_json(bundle) == HYSTERESIS_RESULT_PATH.read_text(
        encoding="utf-8"
    )
    assert bundle.test_run_result.outcome is RunOutcome.PASS
    assert bundle.test_run_result.metadata.evidence_source is EvidenceSource.SYNTHETIC
    metrics = {value.name: value.value for value in bundle.metrics}
    assert metrics["mean_high_threshold"] == 1750.0
    assert metrics["mean_low_threshold"] == 1550.0
    assert metrics["mean_width"] == 200.0


def test_phase3_golden_results_never_claim_bench_evidence() -> None:
    for bundle in (dc_bundle(), hysteresis_bundle()):
        assert not bundle.test_run_result.metadata.is_bench_evidence
        assert all(not point.evidence_source.is_bench_evidence for point in bundle.points)
        assert any("no " in value.lower() for value in bundle.limitations)
