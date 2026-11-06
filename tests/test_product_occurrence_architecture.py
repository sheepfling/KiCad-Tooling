"""Guard the source-bound product occurrence route across its consumers."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

_ROOT = Path(__file__).parents[1]


def _tree(relative_path: str) -> ast.Module:
    return ast.parse((_ROOT / relative_path).read_text(encoding="utf-8"))


def _function(tree: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    return next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )


def _called_names(node: ast.AST) -> set[str]:
    return {
        call.func.id if isinstance(call.func, ast.Name) else call.func.attr
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and isinstance(call.func, (ast.Name, ast.Attribute))
    }


def test_occurrence_contract_is_owned_by_the_product_domain() -> None:
    product_models = _tree("kicad_tooling/hwrepo/product_models.py")
    product_service = _tree("kicad_tooling/hwrepo/product.py")
    occurrence_service = _tree("kicad_tooling/hwrepo/product_occurrences.py")
    source_inputs = _tree("kicad_tooling/hwrepo/product_source_inputs.py")
    repository_models = _tree("kicad_tooling/hwrepo/product_repository_models.py")

    assert any(
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "ProductOccurrenceMap"
        for node in product_models.body
    )
    assert "ProductSourceIdentity" in {
        node.name for node in source_inputs.body if isinstance(node, ast.ClassDef)
    }
    assert "ProductOccurrenceIndex" in {
        node.name for node in occurrence_service.body if isinstance(node, ast.ClassDef)
    }
    compatibility_exports = {
        alias.name
        for node in product_service.body
        if isinstance(node, ast.ImportFrom) and node.module == "product_occurrences"
        for alias in node.names
    }
    assert {
        "ProductOccurrenceIndex",
        "occurrences",
        "occurrences_for",
        "product_occurrence_index",
    } <= compatibility_exports
    repository = next(
        node
        for node in repository_models.body
        if isinstance(node, ast.ClassDef) and node.name == "ProductRepository"
    )
    assert "product_sources" in {
        node.target.id
        for node in repository.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert "product_index_document" in {
        node.target.id
        for node in repository.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }


def test_repository_consumers_import_the_product_repository_owner() -> None:
    for path in ("kicad_tooling/hwrepo/release.py", "kicad_tooling/hwrepo/releasing.py"):
        tree = _tree(path)
        owner_imports = {
            alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "product_repository_models"
            for alias in node.names
        }
        assert "ProductRepository" in owner_imports, path


def test_generation_projection_owner_and_coordinator_have_clear_boundaries() -> None:
    for path in (
        "kicad_tooling/hwrepo/generation.py",
        "kicad_tooling/hwrepo/generation_outputs.py",
    ):
        assert len((_ROOT / path).read_text(encoding="utf-8").splitlines()) < 500, path

    outputs = _tree("kicad_tooling/hwrepo/generation_outputs.py")
    assert not any(
        isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.endswith(".generation")
        for node in outputs.body
    )
    repository_projection = _function(outputs, "expected_outputs_from_repository")
    assert "ProductRepository" in ast.unparse(repository_projection.args)
    assert "product_occurrence_index" in _called_names(repository_projection)


def test_generation_drift_and_snapshot_share_one_repository_capture() -> None:
    generation = _tree("kicad_tooling/hwrepo/generation.py")
    for function_name in ("drift", "snapshot"):
        function = _function(generation, function_name)
        calls = [
            call.func.id
            for call in ast.walk(function)
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
        ]
        assert calls.count("load_repository") == 1, function_name
        assert calls.count("expected_outputs_from_repository") == 1, function_name


def test_product_visual_reuses_its_captured_index_document() -> None:
    tree = _tree("kicad_tooling/hwrepo/product_visual.py")
    function = _function(tree, "build_product_visual")
    repository_calls = [
        call
        for call in ast.walk(function)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "load_repository"
    ]
    index_arguments = [
        keyword.value
        for call in repository_calls
        for keyword in call.keywords
        if keyword.arg == "product_index_document"
    ]

    assert "parse_product_index_document" in _called_names(function)
    assert len(repository_calls) == 1
    assert len(index_arguments) == 1
    assert isinstance(index_arguments[0], ast.Name)
    assert index_arguments[0].id == "index_document"


def test_production_occurrence_consumers_use_source_bound_indexes() -> None:
    consumers = (
        (
            "kicad_tooling/hwrepo/generation_outputs.py",
            "expected_outputs_from_repository",
        ),
        ("kicad_tooling/hwrepo/product_visual.py", "build_product_visual"),
        ("kicad_tooling/hwrepo/release_population.py", "verify_board_population"),
        ("kicad_tooling/hwrepo/product_revision_bom.py", "_load_view"),
        ("kicad_tooling/hwrepo/product_variant_bom.py", "compare_product_variants"),
    )
    for path, function_name in consumers:
        function = _function(_tree(path), function_name)
        assert "product_occurrence_index" in _called_names(function), (path, function_name)


def test_occurrence_and_release_population_owners_stay_focused() -> None:
    for path in (
        "kicad_tooling/hwrepo/product_occurrences.py",
        "kicad_tooling/hwrepo/release_population.py",
        "kicad_tooling/hwrepo/product_view_contracts.py",
    ):
        assert len((_ROOT / path).read_text(encoding="utf-8").splitlines()) < 500, path

    for path in (
        "kicad_tooling/hwrepo/generation_outputs.py",
        "kicad_tooling/hwrepo/product_visual.py",
        "kicad_tooling/hwrepo/product_revision_bom.py",
        "kicad_tooling/hwrepo/product_variant_bom.py",
        "kicad_tooling/hwrepo/release_population.py",
    ):
        tree = _tree(path)
        assert any(
            isinstance(node, ast.ImportFrom) and node.module == "product_occurrences"
            for node in tree.body
        ), path

    view_contracts = _tree("kicad_tooling/hwrepo/product_view_contracts.py")
    owned_functions = {
        node.name for node in view_contracts.body if isinstance(node, ast.FunctionDef)
    }
    assert {
        "validate_system_wiring_contract",
        "validate_harness_interface_contract",
    } <= owned_functions
    assert not any(
        isinstance(node, ast.ImportFrom) and node.module == "product"
        for node in view_contracts.body
    )


def test_release_preparation_passes_repository_product_sources() -> None:
    tree = _tree("kicad_tooling/hwrepo/releasing.py")
    function = _function(tree, "prepare_request")
    source_arguments = [
        keyword.value
        for call in ast.walk(function)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "verify_board_population"
        for keyword in call.keywords
        if keyword.arg == "product_sources"
    ]

    assert len(source_arguments) == 1
    source_argument = source_arguments[0]
    assert isinstance(source_argument, ast.Attribute)
    assert isinstance(source_argument.value, ast.Name)
    assert source_argument.value.id == "repository"
    assert source_argument.attr == "product_sources"


def test_product_instance_paths_keep_the_string_wire_shape() -> None:
    product_models = _tree("kicad_tooling/hwrepo/product_models.py")
    product_visual_models = _tree("kicad_tooling/hwrepo/product_visual_models.py")
    variant_bom_models = _tree("kicad_tooling/hwrepo/product_variant_bom_models.py")
    path_alias = next(
        node
        for node in product_models.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "ProductInstancePath"
            for target in node.targets
        )
    )
    assert isinstance(path_alias.value, ast.Call)
    assert isinstance(path_alias.value.func, ast.Name) and path_alias.value.func.id == "NewType"
    instance = next(
        node
        for node in product_visual_models.body
        if isinstance(node, ast.ClassDef) and node.name == "ProductVisualInstance"
    )
    path_field = next(
        node
        for node in instance.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "path"
    )
    assert isinstance(path_field.annotation, ast.Name)
    assert path_field.annotation.id == "ProductInstancePath"

    difference = next(
        node
        for node in variant_bom_models.body
        if isinstance(node, ast.ClassDef) and node.name == "VariantBomInstanceDifference"
    )
    difference_path = next(
        node
        for node in difference.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "path"
    )
    assert isinstance(difference_path.annotation, ast.Name)
    assert difference_path.annotation.id == "ProductInstancePath"


def test_variant_bom_instance_index_has_a_named_immutable_boundary() -> None:
    variant_models = _tree("kicad_tooling/hwrepo/product_variant_bom_models.py")
    variant_service = _tree("kicad_tooling/hwrepo/product_variant_bom.py")
    alias = next(
        node
        for node in variant_models.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "VariantBomInstanceIndex"
    )
    assert ast.unparse(alias.annotation) == "TypeAlias"
    assert ast.unparse(alias.value) == "Mapping[ProductInstancePath, VariantBomInstanceState]"

    states = _function(variant_service, "instance_states")
    assert isinstance(states.returns, ast.Name)
    assert states.returns.id == "VariantBomInstanceIndex"
    assert "MappingProxyType" in _called_names(states)
