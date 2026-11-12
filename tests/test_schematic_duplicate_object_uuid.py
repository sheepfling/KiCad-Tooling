"""Source-bound regressions for repeated schematic object UUIDs."""

from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_source_integrity import (
    duplicate_schematic_object_uuid_candidates,
)

RULE_ID = "schematic.duplicate_object_uuid"
PROJECT = "projects/synthetic/kicad/controller.kicad_pro"
SCHEMATIC = "projects/synthetic/kicad/controller.kicad_sch"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/schematic-duplicate-object-uuid"
HIERARCHY_FIXTURES = (
    Path(__file__).parent / "fixtures/design_lint/schematic-duplicate-object-uuid-across-files"
)
REPEATED_SHEET_FIXTURES = Path(__file__).parent / "fixtures/design_lint/repeated-sheet"
SHARED_UUID = "b0000000-0000-4000-8000-000000000005"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _project(
    tmp_path: Path,
    fixture: str,
    *,
    version: str = "10.0.5",
    kind: ProjectKind = ProjectKind.PCB,
) -> tuple[Path, ProjectConfig, dict[str, str]]:
    root = tmp_path / "repository"
    source = root / SCHEMATIC
    source.parent.mkdir(parents=True)
    source.write_bytes((FIXTURES / fixture).read_bytes())
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=kind, project=Path(PROJECT), kicad_version=version),
    )
    return root, config, {SCHEMATIC: digest(source)}


def _scan(root: Path, config: ProjectConfig, source_hashes: dict[str, str]):
    return duplicate_schematic_object_uuid_candidates(root, config, source_hashes)


def _hierarchical_project(
    tmp_path: Path,
    *,
    channel_b: str,
) -> tuple[Path, ProjectConfig, dict[str, str]]:
    root = tmp_path / "repository"
    project_directory = root / Path(SCHEMATIC).parent
    project_directory.mkdir(parents=True)
    fixture_names = {
        SCHEMATIC: "root.kicad_sch",
        "projects/synthetic/kicad/channel-a.kicad_sch": "channel-a.kicad_sch",
        "projects/synthetic/kicad/channel-b.kicad_sch": channel_b,
    }
    for relative, fixture_name in fixture_names.items():
        shutil.copyfile(HIERARCHY_FIXTURES / fixture_name, root / relative)
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=ProjectKind.PCB, project=Path(PROJECT), kicad_version="10.0.5"),
    )
    return root, config, {relative: digest(root / relative) for relative in fixture_names}


def test_duplicate_object_uuid_is_localized_and_control_is_quiet(tmp_path: Path) -> None:
    fault_root, config, fault_hashes = _project(tmp_path / "fault", "fault.kicad_sch")
    control_root, control_config, control_hashes = _project(
        tmp_path / "control", "control.kicad_sch"
    )

    (candidate,) = _scan(fault_root, config, fault_hashes)

    assert candidate.rule_id == RULE_ID
    assert candidate.subject.endswith(":54:48000000-0000-4000-8000-000000000211")
    assert "assigned to 2 objects" in candidate.message
    assert candidate.evidence["source_path"] == (SCHEMATIC,)
    assert candidate.evidence["source_sha256"] == (fault_hashes[SCHEMATIC],)
    assert candidate.evidence["object_uuid"] == ("48000000-0000-4000-8000-000000000211",)
    assert candidate.evidence["occurrence_count"] == ("2",)
    assert candidate.evidence["source_lines"] == ("54", "55")
    assert candidate.evidence["object_kinds"] == ("pin",)
    assert _scan(control_root, control_config, control_hashes) == ()


def test_irrelevant_source_edit_preserves_finding_and_refreshes_hash(tmp_path: Path) -> None:
    root, config, source_hashes = _project(tmp_path, "fault.kicad_sch")
    (before,) = _scan(root, config, source_hashes)
    source = root / SCHEMATIC
    source.write_bytes(
        source.read_bytes().replace(
            b"Synthetic USB direct peer reference review",
            b"Synthetic duplicate object UUID review",
        )
    )
    source_hashes[SCHEMATIC] = digest(source)

    first = _scan(root, config, source_hashes)
    assert first == _scan(root, config, source_hashes)
    assert len(first) == 1
    assert first[0].subject == before.subject
    assert first[0].evidence["source_sha256"] == (source_hashes[SCHEMATIC],)
    assert first[0].evidence["source_sha256"] != before.evidence["source_sha256"]


