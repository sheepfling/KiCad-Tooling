"""Keep reviewed custom component-role contracts in their component-theme owner."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import component_role_models
from kicad_tooling.hwrepo import models as shared_models
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.component_lint, pytest.mark.architecture]

MODEL_NAMES = ("ComponentRolePin", "ComponentRoleBinding", "ComponentRoleMap")
EXPECTED_OWNER_IMPORTS = {
    "kicad_tooling/ci_hosted_ic_rail_capacitors.py": set(MODEL_NAMES),
    "kicad_tooling/ci_hosted_led_rail.py": set(MODEL_NAMES),
    "kicad_tooling/ci_hosted_two_pin_components.py": set(MODEL_NAMES),
    "kicad_tooling/hwrepo/component_roles.py": {"ComponentRoleBinding", "ComponentRoleMap"},
    "kicad_tooling/hwrepo/design_lint_candidate_aggregation.py": {"ComponentRoleMap"},
    "kicad_tooling/hwrepo/design_lint_component_candidates.py": {"ComponentRoleMap"},
    "kicad_tooling/hwrepo/design_lint_power_candidates.py": {"ComponentRoleMap"},
    "kicad_tooling/hwrepo/led_heuristics.py": {"ComponentRoleBinding", "ComponentRoleMap"},
    "kicad_tooling/hwrepo/two_pin_components.py": {"ComponentRoleBinding", "ComponentRoleMap"},
    "kicad_tooling/hwrepo/two_pin_passives.py": {"ComponentRoleBinding", "ComponentRoleMap"},
}


def _top_level_definitions(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names.update(target.id for target in targets if isinstance(target, ast.Name))
    return names


def test_component_role_models_live_in_owner_and_registry_exports_keep_identity() -> None:
    owner_path = REPO_ROOT / "kicad_tooling/hwrepo/component_role_models.py"
    registry_path = REPO_ROOT / "kicad_tooling/hwrepo/models.py"
    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
    registry_tree = ast.parse(registry_path.read_text(encoding="utf-8"))
    registry_classes = {node.name for node in registry_tree.body if isinstance(node, ast.ClassDef)}

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert set(MODEL_NAMES) <= _top_level_definitions(owner_tree)
    assert not (set(MODEL_NAMES) & registry_classes)
    for name in MODEL_NAMES:
        assert getattr(shared_models, name) is getattr(component_role_models, name)


def test_internal_component_role_services_import_models_from_owner() -> None:
    package = REPO_ROOT / "kicad_tooling"
    registry_path = package / "hwrepo/models.py"
    legacy_imports: list[str] = []
    actual_owner_imports: dict[str, set[str]] = {}

    for source in sorted(package.rglob("*.py")):
        if source == registry_path:
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            imported = {alias.name for alias in node.names}
            relative_path = source.relative_to(REPO_ROOT).as_posix()
            if node.module == "component_role_models" or node.module.endswith(
                ".component_role_models"
            ):
                actual_owner_imports.setdefault(relative_path, set()).update(
                    imported & set(MODEL_NAMES)
                )
            elif node.module == "models" or node.module.endswith(".models"):
                legacy_imports.extend(
                    f"{relative_path}:{name}" for name in sorted(imported & set(MODEL_NAMES))
                )

    assert not legacy_imports, (
        "Internal component-role services must import theme-owned models directly: "
        f"{legacy_imports}"
    )
    for source_name, expected in EXPECTED_OWNER_IMPORTS.items():
        assert expected <= actual_owner_imports.get(source_name, set()), (
            f"{source_name} must import component-role models from their owner: "
            f"missing {sorted(expected - actual_owner_imports.get(source_name, set()))}"
        )
