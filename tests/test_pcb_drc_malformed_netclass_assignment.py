"""Source-bound reviews for malformed PCB netclass assignment shapes."""

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
    configured_pcb_malformed_netclass_assignments,
)
from kicad_tooling.hwrepo.pcb_drc_malformed_netclass_assignment_review import (
    PcbMalformedNetClassAssignmentCandidate,
    source_bound_pcb_malformed_netclass_assignment_candidates,
)

RULE_ID = "pcb.drc_malformed_netclass_assignment"
PROJECT_RELATIVE = "projects/board.kicad_pro"
FIXTURES = Path(__file__).parent / "fixtures/design_lint/pcb-drc-duplicate-net-settings"
FAULT_FIXTURES = (
    "fault-netclass-assignment-array-nonstring.kicad_pro",
    "fault-netclass-assignment-value-number.kicad_pro",
    "fault-netclass-assignment-map-array.kicad_pro",
)
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
    return source_bound_pcb_malformed_netclass_assignment_candidates(
        root,
        config,
        source_hashes,
    )


@pytest.mark.parametrize("fixture", FAULT_FIXTURES)
def test_malformed_fixture_source_hashes_are_reviewed(fixture: str) -> None:
    source = FIXTURES / fixture

    assert (
        hashlib.sha256(source.read_bytes()).hexdigest()
        == {
            "fault-netclass-assignment-array-nonstring.kicad_pro": (
                "30dc2a9893349267ee687712d42f46bf3e34f228f863560fd280699356820c78"
            ),
            "fault-netclass-assignment-value-number.kicad_pro": (
                "d25e8ef51e4057815a4b8c0c560e1f28a0309969df891000a8b84df7b7117c87"
            ),
            "fault-netclass-assignment-map-array.kicad_pro": (
                "f7b10a8cad4c0e305b61e50b43009ea25e9d52a077e96421d9a8fcec62dc026c"
            ),
        }[fixture]
    )


def test_non_string_array_member_is_source_bound(tmp_path: Path) -> None:
    root, project, config, hashes = _project(
        tmp_path,
        "fault-netclass-assignment-array-nonstring.kicad_pro",
    )

    (candidate,) = _scan(root, config, hashes)

    assert isinstance(candidate, PcbMalformedNetClassAssignmentCandidate)
    assert candidate.rule_id == RULE_ID
    assert candidate.subject == (f"{PROJECT_RELATIVE}#net_settings/netclass_assignments/N1")
    assert candidate.source_evidence.source_sha256 == digest(project)
    assert candidate.evidence == {
        "source_path": (PROJECT_RELATIVE,),
        "source_sha256": (digest(project),),
        "kicad_version": ("10.0.8",),
        "project_kind": ("pcb",),
        "observed_json_type": ("array",),
        "net_name": ("N1",),
        "malformed_member_indexes": ("1",),
        "malformed_member_kinds": ("null",),
    }


def test_non_string_assignment_is_source_bound(tmp_path: Path) -> None:
    root, _, config, hashes = _project(
        tmp_path,
        "fault-netclass-assignment-value-number.kicad_pro",
    )

    (candidate,) = _scan(root, config, hashes)

    assert candidate.subject.endswith("#net_settings/netclass_assignments/N1")
    assert candidate.evidence["observed_json_type"] == ("number",)


def test_malformed_assignment_map_is_source_bound(tmp_path: Path) -> None:
    root, project, config, hashes = _project(
        tmp_path,
        "fault-netclass-assignment-map-array.kicad_pro",
    )

    (candidate,) = _scan(root, config, hashes)

    assert candidate.subject == f"{PROJECT_RELATIVE}#net_settings/netclass_assignments"
    assert candidate.source_evidence.source_sha256 == digest(project)
    assert candidate.evidence["observed_json_type"] == ("array",)
    assert "net_name" not in candidate.evidence


@pytest.mark.parametrize(
    ("assignment_map", "expected_type"),
    ((None, "null"), (True, "boolean"), (17, "number"), ("not-a-map", "string")),
)
def test_non_object_assignment_map_json_types_are_reviewed(
    assignment_map: object,
    expected_type: str,
) -> None:
    source = json.loads(
        (FIXTURES / "control-netclass-assignment-array-narrow.kicad_pro").read_text(
            encoding="utf-8"
        )
    )
    source["net_settings"]["netclass_assignments"] = assignment_map

    (assignment,) = configured_pcb_malformed_netclass_assignments(json.dumps(source))

    assert assignment.net_name is None
    assert assignment.observed_json_type == expected_type


