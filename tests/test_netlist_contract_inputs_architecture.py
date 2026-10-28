"""Keep netlist input normalization outside the shrinking model registry."""

from __future__ import annotations

import ast

import pytest

from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = pytest.mark.architecture


def test_netlist_input_owner_is_small_and_independent_of_model_registry() -> None:
    owner_path = REPO_ROOT / "kicad_tooling/hwrepo/netlist_contract_inputs.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "normalize_native_unconnected_nets"
        for node in owner_tree.body
    )
    assert not any(
        isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.endswith("models")
        for node in owner_tree.body
    )


def test_model_registry_delegates_netlist_input_normalization() -> None:
    registry = ast.parse((REPO_ROOT / "kicad_tooling/hwrepo/models.py").read_text(encoding="utf-8"))
    netlist = next(
        node
        for node in registry.body
        if isinstance(node, ast.ClassDef) and node.name == "NetlistContract"
    )
    validator = next(
        node
        for node in netlist.body
        if isinstance(node, ast.FunctionDef) and node.name == "separate_native_unconnected_nets"
    )
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "netlist_contract_inputs"
        and any(alias.name == "normalize_native_unconnected_nets" for alias in node.names)
        for node in registry.body
    )
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "normalize_native_unconnected_nets"
        for node in ast.walk(validator)
    )
