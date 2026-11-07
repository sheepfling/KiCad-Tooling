"""Validate the catalog's regression fixture references."""

from __future__ import annotations

import importlib
from inspect import isclass

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog

pytestmark = pytest.mark.design_lint


def _pytest_collects_class(owner: type) -> bool:
    return (
        owner.__name__.startswith("Test")
        or owner.__name__.endswith("Tests")
        or any(
            base.__module__ == "unittest.case" and base.__name__ == "TestCase"
            for base in owner.__mro__
        )
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
            if isclass(owner):
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
