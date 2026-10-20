"""Validation helpers for explicit pytest module selection."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path, PurePosixPath

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
