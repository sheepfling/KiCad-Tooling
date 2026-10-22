"""Keep electrical simulation contracts in one focused model owner."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import electrical_simulation_models
from kicad_tooling.hwrepo import models as compatibility_models
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = pytest.mark.architecture

MODEL_NAMES = (
    "PowerLoad",
    "PowerRail",
    "SimulationMeasure",
    "SimulationModel",
    "TransientAnalysis",
    "FrequencyAnalysis",
    "PowerAnalysis",
    "HighFrequencyAnalysis",
    "SpiceExpression",
)

CONSUMER_IMPORTS = {
    "electrical.py": {
        "FrequencyAnalysis",
        "HighFrequencyAnalysis",
        "PowerAnalysis",
        "TransientAnalysis",
    },
    "spice.py": {"TransientAnalysis"},
    "electrical_plot.py": {"FrequencyAnalysis", "SimulationMeasure", "TransientAnalysis"},
    "electrical_charts.py": {"PowerAnalysis"},
}


def _owner_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.level == 1
        and node.module == "electrical_simulation_models"
        for alias in node.names
    }


def test_simulation_models_have_bounded_owner_and_compatible_exports() -> None:
    owner_path = REPO_ROOT / "kicad_tooling/hwrepo/electrical_simulation_models.py"
    registry_path = REPO_ROOT / "kicad_tooling/hwrepo/models.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"), filename=owner_path.name)
    registry_tree = ast.parse(
        registry_path.read_text(encoding="utf-8"), filename=registry_path.name
    )
    owner_classes = {node.name for node in owner_tree.body if isinstance(node, ast.ClassDef)}
    registry_classes = {node.name for node in registry_tree.body if isinstance(node, ast.ClassDef)}

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert set(MODEL_NAMES) - {"SpiceExpression"} <= owner_classes
    assert not (set(MODEL_NAMES) & registry_classes)
    assert any(
        isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "SpiceExpression"
            for target in node.targets
        )
        for node in owner_tree.body
    )
    for name in MODEL_NAMES:
        model = getattr(electrical_simulation_models, name)
        assert getattr(compatibility_models, name) is model
        if name != "SpiceExpression":
            assert model.__module__ == "kicad_tooling.hwrepo.electrical_simulation_models"


def test_internal_electrical_services_import_simulation_models_from_owner() -> None:
    owner_path = REPO_ROOT / "kicad_tooling/hwrepo/electrical_simulation_models.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"), filename=owner_path.name)
    assert not any(
        isinstance(node, ast.ImportFrom)
        and node.module is not None
        and (node.module == "models" or node.module.endswith(".models"))
        for node in ast.walk(owner_tree)
    )

    for filename, expected_names in CONSUMER_IMPORTS.items():
        consumer = REPO_ROOT / "kicad_tooling/hwrepo" / filename
        assert expected_names <= _owner_imports(consumer)

    registry = REPO_ROOT / "kicad_tooling/hwrepo/models.py"
    legacy_imports: list[str] = []
    for source in sorted((REPO_ROOT / "kicad_tooling").rglob("*.py")):
        if source == registry or source == owner_path:
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            if node.module == "models" or node.module.endswith(".models"):
                legacy_imports.extend(
                    f"{source.relative_to(REPO_ROOT)}:{alias.name}"
                    for alias in node.names
                    if alias.name in MODEL_NAMES
                )
    assert not legacy_imports, f"Internal services still import simulation models: {legacy_imports}"
