"""Resolve a prerelease lint tag's review scope from its annotated message."""

from __future__ import annotations

import argparse
import ast
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from kicad_tooling.git import run_git_text
from kicad_tooling.pytest_scope import (
    pytest_collection_patterns,
    pytest_name_matches,
    validate_test_module_files,
    validate_test_module_paths,
)

LINT_AREAS = frozenset(
    {
        "design_lint",
        "catalog_lint",
        "architecture",
        "schematic_lint",
        "schematic_text_lint",
        "schematic_connectivity_lint",
        "schematic_hierarchy_lint",
        "component_lint",
        "connector_lint",
        "interface_lint",
        "power_lint",
        "evidence_lint",
        "pcb_lint",
        "pcb_reference_lint",
        "return_path_lint",
        "parity_lint",
    }
)
_NATIVE_FIXTURE_PATTERN = re.compile(
    r"^\s*(KICAD_RUN_NATIVE_[A-Z0-9_]+):\s*['\"]1['\"]\s*$", re.MULTILINE
)


@dataclass(frozen=True, slots=True)
class LintGateScope:
    area: str | None
    rule_id: str | None
    native_fixtures: tuple[str, ...]
    test_paths: tuple[str, ...] = ()

    @property
    def pytest_markexpr(self) -> str:
        if self.rule_id is not None:
            return (
                "design_lint and "
                f'(design_lint_rule(rule_id="{self.rule_id}") or rule_gate_integrity)'
            )
        if self.area is None:
            raise ValueError("lint gate scope has no selector")
        if self.area in {"design_lint", "architecture"}:
            return self.area
        return f"design_lint and {self.area}"


def configured_native_fixtures(repository: Path) -> frozenset[str]:
    """Return fixture switches already covered by the full acceptance workflow."""
    workflow = (repository / ".github/workflows/tooling.yml").read_text(encoding="utf-8")
    return frozenset(_NATIVE_FIXTURE_PATTERN.findall(workflow))


def active_design_lint_rule_ids() -> frozenset[str]:
    """Return active rule IDs from the installed package's validated catalog."""
    return frozenset(required_native_fixtures_by_rule())


def required_native_fixtures_by_rule() -> dict[str, tuple[str, ...]]:
    """Return required exact-native fixture switches for active rules."""
    from kicad_tooling.hwrepo.design_lint_catalog import rule_catalog

    return {
        str(rule.rule_id): tuple(rule.required_native_fixtures)
        for rule in rule_catalog().rules
        if rule.status == "active"
    }


def parse_tag_message(
    message: str,
    known_fixtures: frozenset[str],
    known_rule_ids: frozenset[str] = frozenset(),
    required_native_fixtures: Mapping[str, tuple[str, ...]] | None = None,
) -> LintGateScope:
    """Parse a lint selector, optional test modules, and native fixture switches."""
    selectors = [
        (key.strip(), value.strip())
        for key, separator, value in (line.partition(":") for line in message.splitlines())
        if separator and key.strip() in {"Lint-Area", "Lint-Rule"}
    ]
    if len(selectors) != 1:
        raise ValueError("tag message must declare exactly one Lint-Area or Lint-Rule")

    selector, value = selectors[0]
    if selector == "Lint-Area":
        if value not in LINT_AREAS:
            expected = ", ".join(sorted(LINT_AREAS))
            raise ValueError(f"tag message declares an unsupported Lint-Area ({expected})")
        area, rule_id = value, None
    else:
        if value not in known_rule_ids:
            raise ValueError(f"tag message names an unknown or inactive Lint-Rule: {value!r}")
        area, rule_id = None, value

    fixtures = [
        value.strip()
        for key, separator, value in (line.partition(":") for line in message.splitlines())
        if separator and key.strip() == "Native-Fixture"
    ]
    if len(fixtures) != len(set(fixtures)):
        raise ValueError("tag message declares a Native-Fixture more than once")
    unknown = set(fixtures) - known_fixtures
    if unknown:
        raise ValueError(
            f"tag message names fixtures absent from full acceptance: {sorted(unknown)}"
        )
    required = set((required_native_fixtures or {}).get(rule_id or "", ()))
    missing = required - set(fixtures)
    if missing:
        raise ValueError(
            f"Lint-Rule {rule_id!r} requires Native-Fixture declarations: {sorted(missing)}"
        )

    test_paths = validate_test_module_paths(
        value.strip()
        for key, separator, value in (line.partition(":") for line in message.splitlines())
        if separator and key.strip() == "Test-Path"
    )
    if test_paths and rule_id is not None:
        raise ValueError(
            "Test-Path cannot narrow a Lint-Rule selection; use its catalogued fixtures"
        )
    return LintGateScope(area, rule_id, tuple(fixtures), test_paths)


