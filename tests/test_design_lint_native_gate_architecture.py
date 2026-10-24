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


def _native_switches(nodes: ast.AST | tuple[ast.AST, ...]) -> frozenset[str]:
    roots = nodes if isinstance(nodes, tuple) else (nodes,)
    switches: set[str] = set()
    for root in roots:
        for node in ast.walk(root):
            if (
                isinstance(node, ast.Call)
                and ast.unparse(node.func) in {"os.environ.get", "os.getenv"}
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                value = node.args[0].value
                if isinstance(value, str) and re.fullmatch(r"KICAD_RUN_NATIVE_[A-Z0-9_]+", value):
                    switches.add(value)
            if (
                isinstance(node, ast.Subscript)
                and ast.unparse(node.value) == "os.environ"
                and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)
                and re.fullmatch(r"KICAD_RUN_NATIVE_[A-Z0-9_]+", node.slice.value)
            ):
                switches.add(node.slice.value)
    return frozenset(switches)


def _fixture_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    return {
        argument.arg
        for argument in (
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
        )
        if argument.arg not in {"self", "cls"}
    }


def _usefixture_names(nodes: tuple[ast.AST, ...]) -> set[str]:
    names: set[str] = set()
    for root in nodes:
        for node in ast.walk(root):
            if (
                not isinstance(node, ast.Call)
                or ast.unparse(node.func) != "pytest.mark.usefixtures"
            ):
                continue
            names.update(
                fixture
                for argument in node.args
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str)
                for fixture in argument.value.split()
            )
    return names


def _pytest_fixture_name(function: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    for decorator in function.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if ast.unparse(target) != "pytest.fixture":
            continue
        if isinstance(decorator, ast.Call):
            for keyword in decorator.keywords:
                if (
                    keyword.arg == "name"
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                ):
                    return keyword.value.value
        return function.name
    return None


def _fixture_index(
    tests_root: Path,
    parsed_modules: dict[Path, ast.Module],
) -> dict[str, list[tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef]]]:
    fixtures: dict[str, list[tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef]]] = {}
    for source_path in tests_root.rglob("*.py"):
        tree = parsed_modules.get(source_path)
        if tree is None:
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            parsed_modules[source_path] = tree
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = _pytest_fixture_name(node)
            if name is not None:
                fixtures.setdefault(name, []).append((source_path, node))
    return fixtures


def _fixture_dependency_switches(
    names: set[str],
    fixtures: dict[str, list[tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef]]],
) -> frozenset[str]:
    pending = set(names)
    visited: set[tuple[Path, int]] = set()
    switches: set[str] = set()
    while pending:
        name = pending.pop()
        for source_path, function in fixtures.get(name, ()):
            identity = (source_path, function.lineno)
            if identity in visited:
                continue
            visited.add(identity)
            switches.update(_native_switches(function))
            dependencies = _fixture_names(function)
            dependencies.update(_usefixture_names(tuple(function.decorator_list)))
            pending.update(dependencies)
    return frozenset(switches)


def _fixture_reference_native_switches(
    reference: str,
    tests_root: Path,
    parsed_modules: dict[Path, ast.Module],
    fixtures: dict[str, list[tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef]]],
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
            dependencies = _fixture_names(function)
            dependencies.update(_usefixture_names(tuple(marked_nodes)))
            switches = set(_native_switches(tuple(marked_nodes)))
            switches.update(_fixture_dependency_switches(dependencies, fixtures))
            return frozenset(switches)
    return None


def test_native_catalog_fixtures_require_rule_tag_lanes() -> None:
    tests_root = Path(__file__).parent
    parsed_modules: dict[Path, ast.Module] = {}
    fixtures = _fixture_index(tests_root, parsed_modules)
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
        observed_switches: set[str] = set()
        for reference in references:
            switches = _fixture_reference_native_switches(
                reference,
                tests_root,
                parsed_modules,
                fixtures,
            )
            if switches is None:
                continue
            native_references.append(reference)
            observed_switches.update(switches)
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
            assert declared_switches == observed_switches, (
                f"{rule.rule_id} required_native_fixtures do not match its native fixture "
                f"dependency gates; missing={sorted(observed_switches - declared_switches)}, "
                f"unused={sorted(declared_switches - observed_switches)}"
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


def test_two_pin_native_fault_control_cases_are_selectable_by_rule() -> None:
    rules = {rule.rule_id: rule for rule in rule_catalog().rules}
    native_fixture = "KICAD_RUN_NATIVE_TWO_PIN_COMPONENT_FIXTURES"
    fixture_module = "tests.test_two_pin_component_native_fixture_lane"
    test_refs = {
        "component.two_pin_passive_same_net": (
            f"{fixture_module}.test_native_two_pin_passive_same_net_fault_and_control",
            f"{fixture_module}.test_passive_native_fixture_scope_contains_only_passive_faults_and_controls",
        ),
        "component.two_pin_buzzer_same_net": (
            f"{fixture_module}.test_native_two_pin_buzzer_same_net_fault_and_control",
            f"{fixture_module}.test_buzzer_native_fixture_scope_contains_only_buzzer_fault_and_control",
        ),
        "component.two_pin_speaker_same_net": (
            f"{fixture_module}.test_native_two_pin_speaker_same_net_fault_and_control",
            f"{fixture_module}.test_speaker_native_fixture_scope_contains_only_speaker_fault_and_control",
        ),
        "component.two_pin_fuse_same_net": (
            f"{fixture_module}.test_native_two_pin_fuse_same_net_fault_and_control",
            f"{fixture_module}.test_fuse_native_fixture_scope_contains_only_fuse_faults_and_controls",
        ),
        "component.two_pin_ferrite_same_net": (
            f"{fixture_module}.test_native_two_pin_ferrite_same_net_fault_and_control",
            f"{fixture_module}.test_ferrite_native_fixture_scope_contains_only_ferrite_fault_and_control",
        ),
        "component.two_pin_diode_same_net": (
            f"{fixture_module}.test_native_two_pin_diode_same_net_fault_and_control",
            f"{fixture_module}.test_diode_native_fixture_scope_contains_only_diode_fault_and_control",
        ),
        "component.two_pin_crystal_same_net": (
            f"{fixture_module}.test_native_two_pin_crystal_same_net_fault_and_control",
            f"{fixture_module}.test_crystal_native_fixture_scope_contains_only_crystal_fault_and_control",
        ),
        "component.two_pin_switch_same_net": (
            f"{fixture_module}.test_native_two_pin_switch_same_net_fault_and_control",
            f"{fixture_module}.test_switch_native_fixture_scope_contains_only_switch_fault_and_control",
        ),
    }
    for rule_id, (native_test_ref, scope_test_ref) in test_refs.items():
        rule = rules[rule_id]
        assert native_fixture in rule.required_native_fixtures
        for test_ref in (native_test_ref, scope_test_ref):
            assert test_ref in rule.fault_fixtures
            assert test_ref in rule.valid_control_fixtures
