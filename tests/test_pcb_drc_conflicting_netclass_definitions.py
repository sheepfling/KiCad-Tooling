"""Source-bound review of conflicting PCB netclass definitions."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_drc_duplicate_net_settings_sections import (
    configured_pcb_conflicting_netclass_settings,
)
from kicad_tooling.hwrepo.pcb_drc_netclass_conflict_review import (
    PcbNetClassConflictCandidate,
    source_bound_pcb_netclass_conflict_candidates,
)

RULE_ID = "pcb.drc_conflicting_netclass_definitions"
PROJECT_RELATIVE = "projects/controller.kicad_pro"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-duplicate-net-settings"
pytestmark = [
    pytest.mark.design_lint,
    pytest.mark.pcb_lint,
    pytest.mark.evidence_lint,
    pytest.mark.design_lint_rule(rule_id=RULE_ID),
]


def _project(
    tmp_path: Path,
    fixture: str,
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
    return source_bound_pcb_netclass_conflict_candidates(root, config, source_hashes)


@pytest.mark.parametrize(
    "fixture,scope,expected_clearances",
    (
        ("fault-netclass-list-narrow-last.kicad_pro", "classes_member", (0.2, 0.05)),
        ("fault-netclass-list-wide-last.kicad_pro", "classes_member", (0.05, 0.2)),
        ("fault-netclass-name-narrow-last.kicad_pro", "class_name", (0.2, 0.05)),
        ("fault-netclass-name-wide-last.kicad_pro", "class_name", (0.05, 0.2)),
    ),
)
def test_conflicting_netclass_values_are_source_bound(
    tmp_path: Path,
    fixture: str,
    scope: str,
    expected_clearances: tuple[float, float],
) -> None:
    root, project, config, hashes = _project(tmp_path, fixture)

    (candidate,) = _scan(root, config, hashes)

    assert isinstance(candidate, PcbNetClassConflictCandidate)
    assert candidate.rule_id == RULE_ID
    assert candidate.source_evidence.source_sha256 == digest(project)
    assert candidate.evidence["source_sha256"] == (digest(project),)
    assert candidate.evidence["conflict_scope"] == (scope,)
    assert len(candidate.evidence["source_order_values_json"]) == 2
    if scope == "class_name":
        assert candidate.evidence["class_name"] == ("Narrow",)
        values = tuple(
            json.loads(value) for value in candidate.evidence["source_order_values_json"]
        )
        assert tuple(value["clearance"] for value in values) == expected_clearances
    else:
        values = tuple(
            json.loads(value) for value in candidate.evidence["source_order_values_json"]
        )
        assert tuple(value[1]["clearance"] for value in values) == expected_clearances


def test_equal_duplicate_classes_member_is_quiet(tmp_path: Path) -> None:
    root, _, config, hashes = _project(tmp_path, "control-identical-netclass-list.kicad_pro")

    assert _scan(root, config, hashes) == ()
    assert (
        configured_pcb_conflicting_netclass_settings(
            (FIXTURES / "control-identical-netclass-list.kicad_pro").read_text(encoding="utf-8")
        )
        == ()
    )


def test_unique_netclass_list_is_quiet_and_unrelated_duplicates_stay_strict(
    tmp_path: Path,
) -> None:
    root, _, config, hashes = _project(tmp_path, "control-unique-narrow.kicad_pro")

    assert _scan(root, config, hashes) == ()
    with pytest.raises(ValueError, match="Duplicate JSON key at <root>: other"):
        configured_pcb_conflicting_netclass_settings('{"other":1,"other":2}')


@pytest.mark.parametrize("version", ("10.0.0", "10.0.5", "10.0.7", "10.0.9", "11.0.0"))
def test_unmeasured_kicad_versions_are_out_of_scope(tmp_path: Path, version: str) -> None:
    root, _, config, hashes = _project(
        tmp_path,
        "fault-netclass-list-wide-last.kicad_pro",
        kicad_version=version,
    )

    assert _scan(root, config, hashes) == ()


@pytest.mark.parametrize(
    "kind",
    (ProjectKind.SCHEMATIC, ProjectKind.SYSTEM_WIRING, ProjectKind.HARNESS_INTERFACE),
)
def test_non_pcb_projects_are_out_of_scope(tmp_path: Path, kind: ProjectKind) -> None:
    root, _, config, hashes = _project(
        tmp_path,
        "fault-netclass-list-wide-last.kicad_pro",
        kind=kind,
    )

    assert _scan(root, config, hashes) == ()


def test_pcb_only_projects_are_supported(tmp_path: Path) -> None:
    root, _, config, hashes = _project(
        tmp_path,
        "fault-netclass-list-wide-last.kicad_pro",
        kind=ProjectKind.PCB_ONLY,
    )

    assert tuple(item.rule_id for item in _scan(root, config, hashes)) == (RULE_ID,)


def test_repeated_scans_preserve_class_and_list_order(tmp_path: Path) -> None:
    root, _, config, hashes = _project(tmp_path, "fault-netclass-list-wide-last.kicad_pro")

    first = _scan(root, config, hashes)
    second = _scan(root, config, hashes)

    assert first == second
    values = tuple(json.loads(value) for value in first[0].evidence["source_order_values_json"])
    assert tuple(item[1]["clearance"] for item in values) == (0.05, 0.2)


def test_stale_source_inventory_blocks_the_finding(tmp_path: Path) -> None:
    root, project, config, hashes = _project(tmp_path, "fault-netclass-list-wide-last.kicad_pro")
    project.write_text(project.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="differ from source-bound project inputs"):
        _scan(root, config, hashes)
