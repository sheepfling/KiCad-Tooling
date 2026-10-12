"""Require catalogued exact-native lint regressions to select their tag lanes."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog
from scripts.lint_gate_scope import (
    parse_tag_message,
    required_native_fixtures_by_rule,
)
from tests.execution_test_markers import execution_markers_for_path

pytestmark = [pytest.mark.design_lint, pytest.mark.catalog_lint, pytest.mark.architecture]


def _has_exact_native_marker(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Attribute) and ast.unparse(child) == "pytest.mark.native_kicad"
        for child in ast.walk(node)
    )


def _fixture_reference_native_switches(
    reference: str,
    tests_root: Path,
    parsed_modules: dict[Path, ast.Module],
) -> frozenset[str] | None:
    parts = reference.split(".")
    module = ".".join(parts[:2])
    source_path = tests_root.parent.joinpath(*module.split(".")).with_suffix(".py")
    tree = parsed_modules.get(source_path)
    if tree is None:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        parsed_modules[source_path] = tree
    module_markers = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "pytestmark" for target in node.targets
        )
    ]
    class_names = parts[2:-1]
    function_name = parts[-1]
    path = source_path.relative_to(tests_root.parent).as_posix()
    owners: list[ast.ClassDef | None] = []
    if class_names:
        owners = [
            owner
            for owner in ast.walk(tree)
            if isinstance(owner, ast.ClassDef) and owner.name == class_names[-1]
        ]
    else:
        owners = [None]

    for owner in owners:
        functions = tree.body if owner is None else owner.body
        for function in functions:
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if function.name != function_name:
                continue
            marked_nodes: list[ast.AST] = [*module_markers, *function.decorator_list]
            if owner is not None:
                marked_nodes.extend(owner.decorator_list)
            if not (
                any(_has_exact_native_marker(node) for node in marked_nodes)
                or "native_kicad" in execution_markers_for_path(path)
            ):
                continue
            switches = {
                child.value
                for node in marked_nodes
                for child in ast.walk(node)
                if isinstance(child, ast.Constant)
                and isinstance(child.value, str)
                and re.fullmatch(r"KICAD_RUN_NATIVE_[A-Z0-9_]+", child.value)
            }
            return frozenset(switches)
    return None


def test_native_catalog_fixtures_require_rule_tag_lanes() -> None:
    tests_root = Path(__file__).parent
    parsed_modules: dict[Path, ast.Module] = {}
    for rule in rule_catalog().rules:
        if rule.status != "active":
            continue
        references = (
            *rule.fault_fixtures,
            *rule.valid_control_fixtures,
            *rule.metamorphic_fixtures,
        )
        native_references: list[str] = []
        declared_switches = set(rule.required_native_fixtures)
        for reference in references:
            switches = _fixture_reference_native_switches(
                reference,
                tests_root,
                parsed_modules,
            )
            if switches is None:
                continue
            native_references.append(reference)
            assert switches <= declared_switches, (
                f"{rule.rule_id} does not require native fixture switches "
                f"{sorted(switches - declared_switches)} declared by {reference}"
            )
        if native_references:
            assert rule.required_native_fixtures, (
                f"{rule.rule_id} catalogues exact-native regressions without a required "
                f"Native-Fixture lane: {native_references}"
            )
        if rule.required_native_fixtures:
            assert native_references, (
                f"{rule.rule_id} requires a Native-Fixture lane without a catalogued "
                "exact-native regression"
            )


def test_workflow_enables_every_native_fixture_regression() -> None:
    repository = Path(__file__).resolve().parents[1]
    gated_fixtures: set[str] = set()
    for path in (repository / "tests").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        gated_fixtures.update(
            re.findall(
                r"os\.environ\.get\([\"'](KICAD_RUN_NATIVE_[A-Z0-9_]+)[\"']\)",
                source,
            )
        )
    workflow = (repository / ".github/workflows/tooling.yml").read_text(encoding="utf-8")
    package_gate = workflow.split(
        "      - name: Check tooling and installed wheel against a separate project\n", 1
    )[1].split("      - name: Keep stage logs", 1)[0]
    assert "run: python scripts/ci.py --project-root build/acceptance-template" in package_gate
    configured_fixtures = set(
        re.findall(
            r"^\s*(KICAD_RUN_NATIVE_[A-Z0-9_]+):\s*['\"]1['\"]\s*$",
            package_gate,
            flags=re.MULTILINE,
        )
    )
    assert gated_fixtures
    assert gated_fixtures <= configured_fixtures
    native_fixtures_by_rule = required_native_fixtures_by_rule()
    active_rules = frozenset(native_fixtures_by_rule)
    for rule_id, required in native_fixtures_by_rule.items():
        assert set(required) <= configured_fixtures, rule_id
        assert set(required) <= gated_fixtures, rule_id
        tag_message = "\n".join(
            (f"Lint-Rule: {rule_id}", *(f"Native-Fixture: {fixture}" for fixture in required))
        )
        scope = parse_tag_message(
            tag_message,
            frozenset(configured_fixtures),
            active_rules,
            native_fixtures_by_rule,
        )
        assert set(scope.native_fixtures) == set(required), rule_id
