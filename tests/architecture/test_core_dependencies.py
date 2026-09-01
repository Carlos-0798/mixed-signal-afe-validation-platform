"""Executable dependency boundaries for the formal product core."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parents[2] / "src" / "analog_validation"
PYSERIAL_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "analog_validation_pyserial"
)
REPOSITORY_ROOT = CORE_ROOT.parents[1]


def test_formal_core_uses_only_stdlib_and_its_own_package() -> None:
    unexpected: list[str] = []
    for path in sorted(CORE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {item.name.partition(".")[0] for item in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = {node.module.partition(".")[0]}
            else:
                continue
            for root in roots:
                if root != "analog_validation" and root not in sys.stdlib_module_names:
                    unexpected.append(f"{path.relative_to(REPOSITORY_ROOT)} -> {root}")
    assert unexpected == []


def test_retired_phase0_protocol_and_shared_models_are_absent() -> None:
    assert not (REPOSITORY_ROOT / "dashboard" / "protocol.py").exists()
    assert not (REPOSITORY_ROOT / "dashboard" / "models.py").exists()


def _absolute_imports(root: Path) -> set[str]:
    imports: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(item.name for item in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imports.add(node.module)
    return imports


def test_transport_and_profile_dependency_direction_is_one_way() -> None:
    transport_imports = _absolute_imports(CORE_ROOT / "transport")
    profile_imports = _absolute_imports(CORE_ROOT / "profiles")
    forbidden_transport = (
        "analog_validation.profiles",
        "analog_validation.adapters",
        "analog_validation.analysis",
        "analog_validation.runners",
        "analog_validation.workflows",
    )
    forbidden_profiles = (
        "analog_validation.adapters",
        "analog_validation.analysis",
        "analog_validation.runners",
        "analog_validation.workflows",
    )

    assert not any(
        imported == prefix or imported.startswith(f"{prefix}.")
        for imported in transport_imports
        for prefix in forbidden_transport
    )
    assert not any(
        imported == prefix or imported.startswith(f"{prefix}.")
        for imported in profile_imports
        for prefix in forbidden_profiles
    )


def test_serial_adapter_dependency_direction_stays_below_product_workflows() -> None:
    imports = _absolute_imports(CORE_ROOT / "serial_adapters")
    forbidden = (
        "analog_validation.analysis",
        "analog_validation.exports",
        "analog_validation.runners",
        "analog_validation.workflows",
        "dashboard",
        "serial",
    )

    assert not any(
        imported == prefix or imported.startswith(f"{prefix}.")
        for imported in imports
        for prefix in forbidden
    )


def test_msp430_interoperability_uses_no_peer_runtime_namespace() -> None:
    modules = (
        CORE_ROOT / "protocol" / "msp430_health_v1.py",
        CORE_ROOT / "profiles" / "msp430_health_v1.py",
    )
    imports = set().union(*(_absolute_imports(path.parent) for path in modules))
    peer_roots = ("dashboard", "firmware", "tools")

    assert all(
        imported != root and not imported.startswith(f"{root}.")
        for imported in imports
        for root in peer_roots
    )


def test_optional_pyserial_backend_stays_below_product_workflows() -> None:
    imports = _absolute_imports(PYSERIAL_ROOT)
    forbidden = (
        "analog_validation.adapters",
        "analog_validation.analysis",
        "analog_validation.exports",
        "analog_validation.profiles",
        "analog_validation.runners",
        "analog_validation.serial_adapters",
        "analog_validation.workflows",
        "dashboard",
        "tools",
    )

    assert not any(
        imported == prefix or imported.startswith(f"{prefix}.")
        for imported in imports
        for prefix in forbidden
    )
