"""Bound lint-marked regression suites and track legacy decomposition debt."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from tests.lint_architecture_support import (
    TESTS,
    THEME_SUITE_MAX_LINES,
)
from tests.lint_architecture_support import (
    line_count as _line_count,
)

pytestmark = [pytest.mark.design_lint, pytest.mark.architecture]

REVIEW_LIMIT = THEME_SUITE_MAX_LINES
LEGACY_LIMITS_PATH = TESTS / "lint_suite_line_ceilings.json"
NATIVE_LINT_AREAS = {
    "component_lint",
    "connector_lint",
    "interface_lint",
    "power_lint",
    "evidence_lint",
    "return_path_lint",
    "schematic_lint",
    "pcb_lint",
}
NON_RULE_SUITES = {
    "test_lint_suite_architecture.py",
}


def _has_lint_marker(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name.startswith("Native"):
            return True
    return any(
        marker == "design_lint" or marker.endswith("_lint") for marker in _pytest_marker_names(tree)
    )


def _pytest_marker_names(tree: ast.AST) -> set[str]:
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "mark"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "pytest"
    }


def test_lint_marked_test_suites_are_small_or_shrinking_legacy() -> None:
    ceilings = json.loads(LEGACY_LIMITS_PATH.read_text(encoding="utf-8"))
    marked = {
        path.name: _line_count(path)
        for path in sorted(TESTS.glob("test_*.py"))
        if path.name not in NON_RULE_SUITES and _has_lint_marker(path)
    }
    oversized = {name: lines for name, lines in marked.items() if lines >= REVIEW_LIMIT}

    assert set(oversized) == set(ceilings), (
        "New lint-marked test suites must stay below 500 lines. Split an oversized suite, "
        "or explicitly record an existing suite for incremental decomposition; "
        f"untracked={sorted(set(oversized) - set(ceilings))}, "
        f"stale={sorted(set(ceilings) - set(oversized))}"
    )
    growth = {
        name: {"current": oversized[name], "ceiling": ceilings[name]}
        for name in ceilings
        if oversized[name] > ceilings[name]
    }
    assert not growth, f"Shrink legacy lint suites; do not grow them: {growth}"


def test_cli_mcp_parity_suites_stay_below_review_limit() -> None:
    modules = sorted(TESTS.glob("test_*mcp_parity*.py"))
    oversized = {
        path.name: _line_count(path) for path in modules if _line_count(path) >= REVIEW_LIMIT
    }

    assert not oversized, f"Split CLI/MCP parity suites by theme below 500 lines: {oversized}"
    assert not (TESTS / "test_mcp_parity.py").exists()


def test_architecture_suites_are_selectable_with_the_architecture_marker() -> None:
    missing = []
    for path in sorted(TESTS.glob("test_*architecture*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        if "architecture" not in _pytest_marker_names(tree):
            missing.append(path.name)

    assert not missing, f"Mark architecture suites for focused pytest selection: {missing}"


def test_exact_native_fixture_suites_have_selectable_native_markers() -> None:
    missing: dict[str, tuple[str, ...]] = {}
    for path in sorted(TESTS.glob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=path.name)
        native_gated_cases = (
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and any(
                "KICAD_RUN_NATIVE_" in decorator_source and "skip" in decorator_source.lower()
                for decorator_source in (
                    ast.unparse(decorator) for decorator in node.decorator_list
                )
            )
        )
        if next(native_gated_cases, None) is None:
            continue
        markers = _pytest_marker_names(tree)
        absent = tuple(
            marker for marker in ("design_lint", "native_kicad", "slow") if marker not in markers
        )
        if not markers.intersection(NATIVE_LINT_AREAS):
            absent = (*absent, "focused lint-area marker")
        if absent:
            missing[path.name] = absent

    assert not missing, (
        "Exact native lint fixtures need design_lint, a focused area, native_kicad, "
        f"and slow markers for test selection; missing={missing}"
    )
