"""Freeze the public-only and no-output boundaries of the extension example."""

from __future__ import annotations

import ast
from pathlib import Path

import analog_validation

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "public_adapter" / "read_only_voltage_adapter.py"
DOC = ROOT / "docs" / "PUBLIC_ADAPTER_EXAMPLE.md"


def _tree() -> ast.Module:
    return ast.parse(EXAMPLE.read_text(encoding="utf-8"), filename=str(EXAMPLE))


def test_example_imports_only_the_installed_top_level_public_api() -> None:
    tree = _tree()
    imported_public_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                not alias.name.startswith("analog_validation")
                for alias in node.names
            )
        if (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.startswith("analog_validation")
        ):
            assert node.module == "analog_validation"
            imported_public_names.update(alias.name for alias in node.names)

    assert imported_public_names
    assert imported_public_names <= set(analog_validation.__all__)


def test_example_declares_no_output_implementation_or_private_dependency() -> None:
    tree = _tree()
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    adapter = next(node for node in classes if node.name == "ReadOnlyVoltageAdapter")
    methods = {
        node.name for node in adapter.body if isinstance(node, ast.FunctionDef)
    }

    assert {"_connect", "_disconnect", "_get_capabilities", "_read_measurement"} <= methods
    assert methods.isdisjoint({"_set_stimulus", "_run_command", "_safe_shutdown"})
    source = EXAMPLE.read_text(encoding="utf-8")
    for forbidden in (
        "analog_validation.",
        "analog_validation_app",
        "analog_validation_pyserial",
        "pyserial",
        "serial",
        "socket",
        "subprocess",
    ):
        assert forbidden not in source


def test_example_document_explains_lifecycle_evidence_and_external_wheel_gate() -> None:
    document = DOC.read_text(encoding="utf-8")

    for required in (
        "connect()",
        "get_capabilities()",
        "read_measurement()",
        "disconnect()",
        "COMPLETED",
        "SYNTHETIC",
        "application_bytes_written = 0",
        "outside the repository",
        "isolated mode (`-I`)",
        "does not authorize hardware",
    ):
        assert required in document
