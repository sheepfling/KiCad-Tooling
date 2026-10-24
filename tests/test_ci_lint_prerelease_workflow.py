"""Lint-scope regressions for the hosted acceptance workflow."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.design_lint, pytest.mark.catalog_lint, pytest.mark.rule_gate_integrity]


def _job_section(workflow: str, name: str, next_name: str) -> str:
    return workflow.split(f"  {name}:\n", 1)[1].split(f"  {next_name}:\n", 1)[0]


def _condition(job: str) -> str:
    match = re.search(r"(?m)^    if: >-\n((?:^      .+\n)+)", job)
    assert match is not None
    return " ".join(line.strip() for line in match.group(1).splitlines())


def test_lint_prerelease_skips_portability_previews_but_keeps_focused_acceptance() -> None:
    repository = Path(__file__).resolve().parents[1]
    workflow = (repository / ".github/workflows/tooling.yml").read_text(encoding="utf-8")

    preview = _job_section(workflow, "preview-portability", "package")
    package = _job_section(workflow, "package", "prerelease-lint-gate")
    lint_gate = workflow.split("  prerelease-lint-gate:\n", 1)[1]

    expected_full_acceptance = (
        "github.event_name != 'push' || github.ref == 'refs/heads/main' || "
        "!contains(github.ref_name, 'rc')"
    )
    assert _condition(preview) == expected_full_acceptance
    assert _condition(package) == expected_full_acceptance
    assert "os: [ubuntu-24.04, windows-2022, macos-14]" in preview

    assert "startsWith(github.ref, 'refs/tags/v')" in lint_gate
    assert "contains(github.ref_name, 'rc')" in lint_gate
    assert 'python scripts/lint_gate_scope.py --tag "$GITHUB_REF_NAME"' in lint_gate
    assert '--pytest-markexpr "$PYTEST_MARKEXPR"' in lint_gate
    assert "build/acceptance-template" in lint_gate
