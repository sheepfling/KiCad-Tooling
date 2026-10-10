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

pytestmark = pytest.mark.design_lint

REVIEW_LIMIT = THEME_SUITE_MAX_LINES
LEGACY_LIMITS_PATH = TESTS / "lint_suite_line_ceilings.json"
NON_RULE_SUITES = {
    "test_lint_suite_architecture.py",
}


def _has_lint_marker(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name.startswith("Native"):
            return True
        if not isinstance(node, ast.Attribute):
            continue
        marker = node.value
        if (
            isinstance(marker, ast.Attribute)
            and marker.attr == "mark"
            and isinstance(marker.value, ast.Name)
            and marker.value.id == "pytest"
            and (node.attr == "design_lint" or node.attr.endswith("_lint"))
        ):
            return True
    return False


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