def read_tag_scope(tag_name: str, repository: Path) -> LintGateScope:
    """Read an annotated Git tag and validate its scoped-test declarations."""
    if not tag_name.startswith("v") or not re.fullmatch(r"[A-Za-z0-9.+_-]+", tag_name):
        raise ValueError(f"invalid version tag name: {tag_name!r}")
    result = run_git_text(
        repository,
        "cat-file",
        "tag",
        f"refs/tags/{tag_name}",
        check=False,
    )
    if result.returncode:
        raise ValueError(f"prerelease lint tag {tag_name} must be annotated")
    _, separator, message = result.stdout.partition("\n\n")
    if not separator:
        raise ValueError(f"annotated lint tag {tag_name} has no message")
    return read_message_scope(message, repository)


def read_message_scope(message: str, repository: Path) -> LintGateScope:
    """Validate a proposed tag message against this checkout's workflow and catalog."""
    native_fixtures_by_rule = required_native_fixtures_by_rule()
    scope = parse_tag_message(
        message,
        configured_native_fixtures(repository),
        frozenset(native_fixtures_by_rule),
        native_fixtures_by_rule,
    )
    validate_test_module_files(scope.test_paths, repository)
    _validate_native_fixture_test_paths(scope, repository)
    return scope


def _validate_native_fixture_test_paths(scope: LintGateScope, repository: Path) -> None:
    if not scope.test_paths or not scope.native_fixtures:
        return
    guarded: set[str] = set()
    _, class_patterns, function_patterns = pytest_collection_patterns(repository)
    for relative in scope.test_paths:
        tree = ast.parse((repository / relative).read_text(encoding="utf-8"))
        module_markers = tuple(_pytestmark_values(tree.body))
        for markers in _collected_test_markers(
            tree.body, module_markers, class_patterns, function_patterns
        ):
            if not any(_pytest_marker_name(marker) == "native_kicad" for marker in markers):
                continue
            for marker in markers:
                condition = _skipif_condition(marker)
                if condition is not None:
                    guarded.update(
                        fixture
                        for fixture in scope.native_fixtures
                        if _skipif_enables_fixture(condition, fixture)
                    )
    missing = set(scope.native_fixtures) - guarded
    if missing:
        raise ValueError(
            "Test-Path selection has no native_kicad test guarded by each declared "
            f"Native-Fixture switch: {sorted(missing)}"
        )


def _collected_test_markers(
    statements: Sequence[ast.stmt],
    inherited: tuple[ast.expr, ...],
    class_patterns: tuple[str, ...],
    function_patterns: tuple[str, ...],
) -> Sequence[tuple[ast.expr, ...]]:
    markers: list[tuple[ast.expr, ...]] = []
    for statement in statements:
        if isinstance(statement, ast.ClassDef):
            is_test_case = any(
                (path := _attribute_path(base)) and path[-1] == "TestCase"
                for base in statement.bases
            )
            if not pytest_name_matches(statement.name, class_patterns) and not is_test_case:
                continue
            class_markers = (
                *inherited,
                *statement.decorator_list,
                *_pytestmark_values(statement.body),
            )
            markers.extend(
                _collected_test_markers(
                    statement.body, class_markers, class_patterns, function_patterns
                )
            )
        elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if pytest_name_matches(statement.name, function_patterns):
                markers.append((*inherited, *statement.decorator_list))
    return tuple(markers)


