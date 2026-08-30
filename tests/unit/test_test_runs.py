"""Tests for reproducible test-run metadata and outcome semantics."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest

from analog_validation import (
    TEST_RUN_SCHEMA_VERSION,
    EvidenceSource,
    ValidationError,
)
from analog_validation import TestRunMetadata as RunMetadata
from analog_validation import TestRunOutcome as RunOutcome
from analog_validation import TestRunResult as RunResult


def make_metadata(**changes: Any) -> RunMetadata:
    values: dict[str, Any] = {
        "run_id": "run-001",
        "test_type": "dc-sweep",
        "configuration_id": "dc-sweep-default",
        "configuration_version": "1.0",
        "started_at": datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
        "ended_at": datetime(2026, 8, 29, 12, 0, 2, tzinfo=timezone.utc),
        "software_version": "0.1.0.dev0",
        "device_id": "simulator-001",
        "profile_name": "afe-simulator",
        "profile_version": "1.0",
        "evidence_source": EvidenceSource.SYNTHETIC,
        "input_record_ids": ("raw-001",),
    }
    values.update(changes)
    return RunMetadata(**values)


def test_test_run_outcome_values_are_stable() -> None:
    assert [outcome.value for outcome in RunOutcome] == [
        "PASS",
        "FAIL",
        "INCOMPLETE",
        "UNSUPPORTED",
        "ABORTED",
        "ERROR",
    ]


def test_metadata_is_versioned_immutable_and_normalized_to_utc() -> None:
    eastern = timezone(timedelta(hours=-4))
    records = ["raw-001"]
    metadata = make_metadata(
        started_at=datetime(2026, 8, 29, 8, 0, tzinfo=eastern),
        ended_at=datetime(2026, 8, 29, 8, 0, 2, tzinfo=eastern),
        input_record_ids=records,
    )
    records.clear()

    assert metadata.started_at == datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    assert metadata.ended_at.tzinfo is timezone.utc
    assert metadata.duration_seconds == 2.0
    assert metadata.input_record_ids == ("raw-001",)
    assert metadata.schema_version == TEST_RUN_SCHEMA_VERSION
    assert not metadata.is_bench_evidence
    with pytest.raises(FrozenInstanceError):
        metadata.run_id = "changed"  # type: ignore[misc]


def test_metadata_preserves_explicit_bench_provenance() -> None:
    assert make_metadata(evidence_source=EvidenceSource.BENCH_DMM).is_bench_evidence


@pytest.mark.parametrize(
    "field",
    [
        "run_id",
        "test_type",
        "configuration_id",
        "configuration_version",
        "software_version",
        "device_id",
        "profile_name",
        "profile_version",
    ],
)
def test_metadata_identifiers_must_be_nonempty(field: str) -> None:
    with pytest.raises(ValidationError, match=field):
        make_metadata(**{field: ""})


def test_metadata_identifiers_cannot_have_surrounding_whitespace() -> None:
    with pytest.raises(ValidationError, match="test_type"):
        make_metadata(test_type=" dc-sweep")


def test_metadata_requires_timezone_aware_ordered_datetimes() -> None:
    with pytest.raises(ValidationError, match="datetime"):
        make_metadata(started_at=cast(datetime, "2026-08-29"))
    with pytest.raises(ValidationError, match="timezone"):
        make_metadata(started_at=datetime(2026, 8, 29, 12, 0))  # noqa: DTZ001
    with pytest.raises(ValidationError, match="earlier"):
        make_metadata(
            ended_at=datetime(2026, 8, 29, 11, 59, tzinfo=timezone.utc)
        )


def test_metadata_requires_known_evidence_source_and_schema() -> None:
    with pytest.raises(ValidationError, match="EvidenceSource"):
        make_metadata(evidence_source=cast(EvidenceSource, "SYNTHETIC"))
    with pytest.raises(ValidationError, match="schema version"):
        make_metadata(schema_version="test-run.v2")


def test_input_record_ids_must_be_iterable_unique_identifiers() -> None:
    with pytest.raises(ValidationError, match="iterable"):
        make_metadata(input_record_ids=cast(Any, None))
    with pytest.raises(ValidationError, match="iterable"):
        make_metadata(input_record_ids=cast(Any, "raw-001"))
    with pytest.raises(ValidationError, match="input_record_ids"):
        make_metadata(input_record_ids=("",))
    with pytest.raises(ValidationError, match="duplicates"):
        make_metadata(input_record_ids=("raw-001", "raw-001"))


@pytest.mark.parametrize("outcome", [RunOutcome.PASS, RunOutcome.FAIL])
def test_complete_outcomes_require_evidence(outcome: RunOutcome) -> None:
    result = RunResult(
        metadata=make_metadata(),
        outcome=outcome,
        summary="criteria evaluated",
        evidence_record_ids=("measurement-001",),
    )

    assert result.is_complete
    assert result.is_pass is (outcome is RunOutcome.PASS)
    with pytest.raises(FrozenInstanceError):
        result.summary = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "outcome",
    [
        RunOutcome.INCOMPLETE,
        RunOutcome.UNSUPPORTED,
    ],
)
def test_missing_capability_or_data_never_becomes_pass(
    outcome: RunOutcome,
) -> None:
    result = RunResult(
        metadata=make_metadata(input_record_ids=()),
        outcome=outcome,
        summary="required evidence unavailable",
        missing_requirements=("dac-output",),
    )

    assert not result.is_complete
    assert not result.is_pass


@pytest.mark.parametrize("outcome", [RunOutcome.ABORTED, RunOutcome.ERROR])
def test_interrupted_or_error_results_are_not_conclusions(
    outcome: RunOutcome,
) -> None:
    result = RunResult(make_metadata(), outcome, "run did not finish")

    assert not result.is_complete
    assert not result.is_pass


def test_result_requires_typed_metadata_outcome_and_summary() -> None:
    with pytest.raises(ValidationError, match="metadata"):
        RunResult(cast(RunMetadata, None), RunOutcome.ERROR, "error")
    with pytest.raises(ValidationError, match="outcome"):
        RunResult(make_metadata(), cast(RunOutcome, "PASS"), "summary")
    with pytest.raises(ValidationError, match="summary"):
        RunResult(make_metadata(), RunOutcome.ERROR, "")
    with pytest.raises(ValidationError, match="summary"):
        RunResult(make_metadata(), RunOutcome.ERROR, " summary")


def test_result_record_collections_are_frozen_and_validated() -> None:
    evidence = ["measurement-001"]
    missing: list[str] = []
    result = RunResult(
        make_metadata(),
        RunOutcome.PASS,
        "passed",
        evidence_record_ids=cast(tuple[str, ...], evidence),
        missing_requirements=cast(tuple[str, ...], missing),
    )
    evidence.clear()

    assert result.evidence_record_ids == ("measurement-001",)
    with pytest.raises(ValidationError, match="iterable"):
        RunResult(
            make_metadata(),
            RunOutcome.ERROR,
            "error",
            evidence_record_ids=cast(Any, None),
        )
    with pytest.raises(ValidationError, match="evidence_record_ids"):
        RunResult(
            make_metadata(),
            RunOutcome.PASS,
            "passed",
            evidence_record_ids=("",),
        )
    with pytest.raises(ValidationError, match="duplicates"):
        RunResult(
            make_metadata(),
            RunOutcome.PASS,
            "passed",
            evidence_record_ids=("m1", "m1"),
        )
    with pytest.raises(ValidationError, match="duplicates"):
        RunResult(
            make_metadata(),
            RunOutcome.INCOMPLETE,
            "incomplete",
            missing_requirements=("adc", "adc"),
        )


@pytest.mark.parametrize("outcome", [RunOutcome.PASS, RunOutcome.FAIL])
def test_pass_or_fail_cannot_hide_missing_requirements(
    outcome: RunOutcome,
) -> None:
    with pytest.raises(ValidationError, match="cannot have missing"):
        RunResult(
            make_metadata(),
            outcome,
            "criteria evaluated",
            evidence_record_ids=("measurement-001",),
            missing_requirements=("required-sample",),
        )


@pytest.mark.parametrize("outcome", [RunOutcome.PASS, RunOutcome.FAIL])
def test_complete_result_cannot_exist_without_evidence(
    outcome: RunOutcome,
) -> None:
    with pytest.raises(ValidationError, match="require evidence"):
        RunResult(make_metadata(), outcome, "criteria evaluated")


@pytest.mark.parametrize(
    "outcome",
    [RunOutcome.INCOMPLETE, RunOutcome.UNSUPPORTED],
)
def test_non_conclusion_must_explain_what_is_missing(
    outcome: RunOutcome,
) -> None:
    with pytest.raises(ValidationError, match="missing requirements"):
        RunResult(make_metadata(), outcome, "not evaluated")
