"""Audit the contributor environment without opening hardware or using a network."""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

ENVIRONMENT_AUDIT_SCHEMA_VERSION = "development-environment-audit.v1"
HOSTED_PYTHON_MATRIX = {(3, 10), (3, 12), (3, 14)}
PROJECT_DISTRIBUTION = "mixed-signal-afe-validation-platform"
TK_RUNTIME_PROBE = (
    "import tkinter as tk; "
    "root = tk.Tk(); "
    "root.withdraw(); "
    "root.update_idletasks(); "
    "root.destroy()"
)

CheckStatus = Literal["PASS", "WARN", "FAIL"]
PackageProbe = Callable[[str, str], str | None]
CommandLocator = Callable[[str], str | None]
PathProbe = Callable[[Path], bool]
CommandRunner = Callable[[Sequence[str]], tuple[int, str]]


@dataclass(frozen=True)
class EnvironmentCheck:
    """One path-free required or optional environment observation."""

    check_id: str
    category: str
    required: bool
    status: CheckStatus
    detail: str
    safe_next_step: str | None = None

    def to_document(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return asdict(self)


def _package_version(module_name: str, distribution_name: str) -> str | None:
    if importlib.util.find_spec(module_name) is None:
        return None
    try:
        return importlib.metadata.version(distribution_name)
    except importlib.metadata.PackageNotFoundError:
        return "present"


def _run_command(command: Sequence[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""
    output = completed.stdout.strip() or completed.stderr.strip()
    return completed.returncode, output


def _windows_candidates(
    tool_id: str,
    environment: Mapping[str, str],
) -> tuple[Path, ...]:
    candidates: list[Path] = []
    if tool_id == "ltspice":
        local_app_data = environment.get("LOCALAPPDATA")
        if local_app_data:
            candidates.append(
                Path(local_app_data) / "Programs" / "ADI" / "LTspice" / "LTspice.exe"
            )
        candidates.extend(
            (
                Path("C:/Program Files/ADI/LTspice/LTspice.exe"),
                Path("C:/Program Files/LTC/LTspiceXVII/XVIIx64.exe"),
            )
        )
    elif tool_id == "msp430_gcc":
        ti_root = Path(environment.get("TI_ROOT", "C:/ti"))
        try:
            candidates.extend(
                sorted(ti_root.glob("msp430-gcc-*/bin/msp430-elf-gcc.exe"))
            )
        except OSError:
            pass
    return tuple(candidates)


def _locate_tool(
    command: str,
    tool_id: str,
    *,
    system: str,
    environment: Mapping[str, str],
    command_locator: CommandLocator,
    path_probe: PathProbe,
) -> tuple[str | None, str | None]:
    executable = command_locator(command)
    if executable is not None:
        return executable, "PATH"
    if system == "Windows":
        for candidate in _windows_candidates(tool_id, environment):
            if path_probe(candidate):
                return str(candidate), "known install location"
    return None, None


def _first_line(output: str) -> str:
    return output.splitlines()[0].strip() if output else "version probe completed"


def run_audit(
    *,
    python_version: tuple[int, int, int] | None = None,
    system: str | None = None,
    environment: Mapping[str, str] | None = None,
    package_probe: PackageProbe = _package_version,
    command_locator: CommandLocator = shutil.which,
    path_probe: PathProbe = Path.is_file,
    command_runner: CommandRunner = _run_command,
) -> dict[str, Any]:
    """Return a privacy-minimal, hardware-free contributor environment audit."""

    version = python_version or (
        sys.version_info.major,
        sys.version_info.minor,
        sys.version_info.micro,
    )
    host_system = system or platform.system()
    host_environment = environment or os.environ
    checks: list[EnvironmentCheck] = []

    minimum_ok = version >= (3, 10, 0)
    checks.append(
        EnvironmentCheck(
            "python.minimum",
            "python",
            True,
            "PASS" if minimum_ok else "FAIL",
            f"Python {version[0]}.{version[1]}.{version[2]}; project requires 3.10 or newer.",
            None if minimum_ok else "Install 64-bit Python 3.12 from python.org.",
        )
    )
    matrix_verified = version[:2] in HOSTED_PYTHON_MATRIX
    checks.append(
        EnvironmentCheck(
            "python.hosted-matrix",
            "python",
            False,
            "PASS" if matrix_verified else "WARN",
            (
                "This Python minor is in the hosted Windows/Ubuntu matrix."
                if matrix_verified
                else "This Python minor meets metadata requirements but is outside the hosted matrix."
            ),
            None if matrix_verified else "Prefer Python 3.12 for local release verification.",
        )
    )

    required_packages = (
        ("package.core", "analog_validation", PROJECT_DISTRIBUTION),
        ("package.product", "analog_validation_app", PROJECT_DISTRIBUTION),
        ("package.pytest", "pytest", "pytest"),
        ("package.pytest-cov", "pytest_cov", "pytest-cov"),
        ("package.ruff", "ruff", "ruff"),
        ("package.mypy", "mypy", "mypy"),
        ("package.build", "build", "build"),
    )
    for check_id, module_name, distribution_name in required_packages:
        installed_version = package_probe(module_name, distribution_name)
        present = installed_version is not None
        checks.append(
            EnvironmentCheck(
                check_id,
                "python-package",
                True,
                "PASS" if present else "FAIL",
                (
                    f"{distribution_name} ({installed_version}) is available."
                    if present
                    else f"{distribution_name} is not available in this interpreter."
                ),
                None if present else 'Install the repository with the "dev" extra.',
            )
        )

    optional_presence: dict[str, bool] = {}
    for check_id, module_name, distribution_name, next_step in (
        (
            "optional.pyserial-backend",
            "analog_validation_pyserial",
            PROJECT_DISTRIBUTION,
            'Install the repository with the "serial" extra before approved real-port work.',
        ),
        (
            "optional.pyserial",
            "serial",
            "pyserial",
            'Install the repository with the "serial" extra before approved real-port work.',
        ),
        (
            "optional.tk",
            "tkinter",
            "tk",
            "Install a Python build that includes Tcl/Tk to use the optional Dashboard.",
        ),
    ):
        installed_version = package_probe(module_name, distribution_name)
        present = installed_version is not None
        optional_presence[check_id] = present
        checks.append(
            EnvironmentCheck(
                check_id,
                "optional-python",
                False,
                "PASS" if present else "WARN",
                (
                    f"{distribution_name} ({installed_version}) is available."
                    if present
                    else f"{distribution_name} is not installed; the base product remains usable."
                ),
                None if present else next_step,
            )
        )

    tk_runtime_code = 127
    if optional_presence["optional.tk"]:
        tk_runtime_code, _ = command_runner((sys.executable, "-c", TK_RUNTIME_PROBE))
    tk_runtime_ready = tk_runtime_code == 0
    checks.append(
        EnvironmentCheck(
            "optional.tk-runtime",
            "optional-python",
            False,
            "PASS" if tk_runtime_ready else "WARN",
            (
                "Tk created, hid, and closed a local root window successfully."
                if tk_runtime_ready
                else "Tk is unavailable or could not complete a local root-window smoke."
            ),
            (
                None
                if tk_runtime_ready
                else "Repair Tcl/Tk or record Dashboard as NOT_RUN; the CLI remains supported."
            ),
        )
    )

    pip_code, _ = command_runner((sys.executable, "-m", "pip", "check"))
    checks.append(
        EnvironmentCheck(
            "python.pip-check",
            "python-package",
            True,
            "PASS" if pip_code == 0 else "FAIL",
            (
                "pip reports no broken requirements."
                if pip_code == 0
                else "pip reported a dependency consistency problem."
            ),
            None if pip_code == 0 else "Recreate the short-path virtual environment.",
        )
    )

    located_tools: dict[str, str | None] = {}
    for tool_id, command, required, description, next_step in (
        (
            "git",
            "git",
            True,
            "Git is available for source and worktree operations.",
            "Install Git for Windows or the platform Git package.",
        ),
        (
            "gh",
            "gh",
            False,
            "GitHub CLI is available for explicitly approved remote work.",
            "Install GitHub CLI only if remote repository operations are needed.",
        ),
        (
            "vscode",
            "code",
            False,
            "Visual Studio Code is available.",
            "Install VS Code only if a graphical editor is wanted.",
        ),
        (
            "ltspice",
            "LTspice.exe",
            False,
            "LTspice is available for explicitly labeled SPICE simulation.",
            "Install LTspice only when local circuit simulation is needed.",
        ),
        (
            "msp430_gcc",
            "msp430-elf-gcc.exe",
            False,
            "MSP430 GCC is available for the separate controller toolchain.",
            "Install a reviewed MSP430 toolchain only before firmware work.",
        ),
    ):
        executable, source = _locate_tool(
            command,
            tool_id,
            system=host_system,
            environment=host_environment,
            command_locator=command_locator,
            path_probe=path_probe,
        )
        located_tools[tool_id] = executable
        present = executable is not None
        version_detail = ""
        if executable is not None and tool_id in {"git", "gh", "msp430_gcc"}:
            code, output = command_runner((executable, "--version"))
            if code == 0:
                version_detail = f" {_first_line(output)}"
        checks.append(
            EnvironmentCheck(
                f"tool.{tool_id}",
                "host-tool",
                required,
                "PASS" if present else ("FAIL" if required else "WARN"),
                (
                    f"{description} Detection: {source}.{version_detail}"
                    if present
                    else f"{tool_id} was not detected; it is {'required' if required else 'optional'}."
                ),
                None if present else next_step,
            )
        )

    vscode = located_tools["vscode"]
    if vscode is not None:
        code, output = command_runner((vscode, "--list-extensions"))
        installed_extensions = {line.strip().lower() for line in output.splitlines()}
        for extension in (
            "ms-python.python",
            "ms-python.vscode-pylance",
            "charliermarsh.ruff",
        ):
            present = code == 0 and extension in installed_extensions
            checks.append(
                EnvironmentCheck(
                    f"vscode.{extension}",
                    "editor-extension",
                    False,
                    "PASS" if present else "WARN",
                    (
                        f"VS Code extension {extension} is installed."
                        if present
                        else f"VS Code extension {extension} was not detected."
                    ),
                    None if present else f"Install the recommended extension {extension}.",
                )
            )

    required_checks = [check for check in checks if check.required]
    overall_ready = all(check.status == "PASS" for check in required_checks)
    return {
        "schema_version": ENVIRONMENT_AUDIT_SCHEMA_VERSION,
        "scope": "HOST_DEVELOPMENT_ENVIRONMENT",
        "overall_ready": overall_ready,
        "platform": {
            "system": host_system,
            "release": platform.release(),
            "machine": platform.machine(),
            "python": f"{version[0]}.{version[1]}.{version[2]}",
        },
        "summary": {
            "pass": sum(check.status == "PASS" for check in checks),
            "warn": sum(check.status == "WARN" for check in checks),
            "fail": sum(check.status == "FAIL" for check in checks),
            "required": len(required_checks),
        },
        "checks": [check.to_document() for check in checks],
        "safety": {
            "network_accessed": False,
            "serial_ports_enumerated": False,
            "serial_ports_opened": 0,
            "device_writes": 0,
            "hardware_validation": False,
        },
        "limitations": (
            "Tool presence does not validate an AFE, controller firmware, wiring, or instruments.",
            "Optional tool detection does not add the tool to global PATH.",
            "Python 3.10 and 3.14 compatibility is primarily covered by hosted CI; 3.12 is recommended locally.",
        ),
    }


def _render_human(document: Mapping[str, Any]) -> str:
    lines = [
        "Development environment: "
        + ("READY" if document["overall_ready"] else "NOT READY")
    ]
    for check in document["checks"]:
        required = "required" if check["required"] else "optional"
        lines.append(
            f"[{check['status']}] {check['check_id']} ({required}): {check['detail']}"
        )
        if check["safe_next_step"]:
            lines.append(f"  Next: {check['safe_next_step']}")
    lines.append(
        "Safety: no network access, serial enumeration/open, device write, or hardware validation."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit required and optional development tools without touching hardware."
    )
    parser.add_argument("--json", action="store_true", help="emit structured JSON")
    args = parser.parse_args(argv)
    document = run_audit()
    if args.json:
        print(json.dumps(document, indent=2, sort_keys=True))
    else:
        print(_render_human(document))
    return 0 if document["overall_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
