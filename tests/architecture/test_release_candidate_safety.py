"""Static no-hardware and atomic-publication boundary for the release verifier."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "release_candidate_check.py"


def test_release_verifier_has_no_physical_serial_or_publication_command() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert "SYNTHETIC_PORT" in source
    assert "port_enumerator=lambda" in source
    forbidden = (
        "serial.tools.list_ports",
        "analog-validation ports",
        "analog-validation observe",
        "COM4",
        "COM5",
        "gh release",
        "twine upload",
        "git tag",
    )
    assert all(value not in source for value in forbidden)


def test_release_verifier_uses_create_new_manifest_and_atomic_directory_rename() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert 'manifest_path.open("x"' in source
    assert "candidate.rename(output)" in source
    assert "candidate output already exists" in source
    assert '"candidate_status": "PASS"' in source
    assert '"afe_bench_requirements_verified": 0' in source
