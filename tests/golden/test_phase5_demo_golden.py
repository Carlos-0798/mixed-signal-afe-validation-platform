"""Freeze the exact Phase 5 software-only portfolio demo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from analog_validation_app import publish_portfolio_demo

ROOT = Path(__file__).resolve().parents[2]
EXPECTED: dict[str, Any] = json.loads(
    (ROOT / "test-data/golden/phase5_demo_v1.json").read_text(encoding="utf-8")
)


def test_phase5_demo_matches_frozen_artifact_hashes(tmp_path: Path) -> None:
    publication = publish_portfolio_demo(tmp_path / "frozen-demo")
    artifacts = {
        artifact.relative_path: {
            "size_bytes": artifact.size_bytes,
            "sha256": artifact.sha256,
        }
        for artifact in publication.artifacts
    }

    assert publication.schema_version == EXPECTED["demo_schema_version"]
    assert publication.outcome.value == EXPECTED["outcome"]
    assert publication.evidence_source.value == EXPECTED["evidence_source"]
    assert publication.canonical_result_sha256 == EXPECTED["canonical_result_sha256"]
    assert artifacts == EXPECTED["artifacts"]


def test_phase5_demo_golden_keeps_software_and_hardware_claims_separate() -> None:
    assert EXPECTED["schema_version"] == "phase5-demo-golden.v1"
    assert EXPECTED["verification_scope"].startswith("HOST_TEST")
    assert EXPECTED["new_hardware_validation"] is False
    assert EXPECTED["evidence_source"] == "SYNTHETIC"
    assert EXPECTED["outcome"] == "PASS"
