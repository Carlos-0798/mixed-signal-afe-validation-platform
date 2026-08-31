"""Phase 5 Step 7 performance, privacy, and offline acceptance."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any, NoReturn

import pytest

from analog_validation_app import publish_portfolio_demo
from tools.product_quality_acceptance import run_acceptance


def test_ten_thousand_record_and_event_acceptance_is_bounded() -> None:
    document: Any = run_acceptance()

    assert document["schema_version"] == "phase5-product-quality-acceptance.v1"
    assert document["scope"] == "HOST_SOFTWARE_ONLY"
    assert document["hardware_validation"] is False
    assert document["passed"] is True
    assert all(document["checks"].values())
    replay = document["measurements"]["replay"]
    assert [measurement["records"] for measurement in replay] == [100, 1_000, 10_000]
    events = document["measurements"]["event_volume"]
    assert events["requested_progress_events"] == 10_000
    assert events["retained_events"] <= events["queue_limit"] == 256
    assert events["dropped_events"] > 0
    assert events["cleanup_complete"] is True
    assert events["worker_state"] == "SUCCEEDED"


def test_demo_runtime_does_not_request_a_network_socket(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def deny_socket(*_args: object, **_kwargs: object) -> NoReturn:
        raise AssertionError("the software demo must remain offline")

    monkeypatch.setattr(socket, "socket", deny_socket)
    publication = publish_portfolio_demo(tmp_path / "offline-demo")

    assert publication.evidence_source.value == "SYNTHETIC"
    assert publication.outcome.value == "PASS"
