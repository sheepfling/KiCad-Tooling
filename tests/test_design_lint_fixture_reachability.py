"""Check catalogued lint fixtures resolve to collected pytest tests."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from tests.design_lint_fixture_reachability import (
    RULE_FIXTURE_FIELDS,
    fixture_function_exists,
    fixture_module_path,
    pytest_discovers_fixture_target,
)
from tests.lint_architecture_support import HWREPO, REPO_ROOT, line_count

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.architecture,
]


@pytest.mark.rule_gate_integrity
def test_fixture_targets_follow_pytest_collection_names_and_class_controls() -> None:
    module = REPO_ROOT / "tests" / "test_fixture_target.py"
    assert pytest_discovers_fixture_target(module, (), "test_detects_the_fault")
    assert not pytest_discovers_fixture_target(module, (), "detects_the_fault")
    assert not pytest_discovers_fixture_target(
        REPO_ROOT / "tests" / "fixture_target.py", (), "test_detects_the_fault"
    )
    assert pytest_discovers_fixture_target(module, ("FixtureTargetTests",), "test_fault")
    assert not pytest_discovers_fixture_target(module, ("FixtureTargetHelper",), "test_fault")

    collectable = ast.parse("class FixtureTargetTests:\n    def test_fault(self): ...\n")
    with_initializer = ast.parse(
        "class FixtureTargetTests:\n    def __init__(self): ...\n    def test_fault(self): ...\n"
    )
    assert fixture_function_exists(collectable, ("FixtureTargetTests",), "test_fault")
    assert not fixture_function_exists(with_initializer, ("FixtureTargetTests",), "test_fault")


@pytest.mark.rule_gate_integrity
def test_active_rule_fixture_references_resolve_to_pytest_discoverable_tests() -> None:
    catalog = json.loads((HWREPO / "design-lint-rules.json").read_text(encoding="utf-8"))
    trees: dict[Path, ast.Module] = {}
    missing: list[str] = []
    for rule in catalog["rules"]:
        if rule.get("status") != "active":
            continue
        for field in RULE_FIXTURE_FIELDS:
            for reference in rule.get(field, []):
                module_path = fixture_module_path(reference)
                if module_path is None:
                    missing.append(reference)
                    continue
                parts = reference.split(".")
                module_parts = module_path.relative_to(REPO_ROOT).with_suffix("").parts
                if module_parts[-1] == "__init__":
                    module_parts = module_parts[:-1]
                node_parts = parts[len(module_parts) :]
                if not node_parts:
                    missing.append(reference)
                    continue
                if module_path not in trees:
                    trees[module_path] = ast.parse(
                        module_path.read_text(encoding="utf-8"), filename=str(module_path)
                    )
                tree = trees[module_path]
                owner_names = tuple(node_parts[:-1])
                function_name = node_parts[-1]
                if not fixture_function_exists(tree, owner_names, function_name) or not (
                    pytest_discovers_fixture_target(module_path, owner_names, function_name)
                ):
                    missing.append(reference)

    assert not missing, f"Active rule fixture references must resolve to pytest tests: {missing}"


@pytest.mark.rule_gate_integrity
def test_fixture_reachability_owners_stay_under_the_architecture_limit() -> None:
    paths = (
        Path(__file__),
        REPO_ROOT / "tests" / "design_lint_fixture_reachability.py",
    )
    sizes = {path.name: line_count(path) for path in paths}
    oversized = {name: size for name, size in sizes.items() if size >= 500}
    assert not oversized, f"Keep fixture reachability owners below 500 lines: {oversized}"
