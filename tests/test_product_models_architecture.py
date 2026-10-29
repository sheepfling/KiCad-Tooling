"""Guard product contract ownership and the models.py compatibility registry."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import models, product_models

pytestmark = pytest.mark.architecture

_REPOSITORY_ROOT = Path(__file__).parents[1]
_PRODUCT_MODEL_NAMES = frozenset(
    {
        "Assurance",
        "ProductIndexEntry",
        "ProductIndex",
        "AssemblyKind",
        "AssemblyMember",
        "Assembly",
        "TerminalKind",
        "Terminal",
        "ConnectionKind",
        "Connection",
        "Variant",
        "EvidenceKind",
        "Evidence",
        "Harness",
        "MechanicalHandoff",
        "ProductRecord",
        "ProductPolicyReport",
        "Occurrence",
        "BomRow",
        "HarnessScheduleRow",
        "HarnessSchedule",
        "ElectricalConnectionView",
        "ElectricalView",
        "SystemConnectionView",
        "SystemView",
    }
)


def test_product_models_have_a_closed_domain_dependency_set() -> None:
    path = _REPOSITORY_ROOT / "kicad_tooling/hwrepo/product_models.py"
    source = path.read_text(encoding="utf-8")
    imported_modules = {
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module != "__future__"
    }

    assert len(source.splitlines()) < 500
    assert imported_modules == {
        "collections.abc",
        "enum",
        "typing",
        "pydantic",
        "model_primitives",
        "policy_issue_models",
    }


def test_production_modules_import_product_contracts_from_the_owner() -> None:
    tooling_root = _REPOSITORY_ROOT / "kicad_tooling"
    compatibility_registry = tooling_root / "hwrepo/models.py"
    violations: list[str] = []
    for path in tooling_root.rglob("*.py"):
        if path == compatibility_registry:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module not in {
                "models",
                "hwrepo.models",
                "kicad_tooling.hwrepo.models",
            }:
                continue
            imported = _PRODUCT_MODEL_NAMES.intersection(alias.name for alias in node.names)
            if imported:
                names = ", ".join(sorted(imported))
                violations.append(f"{path.relative_to(_REPOSITORY_ROOT)}:{node.lineno}: {names}")

    assert not violations, "Production imports must use product_models: " + "; ".join(violations)


def test_registry_exports_and_product_contract_json_remain_compatible() -> None:
    for name in _PRODUCT_MODEL_NAMES:
        assert getattr(models, name) is getattr(product_models, name)

    product = product_models.ProductRecord(
        schema_version="1",
        id="assembly-1",
        revision="A",
        maturity="training",
        root_assembly="root",
        assemblies=(),
        terminals=(),
        connections=(),
        variants=(),
        evidence=(),
        harnesses=(),
        mechanical=(),
        blocking_issues=(),
    )
    index = product_models.ProductIndex(
        schema_version="1",
        products=(
            product_models.ProductIndexEntry(
                id=product.id,
                path="catalog/products/assembly-1.json",
                project_ids=(),
            ),
        ),
    )
    policy = product_models.ProductPolicyReport(
        status="PASS",
        products=(product.id,),
        open_items={},
        issues=(),
    )

    assert models.ProductRecord.model_validate_json(product.model_dump_json()) == product
    assert models.ProductIndex.model_validate_json(index.model_dump_json()) == index
    assert models.ProductPolicyReport.model_validate_json(policy.model_dump_json()) == policy
    assert (
        models.ProductRecord.model_json_schema() == product_models.ProductRecord.model_json_schema()
    )
