"""Focused privacy, workbook, and destination tests for the release audit."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

import tools.release_audit as release_module
from tools.release_audit import (
    LICENSE_POLICY_TEXT,
    RELEASE_AUDIT_SCHEMA_VERSION,
    ReleaseAuditDestinationError,
    ReleaseAuditError,
    _audit_candidate,
    _is_approved_fixture,
    _is_approved_github_noreply,
    _normalize_member_path,
    _partition_findings,
    _validate_output_destination,
    audit_xlsx_bytes,
    scan_sensitive_payload,
)


def _workbook(*, creator: str = "", hidden: bool = False) -> bytes:
    state = ' state="hidden"' if hidden else ""
    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheets><sheet name="Purchase List" sheetId="1"{state}/></sheets>'
        "</workbook>"
    )
    core = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<cp:coreProperties '
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"<dc:creator>{creator}</dc:creator>"
        "</cp:coreProperties>"
    )
    sheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData><row><c><f>SUM(1,2)</f><v>3</v></c></row></sheetData>"
        "</worksheet>"
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
        archive.writestr("docProps/core.xml", core)
    return output.getvalue()


def _email(local: str, domain: str) -> str:
    return local + "@" + domain


def _candidate_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, str, dict[str, Any]]:
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    wheel = candidate / "package-0.1-py3-none-any.whl"
    sdist = candidate / "package-0.1.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")
    commit = "a" * 40

    def record(path: Path, kind: str) -> dict[str, object]:
        return {
            "filename": path.name,
            "kind": kind,
            "size_bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }

    manifest: dict[str, Any] = {
        "schema_version": release_module.RELEASE_MANIFEST_SCHEMA_VERSION,
        "candidate_status": "PASS",
        "source": {"commit": commit, "working_tree": "CLEAN"},
        "evidence_boundary": {
            "hardware_claim": "NO_NEW_HARDWARE_VALIDATION",
            "serial_ports_enumerated": 0,
            "serial_ports_opened": 0,
            "application_bytes_written": 0,
        },
        "artifacts": [record(wheel, "wheel"), record(sdist, "sdist")],
    }
    _write_candidate_manifest(candidate, manifest)
    monkeypatch.setattr(
        release_module,
        "_audit_wheel",
        lambda _path: ({"status": "PASS"}, {"status": "PASS"}),
    )
    monkeypatch.setattr(
        release_module, "_audit_sdist", lambda _path: {"status": "PASS"}
    )
    return candidate, commit, manifest


def _write_candidate_manifest(candidate: Path, manifest: dict[str, Any]) -> None:
    (candidate / "release-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


def test_release_audit_schema_is_explicit() -> None:
    assert RELEASE_AUDIT_SCHEMA_VERSION == "release-audit.v1"


@pytest.mark.parametrize(
    "email",
    (
        _email("123+example", "users.noreply.github.com"),
        _email("noreply", "github.com"),
    ),
)
def test_github_user_and_system_noreply_identities_are_approved(email: str) -> None:
    assert _is_approved_github_noreply(email)


@pytest.mark.parametrize(
    "email",
    (
        _email("developer", "example.com"),
        _email("noreply", "example.com"),
        _email("example", "github.com"),
        "@users.noreply.github.com",
    ),
)
def test_non_github_noreply_identities_are_rejected(email: str) -> None:
    assert not _is_approved_github_noreply(email)


def test_license_placeholder_matches_the_reviewed_exact_text() -> None:
    license_path = Path(__file__).resolve().parents[2] / "LICENSE"

    assert license_path.read_text(encoding="utf-8") == LICENSE_POLICY_TEXT


def test_sensitive_scan_returns_only_rule_and_relative_path() -> None:
    private_path = b"C:" + b"\\Users\\" + b"private\\candidate.whl"

    findings = scan_sensitive_payload(private_path, "reports/example.md")

    assert [item.rule for item in findings] == ["windows_user_path"]
    assert findings[0].to_document() == {
        "rule": "windows_user_path",
        "relative_path": "reports/example.md",
    }
    assert b"private" not in repr(findings[0].to_document()).encode("utf-8")


def test_only_reviewed_manifest_privacy_fixture_is_allowlisted() -> None:
    private_path = b"/" + b"home/private/candidate.whl"
    approved_source = "tests/unit/test_release_candidate_check.py"
    unapproved_source = "reports/checkpoint.md"
    approved_finding = scan_sensitive_payload(private_path, approved_source)
    unapproved_finding = scan_sensitive_payload(private_path, unapproved_source)

    approved, unapproved = _partition_findings(approved_finding)
    assert approved and not unapproved
    approved, unapproved = _partition_findings(unapproved_finding)
    assert not approved and unapproved
    assert _is_approved_fixture(approved_source, "unix_user_path")
    assert not _is_approved_fixture(approved_source, "email_address")


def test_archive_member_path_rejects_traversal_and_backslashes() -> None:
    assert _normalize_member_path("package/module.py").as_posix() == "package/module.py"
    with pytest.raises(ReleaseAuditError, match="unsafe member"):
        _normalize_member_path("../outside.txt")
    with pytest.raises(ReleaseAuditError, match="unsafe member"):
        _normalize_member_path("package\\module.py")


@pytest.mark.parametrize("duplicate_index", (0, 1), ids=("wheel-only", "sdist-only"))
def test_candidate_manifest_requires_unique_complete_archive_filenames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, duplicate_index: int
) -> None:
    candidate, commit, manifest = _candidate_fixture(tmp_path, monkeypatch)
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list)
    duplicated = dict(artifacts[duplicate_index])
    manifest["artifacts"] = [duplicated, dict(duplicated)]
    _write_candidate_manifest(candidate, manifest)

    with pytest.raises(ReleaseAuditError, match="artifact inventory"):
        _audit_candidate(candidate, commit)


def test_candidate_manifest_accepts_unique_records_in_either_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate, commit, manifest = _candidate_fixture(tmp_path, monkeypatch)
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list)
    manifest["artifacts"] = list(reversed(artifacts))
    _write_candidate_manifest(candidate, manifest)

    result = _audit_candidate(candidate, commit)

    assert result["status"] == "PASS"
    assert result["manifest_source_commit_matches"] is True


def test_candidate_manifest_still_rejects_tampered_artifact_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate, commit, manifest = _candidate_fixture(tmp_path, monkeypatch)
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list)
    tampered = dict(artifacts[0])
    tampered["sha256"] = "0" * 64
    manifest["artifacts"] = [tampered, artifacts[1]]
    _write_candidate_manifest(candidate, manifest)

    with pytest.raises(ReleaseAuditError, match="identity does not match bytes"):
        _audit_candidate(candidate, commit)


def test_candidate_manifest_rejects_non_string_filename_as_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate, commit, manifest = _candidate_fixture(tmp_path, monkeypatch)
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list)
    malformed = dict(artifacts[0])
    malformed["filename"] = [malformed["filename"]]
    manifest["artifacts"] = [malformed, artifacts[1]]
    _write_candidate_manifest(candidate, manifest)

    with pytest.raises(ReleaseAuditError, match="unknown artifact"):
        _audit_candidate(candidate, commit)


def test_workbook_audit_accepts_visible_metadata_free_structure() -> None:
    document = audit_xlsx_bytes(_workbook())

    assert document["status"] == "PASS"
    assert document["sheet_count"] == 1
    assert document["formula_count"] == 1
    assert document["author_or_modifier_value_count"] == 0
    assert document["external_relationship_count"] == 0


@pytest.mark.parametrize(
    ("creator", "hidden", "message"),
    (
        ("private-builder", False, "author or modifier"),
        ("", True, "hidden sheet"),
    ),
)
def test_workbook_audit_rejects_private_metadata_or_hidden_sheet(
    creator: str, hidden: bool, message: str
) -> None:
    with pytest.raises(ReleaseAuditError, match=message):
        audit_xlsx_bytes(_workbook(creator=creator, hidden=hidden))


def test_audit_destination_is_strictly_create_new(tmp_path: Path) -> None:
    new_output = tmp_path / "release-audit.json"
    _validate_output_destination(new_output)

    new_output.write_text("existing", encoding="utf-8")
    with pytest.raises(ReleaseAuditDestinationError, match="already exists"):
        _validate_output_destination(new_output)

    missing_parent = tmp_path / "missing" / "release-audit.json"
    with pytest.raises(ReleaseAuditDestinationError, match="parent"):
        _validate_output_destination(missing_parent)
