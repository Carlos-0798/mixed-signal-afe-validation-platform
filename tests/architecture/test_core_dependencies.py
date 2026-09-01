"""Executable dependency boundaries for the formal product core."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parents[2] / "src" / "analog_validation"
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
