"""Installation and public-package tests."""

from __future__ import annotations

import subprocess
import sys
from importlib.metadata import metadata, version
from pathlib import Path

import analog_validation


def test_public_version_matches_distribution_metadata() -> None:
    assert analog_validation.__version__ == "0.1.0b1"
    assert analog_validation.__version__ == version(
        "mixed-signal-afe-validation-platform"
    )


def test_distribution_metadata_describes_beta_without_inventing_a_license() -> None:
    document = metadata("mixed-signal-afe-validation-platform")
    classifiers = set(document.get_all("Classifier") or ())
    project_urls = set(document.get_all("Project-URL") or ())

    assert document["Name"] == "mixed-signal-afe-validation-platform"
    assert document["Version"] == analog_validation.__version__
    assert document["Summary"] == (
        "Controller-neutral analog front-end validation and test automation software"
    )
    assert document["Author"] == "Carlos-0798"
    assert "Development Status :: 4 - Beta" in classifiers
    assert "Programming Language :: Python :: 3.10" in classifiers
    assert "Programming Language :: Python :: 3.12" in classifiers
    assert "Programming Language :: Python :: 3.14" in classifiers
    assert project_urls == {
        "Repository, https://github.com/Carlos-0798/mixed-signal-afe-validation-platform",
        "Documentation, https://github.com/Carlos-0798/mixed-signal-afe-validation-platform/tree/main/docs",
        "Issues, https://github.com/Carlos-0798/mixed-signal-afe-validation-platform/issues",
    }
    assert not document.get("Author-email")
    assert not document.get("License")
    assert not any(value.startswith("License ::") for value in classifiers)


def test_installed_package_imports_outside_repository(tmp_path: Path) -> None:
    command = [
        sys.executable,
        "-c",
        "import analog_validation; print(analog_validation.__version__)",
    ]

    completed = subprocess.run(
        command,
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == analog_validation.__version__
