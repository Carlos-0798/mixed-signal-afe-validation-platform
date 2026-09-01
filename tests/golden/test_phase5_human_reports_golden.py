"""Freeze deterministic Phase 5 human-report artifacts without hardware claims."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from analog_validation.exports import load_result_export_json
from analog_validation_app import build_human_report_view, publish_human_report

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = ROOT / "test-data" / "golden"
EXPECTED_PATH = GOLDEN_DIR / "phase5_human_reports_v1.json"
EXPECTED: dict[str, Any] = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))


def test_phase5_report_golden_manifest_declares_host_only_scope() -> None:
    assert EXPECTED["schema_version"] == "phase5-human-report-golden.v1"
    assert EXPECTED["verification_scope"].startswith("HOST_TEST")
    assert EXPECTED["new_hardware_validation"] is False
    assert {case["id"] for case in EXPECTED["cases"]} == {
        "dc-sweep",
        "hysteresis",
    }


@pytest.mark.parametrize("case", EXPECTED["cases"], ids=lambda value: value["id"])
def test_phase5_human_report_artifacts_match_frozen_hashes(
    case: dict[str, Any],
    tmp_path: Path,
) -> None:
    bundle = load_result_export_json(GOLDEN_DIR / case["result_export"])
    view = build_human_report_view(bundle)
    publication = publish_human_report(tmp_path / case["id"], view)

    actual = {
        artifact.name: {
            "size_bytes": artifact.size_bytes,
            "sha256": artifact.sha256,
        }
        for artifact in publication.artifacts
    }
    assert view.canonical_result_sha256 == case["canonical_result_sha256"]
    assert view.outcome.value == case["outcome"]
    assert view.evidence_source.value == case["evidence_source"]
    assert actual == case["artifacts"]


def test_phase5_frozen_reports_keep_synthetic_evidence_and_no_hardware_claim() -> None:
    for case in EXPECTED["cases"]:
        assert case["evidence_source"] == "SYNTHETIC"
        assert case["outcome"] == "PASS"
