"""Keep the electrical-analysis contract out of the shared model registry."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import electrical_analysis_contract_models
from kicad_tooling.hwrepo import models as compatibility_models
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = pytest.mark.architecture

MODEL_NAMES = ("ElectricalAnalysisContract",)
CONSUMER_FILES = (
    "electrical.py",
    "electrical_charts.py",
    "electrical_evidence.py",
    "electrical_setup.py",
    "generation.py",
    "mcp_files.py",
)


def _imports(path: Path, module: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and (node.module == module or node.module.endswith(f".{module}"))
        for alias in node.names
    }


def test_electrical_analysis_contract_has_bounded_compatible_owner() -> None:
    owner_path = REPO_ROOT / "kicad_tooling/hwrepo/electrical_analysis_contract_models.py"
    registry_path = REPO_ROOT / "kicad_tooling/hwrepo/models.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"), filename=str(owner_path))
    registry_tree = ast.parse(
        registry_path.read_text(encoding="utf-8"), filename=str(registry_path)
    )
    owner_classes = {node.name for node in owner_tree.body if isinstance(node, ast.ClassDef)}
    registry_classes = {node.name for node in registry_tree.body if isinstance(node, ast.ClassDef)}

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert set(MODEL_NAMES) <= owner_classes
    assert not (set(MODEL_NAMES) & registry_classes)
    for name in MODEL_NAMES:
        model = getattr(electrical_analysis_contract_models, name)
        assert getattr(compatibility_models, name) is model
        assert model.__module__ == "kicad_tooling.hwrepo.electrical_analysis_contract_models"


def test_services_import_contract_from_owner_without_registry_cycles() -> None:
    owner_path = REPO_ROOT / "kicad_tooling/hwrepo/electrical_analysis_contract_models.py"
    registry_path = REPO_ROOT / "kicad_tooling/hwrepo/models.py"
    owner_imports_models = any(
        isinstance(node, ast.ImportFrom)
        and node.module is not None
        and (node.module == "models" or node.module.endswith(".models"))
        for node in ast.walk(ast.parse(owner_path.read_text(encoding="utf-8")))
    )
    assert not owner_imports_models

    package = REPO_ROOT / "kicad_tooling/hwrepo"
    for filename in CONSUMER_FILES:
        source = package / filename
        assert set(MODEL_NAMES) <= _imports(source, "electrical_analysis_contract_models")

    legacy_imports: list[str] = []
    for source in sorted((REPO_ROOT / "kicad_tooling").rglob("*.py")):
        if source in {registry_path, owner_path}:
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
    assert not legacy_imports, f"Internal services still import through models.py: {legacy_imports}"
