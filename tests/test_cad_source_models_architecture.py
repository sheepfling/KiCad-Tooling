"""Keep sourced-CAD contracts in their owner with compatible registry exports."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import cad_source_models, models

pytestmark = pytest.mark.architecture

_REPOSITORY_ROOT = Path(__file__).parents[1]
_CAD_SOURCE_MODEL_NAMES = frozenset(
    {
        "CadProviderIdentity",
        "CadSourceFile",
        "CadSourceBundle",
        "CadSourceReport",
        "CadStepReport",
        "CadBundleCheck",
        "CadImportPlan",
        "CadImportReport",
        "CadSourcingReview",
    }
)


def test_cad_source_models_have_a_small_evidence_and_primitives_boundary() -> None:
    path = _REPOSITORY_ROOT / "kicad_tooling/hwrepo/cad_source_models.py"
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
        "typing",
        "pydantic",
        "command_evidence_models",
        "model_primitives",
    }


def test_production_modules_import_cad_source_contracts_from_the_owner() -> None:
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
            imported = _CAD_SOURCE_MODEL_NAMES.intersection(alias.name for alias in node.names)
            if imported:
                violations.append(
                    f"{path.relative_to(_REPOSITORY_ROOT)}:{node.lineno}: "
                    + ", ".join(sorted(imported))
                )

    assert not violations, "Production imports must use cad_source_models: " + "; ".join(violations)


def test_registry_exports_preserve_cad_source_model_identity_and_json() -> None:
    source_file = cad_source_models.CadSourceFile(
        path="vendor/device.kicad_sym",
        sha256="a" * 64,
        source_url="https://example.invalid/source",
    )
    bundle = cad_source_models.CadSourceBundle(
        supplier_id="C1",
        manufacturer="Example",
        mpn="PART-1",
        package="QFN-16",
        symbol_file="vendor/device.kicad_sym",
        symbol_name="Device",
        footprint_file="vendor.pretty/device.kicad_mod",
        footprint_name="Device_QFN",
        model_file="vendor/device.wrl",
        files=(source_file,),
        source_url="https://example.invalid/source",
        source_sha256="b" * 64,
        retrieved_at="2026-10-29T00:00:00Z",
    )
    source = cad_source_models.CadSourceReport(
        status="READY",
        supplier_id="C1",
        bundle_directory="build/cad-source/bundle",
        bundle=bundle,
        receipt_directory="build/cad-source/receipt",
    )
    bundle_check = cad_source_models.CadBundleCheck(status="READY")
    records = (
        cad_source_models.CadProviderIdentity(
            supplier_id="C1",
            component_supplier_id="C2",
            manufacturer="Example",
            mpn="PART-1",
            package="QFN-16",
            symbol_name="Device",
            model_uuid="c" * 32,
        ),
        source_file,
        bundle,
        source,
        cad_source_models.CadStepReport(
            status="REVIEW",
            project_id="fixture",
            supplier_id="C1",
            receipt_directory="build/cad-step/receipt",
        ),
        bundle_check,
        cad_source_models.CadImportPlan(
            project_id="fixture",
            bundle_dir="build/cad-source/bundle",
            bundle_sha256="d" * 64,
            preconditions={"kicad/fixture.kicad_pro": None},
            after_hashes={"kicad/fixture.kicad_pro": "e" * 64},
        ),
        cad_source_models.CadImportReport(
            status="PLAN",
            project_id="fixture",
            check=bundle_check,
            receipt_directory="build/cad-import/receipt",
        ),
        cad_source_models.CadSourcingReview(source=source, review_id="review-1"),
    )

    assert tuple(type(record).__name__ for record in records) == tuple(
        name
        for name in (
            "CadProviderIdentity",
            "CadSourceFile",
            "CadSourceBundle",
            "CadSourceReport",
            "CadStepReport",
            "CadBundleCheck",
            "CadImportPlan",
            "CadImportReport",
            "CadSourcingReview",
        )
    )
    for record in records:
        record_type = type(record)
        assert getattr(models, record_type.__name__) is record_type
        assert (
            getattr(cad_source_models, record_type.__name__).model_validate_json(
                record.model_dump_json()
            )
            == record
        )
