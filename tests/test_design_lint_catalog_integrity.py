"""Validate rule catalog references and focused fixture selection metadata."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint import rule_catalog
from tests.test_design_lint_catalog_fixtures import _PARITY_FIXTURES_BY_RULE

pytestmark = [pytest.mark.design_lint, pytest.mark.architecture]


@pytest.mark.parity_lint
def test_cli_mcp_fault_and_control_parity_is_reachable_by_rule_selector() -> None:
    """Keep cross-surface fault/control cases visible to focused lint gates."""
    rules = {entry.rule_id: entry for entry in rule_catalog().rules}
    for rule_id, expected_fields in _PARITY_FIXTURES_BY_RULE.items():
        entry = rules[rule_id]
        for field, references in expected_fields.items():
            catalogued = set(getattr(entry, field))
            assert set(references) <= catalogued, (
                f"{rule_id}: {field} omits CLI/MCP fixture references "
                f"{sorted(set(references) - catalogued)}"
            )


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
