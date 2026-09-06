from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

import analog_validation_app
from analog_validation import EvidenceSource
from analog_validation import TestRunOutcome as RunOutcome
from analog_validation import __version__ as core_version
from analog_validation_app import (
    MAX_PRODUCT_EVENT_TEXT_CHARS,
    MAX_PRODUCT_IDENTIFIER_CHARS,
    MAX_PRODUCT_LIMITATION_CHARS,
    MAX_PRODUCT_LIMITATIONS,
    PRODUCT_JOB_EVENT_SCHEMA_VERSION,
    PRODUCT_JOB_SCHEMA_VERSION,
    PRODUCT_RESULT_SCHEMA_VERSION,
    ProductJobEvent,
    ProductJobRequest,
    ProductJobResult,
    ProductJobType,
    ProductRequestError,
    ProductResultStatus,
    ProductSourceMode,
    ProductWorkerError,
    ProductWorkerState,
    issue_from_exception,
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


def make_request(**overrides: Any) -> ProductJobRequest:
    values: dict[str, Any] = {
        "job_id": "job-001",
        "source_mode": ProductSourceMode.SIMULATOR,
        "job_type": ProductJobType.DC_ANALYSIS,
        "profile_name": "afe",
        "profile_version": "1",
    }
    values.update(overrides)
    return ProductJobRequest(**values)


def make_result(**overrides: Any) -> ProductJobResult:
    values: dict[str, Any] = {
        "request": make_request(),
        "status": ProductResultStatus.COMPLETED,
        "evidence_source": EvidenceSource.SYNTHETIC,
        "test_run_outcome": RunOutcome.PASS,
        "limitations": ("Synthetic data is not hardware evidence.",),
    }
    values.update(overrides)
    return ProductJobResult(**values)


def make_event(**overrides: Any) -> ProductJobEvent:
    values: dict[str, Any] = {
        "job_id": "job-001",
        "index": 1,
        "created_at": NOW,
        "state": ProductWorkerState.STARTING,
        "message": "Job accepted.",
    }
    values.update(overrides)
    return ProductJobEvent(**values)


def test_product_enums_and_schema_values_are_explicit() -> None:
    assert [item.value for item in ProductSourceMode] == [
        "SIMULATOR",
        "CSV_REPLAY",
        "SERIAL_READ_ONLY",
    ]
    assert [item.value for item in ProductJobType] == [
        "READ",
        "DC_ANALYSIS",
        "HYSTERESIS_ANALYSIS",
        "CALIBRATION_ANALYSIS",
        "FREQUENCY_RESPONSE_ANALYSIS",
        "LIVE_MONITOR",
    ]
    assert [item.value for item in ProductResultStatus] == [
        "COMPLETED",
        "INCOMPLETE",
        "UNSUPPORTED",
        "CANCELLED",
        "ERROR",
    ]
    assert [item.value for item in ProductWorkerState] == [
        "IDLE",
        "STARTING",
        "RUNNING",
        "CANCELLING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
    ]
    assert all(
        state.is_active
        for state in (
            ProductWorkerState.STARTING,
            ProductWorkerState.RUNNING,
            ProductWorkerState.CANCELLING,
        )
    )
    assert all(
        state.is_terminal
        for state in (
            ProductWorkerState.SUCCEEDED,
            ProductWorkerState.FAILED,
            ProductWorkerState.CANCELLED,
        )
    )
    assert not ProductWorkerState.IDLE.is_active
    assert not ProductWorkerState.IDLE.is_terminal
    assert PRODUCT_JOB_EVENT_SCHEMA_VERSION == "product-job-event.v1"
    assert PRODUCT_JOB_SCHEMA_VERSION == "product-job.v1"
    assert PRODUCT_RESULT_SCHEMA_VERSION == "product-result.v1"


def test_product_package_has_one_version_and_typed_public_exports() -> None:
    package_root = Path(analog_validation_app.__file__).resolve().parent

    assert analog_validation_app.__version__ == core_version
    assert (package_root / "py.typed").is_file()
    assert len(analog_validation_app.__all__) == len(set(analog_validation_app.__all__))
    assert all(
        hasattr(analog_validation_app, name) for name in analog_validation_app.__all__
    )


def test_product_request_is_immutable_read_only_and_explicit() -> None:
    request = make_request()

    assert request.profile_identity == "afe/1"
    assert request.allow_output is False
    assert request.schema_version == PRODUCT_JOB_SCHEMA_VERSION
    with pytest.raises(FrozenInstanceError):
        request.job_id = "changed"  # type: ignore[misc]


def test_product_job_event_is_immutable_bounded_and_normalizes_utc() -> None:
    eastern = timezone(timedelta(hours=-4))
    event = make_event(
        created_at=datetime(2026, 8, 31, 8, 0, tzinfo=eastern),
        state=ProductWorkerState.RUNNING,
        completed=2,
        total=3,
    )

    assert event.created_at == NOW
    assert event.created_at.tzinfo is timezone.utc
    assert event.completed == 2
    assert event.total == 3
    assert event.schema_version == PRODUCT_JOB_EVENT_SCHEMA_VERSION
    with pytest.raises(FrozenInstanceError):
        event.index = 2  # type: ignore[misc]


def test_failed_job_event_carries_one_safe_user_issue() -> None:
    issue = issue_from_exception(ProductWorkerError("expected worker failure"))
    event = make_event(
        state=ProductWorkerState.FAILED,
        message="Job failed.",
        issue=issue,
    )

    assert event.issue is issue


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"job_id": ""}, "job_id"),
        ({"index": True}, "integer"),
        ({"index": 0}, "positive"),
        ({"created_at": "now"}, "datetime"),
        ({"created_at": datetime(2026, 8, 31, 12)}, "timezone-aware"),  # noqa: DTZ001
        ({"state": "RUNNING"}, "ProductWorkerState"),
        ({"message": ""}, "non-empty"),
        ({"message": " padded "}, "non-empty"),
        ({"message": "line\nbreak"}, "printable"),
        ({"message": "x" * (MAX_PRODUCT_EVENT_TEXT_CHARS + 1)}, "exceeds"),
        ({"completed": 1}, "provided together"),
        ({"total": 1}, "provided together"),
        (
            {
                "state": ProductWorkerState.RUNNING,
                "completed": True,
                "total": 1,
            },
            "integers",
        ),
        (
            {
                "state": ProductWorkerState.RUNNING,
                "completed": -1,
                "total": 1,
            },
            "0 <= completed",
        ),
        (
            {
                "state": ProductWorkerState.RUNNING,
                "completed": 0,
                "total": 0,
            },
            "0 <= completed",
        ),
        (
            {
                "state": ProductWorkerState.RUNNING,
                "completed": 2,
                "total": 1,
            },
            "0 <= completed",
        ),
        ({"completed": 0, "total": 1}, "RUNNING"),
        ({"issue": object()}, "UserIssue"),
        ({"state": ProductWorkerState.FAILED}, "require"),
        (
            {"issue": issue_from_exception(ProductWorkerError("failure"))},
            "only FAILED",
        ),
        ({"schema_version": "product-job-event.v2"}, "unsupported"),
    ],
)
def test_product_job_event_rejects_invalid_or_ambiguous_values(
    overrides: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ProductRequestError, match=message):
        make_event(**overrides)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"job_id": ""}, "job_id"),
        ({"job_id": " surrounded "}, "job_id"),
        ({"job_id": "line\nbreak"}, "printable"),
        ({"job_id": "x" * (MAX_PRODUCT_IDENTIFIER_CHARS + 1)}, "exceeds"),
        ({"source_mode": "SIMULATOR"}, "ProductSourceMode"),
        ({"job_type": "READ"}, "ProductJobType"),
        ({"profile_name": ""}, "profile_name"),
        ({"profile_version": " 1"}, "profile_version"),
        ({"allow_output": 1}, "boolean"),
        ({"allow_output": True}, "read-only"),
        ({"schema_version": "product-job.v2"}, "unsupported"),
    ],
)
def test_product_request_rejects_ambiguous_or_output_capable_values(
    overrides: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ProductRequestError, match=message):
        make_request(**overrides)


