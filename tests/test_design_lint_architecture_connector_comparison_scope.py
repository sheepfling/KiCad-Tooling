"""Guard the typed route for source-reviewed connector comparison scopes."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import connector_peer_pin_compat, connector_pins
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


def test_public_connector_facade_reexports_the_scoped_compatibility_adapter() -> None:
    facade = HWREPO / "connector_pins.py"
    adapter = HWREPO / "connector_peer_pin_compat.py"
    tree = ast.parse(adapter.read_text(encoding="utf-8"), filename=adapter.name)
    aliases = {
        node.target.id: ast.unparse(node.value)
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.value is not None
    }

    assert line_count(facade) < 100
    assert line_count(adapter) < IMPLEMENTATION_MAX_LINES
    assert "tuple[str, str]" in aliases["ConnectorComparisonScopeInputValue"]
    assert any(
        isinstance(node, ast.FunctionDef) and node.name == "_typed_comparison_scopes"
        for node in tree.body
    )
    facade_tree = ast.parse(facade.read_text(encoding="utf-8"), filename=facade.name)
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "connector_peer_pin_compat"
        and any(alias.name == "similar_connector_pin_groups" for alias in node.names)
        for node in facade_tree.body
    )
    for name in (
        "similar_connector_pin_groups",
        "connector_peer_pin_assignment_divergences",
        "connector_peer_pin_assignment_outliers",
        "connector_peer_pin_heuristic_coverage",
    ):
        assert getattr(connector_pins, name) is getattr(connector_peer_pin_compat, name)


def test_internal_connector_services_import_the_theme_owner_directly() -> None:
    service_paths = (
        HWREPO / "native_report_parsing.py",
        HWREPO.parent / "ci_hosted_connector_inventory.py",
    )
    for path in service_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        imports = {
            (node.level, node.module) for node in tree.body if isinstance(node, ast.ImportFrom)
        }
        assert not any(module.endswith("connector_pins") for _, module in imports if module)
        assert any(module.endswith("connector_identity") for _, module in imports if module)
