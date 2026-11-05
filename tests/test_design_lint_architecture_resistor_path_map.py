"""Guard the named immutable result contract for resistor-path services."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
]


def test_resistor_path_services_share_the_named_map_contract() -> None:
    owner = HWREPO / "resistor_paths.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert {
        name: ast.unparse(function.returns)
        for name, function in functions.items()
        if name in {"visible_resistor_paths", "visible_resistor_pullups"}
    } == {
        "visible_resistor_paths": "VisibleResistorPathsByNet",
        "visible_resistor_pullups": "VisibleResistorPathsByNet",
    }
