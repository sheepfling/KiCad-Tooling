"""Keep energy-storage requirements in their theme-owned model module."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import energy_storage_models
from kicad_tooling.hwrepo import models as compatibility_models
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = pytest.mark.architecture

MODEL_NAMES = ("EnergyStorageHoldUpRequirement", "EnergyStorageAnalysis")


def test_energy_storage_models_have_a_bounded_theme_owner_and_compatible_exports() -> None:
    owner = REPO_ROOT / "kicad_tooling/hwrepo/energy_storage_models.py"
    registry = REPO_ROOT / "kicad_tooling/hwrepo/models.py"
    owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=str(owner))
    registry_tree = ast.parse(registry.read_text(encoding="utf-8"), filename=str(registry))
    owner_classes = {node.name for node in owner_tree.body if isinstance(node, ast.ClassDef)}
    registry_classes = {node.name for node in registry_tree.body if isinstance(node, ast.ClassDef)}

    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert set(MODEL_NAMES) <= owner_classes
    assert not (set(MODEL_NAMES) & registry_classes)
    for name in MODEL_NAMES:
        model = getattr(energy_storage_models, name)
        assert getattr(compatibility_models, name) is model
        assert model.__module__ == "kicad_tooling.hwrepo.energy_storage_models"


def test_energy_storage_owner_does_not_import_the_shared_registry() -> None:
    owner = REPO_ROOT / "kicad_tooling/hwrepo/energy_storage_models.py"
    tree = ast.parse(owner.read_text(encoding="utf-8"), filename=str(owner))
    forbidden = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and (node.module == "models" or node.module.endswith(".models"))
    ]
    assert forbidden == []
