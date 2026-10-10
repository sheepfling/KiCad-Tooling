"""Shared paths and review limits for lint architecture tests."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HWREPO = REPO_ROOT / "kicad_tooling" / "hwrepo"
TESTS = Path(__file__).resolve().parent

FACADE_MAX_LINES = 100
EVALUATOR_MAX_LINES = 200
IMPLEMENTATION_MAX_LINES = 500
THEME_SUITE_MAX_LINES = 500
SUPPORT_MODULE_MAX_LINES = 500
HOSTED_CI_COORDINATOR_MAX_LINES = 1_000


def line_count(path: Path) -> int:
    """Count source lines consistently across architecture suites."""
    return len(path.read_text(encoding="utf-8").splitlines())
