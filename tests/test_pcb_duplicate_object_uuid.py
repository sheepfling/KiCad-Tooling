"""Source-bound review for repeated PCB object UUIDs."""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_object_uuid_integrity import (
    duplicate_pcb_object_uuid_candidates,
)

RULE_ID = "pcb.duplicate_object_uuid"
PROJECT = "projects/synthetic/controller.kicad_pro"
BOARD = "projects/synthetic/controller.kicad_pcb"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-duplicate-object-uuid"
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
    return duplicate_pcb_object_uuid_candidates(root, config, hashes)


def test_duplicate_uuid_on_distinct_board_objects_is_localized(tmp_path: Path) -> None:
    root, board, config, hashes = _project(tmp_path)

    candidates = _scan(root, config, hashes)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.rule_id == RULE_ID
    assert candidate.subject.startswith(f"{BOARD}:")
    assert "native diagnostics" in candidate.message
    assert candidate.evidence["source_path"] == (BOARD,)
    assert candidate.evidence["source_sha256"] == (digest(board),)
    assert candidate.evidence["object_uuid"] == ("00000000-0000-0000-0000-000000000002",)
    assert candidate.evidence["occurrence_count"] == ("2",)
    assert len(candidate.evidence["source_lines"]) == 2
    assert candidate.evidence["object_kinds"] == ("segment",)
    assert candidate.evidence["occurrence_object_kinds"] == ("segment", "segment")
    assert candidate.evidence["occurrence_identity_fields"] == ("uuid", "uuid")


def test_zone_tstamp_and_object_uuid_share_the_identity_check(tmp_path: Path) -> None:
    root, _board, config, hashes = _project(tmp_path, "zone-tstamp-fault")

    (candidate,) = _scan(root, config, hashes)

    assert candidate.evidence["object_uuid"] == ("00000000-0000-0000-0000-000000000002",)
    assert candidate.evidence["object_kinds"] == ("segment", "zone")
    assert candidate.evidence["occurrence_object_kinds"] == ("segment", "zone")
    assert candidate.evidence["occurrence_identity_fields"] == ("uuid", "tstamp")


def test_unique_object_uuids_are_quiet(tmp_path: Path) -> None:
    root, _board, config, hashes = _project(tmp_path, "control")

    assert _scan(root, config, hashes) == ()


def test_zone_tstamp_control_remains_quiet(tmp_path: Path) -> None:
    root, _board, config, hashes = _project(tmp_path, "control")

    assert _scan(root, config, hashes) == ()


@pytest.mark.parametrize("version", ("10.0.1", "10.0.4", "10.0.6", "11.0.0"))
@pytest.mark.parametrize("kind", (ProjectKind.PCB, ProjectKind.PCB_ONLY))
def test_unmeasured_versions_are_out_of_scope(
    tmp_path: Path,
    version: str,
    kind: ProjectKind,
) -> None:
    root, _board, config, hashes = _project(tmp_path, version=version, kind=kind)

    assert _scan(root, config, hashes) == ()


@pytest.mark.parametrize("kind", (ProjectKind.SCHEMATIC, ProjectKind.SYSTEM_WIRING))
def test_non_pcb_project_kinds_are_out_of_scope(tmp_path: Path, kind: ProjectKind) -> None:
    root, _board, config, hashes = _project(tmp_path, kind=kind)

    assert _scan(root, config, hashes) == ()


@pytest.mark.parametrize("kind", (ProjectKind.PCB, ProjectKind.PCB_ONLY))
def test_measured_pcb_project_kinds_are_supported(tmp_path: Path, kind: ProjectKind) -> None:
    root, _board, config, hashes = _project(tmp_path, kind=kind)

    assert len(_scan(root, config, hashes)) == 1


def test_missing_or_stale_source_hash_never_emits_an_unbound_candidate(tmp_path: Path) -> None:
    root, board, config, _hashes = _project(tmp_path)

    assert _scan(root, config, {}) == ()
    with pytest.raises(ValueError, match="differs from the source-bound hashes"):
        _scan(root, config, {BOARD: "0" * 64})
    assert board.is_file()


def test_irrelevant_source_edit_preserves_identity_and_refreshes_hash(tmp_path: Path) -> None:
    root, board, config, hashes = _project(tmp_path)
    (before,) = _scan(root, config, hashes)
    board.write_bytes(board.read_bytes() + b"\n# harmless source comment\n")
    updated_hashes = {BOARD: digest(board)}

    (after,) = _scan(root, config, updated_hashes)

    assert after.subject == before.subject
    assert after.evidence["source_sha256"] == (digest(board),)
    assert after.evidence["source_sha256"] != before.evidence["source_sha256"]


def test_uuid_hex_case_is_normalized_and_noncanonical_forms_are_ignored(tmp_path: Path) -> None:
    root, board, config, _hashes = _project(tmp_path)
    source = board.read_text(encoding="utf-8").replace(
        "00000000-0000-0000-0000-000000000002",
        "a0000000-0000-0000-0000-000000000002",
        1,
    )
    source = source.replace(
        "00000000-0000-0000-0000-000000000002",
        "A0000000-0000-0000-0000-000000000002",
        1,
    )
    board.write_text(source, encoding="utf-8")

    (candidate,) = _scan(root, config, {BOARD: digest(board)})
    assert candidate.evidence["object_uuid"] == ("a0000000-0000-0000-0000-000000000002",)

    malformed = source.replace(
        "A0000000-0000-0000-0000-000000000002", "a00000000000000000000000000000002"
    )
    board.write_text(malformed, encoding="utf-8")
    assert _scan(root, config, {BOARD: digest(board)}) == ()
