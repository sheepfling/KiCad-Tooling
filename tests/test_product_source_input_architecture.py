"""Ownership and compatibility boundaries for product source reads."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import (
    product,
    product_source_inputs,
    product_variant_bom,
    product_visual,
    release,
    release_variants,
    releasing,
)

pytestmark = pytest.mark.architecture


def test_product_source_models_and_reads_have_one_owner() -> None:
    owner = Path(product_source_inputs.__file__)
    assert len(owner.read_text(encoding="utf-8").splitlines()) < 500
    assert product.ProductSourceIdentity is product_source_inputs.ProductSourceIdentity
    assert product.read_product_source is product_source_inputs.read_product_source
    assert product_visual.read_product_source is product_source_inputs.read_product_source
    assert (
        product_visual.parse_product_index_document
        is product_source_inputs.parse_product_index_document
    )
    assert product_variant_bom.read_product_source is product_source_inputs.read_product_source
    assert release.ProductSourceIdentity is product_source_inputs.ProductSourceIdentity


def test_release_variant_resolution_uses_captured_layout_and_product_sources() -> None:
    source = Path(release_variants.__file__).read_text(encoding="utf-8")
    assert len(source.splitlines()) < 500
    tree = ast.parse(source)
    resolver = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "resolve_variants"
    )
    calls = {
        node.func.id
        for node in ast.walk(resolver)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert {
        "read_repository_layout",
        "require_repository_layout_current",
        "read_product_index_document",
        "require_product_index_document_current",
        "capture_product_record",
        "product_record_freshness_issues",
    } <= calls
    assert "read_model" not in calls

    owner_imports = {
        node.module: {alias.name for alias in node.names}
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
    }
    assert {
        "read_repository_layout",
        "require_repository_layout_current",
    } <= owner_imports["layout"]
    assert {
        "read_product_index_document",
        "require_product_index_document_current",
        "capture_product_record",
        "product_record_freshness_issues",
    } <= owner_imports["product_source_inputs"]

    compatibility = next(
        node
        for node in ast.parse(Path(releasing.__file__).read_text(encoding="utf-8")).body
        if isinstance(node, ast.FunctionDef) and node.name == "resolve_variants"
    )
    compatibility_calls = {
        node.func.id
        for node in ast.walk(compatibility)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert compatibility_calls == {"select_release_variants"}
