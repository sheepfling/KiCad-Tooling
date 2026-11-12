"""Source-bound review of duplicate saved PCB DRC severity keys."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_drc_duplicate_severity_key_review import (
    PcbDrcDuplicateSeverityKeyCandidate,
    source_bound_pcb_drc_duplicate_severity_key_candidates,
)
from kicad_tooling.hwrepo.pcb_drc_project_settings import (
    PcbDrcDuplicateRuleSeveritySetting,
    configured_pcb_drc_duplicate_rule_severity_settings,
    configured_pcb_drc_rule_severity_settings,
)

RULE_ID = "pcb.drc_duplicate_severity_key"
PROJECT_RELATIVE = "projects/board.kicad_pro"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-duplicate-severity-key"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _project(
    tmp_path: Path,
    fixture: str = "fault-ignore-last.kicad_pro",
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
    return source_bound_pcb_drc_duplicate_severity_key_candidates(root, config, source_hashes)


def test_duplicate_known_key_preserves_source_order_and_hash(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)

    candidates = _scan(root, config, source_hashes)

    assert len(candidates) == 1
    (candidate,) = candidates
    assert isinstance(candidate, PcbDrcDuplicateSeverityKeyCandidate)
    assert candidate.rule_id == RULE_ID
    assert candidate.subject == (
        f"{PROJECT_RELATIVE}#board/design_settings/rule_severities/track_dangling"
    )
    assert "review the source-order values" in candidate.message
    assert candidate.evidence == {
        "source_path": (PROJECT_RELATIVE,),
        "source_sha256": (digest(project),),
        "kicad_version": ("10.0.8",),
        "project_kind": ("pcb",),
        "drc_severity_key": ("track_dangling",),
        "configured_values_json": ('"warning"', '"ignore"'),
        "occurrence_count": ("2",),
    }


def test_unknown_and_equal_duplicate_values_are_reviewable(tmp_path: Path) -> None:
    observed: list[tuple[str, tuple[str, ...]]] = []

    for fixture in (
        "fault-unknown-duplicate.kicad_pro",
        "fault-same-value-duplicate.kicad_pro",
    ):
        fixture_root, project, config, _ = _project(tmp_path / fixture, fixture)
        candidates = _scan(fixture_root, config, {PROJECT_RELATIVE: digest(project)})
        observed.extend(
            (item.evidence["drc_severity_key"][0], item.evidence["configured_values_json"])
            for item in candidates
        )

    assert observed == [
        ("future_check", ('"warning"', '"ignore"')),
        ("track_dangling", ('"warning"', '"warning"')),
    ]


def test_unique_map_is_quiet_and_direct_reader_remains_strict(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path, "control-unique-warning.kicad_pro")

    assert _scan(root, config, source_hashes) == ()
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        configured_pcb_drc_rule_severity_settings(
            (FIXTURES / "fault-ignore-last.kicad_pro").read_text(encoding="utf-8")
        )


def test_duplicate_json_keys_outside_drc_severity_map_remain_strict(tmp_path: Path) -> None:
    root, project, config, _ = _project(tmp_path, "control-duplicate-outside-map.kicad_pro")

    with pytest.raises(ValueError, match="could not read supported"):
        _scan(root, config, {PROJECT_RELATIVE: digest(project)})


def test_repeated_scan_is_deterministic(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path)

    first = _scan(root, config, source_hashes)
    second = _scan(root, config, source_hashes)

    assert first == second


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


def test_missing_or_unhashed_source_does_not_create_candidate(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    project.unlink()

    assert _scan(root, config, {}) == ()
    with pytest.raises(ValueError, match="disappeared"):
        _scan(root, config, source_hashes)
    project.parent.mkdir(parents=True, exist_ok=True)
    project.write_bytes((FIXTURES / "fault-ignore-last.kicad_pro").read_bytes())
    with pytest.raises(ValueError, match="outside source-bound"):
        _scan(root, config, {})


def test_source_hash_must_match(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    project.write_text(project.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="differ from source-bound"):
        _scan(root, config, source_hashes)


def test_invalid_severity_map_fails_closed(tmp_path: Path) -> None:
    root, project, config, _ = _project(tmp_path)
    project.write_text('{"board":{"design_settings":{"rule_severities":[]}}}', encoding="utf-8")

    with pytest.raises(ValueError, match="could not read supported"):
        _scan(root, config, {PROJECT_RELATIVE: digest(project)})


def test_candidate_fields_cannot_diverge_from_source_settings(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path)
    (candidate,) = _scan(root, config, source_hashes)

    with pytest.raises(ValueError, match="must match source evidence"):
        replace(candidate, subject=f"{candidate.subject}/stale")


def test_parser_retains_canonical_source_order_for_duplicates(tmp_path: Path) -> None:
    _, project, _, _ = _project(tmp_path)

    assert configured_pcb_drc_duplicate_rule_severity_settings(
        project.read_text(encoding="utf-8")
    ) == (
        PcbDrcDuplicateRuleSeveritySetting(
            "track_dangling",
            ('"warning"', '"ignore"'),
        ),
    )
