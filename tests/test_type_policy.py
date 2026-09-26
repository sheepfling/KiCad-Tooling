"""Guard typed service boundaries against unbounded ``Any`` annotations."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "kicad_tooling"


class TypeBoundaryPolicyTests(unittest.TestCase):
    def test_runtime_package_does_not_use_any(self) -> None:
        violations: list[str] = []
        for path in sorted(PACKAGE_ROOT.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                imports_any = isinstance(node, ast.ImportFrom) and any(
                    alias.name == "Any" for alias in node.names
                )
                references_any = isinstance(node, ast.Name) and node.id == "Any"
                qualified_any = isinstance(node, ast.Attribute) and node.attr == "Any"
                if imports_any or references_any or qualified_any:
                    relative = path.relative_to(PACKAGE_ROOT.parent)
                    violations.append(f"{relative}:{node.lineno}")

        self.assertEqual(
            violations,
            [],
            "Use object for untrusted values at I/O boundaries and validate them into "
            "typed contracts before passing them to services.",
        )
