"""Keep PCB test-access models in a bounded theme-owned module."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import model_primitives, pcb_test_access_models
from kicad_tooling.hwrepo import models as compatibility_models
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.architecture]

MODEL_NAMES = (
    "TestAccessProbeEnvelope",
    "PcbAccessProbeRequest",
    "PcbAccessProbeRequestSet",
    "TestAccessEndpointRequirement",
    "RequiredTestAccess",
    "ExcludedTestAccess",
    "TestAccessDecision",
    "PcbAccessAnalysis",
    "TestAccessAnalysis",
)
MODEL_CLASS_NAMES = tuple(name for name in MODEL_NAMES if name != "TestAccessDecision")


def _top_level_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return names


def _top_level_classes(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.ClassDef)}


def test_pcb_test_access_models_have_bounded_owner_and_compatibility_exports() -> None:
    owner_path = REPO_ROOT / "kicad_tooling/hwrepo/pcb_test_access_models.py"
    registry_path = REPO_ROOT / "kicad_tooling/hwrepo/models.py"

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert set(MODEL_NAMES) <= _top_level_names(owner_path)
    assert not (set(MODEL_CLASS_NAMES) & _top_level_classes(registry_path))
    for name in MODEL_NAMES:
        assert getattr(compatibility_models, name) is getattr(pcb_test_access_models, name)
    assert compatibility_models.NetName is model_primitives.NetName


def test_internal_services_import_test_access_models_from_their_owner() -> None:
    legacy_imports: list[str] = []
    tooling_root = REPO_ROOT / "kicad_tooling"
    for source in sorted(tooling_root.rglob("*.py")):
        if source == tooling_root / "hwrepo/models.py":
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
                    if alias.name in MODEL_NAMES
                )

    assert not legacy_imports, (
        "Internal services must import PCB test-access models from their owner; "
        f"legacy imports: {legacy_imports}"
    )
