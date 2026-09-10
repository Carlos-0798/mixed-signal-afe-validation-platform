"""Static contract for the private-beta beginner and feedback workflow."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
TEMPLATES = ROOT / ".github" / "ISSUE_TEMPLATE"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_required_tester_documents_exist_and_cross_link() -> None:
    expected = {
        "INSTALLATION.md",
        "USER_TESTING_GUIDE.md",
        "TROUBLESHOOTING.md",
        "KNOWN_LIMITATIONS.md",
        "BETA_TEST_CHECKLIST.md",
    }
    assert expected <= {path.name for path in DOCS.glob("*.md")}

    combined = "\n".join(_text(DOCS / name) for name in sorted(expected))
    for name in expected:
        assert name in combined
    assert "0.1.0b1" in combined
    assert "NO_NEW_HARDWARE_VALIDATION" in combined
    assert "SYNTHETIC" in combined
    assert "CSV_REPLAY" in combined
    assert "HOST_TEST" in combined


def test_base_install_and_demo_path_is_exact_and_hardware_free() -> None:
    installation = _text(DOCS / "INSTALLATION.md")
    testing = _text(DOCS / "USER_TESTING_GUIDE.md")

    assert "pip install --no-deps" in installation
    assert "pip check" in installation
    assert "version --json" in installation
    assert "demo --output" in installation
    assert "Get-FileHash -Algorithm SHA256" in installation
    assert "candidate_status: PASS" in testing
    assert "serial ports opened | 0" in testing
    assert "application bytes written | 0" in testing
    assert "Do not investigate by connecting hardware" in testing
    assert "Do not select Serial" in testing


def test_troubleshooting_and_limit_docs_preserve_stop_conditions() -> None:
    troubleshooting = _text(DOCS / "TROUBLESHOOTING.md")
    limitations = _text(DOCS / "KNOWN_LIMITATIONS.md")

    for value in (
        "Candidate SHA-256 differs",
        "WinError 206",
        "OUTPUT_EXISTS",
        "Exit code `70`",
        "Do not include",
    ):
        assert value in troubleshooting
    for value in (
        "The owner selected the MIT License",
        "not v1.0 or production-ready",
        "macOS",
        "pyserial is optional",
        "Verified AFE gain",
        "OSU Lab Bench Monitor Capstone",
    ):
        assert value in limitations


def test_issue_forms_collect_bounded_sanitized_feedback() -> None:
    bug = _text(TEMPLATES / "bug_report.yml")
    feedback = _text(TEMPLATES / "test_feedback.yml")
    config = _text(TEMPLATES / "config.yml")

    for source in (bug, feedback):
        assert "<beta-root>" in source
        assert "required: true" in source
        assert "raw serial" in source or "raw frames" in source
        assert "USB/port" in source
        assert "SHA-256" in source
        assert "password" not in source.casefold()
        assert "access_token" not in source.casefold()
        assert "COM4" not in source
    assert "SYNTHETIC" in bug
    assert "CSV_REPLAY" in bug
    assert "HOST_TEST" in bug
    assert "PASS" in feedback and "PARTIAL" in feedback and "BLOCKED" in feedback
    assert "blank_issues_enabled: false" in config
    assert "contact_links: []" in config


def test_checklist_does_not_authorize_publication_or_hardware() -> None:
    checklist = _text(DOCS / "BETA_TEST_CHECKLIST.md")

    for decision in (
        "merge",
        "tag",
        "GitHub Release",
        "license change",
        "public repository",
        "PyPI upload",
        "LinkedIn publication",
        "v1.0 claim",
    ):
        assert decision in checklist
    assert "Serial remained NOT_RUN" in checklist
    assert "No administrator" in checklist
