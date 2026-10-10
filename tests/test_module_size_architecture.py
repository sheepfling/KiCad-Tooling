"""Prevent new oversized Python modules and track existing size debt."""

from __future__ import annotations

import json
from pathlib import Path

from tests.lint_architecture_support import REPO_ROOT, line_count

LINE_LIMIT = 500
CEILINGS_PATH = Path(__file__).with_name("python_module_line_ceilings.json")
MODULE_ROOTS = ("kicad_tooling", "scripts", "tests")


def _python_modules() -> dict[str, Path]:
    return {
        path.relative_to(REPO_ROOT).as_posix(): path
        for root in MODULE_ROOTS
        for path in sorted((REPO_ROOT / root).rglob("*.py"))
        if "__pycache__" not in path.parts
    }


def test_oversized_python_modules_are_explicit_legacy_and_must_shrink() -> None:
    document = json.loads(CEILINGS_PATH.read_text(encoding="utf-8"))
    assert document.get("line_limit") == LINE_LIMIT
    ceilings = document.get("ceilings")
    assert isinstance(ceilings, dict)

    modules = _python_modules()
    module_sizes = {path: line_count(source) for path, source in modules.items()}
    oversized = {path: lines for path, lines in module_sizes.items() if lines >= LINE_LIMIT}
    missing = sorted(set(oversized) - set(ceilings))
    stale = sorted(set(ceilings) - set(oversized))
    assert not missing, (
        "New Python modules must stay below 500 lines; split oversized modules or document a "
        f"reviewed exception: {missing}"
    )
    assert not stale, f"Remove size ceilings after modules shrink below 500 lines: {stale}"

    invalid = {
        path: limit
        for path, limit in ceilings.items()
        if path not in modules or not isinstance(limit, int) or limit < LINE_LIMIT
    }
    assert not invalid, f"Invalid or missing legacy module ceilings: {invalid}"
    growth = {
        path: {"current": oversized[path], "ceiling": limit}
        for path, limit in ceilings.items()
        if oversized[path] > limit
    }
    assert not growth, f"Do not grow existing oversized Python modules: {growth}"
