"""Shared source checks for active design-lint fixture references."""

from __future__ import annotations

import ast
import fnmatch
import tomllib
from functools import lru_cache
from pathlib import Path

from tests.lint_architecture_support import REPO_ROOT

RULE_FIXTURE_FIELDS = ("fault_fixtures", "valid_control_fixtures", "metamorphic_fixtures")


def fixture_module_path(reference: str) -> Path | None:
    """Find the Python module that owns a catalogued fixture reference."""
    parts = reference.split(".")
    if not parts or parts[0] != "tests":
        return None
    for end in range(len(parts), 1, -1):
        module = REPO_ROOT.joinpath(*parts[:end]).with_suffix(".py")
        if module.is_file():
            return module
        package = REPO_ROOT.joinpath(*parts[:end], "__init__.py")
        if package.is_file():
            return package
    return None


def fixture_function_exists(
    tree: ast.Module, owner_names: tuple[str, ...], function_name: str
) -> bool:
    """Check that a catalogued function or class method exists and can be collected."""
    body: list[ast.stmt] = tree.body
    for owner_name in owner_names:
        owner = next(
            (
                statement
                for statement in body
                if isinstance(statement, ast.ClassDef) and statement.name == owner_name
            ),
            None,
        )
        if owner is None or any(
            isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
            and statement.name == "__init__"
            for statement in owner.body
        ):
            return False
        body = owner.body
    return any(
        isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
        and statement.name == function_name
        for statement in body
    )


@lru_cache(maxsize=1)
def pytest_naming_options() -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Read pytest's effective discovery patterns from the repository config."""
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    options = config["tool"]["pytest"]["ini_options"]
    return (
        tuple(options.get("python_files", ("test_*.py",))),
        tuple(options.get("python_classes", ("Test",))),
        tuple(options.get("python_functions", ("test",))),
    )


def pytest_discovers_fixture_target(
    module_path: Path, owner_names: tuple[str, ...], function_name: str
) -> bool:
    """Check the configured pytest file, class, and function naming rules."""
    file_patterns, class_patterns, function_patterns = pytest_naming_options()
    return (
        any(fnmatch.fnmatchcase(module_path.name, pattern) for pattern in file_patterns)
        and all(
            any(fnmatch.fnmatchcase(name, pattern) for pattern in class_patterns)
            for name in owner_names
        )
        and any(fnmatch.fnmatchcase(function_name, pattern) for pattern in function_patterns)
    )
