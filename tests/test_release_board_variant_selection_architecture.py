"""Guard the release board-variant owner and source-freshness route."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import release, release_board_variant_selection, releasing

pytestmark = pytest.mark.architecture


_ROOT = Path(__file__).parents[1]


def _tree(module: object) -> ast.Module:
    return ast.parse(Path(module.__file__).read_text(encoding="utf-8"))


def _calls(node: ast.AST) -> set[str]:
    return {
        call.func.id if isinstance(call.func, ast.Name) else call.func.attr
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and isinstance(call.func, (ast.Name, ast.Attribute))
    }


def test_release_board_variant_contract_has_one_small_owner() -> None:
    owner_path = Path(release_board_variant_selection.__file__)
    owner = _tree(release_board_variant_selection)
    assert len(owner_path.read_text(encoding="utf-8").splitlines()) < 500
    assert {
        "ReleaseBoardVariantChoice",
        "ReleaseBoardVariantSelection",
        "resolve_release_board_variants",
        "require_release_board_variant_sources_current",
    } <= {node.name for node in owner.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))}
    resolver = next(
        node
        for node in owner.body
        if isinstance(node, ast.FunctionDef) and node.name == "resolve_release_board_variants"
    )
    repository_import = next(
        node
        for node in owner.body
        if isinstance(node, ast.ImportFrom) and node.module == "product_repository_models"
    )
    assert {alias.name for alias in repository_import.names} == {"ProductRepository"}
    assert "ProductRepository" in ast.unparse(resolver.args.args[0].annotation)
    freshness = next(
        node
        for node in owner.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "require_release_board_variant_sources_current"
    )
    assert "require_product_file_current" in _calls(freshness)


def test_readiness_uses_explicit_typed_choice_while_retaining_mapping_adapter() -> None:
    readiness = Path(release.__file__).read_text(encoding="utf-8")
    tree = _tree(release)
    compatibility = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "selected_board_variants"
    )
    assert _calls(compatibility) == {"project_board_variant_names"}
    check = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "check"
    )
    check_calls = _calls(check)
    assert "resolve_release_board_variants" in check_calls
    assert "require_release_board_variant_sources_current" in check_calls
    assert "selected_board_variants" not in check_calls
    assert "ReleaseBoardVariantSelection" not in readiness


def test_preparation_uses_owner_directly_and_rechecks_sources_before_publication() -> None:
    tree = _tree(releasing)
    imports = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "release_board_variant_selection"
        for alias in node.names
    }
    assert {
        "ReleaseBoardVariantSelection",
        "resolve_release_board_variants",
        "require_release_board_variant_sources_current",
    } <= imports
    assert "selected_board_variants" not in imports
    prepare = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "prepare_request"
    )
    assert "require_release_board_variant_sources_current" in _calls(prepare)
    assert "source_state" in _calls(prepare)
    assert "write_model" in _calls(prepare)


def test_architecture_suite_guards_new_owner_and_behavior_suite_size() -> None:
    for relative in (
        "kicad_tooling/hwrepo/release_board_variant_selection.py",
        "tests/test_release_board_variant_selection.py",
        "tests/test_release_board_variant_selection_architecture.py",
    ):
        assert len((_ROOT / relative).read_text(encoding="utf-8").splitlines()) < 500
