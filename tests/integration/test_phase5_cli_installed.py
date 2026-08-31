from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

CONSOLE_SCRIPT = Path(sys.executable).with_name("analog-validation.exe")
INTERRUPT_PROBE = Path(__file__).parents[1] / "support" / "cli_interrupt_probe.py"
SOURCE_ROOT = Path(__file__).parents[2] / "src"
BASE_PYTHON = Path(getattr(sys, "_base_executable", sys.executable))


def run_module(*arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "analog_validation_app", *arguments],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )


def test_installed_module_runs_outside_repository_without_traceback(
    tmp_path: Path,
) -> None:
    completed = run_module("simulate", "read", "--samples", "2", "--json", cwd=tmp_path)

    assert completed.returncode == 0
    assert completed.stderr == ""
    document = json.loads(completed.stdout)
    assert document["result"]["status"] == "COMPLETED"
    assert document["result"]["evidence_source"] == "SYNTHETIC"
    assert document["hardware_claim"] == "NO_PERFORMANCE_VALIDATION"


def test_installed_module_invalid_command_has_stable_usage_exit(
    tmp_path: Path,
) -> None:
    completed = run_module("unknown", cwd=tmp_path)

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "INVALID_REQUEST" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_installed_module_builds_self_contained_report_outside_repository(
    tmp_path: Path,
) -> None:
    result_path = tmp_path / "result.json"
    report_path = tmp_path / "human-report"
    generated = run_module(
        "simulate",
        "dc",
        "--points",
        "6",
        "--output",
        str(result_path),
        "--json",
        cwd=tmp_path,
    )
    assert generated.returncode == 0

    completed = run_module(
        "report",
        "--input",
        str(result_path),
        "--output",
        str(report_path),
        "--json",
        cwd=tmp_path,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    document = json.loads(completed.stdout)
    assert document["command"] == "report"
    assert document["evidence_source"] == "SYNTHETIC"
    assert document["hardware_claim"] == "NO_NEW_HARDWARE_VALIDATION"
    assert {path.name for path in report_path.iterdir()} == {
        "report.txt",
        "report.md",
        "report.html",
        "chart.svg",
        "manifest.json",
    }
    html = (report_path / "report.html").read_text(encoding="utf-8")
    assert "<script" not in html.lower()
    assert "src=" not in html.lower()


@pytest.mark.skipif(
    sys.platform != "win32" or not CONSOLE_SCRIPT.is_file(),
    reason="Windows console script is verified after an installed build",
)
def test_installed_console_script_runs_from_external_directory(tmp_path: Path) -> None:
    completed = subprocess.run(
        [str(CONSOLE_SCRIPT), "version", "--json"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert json.loads(completed.stdout)["command"] == "version"


def test_cli_subprocess_keyboard_interrupt_cancels_and_cleans_up(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "interrupt-probe.state"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(SOURCE_ROOT), environment.get("PYTHONPATH", "")) if part
    )
    completed = subprocess.run(
        [str(BASE_PYTHON), str(INTERRUPT_PROBE), str(marker)],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )

    assert completed.returncode == 130
    assert completed.stderr == ""
    document = json.loads(completed.stdout)
    assert document["worker"]["state"] == "CANCELLED"
    assert document["worker"]["interrupted"] is True
    assert document["hardware_claim"] == "NO_PERFORMANCE_VALIDATION"
    assert marker.with_suffix(".cleaned").read_text(encoding="utf-8") == "CLEANED\n"
