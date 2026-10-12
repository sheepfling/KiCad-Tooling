"""Keep crystal-network contracts in their component-owned model module."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import crystal_network_models
from kicad_tooling.hwrepo import models as shared_models
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.architecture,
]

CRYSTAL_MODEL_NAMES = (
    "CrystalLoadCapRequirement",
    "CrystalNetworkRequirement",
    "CrystalNetworkMap",
    "CrystalNetworkCoverageEntry",
    "CrystalNetworkCoverageReport",
)


def test_crystal_network_models_have_one_owner_and_compatible_exports() -> None:
    owner_path = REPO_ROOT / "kicad_tooling/hwrepo/crystal_network_models.py"
    registry_path = REPO_ROOT / "kicad_tooling/hwrepo/models.py"
    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES

    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    owner_definitions = {node.name for node in owner_tree.body if isinstance(node, ast.ClassDef)}
    registry_tree = ast.parse(registry_path.read_text(encoding="utf-8"))
    registry_definitions = {
        node.name for node in registry_tree.body if isinstance(node, ast.ClassDef)
    }

    assert set(CRYSTAL_MODEL_NAMES) <= owner_definitions
    assert not (set(CRYSTAL_MODEL_NAMES) & registry_definitions)
    for name in CRYSTAL_MODEL_NAMES:
        assert getattr(shared_models, name) is getattr(crystal_network_models, name)


def test_internal_crystal_services_import_models_from_the_owner() -> None:
    legacy_imports: list[str] = []
    for directory in (REPO_ROOT / "kicad_tooling", REPO_ROOT / "tests"):
        for source in sorted(directory.rglob("*.py")):
            if source == REPO_ROOT / "kicad_tooling/hwrepo/models.py":
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
                        if alias.name in CRYSTAL_MODEL_NAMES
                    )

    assert not legacy_imports, (
        "Internal crystal-network services and regressions should import theme-owned "
        f"models directly: {legacy_imports}"
    )
