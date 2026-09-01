#!/usr/bin/env python3
"""Audit a private-beta candidate without touching hardware or publishing it.

The audit intentionally reports rule names and repository-relative paths, never
the matched text.  Historical local-path/email findings are review items because
removing them would require an owner-approved Git history rewrite.  A current
tree or candidate finding is a hard failure.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree

RELEASE_AUDIT_SCHEMA_VERSION = "release-audit.v1"
RELEASE_MANIFEST_SCHEMA_VERSION = "release-candidate-manifest.v1"
PACKAGE_NAME = "mixed-signal-afe-validation-platform"
PACKAGE_VERSION = "0.1.0b1"
ROOT = Path(__file__).resolve().parents[1]
MAX_ARCHIVE_MEMBERS = 10_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_HISTORY_BLOB_BYTES = 2 * 1024 * 1024
WORKBOOK_PATH = "hardware/bom/independent-product-purchase.xlsx"
APPROVED_PRIVACY_FIXTURE = "tests/unit/test_release_candidate_check.py"
LICENSE_POLICY_TEXT = (
    "No license has been selected yet.\n\n"
    "All rights are reserved until the project owner chooses and adds a license.\n"
)


class ReleaseAuditError(RuntimeError):
    """Raised when an audit gate fails."""


class ReleaseAuditDestinationError(ReleaseAuditError):
    """Raised when the create-new report boundary is not satisfied."""


@dataclass(frozen=True)
class PrivacyFinding:
    """A finding that deliberately excludes the matched value."""

    rule: str
    relative_path: str

    def to_document(self) -> dict[str, str]:
        return {"rule": self.rule, "relative_path": self.relative_path}


SENSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[bytes]], ...] = (
    (
        "windows_user_path",
        re.compile(rb"(?i)(?<![A-Z0-9_])[A-Z]:\\Users\\[^\\/\s:*?\"<>|]+\\"),
    ),
    (
        "unix_user_path",
        re.compile(rb"(?i)(?<![A-Z0-9_])/(?:home|Users)/[^/\s]+/"),
    ),
    (
        "email_address",
        re.compile(rb"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    ),
    ("github_classic_token", re.compile(rb"\bghp_[A-Za-z0-9]{20,}\b")),
    (
        "github_fine_grained_token",
        re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    ),
    ("aws_access_key", re.compile(rb"\bAKIA[0-9A-Z]{16}\b")),
    (
        "private_key_block",
        re.compile(rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    ),
)
SEVERE_HISTORY_RULES = {
    "github_classic_token",
    "github_fine_grained_token",
    "aws_access_key",
    "private_key_block",
}


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run_git(*arguments: str, root: Path = ROOT) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=120,
    )
    if completed.returncode != 0:
        raise ReleaseAuditError("Git audit command failed")
    return completed.stdout


def _normalize_member_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not name or "\\" in name or path.is_absolute() or ".." in path.parts:
        raise ReleaseAuditError("archive contains an unsafe member path")
    return path


def _is_approved_fixture(relative_path: str, rule: str) -> bool:
    normalized = relative_path.replace("\\", "/")
    return normalized.endswith(APPROVED_PRIVACY_FIXTURE) and rule in {
        "windows_user_path",
        "unix_user_path",
    }


def scan_sensitive_payload(payload: bytes, relative_path: str) -> tuple[PrivacyFinding, ...]:
    """Return rule/path findings without returning or logging matched values."""

    findings: list[PrivacyFinding] = []
    for rule, pattern in SENSITIVE_PATTERNS:
        if pattern.search(payload) is not None:
            findings.append(PrivacyFinding(rule, relative_path.replace("\\", "/")))
    return tuple(findings)


def _partition_findings(
    findings: Iterable[PrivacyFinding],
) -> tuple[tuple[PrivacyFinding, ...], tuple[PrivacyFinding, ...]]:
    approved: set[PrivacyFinding] = set()
    unapproved: set[PrivacyFinding] = set()
    for finding in findings:
        target = approved if _is_approved_fixture(finding.relative_path, finding.rule) else unapproved
        target.add(finding)
    ordering = lambda item: (item.relative_path, item.rule)
    return tuple(sorted(approved, key=ordering)), tuple(sorted(unapproved, key=ordering))


def _validate_output_destination(output: Path) -> None:
    if output.exists() or output.is_symlink():
        raise ReleaseAuditDestinationError(
            "audit output already exists; choose a new file"
        )
    if not output.parent.is_dir():
        raise ReleaseAuditDestinationError("audit output parent must already exist")
    if output.name in {"", ".", ".."}:
        raise ReleaseAuditDestinationError("audit output name is invalid")


def _source_identity(root: Path) -> tuple[str, str]:
    status = _run_git(
        "status", "--porcelain=v1", "--untracked-files=all", root=root
    )
    if status.strip():
        raise ReleaseAuditError("Git working tree is not clean")
    commit = _run_git("rev-parse", "HEAD", root=root).strip()
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ReleaseAuditError("Git returned an invalid source commit")
    timestamp = _run_git(
        "show", "-s", "--format=%cI", "HEAD", root=root
    ).strip()
    if not timestamp:
        raise ReleaseAuditError("Git returned no source timestamp")
    return commit, timestamp


def _tracked_entries(root: Path) -> tuple[tuple[str, str, str], ...]:
    output = _run_git("ls-files", "-s", "-z", root=root)
    entries: list[tuple[str, str, str]] = []
    for record in output.split("\0"):
        if not record:
            continue
        metadata, path = record.split("\t", 1)
        mode, object_id, _stage = metadata.split(" ", 2)
        entries.append((path.replace("\\", "/"), mode, object_id))
    return tuple(entries)


def _audit_tracked_tree(root: Path) -> dict[str, object]:
    entries = _tracked_entries(root)
    paths = tuple(path for path, _mode, _object_id in entries)
    banned_names = {
        ".env",
        "id_rsa",
        "id_ed25519",
        "credentials.json",
        "credentials.yml",
        "credentials.yaml",
    }
    banned_suffixes = {".key", ".p12", ".pfx", ".pem"}
    invalid_paths = sorted(
        path
        for path in paths
        if Path(path).name.casefold() in banned_names
        or Path(path).suffix.casefold() in banned_suffixes
        or any(
            part.casefold() in {".venv", "dist", "build", "__pycache__"}
            for part in PurePosixPath(path).parts
        )
    )
    symlinks = sorted(path for path, mode, _object_id in entries if mode == "120000")
    if invalid_paths or symlinks:
        raise ReleaseAuditError("tracked tree contains a forbidden path or symbolic link")

    binary_paths: list[str] = []
    findings: list[PrivacyFinding] = []
    for path, _mode, _object_id in entries:
        payload = (root / Path(path)).read_bytes()
        if path == WORKBOOK_PATH:
            binary_paths.append(path)
            continue
        if b"\x00" in payload:
            binary_paths.append(path)
            continue
        findings.extend(scan_sensitive_payload(payload, path))
    approved, unapproved = _partition_findings(findings)
    if unapproved:
        raise ReleaseAuditError(
            "current tracked text contains a privacy finding: "
            f"{unapproved[0].rule} in {unapproved[0].relative_path}"
        )
    if binary_paths != [WORKBOOK_PATH]:
        raise ReleaseAuditError("tracked binary inventory differs from the reviewed allowlist")

    return {
        "status": "PASS",
        "tracked_file_count": len(entries),
        "tracked_binary_count": len(binary_paths),
        "tracked_binary_paths": binary_paths,
        "approved_test_fixture_findings": [item.to_document() for item in approved],
        "forbidden_path_count": 0,
        "symlink_count": 0,
        "current_privacy_finding_count": 0,
    }


def _xlsx_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def audit_xlsx_bytes(payload: bytes) -> dict[str, object]:
    """Inspect workbook structure and metadata using only the standard library."""

    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = archive.namelist()
            if not names or len(names) > MAX_ARCHIVE_MEMBERS:
                raise ReleaseAuditError("workbook member inventory is invalid")
            for name in names:
                _normalize_member_path(name)
            lowered = tuple(name.casefold() for name in names)
            forbidden_fragments = (
                "vbaproject",
                "externallinks/",
                "embeddings/",
                "customxml/",
                "comments",
                "oleobject",
            )
            if any(
                fragment in name
                for name in lowered
                for fragment in forbidden_fragments
            ):
                raise ReleaseAuditError("workbook contains an unreviewed active component")

            xml_payloads: list[tuple[str, bytes]] = []
            total_size = 0
            for name in names:
                item = archive.getinfo(name)
                total_size += item.file_size
                if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                    raise ReleaseAuditError("workbook uncompressed content is too large")
                if name.casefold().endswith((".xml", ".rels")):
                    xml_payloads.append((name, archive.read(name)))

            workbook_name = "xl/workbook.xml"
            if workbook_name not in names:
                raise ReleaseAuditError("workbook is missing xl/workbook.xml")
            workbook_root = ElementTree.fromstring(archive.read(workbook_name))
            sheets = [
                element
                for element in workbook_root.iter()
                if _xlsx_local_name(element.tag) == "sheet"
            ]
            hidden = [
                element
                for element in sheets
                if element.attrib.get("state", "visible") != "visible"
            ]
            if hidden:
                raise ReleaseAuditError("workbook contains a hidden sheet")

            metadata_fields = 0
            if "docProps/core.xml" in names:
                core_root = ElementTree.fromstring(archive.read("docProps/core.xml"))
                for element in core_root.iter():
                    if _xlsx_local_name(element.tag) in {"creator", "lastModifiedBy"}:
                        if (element.text or "").strip():
                            raise ReleaseAuditError(
                                "workbook contains author or modifier metadata"
                            )
                        metadata_fields += 1

            external_relationships = 0
            formula_count = 0
            findings: list[PrivacyFinding] = []
            for name, xml_payload in xml_payloads:
                root = ElementTree.fromstring(xml_payload)
                for element in root.iter():
                    if (
                        _xlsx_local_name(element.tag) == "Relationship"
                        and element.attrib.get("TargetMode") == "External"
                    ):
                        external_relationships += 1
                    if _xlsx_local_name(element.tag) == "f":
                        formula_count += 1
                findings.extend(scan_sensitive_payload(xml_payload, WORKBOOK_PATH))
            _approved, unapproved = _partition_findings(findings)
            if unapproved:
                raise ReleaseAuditError("workbook XML contains a privacy finding")
            if external_relationships:
                raise ReleaseAuditError("workbook contains an external relationship")
    except (ElementTree.ParseError, KeyError, OSError, zipfile.BadZipFile) as error:
        if isinstance(error, ReleaseAuditError):  # pragma: no cover - defensive
            raise
        raise ReleaseAuditError("workbook could not be structurally inspected") from error

    return {
        "status": "PASS",
        "relative_path": WORKBOOK_PATH,
        "archive_member_count": len(names),
        "sheet_count": len(sheets),
        "formula_count": formula_count,
        "author_or_modifier_value_count": 0,
        "external_relationship_count": 0,
        "hidden_sheet_count": 0,
        "active_component_count": 0,
        "privacy_finding_count": 0,
        "metadata_field_count": metadata_fields,
    }


def _audit_current_workbook(root: Path) -> dict[str, object]:
    path = root / WORKBOOK_PATH
    if not path.is_file():
        raise ReleaseAuditError("reviewed workbook is missing")
    return audit_xlsx_bytes(path.read_bytes())


def _history_object_inventory(root: Path) -> tuple[dict[str, str], dict[str, int]]:
    lines = _run_git("rev-list", "--objects", "--all", root=root).splitlines()
    object_paths: dict[str, str] = {}
    object_ids: list[str] = []
    for line in lines:
        object_id, separator, path = line.partition(" ")
        object_ids.append(object_id)
        if separator and object_id not in object_paths:
            object_paths[object_id] = path.replace("\\", "/")

    checked = subprocess.run(
        ("git", "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)"),
        cwd=root,
        input="\n".join(object_ids) + "\n",
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=120,
    )
    if checked.returncode != 0:
        raise ReleaseAuditError("Git history object inventory failed")
    blob_sizes: dict[str, int] = {}
    for line in checked.stdout.splitlines():
        object_id, object_type, size_text = line.split(" ", 2)
        if object_type == "blob":
            blob_sizes[object_id] = int(size_text)
    return object_paths, blob_sizes


def _read_git_blobs(root: Path, object_ids: Sequence[str]) -> dict[str, bytes]:
    if not object_ids:
        return {}
    completed = subprocess.run(
        ("git", "cat-file", "--batch"),
        cwd=root,
        input=("\n".join(object_ids) + "\n").encode("ascii"),
        capture_output=True,
        check=False,
        timeout=120,
    )
    if completed.returncode != 0:
        raise ReleaseAuditError("Git history blob read failed")
    data = completed.stdout
    cursor = 0
    blobs: dict[str, bytes] = {}
    for expected in object_ids:
        end = data.find(b"\n", cursor)
        if end < 0:
            raise ReleaseAuditError("Git history blob stream is truncated")
        header = data[cursor:end].decode("ascii", errors="strict")
        object_id, object_type, size_text = header.split(" ", 2)
        if object_id != expected or object_type != "blob":
            raise ReleaseAuditError("Git history blob stream identity changed")
        size = int(size_text)
        start = end + 1
        finish = start + size
        blobs[object_id] = data[start:finish]
        if data[finish : finish + 1] != b"\n":
            raise ReleaseAuditError("Git history blob stream terminator is invalid")
        cursor = finish + 1
    return blobs


def _audit_git_history(root: Path) -> dict[str, object]:
    shallow = _run_git("rev-parse", "--is-shallow-repository", root=root).strip()
    if shallow != "false":
        raise ReleaseAuditError("complete Git history is unavailable; use a full clone")
    commit_count = int(_run_git("rev-list", "--all", "--count", root=root).strip())
    object_paths, blob_sizes = _history_object_inventory(root)
    oversized = sorted(
        object_paths.get(object_id, "<unmapped>")
        for object_id, size in blob_sizes.items()
        if size > MAX_HISTORY_BLOB_BYTES
    )
    if oversized:
        raise ReleaseAuditError("Git history contains an oversized unreviewed blob")

    object_ids = sorted(blob_sizes)
    blobs = _read_git_blobs(root, object_ids)
    current_ids = {object_id for _path, _mode, object_id in _tracked_entries(root)}
    approved: set[PrivacyFinding] = set()
    current_findings: set[PrivacyFinding] = set()
    historical_findings: set[PrivacyFinding] = set()
    workbook_versions = 0
    historical_workbook_review_paths: set[str] = set()

    for object_id in object_ids:
        path = object_paths.get(object_id, "<unmapped>")
        payload = blobs[object_id]
        if path.casefold().endswith(".xlsx"):
            workbook_versions += 1
            try:
                audit_xlsx_bytes(payload)
            except ReleaseAuditError:
                if object_id in current_ids:
                    raise
                historical_workbook_review_paths.add(path)
            continue
        for finding in scan_sensitive_payload(payload, path):
            if _is_approved_fixture(finding.relative_path, finding.rule):
                approved.add(finding)
            elif object_id in current_ids:
                current_findings.add(finding)
            else:
                historical_findings.add(finding)

    if current_findings:
        finding = min(current_findings, key=lambda item: (item.relative_path, item.rule))
        raise ReleaseAuditError(
            "current Git blob contains a privacy finding: "
            f"{finding.rule} in {finding.relative_path}"
        )
    severe = sorted(
        (
            finding
            for finding in historical_findings
            if finding.rule in SEVERE_HISTORY_RULES
        ),
        key=lambda item: (item.relative_path, item.rule),
    )
    if severe:
        raise ReleaseAuditError(
            "complete Git history contains a high-confidence credential finding"
        )

    history_review = sorted(
        historical_findings, key=lambda item: (item.relative_path, item.rule)
    )
    workbook_review = sorted(historical_workbook_review_paths)
    status = "REVIEW" if history_review or workbook_review else "PASS"
    return {
        "status": status,
        "complete_history_available": True,
        "commit_count": commit_count,
        "unique_blob_count": len(blob_sizes),
        "maximum_reviewed_blob_bytes": max(blob_sizes.values(), default=0),
        "oversized_blob_count": 0,
        "current_privacy_finding_count": 0,
        "historical_review_finding_count": len(history_review),
        "historical_review_findings": [item.to_document() for item in history_review],
        "approved_test_fixture_findings": [
            item.to_document()
            for item in sorted(approved, key=lambda item: (item.relative_path, item.rule))
        ],
        "workbook_version_count": workbook_versions,
        "historical_workbook_review_paths": workbook_review,
        "high_confidence_credential_finding_count": 0,
    }


def _audit_git_identities(root: Path) -> dict[str, object]:
    records = _run_git(
        "log", "--all", "--format=%an%x00%ae%x00%cn%x00%ce", root=root
    ).splitlines()
    names: set[str] = set()
    emails: set[str] = set()
    for record in records:
        fields = record.split("\0")
        if len(fields) != 4:
            raise ReleaseAuditError("Git identity record is malformed")
        author_name, author_email, committer_name, committer_email = fields
        names.update((author_name, committer_name))
        emails.update((author_email, committer_email))
    if not emails or any(not _is_approved_github_noreply(value) for value in emails):
        raise ReleaseAuditError("Git history contains an unreviewed commit email")
    return {
        "status": "PASS",
        "unique_name_count": len(names),
        "unique_email_count": len(emails),
        "all_commit_emails_use_github_noreply": True,
        "identity_values_embedded": False,
    }


def _is_approved_github_noreply(value: str) -> bool:
    """Accept GitHub user and system noreply identities, but no other email."""

    return value == "noreply" + "@" + "github.com" or re.fullmatch(
        r"[^@\s]+@users\.noreply\.github\.com", value
    ) is not None


def _archive_privacy(
    members: Iterable[tuple[str, bytes]],
) -> tuple[tuple[PrivacyFinding, ...], tuple[PrivacyFinding, ...]]:
    findings: list[PrivacyFinding] = []
    for name, payload in members:
        findings.extend(scan_sensitive_payload(payload, name))
    return _partition_findings(findings)


def _audit_wheel(path: Path) -> tuple[dict[str, object], dict[str, Any]]:
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if not names or len(names) > MAX_ARCHIVE_MEMBERS:
                raise ReleaseAuditError("wheel member inventory is invalid")
            total_size = 0
            payloads: list[tuple[str, bytes]] = []
            for name in names:
                _normalize_member_path(name)
                info = archive.getinfo(name)
                total_size += info.file_size
                if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                    raise ReleaseAuditError("wheel uncompressed content is too large")
                if not name.endswith("/"):
                    payloads.append((name, archive.read(name)))
            damaged = archive.testzip()
            if damaged is not None:
                raise ReleaseAuditError("wheel contains a damaged member")
            metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
            if len(metadata_names) != 1:
                raise ReleaseAuditError("wheel metadata inventory is invalid")
            metadata = BytesParser(policy=policy.default).parsebytes(
                archive.read(metadata_names[0])
            )
    except (KeyError, OSError, zipfile.BadZipFile) as error:
        raise ReleaseAuditError("wheel could not be inspected") from error

    approved, unapproved = _archive_privacy(payloads)
    if unapproved:
        raise ReleaseAuditError("wheel contains a privacy finding")
    classifiers = tuple(str(item) for item in metadata.get_all("Classifier", []))
    requirements = tuple(str(item) for item in metadata.get_all("Requires-Dist", []))
    base_requirements = tuple(
        item for item in requirements if "extra ==" not in item.casefold()
    )
    serial_requirements = tuple(
        item
        for item in requirements
        if re.search(r"extra\s*==\s*['\"]serial['\"]", item, re.IGNORECASE)
    )
    license_members = sorted(
        name for name in names if ".dist-info/licenses/" in name
    )
    if str(metadata.get("Name", "")) != PACKAGE_NAME:
        raise ReleaseAuditError("wheel package name differs from the release contract")
    if str(metadata.get("Version", "")) != PACKAGE_VERSION:
        raise ReleaseAuditError("wheel version differs from the release contract")
    if metadata.get("License") or metadata.get("License-Expression"):
        raise ReleaseAuditError("wheel unexpectedly declares a project license")
    if any(item.startswith("License ::") for item in classifiers):
        raise ReleaseAuditError("wheel unexpectedly declares a license classifier")
    if base_requirements:
        raise ReleaseAuditError("wheel unexpectedly declares a base dependency")
    if len(serial_requirements) != 1 or not serial_requirements[0].casefold().startswith(
        "pyserial"
    ):
        raise ReleaseAuditError("wheel serial dependency differs from the release contract")
    if not any(name.endswith("/LICENSE") for name in license_members):
        raise ReleaseAuditError("wheel does not carry the project rights-reserved notice")
    if not any(name.endswith("/THIRD_PARTY_NOTICES.md") for name in license_members):
        raise ReleaseAuditError("wheel does not carry third-party notices")

    return (
        {
            "status": "PASS",
            "member_count": len(names),
            "uncompressed_bytes": total_size,
            "approved_test_fixture_findings": [
                item.to_document() for item in approved
            ],
            "privacy_finding_count": 0,
            "license_notice_member_count": len(license_members),
        },
        {
            "name": str(metadata.get("Name", "")),
            "version": str(metadata.get("Version", "")),
            "base_requirements": list(base_requirements),
            "serial_requirements": list(serial_requirements),
            "license_header_present": False,
            "license_expression_present": False,
            "license_classifier_count": 0,
        },
    )


def _audit_sdist(path: Path) -> dict[str, object]:
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            members = archive.getmembers()
            if not members or len(members) > MAX_ARCHIVE_MEMBERS:
                raise ReleaseAuditError("sdist member inventory is invalid")
            total_size = 0
            payloads: list[tuple[str, bytes]] = []
            file_names: list[str] = []
            for member in members:
                _normalize_member_path(member.name)
                if member.isdir():
                    continue
                if not member.isfile():
                    raise ReleaseAuditError("sdist contains an unsupported member type")
                total_size += member.size
                if total_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                    raise ReleaseAuditError("sdist uncompressed content is too large")
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise ReleaseAuditError("sdist member could not be read")
                payloads.append((member.name, extracted.read()))
                file_names.append(member.name)
    except (OSError, tarfile.TarError) as error:
        raise ReleaseAuditError("sdist could not be inspected") from error

    approved, unapproved = _archive_privacy(payloads)
    if unapproved:
        finding = unapproved[0]
        raise ReleaseAuditError(
            "sdist contains a privacy finding: "
            f"{finding.rule} in {finding.relative_path}"
        )
    if any(name.casefold().endswith(".xlsx") for name in file_names):
        raise ReleaseAuditError("sdist unexpectedly contains the planning workbook")
    if not any(name.endswith("/LICENSE") for name in file_names):
        raise ReleaseAuditError("sdist does not carry the project rights-reserved notice")
    if not any(name.endswith("/THIRD_PARTY_NOTICES.md") for name in file_names):
        raise ReleaseAuditError("sdist does not carry third-party notices")
    required_suffixes = (
        "/ASSUMPTIONS.md",
        "/docs/INSTALLATION.md",
        "/docs/USER_TESTING_GUIDE.md",
        "/docs/KNOWN_LIMITATIONS.md",
        "/docs/RELEASE_NOTES_DRAFT.md",
        "/docs/PRIVATE_BETA_HANDOFF.md",
        "/examples/public_adapter/read_only_voltage_adapter.py",
    )
    if any(
        not any(name.endswith(suffix) for name in file_names)
        for suffix in required_suffixes
    ):
        raise ReleaseAuditError("sdist is missing a required tester or extension document")
    return {
        "status": "PASS",
        "member_count": len(members),
        "file_count": len(file_names),
        "uncompressed_bytes": total_size,
        "approved_test_fixture_findings": [item.to_document() for item in approved],
        "privacy_finding_count": 0,
        "planning_workbook_included": False,
        "required_tester_and_extension_files_present": True,
    }


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseAuditError(f"{label} could not be read") from error
    if not isinstance(document, dict):
        raise ReleaseAuditError(f"{label} must be a JSON object")
    return document


def _audit_candidate(candidate: Path, commit: str) -> dict[str, object]:
    if not candidate.is_dir():
        raise ReleaseAuditError("candidate directory does not exist")
    paths = sorted(path for path in candidate.iterdir() if path.is_file())
    wheels = [path for path in paths if path.name.endswith(".whl")]
    sdists = [path for path in paths if path.name.endswith(".tar.gz")]
    manifests = [path for path in paths if path.name == "release-manifest.json"]
    if len(paths) != 3 or len(wheels) != 1 or len(sdists) != 1 or len(manifests) != 1:
        raise ReleaseAuditError("candidate must contain exactly one wheel, sdist, and manifest")

    manifest = _load_json(manifests[0], "release manifest")
    source = manifest.get("source")
    evidence = manifest.get("evidence_boundary")
    artifacts = manifest.get("artifacts")
    if manifest.get("schema_version") != RELEASE_MANIFEST_SCHEMA_VERSION:
        raise ReleaseAuditError("release manifest schema differs from the contract")
    if manifest.get("candidate_status") != "PASS":
        raise ReleaseAuditError("release manifest does not report PASS")
    if not isinstance(source, dict) or source.get("commit") != commit:
        raise ReleaseAuditError("candidate source commit differs from the audited commit")
    if source.get("working_tree") != "CLEAN":
        raise ReleaseAuditError("candidate was not produced from a clean tree")
    if not isinstance(evidence, dict) or evidence.get("hardware_claim") != (
        "NO_NEW_HARDWARE_VALIDATION"
    ):
        raise ReleaseAuditError("candidate hardware evidence boundary changed")
    for field in ("serial_ports_enumerated", "serial_ports_opened", "application_bytes_written"):
        if evidence.get(field) != 0:
            raise ReleaseAuditError("candidate performed a forbidden hardware operation")
    if not isinstance(artifacts, list) or len(artifacts) != 2:
        raise ReleaseAuditError("release manifest artifact inventory is invalid")
    expected_records = {
        path.name: {"size_bytes": path.stat().st_size, "sha256": _sha256(path)}
        for path in (wheels[0], sdists[0])
    }
    for record in artifacts:
        if not isinstance(record, dict) or record.get("filename") not in expected_records:
            raise ReleaseAuditError("release manifest contains an unknown artifact")
        expected = expected_records[str(record["filename"])]
        if record.get("size_bytes") != expected["size_bytes"] or record.get("sha256") != expected["sha256"]:
            raise ReleaseAuditError("release manifest artifact identity does not match bytes")

    wheel, metadata = _audit_wheel(wheels[0])
    sdist = _audit_sdist(sdists[0])
    inventory = [
        {
            "filename": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in paths
    ]
    return {
        "status": "PASS",
        "file_count_before_audit_report": 3,
        "artifacts": inventory,
        "manifest_schema": RELEASE_MANIFEST_SCHEMA_VERSION,
        "manifest_candidate_status": "PASS",
        "manifest_source_commit_matches": True,
        "wheel": wheel,
        "sdist": sdist,
        "metadata": metadata,
    }


def _audit_license_and_notices(root: Path) -> dict[str, object]:
    license_text = (root / "LICENSE").read_text(encoding="utf-8")
    if license_text != LICENSE_POLICY_TEXT:
        raise ReleaseAuditError("LICENSE differs from the owner-decision placeholder")
    notice = root / "THIRD_PARTY_NOTICES.md"
    if not notice.is_file():
        raise ReleaseAuditError("THIRD_PARTY_NOTICES.md is missing")
    notice_text = notice.read_text(encoding="utf-8")
    for required in (
        "pyserial",
        "BSD-3-Clause",
        "actions/checkout",
        "actions/setup-python",
        "actions/upload-artifact",
        "does not grant a license",
    ):
        if required not in notice_text:
            raise ReleaseAuditError("third-party notices are incomplete")
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    project_block = pyproject.split("[project.urls]", 1)[0]
    if re.search(r"(?m)^license\s*=", project_block):
        raise ReleaseAuditError("pyproject unexpectedly declares a project license")
    if "License ::" in pyproject:
        raise ReleaseAuditError("pyproject unexpectedly declares a license classifier")
    return {
        "status": "PASS",
        "project_license_state": "OWNER_DECISION_REQUIRED_ALL_RIGHTS_RESERVED",
        "open_source_license_selected": False,
        "project_license_metadata_present": False,
        "third_party_notice_present": True,
        "base_runtime_dependency_count": 0,
        "optional_serial_dependency": "pyserial>=3.5,<4",
    }


def _audit_project_boundaries(root: Path) -> dict[str, object]:
    tracked = tuple(path for path, _mode, _object_id in _tracked_entries(root))
    forbidden_path_terms = ("osu-lab-bench", "osu_lab_bench", "lab-bench-monitor", "capstone-source")
    if any(term in path.casefold() for path in tracked for term in forbidden_path_terms):
        raise ReleaseAuditError("tracked path crosses the independent-project boundary")
    import_pattern = re.compile(
        r"(?m)^\s*(?:from|import)\s+(?:osu(?:\.|\s)|lab_bench_monitor(?:\.|\s)|equipment_health_controller(?:\.|\s))"
    )
    python_files = [path for path in tracked if path.endswith(".py")]
    if any(
        import_pattern.search((root / path).read_text(encoding="utf-8"))
        for path in python_files
    ):
        raise ReleaseAuditError("runtime imports a peer or team project")
    readme = (root / "README.md").read_text(encoding="utf-8")
    required_claims = (
        "independent personal engineering project",
        "OSU Lab Bench Monitor Senior Capstone",
        "NO_NEW_HARDWARE_VALIDATION",
        "AFE hardware bench tests | Not run",
        "No open-source license has been selected",
    )
    if any(value.casefold() not in readme.casefold() for value in required_claims):
        raise ReleaseAuditError("README evidence or independence boundary is incomplete")
    target_tag = f"v{PACKAGE_VERSION}"
    tags = _run_git("tag", "--list", target_tag, root=root).splitlines()
    if tags:
        raise ReleaseAuditError("private-beta target tag already exists")
    return {
        "status": "PASS",
        "independent_product": True,
        "peer_project_runtime_import_count": 0,
        "team_project_tracked_path_count": 0,
        "msp430_role": "OPTIONAL_PUBLIC_COMPATIBILITY_PROFILE",
        "osu_capstone_role": "SEPARATE_NO_TEAM_OUTPUT_INCLUDED",
        "target_tag_absent": True,
        "hardware_claim": "NO_NEW_HARDWARE_VALIDATION",
        "afe_bench_requirements_verified": 0,
    }


def build_release_audit(candidate: Path, *, root: Path = ROOT) -> dict[str, object]:
    """Build one deterministic audit document without writing it."""

    commit, timestamp = _source_identity(root)
    tracked = _audit_tracked_tree(root)
    workbook = _audit_current_workbook(root)
    history = _audit_git_history(root)
    identities = _audit_git_identities(root)
    license_state = _audit_license_and_notices(root)
    boundaries = _audit_project_boundaries(root)
    candidate_result = _audit_candidate(candidate, commit)
    review_required = history["status"] == "REVIEW"
    audit_status = "PASS_WITH_REVIEW" if review_required else "PASS"
    document: dict[str, object] = {
        "schema_version": RELEASE_AUDIT_SCHEMA_VERSION,
        "audit_status": audit_status,
        "source": {
            "commit": commit,
            "commit_timestamp": timestamp,
            "working_tree": "CLEAN",
        },
        "gates": {
            "candidate_archives_and_metadata": "PASS",
            "current_tracked_tree_privacy": "PASS",
            "complete_git_history": history["status"],
            "git_commit_identities": "PASS",
            "planning_workbook_structure_and_privacy": "PASS",
            "license_and_third_party_notices": "PASS",
            "claims_and_project_boundaries": "PASS",
        },
        "release_readiness": {
            "private_binary_beta": "READY",
            "public_git_history": (
                "OWNER_REVIEW_REQUIRED" if review_required else "READY"
            ),
            "open_source_distribution": "BLOCKED_NO_PROJECT_LICENSE",
            "v1_0": "BLOCKED_OWNER_DECISION_AND_BETA_FEEDBACK",
        },
        "candidate": candidate_result,
        "current_tracked_tree": tracked,
        "complete_git_history": history,
        "git_commit_identities": identities,
        "planning_workbook": workbook,
        "license_and_notices": license_state,
        "project_boundaries": boundaries,
        "evidence_boundary": {
            "evidence_sources": ["HOST_TEST", "SYNTHETIC"],
            "hardware_claim": "NO_NEW_HARDWARE_VALIDATION",
            "afe_bench_requirements_verified": 0,
            "physical_hardware_operations": "NOT_RUN",
            "serial_ports_enumerated": 0,
            "serial_ports_opened": 0,
            "application_bytes_written": 0,
        },
        "not_run": [
            "Git history rewrite or force push",
            "merge, tag, GitHub Release, PyPI upload, or visibility change",
            "project license selection",
            "LinkedIn publication",
            "MSP430 or AFE device access",
            "laboratory instrument operation",
            "physical AFE assembly or measurement",
        ],
    }
    serialized = json.dumps(document, ensure_ascii=False, sort_keys=True).encode("utf-8")
    _approved, unapproved = _partition_findings(
        scan_sensitive_payload(serialized, "release-audit.json")
    )
    if unapproved:
        raise ReleaseAuditError("audit document would contain a privacy finding")
    return document


def write_release_audit(
    output: Path, candidate: Path, *, root: Path = ROOT
) -> dict[str, object]:
    """Write one create-new report after every audit gate has passed."""

    _validate_output_destination(output)
    document = build_release_audit(candidate, root=root)
    payload = (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    staging_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="xb",
            prefix=".release-audit-",
            suffix=".json",
            dir=output.parent,
            delete=False,
        ) as handle:
            staging_path = Path(handle.name)
            handle.write(payload)
        staging_path.rename(output)
    except OSError as error:
        if staging_path is not None:
            staging_path.unlink(missing_ok=True)
        raise ReleaseAuditError("audit report could not be written atomically") from error
    return document


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit a private-beta candidate without hardware or publication"
    )
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        document = write_release_audit(arguments.output, arguments.candidate)
    except ReleaseAuditDestinationError as error:
        print(f"[BLOCKED] {error}", file=sys.stderr)
        return 2
    except ReleaseAuditError as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        return 1
    print(f"[PASS] release audit: {document['audit_status']}")
    print("[PASS] current candidate and tracked tree contain no unapproved privacy findings")
    print("[INFO] no hardware, publication, or license-selection action was performed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
