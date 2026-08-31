"""One-way boundaries for the Phase 5 product shell."""

from __future__ import annotations

import ast
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[2]
CORE_ROOT = ROOT / "src" / "analog_validation"
PYSERIAL_ROOT = ROOT / "src" / "analog_validation_pyserial"
APP_ROOT = ROOT / "src" / "analog_validation_app"


def _absolute_imports(root: Path) -> set[str]:
    imports: set[str] = set()
    paths = (root,) if root.is_file() else tuple(root.rglob("*.py"))
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(item.name for item in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imports.add(node.module)
    return imports


def _imports_prefix(imports: set[str], prefix: str) -> bool:
    return any(
        imported == prefix or imported.startswith(f"{prefix}.")
        for imported in imports
    )


def test_lower_layers_do_not_import_the_product_shell() -> None:
    assert not _imports_prefix(_absolute_imports(CORE_ROOT), "analog_validation_app")
    assert not _imports_prefix(
        _absolute_imports(PYSERIAL_ROOT), "analog_validation_app"
    )


def test_step1_product_shell_has_no_gui_driver_or_legacy_runtime_imports() -> None:
    imports = _absolute_imports(APP_ROOT)
    forbidden = (
        "dashboard",
        "tools",
        "tkinter",
        "serial",
        "analog_validation_pyserial",
    )

    assert all(not _imports_prefix(imports, prefix) for prefix in forbidden)


def test_product_shell_does_not_own_protocol_or_analysis_implementations() -> None:
    forbidden_files = {
        "protocol.py",
        "crc.py",
        "dc_sweep.py",
        "hysteresis.py",
        "calibration.py",
        "frequency_response.py",
        "serial_worker.py",
    }
    assert not {path.name for path in APP_ROOT.rglob("*.py")} & forbidden_files


def test_product_worker_is_generic_orchestration_not_device_or_analysis_code() -> None:
    imports = _absolute_imports(APP_ROOT / "worker.py")
    forbidden = (
        "analog_validation.adapters",
        "analog_validation.analysis",
        "analog_validation.exports",
        "analog_validation.profiles",
        "analog_validation.protocol",
        "analog_validation.replay",
        "analog_validation.runners",
        "analog_validation.serial_adapters",
        "analog_validation.transport",
        "analog_validation.workflows",
        "analog_validation_pyserial",
        "tkinter",
    )

    assert all(not _imports_prefix(imports, prefix) for prefix in forbidden)


def test_superseded_phase0_dashboard_and_legacy_tests_are_absent() -> None:
    assert not tuple((ROOT / "dashboard").rglob("*.py"))
    assert not (ROOT / "tests" / "test_dc_sweep.py").exists()
    assert not (ROOT / "tests" / "test_hysteresis.py").exists()


def test_console_script_uses_the_product_cli_without_a_second_entrypoint() -> None:
    document = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert document["project"]["scripts"] == {
        "analog-validation": "analog_validation_app.cli:main"
    }
