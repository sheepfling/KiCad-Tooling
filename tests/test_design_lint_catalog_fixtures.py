"""The shipped lint catalog is tied to implementation and fault/control regressions."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog

pytestmark = pytest.mark.design_lint


def _pytest_collects_class(owner: type) -> bool:
    return owner.__name__.startswith("Test") or any(
        base.__module__ == "unittest.case" and base.__name__ == "TestCase" for base in owner.__mro__
    )


def test_active_rules_reference_existing_regression_fixtures() -> None:
    """Validate locators and exercise only class cases pytest cannot collect."""
    pytest_class_tests: set[str] = set()
    legacy_class_tests: set[tuple[type, str]] = set()
    pytest_fixtures: set[str] = set()
    metamorphic_rules: set[str] = set()
    for entry in rule_catalog().rules:
        assert entry.fault_fixtures
        assert entry.valid_control_fixtures
        if entry.metamorphic_fixtures:
            metamorphic_rules.add(entry.rule_id)
        for name in (
            *entry.fault_fixtures,
            *entry.valid_control_fixtures,
            *entry.metamorphic_fixtures,
        ):
            parts = name.split(".")
            module = None
            module_length = 0
            for length in range(len(parts) - 1, 0, -1):
                try:
                    module = importlib.import_module(".".join(parts[:length]))
                except ModuleNotFoundError:
                    continue
                module_length = length
                break
            assert module is not None, name
            attributes = parts[module_length:]
            owner = module
            for attribute in attributes[:-1]:
                owner = getattr(owner, attribute)
            target = getattr(owner, attributes[-1])
            assert callable(target), name
            if isinstance(owner, type):
                assert target.__name__.startswith("test_"), name
                if _pytest_collects_class(owner):
                    pytest_class_tests.add(name)
                else:
                    legacy_class_tests.add((owner, attributes[-1]))
            else:
                assert len(attributes) == 1, name
                assert target.__name__.startswith("test_"), name
                pytest_fixtures.add(name)

    assert len(metamorphic_rules) >= 2
    assert pytest_class_tests, "catalog should support pytest-collected class methods"
    assert pytest_fixtures, "catalog should support pytest function fixtures"
    for owner, method_name in sorted(
        legacy_class_tests,
        key=lambda item: (item[0].__module__, item[0].__qualname__, item[1]),
    ):
        getattr(owner(), method_name)()


def test_catalog_implementation_references_resolve_to_sources_or_fixtures() -> None:
    repository = Path(__file__).resolve().parents[1]
    for rule in rule_catalog().rules:
        for reference in rule.implementation_refs:
            target, separator, symbol = reference.partition("#")
            target_path = (
                repository / target
                if "/" in target
                else repository.joinpath(*target.split(".")).with_suffix(".py")
            )
            assert target_path.is_file(), f"{rule.rule_id}: missing implementation {target}"
            if not separator or target_path.suffix != ".py":
                continue
            module = ast.parse(target_path.read_text(encoding="utf-8"))
            names = {
                node.name
                for node in module.body
                if isinstance(node, (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef))
            }
            names.update(
                alias.asname or alias.name
                for node in module.body
                if isinstance(node, ast.ImportFrom)
                for alias in node.names
            )
            assert symbol in names, (
                f"{rule.rule_id}: {reference} does not resolve to a top-level source symbol"
            )


def test_every_rule_fixture_module_has_design_lint_selection_marker() -> None:
    repository = Path(__file__).resolve().parents[1]
    for rule in rule_catalog().rules:
        for field in ("fault_fixtures", "valid_control_fixtures", "metamorphic_fixtures"):
            for fixture in getattr(rule, field):
                module_name = ".".join(fixture.split(".")[:2])
                module_path = repository.joinpath(*module_name.split(".")).with_suffix(".py")
                module = ast.parse(module_path.read_text(encoding="utf-8"))
                assignment = next(
                    (
                        node
                        for node in module.body
                        if isinstance(node, ast.Assign)
                        and any(
                            isinstance(target, ast.Name) and target.id == "pytestmark"
                            for target in node.targets
                        )
                    ),
                    None,
                )
                assert assignment is not None, f"{rule.rule_id}: {module_path} is not tagged"
                markers = {
                    node.attr
                    for node in ast.walk(assignment.value)
                    if isinstance(node, ast.Attribute)
                    and node.attr == "design_lint"
                    and isinstance(node.value, ast.Attribute)
                    and node.value.attr == "mark"
                    and isinstance(node.value.value, ast.Name)
                    and node.value.value.id == "pytest"
                }
                assert "design_lint" in markers, (
                    f"{rule.rule_id}: {module_path} lacks the design_lint marker"
                )
