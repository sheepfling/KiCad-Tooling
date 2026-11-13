"""Source-bound review for incomplete PCB footprint schematic paths."""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_footprint_path_integrity import (
    pcb_footprint_path_trailing_separator_candidates,
)

RULE_ID = "pcb.footprint_path_trailing_separator"
PROJECT = "projects/synthetic/controller.kicad_pro"
BOARD = "projects/synthetic/controller.kicad_pcb"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-footprint-path-trailing-separator"
SHEET_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
SYMBOL_UUID = "11111111-2222-3333-4444-555555555555"

pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _project(
    tmp_path: Path,
    case: str = "fault",
    *,
    version: str = "10.0.5",
    kind: ProjectKind = ProjectKind.PCB,
) -> tuple[Path, Path, ProjectConfig, dict[str, str]]:
    root = tmp_path / "repository"
    board_path = root / BOARD
    board_path.parent.mkdir(parents=True)
    shutil.copyfile(FIXTURES / f"{case}.kicad_pcb", board_path)
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=kind, project=PROJECT, kicad_version=version),
    )
    return root, board_path, config, {BOARD: digest(board_path)}


def _scan(root: Path, config: ProjectConfig, hashes: dict[str, str]):
    return pcb_footprint_path_trailing_separator_candidates(root, config, hashes)


def test_trailing_sheet_path_is_localized_and_source_bound(tmp_path: Path) -> None:
    root, board, config, hashes = _project(tmp_path)

    (candidate,) = _scan(root, config, hashes)

    assert candidate.rule_id == RULE_ID
    assert candidate.subject.startswith(f"{BOARD}:")
    assert "empty path segment" in candidate.message
    assert candidate.evidence["source_path"] == (BOARD,)
    assert candidate.evidence["source_sha256"] == (digest(board),)
    assert candidate.evidence["reference"] == ("J1",)
    assert candidate.evidence["instance_path"] == (f"/{SHEET_UUID}/",)
    assert candidate.evidence["path_uuid_segments"] == (SHEET_UUID,)
    assert len(candidate.evidence["source_line"]) == 1


def test_complete_footprint_path_is_a_quiet_control(tmp_path: Path) -> None:
    root, _board, config, hashes = _project(tmp_path, "control")

    assert _scan(root, config, hashes) == ()


@pytest.mark.parametrize(
    "instance_path",
    (
        "/",
        "/not-a-uuid/",
        f"/{SHEET_UUID}//",
        f"/{SHEET_UUID}/{SYMBOL_UUID}",
    ),
)
def test_other_path_shapes_are_outside_the_predicate(tmp_path: Path, instance_path: str) -> None:
    root, board, config, _hashes = _project(tmp_path)
    source = board.read_text(encoding="utf-8").replace(f"/{SHEET_UUID}/", instance_path, 1)
    board.write_text(source, encoding="utf-8")

    assert _scan(root, config, {BOARD: digest(board)}) == ()


@pytest.mark.parametrize(
    "path_fields",
    (
        f'(path "/{SHEET_UUID}/")\n    (path "/{SHEET_UUID}/{SYMBOL_UUID}")',
        f"(path /{SHEET_UUID}/)",
    ),
)
def test_duplicate_or_unquoted_path_fields_are_outside_the_predicate(
    tmp_path: Path,
    path_fields: str,
) -> None:
    root, board, config, _hashes = _project(tmp_path)
    source = board.read_text(encoding="utf-8").replace(f'(path "/{SHEET_UUID}/")', path_fields, 1)
    board.write_text(source, encoding="utf-8")

    assert _scan(root, config, {BOARD: digest(board)}) == ()


def test_trailing_separator_after_component_uuid_is_also_reviewable(tmp_path: Path) -> None:
    root, board, config, _hashes = _project(tmp_path)
    source = board.read_text(encoding="utf-8").replace(
        f"/{SHEET_UUID}/", f"/{SHEET_UUID}/{SYMBOL_UUID}/", 1
    )
    board.write_text(source, encoding="utf-8")

    (candidate,) = _scan(root, config, {BOARD: digest(board)})

    assert candidate.evidence["path_uuid_segments"] == (SHEET_UUID, SYMBOL_UUID)


@pytest.mark.parametrize("kind", (ProjectKind.PCB, ProjectKind.PCB_ONLY))
def test_pcb_project_kinds_are_supported(tmp_path: Path, kind: ProjectKind) -> None:
    root, _board, config, hashes = _project(tmp_path, kind=kind)

    assert len(_scan(root, config, hashes)) == 1


@pytest.mark.parametrize("kind", (ProjectKind.SCHEMATIC, ProjectKind.SYSTEM_WIRING))
def test_non_pcb_project_kinds_are_out_of_scope(tmp_path: Path, kind: ProjectKind) -> None:
    root, _board, config, hashes = _project(tmp_path, kind=kind)

    assert _scan(root, config, hashes) == ()


@pytest.mark.parametrize("version", ("10.0.1", "10.0.4", "10.0.6", "11.0.0"))
def test_unmeasured_versions_are_out_of_scope(tmp_path: Path, version: str) -> None:
    root, _board, config, hashes = _project(tmp_path, version=version)

    assert _scan(root, config, hashes) == ()


def test_missing_or_stale_source_hash_never_emits_an_unbound_candidate(tmp_path: Path) -> None:
    root, board, config, _hashes = _project(tmp_path)

    assert _scan(root, config, {}) == ()
    with pytest.raises(ValueError, match="differs from the source-bound hashes"):
        _scan(root, config, {BOARD: "0" * 64})
    assert board.is_file()


def test_irrelevant_source_edit_preserves_identity_and_refreshes_its_hash(tmp_path: Path) -> None:
    root, board, config, hashes = _project(tmp_path)
    (before,) = _scan(root, config, hashes)
    board.write_bytes(board.read_bytes() + b"\n# harmless source comment\n")

    (after,) = _scan(root, config, {BOARD: digest(board)})

    assert after.subject == before.subject
    assert after.evidence["source_sha256"] == (digest(board),)
    assert after.evidence["source_sha256"] != before.evidence["source_sha256"]


def test_changing_only_the_path_to_a_complete_instance_clears_the_candidate(
    tmp_path: Path,
) -> None:
    root, board, config, hashes = _project(tmp_path)
    (fault,) = _scan(root, config, hashes)
    source = board.read_text(encoding="utf-8").replace(
        f"/{SHEET_UUID}/", f"/{SHEET_UUID}/{SYMBOL_UUID}", 1
    )
    board.write_text(source, encoding="utf-8")

    assert _scan(root, config, {BOARD: digest(board)}) == ()
    assert fault.evidence["instance_path"] == (f"/{SHEET_UUID}/",)
