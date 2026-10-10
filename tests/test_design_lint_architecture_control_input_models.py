"""Keep control-input requirements and coverage in their theme-owned model module."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import control_input_models
from kicad_tooling.hwrepo import models as shared_models
from tests.lint_architecture_support import (
    IMPLEMENTATION_MAX_LINES,
    REPO_ROOT,
    line_count,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]

CONTROL_INPUT_MODEL_NAMES = (
    "ControlInputBiasHeuristicEntry",
    "ControlInputBiasHeuristicCoverage",
    "ControlElectricalType",
    "ControlPinRequirement",
    "ControlBiasResistorRequirement",
    "ControlLocalBiasRequirement",
    "ControlInternalBiasRequirement",
    "ControlExternalBiasRequirement",
    "ControlNoBiasRequirement",
    "ControlBiasRequirement",
    "ControlSignalRequirement",
    "ControlInputsAnalysis",
)


def _top_level_definitions(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names.update(target.id for target in targets if isinstance(target, ast.Name))
    return names


def test_control_input_models_live_in_owner_and_registry_exports_keep_identity() -> None:
    owner_path = REPO_ROOT / "kicad_tooling/hwrepo/control_input_models.py"
    registry_path = REPO_ROOT / "kicad_tooling/hwrepo/models.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    registry_tree = ast.parse(registry_path.read_text(encoding="utf-8"))

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert set(CONTROL_INPUT_MODEL_NAMES) <= _top_level_definitions(owner_tree)
    registry_class_definitions = {
        node.name for node in registry_tree.body if isinstance(node, ast.ClassDef)
    }
    assert not (set(CONTROL_INPUT_MODEL_NAMES) & registry_class_definitions)
    for name in CONTROL_INPUT_MODEL_NAMES:
        assert getattr(shared_models, name) is getattr(control_input_models, name)


def test_internal_control_input_services_import_models_from_the_owner() -> None:
    legacy_imports: list[str] = []
    package = REPO_ROOT / "kicad_tooling"

    for source in sorted(package.rglob("*.py")):
        if source.name == "models.py":
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
                    if alias.name in CONTROL_INPUT_MODEL_NAMES
                )

    assert not legacy_imports, (
        f"Internal control-input services must import theme-owned models directly: {legacy_imports}"
    )
