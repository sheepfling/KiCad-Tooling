"""Source-bound review of repeated top-level schematic ERC sections."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.schematic_erc_duplicate_section_review import (
    SchematicErcDuplicateSectionCandidate,
    source_bound_schematic_erc_duplicate_section_candidates,
)
from kicad_tooling.hwrepo.schematic_erc_project_settings import (
    configured_schematic_erc_duplicate_sections,
    configured_schematic_erc_rule_severity_settings,
)

RULE_ID = "schematic.erc_duplicate_section"
PROJECT_RELATIVE = "projects/controller.kicad_pro"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/schematic-erc-duplicate-section"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.schematic_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _project(
    tmp_path: Path,
    fixture: str = "fault-warning-ignore.kicad_pro",
    *,
    version: str = "10.0.8",
    kind: ProjectKind = ProjectKind.PCB,
) -> tuple[Path, Path, ProjectConfig, dict[str, str]]:
    root = tmp_path / "repository"
    project = root / PROJECT_RELATIVE
    project.parent.mkdir(parents=True)
    project.write_bytes((FIXTURES / fixture).read_bytes())
    config = cast(
        ProjectConfig,
        SimpleNamespace(kind=kind, project=Path(PROJECT_RELATIVE), kicad_version=version),
    )
    return root, project, config, {PROJECT_RELATIVE: digest(project)}


def _scan(root: Path, config: ProjectConfig, source_hashes: dict[str, str]):
    return source_bound_schematic_erc_duplicate_section_candidates(root, config, source_hashes)


@pytest.mark.parametrize(
    ("fixture", "expected_severities"),
    (
        ("fault-warning-ignore.kicad_pro", ('"warning"', '"ignore"')),
        ("fault-ignore-warning.kicad_pro", ('"ignore"', '"warning"')),
    ),
)
def test_duplicate_erc_sections_preserve_source_order_and_hash(
    tmp_path: Path,
    fixture: str,
    expected_severities: tuple[str, ...],
) -> None:
    root, project, config, source_hashes = _project(tmp_path, fixture)

    (candidate,) = _scan(root, config, source_hashes)

    assert isinstance(candidate, SchematicErcDuplicateSectionCandidate)
    assert candidate.rule_id == RULE_ID
    assert candidate.subject == f"{PROJECT_RELATIVE}#erc"
    sections = tuple(json.loads(item) for item in candidate.evidence["source_order_sections_json"])
    assert len(sections) == 2
    assert tuple(
        dict(dict(section)["rule_severities"])["pin_not_connected"] for section in sections
    ) == tuple(json.loads(item) for item in expected_severities)
    assert candidate.evidence["source_sha256"] == (digest(project),)
    assert candidate.evidence["project_section_key"] == ("erc",)
    assert candidate.evidence["occurrence_count"] == ("2",)


def test_unique_section_is_quiet_and_direct_reader_stays_strict(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path, "control-warning.kicad_pro")

    assert _scan(root, config, source_hashes) == ()
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        configured_schematic_erc_rule_severity_settings(
            (FIXTURES / "fault-warning-ignore.kicad_pro").read_text(encoding="utf-8")
        )
    duplicate_sections = configured_schematic_erc_duplicate_sections(
        (FIXTURES / "fault-warning-ignore.kicad_pro").read_text(encoding="utf-8")
    )
    assert len(duplicate_sections) == 1
    assert len(duplicate_sections[0].source_order_sections_json) == 2


def test_other_duplicate_members_remain_strict(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    project.write_text(
        '{"other":{"repeat":"first","repeat":"last"},'
        '"erc":{"meta":{"version":0}},"erc":{"meta":{"version":0}}}',
        encoding="utf-8",
    )
    source_hashes[PROJECT_RELATIVE] = digest(project)

    with pytest.raises(ValueError, match="could not read supported schematic ERC project settings"):
        _scan(root, config, source_hashes)


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5", "10.0.7", "10.0.9", "11.0.0"))
def test_unmeasured_versions_are_out_of_scope(tmp_path: Path, version: str) -> None:
    root, _, config, source_hashes = _project(tmp_path, version=version)

    assert _scan(root, config, source_hashes) == ()


@pytest.mark.parametrize(
    "kind",
    (ProjectKind.SCHEMATIC, ProjectKind.SYSTEM_WIRING, ProjectKind.HARNESS_INTERFACE),
)
def test_schematic_capable_project_kinds_are_supported(tmp_path: Path, kind: ProjectKind) -> None:
    root, _, config, source_hashes = _project(tmp_path, kind=kind)

    assert tuple(item.rule_id for item in _scan(root, config, source_hashes)) == (RULE_ID,)


def test_non_schematic_project_kind_is_out_of_scope(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path, kind=ProjectKind.PCB_ONLY)

    assert _scan(root, config, source_hashes) == ()


def test_source_hash_must_be_present_and_current_and_candidate_is_derived(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    with pytest.raises(ValueError, match="outside source-bound"):
        _scan(root, config, {})
    (candidate,) = _scan(root, config, source_hashes)

    with pytest.raises(ValueError, match="must match source evidence"):
        replace(candidate, subject=f"{candidate.subject}/stale")

    project.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from source-bound project inputs"):
        _scan(root, config, source_hashes)


def test_repeated_scan_is_deterministic(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path)

    assert _scan(root, config, source_hashes) == _scan(root, config, source_hashes)
