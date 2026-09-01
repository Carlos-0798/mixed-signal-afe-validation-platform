"""Static safety and quality contract for the hosted CI workflow."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_ci_workflow_exists_with_read_only_permissions_and_safe_triggers() -> None:
    text = _workflow_text()

    assert "permissions:\n  contents: read\n" in text
    assert "pull_request_target" not in text
    assert "contents: write" not in text
    assert "packages: write" not in text
    assert "id-token: write" not in text
    assert "secrets." not in text
    assert "workflow_dispatch:" in text
    assert "cancel-in-progress: true" in text


def test_ci_actions_are_pinned_to_reviewed_commit_shas() -> None:
    text = _workflow_text()
    expected = {
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    }

    action_references = {
        line.strip().removeprefix("uses: ")
        for line in text.splitlines()
        if line.strip().startswith("uses:")
    }

    assert action_references == expected
    assert "actions/checkout v7.0.1" in text
    assert "actions/setup-python v7.0.0" in text
    assert "actions/upload-artifact v7.0.1" in text


def test_ci_matrix_and_formal_quality_gates_are_explicit() -> None:
    text = _workflow_text()

    assert "ubuntu-latest" in text
    assert "windows-latest" in text
    for version in ('"3.10"', '"3.12"', '"3.14"'):
        assert version in text
    assert "python -m pytest -q" in text
    assert "--cov-fail-under=100" in text
    assert "python -m ruff check src tools tests examples/public_adapter" in text
    assert "python -m mypy src tools tests examples/public_adapter" in text
    assert text.count("python -m pip check") >= 2


def test_ci_package_job_preserves_optional_and_hardware_boundaries() -> None:
    text = _workflow_text()

    assert 'python -m pip install ".[dev,serial]"' in text
    assert "python tools/release_candidate_check.py" in text
    assert '--output "${{ runner.temp }}/release-candidate"' in text
    assert "python tools/release_audit.py" in text
    assert '--candidate "${{ runner.temp }}/release-candidate"' in text
    assert '--output "${{ runner.temp }}/release-candidate/release-audit.json"' in text
    assert "fetch-depth: 0" in text
    assert text.count("fetch-depth: 0") == 1
    assert "private-beta-release-candidate" in text
    assert "${{ runner.temp }}/release-candidate/*" in text
    assert "retention-days: 7" in text
    forbidden = (
        "gh release",
        "pypi",
        "twine upload",
        "analog-validation ports",
        "analog-validation observe",
        "COM4",
        "COM5",
    )
    assert all(value not in text for value in forbidden)
