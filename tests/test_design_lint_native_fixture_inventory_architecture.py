"""Require a rule or scope decision for registered native lint suites."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.design_lint_test_markers import (
    design_lint_markers_for_path,
    design_lint_rule_ids_for_test,
)
from tests.execution_test_markers import execution_markers_for_path

pytestmark = [pytest.mark.design_lint, pytest.mark.catalog_lint, pytest.mark.architecture]

_NON_RULE_NATIVE_TESTS = {
    (
        "tests.test_can_native_fixture_lanes",
        None,
        "test_native_can_split_termination_fault_and_control",
    ): "The authored CAN termination contract checks its ordered topology and midpoint capacitor; it is distinct from the active direct-termination review heuristic.",
    (
        "tests.test_component_rating_native_fixture_lane",
        None,
        "test_component_and_connector_rating_controls_export_repeatably",
    ): "This native lane validates authored component and connector rating requirements; the design-lint catalog has no rating predicate.",
    (
        "tests.test_empty_netlist_evidence_native_fixture_lane",
        None,
        "test_native_empty_inventory_trigger_and_nonempty_control_on_supported_images",
    ): "This lane verifies native export evidence integrity for empty and nonempty netlists; it is not an active design-lint predicate.",
    (
        "tests.test_native_connector_return_lint",
        None,
        "test_native_netlist_distinguishes_split_and_common_return_domains",
    ): "This KiCad 10.0.6 public cohort sample supports analyzer comparison; the active return-net rules already have a rule-selectable KiCad 10.0.0 and 10.0.5 fault/control lane.",
    (
        "tests.test_pcb_access_native_fixture_lane",
        None,
        "test_native_probe_envelope_fixtures_on_supported_images",
    ): "This lane validates native PCB probe-envelope evidence for authored test-access requirements; no active design-lint rule owns that predicate.",
    (
        "tests.test_pcb_return_path_native_fixture_lane",
        None,
        "test_native_return_path_fixture_cases_on_supported_kicad",
    ): "This lane validates authored PCB copper-continuity cases; it does not implement a catalogued schematic return-label or PCB layout heuristic.",
}


class _TestFunctionReferences(ast.NodeVisitor):
    def __init__(self, module: str) -> None:
        self.module = module
        self.classes: list[str] = []
        self.references: list[tuple[str, str | None, str]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.classes.append(node.name)
        self.generic_visit(node)
        self.classes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name.startswith("test_"):
            self.references.append((self.module, ".".join(self.classes) or None, node.name))
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef


def _native_design_lint_test_functions(tests_root: Path) -> set[tuple[str, str | None, str]]:
    references: set[tuple[str, str | None, str]] = set()
    repository = tests_root.parent
    for path in tests_root.rglob("test_*.py"):
        relative_path = path.relative_to(repository).as_posix()
        if "native_kicad" not in execution_markers_for_path(relative_path):
            continue
        if "design_lint" not in design_lint_markers_for_path(relative_path):
            continue
        module = ".".join(path.relative_to(repository).with_suffix("").parts)
        visitor = _TestFunctionReferences(module)
        visitor.visit(ast.parse(path.read_text(encoding="utf-8"), filename=relative_path))
        references.update(visitor.references)
    return references


def test_native_design_lint_tests_are_catalogued_or_have_reviewed_scope() -> None:
    tests_root = Path(__file__).parent
    native_tests = _native_design_lint_test_functions(tests_root)
    unindexed = {
        reference for reference in native_tests if not design_lint_rule_ids_for_test(*reference)
    }
    expected = set(_NON_RULE_NATIVE_TESTS)
    assert unindexed == expected, (
        "Registered native design-lint tests need a rule fixture reference or an explicit scope review; "
        f"unreviewed={sorted(unindexed - expected)}, stale={sorted(expected - unindexed)}"
    )
    assert all(len(reason) >= 40 for reason in _NON_RULE_NATIVE_TESTS.values())