@pytest.mark.parametrize(
    ("source_mode", "evidence_source"),
    [
        (ProductSourceMode.SIMULATOR, EvidenceSource.SYNTHETIC),
        (ProductSourceMode.CSV_REPLAY, EvidenceSource.CSV_REPLAY),
        (ProductSourceMode.SERIAL_READ_ONLY, EvidenceSource.HOST_TEST),
        (ProductSourceMode.SERIAL_READ_ONLY, EvidenceSource.BENCH_CONTROLLER),
    ],
)
def test_result_accepts_only_evidence_allowed_by_the_selected_source(
    source_mode: ProductSourceMode,
    evidence_source: EvidenceSource,
) -> None:
    request = make_request(source_mode=source_mode)
    result = make_result(request=request, evidence_source=evidence_source)

    assert result.evidence_source is evidence_source


@pytest.mark.parametrize(
    ("status", "outcome", "is_conclusion"),
    [
        (ProductResultStatus.COMPLETED, None, False),
        (ProductResultStatus.COMPLETED, RunOutcome.PASS, True),
        (ProductResultStatus.COMPLETED, RunOutcome.FAIL, True),
        (ProductResultStatus.INCOMPLETE, None, False),
        (ProductResultStatus.INCOMPLETE, RunOutcome.INCOMPLETE, False),
        (ProductResultStatus.UNSUPPORTED, None, False),
        (ProductResultStatus.UNSUPPORTED, RunOutcome.UNSUPPORTED, False),
        (ProductResultStatus.CANCELLED, None, False),
        (ProductResultStatus.CANCELLED, RunOutcome.ABORTED, False),
        (ProductResultStatus.ERROR, None, False),
        (ProductResultStatus.ERROR, RunOutcome.ERROR, False),
    ],
)
def test_result_status_and_engineering_outcome_remain_separate(
    status: ProductResultStatus,
    outcome: RunOutcome | None,
    is_conclusion: bool,
) -> None:
    result = make_result(status=status, test_run_outcome=outcome)

    assert result.is_engineering_conclusion is is_conclusion