def _pytestmark_values(statements: Sequence[ast.stmt]) -> Sequence[ast.expr]:
    values: list[ast.expr] = []
    for statement in statements:
        if isinstance(statement, ast.Assign):
            if not any(
                isinstance(target, ast.Name) and target.id == "pytestmark"
                for target in statement.targets
            ):
                continue
            value = statement.value
        elif (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == "pytestmark"
        ):
            value = statement.value
        else:
            continue
        if value is None:
            continue
        if isinstance(value, (ast.List, ast.Tuple)):
            values.extend(value.elts)
        else:
            values.append(value)
    return tuple(values)


def _attribute_path(node: ast.expr) -> tuple[str, ...]:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return tuple(reversed(parts))


def _pytest_marker_name(marker: ast.expr) -> str | None:
    target = marker.func if isinstance(marker, ast.Call) else marker
    path = _attribute_path(target)
    return path[-1] if len(path) >= 2 and path[-2] == "mark" else None


def _skipif_condition(marker: ast.expr) -> ast.expr | None:
    if _pytest_marker_name(marker) != "skipif" or not isinstance(marker, ast.Call):
        return None
    if marker.args:
        return marker.args[0]
    return next((keyword.value for keyword in marker.keywords if keyword.arg == "condition"), None)


def _skipif_enables_fixture(condition: ast.expr, fixture: str) -> bool:
    comparison = condition
    expected_operator: type[ast.cmpop] = ast.NotEq
    if isinstance(condition, ast.UnaryOp) and isinstance(condition.op, ast.Not):
        comparison = condition.operand
        expected_operator = ast.Eq
    return (
        isinstance(comparison, ast.Compare)
        and len(comparison.ops) == 1
        and isinstance(comparison.ops[0], expected_operator)
        and len(comparison.comparators) == 1
        and isinstance(comparison.comparators[0], ast.Constant)
        and comparison.comparators[0].value == "1"
        and _environment_lookup_is_fixture(comparison.left, fixture)
    )


def _environment_lookup_is_fixture(expression: ast.expr, fixture: str) -> bool:
    if isinstance(expression, ast.Call):
        path = _attribute_path(expression.func)
        is_environment_lookup = path[-1:] == ("getenv",) or path[-2:] == ("environ", "get")
        return (
            is_environment_lookup
            and bool(expression.args)
            and isinstance(expression.args[0], ast.Constant)
            and expression.args[0].value == fixture
        )
    if isinstance(expression, ast.Subscript):
        path = _attribute_path(expression.value)
        return (
            path[-1:] == ("environ",)
            and isinstance(expression.slice, ast.Constant)
            and expression.slice.value == fixture
        )
    return False


def write_github_scope(scope: LintGateScope, *, write_github_files: bool = True) -> None:
    """Publish validated values through GitHub Actions environment files."""
    output = os.environ.get("GITHUB_OUTPUT")
    if write_github_files and output:
        with Path(output).open("a", encoding="utf-8") as stream:
            stream.write(f"markexpr={scope.pytest_markexpr}\n")
            if scope.test_paths:
                stream.write(f"pytestpaths={','.join(scope.test_paths)}\n")
    else:
        print(f"markexpr={scope.pytest_markexpr}")
        if scope.test_paths:
            print(f"pytestpaths={','.join(scope.test_paths)}")

    environment = os.environ.get("GITHUB_ENV")
    if write_github_files and environment:
        with Path(environment).open("a", encoding="utf-8") as stream:
            stream.writelines(f"{fixture}=1\n" for fixture in scope.native_fixtures)
    else:
        for fixture in scope.native_fixtures:
            print(f"{fixture}=1")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--tag", help="Annotated prerelease Git tag to inspect")
    selector.add_argument(
        "--message-file",
        type=Path,
        help="Preflight a proposed annotated tag message before creating the tag",
    )
    args = parser.parse_args(argv)
    repository = Path(__file__).resolve().parents[1]
    if args.tag is not None:
        scope = read_tag_scope(args.tag, repository)
        write_github_scope(scope)
    else:
        message = args.message_file.read_text(encoding="utf-8")
        scope = read_message_scope(message, repository)
        write_github_scope(scope, write_github_files=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
