"""Source-bound review of unknown saved PCB DRC severity keys."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_drc_severity_key_catalog import (
    KICAD_10_0_8_DRC_SEVERITY_KEYS,
    KICAD_10_0_8_DRC_SEVERITY_MIGRATION_KEYS,
    PCB_DRC_RULE_SEVERITY_KEYS_BY_KICAD_VERSION,
)
from kicad_tooling.hwrepo.pcb_drc_unknown_severity_key_review import (
    PcbDrcUnknownSeverityKeyCandidate,
    source_bound_pcb_drc_unknown_severity_key_candidates,
)

RULE_ID = "pcb.drc_unknown_severity_key"
PROJECT_RELATIVE = "projects/board.kicad_pro"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-unknown-severity-key"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _project(
    tmp_path: Path,
    fixture: str = "fault.kicad_pro",
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
    return source_bound_pcb_drc_unknown_severity_key_candidates(root, config, source_hashes)


def test_key_catalog_is_exactly_scoped_to_audited_kicad_1008() -> None:
    assert set(PCB_DRC_RULE_SEVERITY_KEYS_BY_KICAD_VERSION) == {"10.0.8"}
    assert PCB_DRC_RULE_SEVERITY_KEYS_BY_KICAD_VERSION["10.0.8"] == (
        KICAD_10_0_8_DRC_SEVERITY_KEYS | KICAD_10_0_8_DRC_SEVERITY_MIGRATION_KEYS
    )
    assert len(KICAD_10_0_8_DRC_SEVERITY_KEYS) == 62
    assert len(KICAD_10_0_8_DRC_SEVERITY_MIGRATION_KEYS) == 3


def test_unknown_key_creates_source_bound_review_candidate(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)

    candidates = _scan(root, config, source_hashes)

    assert len(candidates) == 1
    (candidate,) = candidates
    assert isinstance(candidate, PcbDrcUnknownSeverityKeyCandidate)
    assert candidate.rule_id == RULE_ID
    assert candidate.subject == (
        f"{PROJECT_RELATIVE}#board/design_settings/rule_severities/track_dangling_typo"
    )
    assert "may not affect native DRC" in candidate.message
    assert candidate.evidence == {
        "source_path": (PROJECT_RELATIVE,),
        "source_sha256": (digest(project),),
        "kicad_version": ("10.0.8",),
        "project_kind": ("pcb",),
        "drc_severity_key": ("track_dangling_typo",),
        "configured_value_json": ('"ignore"',),
    }


def test_all_current_keys_and_migration_aliases_are_valid_controls(tmp_path: Path) -> None:
    root, project, config, _ = _project(tmp_path, "control.kicad_pro")
    settings = {key: "ignore" for key in KICAD_10_0_8_DRC_SEVERITY_KEYS}
    settings.update({key: True for key in KICAD_10_0_8_DRC_SEVERITY_MIGRATION_KEYS})
    project.write_text(
        json.dumps(
            {"board": {"design_settings": {"rule_severities": settings}}, "meta": {"version": 1}},
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    assert _scan(root, config, {PROJECT_RELATIVE: digest(project)}) == ()


def test_unknown_keys_are_sorted_and_json_values_are_canonical(tmp_path: Path) -> None:
    root, project, config, _ = _project(tmp_path)
    first_settings = {
        "z_future": {"b": 2, "a": 1},
        "a_future": ["warning", {"z": False, "a": None}],
    }
    observed: list[tuple[tuple[str, str], ...]] = []
    for settings in (first_settings, dict(reversed(tuple(first_settings.items())))):
        project.write_text(
            json.dumps({"board": {"design_settings": {"rule_severities": settings}}}),
            encoding="utf-8",
        )
        candidates = _scan(root, config, {PROJECT_RELATIVE: digest(project)})
        observed.append(
            tuple(
                (
                    item.source_evidence.configured_setting.check_id,
                    item.source_evidence.configured_setting.configured_value_json,
                )
                for item in candidates
                if isinstance(item, PcbDrcUnknownSeverityKeyCandidate)
            )
        )

    assert (
        observed[0]
        == observed[1]
        == (
            ("a_future", '["warning",{"a":null,"z":false}]'),
            ("z_future", '{"a":1,"b":2}'),
        )
    )


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5", "10.0.7", "10.0.9", "11.0.0"))
def test_unreviewed_kicad_versions_are_out_of_scope(tmp_path: Path, version: str) -> None:
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


def test_source_hash_is_required_and_must_match(tmp_path: Path) -> None:
    root, project, config, source_hashes = _project(tmp_path)
    with pytest.raises(ValueError, match="outside source-bound"):
        _scan(root, config, {})

    project.write_text(project.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differ from source-bound"):
        _scan(root, config, source_hashes)


def test_invalid_rule_severity_map_fails_closed(tmp_path: Path) -> None:
    root, project, config, _ = _project(tmp_path)
    project.write_text('{"board":{"design_settings":{"rule_severities":[]}}}', encoding="utf-8")

    with pytest.raises(ValueError, match="could not read supported"):
        _scan(root, config, {PROJECT_RELATIVE: digest(project)})


def test_candidate_fields_cannot_diverge_from_source_settings(tmp_path: Path) -> None:
    root, _, config, source_hashes = _project(tmp_path)
    (candidate,) = _scan(root, config, source_hashes)

    with pytest.raises(ValueError, match="must match source evidence"):
        replace(candidate, subject=f"{candidate.subject}/stale")
