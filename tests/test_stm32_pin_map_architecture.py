"""Keep STM32/CubeMX models owned by the interface theme."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo import model_primitives, stm32_pin_map_models
from kicad_tooling.hwrepo import models as shared_models
from tests.lint_architecture_support import HWREPO, IMPLEMENTATION_MAX_LINES, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.interface_lint,
    pytest.mark.architecture,
]

MODEL_NAMES = {
    "Stm32PinRequirement",
    "Stm32PinExclusion",
    "Stm32CubeMxPinMap",
    "Stm32PinMapMismatch",
    "Stm32UnmappedDevice",
    "Stm32PinMapCoverageReport",
}

MODEL_CONSUMERS = {
    HWREPO / "stm32_pin_map.py": {
        "Stm32CubeMxPinMap",
        "Stm32PinMapMismatch",
        "Stm32UnmappedDevice",
    },
    HWREPO / "design_lint_stm32_coverage.py": {
        "Stm32PinMapCoverageReport",
        "Stm32PinMapMismatch",
    },
    HWREPO / "design_lint_stm32_candidates.py": {"Stm32PinMapCoverageReport"},
    HWREPO / "design_lint_evaluation_types.py": {"Stm32PinMapCoverageReport"},
    HWREPO / "design_lint_evaluator.py": {"Stm32PinMapCoverageReport"},
    HWREPO / "design_lint_missing_evidence.py": {"Stm32PinMapCoverageReport"},
    HWREPO / "design_lint_candidate_aggregation.py": {"Stm32PinMapCoverageReport"},
    HWREPO / "design_lint_report_models.py": {"Stm32PinMapCoverageReport"},
    HWREPO.parents[0] / "ci_hosted_stm32_pin_map.py": {
        "Stm32CubeMxPinMap",
        "Stm32PinExclusion",
        "Stm32PinRequirement",
    },
}


def _imported_names(tree: ast.Module, module_suffix: str) -> set[str]:
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module is not None
        and (node.module == module_suffix or node.module.endswith(f".{module_suffix}"))
        for alias in node.names
    }


def test_stm32_models_have_a_theme_owner_and_compatibility_exports() -> None:
    owner = HWREPO / "stm32_pin_map_models.py"
    owner_tree = ast.parse(owner.read_text(encoding="utf-8"), filename=owner.name)
    owner_definitions = {node.name for node in owner_tree.body if isinstance(node, ast.ClassDef)}
    registry = HWREPO / "models.py"
    registry_tree = ast.parse(registry.read_text(encoding="utf-8"), filename=registry.name)
    registry_definitions = {
        node.name for node in registry_tree.body if isinstance(node, ast.ClassDef)
    }

    assert MODEL_NAMES <= owner_definitions
    assert not (MODEL_NAMES & registry_definitions)
    assert line_count(owner) < IMPLEMENTATION_MAX_LINES
    for name in MODEL_NAMES:
        assert getattr(shared_models, name) is getattr(stm32_pin_map_models, name)
    assert shared_models.Stm32PortPin is model_primitives.Stm32PortPin
    assert shared_models.Stm32SymbolPin is model_primitives.Stm32SymbolPin


def test_stm32_regressions_are_plain_pytest_functions() -> None:
    suite = Path(__file__).with_name("test_stm32_pin_map.py")
    tree = ast.parse(suite.read_text(encoding="utf-8"), filename=suite.name)
    tests = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    ]
    unittest_imports = [
        node
        for node in tree.body
        if isinstance(node, ast.Import) and any(alias.name == "unittest" for alias in node.names)
    ]
    unittest_classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and any("TestCase" in ast.unparse(base) for base in node.bases)
    ]

    assert len(tests) >= 10
    assert not unittest_imports
    assert not unittest_classes


@pytest.mark.parametrize(("consumer", "expected_models"), MODEL_CONSUMERS.items())
def test_stm32_services_import_models_from_owner(consumer: Path, expected_models: set[str]) -> None:
    tree = ast.parse(consumer.read_text(encoding="utf-8"), filename=consumer.name)
    owner_imports = _imported_names(tree, "stm32_pin_map_models")
    facade_imports = _imported_names(tree, "models")

    assert expected_models <= owner_imports, consumer.name
    assert not (MODEL_NAMES & facade_imports), consumer.name
