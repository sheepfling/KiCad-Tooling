"""Guard the typed route for source-reviewed connector comparison scopes."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo.connector_comparison_scope_types import (
    ConnectorComparisonScope,
    connector_comparison_scopes_by_reference,
)
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.architecture,
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
]


def test_scope_record_names_group_and_review_basis_and_freezes_reference_index() -> None:
    scope = ConnectorComparisonScope(group="usb-a", basis="Reviewed USB A")
    scopes = connector_comparison_scopes_by_reference({"J1": scope})

    assert scope.group == "usb-a"
    assert scope.basis == "Reviewed USB A"
    assert dict(scopes) == {"j1": scope}
    with pytest.raises(TypeError):
        scopes["j2"] = scope  # type: ignore[index]
    with pytest.raises(ValueError, match="references must be unique"):
        connector_comparison_scopes_by_reference(
            {"J1": scope, "j1": ConnectorComparisonScope("usb-b", "Reviewed USB B")}
        )


def test_connector_scope_consumers_do_not_reintroduce_tuple_payloads() -> None:
    scope_arguments = {
        "peer_assignment_groups",
        "return_comparison_groups",
        "supply_comparison_groups",
    }
    checked_arguments = 0
    for path in HWREPO.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                if argument.arg not in scope_arguments:
                    continue
                checked_arguments += 1
                assert argument.annotation is not None
                assert "ConnectorComparisonScopes" in ast.unparse(argument.annotation)
                assert "tuple[str, str]" not in ast.unparse(argument.annotation)

    assert checked_arguments >= 15


def test_scope_record_stays_in_its_theme_owned_module() -> None:
    path = HWREPO / "connector_comparison_scope_types.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)

    assert line_count(path) < IMPLEMENTATION_MAX_LINES
    scope = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ConnectorComparisonScope"
    )
    fields = {
        node.target.id
        for node in scope.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert fields == {"group", "basis"}


def test_public_connector_facade_is_the_only_legacy_tuple_adapter() -> None:
    path = HWREPO / "connector_pins.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    aliases = {
        node.target.id: ast.unparse(node.value)
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.value is not None
    }

    assert line_count(path) < 220
    assert "tuple[str, str]" in aliases["ConnectorComparisonScopeInputValue"]
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "_typed_comparison_scopes"
        for node in tree.body
    )
