"""Keep connector return-distribution contracts in their theme-owned module."""

from __future__ import annotations

import ast
from pathlib import Path
from types import MappingProxyType

import pytest

from kicad_tooling.hwrepo import connector_return_distribution_models
from kicad_tooling.hwrepo import models as shared_models
from tests.lint_architecture_support import IMPLEMENTATION_MAX_LINES, REPO_ROOT, line_count

pytestmark = [pytest.mark.design_lint, pytest.mark.connector_lint, pytest.mark.architecture]

MODEL_NAMES = (
    "ConnectorReturnDistributionRequirement",
    "ConnectorReturnDistributionMap",
    "ConnectorReturnDistributionEntry",
    "ConnectorReturnDistributionCoverageReport",
)

EXPECTED_OWNER_IMPORTS = MappingProxyType(
    {
        "kicad_tooling/hwrepo/connector_return_distribution.py": frozenset(MODEL_NAMES),
        "kicad_tooling/hwrepo/design_lint_component_coverage.py": frozenset(
            {
                "ConnectorReturnDistributionCoverageReport",
                "ConnectorReturnDistributionMap",
            }
        ),
        "kicad_tooling/hwrepo/design_lint_evaluator.py": frozenset(
            {
                "ConnectorReturnDistributionCoverageReport",
            }
        ),
        "kicad_tooling/hwrepo/design_lint_report_models.py": frozenset(
            {
                "ConnectorReturnDistributionCoverageReport",
            }
        ),
        "kicad_tooling/hwrepo/design_lint_candidate_aggregation.py": frozenset(
            {
                "ConnectorReturnDistributionCoverageReport",
            }
        ),
        "kicad_tooling/hwrepo/design_lint_evaluation_types.py": frozenset(
            {
                "ConnectorReturnDistributionCoverageReport",
            }
        ),
        "kicad_tooling/hwrepo/design_lint_return_distribution_candidates.py": frozenset(
            {
                "ConnectorReturnDistributionCoverageReport",
            }
        ),
        "kicad_tooling/hwrepo/design_lint_missing_evidence.py": frozenset(
            {
                "ConnectorReturnDistributionCoverageReport",
            }
        ),
    }
)


def _top_level_class_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    return {node.name for node in tree.body if isinstance(node, ast.ClassDef)}


def test_connector_return_distribution_models_have_a_theme_owner_and_compatible_exports() -> None:
    owner_path = REPO_ROOT / "kicad_tooling/hwrepo/connector_return_distribution_models.py"
    registry_path = REPO_ROOT / "kicad_tooling/hwrepo/models.py"

    assert line_count(owner_path) < IMPLEMENTATION_MAX_LINES
    assert set(MODEL_NAMES) <= _top_level_class_names(owner_path)
    assert not (set(MODEL_NAMES) & _top_level_class_names(registry_path))
    for name in MODEL_NAMES:
        assert getattr(shared_models, name) is getattr(connector_return_distribution_models, name)


def test_internal_services_import_connector_return_models_from_the_theme_owner() -> None:
    package = REPO_ROOT / "kicad_tooling"
    registry = package / "hwrepo/models.py"
    legacy_imports: list[str] = []
    owner_imports: dict[str, set[str]] = {}

    for source in sorted(package.rglob("*.py")):
        if source == registry:
            continue
        relative_path = source.relative_to(REPO_ROOT).as_posix()
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=relative_path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            imported = {alias.name for alias in node.names} & set(MODEL_NAMES)
            if not imported:
                continue
            if node.module == "connector_return_distribution_models" or node.module.endswith(
                ".connector_return_distribution_models"
            ):
                owner_imports.setdefault(relative_path, set()).update(imported)
            elif node.module == "models" or node.module.endswith(".models"):
                legacy_imports.extend(f"{relative_path}:{name}" for name in sorted(imported))

    assert not legacy_imports, (
        "Internal services must import connector return-distribution models from their owner: "
        f"{legacy_imports}"
    )
    for source, expected_names in EXPECTED_OWNER_IMPORTS.items():
        assert expected_names <= owner_imports.get(source, set()), (
            f"{source} must import connector models from their owner; missing "
            f"{sorted(expected_names - owner_imports.get(source, set()))}"
        )
