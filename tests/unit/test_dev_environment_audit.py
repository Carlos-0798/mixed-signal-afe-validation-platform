from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest

import tools.dev_environment_audit as audit_module
from tools.dev_environment_audit import _render_human, run_audit


def _ready_package_probe(module_name: str, distribution_name: str) -> str | None:
    versions = {
        "analog_validation": "0.1.0b1",
        "analog_validation_app": "0.1.0b1",
        "analog_validation_pyserial": "0.1.0b1",
        "pytest": "8.4.2",
        "pytest_cov": "7.1.0",
        "ruff": "0.16.5",
        "mypy": "2.3.1",
        "build": "1.6.0",
        "serial": "3.5",
        "tkinter": "8.6",
    }
    del distribution_name
    return versions.get(module_name)


def _ready_locator(command: str) -> str | None:
    return {
        "git": "git",
        "gh": "gh",
        "code": "code",
        "LTspice.exe": "LTspice.exe",
        "msp430-elf-gcc.exe": "msp430-elf-gcc.exe",
    }.get(command)


def _ready_runner(command: Sequence[str]) -> tuple[int, str]:
    if tuple(command[-2:]) == ("pip", "check"):
        return 0, "No broken requirements found."
    if command[-1] == "--list-extensions":
        return 0, "ms-python.python\nms-python.vscode-pylance\ncharliermarsh.ruff"
    return 0, f"{Path(command[0]).name} test-version"


def test_ready_environment_is_path_free_and_hardware_free() -> None:
    document = run_audit(
        python_version=(3, 12, 10),
        system="Windows",
        environment={"LOCALAPPDATA": "X:/fixture-profile/LocalAppData"},
        package_probe=_ready_package_probe,
        command_locator=_ready_locator,
        path_probe=lambda _path: False,
        command_runner=_ready_runner,
    )

    serialized = json.dumps(document)
    assert document["overall_ready"] is True
    assert document["summary"] == {"pass": 22, "warn": 0, "fail": 0, "required": 10}
    assert "X:/fixture-profile" not in serialized
    assert document["safety"] == {
        "network_accessed": False,
        "serial_ports_enumerated": False,
        "serial_ports_opened": 0,
        "device_writes": 0,
        "hardware_validation": False,
    }


def test_missing_required_package_and_failed_pip_check_block_readiness() -> None:
    def missing_pytest(module_name: str, distribution_name: str) -> str | None:
        if module_name == "pytest":
            return None
        return _ready_package_probe(module_name, distribution_name)

    def failed_pip(command: Sequence[str]) -> tuple[int, str]:
        if tuple(command[-2:]) == ("pip", "check"):
            return 1, "dependency problem with a private path"
        return _ready_runner(command)

    document = run_audit(
        python_version=(3, 12, 10),
        system="Windows",
        environment={},
        package_probe=missing_pytest,
        command_locator=_ready_locator,
        path_probe=lambda _path: False,
        command_runner=failed_pip,
    )

    failures = {
        check["check_id"] for check in document["checks"] if check["status"] == "FAIL"
    }
    assert document["overall_ready"] is False
    assert failures == {"package.pytest", "python.pip-check"}
    assert "private path" not in json.dumps(document)


def test_optional_absence_and_unverified_minor_only_warn() -> None:
    def base_only_probe(module_name: str, distribution_name: str) -> str | None:
        if module_name in {"analog_validation_pyserial", "serial", "tkinter"}:
            return None
        return _ready_package_probe(module_name, distribution_name)

    document = run_audit(
        python_version=(3, 13, 7),
        system="Linux",
        environment={},
        package_probe=base_only_probe,
        command_locator=lambda command: "git" if command == "git" else None,
        path_probe=lambda _path: False,
        command_runner=_ready_runner,
    )

    warning_ids = {
        check["check_id"] for check in document["checks"] if check["status"] == "WARN"
    }
    assert document["overall_ready"] is True
    assert {
        "python.hosted-matrix",
        "optional.pyserial-backend",
        "optional.pyserial",
        "optional.tk",
        "optional.tk-runtime",
        "tool.gh",
        "tool.vscode",
        "tool.ltspice",
        "tool.msp430_gcc",
    } <= warning_ids


def test_windows_known_install_location_is_detected_without_path_disclosure() -> None:
    def path_probe(path: Path) -> bool:
        normalized = path.as_posix().lower()
        return normalized.endswith(
            (
                "/programs/adi/ltspice/ltspice.exe",
                "/msp430-gcc-9.3.1.2/bin/msp430-elf-gcc.exe",
            )
        )

    document = run_audit(
        python_version=(3, 12, 10),
        system="Windows",
        environment={
            "LOCALAPPDATA": "X:/fixture-profile/LocalAppData",
            "TI_ROOT": "C:/ti",
        },
        package_probe=_ready_package_probe,
        command_locator=lambda command: command if command in {"git", "gh"} else None,
        path_probe=path_probe,
        command_runner=_ready_runner,
    )

    checks = {check["check_id"]: check for check in document["checks"]}
    assert checks["tool.ltspice"]["status"] == "PASS"
    assert checks["tool.msp430_gcc"]["status"] == "PASS"
    assert "known install location" in checks["tool.ltspice"]["detail"]
    assert "X:/fixture-profile" not in json.dumps(document)


def test_tk_runtime_failure_is_optional_and_redacted() -> None:
    def tk_failure_runner(command: Sequence[str]) -> tuple[int, str]:
        if "-c" in command:
            return 1, "Tk error below X:/fixture-profile"
        return _ready_runner(command)

    document = run_audit(
        python_version=(3, 12, 10),
        system="Windows",
        environment={},
        package_probe=_ready_package_probe,
        command_locator=_ready_locator,
        path_probe=lambda _path: False,
        command_runner=tk_failure_runner,
    )

    checks = {check["check_id"]: check for check in document["checks"]}
    assert document["overall_ready"] is True
    assert checks["optional.tk-runtime"]["status"] == "WARN"
    assert "X:/fixture-profile" not in json.dumps(document)


def test_human_render_and_cli_exit_codes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ready = run_audit(
        python_version=(3, 12, 10),
        system="Windows",
        environment={},
        package_probe=_ready_package_probe,
        command_locator=_ready_locator,
        path_probe=lambda _path: False,
        command_runner=_ready_runner,
    )
    assert "Development environment: READY" in _render_human(ready)
    assert "no network access" in _render_human(ready)

    monkeypatch.setattr(audit_module, "run_audit", lambda: ready)
    assert audit_module.main(["--json"]) == 0
    json_output = json.loads(capsys.readouterr().out)
    assert json_output["schema_version"] == "development-environment-audit.v1"

    blocked = dict(ready)
    blocked["overall_ready"] = False
    monkeypatch.setattr(audit_module, "run_audit", lambda: blocked)
    assert audit_module.main([]) == 2
    assert "Development environment: NOT READY" in capsys.readouterr().out
