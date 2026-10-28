"""Keep grounding and pin-connectivity contracts in electrical-theme owners."""

from __future__ import annotations

import ast
from types import MappingProxyType

import pytest

from kicad_tooling.hwrepo import grounding_models, pin_connectivity_models
from kicad_tooling.hwrepo import models as shared_models
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.connector_lint,
    pytest.mark.return_path_lint,
    pytest.mark.architecture,
]

MODEL_OWNERS = MappingProxyType(
    {
        "grounding_models.py": (
            grounding_models,
            ("GroundDomain", "GroundingAnalysis"),
        ),
        "pin_connectivity_models.py": (
            pin_connectivity_models,
            ("PinRelationshipRule", "PinConnectivityAnalysis"),
        ),
    }
)


def test_electrical_contract_types_have_theme_owners_and_compatible_exports() -> None:
    registry_path = REPO_ROOT / "kicad_tooling/hwrepo/models.py"
    registry_tree = ast.parse(registry_path.read_text(encoding="utf-8"))
    registry_classes = {node.name for node in registry_tree.body if isinstance(node, ast.ClassDef)}

    for module_name, (owner, names) in MODEL_OWNERS.items():
        owner_path = REPO_ROOT / "kicad_tooling/hwrepo" / module_name
        owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
        owner_classes = {node.name for node in owner_tree.body if isinstance(node, ast.ClassDef)}
        assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
        assert set(names) <= owner_classes
        assert not (set(names) & registry_classes)
        for name in names:
            assert getattr(shared_models, name) is getattr(owner, name)


def test_internal_electrical_services_import_contracts_from_theme_owners() -> None:
    moved_names = {
        "GroundDomain",
        "GroundingAnalysis",
        "PinRelationshipRule",
        "PinConnectivityAnalysis",
    }
    registry = REPO_ROOT / "kicad_tooling/hwrepo/models.py"
    legacy_imports: list[str] = []

    for source in sorted((REPO_ROOT / "kicad_tooling").rglob("*.py")):
        if source == registry:
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and (node.module == "models" or node.module.endswith(".models"))
            ):
                legacy_imports.extend(
                    f"{source.relative_to(REPO_ROOT).as_posix()}:{alias.name}"
                    for alias in node.names
                    if alias.name in moved_names
                )

    assert not legacy_imports, (
        "Internal electrical services should import grounding and pin-connectivity "
        f"contracts from their theme owners: {legacy_imports}"
    )
