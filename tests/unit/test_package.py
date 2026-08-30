"""Installation and public-package tests."""

from __future__ import annotations

import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import analog_validation


def test_public_version_matches_distribution_metadata() -> None:
    assert analog_validation.__version__ == version(
        "mixed-signal-afe-validation-platform"
    )


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
