"""Guard the authored parts catalog model owner and registry compatibility."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import models, part_catalog_models

pytestmark = pytest.mark.architecture

_REPOSITORY_ROOT = Path(__file__).parents[1]
_PART_MODEL_NAMES = frozenset({"PartStatus", "PartCadBinding", "PartRecord", "PartsCatalog"})


def test_part_catalog_models_have_a_small_primitive_only_boundary() -> None:
    path = _REPOSITORY_ROOT / "kicad_tooling/hwrepo/part_catalog_models.py"
    source = path.read_text(encoding="utf-8")
    imported_modules = {
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module != "__future__"
    }

    assert len(source.splitlines()) < 500
    assert imported_modules == {"enum", "typing", "pydantic", "model_primitives"}


def test_production_modules_import_part_catalog_contracts_from_the_owner() -> None:
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
            imported = _PART_MODEL_NAMES.intersection(alias.name for alias in node.names)
            if imported:
                names = ", ".join(sorted(imported))
                violations.append(f"{path.relative_to(_REPOSITORY_ROOT)}:{node.lineno}: {names}")

    assert not violations, "Production imports must use part_catalog_models: " + "; ".join(
        violations
    )


def test_registry_exports_and_part_catalog_json_remain_compatible() -> None:
    for name in _PART_MODEL_NAMES:
        assert getattr(models, name) is getattr(part_catalog_models, name)

    record = part_catalog_models.PartRecord(
        id="part-1",
        revision="A",
        description="Training resistor",
        part_class="passive",
        unit="each",
        manufacturer="Example",
        mpn="R-1",
        datasheet_url="https://example.invalid/datasheet",
        lifecycle="active",
        status=part_catalog_models.PartStatus.APPROVED,
        cad=part_catalog_models.PartCadBinding(
            symbol_id="Device:R",
            value="10k",
            footprint="Resistor_SMD:R_0603_1608Metric",
            model="models/resistor.step",
            digikey_sku="123-456",
        ),
    )
    catalog = part_catalog_models.PartsCatalog(schema_version="0.1", parts=(record,))

    assert models.PartsCatalog.model_validate_json(catalog.model_dump_json()) == catalog
    assert (
        models.PartRecord.model_json_schema() == part_catalog_models.PartRecord.model_json_schema()
    )
