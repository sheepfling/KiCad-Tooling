"""Validation helpers for explicit pytest module selection."""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping, Sequence
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import cast

_INVALID_PORTABLE_PATH_CHARACTERS = frozenset('<>:"\\|?*')


def validate_test_module_paths(paths: Iterable[str]) -> tuple[str, ...]:
    """Validate canonical pytest module paths rooted beneath ``tests/``."""
    test_paths = tuple(paths)
    if len(test_paths) != len(set(test_paths)):
        raise ValueError("pytest test-module paths must be unique")
    for path in test_paths:
        candidate = PurePosixPath(path)
        if (
            path != candidate.as_posix()
            or candidate.is_absolute()
            or len(candidate.parts) < 2
            or candidate.parts[0] != "tests"
            or any(part in {".", ".."} for part in candidate.parts)
            or not candidate.name.startswith("test_")
            or candidate.suffix != ".py"
            or "," in path
            or any(character in path for character in _INVALID_PORTABLE_PATH_CHARACTERS)
        ):
            raise ValueError("pytest test-module paths must name Python test files beneath tests/")
    return test_paths


def validate_test_module_files(paths: Iterable[str], repository: Path) -> tuple[str, ...]:
    """Validate selected test paths and require each to resolve to a file in this checkout."""
    test_paths = validate_test_module_paths(paths)
    tests_root = (repository / "tests").resolve()
    missing_paths = tuple(
        path
        for path in test_paths
        if not (repository / path).resolve().is_relative_to(tests_root)
        or not (repository / path).is_file()
    )
    if missing_paths:
        raise ValueError(f"pytest test-module paths are missing or outside tests/: {missing_paths}")
    return test_paths


def pytest_collection_patterns(
    repository: Path,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Return configured file, class, and function patterns for this checkout."""
    config_path = repository / "pyproject.toml"
    if not config_path.is_file():
        return ("test_*.py",), ("Test*",), ("test*",)
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"pytest naming configuration is unreadable: {config_path}") from error
    tool = _mapping(config.get("tool", {}), "tool")
    pytest_config = _mapping(tool.get("pytest", {}), "tool.pytest")
    options = _mapping(pytest_config.get("ini_options", {}), "tool.pytest.ini_options")
    return (
        _pattern_values(options.get("python_files", ("test_*.py",))),
        _pattern_values(options.get("python_classes", ("Test*",))),
        _pattern_values(options.get("python_functions", ("test*",))),
    )


def pytest_name_matches(name: str, patterns: tuple[str, ...]) -> bool:
    """Return whether a Python name matches any configured pytest glob."""
    return any(fnmatchcase(name, pattern) for pattern in patterns)


def _pattern_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return tuple(value.split())
    if isinstance(value, (list, tuple)) and all(
        isinstance(pattern, str) for pattern in cast(Sequence[object], value)
    ):
        return tuple(cast(str, pattern) for pattern in cast(Sequence[object], value))
    raise ValueError("pytest naming patterns must be strings or arrays of strings")


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"pytest configuration {name} must be a table")
    return cast(Mapping[str, object], value)
