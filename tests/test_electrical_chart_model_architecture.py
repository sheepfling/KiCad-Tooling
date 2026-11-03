"""Keep chart receipt contracts owned by their focused electrical module."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import electrical_chart_models, models
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = pytest.mark.architecture

MODEL_NAMES = (
    "ElectricalChartCase",
    "ElectricalChartsReport",
    "ElectricalChartsSuiteReport",
)


def test_chart_models_have_bounded_owner_and_compatible_exports() -> None:
    owner = REPO_ROOT / "kicad_tooling/hwrepo/electrical_chart_models.py"
    registry = REPO_ROOT / "kicad_tooling/hwrepo/models.py"
    owner_classes = {
        node.name for node in ast.parse(owner.read_text()).body if isinstance(node, ast.ClassDef)
    }
    registry_classes = {
        node.name for node in ast.parse(registry.read_text()).body if isinstance(node, ast.ClassDef)
    }
    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert set(MODEL_NAMES) <= owner_classes
    assert not (set(MODEL_NAMES) & registry_classes)
    for name in MODEL_NAMES:
        model = getattr(electrical_chart_models, name)
        assert getattr(models, name) is model
        assert model.__module__ == "kicad_tooling.hwrepo.electrical_chart_models"


def test_production_consumers_import_chart_models_from_owner() -> None:
    package = REPO_ROOT / "kicad_tooling"
    for path in sorted(package.rglob("*.py")):
        if path.name in {"models.py", "electrical_chart_models.py"}:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            if node.module == "models" or node.module.endswith(".models"):
                assert not ({item.name for item in node.names} & set(MODEL_NAMES)), path
    for relative in (
        "hwrepo/electrical_charts.py",
        "hwrepo/mcp_new_workflows.py",
        "hwrepo/mcp_server.py",
        "hwrepo/review_overview_receipts.py",
        "electrical_charts.py",
    ):
        path: Path = package / relative
        imported = {
            item.name
            for node in ast.walk(ast.parse(path.read_text()))
            if isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.endswith("electrical_chart_models")
            for item in node.names
        }
        assert imported & set(MODEL_NAMES), path
