"""Guard precise input types at retained-report and serialized JSON boundaries."""

from __future__ import annotations

import ast
from typing import get_type_hints

import pytest
from pydantic import JsonValue

from kicad_tooling.hwrepo.connectivity_view import _authored  # pyright: ignore[reportPrivateUsage]
from kicad_tooling.hwrepo.electrical_analysis_contract_models import ElectricalAnalysisContract
from kicad_tooling.hwrepo.hosted_governance import (  # pyright: ignore[reportPrivateUsage]
    _gh,
    _model,
)
from kicad_tooling.playtest_mcp import PlaytestHost
from tests.support import SOURCE_ROOT

pytestmark = pytest.mark.architecture


def _return_annotation(relative: str, name: str) -> str:
    source = (SOURCE_ROOT / relative).read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source, filename=relative)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            assert node.returns is not None
            return ast.unparse(node.returns)
    raise AssertionError(f"Function {name} is missing from {relative}")


def _imported_type_names(tree: ast.Module, names: set[str]) -> set[str]:
    result = set(names)
    typing_modules = {"typing", "typing_extensions", "collections.abc"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in typing_modules:
            for imported in node.names:
                if imported.name in names:
                    result.add(imported.asname or imported.name)
    return result


def _contains_any_annotation(node: ast.AST, any_names: set[str]) -> bool:
    return any(
        (isinstance(child, ast.Name) and child.id in any_names)
        or (isinstance(child, ast.Attribute) and child.attr == "Any")
        for child in ast.walk(node)
    )


def _contains_opaque_collection(node: ast.AST, collection_names: set[str]) -> bool:
    opaque_names = {"Any", "object"}

    def has_opaque_value(value: ast.AST) -> bool:
        return any(
            (isinstance(child, ast.Name) and child.id in opaque_names)
            or (isinstance(child, ast.Attribute) and child.attr in opaque_names)
            for child in ast.walk(value)
        )

    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id in collection_names:
            # A bare collection annotation has no declared key or value type.
            parent_is_subscript = any(
                isinstance(parent, ast.Subscript) and parent.value is child
                for parent in ast.walk(node)
            )
            if not parent_is_subscript:
                return True
        if isinstance(child, ast.Subscript):
            base = ast.unparse(child.value).split(".")[-1]
            if base in collection_names and has_opaque_value(child.slice):
                return True
    return False


def _canonical_collection_names() -> set[str]:
    return {
        "dict",
        "Dict",
        "Mapping",
        "MutableMapping",
        "DefaultDict",
        "OrderedDict",
        "Counter",
        "Collection",
        "Iterable",
        "Iterator",
        "Generator",
        "Deque",
        "KeysView",
        "ValuesView",
        "ItemsView",
        "Sequence",
        "MutableSequence",
        "list",
        "List",
        "tuple",
        "Tuple",
        "set",
        "Set",
        "MutableSet",
        "frozenset",
        "FrozenSet",
    }


def _annotations(tree: ast.Module) -> tuple[ast.AST, ...]:
    values: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            values.extend(
                argument.annotation
                for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
                if argument.annotation is not None
            )
            if node.args.vararg is not None and node.args.vararg.annotation is not None:
                values.append(node.args.vararg.annotation)
            if node.args.kwarg is not None and node.args.kwarg.annotation is not None:
                values.append(node.args.kwarg.annotation)
            if node.returns is not None:
                values.append(node.returns)
        elif isinstance(node, ast.AnnAssign):
            values.append(node.annotation)
    return tuple(values)


def test_opaque_annotation_check_distinguishes_raw_parser_values() -> None:
    examples = {
        "dict[str, object]": True,
        "Mapping[str, list[object]]": True,
        "dict": True,
        "dict[str, JsonValue]": False,
        "list[str]": False,
        "object": False,
    }
    for source, expected in examples.items():
        tree = ast.parse(f"value: {source}")
        annotation = tree.body[0]
        assert isinstance(annotation, ast.AnnAssign)
        collection_names = _imported_type_names(tree, _canonical_collection_names())
        assert _contains_opaque_collection(annotation.annotation, collection_names) is expected

    aliased = ast.parse("from typing import Mapping as Fields\nvalue: Fields[str, object]")
    annotation = aliased.body[1]
    assert isinstance(annotation, ast.AnnAssign)
    collection_names = _imported_type_names(aliased, _canonical_collection_names())
    assert _contains_opaque_collection(annotation.annotation, collection_names)

    aliased_any = ast.parse("from typing import Any as Unknown\nvalue: list[Unknown]")
    annotation = aliased_any.body[1]
    assert isinstance(annotation, ast.AnnAssign)
    any_names = _imported_type_names(aliased_any, {"Any"})
    assert _contains_any_annotation(annotation.annotation, any_names)


def test_connectivity_view_uses_the_authored_contract_owner() -> None:
    assert get_type_hints(_authored, include_extras=True)["contract"] is (
        ElectricalAnalysisContract
    )


def test_external_json_adapters_keep_the_closed_json_value_type() -> None:
    assert get_type_hints(_gh, include_extras=True)["return"] == JsonValue
    assert get_type_hints(_model, include_extras=True)["value"] == JsonValue
    assert get_type_hints(PlaytestHost.save, include_extras=True)["document"] == JsonValue
    assert (
        _return_annotation(
            "kicad_tooling/hwrepo/netlist_contract_inputs.py",
            "normalize_native_unconnected_nets",
        )
        == "NetlistRawValue"
    )


def test_fixture_repeatability_keys_use_their_finding_record_types() -> None:
    for module, function in (
        ("kicad_tooling/ci_hosted_open_drain_bias.py", "finding_key"),
        ("kicad_tooling/ci_hosted_serial_peer_net_labels.py", "report_signature"),
    ):
        assert "object" not in _return_annotation(module, function)


def test_package_and_script_annotations_do_not_use_any_or_opaque_collections() -> None:
    roots = (SOURCE_ROOT / "kicad_tooling", SOURCE_ROOT / "scripts")
    violations: list[str] = []
    for root in roots:
        for path in sorted(root.rglob("*.py")):
            relative = path.relative_to(SOURCE_ROOT).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            collection_names = _imported_type_names(tree, _canonical_collection_names())
            any_names = _imported_type_names(tree, {"Any"})
            for annotation in _annotations(tree):
                rendered = ast.unparse(annotation)
                if _contains_any_annotation(annotation, any_names):
                    violations.append(f"{relative}: Any in {rendered}")
                elif _contains_opaque_collection(annotation, collection_names):
                    violations.append(f"{relative}: opaque collection in {rendered}")
    assert not violations, "\n".join(violations)
