"""Guard authored release contracts and their compatibility exports."""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import models, release_contract_models
from kicad_tooling.hwrepo.product_models import Assurance
from kicad_tooling.hwrepo.release_model_types import ReleaseClass

pytestmark = pytest.mark.architecture

_ROOT = Path(__file__).parents[1]
_OWNER = _ROOT / "kicad_tooling/hwrepo/release_contract_models.py"
_MODEL_NAMES = frozenset(
    {
        "ReleaseAssurancePolicy",
        "ReleasePoliciesCatalog",
        "ReleaseStatus",
        "DeviationStatus",
        "ReleaseVariant",
        "ReleaseLibrary",
        "ReleaseInterface",
        "ReleaseArtifactKind",
        "ReleaseArtifact",
        "ReleaseDeviation",
        "ReleaseApproval",
        "EvidenceFile",
        "ReleaseEvidence",
        "ReleaseManifest",
    }
)


def _imports(path: Path) -> set[str]:
    return {
        node.module
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module != "__future__"
    }


def test_release_contract_owner_has_only_domain_and_primitive_dependencies() -> None:
    assert len(_OWNER.read_text(encoding="utf-8").splitlines()) < 500
    assert _imports(_OWNER) == {
        "collections.abc",
        "datetime",
        "enum",
        "typing",
        "pydantic",
        "model_primitives",
        "product_models",
        "release_model_types",
    }


def test_production_consumers_import_release_contracts_from_the_owner() -> None:
    tooling = _ROOT / "kicad_tooling"
    registry = tooling / "hwrepo/models.py"
    violations: list[str] = []

    for path in tooling.rglob("*.py"):
        if path == registry:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ImportFrom) or node.module not in {
                "models",
                "hwrepo.models",
                "kicad_tooling.hwrepo.models",
            }:
                continue
            misplaced = _MODEL_NAMES.intersection(alias.name for alias in node.names)
            if misplaced:
                violations.append(f"{path.relative_to(_ROOT)}:{node.lineno}: {sorted(misplaced)}")

    assert not violations, "Import release contracts from their owner: " + "; ".join(violations)


def test_registry_exports_and_authored_manifest_json_remain_compatible() -> None:
    for name in _MODEL_NAMES:
        assert getattr(models, name) is getattr(release_contract_models, name)

    evidence = release_contract_models.EvidenceFile(
        path="build/release/native.json", sha256="b" * 64
    )
    report = release_contract_models.ReleaseManifest(
        release_id="controller-1.0.0",
        release_class=ReleaseClass.ENGINEERING_REVIEW,
        status=release_contract_models.ReleaseStatus.CANDIDATE,
        source_commit="a" * 40,
        toolchain_id="kicad-9",
        variants=(
            release_contract_models.ReleaseVariant(
                product="controller",
                product_revision="1.0.0",
                variant="base",
                variant_revision="1",
            ),
        ),
        libraries=(
            release_contract_models.ReleaseLibrary(
                id="symbols",
                version="1.0",
                provenance_sha256="c" * 64,
                licensing_sha256="d" * 64,
            ),
        ),
        interfaces=(release_contract_models.ReleaseInterface(id="power", revision="1"),),
        evidence=release_contract_models.ReleaseEvidence(portable=evidence, native={}),
        artifacts=(
            release_contract_models.ReleaseArtifact(
                id="review",
                kind=release_contract_models.ReleaseArtifactKind.REVIEW_RECORD,
                path="release/review.md",
                sha256="e" * 64,
                intended_use="engineering review",
            ),
        ),
        deviations=(
            release_contract_models.ReleaseDeviation(
                id="temporary-note",
                scope=("controller",),
                owner="hardware team",
                reason="Awaiting the updated enclosure drawing.",
                status=release_contract_models.DeviationStatus.OPEN,
                expires=date(2027, 1, 1),
                evidence=("review",),
            ),
        ),
        approval=release_contract_models.ReleaseApproval(
            electrical_reviewer="reviewer-a",
            integrator="integrator-a",
            approved_at=date(2026, 11, 3),
            evidence=("review",),
        ),
    )
    policy = release_contract_models.ReleasePoliciesCatalog(
        policies=(
            release_contract_models.ReleaseAssurancePolicy(
                release_class=ReleaseClass.ENGINEERING_REVIEW,
                minimum_assurance=Assurance.UNKNOWN,
            ),
        ),
    )

    assert type(report).model_validate_json(report.model_dump_json()) == report
    assert type(policy).model_validate_json(policy.model_dump_json()) == policy
