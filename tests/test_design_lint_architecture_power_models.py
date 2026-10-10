"""Keep power contract records in their theme-owned model modules."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import models as shared_models
from kicad_tooling.hwrepo import power_path_models, power_sequence_models
from tests.lint_architecture_support import (
    HWREPO,
    IMPLEMENTATION_MAX_LINES,
    REPO_ROOT,
    line_count,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.power_lint]

POWER_PATH_MODEL_NAMES = (
    "PowerPathEndpointRequirement",
    "PowerPathElementRequirement",
    "PowerPathRequirement",
    "PowerPathMap",
)
POWER_SEQUENCE_MODEL_NAMES = (
    "PowerSequenceEndpointRequirement",
    "PowerSequenceStageRequirement",
    "PowerSequenceDependencyRequirement",
    "PowerSequenceMap",
)


def test_power_models_have_bounded_theme_owners_and_compat_exports() -> None:
    owners = (
        ("power_path_models.py", power_path_models, POWER_PATH_MODEL_NAMES),
        ("power_sequence_models.py", power_sequence_models, POWER_SEQUENCE_MODEL_NAMES),
    )
    for filename, owner_module, model_names in owners:
        owner = HWREPO / filename
        assert line_count(owner) < IMPLEMENTATION_MAX_LINES
        tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
        definitions = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
        assert set(model_names) <= definitions
        for name in model_names:
            model = getattr(owner_module, name)
            assert getattr(shared_models, name) is model
            assert (
                model.__module__
                == f"kicad_tooling.hwrepo.{owner_module.__name__.rsplit('.', 1)[-1]}"
            )


def test_internal_power_services_import_models_from_theme_owners() -> None:
    model_names = set(POWER_PATH_MODEL_NAMES) | set(POWER_SEQUENCE_MODEL_NAMES)
    legacy_imports: list[str] = []
    for scope in (REPO_ROOT / "kicad_tooling", REPO_ROOT / "tests"):
        for path in sorted(scope.rglob("*.py")):
            if path == HWREPO / "models.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or node.module is None:
                    continue
                is_compat_registry = (
                    node.level == 1 and node.module in {"models", "hwrepo.models"}
                ) or node.module == "kicad_tooling.hwrepo.models"
                if is_compat_registry:
                    imported = {item.name for item in node.names} & model_names
                    legacy_imports.extend(
                        f"{path.relative_to(REPO_ROOT)}: {name}" for name in sorted(imported)
                    )

    assert not legacy_imports, (
        "Power services and regression tests must import models from their theme owners; "
        f"compatibility imports: {legacy_imports}"
    )
