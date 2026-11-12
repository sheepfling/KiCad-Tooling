"""Source-bound review tests for PCB assignments to undeclared netclasses."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from kicad_tooling.hwrepo.evidence import digest
from kicad_tooling.hwrepo.models import ProjectConfig, ProjectKind
from kicad_tooling.hwrepo.pcb_drc_duplicate_net_settings_sections import (
    PcbUnresolvedNetClassAssignment,
    configured_pcb_unresolved_netclass_assignments,
)
from kicad_tooling.hwrepo.pcb_drc_unresolved_netclass_assignment_review import (
    PcbUnresolvedNetClassAssignmentCandidate,
    source_bound_pcb_unresolved_netclass_assignment_candidates,
)

RULE_ID = "pcb.drc_unresolved_netclass_assignment"
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
    return source_bound_pcb_unresolved_netclass_assignment_candidates(
        root,
        config,
        source_hashes,
    )


def test_fault_fixture_source_matches_reviewed_hash() -> None:
    source = FIXTURES / "fault-netclass-assignment-undeclared.kicad_pro"

    assert hashlib.sha256(source.read_bytes()).hexdigest() == (
        "19df5a0b5492c549612e921c00e13a36e0ff0b4a56b79e881434c361acd202dd"
    )


def test_case_mismatch_fixture_source_matches_reviewed_hash() -> None:
    source = FIXTURES / "fault-netclass-assignment-case-mismatch.kicad_pro"

    assert hashlib.sha256(source.read_bytes()).hexdigest() == (
        "c9f6b01751f80d867a8c1b45f6ddc236afe44751da31d6464ba50b287ff73551"
    )


@pytest.mark.parametrize(
    ("fixture", "expected_hash"),
    (
        (
            "fault-netclass-assignment-array-undeclared.kicad_pro",
            "0b82fbd7a2cae5413427c493964ac8a03c948d598cb6dea4876180bf37a4edf0",
        ),
        (
            "fault-netclass-assignment-array-mixed.kicad_pro",
            "567b9e54335359274b2fe1a42dacdf5542fcf87ec44fdee78c2219ed4e48c76d",
        ),
    ),
)
def test_current_array_fault_fixture_source_matches_reviewed_hash(
    fixture: str,
    expected_hash: str,
) -> None:
    source = FIXTURES / fixture

    assert hashlib.sha256(source.read_bytes()).hexdigest() == expected_hash


def test_default_assignment_control_fixture_source_matches_reviewed_hash() -> None:
    source = FIXTURES / "control-netclass-assignment-default.kicad_pro"

    assert hashlib.sha256(source.read_bytes()).hexdigest() == (
        "f6a4b45a1be90581b0449355151325138ab0e9c4e6a3252bf0d602577901e467"
    )


def test_undeclared_netclass_assignment_is_source_bound(tmp_path: Path) -> None:
    root, project, config, hashes = _project(
        tmp_path,
        "fault-netclass-assignment-undeclared.kicad_pro",
    )

    (candidate,) = _scan(root, config, hashes)

    assert isinstance(candidate, PcbUnresolvedNetClassAssignmentCandidate)
    assert candidate.rule_id == RULE_ID
    assert candidate.source_evidence.source_sha256 == digest(project)
    assert candidate.evidence == {
        "source_path": (PROJECT_RELATIVE,),
        "source_sha256": (digest(project),),
        "kicad_version": ("10.0.8",),
        "project_kind": ("pcb",),
        "net_name": ("N1",),
        "assigned_class": ("MissingClass",),
        "declared_class_names": ("Default", "Narrow"),
    }
    assert candidate.subject == (f"{PROJECT_RELATIVE}#net_settings/netclass_assignments/N1")


def test_netclass_assignment_name_match_is_case_sensitive(tmp_path: Path) -> None:
    root, _, config, hashes = _project(
        tmp_path,
        "fault-netclass-assignment-case-mismatch.kicad_pro",
    )

    (candidate,) = _scan(root, config, hashes)

    assert candidate.evidence["assigned_class"] == ("narrow",)
    assert candidate.evidence["declared_class_names"] == ("Default", "Narrow")


def test_current_array_assignment_is_source_bound_and_keeps_all_class_names(
    tmp_path: Path,
) -> None:
    root, project, config, hashes = _project(
        tmp_path,
        "fault-netclass-assignment-array-mixed.kicad_pro",
    )

    (candidate,) = _scan(root, config, hashes)

    assert isinstance(candidate, PcbUnresolvedNetClassAssignmentCandidate)
    assert candidate.source_evidence.source_sha256 == digest(project)
    assert candidate.subject == (f"{PROJECT_RELATIVE}#net_settings/netclass_assignments/N1")
    assert candidate.evidence == {
        "source_path": (PROJECT_RELATIVE,),
        "source_sha256": (digest(project),),
        "kicad_version": ("10.0.8",),
        "project_kind": ("pcb",),
        "net_name": ("N1",),
        "assigned_class": ("MissingClass",),
        "assigned_classes": ("Narrow", "MissingClass"),
        "declared_class_names": ("Default", "Narrow"),
    }


@pytest.mark.parametrize(
    ("fixture", "expected_classes"),
    (
        ("fault-netclass-assignment-array-undeclared.kicad_pro", ("MissingClass",)),
        (
            "fault-netclass-assignment-array-mixed.kicad_pro",
            ("Narrow", "MissingClass"),
        ),
    ),
)
def test_unknown_current_array_member_is_reviewed(
    tmp_path: Path,
    fixture: str,
    expected_classes: tuple[str, ...],
) -> None:
    root, _, config, hashes = _project(tmp_path, fixture)

    (candidate,) = _scan(root, config, hashes)

    assert candidate.rule_id == RULE_ID
    assert candidate.evidence["assigned_class"] == ("MissingClass",)
    assert candidate.evidence["assigned_classes"] == expected_classes


@pytest.mark.parametrize(
    "fixture",
    (
        "control-netclass-assignment-array-narrow.kicad_pro",
        "control-netclass-assignment-array-empty.kicad_pro",
    ),
)
def test_declared_and_empty_current_array_assignments_are_controls(
    tmp_path: Path,
    fixture: str,
) -> None:
    root, _, config, hashes = _project(tmp_path, fixture)

    assert _scan(root, config, hashes) == ()


def test_declared_default_assignment_is_a_valid_control(tmp_path: Path) -> None:
    root, _, config, hashes = _project(
        tmp_path,
        "control-netclass-assignment-default.kicad_pro",
    )

    assert _scan(root, config, hashes) == ()


def test_assignments_are_sorted_by_exact_net_name() -> None:
    source = json.loads((FIXTURES / "fault-netclass-assignment-undeclared.kicad_pro").read_text())
    assignments = source["net_settings"]["netclass_assignments"]
    assignments.update({"N3": "OtherMissing", "N4": "MissingClass"})

    results = configured_pcb_unresolved_netclass_assignments(json.dumps(source))
    reversed_source = json.loads(json.dumps(source))
    reversed_source["net_settings"]["netclass_assignments"] = dict(
        reversed(tuple(reversed_source["net_settings"]["netclass_assignments"].items()))
    )
    reversed_results = configured_pcb_unresolved_netclass_assignments(json.dumps(reversed_source))

    assert [(item.net_name, item.assigned_class) for item in results] == [
        ("N1", "MissingClass"),
        ("N3", "OtherMissing"),
        ("N4", "MissingClass"),
    ]
    assert results == reversed_results


def test_current_array_unknown_members_are_ordered_and_deduplicated() -> None:
    source = json.loads(
        (FIXTURES / "fault-netclass-assignment-array-undeclared.kicad_pro").read_text()
    )
    assignment = ["OtherMissing", "MissingClass", "OtherMissing"]
    source["net_settings"]["netclass_assignments"]["N1"] = assignment

    results = configured_pcb_unresolved_netclass_assignments(json.dumps(source))
    reversed_source = json.loads(json.dumps(source))
    reversed_source["net_settings"]["netclass_assignments"] = dict(
        reversed(tuple(reversed_source["net_settings"]["netclass_assignments"].items()))
    )
    reversed_results = configured_pcb_unresolved_netclass_assignments(json.dumps(reversed_source))

    assert [(item.net_name, item.assigned_class) for item in results] == [
        ("N1", "OtherMissing"),
        ("N1", "MissingClass"),
    ]
    assert all(item.assigned_classes == tuple(assignment) for item in results)
    assert results == reversed_results


def test_equal_duplicate_missing_assignment_is_reported_once() -> None:
    document = (FIXTURES / "fault-netclass-assignment-undeclared.kicad_pro").read_text()
    document = document.replace(
        '"N2":"Narrow"',
        '"N2":"Narrow","N5":"MissingClass","N5":"MissingClass"',
    )

    results = configured_pcb_unresolved_netclass_assignments(document)

    assert [(item.net_name, item.assigned_class) for item in results] == [
        ("N1", "MissingClass"),
        ("N5", "MissingClass"),
    ]


def test_conflicting_duplicate_assignment_is_left_to_conflict_review() -> None:
    document = (FIXTURES / "fault-netclass-assignment-undeclared.kicad_pro").read_text()
    document = document.replace(
        '"N1":"MissingClass"',
        '"N1":"MissingClass","N1":"Narrow"',
    )

    results = configured_pcb_unresolved_netclass_assignments(document)

    assert results == ()


@pytest.mark.parametrize(
    "mutate",
    (
        lambda source: source.update({"net_settings": [source["net_settings"]]}),
        lambda source: source["net_settings"].update({"classes": []}),
        lambda source: source["net_settings"].update(
            {"classes": [{"clearance": 0.2}, source["net_settings"]["classes"][1]]}
        ),
    ),
)
def test_incomplete_or_ambiguous_class_inventory_stays_quiet(mutate) -> None:
    source = json.loads((FIXTURES / "fault-netclass-assignment-undeclared.kicad_pro").read_text())
    mutate(source)

    assert configured_pcb_unresolved_netclass_assignments(json.dumps(source)) == ()


@pytest.mark.parametrize(
    ("kicad_version", "kind"),
    (("10.0.5", ProjectKind.PCB), ("10.0.8", ProjectKind.SCHEMATIC)),
)
def test_unmeasured_versions_and_non_pcb_projects_are_out_of_scope(
    tmp_path: Path,
    kicad_version: str,
    kind: ProjectKind,
) -> None:
    root, _, config, hashes = _project(
        tmp_path,
        "fault-netclass-assignment-undeclared.kicad_pro",
        kicad_version=kicad_version,
        kind=kind,
    )

    assert _scan(root, config, hashes) == ()


def test_pcb_only_projects_are_supported(tmp_path: Path) -> None:
    root, _, config, hashes = _project(
        tmp_path,
        "fault-netclass-assignment-undeclared.kicad_pro",
        kind=ProjectKind.PCB_ONLY,
    )

    (candidate,) = _scan(root, config, hashes)

    assert candidate.rule_id == RULE_ID


def test_stale_source_hash_does_not_produce_candidate(tmp_path: Path) -> None:
    root, _, config, hashes = _project(
        tmp_path,
        "fault-netclass-assignment-undeclared.kicad_pro",
    )
    hashes[PROJECT_RELATIVE] = "0" * 64

    with pytest.raises(ValueError, match="differ from source-bound project inputs"):
        _scan(root, config, hashes)


def test_assignment_record_rejects_a_declared_class_as_unresolved() -> None:
    with pytest.raises(ValueError, match="must name an undeclared class"):
        PcbUnresolvedNetClassAssignment(
            net_name="N1",
            assigned_class="Default",
            declared_class_names=("Default", "Narrow"),
        )
