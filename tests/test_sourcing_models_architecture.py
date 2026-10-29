"""Supplier sourcing contracts have a cohesive model owner."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import models, sourcing_models

pytestmark = pytest.mark.architecture

_REPOSITORY_ROOT = Path(__file__).parents[1]


def test_sourcing_models_are_small_and_depend_only_on_shared_contracts() -> None:
    path = _REPOSITORY_ROOT / "kicad_tooling/hwrepo/sourcing_models.py"
    source = path.read_text(encoding="utf-8")
    imported_modules = {
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module != "__future__"
    }

    assert len(source.splitlines()) < 500
    assert imported_modules == {"pydantic", "typing", "model_primitives", "policy_issue_models"}


def test_internal_services_import_sourcing_contracts_from_their_owner() -> None:
    directory = _REPOSITORY_ROOT / "kicad_tooling"
    compatibility_registry = directory / "hwrepo/models.py"
    names = {"SupplierOffer", "SourcingSnapshot", "SourcingSnapshotReport"}
    violations: list[str] = []
    for path in directory.rglob("*.py"):
        if path == compatibility_registry:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module not in {
                "models",
                "kicad_tooling.hwrepo.models",
                "hwrepo.models",
            }:
                continue
            if names.intersection(alias.name for alias in node.names):
                violations.append(f"{path.relative_to(_REPOSITORY_ROOT)}:{node.lineno}")

    assert not violations, "Internal callers must import sourcing contracts directly: " + ", ".join(
        violations
    )


def test_registry_exports_and_json_shapes_remain_compatible() -> None:
    offer = sourcing_models.SupplierOffer(
        id="offer-1",
        part_id="part-1",
        supplier="Example supplier",
        supplier_sku="EXAMPLE-1",
        source_url="https://example.invalid/offer",
        region="test-only",
        currency="USD",
        quantity_break=1,
        unit_price_minor=0,
        availability="unverified",
    )
    snapshot = sourcing_models.SourcingSnapshot(
        snapshot_id="snapshot-1",
        source_commit="a" * 40,
        observed_at=datetime(2026, 10, 29, tzinfo=UTC),
        offers=(offer,),
    )
    report = sourcing_models.SourcingSnapshotReport(
        snapshot_id=snapshot.snapshot_id,
        offers=len(snapshot.offers),
        status="PASS",
        issues=(),
    )

    for name in ("SupplierOffer", "SourcingSnapshot", "SourcingSnapshotReport"):
        assert getattr(models, name) is getattr(sourcing_models, name)
    assert models.SourcingSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot
    assert models.SourcingSnapshotReport.model_validate_json(report.model_dump_json()) == report
    assert (
        models.SourcingSnapshot.model_json_schema()
        == sourcing_models.SourcingSnapshot.model_json_schema()
    )
