"""Static no-hardware, no-publication, and handoff contract for Step 7."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "release_audit.py"
NOTICE = ROOT / "THIRD_PARTY_NOTICES.md"
RELEASE_NOTES = ROOT / "docs" / "RELEASE_NOTES_DRAFT.md"
HANDOFF = ROOT / "docs" / "PRIVATE_BETA_HANDOFF.md"


def test_release_audit_is_create_new_privacy_minimal_and_host_only() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert 'RELEASE_AUDIT_SCHEMA_VERSION = "release-audit.v1"' in source
    assert "NamedTemporaryFile" in source
    assert "staging_path.rename(output)" in source
    assert "identity_values_embedded\": False" in source
    assert "NO_NEW_HARDWARE_VALIDATION" in source
    assert '"serial_ports_opened": 0' in source
    assert '"application_bytes_written": 0' in source
    forbidden = (
        "serial.tools.list_ports",
        "analog-validation ports",
        "analog-validation observe",
        "gh release",
        "twine upload",
        "git tag -a",
        "git push --force",
        "COM4",
        "COM5",
    )
    assert all(value not in source for value in forbidden)


def test_notice_and_private_beta_handoff_preserve_owner_boundaries() -> None:
    notice = NOTICE.read_text(encoding="utf-8")
    notes = RELEASE_NOTES.read_text(encoding="utf-8")
    handoff = HANDOFF.read_text(encoding="utf-8")

    assert "BSD-3-Clause" in notice and "pyserial" in notice
    assert "does not grant a license" in notice
    assert "DRAFT — NOT PUBLISHED" in notes
    assert "NO_NEW_HARDWARE_VALIDATION" in notes
    assert "OWNER_REVIEW_REQUIRED" in handoff
    assert "exactly four files" in handoff
    for action in (
        "merge",
        "tag",
        "GitHub Release",
        "visibility",
        "history rewrite",
        "license selection",
        "LinkedIn publication",
        "v1.0",
    ):
        assert action in handoff


def test_packaging_carries_rights_and_third_party_notices() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")

    assert 'requires = ["setuptools>=77"]' in pyproject
    assert 'license-files = ["LICENSE", "THIRD_PARTY_NOTICES.md"]' in pyproject
    assert "include ASSUMPTIONS.md" in manifest
    assert "include THIRD_PARTY_NOTICES.md" in manifest
    assert "recursive-include docs *.md" in manifest
    assert "recursive-include examples *.json *.md *.py" in manifest
    assert "License ::" not in pyproject