def test_source_inventory_must_match_current_schematic_bytes(tmp_path: Path) -> None:
    root, config, source_hashes = _project(tmp_path, "fault.kicad_sch")
    source = root / SCHEMATIC
    source.write_bytes(source.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="differs from the source-bound hashes"):
        _scan(root, config, source_hashes)


@pytest.mark.parametrize("version", ("10.0.0", "10.0.6", "10.0.8", "11.0.0"))
def test_native_evidence_version_boundary_is_exact(tmp_path: Path, version: str) -> None:
    root, config, source_hashes = _project(tmp_path, "fault.kicad_sch", version=version)

    assert _scan(root, config, source_hashes) == ()


def test_pcb_only_projects_are_out_of_scope(tmp_path: Path) -> None:
    root, config, source_hashes = _project(
        tmp_path,
        "fault.kicad_sch",
        kind=ProjectKind.PCB_ONLY,
    )

    assert _scan(root, config, source_hashes) == ()


def test_duplicate_uuid_across_distinct_hierarchical_files_is_localized(
    tmp_path: Path,
) -> None:
    root, config, source_hashes = _hierarchical_project(
        tmp_path, channel_b="channel-b-fault.kicad_sch"
    )

    (candidate,) = _scan(root, config, source_hashes)

    first_path = "projects/synthetic/kicad/channel-a.kicad_sch"
    second_path = "projects/synthetic/kicad/channel-b.kicad_sch"
    assert candidate.rule_id == RULE_ID
    assert candidate.subject == f"{first_path}:46:{SHARED_UUID}"
    assert "across 2 distinct source files" in candidate.message
    assert candidate.evidence["source_path"] == (first_path, second_path)
    assert candidate.evidence["source_sha256"] == (
        source_hashes[first_path],
        source_hashes[second_path],
    )
    assert candidate.evidence["source_lines"] == ("46", "46")
    assert candidate.evidence["object_kinds"] == ("wire",)
    assert candidate.evidence["occurrence_source_paths"] == (first_path, second_path)
    assert candidate.evidence["occurrence_source_sha256"] == (
        source_hashes[first_path],
        source_hashes[second_path],
    )
    assert candidate.evidence["occurrence_object_kinds"] == ("wire", "wire")


def test_distinct_file_control_and_reused_sheet_source_are_quiet(tmp_path: Path) -> None:
    control_root, config, control_hashes = _hierarchical_project(
        tmp_path / "distinct-control", channel_b="channel-b-control.kicad_sch"
    )
    assert _scan(control_root, config, control_hashes) == ()

    reused_root = tmp_path / "reused" / "repository"
    repeated_project_dir = reused_root / Path(SCHEMATIC).parent
    repeated_project_dir.mkdir(parents=True)
    shutil.copyfile(
        REPEATED_SHEET_FIXTURES / "repeated-sheet-root.kicad_sch",
        repeated_project_dir / Path(SCHEMATIC).name,
    )
    reused_sheet = "projects/synthetic/kicad/repeated-channel.kicad_sch"
    shutil.copyfile(
        REPEATED_SHEET_FIXTURES / "repeated-channel.kicad_sch",
        reused_root / reused_sheet,
    )
    reused_hashes = {
        SCHEMATIC: digest(repeated_project_dir / Path(SCHEMATIC).name),
        reused_sheet: digest(reused_root / reused_sheet),
    }

    assert _scan(reused_root, config, reused_hashes) == ()


def test_cross_file_uuid_finding_refreshes_only_the_edited_source_hash(
    tmp_path: Path,
) -> None:
    root, config, source_hashes = _hierarchical_project(
        tmp_path, channel_b="channel-b-fault.kicad_sch"
    )
    (before,) = _scan(root, config, source_hashes)
    edited_path = "projects/synthetic/kicad/channel-b.kicad_sch"
    source = root / edited_path
    source.write_bytes(
        source.read_bytes().replace(b"Synthetic repeated channel", b"Synthetic UUID channel")
    )
    source_hashes[edited_path] = digest(source)

    (after,) = _scan(root, config, source_hashes)

    assert after.subject == before.subject
    assert after.evidence["source_sha256"] == (
        source_hashes["projects/synthetic/kicad/channel-a.kicad_sch"],
        source_hashes[edited_path],
    )
    assert after.evidence["source_sha256"][0] == before.evidence["source_sha256"][0]
    assert after.evidence["source_sha256"][1] != before.evidence["source_sha256"][1]
