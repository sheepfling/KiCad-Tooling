"""Source-root inventory state and freshness behavior."""

from __future__ import annotations

from pathlib import Path

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.project_source_hashes import (
    capture_project_source_inventory,
    project_source_inventory_freshness_issues,
    project_source_inventory_issues,
)


def test_source_inventory_retains_hashes_and_detects_changed_content(tmp_path: Path) -> None:
    source = tmp_path / "projects/board/board.kicad_sch"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"(kicad_sch original)")

    captured = capture_project_source_inventory(tmp_path, ("projects/board",))

    assert captured.state == "EVALUATED"
    assert captured.inventory == {"projects/board/board.kicad_sch": digest(source)}
    assert (
        project_source_inventory_issues("board", captured, ("projects/board/board.kicad_sch",))
        == ()
    )

    source.write_bytes(b"(kicad_sch changed)")

    assert project_source_inventory_freshness_issues(tmp_path, "board", captured) == (
        "project board: source inventory changed during operation",
    )


def test_source_inventory_preserves_missing_and_unavailable_root_states(tmp_path: Path) -> None:
    missing = capture_project_source_inventory(tmp_path, ("projects/missing",))

    assert missing.state == "MISSING"
    assert missing.issue == "Declared source root is missing: projects/missing"

    not_directory = tmp_path / "projects/not-a-directory"
    not_directory.parent.mkdir()
    not_directory.write_text("file", encoding="utf-8")
    unavailable = capture_project_source_inventory(tmp_path, ("projects/not-a-directory",))

    assert unavailable.state == "UNAVAILABLE"
    assert unavailable.issue == "Declared source root is not available: projects/not-a-directory"


def test_disappearing_source_root_is_classified_without_parsing_error_text(
    tmp_path: Path, monkeypatch
) -> None:
    source_root = tmp_path / "projects/board"
    source_root.mkdir(parents=True)

    def remove_then_fail(root: Path, source_roots: tuple[str, ...]) -> dict[str, str]:
        source_root.rmdir()
        raise ValueError("arbitrary failure detail")

    monkeypatch.setattr(
        "kicad_tooling.hwrepo.project_source_hashes.hash_project_sources", remove_then_fail
    )

    captured = capture_project_source_inventory(tmp_path, ("projects/board",))

    assert captured.state == "MISSING"
    assert captured.issue == "arbitrary failure detail"
