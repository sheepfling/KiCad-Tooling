"""Tests for annotated lint tags that select explicit pytest modules."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.lint_gate_scope import parse_tag_message, read_tag_scope, write_github_scope

pytestmark = pytest.mark.architecture


def _git(repository: Path, *arguments: str) -> None:
    subprocess.run(("git", *arguments), cwd=repository, check=True, capture_output=True)


def test_annotated_area_tag_resolves_existing_test_paths_and_writes_action_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    workflow = repository / ".github/workflows/tooling.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: synthetic\n", encoding="utf-8")
    paths = ("tests/test_probe.py", "tests/nested/test_peer.py")
    for path in paths:
        target = repository / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# synthetic test module\n", encoding="utf-8")
    _git(repository, "init", "-q")
    _git(repository, "config", "user.email", "lint-test@example.invalid")
    _git(repository, "config", "user.name", "Lint Test")
    _git(repository, "add", "--all")
    _git(repository, "commit", "-m", "Synthetic scoped test modules")
    _git(
        repository,
        "tag",
        "-a",
        "v0.9.0rc1",
        "-m",
        "Synthetic PCB lint gate",
        "-m",
        "Lint-Area: pcb_lint",
        "-m",
        f"Test-Path: {paths[0]}",
        "-m",
        f"Test-Path: {paths[1]}",
    )

    scope = read_tag_scope("v0.9.0rc1", repository)
    assert scope.test_paths == paths
    assert scope.pytest_markexpr == "design_lint and pcb_lint"

    output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.delenv("GITHUB_ENV", raising=False)
    write_github_scope(scope)
    assert output.read_text(encoding="utf-8") == (
        "markexpr=design_lint and pcb_lint\n"
        "pytestpaths=tests/test_probe.py,tests/nested/test_peer.py\n"
    )


@pytest.mark.parametrize(
    "path",
    (
        "project/test_probe.py",
        "tests/helper.py",
        "tests/../tests/test_probe.py",
        "/tests/test_probe.py",
        "tests/test_probe.py,tests/test_peer.py",
        "tests/test_bad:name.py",
        "tests/test_bad\\name.py",
    ),
)
def test_lint_tag_rejects_invalid_test_module_paths(path: str) -> None:
    with pytest.raises(ValueError, match="beneath tests/"):
        parse_tag_message(f"Lint-Area: pcb_lint\nTest-Path: {path}\n", frozenset())


def test_lint_rule_tag_cannot_override_catalogued_test_selection() -> None:
    rule_id = "power.mapped_sequence_dependency_mismatch"
    with pytest.raises(ValueError, match="cannot narrow a Lint-Rule selection"):
        parse_tag_message(
            f"Lint-Rule: {rule_id}\nTest-Path: tests/test_probe.py\n",
            frozenset(),
            frozenset({rule_id}),
        )


def test_lint_tag_rejects_duplicate_test_module_paths() -> None:
    with pytest.raises(ValueError, match="paths must be unique"):
        parse_tag_message(
            "Lint-Area: pcb_lint\nTest-Path: tests/test_probe.py\nTest-Path: tests/test_probe.py\n",
            frozenset(),
        )


def test_annotated_area_tag_rejects_a_missing_test_module(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    workflow = repository / ".github/workflows/tooling.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: synthetic\n", encoding="utf-8")
    (repository / "tests").mkdir()
    _git(repository, "init", "-q")
    _git(repository, "config", "user.email", "lint-test@example.invalid")
    _git(repository, "config", "user.name", "Lint Test")
    _git(repository, "add", "--all")
    _git(repository, "commit", "-m", "Synthetic scoped test modules")
    _git(
        repository,
        "tag",
        "-a",
        "v0.9.0rc2",
        "-m",
        "Synthetic PCB lint gate",
        "-m",
        "Lint-Area: pcb_lint",
        "-m",
        "Test-Path: tests/test_missing.py",
    )
    with pytest.raises(ValueError, match="missing or outside tests"):
        read_tag_scope("v0.9.0rc2", repository)