@pytest.mark.parametrize(
    ("status", "outcome"),
    [
        (ProductResultStatus.INCOMPLETE, RunOutcome.PASS),
        (ProductResultStatus.UNSUPPORTED, RunOutcome.FAIL),
        (ProductResultStatus.CANCELLED, RunOutcome.ERROR),
        (ProductResultStatus.ERROR, RunOutcome.ABORTED),
        (ProductResultStatus.COMPLETED, RunOutcome.INCOMPLETE),
    ],
)
def test_result_cannot_promote_noncomplete_execution_to_pass_or_fail(
    status: ProductResultStatus,
    outcome: RunOutcome,
) -> None:
    with pytest.raises(ProductRequestError, match="inconsistent"):
        make_result(status=status, test_run_outcome=outcome)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"request": object()}, "ProductJobRequest"),
        ({"status": "COMPLETED"}, "ProductResultStatus"),
        ({"evidence_source": "SYNTHETIC"}, "EvidenceSource"),
        ({"test_run_outcome": "PASS"}, "TestRunOutcome"),
        ({"schema_version": "product-result.v2"}, "unsupported"),
    ],
)
def test_result_rejects_wrong_contract_types(
    overrides: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(ProductRequestError, match=message):
        make_result(**overrides)


def test_result_rejects_evidence_promotion_across_sources() -> None:
    with pytest.raises(ProductRequestError, match="evidence_source"):
        make_result(evidence_source=EvidenceSource.BENCH_CONTROLLER)


def test_limitations_are_frozen_and_required() -> None:
    supplied = ["Synthetic only.", "No AFE hardware was used."]
    result = make_result(limitations=supplied)
    supplied.append("Changed later.")

    assert result.limitations == (
        "Synthetic only.",
        "No AFE hardware was used.",
    )


@pytest.mark.parametrize(
    ("limitations", "message"),
    [
        ("not-an-iterable-contract", "iterable"),
        ((), "at least one"),
        (("",), "non-empty"),
        ((" surrounding ",), "non-empty"),
        (("line\nbreak",), "printable"),
        (("same", "same"), "duplicates"),
        (("x" * (MAX_PRODUCT_LIMITATION_CHARS + 1),), "exceeds"),
        (tuple(str(index) for index in range(MAX_PRODUCT_LIMITATIONS + 1)), "exceeds"),
    ],
)
def test_limitations_reject_unbounded_or_ambiguous_content(
    limitations: object,
    message: str,
) -> None:
    with pytest.raises(ProductRequestError, match=message):
        make_result(limitations=limitations)
