"""Guard PCB keepout model ownership and compatibility boundaries."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import model_primitives, pcb_keepout_models
from kicad_tooling.hwrepo import models as shared_models
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.architecture]

KEEP_OUT_MODEL_NAMES = (
    "PcbKeepoutRequirement",
    "PcbKeepoutMap",
    "PcbKeepoutCoverageEntry",
    "PcbKeepoutCoverageReport",
)


def test_pcb_keepout_models_have_a_theme_owner_and_compatible_exports() -> None:
    owner_path = REPO_ROOT / "kicad_tooling/hwrepo/pcb_keepout_models.py"
    registry_path = REPO_ROOT / "kicad_tooling/hwrepo/models.py"
    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES

    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    owner_definitions = {node.name for node in owner_tree.body if isinstance(node, ast.ClassDef)}
    registry_tree = ast.parse(registry_path.read_text(encoding="utf-8"))
    registry_definitions = {
        node.name for node in registry_tree.body if isinstance(node, ast.ClassDef)
    }

    assert set(KEEP_OUT_MODEL_NAMES) <= owner_definitions
    assert not (set(KEEP_OUT_MODEL_NAMES) & registry_definitions)
    for name in KEEP_OUT_MODEL_NAMES:
        assert getattr(shared_models, name) is getattr(pcb_keepout_models, name)
    assert shared_models.NativePcbUuid is model_primitives.NativePcbUuid


def test_internal_pcb_keepout_services_import_models_from_the_theme_owner() -> None:
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
                    if alias.name in KEEP_OUT_MODEL_NAMES
                )

    assert not legacy_imports, (
        "Internal PCB keepout services should import models from pcb_keepout_models; "
        f"legacy imports: {legacy_imports}"
    )
