"""Keep signal-path requirement models in their focused PCB owner module."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import models as shared_models
from kicad_tooling.hwrepo import pcb_drc_models, pcb_signal_path_rule_models
from kicad_tooling.hwrepo.design_lint_pcb_reference_via_candidate import RULE_ID
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, REPO_ROOT
from tests.lint_architecture_support import line_count as _line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.pcb_lint, pytest.mark.architecture]

SIGNAL_PATH_RULE_MODEL_NAMES = (
    "PcbDrcMinMaxRequirement",
    "PcbDrcMaximumRequirement",
    "PcbDrcPadSelectorPattern",
    "PcbSignalPathRequirement",
    "PcbSignalPathBundleRequirement",
    "PcbSignalPathRuleMap",
)


def _top_level_definitions() -> set[str]:
    tree = ast.parse((HWREPO / "pcb_signal_path_rule_models.py").read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            result.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            result.update(target.id for target in targets if isinstance(target, ast.Name))
    return result


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_signal_path_requirement_models_have_a_focused_owner_and_compatibility_exports() -> None:
    owner = HWREPO / "pcb_signal_path_rule_models.py"
    assert _line_count(owner) < IMPLEMENTATION_MAX_LINES
    assert set(SIGNAL_PATH_RULE_MODEL_NAMES) <= _top_level_definitions()
    for name in SIGNAL_PATH_RULE_MODEL_NAMES:
        model = getattr(pcb_signal_path_rule_models, name)
        assert getattr(pcb_drc_models, name) is model
        assert getattr(shared_models, name) is model


@pytest.mark.design_lint_rule(rule_id=RULE_ID)
def test_internal_signal_path_services_import_requirements_from_their_owner() -> None:
    legacy_imports: list[str] = []
    for path in sorted((REPO_ROOT / "kicad_tooling").rglob("*.py")):
        if path in {
            HWREPO / "models.py",
            HWREPO / "pcb_drc_models.py",
            HWREPO / "pcb_signal_path_rule_models.py",
        }:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and node.module.endswith("pcb_drc_models")
                and any(alias.name in SIGNAL_PATH_RULE_MODEL_NAMES for alias in node.names)
            ):
                legacy_imports.append(path.relative_to(REPO_ROOT).as_posix())
    assert not legacy_imports, (
        "Internal signal-path services should import requirements from "
        f"pcb_signal_path_rule_models; legacy imports: {legacy_imports}"
    )