@pytest.mark.parametrize(
    ("assignment_value", "expected_type"),
    ((None, "null"), (True, "boolean"), (17, "number"), ({}, "object")),
)
def test_non_legacy_per_net_json_types_are_reviewed(
    assignment_value: object,
    expected_type: str,
) -> None:
    source = json.loads(
        (FIXTURES / "control-netclass-assignment-array-narrow.kicad_pro").read_text(
            encoding="utf-8"
        )
    )
    source["net_settings"]["netclass_assignments"]["N1"] = assignment_value

    (assignment,) = configured_pcb_malformed_netclass_assignments(json.dumps(source))

    assert assignment.net_name == "N1"
    assert assignment.observed_json_type == expected_type


@pytest.mark.parametrize(
    "fixture",
    (
        "control-unique-narrow.kicad_pro",
        "control-netclass-assignment-default.kicad_pro",
        "control-netclass-assignment-array-narrow.kicad_pro",
        "control-netclass-assignment-array-empty.kicad_pro",
    ),
)
def test_legacy_and_current_assignment_forms_are_controls(tmp_path: Path, fixture: str) -> None:
    root, _, config, hashes = _project(tmp_path, fixture)

    assert _scan(root, config, hashes) == ()


def test_empty_legacy_string_is_a_valid_no_assignment_control() -> None:
    source = json.loads((FIXTURES / "control-unique-narrow.kicad_pro").read_text(encoding="utf-8"))
    source["net_settings"]["netclass_assignments"]["N1"] = ""

    assert configured_pcb_malformed_netclass_assignments(json.dumps(source)) == ()


def test_malformed_member_kinds_and_indexes_are_stable() -> None:
    source = json.loads(
        (FIXTURES / "fault-netclass-assignment-array-nonstring.kicad_pro").read_text(
            encoding="utf-8"
        )
    )
    source["net_settings"]["netclass_assignments"]["N1"] = [None, False, 7, ""]

    (assignment,) = configured_pcb_malformed_netclass_assignments(json.dumps(source))

    assert assignment.net_name == "N1"
    assert assignment.observed_json_type == "array"
    assert assignment.malformed_member_indexes == (0, 1, 2, 3)
    assert assignment.malformed_member_kinds == ("null", "boolean", "number", "empty-string")


def test_malformed_assignments_are_sorted_by_exact_net_name() -> None:
    source = json.loads(
        (FIXTURES / "fault-netclass-assignment-value-number.kicad_pro").read_text(encoding="utf-8")
    )
    source["net_settings"]["netclass_assignments"].update({"Z9": None, "A1": [False]})
    forward = configured_pcb_malformed_netclass_assignments(json.dumps(source))
    reversed_source = json.loads(json.dumps(source))
    reversed_source["net_settings"]["netclass_assignments"] = dict(
        reversed(tuple(reversed_source["net_settings"]["netclass_assignments"].items()))
    )

    assert tuple(item.net_name for item in forward) == ("A1", "N1", "Z9")
    assert forward == configured_pcb_malformed_netclass_assignments(json.dumps(reversed_source))


def test_duplicate_equal_malformed_assignment_is_reported_once() -> None:
    document = (FIXTURES / "fault-netclass-assignment-value-number.kicad_pro").read_text(
        encoding="utf-8"
    )
    document = document.replace('"N1":17', '"N1":17,"N1":17', 1)

    assignments = configured_pcb_malformed_netclass_assignments(document)

    assert tuple(item.net_name for item in assignments) == ("N1",)


def test_conflicting_duplicate_assignment_is_left_to_conflict_review() -> None:
    document = (FIXTURES / "fault-netclass-assignment-value-number.kicad_pro").read_text(
        encoding="utf-8"
    )
    document = document.replace('"N1":17', '"N1":17,"N1":["Narrow"]', 1)

    assert configured_pcb_malformed_netclass_assignments(document) == ()


@pytest.mark.parametrize(
    ("version", "kind"),
    (("10.0.5", ProjectKind.PCB), ("10.0.8", ProjectKind.SCHEMATIC)),
)
def test_unmeasured_versions_and_non_pcb_projects_are_out_of_scope(
    tmp_path: Path,
    version: str,
    kind: ProjectKind,
) -> None:
    root, _, config, hashes = _project(
        tmp_path,
        "fault-netclass-assignment-array-nonstring.kicad_pro",
        kicad_version=version,
        kind=kind,
    )

    assert _scan(root, config, hashes) == ()


def test_pcb_only_projects_are_supported(tmp_path: Path) -> None:
    root, _, config, hashes = _project(
        tmp_path,
        "fault-netclass-assignment-array-nonstring.kicad_pro",
        kind=ProjectKind.PCB_ONLY,
    )

    (candidate,) = _scan(root, config, hashes)

    assert candidate.rule_id == RULE_ID


def test_stale_source_hash_does_not_produce_candidate(tmp_path: Path) -> None:
    root, _, config, hashes = _project(
        tmp_path,
        "fault-netclass-assignment-array-nonstring.kicad_pro",
    )
    hashes[PROJECT_RELATIVE] = "0" * 64

    with pytest.raises(ValueError, match="differ from source-bound project inputs"):
        _scan(root, config, hashes)
