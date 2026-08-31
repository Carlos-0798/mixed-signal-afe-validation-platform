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
        imported == prefix or imported.startswith(f"{prefix}.") for imported in imports
    )


def test_lower_layers_do_not_import_the_product_shell() -> None:
    assert not _imports_prefix(_absolute_imports(CORE_ROOT), "analog_validation_app")
    assert not _imports_prefix(
        _absolute_imports(PYSERIAL_ROOT), "analog_validation_app"
    )


def test_base_product_shell_has_no_gui_driver_or_legacy_runtime_imports() -> None:
    imports: set[str] = set()
    for path in APP_ROOT.glob("*.py"):
        imports.update(_absolute_imports(path))
    forbidden = (
        "tools",
        "tkinter",
        "serial",
        "analog_validation_pyserial",
    )

    assert all(not _imports_prefix(imports, prefix) for prefix in forbidden)


def test_headless_dashboard_contracts_have_no_tk_network_or_device_runtime() -> None:
    dashboard_root = APP_ROOT / "dashboard"
    imports = set()
    for name in ("__init__.py", "state.py", "presenter.py", "controller.py"):
        imports.update(_absolute_imports(dashboard_root / name))
    forbidden = (
        "analog_validation.adapters",
        "analog_validation.analysis",
        "analog_validation.protocol",
        "analog_validation.runners",
        "analog_validation.serial_adapters",
        "analog_validation.transport",
        "analog_validation.workflows",
        "analog_validation_pyserial",
        "http",
        "requests",
        "serial",
        "socket",
        "tkinter",
        "urllib",
    )

    assert all(not _imports_prefix(imports, prefix) for prefix in forbidden)


def test_tkinter_exists_only_inside_the_explicit_dashboard_app_boundary() -> None:
    tkinter_importers = {
        path.relative_to(APP_ROOT).as_posix()
        for path in APP_ROOT.rglob("*.py")
        if _imports_prefix(_absolute_imports(path), "tkinter")
    }

    assert tkinter_importers == {"dashboard/app.py"}


def test_dashboard_widgets_do_not_own_worker_analysis_or_resource_code() -> None:
    source = (APP_ROOT / "dashboard" / "widgets.py").read_text(encoding="utf-8")
    forbidden = (
        "ProductJobWorker",
        "make_serial_adapter",
        "open(",
        "socket",
        "subprocess",
        "urllib",
    )

    assert all(value not in source for value in forbidden)


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


def test_reporting_is_presentation_only_and_has_no_network_or_analysis_imports() -> (
    None
):
    imports = _absolute_imports(APP_ROOT / "reporting.py") | _absolute_imports(
        APP_ROOT / "presentation.py"
    )
    forbidden = (
        "analog_validation.adapters",
        "analog_validation.analysis",
        "analog_validation.profiles",
        "analog_validation.protocol",
        "analog_validation.runners",
        "analog_validation.serial_adapters",
        "analog_validation.transport",
        "analog_validation.workflows",
        "analog_validation_pyserial",
        "http",
        "requests",
        "socket",
        "tkinter",
        "urllib",
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
