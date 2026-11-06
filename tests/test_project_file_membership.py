"""Bounded native project-file membership and freshness behavior."""

from __future__ import annotations

from pathlib import Path

from kicad_tooling.hwrepo.project_file_membership import (
    capture_project_file_membership,
    project_file_membership_freshness_issues,
    project_file_membership_issues,
)


def test_membership_matches_declared_projects_and_detects_added_project_files(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "examples/projects"
    project_root.mkdir(parents=True)
    declared = "examples/projects/board/board.kicad_pro"
    project_file = tmp_path / declared
    project_file.parent.mkdir()
    project_file.write_text("{}", encoding="utf-8")

    captured = capture_project_file_membership(tmp_path, ("examples/projects",))

    assert captured.files == (declared,)
    assert project_file_membership_issues(captured, {declared}) == ()
    assert project_file_membership_freshness_issues(tmp_path, captured) == ()

    added = project_root / "new-board.kicad_pro"
    added.write_text("{}", encoding="utf-8")
    current = capture_project_file_membership(tmp_path, ("examples/projects",))

    assert (
        "undeclared or missing project files"
        in project_file_membership_issues(current, {declared})[0]
    )
    assert project_file_membership_freshness_issues(tmp_path, captured) == (
        "Project-file membership changed during operation under examples/projects",
    )


def test_membership_ignores_hidden_and_backup_directories(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    for directory in (".hidden", "board-backups", "nested"):
        path = root / directory
        path.mkdir(parents=True)
        (path / "ignored.kicad_pro").write_text("{}", encoding="utf-8")

    captured = capture_project_file_membership(tmp_path, ("projects",))

    assert captured.files == ("projects/nested/ignored.kicad_pro",)
    assert project_file_membership_issues(captured, {"projects/nested/ignored.kicad_pro"}) == ()


def test_missing_membership_root_is_reported_explicitly(tmp_path: Path) -> None:
    captured = capture_project_file_membership(tmp_path, ("projects/missing",))
    expected = (
        "project discovery: project-file membership missing under projects/missing: "
        + "configured project root is missing"
    )

    assert captured.roots[0].state == "MISSING"
    assert project_file_membership_issues(captured, set()) == (expected,)
