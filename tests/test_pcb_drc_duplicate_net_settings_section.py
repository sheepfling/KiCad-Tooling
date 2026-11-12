"""Source-bound review of repeated top-level PCB net_settings sections."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_drc_duplicate_net_settings_section_review import (
    PcbDuplicateNetSettingsSectionCandidate,
    source_bound_pcb_drc_duplicate_net_settings_section_candidates,
)
from kicad_tooling.hwrepo.pcb_drc_duplicate_net_settings_sections import (
    configured_pcb_duplicate_net_settings_sections,
)

RULE_ID = "pcb.drc_duplicate_net_settings_section"
PROJECT_RELATIVE = "projects/board.kicad_pro"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-duplicate-net-settings"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _project(
    tmp_path: Path,
    fixture: str = "fault-narrow-last.kicad_pro",
    *,
    kicad_version: str = "10.0.8",
    kind: ProjectKind = ProjectKind.PCB,
) -> tuple[Path, Path, ProjectConfig, dict[str, str]]:
    root = tmp_path / "repository"
    project = root / PROJECT_RELATIVE
    project.parent.mkdir(parents=True)
    project.write_bytes((FIXTURES / fixture).read_bytes())
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=kind, project=PROJECT_RELATIVE, kicad_version=kicad_version),
    )
    return root, project, config, {PROJECT_RELATIVE: digest(project)}


def _scan(root: Path, config: ProjectConfig, source_hashes: dict[str, str]):
    return source_bound_pcb_drc_duplicate_net_settings_section_candidates(
        root, config, source_hashes
    )


def test_duplicate_net_settings_preserve_source_order_and_hash(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)

    candidates = _scan(root, config, source_hashes)

    assert len(candidates) == 1
    (candidate,) = candidates
    assert isinstance(candidate, PcbDuplicateNetSettingsSectionCandidate)
    assert candidate.rule_id == RULE_ID
    assert candidate.subject == f"{PROJECT_RELATIVE}#net_settings"
    assert "source-order values" in candidate.message
    sections = tuple(json.loads(item) for item in candidate.evidence["source_order_sections_json"])
    assert len(sections) == 2
    assert sections[0][0] == ["meta", [["version", 3]]]
    assert sections[1][0] == ["meta", [["version", 3]]]
    assert sections[0][1][0] == "classes"
    assert sections[0][1][1][1][1] == ["clearance", 0.2]
    assert sections[1][1][1][1][1] == ["clearance", 0.05]
    assert candidate.evidence["source_sha256"] == (digest(project),)
    assert candidate.evidence["occurrence_count"] == ("2",)


def test_unique_section_is_quiet_and_duplicate_scope_is_narrow(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path, "control-unique-narrow.kicad_pro")

    assert _scan(root, config, source_hashes) == ()
    with pytest.raises(ValueError, match="Duplicate JSON key at <root>: other"):
        configured_pcb_duplicate_net_settings_sections(
            '{"other":{},"other":{},"net_settings":{},"net_settings":{}}'
        )
    with pytest.raises(ValueError, match="Duplicate JSON key at net_settings: classes"):
        configured_pcb_duplicate_net_settings_sections(
            '{"net_settings":{"classes":[],"classes":[]},"net_settings":{"classes":[]}}'
        )


def test_unrelated_duplicate_keys_remain_strict(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    project.write_text(
        '{"meta":{"filename":"board.kicad_pro","version":1},'
        '"board":{"design_settings":{"rule_severities":{}}},'
        '"other":{"repeat":"first","repeat":"last"},'
        '"net_settings":{},"net_settings":{}}',
        encoding="utf-8",
    )
    source_hashes[PROJECT_RELATIVE] = digest(project)

    with pytest.raises(ValueError, match="could not read supported PCB project settings"):
        _scan(root, config, source_hashes)


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5", "10.0.7", "10.0.9", "11.0.0"))
def test_unmeasured_kicad_versions_are_out_of_scope(tmp_path: Path, version: str) -> None:
    root, _, config, source_hashes = _project(tmp_path, kicad_version=version)

    assert _scan(root, config, source_hashes) == ()


@pytest.mark.parametrize(
    "kind",
    (ProjectKind.SCHEMATIC, ProjectKind.SYSTEM_WIRING, ProjectKind.HARNESS_INTERFACE),
)
def test_non_pcb_projects_are_out_of_scope(tmp_path: Path, kind: ProjectKind) -> None:
    root, _, config, source_hashes = _project(tmp_path, kind=kind)

    assert _scan(root, config, source_hashes) == ()


def test_pcb_only_projects_are_supported(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path, kind=ProjectKind.PCB_ONLY)

    assert tuple(item.rule_id for item in _scan(root, config, source_hashes)) == (RULE_ID,)


def test_missing_or_stale_source_hash_does_not_create_a_candidate(tmp_path: Path) -> None:
    root, project, config, _ = _project(tmp_path)

    with pytest.raises(ValueError, match="outside source-bound"):
        _scan(root, config, {})
    with pytest.raises(ValueError, match="differ from source-bound"):
        _scan(root, config, {PROJECT_RELATIVE: "0" * 64})

    assert project.is_file()


def test_repeated_scans_are_deterministic(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path)

    assert _scan(root, config, source_hashes) == _scan(root, config, source_hashes)
