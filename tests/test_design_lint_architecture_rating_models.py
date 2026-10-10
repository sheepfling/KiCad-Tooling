"""Keep source-bound component and contact rating models in theme owners."""

from __future__ import annotations

import ast

import pytest

from kicad_tooling.hwrepo import (
    component_rating_models,
    connector_contact_rating_models,
    mosfet_stress_models,
)
from kicad_tooling.hwrepo import (
    models as shared_models,
)
from tests.lint_architecture_support import (
    IMPLEMENTATION_MAX_LINES,
    REPO_ROOT,
    line_count,
)

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.component_lint,
    pytest.mark.connector_lint,
    pytest.mark.power_lint,
]

RATING_MODEL_OWNERS = {
    "component_rating_models.py": (
        component_rating_models,
        (
            "ComponentVoltageRatingRequirement",
            "ComponentVoltageRatingAnalysis",
            "ComponentPowerRatingRequirement",
            "ComponentPowerRatingAnalysis",
        ),
    ),
    "connector_contact_rating_models.py": (
        connector_contact_rating_models,
        (
            "ConnectorContactCurrentRequirement",
            "ConnectorContactRatingRequirement",
            "ConnectorContactRatingAnalysis",
        ),
    ),
    "mosfet_stress_models.py": (
        mosfet_stress_models,
        (
            "MosfetVoltageInterval",
            "MosfetOperatingState",
            "MosfetStressRequirement",
            "MosfetStressAnalysis",
        ),
    ),
}


def test_rating_models_live_in_theme_owners_and_registry_exports_keep_identity() -> None:
    registry_path = REPO_ROOT / "kicad_tooling/hwrepo/models.py"
    registry_tree = ast.parse(registry_path.read_text(encoding="utf-8"))
    registry_definitions = {
        node.name for node in registry_tree.body if isinstance(node, ast.ClassDef)
    }

    for filename, (owner_module, names) in RATING_MODEL_OWNERS.items():
        owner_path = REPO_ROOT / "kicad_tooling/hwrepo" / filename
        assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
        owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
        owner_definitions = {
            node.name for node in owner_tree.body if isinstance(node, ast.ClassDef)
        }
        assert set(names) <= owner_definitions
        assert not (set(names) & registry_definitions)
        for name in names:
            assert getattr(shared_models, name) is getattr(owner_module, name)


def test_internal_rating_services_import_models_from_the_theme_owners() -> None:
    model_names = {name for _, names in RATING_MODEL_OWNERS.values() for name in names}
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
                    if alias.name in model_names
                )

    assert not legacy_imports, (
        f"Internal rating services should import theme-owned models directly: {legacy_imports}"
    )
